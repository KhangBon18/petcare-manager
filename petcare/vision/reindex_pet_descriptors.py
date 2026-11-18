"""Rebuild legacy pet photo descriptors without changing stored images."""

from __future__ import annotations

import argparse
import json

from petcare.config import Config
from petcare.database.connection import read_connection, transaction
from petcare.repositories import pet_repo
from petcare.repositories.base import fetch_all
from petcare.vision.image_features import (
    InvalidImage,
    describe_image,
    descriptor_from_json,
    descriptor_to_json,
)
from petcare.vision.local_pet_detector import enrich_descriptor_with_local_vision
from petcare.vision.media_storage import get_media_storage


_BATCH_SQL = """
SELECT * FROM (
    SELECT 'primary' AS photo_source,
           id AS sort_cursor,
           id,
           id AS pet_id,
           tenant_id,
           photo_filename,
           photo_descriptor
    FROM pets
    WHERE photo_filename IS NOT NULL
      AND (photo_descriptor IS NULL OR
           JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
               NOT REGEXP '^[0-9a-fA-F]{16}$' OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.embedding_version')), '')
               != 'mnv2_op12_fg1280_f16_v1' OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.fg_lab_version')), '')
               != 'cielab_wb_sog_fg16_v1')
    UNION ALL
    SELECT 'reference' AS photo_source,
           1000000000000 + id AS sort_cursor,
           id,
           pet_id,
           tenant_id,
           photo_filename,
           photo_descriptor
    FROM pet_reference_photos
    WHERE (photo_descriptor IS NULL OR
           JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
               NOT REGEXP '^[0-9a-fA-F]{16}$' OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.embedding_version')), '')
               != 'mnv2_op12_fg1280_f16_v1' OR
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.fg_lab_version')), '')
               != 'cielab_wb_sog_fg16_v1')
) AS pending_photos
WHERE sort_cursor > %s
ORDER BY sort_cursor
LIMIT %s
"""

_UPDATE_SQL = """
UPDATE pets
SET photo_descriptor = %s
WHERE id = %s AND tenant_id = %s AND photo_filename = %s
  AND (photo_descriptor IS NULL OR
       JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
           NOT REGEXP '^[0-9a-fA-F]{16}$' OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.embedding_version')), '')
           != 'mnv2_op12_fg1280_f16_v1' OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.fg_lab_version')), '')
           != 'cielab_wb_sog_fg16_v1')
"""

_UPDATE_REF_SQL = """
UPDATE pet_reference_photos
SET photo_descriptor = %s
WHERE id = %s AND pet_id = %s AND tenant_id = %s AND photo_filename = %s
  AND (photo_descriptor IS NULL OR
       JSON_CONTAINS_PATH(photo_descriptor, 'one', '$.center_color_histogram') = 0 OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.visual_hash')), '')
           NOT REGEXP '^[0-9a-fA-F]{16}$' OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.embedding_version')), '')
           != 'mnv2_op12_fg1280_f16_v1' OR
       COALESCE(JSON_UNQUOTE(JSON_EXTRACT(photo_descriptor, '$.fg_lab_version')), '')
           != 'cielab_wb_sog_fg16_v1')
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

        primary_updates = []
        ref_updates = []
        touched_pet_ids: list[int] = []
        for row in rows:
            summary["scanned"] += 1
            try:
                photo_bytes = storage.read(row["photo_filename"])
                prior = descriptor_from_json(row.get("photo_descriptor"))
                rebuilt = describe_image(
                    photo_bytes,
                    raw_sha256=prior.raw_sha256 if prior is not None else "",
                    normalized_sha256=prior.normalized_sha256 if prior is not None else "",
                )
                if getattr(Config, "AI_FOREGROUND_EMBEDDING_ENABLED", True):
                    rebuilt = enrich_descriptor_with_local_vision(photo_bytes, rebuilt)
                descriptor = descriptor_to_json(rebuilt)
            except (FileNotFoundError, InvalidImage):
                summary["skipped"] += 1
                continue
            source = row.get("photo_source", "primary")
            if source == "reference":
                ref_updates.append(
                    (descriptor, row["id"], row["pet_id"], row["tenant_id"], row["photo_filename"])
                )
                touched_pet_ids.append(int(row["pet_id"]))
            else:
                primary_updates.append(
                    (descriptor, row["id"], row["tenant_id"], row["photo_filename"])
                )
                touched_pet_ids.append(int(row["id"]))

        total_prepared = len(primary_updates) + len(ref_updates)
        summary["prepared"] += total_prepared
        if apply and total_prepared:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    if primary_updates:
                        cursor.executemany(_UPDATE_SQL, primary_updates)
                        affected = int(cursor.rowcount)
                        summary["updated"] += len(primary_updates) if affected < 0 else affected
                    if ref_updates:
                        cursor.executemany(_UPDATE_REF_SQL, ref_updates)
                        affected_ref = int(cursor.rowcount)
                        summary["updated"] += len(ref_updates) if affected_ref < 0 else affected_ref

                    unique_pet_ids = list(dict.fromkeys(touched_pet_ids))
                    cursor.execute(
                        "SELECT p.id, p.tenant_id, p.photo_descriptor "
                        "FROM JSON_TABLE(%s, '$[*]' COLUMNS (pet_id BIGINT UNSIGNED PATH '$')) AS batch "
                        "STRAIGHT_JOIN pets p ON p.id = batch.pet_id",
                        (json.dumps(unique_pet_ids, separators=(",", ":")),),
                    )
                    current_descriptors = cursor.fetchall()
                    if ref_updates:
                        cursor.execute(
                            "SELECT rp.pet_id, rp.tenant_id, rp.photo_descriptor "
                            "FROM JSON_TABLE(%s, '$[*]' COLUMNS (pet_id BIGINT UNSIGNED PATH '$')) AS batch "
                            "JOIN pet_reference_photos rp ON rp.pet_id = batch.pet_id "
                            "ORDER BY rp.pet_id, rp.sort_order, rp.id",
                            (json.dumps(unique_pet_ids, separators=(",", ":")),),
                        )
                        ref_descriptors = cursor.fetchall()
                        by_pet_tenant: dict[tuple[int, int], list[str]] = {}
                        for r in current_descriptors:
                            tid, pid, desc_j = (
                                (r["tenant_id"], r["id"], r["photo_descriptor"])
                                if isinstance(r, dict)
                                else (r[1], r[0], r[2])
                            )
                            by_pet_tenant.setdefault((int(tid), int(pid)), [])
                            if desc_j:
                                by_pet_tenant[(int(tid), int(pid))].append(desc_j)
                        for r in ref_descriptors:
                            tid, pid, desc_j = (
                                (r["tenant_id"], r["pet_id"], r["photo_descriptor"])
                                if isinstance(r, dict)
                                else (r[1], r[0], r[2])
                            )
                            if desc_j:
                                by_pet_tenant.setdefault((int(tid), int(pid)), []).append(desc_j)
                        pet_repo.replace_photo_search_indexes(
                            connection,
                            ((tid, pid, dlist) for (tid, pid), dlist in by_pet_tenant.items()),
                        )
                    else:
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

        after_id = rows[-1].get("sort_cursor", rows[-1]["id"])

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
