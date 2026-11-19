import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from petcare.database.export_tenant import (
    EXPORT_MAGIC,
    _EncryptingBinaryWriter,
    _cell,
    _csv_cell,
    _media_files,
    _write_media,
    decrypt_tenant_export,
    encrypt_legacy_tenant_export,
    verify_encrypted_tenant_export,
    verify_tenant_export,
)
from petcare.secure_bundle import ENCRYPTED_FILE_HEADER


class TenantMediaExportTests(unittest.TestCase):
    def test_csv_export_neutralizes_formula_like_text_without_changing_numbers(self):
        for text in (
            "=HYPERLINK(\"https://example.invalid\",\"open\")",
            "  +SUM(A1:A2)",
            "\t-1+1",
            "\x00=HYPERLINK(\"https://example.invalid\",\"open\")",
            "@SUM(A1:A2)",
        ):
            with self.subTest(text=text):
                self.assertEqual(_csv_cell(text), "'" + text)
        self.assertEqual(_csv_cell("PetCare supplies"), "PetCare supplies")
        self.assertEqual(_csv_cell(-25), -25)
        self.assertEqual(_csv_cell(Decimal("-25.50")), "-25.50")

    def test_export_timestamps_are_explicitly_utc(self):
        self.assertEqual(
            _cell(datetime(2026, 10, 18, 6, 30)),
            "2026-10-18 06:30:00+00:00",
        )
        aware = datetime(2026, 10, 18, 9, 30, tzinfo=timezone(timedelta(hours=3)))
        self.assertEqual(_cell(aware), "2026-10-18 06:30:00+00:00")

    def test_export_reads_tenant_media_through_configured_storage_stream(self):
        filename = "d" * 32 + ".jpg"
        contents = b"private object photo"
        storage = _MemoryStorage(contents)
        connection = _MediaConnection((filename,))
        with patch("petcare.database.export_tenant.get_media_storage", return_value=storage):
            media = _media_files(connection, tenant_id=7)

        self.assertEqual(
            media,
            [
                (storage, filename, f"media/products/{filename}"),
                (storage, filename, f"media/pets/{filename}"),
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "media.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                digest = _write_media(
                    archive, storage, filename, f"media/products/{filename}"
                )
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.read(f"media/products/{filename}"), contents)
            self.assertEqual(digest, hashlib.sha256(contents).hexdigest())

    def test_export_rejects_unsafe_database_media_filename(self):
        connection = _MediaConnection(("../../private.jpg",))
        with patch("petcare.database.export_tenant.get_media_storage", return_value=_MemoryStorage(b"")):
            with self.assertRaisesRegex(ValueError, "Unsafe stored media"):
                _media_files(connection, tenant_id=7)


class _MediaCursor:
    def __init__(self, product_filename):
        self.product_filename = product_filename
        self.query = ""

    def execute(self, query, _params):
        self.query = query

    def fetchall(self):
        if "FROM products" in self.query:
            return [(self.product_filename,)]
        if "FROM pets" in self.query:
            return [(self.product_filename,)] if self.product_filename else []
        return []

    def close(self):
        pass


class _MediaConnection:
    def __init__(self, product_filenames):
        self.product_filenames = product_filenames
        self.query_index = 0

    def cursor(self):
        if self.query_index == 0:
            filename = self.product_filenames[0] if self.product_filenames else None
        else:
            filename = self.product_filenames[0] if self.product_filenames else None
        self.query_index += 1
        return _MediaCursor(filename)


class _MemoryStorage:
    def __init__(self, contents):
        self.contents = contents

    @contextmanager
    def open(self, _filename):
        yield BytesIO(self.contents)


class TenantExportVerificationTests(unittest.TestCase):
    PASSPHRASE = "Unit-export-passphrase-2026"

    def _write_archive(
        self, path, payload_name="data/customers.csv", payload=b"id,name\n1,Test\n", checksum_payload=None
    ):
        checksum_payload = payload if checksum_payload is None else checksum_payload
        manifest = {
            "format": "petcare-tenant-export-v1",
            "tenant_slug": "main",
            "tables": {"customers": 1},
            "media_files": 0,
            "sha256": {payload_name: hashlib.sha256(checksum_payload).hexdigest()},
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(payload_name, payload)
            archive.writestr("manifest.json", json.dumps(manifest))

    def _encrypt_archive(self, source_path, encrypted_path, passphrase=None):
        passphrase = self.PASSPHRASE if passphrase is None else passphrase
        with Path(encrypted_path).open("wb") as destination:
            writer = _EncryptingBinaryWriter(destination, passphrase, EXPORT_MAGIC)
            with Path(source_path).open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    writer.write(block)
            writer.finish()

    def test_verifies_manifest_and_payload_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.zip"
            self._write_archive(path)

            manifest = verify_tenant_export(path)

            self.assertEqual(manifest["tenant_slug"], "main")

    def test_rejects_payload_that_does_not_match_manifest_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.zip"
            self._write_archive(
                path, payload=b"id,name\n1,Tampered\n", checksum_payload=b"id,name\n1,Test\n"
            )

            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_tenant_export(path)

    def test_rejects_unsafe_archive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.zip"
            self._write_archive(path, "../outside.csv", b"private\n")

            with self.assertRaisesRegex(ValueError, "unsafe path"):
                verify_tenant_export(path)

    def test_authenticates_and_verifies_encrypted_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "source.zip"
            encrypted_path = Path(directory) / "store.pcarexport"
            self._write_archive(archive_path)
            self._encrypt_archive(archive_path, encrypted_path)

            self.assertNotIn(b"id,name", encrypted_path.read_bytes())
            manifest = verify_encrypted_tenant_export(encrypted_path, self.PASSPHRASE)

            self.assertEqual(manifest["tenant_slug"], "main")

    def test_wrong_passphrase_does_not_create_plaintext_output(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "source.zip"
            encrypted_path = Path(directory) / "store.pcarexport"
            plaintext_path = Path(directory) / "decrypted.zip"
            self._write_archive(archive_path)
            self._encrypt_archive(archive_path, encrypted_path)

            with self.assertRaisesRegex(ValueError, "Passphrase is incorrect"):
                decrypt_tenant_export(encrypted_path, plaintext_path, "Wrong-passphrase-2026")

            self.assertFalse(plaintext_path.exists())

    def test_modified_ciphertext_fails_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "source.zip"
            encrypted_path = Path(directory) / "store.pcarexport"
            self._write_archive(archive_path)
            self._encrypt_archive(archive_path, encrypted_path)
            encrypted_bytes = bytearray(encrypted_path.read_bytes())
            encrypted_bytes[ENCRYPTED_FILE_HEADER.size + 5] ^= 0x01
            encrypted_path.write_bytes(encrypted_bytes)

            with self.assertRaisesRegex(ValueError, "modified"):
                verify_encrypted_tenant_export(encrypted_path, self.PASSPHRASE)

    def test_decryption_is_private_and_checksum_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "source.zip"
            encrypted_path = Path(directory) / "store.pcarexport"
            plaintext_path = Path(directory) / "decrypted.zip"
            self._write_archive(archive_path)
            self._encrypt_archive(archive_path, encrypted_path)

            decrypt_tenant_export(encrypted_path, plaintext_path, self.PASSPHRASE)

            self.assertEqual(stat.S_IMODE(plaintext_path.stat().st_mode), 0o600)
            self.assertEqual(verify_tenant_export(plaintext_path)["tenant_slug"], "main")

    def test_legacy_plain_export_can_be_verified_and_encrypted(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = Path(directory) / "legacy-export.zip"
            encrypted_path = Path(directory) / "migrated-export.pcarexport"
            self._write_archive(legacy_path)

            encrypt_legacy_tenant_export(legacy_path, encrypted_path, self.PASSPHRASE)

            self.assertTrue(legacy_path.is_file())
            self.assertEqual(
                verify_encrypted_tenant_export(encrypted_path, self.PASSPHRASE)["tenant_slug"],
                "main",
            )


if __name__ == "__main__":
    unittest.main()
