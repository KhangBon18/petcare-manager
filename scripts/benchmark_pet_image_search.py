"""Benchmark the local image-ranking service with disposable MySQL rows."""

import argparse
import json
import sys
from contextlib import contextmanager
from io import BytesIO
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter

from flask import g
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from petcare import create_app  # noqa: E402
from petcare.config import Config  # noqa: E402
from petcare.database.connection import get_connection  # noqa: E402
from petcare.services import pet_image_service  # noqa: E402
from petcare.vision.image_features import (  # noqa: E402
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    visual_hash_bands,
)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        required=True,
        help="Existing isolated MySQL database whose name ends in _test.",
    )
    parser.add_argument("--rows", type=int, default=20_000, help="Synthetic pets (1-100,000).")
    parser.add_argument("--runs", type=int, default=5, help="Warm full-service search runs (1-100).")
    parser.add_argument(
        "--candidate-fraction", type=float, default=0.01,
        help="Fraction of pets assigned the query hash (0.01 is selective; 1.0 forces fallback).",
    )
    args = parser.parse_args()
    if not args.database.lower().endswith("_test"):
        parser.error("--database must end in _test; persistent development/production databases are rejected.")
    if not 1 <= args.rows <= 100_000:
        parser.error("--rows must be between 1 and 100000.")
    if not 1 <= args.runs <= 100:
        parser.error("--runs must be between 1 and 100.")
    if not 0 < args.candidate_fraction <= 1:
        parser.error("--candidate-fraction must be greater than 0 and at most 1.")
    args.candidate_rows = max(1, ceil(args.rows * args.candidate_fraction))
    return args


def create_temporary_pets(connection):
    with connection.cursor() as cursor:
        # Temporary table shadows the real table only on this connection and is
        # explicitly removed in finally; it has the columns read by the repo.
        cursor.execute(
            "CREATE TEMPORARY TABLE pets ("
            "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, "
            "tenant_id BIGINT UNSIGNED NOT NULL, code VARCHAR(48) NOT NULL, "
            "name VARCHAR(120) NOT NULL, species VARCHAR(80) NOT NULL, "
            "breed VARCHAR(100) NOT NULL DEFAULT '', coat_color VARCHAR(80) NOT NULL DEFAULT '', "
            "eye_color VARCHAR(60) NOT NULL DEFAULT '', appearance_tags VARCHAR(255) NOT NULL DEFAULT '', "
            "photo_filename VARCHAR(64) NULL, photo_descriptor JSON NULL, "
            "sale_price DECIMAL(20,4) NOT NULL DEFAULT 0, "
            "sale_status ENUM('available','sold','inactive') NOT NULL DEFAULT 'available', "
            "buyer_id BIGINT UNSIGNED NULL, "
            "INDEX idx_bench_pets_tenant_status (tenant_id, sale_status, id)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )
        cursor.execute(
            "CREATE TEMPORARY TABLE pet_photo_lsh ("
            "tenant_id BIGINT UNSIGNED NOT NULL, pet_id BIGINT UNSIGNED NOT NULL, "
            "hash_version TINYINT UNSIGNED NOT NULL, band TINYINT UNSIGNED NOT NULL, "
            "bucket_value TINYINT UNSIGNED NOT NULL, "
            "PRIMARY KEY (tenant_id, pet_id, hash_version, band), "
            "INDEX idx_pet_photo_lsh_bucket (tenant_id, hash_version, band, bucket_value, pet_id)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )


def populate_temporary_pets(
    connection, tenant_id, rows, descriptor_json, query_hash, candidate_rows
):
    # Keep a controlled fraction in the query's bucket; the rest are 4 bits
    # away in every band so they are outside the LSH candidate set.
    far_value = int(query_hash, 16)
    for band in range(8):
        for bit in range(4):
            far_value ^= 1 << (band * 8 + bit)
    far_hash = f"{far_value:016x}"
    base_descriptor = json.loads(descriptor_json)
    far_descriptor_json = json.dumps(
        {**base_descriptor, "visual_hash": far_hash}, separators=(",", ":")
    )
    query_bands = visual_hash_bands(query_hash)
    far_bands = visual_hash_bands(far_hash)
    with connection.cursor() as cursor:
        for start in range(0, rows, 1_000):
            batch = []
            index_rows = []
            for number in range(start, min(start + 1_000, rows)):
                matched = number < candidate_rows
                signature = query_hash if matched else far_hash
                stored_descriptor = descriptor_json if matched else far_descriptor_json
                pet_id = number + 1
                batch.append(
                    (tenant_id, f"BENCH-{number:06d}", f"Cat {number:06d}", "Cat", stored_descriptor)
                )
                bands = query_bands if matched else far_bands
                index_rows.extend(
                    (tenant_id, pet_id, 1, band, bucket_value)
                    for band, bucket_value in enumerate(bands)
                )
            cursor.executemany(
                "INSERT INTO pets (tenant_id, code, name, species, photo_descriptor) "
                "VALUES (%s,%s,%s,%s,%s)",
                batch,
            )
            cursor.executemany(
                "INSERT INTO pet_photo_lsh "
                "(tenant_id, pet_id, hash_version, band, bucket_value) "
                "VALUES (%s,%s,%s,%s,%s)",
                index_rows,
            )


def main():
    args = arguments()
    Config.DB_NAME = args.database
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "isolated-benchmark-only",
        "AI_VISION_ENABLED": False,
    })
    connection = get_connection()
    try:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT DATABASE() database_name")
            database_name = cursor.fetchone()["database_name"]
            if database_name != args.database:
                raise RuntimeError("Connected database does not match --database; stopping without benchmarking.")
            cursor.execute(
                "SELECT tu.tenant_id, tu.user_id FROM tenant_users tu "
                "JOIN users u ON u.id=tu.user_id "
                "JOIN tenants t ON t.id=tu.tenant_id "
                "WHERE tu.active=1 AND u.active=1 AND t.status='active' "
                "ORDER BY tu.tenant_id, tu.user_id LIMIT 1"
            )
            actor = cursor.fetchone()
        if not actor:
            raise RuntimeError("The test database needs one active store member to run the service benchmark.")

        image_stream = BytesIO()
        Image.new("RGB", (128, 128), (190, 132, 88)).save(image_stream, format="JPEG")
        image_bytes = image_stream.getvalue()
        normalized = normalize_image_bytes(image_bytes)
        query_descriptor = describe_image(normalized)
        descriptor_json = descriptor_to_json(query_descriptor)

        create_temporary_pets(connection)
        populate_temporary_pets(
            connection, actor["tenant_id"], args.rows, descriptor_json,
            query_descriptor.visual_hash, args.candidate_rows,
        )
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SET @petcare_tenant_id = %s", (actor["tenant_id"],))
            bucket_probes = [
                {"band": band, "bucket_value": bucket ^ bit_mask}
                for band, bucket in enumerate(visual_hash_bands(query_descriptor.visual_hash))
                for bit_mask in (0, *(1 << bit for bit in range(8)))
            ]
            cursor.execute(
                "EXPLAIN SELECT DISTINCT l.pet_id "
                "FROM JSON_TABLE(%s, '$[*]' COLUMNS (band TINYINT UNSIGNED PATH '$.band', "
                "bucket_value TINYINT UNSIGNED PATH '$.bucket_value')) AS probe "
                "JOIN pet_photo_lsh l FORCE INDEX (idx_pet_photo_lsh_bucket) "
                "ON l.tenant_id = @petcare_tenant_id AND l.hash_version = %s "
                "AND l.band = probe.band AND l.bucket_value = probe.bucket_value "
                "JOIN pets p ON p.tenant_id = l.tenant_id AND p.id = l.pet_id "
                "WHERE p.sale_status = 'available' LIMIT %s",
                (json.dumps(bucket_probes, separators=(",", ":")), 1, 5_001),
            )
            plan = [
                {key: row.get(key) for key in ("table", "type", "key", "rows", "Extra")}
                for row in cursor.fetchall()
            ]

        @contextmanager
        def borrowed_connection():
            yield connection

        original_read_connection = pet_image_service.read_connection
        pet_image_service.read_connection = borrowed_connection
        samples = []
        try:
            with app.test_request_context():
                g.tenant = {"id": actor["tenant_id"]}
                for _ in range(args.runs):
                    started = perf_counter()
                    result = pet_image_service.search_similar(actor["user_id"], image_bytes)
                    samples.append((perf_counter() - started) * 1_000)
        finally:
            pet_image_service.read_connection = original_read_connection

        ordered = sorted(samples)
        print(json.dumps({
            "database": database_name,
            "temporary_available_pets": args.rows,
            "synthetic_index_candidate_fraction": round(args.candidate_rows / args.rows, 4),
            "synthetic_index_candidate_rows": args.candidate_rows,
            "warm_full_service_runs": args.runs,
            "local_ai_provider_enabled": False,
            "persistent_tables_modified": False,
            "query_plan": plan,
            "median_ms": round(median(samples), 2),
            "p95_ms": round(ordered[ceil(0.95 * args.runs) - 1], 2),
            "max_ms": round(max(samples), 2),
            "results_returned": len(result["results"]),
        }, ensure_ascii=False, indent=2))
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TEMPORARY TABLE IF EXISTS pet_photo_lsh")
                cursor.execute("DROP TEMPORARY TABLE IF EXISTS pets")
        finally:
            connection.close()


if __name__ == "__main__":
    main()
