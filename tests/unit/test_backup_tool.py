import io
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import petcare_backup
from petcare.secure_bundle import AuthenticatedEncryptingWriter, ENCRYPTED_FILE_HEADER


class BackupToolTests(unittest.TestCase):
    PASSPHRASE = "Backup-test-passphrase-2026"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pet_dir = self.root / "pet-images"
        self.product_dir = self.root / "product-images"
        self.pet_dir.mkdir()
        self.product_dir.mkdir()
        (self.pet_dir / "pet-demo.jpg").write_bytes(b"synthetic pet image")
        (self.product_dir / "product-demo.jpg").write_bytes(b"synthetic product image")
        self.archive = self.root / "petcare-test.pcarebackup"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_backup(self):
        captured = {}

        def write_synthetic_dump(command, destination, *, label, input_data=None):
            captured["command"] = command
            captured["input_data"] = input_data
            destination.write_bytes(b"-- synthetic database dump\n")

        with (
            patch.object(petcare_backup.Config, "PET_IMAGE_DIR", str(self.pet_dir)),
            patch.object(petcare_backup.Config, "PRODUCT_IMAGE_DIR", str(self.product_dir)),
            patch.object(petcare_backup, "_compose_command", return_value=["docker", "compose"]),
            patch.object(petcare_backup, "_mysql_option_file", return_value=b"[client]\n"),
            patch.object(petcare_backup, "_run_to_file", side_effect=write_synthetic_dump),
        ):
            result = petcare_backup.create_backup(
                self.archive, "petcare_fixture", "host", self.PASSPHRASE
            )
        return result, captured

    def _encrypt_plain_archive(self, source_path, encrypted_path):
        with Path(encrypted_path).open("wb") as destination:
            writer = AuthenticatedEncryptingWriter(
                destination, self.PASSPHRASE, petcare_backup.BACKUP_MAGIC
            )
            with Path(source_path).open("rb") as source:
                while block := source.read(1024 * 1024):
                    writer.write(block)
            writer.finish()

    def test_local_backup_refuses_s3_media_to_prevent_incomplete_bundle(self):
        with patch.object(petcare_backup.Config, "MEDIA_STORAGE_BACKEND", "s3", create=True):
            with self.assertRaisesRegex(petcare_backup.BackupError, "filesystem"):
                petcare_backup.create_backup(
                    self.archive, "petcare_fixture", "host", self.PASSPHRASE
                )
        self.assertFalse(self.archive.exists())

    def test_create_and_verify_private_bundle_with_database_and_images(self):
        result, _captured = self._create_synthetic_backup()

        verified = petcare_backup.verify_backup(result, self.PASSPHRASE)

        self.assertEqual(verified["database"], "petcare_fixture")
        self.assertEqual(verified["media_entries"], 4)
        self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o600)

        plaintext = self.root / "decrypted.tar.gz"
        petcare_backup.decrypt_backup(result, plaintext, self.PASSPHRASE)
        self.assertEqual(stat.S_IMODE(plaintext.stat().st_mode), 0o600)

    def test_backup_sends_escaped_root_options_over_stdin_not_arguments(self):
        secret = 'synthetic"\\password#'
        captured = {}

        def write_synthetic_dump(command, destination, *, label, input_data=None):
            captured["command"] = command
            captured["input_data"] = input_data
            destination.write_bytes(b"-- synthetic database dump\n")

        with (
            patch.object(petcare_backup.Config, "PET_IMAGE_DIR", str(self.pet_dir)),
            patch.object(petcare_backup.Config, "PRODUCT_IMAGE_DIR", str(self.product_dir)),
            patch.object(petcare_backup, "_compose_command", return_value=["docker", "compose"]),
            patch.object(petcare_backup, "_run_to_file", side_effect=write_synthetic_dump),
            patch.dict(os.environ, {"MYSQL_ROOT_PASSWORD": secret}),
        ):
            petcare_backup.create_backup(
                self.archive, "petcare_fixture", "host", self.PASSPHRASE
            )

        self.assertNotIn(secret, " ".join(captured["command"]))
        options = captured["input_data"].decode("utf-8")
        self.assertNotIn(secret, options)
        self.assertIn('password="synthetic\\"\\\\password#"', options)

    def test_refuses_to_overwrite_an_existing_backup(self):
        self.archive.write_bytes(b"existing backup")
        with patch.object(petcare_backup, "_compose_command") as compose_command:
            with self.assertRaisesRegex(petcare_backup.BackupError, "Không ghi đè"):
                petcare_backup.create_backup(
                    self.archive, "petcare_fixture", "host", self.PASSPHRASE
                )
        compose_command.assert_not_called()

    def test_verifier_detects_payload_tampering(self):
        original, _captured = self._create_synthetic_backup()
        original_plaintext = self.root / "original.tar.gz"
        corrupted_plaintext = self.root / "corrupted.tar.gz"
        corrupted = self.root / "corrupted.pcarebackup"
        petcare_backup.decrypt_backup(original, original_plaintext, self.PASSPHRASE)

        with tarfile.open(original_plaintext, "r:gz") as source:
            contents = {
                member.name: source.extractfile(member).read()
                for member in source.getmembers()
            }
        contents["database.sql"] += b"tampered"
        with tarfile.open(corrupted_plaintext, "w:gz") as destination:
            for name, content in contents.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                destination.addfile(info, io.BytesIO(content))

        self._encrypt_plain_archive(corrupted_plaintext, corrupted)

        with self.assertRaisesRegex(petcare_backup.BackupError, "Checksum không khớp"):
            petcare_backup.verify_backup(corrupted, self.PASSPHRASE)

    def test_wrong_passphrase_does_not_create_decrypted_backup(self):
        encrypted, _captured = self._create_synthetic_backup()
        plaintext = self.root / "wrong-password.tar.gz"

        with self.assertRaisesRegex(petcare_backup.BackupError, "Passphrase is incorrect"):
            petcare_backup.decrypt_backup(encrypted, plaintext, "Wrong-backup-passphrase")

        self.assertFalse(plaintext.exists())

    def test_encrypted_backup_rejects_modified_ciphertext(self):
        encrypted, _captured = self._create_synthetic_backup()
        contents = bytearray(encrypted.read_bytes())
        contents[ENCRYPTED_FILE_HEADER.size + 7] ^= 0x01
        encrypted.write_bytes(contents)

        with self.assertRaisesRegex(petcare_backup.BackupError, "was modified"):
            petcare_backup.verify_backup(encrypted, self.PASSPHRASE)

    def test_legacy_plain_backup_can_be_verified_and_encrypted(self):
        encrypted, _captured = self._create_synthetic_backup()
        legacy_plaintext = self.root / "legacy-backup.tar.gz"
        migrated = self.root / "migrated-backup.pcarebackup"
        petcare_backup.decrypt_backup(encrypted, legacy_plaintext, self.PASSPHRASE)

        petcare_backup.encrypt_legacy_backup(legacy_plaintext, migrated, self.PASSPHRASE)

        self.assertTrue(legacy_plaintext.is_file())
        self.assertEqual(
            petcare_backup.verify_backup(migrated, self.PASSPHRASE)["database"],
            "petcare_fixture",
        )

    def test_media_verifier_rejects_path_traversal(self):
        malicious = self.root / "malicious-media.tar.gz"
        with tarfile.open(malicious, "w:gz") as archive:
            info = tarfile.TarInfo("pet-images")
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
            info = tarfile.TarInfo("pet-images/../../outside.jpg")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))

        with self.assertRaisesRegex(petcare_backup.BackupError, "Đường dẫn không an toàn"):
            petcare_backup._validate_media_archive(malicious)


if __name__ == "__main__":
    unittest.main()
