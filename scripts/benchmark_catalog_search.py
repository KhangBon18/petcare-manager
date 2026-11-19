"""Measure tenant-scoped catalog search using disposable MySQL temporary tables."""

import argparse
import json
import sys
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from petcare.config import Config
from petcare.database.connection import get_connection


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        required=True,
        help="Existing isolated MySQL database whose name ends in _test.",
    )
    parser.add_argument("--rows", type=int, default=20_000, help="Synthetic rows per tenant/table (1-100,000).")
    parser.add_argument("--runs", type=int, default=35, help="Warm query runs per measurement (1-1,000).")
    args = parser.parse_args()
    if not args.database.lower().endswith("_test"):
        parser.error("--database must end in _test; persistent development/production databases are rejected.")
    if not 1 <= args.rows <= 100_000:
        parser.error("--rows must be between 1 and 100000.")
    if not 1 <= args.runs <= 1_000:
        parser.error("--runs must be between 1 and 1000.")
    return args


def insert_synthetic_rows(connection, rows):
    batch_size = 1_000
    with connection.cursor() as cursor:
        for start in range(0, rows, batch_size):
            end = min(start + batch_size, rows)
            products = []
            customers = []
            pets = []
            for number in range(start, end):
                marker = "Needle " if number == rows - 1 else ""
                products.append((1, f"B{number:06d}", f"{marker}Pet nutrition {number}", "Food and supplements"))
                customers.append((1, f"{marker}Customer sample {number}", f"+849{number:09d}"))
                pets.append((1, f"P{number:06d}", f"{marker}Cat sample {number}", "Cat"))
            cursor.executemany(
                "INSERT INTO bench_products (tenant_id, code, name, category) VALUES (%s,%s,%s,%s)",
                products,
            )
            cursor.executemany(
                "INSERT INTO bench_customers (tenant_id, full_name, phone) VALUES (%s,%s,%s)",
                customers,
            )
            cursor.executemany(
                "INSERT INTO bench_pets (tenant_id, code, name, species) VALUES (%s,%s,%s,%s)",
                pets,
            )


def query_cases():
    return {
        "products": (
            "SELECT * FROM bench_products WHERE tenant_id=%s AND "
            "(code LIKE %s OR name LIKE %s OR category LIKE %s) AND active=1 "
            "ORDER BY active DESC, name, id LIMIT 25 OFFSET 0",
            "SELECT COUNT(*) total FROM bench_products WHERE tenant_id=%s AND "
            "(code LIKE %s OR name LIKE %s OR category LIKE %s)",
            (1, "%Needle%", "%Needle%", "%Needle%"),
        ),
        "customers": (
            "SELECT c.*, (SELECT COUNT(*) FROM bench_invoices i "
            "WHERE i.customer_id=c.id AND i.tenant_id=c.tenant_id) invoice_count "
            "FROM bench_customers c WHERE c.tenant_id=%s AND (c.full_name LIKE %s OR c.phone LIKE %s) "
            "ORDER BY c.full_name, c.id LIMIT 25 OFFSET 0",
            "SELECT COUNT(*) total FROM bench_customers WHERE tenant_id=%s "
            "AND (full_name LIKE %s OR phone LIKE %s)",
            (1, "%Needle%", "%Needle%"),
        ),
        "pets": (
            "SELECT p.*, c.full_name buyer_name FROM bench_pets p LEFT JOIN bench_customers c "
            "ON c.id=p.buyer_id AND c.tenant_id=p.tenant_id WHERE p.tenant_id=%s "
            "AND (p.code LIKE %s OR p.name LIKE %s OR p.species LIKE %s) "
            "ORDER BY FIELD(p.sale_status, 'available', 'sold', 'inactive'), p.name, p.id LIMIT 25 OFFSET 0",
            "SELECT COUNT(*) total FROM bench_pets WHERE tenant_id=%s "
            "AND (code LIKE %s OR name LIKE %s OR species LIKE %s)",
            (1, "%Needle%", "%Needle%", "%Needle%"),
        ),
    }


def measure(cursor, sql, params, runs):
    cursor.execute("EXPLAIN " + sql, params)
    plan = [
        {key: row.get(key) for key in ("table", "type", "key", "rows", "Extra")}
        for row in cursor.fetchall()
    ]
    samples = []
    result_count = 0
    for _ in range(runs):
        started = perf_counter()
        cursor.execute(sql, params)
        result_count = len(cursor.fetchall())
        samples.append((perf_counter() - started) * 1_000)
    ordered = sorted(samples)
    return {
        "plan": plan,
        "median_ms": round(median(samples), 2),
        "p95_ms": round(ordered[ceil(0.95 * runs) - 1], 2),
        "max_ms": round(max(samples), 2),
        "last_result_rows": result_count,
    }


def main():
    args = arguments()
    Config.DB_NAME = args.database
    connection = get_connection()
    table_names = ("bench_products", "bench_customers", "bench_pets", "bench_invoices")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() database_name")
            database_name = cursor.fetchone()[0]
        if database_name != args.database:
            raise RuntimeError("Connected database does not match --database; stopping without benchmarking.")
        with connection.cursor() as cursor:
            for table, source in (
                ("bench_products", "products"),
                ("bench_customers", "customers"),
                ("bench_pets", "pets"),
                ("bench_invoices", "invoices"),
            ):
                cursor.execute(f"CREATE TEMPORARY TABLE {table} LIKE {source}")
        insert_synthetic_rows(connection, args.rows)
        results = {}
        with connection.cursor(dictionary=True) as cursor:
            for table, (page_sql, count_sql, params) in query_cases().items():
                results[table] = {
                    "page": measure(cursor, page_sql, params, args.runs),
                    "count": measure(cursor, count_sql, params, args.runs),
                }
        print(json.dumps({
            "database": database_name,
            "synthetic_rows_per_tenant_per_table": args.rows,
            "warm_runs_per_query": args.runs,
            "persistent_tables_modified": False,
            "results": results,
        }, ensure_ascii=False, indent=2))
    finally:
        try:
            with connection.cursor() as cursor:
                for table in table_names:
                    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS {table}")
        finally:
            connection.close()


if __name__ == "__main__":
    main()
