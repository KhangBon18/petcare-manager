#!/usr/bin/env python3
"""Safe, idempotent isolated demo provisioning and disposable *_test reset utility.

Refuses production environments and never touches non-_dev/_test databases.
Resetting is restricted strictly to *_test schemas so real/dev data cannot be wiped.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

import mysql.connector

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.app_factory import create_app  # noqa: E402
from petcare.config import Config, mysql_config  # noqa: E402
from petcare.database.connection import read_connection, set_tenant_context  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.readiness import schema_contract_is_ready  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402
from petcare.repositories import storefront_repo  # noqa: E402
from petcare.services import storefront_auth_service, storefront_service  # noqa: E402

_DISPOSABLE_TEST_DB_RE = re.compile(r"^[A-Za-z0-9_]+_test$")
_ALLOWED_DEMO_DB_RE = re.compile(r"^[A-Za-z0-9_]+_(test|dev)$")

DEMO_CUSTOMER_EMAIL = "demo.customer@example.invalid"
DEMO_CUSTOMER_NAME = "Khách hàng Storefront Demo"
DEMO_CUSTOMER_PHONE = "0000000901"
DEMO_CUSTOMER_ADDRESS = "123 Đường Demo, Quận 1, TP.HCM"

_PENDING_ORDER_REQUEST_KEY = str(uuid.uuid5(uuid.NAMESPACE_DNS, "petcare.demo.storefront.order.pending.v1"))
_COMPLETED_ORDER_REQUEST_KEY = str(uuid.uuid5(uuid.NAMESPACE_DNS, "petcare.demo.storefront.order.completed.v1"))


def _require_safe_environment(*, reset: bool) -> None:
    app_env = Config.APP_ENV.strip().lower()
    if app_env == "production":
        raise RuntimeError("Refusing demo setup when APP_ENV='production'.")
    if os.getenv("PETCARE_DEMO_MODE") != "1":
        raise RuntimeError("Demo setup requires PETCARE_DEMO_MODE=1.")
    db_name = Config.DB_NAME.strip()
    if reset:
        if not _DISPOSABLE_TEST_DB_RE.fullmatch(db_name) or any(
            tok in db_name.lower() for tok in ("_dev", "_prod", "production")
        ):
            raise RuntimeError(
                f"--reset-disposable requires a *_test database name; got '{db_name}'."
            )
    elif not _ALLOWED_DEMO_DB_RE.fullmatch(db_name):
        raise RuntimeError(
            f"Demo setup requires a *_test or *_dev database name; got '{db_name}'."
        )
    if app_env == "test" and not db_name.endswith("_test"):
        raise RuntimeError("APP_ENV=test requires DB_NAME ending in _test.")
    if app_env == "development" and not db_name.endswith("_dev"):
        raise RuntimeError("APP_ENV=development requires DB_NAME ending in _dev.")


def _validate_customer_password() -> str:
    admin_pw = os.getenv("PETCARE_DEMO_ADMIN_PASSWORD", "")
    staff_pw = os.getenv("PETCARE_DEMO_STAFF_PASSWORD", "")
    customer_pw = os.getenv("PETCARE_DEMO_CUSTOMER_PASSWORD", "")
    if not isinstance(customer_pw, str) or not 16 <= len(customer_pw) <= 1024:
        raise RuntimeError(
            "Set PETCARE_DEMO_CUSTOMER_PASSWORD (16-1024 characters) in environment."
        )
    if customer_pw in {admin_pw, staff_pw}:
        raise RuntimeError(
            "PETCARE_DEMO_CUSTOMER_PASSWORD must differ from admin and staff passwords."
        )
    return customer_pw


def _reset_disposable_environment() -> None:
    db_name = Config.DB_NAME.strip()
    server_cfg = {k: v for k, v in mysql_config(Config).items() if k != "database"}
    connection = mysql.connector.connect(**server_cfg)
    try:
        cursor = connection.cursor()
        try:
            # Safe identifier: _require_safe_environment verified ^[A-Za-z0-9_]+_test$.
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")  # nosec B608
            cursor.execute(  # nosec B608
                f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        finally:
            cursor.close()
    finally:
        connection.close()

    tmp_root = Path(tempfile.gettempdir()).resolve()
    for folder in (Config.PET_IMAGE_DIR, Config.PRODUCT_IMAGE_DIR, Config.TENANT_EXPORT_DIR):
        target = Path(folder).resolve()
        if str(target).startswith(str(tmp_root)) and target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def _seed_storefront_demo(customer_password: str) -> dict:
    with read_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, name, default_currency, timezone FROM tenants WHERE slug = 'main'")
            tenant = cursor.fetchone()
            if not tenant:
                raise RuntimeError("Missing active 'main' store after seed_database().")
            tenant_id = int(tenant["id"])
            set_tenant_context(connection, tenant_id)
            account = storefront_repo.get_account_by_email(connection, DEMO_CUSTOMER_EMAIL)
            cursor.execute("SELECT id FROM users WHERE username = 'staff1'")
            staff_row = cursor.fetchone()
            staff_id = int(staff_row["id"]) if staff_row else None
            cursor.execute("SELECT id, stock_qty FROM products WHERE tenant_id = %s AND code = %s", (tenant_id, "FOOD-001"))
            food_001 = cursor.fetchone()
            cursor.execute("SELECT id, stock_qty FROM products WHERE tenant_id = %s AND code = %s", (tenant_id, "CARE-001"))
            care_001 = cursor.fetchone()
            cursor.execute(
                "SELECT id, order_code, order_status FROM customer_orders WHERE tenant_id = %s AND request_key = %s",
                (tenant_id, _PENDING_ORDER_REQUEST_KEY),
            )
            pending_order = cursor.fetchone()
            cursor.execute(
                "SELECT id, order_code, order_status FROM customer_orders WHERE tenant_id = %s AND request_key = %s",
                (tenant_id, _COMPLETED_ORDER_REQUEST_KEY),
            )
            completed_order = cursor.fetchone()
        finally:
            cursor.close()

    if not account:
        account = storefront_auth_service.register_customer(
            tenant_id,
            {
                "email": DEMO_CUSTOMER_EMAIL,
                "full_name": DEMO_CUSTOMER_NAME,
                "phone": DEMO_CUSTOMER_PHONE,
                "default_address": DEMO_CUSTOMER_ADDRESS,
                "password": customer_password,
            },
        )
    account_id = int(account["id"])

    if not pending_order and food_001:
        created = storefront_service.place_order(
            tenant_id,
            tenant["default_currency"],
            tenant["timezone"],
            [{"item_type": "product", "item_id": int(food_001["id"]), "quantity": 1}],
            {
                "request_key": _PENDING_ORDER_REQUEST_KEY,
                "customer_name": DEMO_CUSTOMER_NAME,
                "customer_phone": DEMO_CUSTOMER_PHONE,
                "customer_email": DEMO_CUSTOMER_EMAIL,
                "fulfillment_method": "cod_delivery",
                "delivery_address": DEMO_CUSTOMER_ADDRESS,
                "customer_note": "[DEMO] Đơn COD chờ nhân viên xác nhận",
            },
            customer_account_id=account_id,
        )
        pending_order = created["order"]

    if not completed_order and care_001 and staff_id:
        created_done = storefront_service.place_order(
            tenant_id,
            tenant["default_currency"],
            tenant["timezone"],
            [{"item_type": "product", "item_id": int(care_001["id"]), "quantity": 1}],
            {
                "request_key": _COMPLETED_ORDER_REQUEST_KEY,
                "customer_name": DEMO_CUSTOMER_NAME,
                "customer_phone": DEMO_CUSTOMER_PHONE,
                "customer_email": DEMO_CUSTOMER_EMAIL,
                "fulfillment_method": "cod_delivery",
                "delivery_address": DEMO_CUSTOMER_ADDRESS,
                "customer_note": "[DEMO] Đơn COD đã thu tiền & xuất hóa đơn",
            },
            customer_account_id=account_id,
        )["order"]
        oid = int(created_done["id"])
        storefront_service.process_staff_order(staff_id, oid, "confirm", "Demo đã xác nhận", tenant_id=tenant_id)
        storefront_service.process_staff_order(staff_id, oid, "prepare", "Demo đang đóng gói", tenant_id=tenant_id)
        storefront_service.process_staff_order(staff_id, oid, "fulfill", "Demo đã giao · chờ thu tiền", tenant_id=tenant_id)
        storefront_service.process_staff_order(
            staff_id,
            oid,
            "complete_payment",
            "Demo đã thu COD đầy đủ",
            tenant_id=tenant_id,
            payment_confirmed=True,
            collected_amount=created_done["total_amount"],
        )

    with read_connection() as connection:
        cursor = connection.cursor()
        try:
            ready = schema_contract_is_ready(cursor)
            cursor.execute("SELECT COUNT(*) FROM products WHERE tenant_id = %s", (tenant_id,))
            products_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM pets WHERE tenant_id = %s", (tenant_id,))
            pets_cnt = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM pets WHERE tenant_id = %s AND photo_filename IS NOT NULL AND photo_filename <> ''",
                (tenant_id,),
            )
            verified_pets_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE tenant_id = %s AND status = 'paid'", (tenant_id,))
            paid_invoices_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM customer_orders WHERE tenant_id = %s", (tenant_id,))
            online_orders_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM stock_movements WHERE tenant_id = %s", (tenant_id,))
            movements_cnt = cursor.fetchone()[0]
        finally:
            cursor.close()

    return {
        "database": Config.DB_NAME,
        "schema_ready": bool(ready),
        "staff_accounts": ["admin", "staff1"],
        "customer_account_email": DEMO_CUSTOMER_EMAIL,
        "products": products_cnt,
        "pets_total": pets_cnt,
        "pets_with_stored_photos": verified_pets_cnt,
        "pets_illustrative_only": pets_cnt - verified_pets_cnt,
        "paid_invoices": paid_invoices_cnt,
        "customer_orders": online_orders_cnt,
        "stock_movements": movements_cnt,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotently provision an isolated demo database (Admin/Staff/Customer/Storefront)."
    )
    parser.add_argument(
        "--reset-disposable",
        action="store_true",
        help="Drop and recreate an explicit *_test schema and temporary /tmp media before seeding.",
    )
    parser.add_argument("--json", action="store_true", help="Output summary as JSON.")
    args = parser.parse_args(argv)

    _require_safe_environment(reset=args.reset_disposable)
    customer_password = _validate_customer_password()

    app = create_app()
    with app.app_context():
        if args.reset_disposable:
            _reset_disposable_environment()
        initialize_database()
        seed_database()
        summary = _seed_storefront_demo(customer_password)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Demo DB ready: {summary['database']} (schema_ready={summary['schema_ready']})")
        print(
            f"Accounts: staff={summary['staff_accounts']}, customer={summary['customer_account_email']}"
        )
        print(
            f"Catalog: {summary['products']} products, {summary['pets_total']} pets "
            f"({summary['pets_with_stored_photos']} stored photos, {summary['pets_illustrative_only']} illustrative)"
        )
        print(
            f"Transactions: {summary['paid_invoices']} paid invoices, "
            f"{summary['customer_orders']} customer orders, {summary['stock_movements']} stock movements"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
