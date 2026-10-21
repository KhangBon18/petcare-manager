"""Copy all referenced pet/product photos between local and S3 storage."""

from __future__ import annotations

import argparse
import hashlib

from petcare.config import Config
from petcare.database.connection import read_connection
from petcare.vision.media_storage import SAFE_MEDIA_NAME, get_media_storage


def list_referenced_media():
    """Read the current database's referenced photo names across all tenants."""
    records = []
    with read_connection() as connection:
        cursor = connection.cursor()
        try:
            for table, category in (("pets", "pets"), ("products", "products")):
                cursor.execute(
                    f"SELECT DISTINCT photo_filename FROM {table} "
                    "WHERE photo_filename IS NOT NULL ORDER BY photo_filename"
                )
                for (filename,) in cursor.fetchall():
                    if not isinstance(filename, str) or not SAFE_MEDIA_NAME.fullmatch(filename):
                        raise ValueError(f"Unsafe photo reference found in the {table} table.")
                    records.append((category, filename))
        finally:
            cursor.close()
    return records


def copy_referenced_media(source_backend: str, destination_backend: str, records=None) -> int:
    """Copy and hash-verify each referenced object. Never deletes the source."""
    if source_backend == destination_backend:
        raise ValueError("Source and destination storage backends must differ.")
    records = list_referenced_media() if records is None else records
    storages = {
        (backend, category): get_media_storage(Config, category, backend=backend)
        for category in ("pets", "products")
        for backend in (source_backend, destination_backend)
    }
    for category, filename in records:
        source = storages[(source_backend, category)].read(filename)
        destination_storage = storages[(destination_backend, category)]
        destination_storage.put(filename, source)
        copied = destination_storage.read(filename)
        if not hashlib.sha256(source).digest() == hashlib.sha256(copied).digest():
            raise IOError("Photo verification failed during storage migration.")
    return len(records)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Dry-run or copy referenced photos between local and S3-compatible storage."
    )
    parser.add_argument("--from", dest="source", choices=("local", "s3"), required=True)
    parser.add_argument("--to", dest="destination", choices=("local", "s3"), required=True)
    parser.add_argument(
        "--apply", action="store_true", help="copy and verify files; default is a read-only count"
    )
    args = parser.parse_args(argv)
    if args.source == args.destination:
        parser.error("--from and --to must select different backends.")

    records = list_referenced_media()
    print(f"Found {len(records)} referenced photo(s) across pets/products.")
    if not args.apply:
        print("Dry run only; rerun with --apply to copy and verify. Source files will be kept.")
        return 0

    copied = copy_referenced_media(args.source, args.destination, records=records)
    print(f"Copied and SHA-256 verified {copied} photo(s). Source files were kept for rollback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
