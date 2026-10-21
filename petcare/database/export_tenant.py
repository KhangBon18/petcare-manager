"""Export one store's records and images into a private, verifiable ZIP bundle."""

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import stat
import zipfile

from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.repositories.base import fetch_one
from petcare.secure_bundle import (
    AuthenticatedEncryptingWriter as _EncryptingBinaryWriter,
    decrypt_to_private_temp,
    validate_passphrase,
)
from petcare.vision.media_storage import SAFE_MEDIA_NAME, get_media_storage, media_tenant_id


BATCH_SIZE = 500
EXPORT_MAGIC = b"PCEXP001"
TABLE_EXPORTS = (
    ("memberships.csv", "SELECT u.id user_id, u.username, u.email, u.email_verified_at, "
     "u.full_name, tu.role, tu.active, tu.created_at "
     "FROM tenant_users tu JOIN users u ON u.id = tu.user_id "
     "WHERE tu.tenant_id = %s ORDER BY u.username"),
    ("customers.csv", "SELECT id, full_name, phone, address, active, created_at, updated_at "
     "FROM customers WHERE tenant_id = %s ORDER BY id"),
    ("products.csv", "SELECT id, code, name, category, description, unit_price, stock_qty, "
     "reorder_level, photo_filename, active, created_at, updated_at "
     "FROM products WHERE tenant_id = %s ORDER BY id"),
    ("pets.csv", "SELECT id, code, name, species, breed, sex, birth_date, weight_kg, coat_color, "
     "eye_color, appearance_tags, photo_filename, photo_descriptor, sale_price, sale_status, "
     "buyer_id, sold_at, created_at, updated_at FROM pets WHERE tenant_id = %s ORDER BY id"),
    ("invoices.csv", "SELECT id, customer_id, created_by, created_at, status, currency_code, paid_at, note "
     "FROM invoices WHERE tenant_id = %s ORDER BY id"),
    ("invoice_items.csv", "SELECT id, invoice_id, item_type, product_id, pet_id, item_code_snapshot, "
     "name_snapshot, unit_price, quantity, line_total FROM invoice_items "
     "WHERE tenant_id = %s ORDER BY invoice_id, id"),
    ("stock_movements.csv", "SELECT id, product_id, quantity_delta, reason, created_by, invoice_id, created_at "
     "FROM stock_movements WHERE tenant_id = %s ORDER BY id"),
    ("audit_events.csv", "SELECT e.id, u.username actor_username, e.event_type, e.entity_type, "
     "e.entity_id, e.summary, e.details, e.created_at FROM audit_events e "
     "JOIN users u ON u.id = e.actor_user_id WHERE e.tenant_id = %s ORDER BY e.id"),
    ("invitations.csv", "SELECT i.id, i.email, i.role, creator.username created_by_username, "
     "acceptor.username accepted_by_username, i.created_at, i.expires_at, i.accepted_at, i.revoked_at "
     "FROM tenant_invitations i JOIN users creator ON creator.id = i.created_by "
     "LEFT JOIN users acceptor ON acceptor.id = i.accepted_by "
     "WHERE i.tenant_id = %s ORDER BY i.id"),
    ("owner_transfers.csv", "SELECT tr.id, requester.username requested_by_username, "
     "target.username target_username, tr.created_at, tr.expires_at, tr.accepted_at, tr.cancelled_at "
     "FROM tenant_owner_transfers tr "
     "JOIN users requester ON requester.id = tr.requested_by "
     "JOIN users target ON target.id = tr.target_user_id "
     "WHERE tr.tenant_id = %s ORDER BY tr.id"),
)


class _HashingTextWriter:
    """Hash UTF-8 CSV bytes as csv.writer streams them into a ZIP member."""

    def __init__(self, binary_stream):
        self._text = io.TextIOWrapper(binary_stream, encoding="utf-8", newline="")
        self.digest = hashlib.sha256()

    def write(self, value):
        self.digest.update(value.encode("utf-8"))
        return self._text.write(value)

    def flush(self):
        self._text.flush()

    def finish(self):
        self._text.flush()
        self._text.detach()


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        # MySQL DATETIME is stored UTC-naive; make that contract explicit in CSV/JSON.
        instant = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return instant.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _csv_cell(value):
    """Keep user-controlled CSV text from becoming spreadsheet formulas.

    Numeric/date values retain their original representation. For text and
    bytes, prefix an apostrophe when the first non-whitespace character is a
    formula marker; CSV quoting alone does not prevent spreadsheet execution.
    """
    cell = _cell(value)
    if isinstance(value, (str, bytes)) and isinstance(cell, str):
        index = 0
        while index < len(cell) and (
            cell[index].isspace()
            or ord(cell[index]) < 0x20
            or 0x7F <= ord(cell[index]) <= 0x9F
        ):
            index += 1
        if index < len(cell) and cell[index] in "=+-@":
            return "'" + cell
    return cell


def _write_csv(connection, archive, archive_name, query, tenant_id):
    cursor = connection.cursor(dictionary=True, buffered=False)
    try:
        cursor.execute(query, (tenant_id,))
        fieldnames = [column[0] for column in cursor.description]
        count = 0
        with archive.open(archive_name, "w") as binary_stream:
            writer_stream = _HashingTextWriter(binary_stream)
            writer = csv.DictWriter(writer_stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            while True:
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    writer.writerow({key: _csv_cell(value) for key, value in row.items()})
                    count += 1
            writer_stream.finish()
            checksum = writer_stream.digest.hexdigest()
        return count, checksum
    finally:
        cursor.close()


def _media_files(connection, tenant_id):
    cursor = connection.cursor()
    try:
        files = []
        for table, category, prefix in (
            ("products", "products", "media/products"),
            ("pets", "pets", "media/pets"),
        ):
            storage = get_media_storage(Config, category)
            cursor.execute(
                f"SELECT DISTINCT photo_filename FROM {table} "
                "WHERE tenant_id = %s AND photo_filename IS NOT NULL ORDER BY photo_filename",
                (tenant_id,),
            )
            for (filename,) in cursor.fetchall():
                if not isinstance(filename, str) or not SAFE_MEDIA_NAME.fullmatch(filename):
                    raise ValueError(f"Unsafe stored media filename in {table}.")
                scoped_tenant_id = media_tenant_id(filename)
                if scoped_tenant_id is not None and scoped_tenant_id != tenant_id:
                    raise ValueError(f"Tenant-scoped media reference mismatch in {table}.")
                files.append((storage, filename, f"{prefix}/{filename}"))
        return files
    finally:
        cursor.close()


def _write_media(archive, storage, filename, archive_name):
    digest = hashlib.sha256()
    with storage.open(filename) as source, archive.open(archive_name, "w") as target:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            target.write(block)
            digest.update(block)
    return digest.hexdigest()


def verify_tenant_export(archive_path):
    """Validate ZIP structure, tenant-export manifest and every payload checksum."""
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Export archive contains duplicate filenames.")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or "\\" in name or ".." in path.parts:
                raise ValueError("Export archive contains an unsafe path.")
        corrupt_member = archive.testzip()
        if corrupt_member:
            raise zipfile.BadZipFile(f"Archive CRC verification failed at {corrupt_member}.")
        if "manifest.json" not in names:
            raise ValueError("Export manifest is missing.")
        manifest_info = archive.getinfo("manifest.json")
        if manifest_info.file_size > 1_000_000:
            raise ValueError("Export manifest is too large.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "petcare-tenant-export-v1":
            raise ValueError("Unsupported tenant-export format.")
        expected = manifest.get("sha256")
        if not isinstance(expected, dict):
            raise ValueError("Export checksums are missing.")
        payload_names = set(names) - {"manifest.json"}
        if payload_names != set(expected):
            raise ValueError("Export contents do not match the manifest.")
        for name, expected_digest in expected.items():
            digest = hashlib.sha256()
            with archive.open(name, "r") as member:
                for block in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected_digest:
                raise ValueError(f"Export checksum mismatch: {name}")
        return manifest


def _passphrase_bytes(passphrase):
    return validate_passphrase(passphrase)


def _decrypt_to_private_temp(encrypted_path, passphrase):
    return decrypt_to_private_temp(
        encrypted_path, passphrase, EXPORT_MAGIC, suffix=".zip"
    )


def verify_encrypted_tenant_export(encrypted_path, passphrase):
    """Authenticate, privately decrypt, and verify an encrypted tenant bundle."""
    plaintext_path = _decrypt_to_private_temp(encrypted_path, passphrase)
    try:
        return verify_tenant_export(plaintext_path)
    finally:
        plaintext_path.unlink(missing_ok=True)


def decrypt_tenant_export(encrypted_path, output_path, passphrase):
    """Create a new private plaintext ZIP after authentication and checksum verification."""
    output = Path(output_path).expanduser().absolute()
    if not output.parent.is_dir():
        raise FileNotFoundError("The decryption destination directory does not exist.")
    plaintext_path = _decrypt_to_private_temp(encrypted_path, passphrase)
    created = False
    try:
        verify_tenant_export(plaintext_path)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as destination, plaintext_path.open("rb") as source:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                destination.write(block)
            destination.flush()
            os.fsync(destination.fileno())
        if stat.S_IMODE(output.stat().st_mode) & 0o077:
            output.chmod(0o600)
        created = False
        return output
    finally:
        plaintext_path.unlink(missing_ok=True)
        if created:
            output.unlink(missing_ok=True)


def encrypt_legacy_tenant_export(archive_path, output_path, passphrase):
    """Verify and encrypt a previous plaintext tenant ZIP without modifying it."""
    _passphrase_bytes(passphrase)
    source = Path(archive_path).expanduser()
    verify_tenant_export(source)
    output = Path(output_path).expanduser().absolute()
    if not output.parent.is_dir():
        raise FileNotFoundError("The encrypted-export destination directory does not exist.")
    if output.exists():
        raise FileExistsError(output)

    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    created = True
    try:
        with os.fdopen(descriptor, "wb") as output_stream:
            encrypted_stream = _EncryptingBinaryWriter(output_stream, passphrase, EXPORT_MAGIC)
            with source.open("rb") as source_stream:
                while block := source_stream.read(1024 * 1024):
                    encrypted_stream.write(block)
            encrypted_stream.finish()
        verify_encrypted_tenant_export(output, passphrase)
        if stat.S_IMODE(output.stat().st_mode) & 0o077:
            output.chmod(0o600)
        created = False
        return output
    finally:
        if created:
            output.unlink(missing_ok=True)


def export_tenant(slug, output_path, passphrase):
    """Write a new authenticated encrypted tenant bundle; never overwrite."""
    _passphrase_bytes(passphrase)
    slug = (slug or "").strip().lower()
    if not slug or len(slug) > 80:
        raise ValueError("Store slug is required and must be at most 80 characters.")
    output = Path(output_path).expanduser().absolute()
    if not output.parent.is_dir():
        raise FileNotFoundError("The export destination directory does not exist.")
    if output.exists():
        raise FileExistsError(output)

    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    output_created = True
    table_counts = {}
    checksums = {}
    media_count = 0
    try:
        with os.fdopen(descriptor, "wb") as output_stream:
            encrypted_stream = _EncryptingBinaryWriter(output_stream, passphrase, EXPORT_MAGIC)
            with zipfile.ZipFile(
                encrypted_stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
                    finally:
                        cursor.close()
                    tenant = fetch_one(
                        connection,
                        "SELECT id, name, slug, status, default_currency, timezone, created_at, updated_at "
                        "FROM tenants WHERE slug = %s",
                        (slug,),
                    )
                    if not tenant:
                        raise ValueError("Active store not found.")
                    tenant_id = tenant["id"]
                    media = _media_files(connection, tenant_id)
                    tenant_bytes = json.dumps(
                        {key: _cell(value) for key, value in tenant.items()},
                        ensure_ascii=False, indent=2,
                    ).encode("utf-8")
                    archive.writestr("tenant.json", tenant_bytes)
                    checksums["tenant.json"] = hashlib.sha256(tenant_bytes).hexdigest()
                    for archive_name, query in TABLE_EXPORTS:
                        count, checksum = _write_csv(
                            connection, archive, f"data/{archive_name}", query, tenant_id
                        )
                        table_counts[archive_name.removesuffix(".csv")] = count
                        checksums[f"data/{archive_name}"] = checksum
                    # Release the consistent-read snapshot before pulling objects
                    # over the network; large exports must not pin MySQL undo history.
                    connection.rollback()
                # Close the DB connection before network object reads.
                for storage, filename, archive_name in media:
                    checksums[archive_name] = _write_media(
                        archive, storage, filename, archive_name
                    )
                    media_count += 1
                manifest = {
                    "format": "petcare-tenant-export-v1",
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "tenant_slug": slug,
                    "tenant_id": tenant_id,
                    "tables": table_counts,
                    "media_files": media_count,
                    "sha256": checksums,
                    "excluded_secrets": ["user password hashes", "invitation token hashes"],
                }
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
            encrypted_stream.finish()
        verify_encrypted_tenant_export(output, passphrase)
        if stat.S_IMODE(output.stat().st_mode) & 0o077:
            output.chmod(0o600)
        output_created = False
        return {
            "path": output,
            "tenant_slug": slug,
            "tables": table_counts,
            "media_files": media_count,
            "encrypted": True,
        }
    finally:
        if output_created:
            output.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export one PetCare store to a private encrypted bundle.")
    commands = parser.add_subparsers(dest="command", required=True)
    export_parser = commands.add_parser("export", help="Create a tenant-scoped export")
    export_parser.add_argument("slug", help="Exact tenant/store slug to export")
    export_parser.add_argument("output", help="New .pcarexport destination; existing files are never overwritten")
    verify_parser = commands.add_parser("verify", help="Authenticate and verify an encrypted export without extracting")
    verify_parser.add_argument("archive", help="Encrypted .pcarexport bundle to verify")
    encrypt_parser = commands.add_parser("encrypt", help="Verify and encrypt an older plaintext tenant ZIP")
    encrypt_parser.add_argument("archive", help="Existing plaintext tenant-export ZIP")
    encrypt_parser.add_argument("output", help="New .pcarexport destination; existing files are never overwritten")
    decrypt_parser = commands.add_parser("decrypt", help="Create a private plaintext ZIP for an authorized data handoff")
    decrypt_parser.add_argument("archive", help="Encrypted .pcarexport bundle to decrypt")
    decrypt_parser.add_argument("output", help="New private .zip destination; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            passphrase = getpass.getpass("Export passphrase: ")
            manifest = verify_encrypted_tenant_export(args.archive, passphrase)
            print(f"Verified encrypted export for store {manifest['tenant_slug']}")
            print(f"Tables: {len(manifest['tables'])}; photos: {manifest['media_files']}")
            return
        if args.command == "decrypt":
            passphrase = getpass.getpass("Export passphrase: ")
            output = decrypt_tenant_export(args.archive, args.output, passphrase)
            print(f"Authenticated export decrypted to {output}")
            print("The ZIP contains personal data. Keep it private and remove it when the handoff is complete.")
            return
        if args.command == "encrypt":
            passphrase = getpass.getpass("Choose an export passphrase (at least 12 characters): ")
            confirmation = getpass.getpass("Confirm export passphrase: ")
            if passphrase != confirmation:
                raise ValueError("Passphrases do not match.")
            output = encrypt_legacy_tenant_export(args.archive, args.output, passphrase)
            print(f"Legacy export verified and encrypted to {output}")
            print("Keep the original ZIP private until the encrypted bundle has been backed up safely.")
            return
        passphrase = getpass.getpass("Choose an export passphrase (at least 12 characters): ")
        confirmation = getpass.getpass("Confirm export passphrase: ")
        if passphrase != confirmation:
            raise ValueError("Passphrases do not match.")
        result = export_tenant(args.slug, args.output, passphrase)
        print(f"Store {result['tenant_slug']} exported and encrypted to {result['path']}")
        print(f"Rows: {sum(result['tables'].values())}; photos: {result['media_files']}")
        print("Keep the passphrase separately; the encrypted export cannot be recovered without it.")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
