"""Rebuild legacy pet photo descriptors without changing stored images."""

from __future__ import annotations

import argparse
import json

from petcare.config import Config
from petcare.database.connection import read_connection, transaction
from petcare.repositories import pet_repo
from petcare.repositories.base import fetch_all
from petcare.vision.image_features import InvalidImage, describe_image, descriptor_to_json
from petcare.vision.media_storage import get_media_storage


_BATCH_SQL = """
SELECT id, tenant_id, photo_filename
FROM pets
WHERE photo_filename IS NOT NULL
  AND (photo_descriptor IS NULL OR
       JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
           NOT REGEXP '^[0-9a-fA-F]{16}$')
  AND id > %s
ORDER BY id
LIMIT %s
"""

_UPDATE_SQL = """
UPDATE pets
SET photo_descriptor = %s
WHERE id = %s AND tenant_id = %s AND photo_filename = %s
  AND (photo_descriptor IS NULL OR
       JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
           NOT REGEXP '^[0-9a-fA-F]{16}$')
"""


def reindex_pet_descriptors(*, apply: bool = False, batch_size: int = 100, storage=None) -> dict:
    """Rebuild descriptors in bounded batches; writes only when ``apply`` is true."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 500:
        raise ValueError("Batch size must be between 1 and 500.")
    storage = storage or get_media_storage(Config, "pets")
    after_id = 0
    summary = {"scanned": 0, "prepared": 0, "updated": 0, "skipped": 0}

    while True:
        with read_connection() as connection:
            rows = fetch_all(connection, _BATCH_SQL, (after_id, batch_size))
        if not rows:
            break

        updates = []
        for row in rows:
            summary["scanned"] += 1
            try:
                photo_bytes = storage.read(row["photo_filename"])
                descriptor = descriptor_to_json(describe_image(photo_bytes))
            except (FileNotFoundError, InvalidImage):
                summary["skipped"] += 1
                continue
            updates.append((descriptor, row["id"], row["tenant_id"], row["photo_filename"]))

        summary["prepared"] += len(updates)
        if apply and updates:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.executemany(_UPDATE_SQL, updates)
                    affected = int(cursor.rowcount)
                    summary["updated"] += len(updates) if affected < 0 else affected
                    pet_ids = [update[1] for update in updates]
                    cursor.execute(
                        "SELECT p.id, p.tenant_id, p.photo_descriptor "
                        "FROM JSON_TABLE(%s, '$[*]' COLUMNS (pet_id BIGINT UNSIGNED PATH '$')) AS batch "
                        "STRAIGHT_JOIN pets p ON p.id = batch.pet_id",
                        (json.dumps(pet_ids, separators=(",", ":")),),
                    )
                    current_descriptors = cursor.fetchall()
                    pet_repo.replace_photo_search_indexes(
                        connection,
                        (
                            (row["tenant_id"], row["id"], row["photo_descriptor"])
                            if isinstance(row, dict)
                            else (row[1], row[0], row[2])
                            for row in current_descriptors
                        ),
                    )
                finally:
                    cursor.close()

        after_id = rows[-1]["id"]

    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild pet image descriptors and derived locality-sensitive index buckets."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="write rebuilt descriptors; without this flag the command only previews the work",
    )
    parser.add_argument("--batch-size", type=int, default=100, help="rows per DB read (1–500)")
    args = parser.parse_args(argv)
    try:
        result = reindex_pet_descriptors(apply=args.apply, batch_size=args.batch_size)
    except ValueError as exc:
        parser.error(str(exc))
    action = "Updated" if args.apply else "Would update"
    print(
        f"Scanned {result['scanned']} pet photo(s); {action.lower()} "
        f"{result['updated'] if args.apply else result['prepared']} descriptor(s); "
        f"skipped {result['skipped']} missing or invalid photo(s)."
    )
    if not args.apply:
        print("Run again with --apply to write the rebuilt descriptors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
