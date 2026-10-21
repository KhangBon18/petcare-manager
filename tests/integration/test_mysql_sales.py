import os
import re
import threading
import unittest
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from threading import Event, Thread, current_thread
from uuid import uuid4
from unittest.mock import patch

from petcare.config import Config
from petcare.database.connection import get_connection, transaction
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories import product_repo
from petcare.repositories.base import fetch_all, fetch_one
from petcare.services import customer_service, invoice_service, pet_service, product_service, report_service
from petcare.services.exceptions import ConflictError, ValidationError


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class MySQLSalesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        with get_connection() as connection:
            user = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
        cls.admin_id = user["id"]

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.previous_db_name

    def setUp(self):
        self.customer_ids = []
        self.product_ids = []
        self.pet_ids = []
        self.invoice_ids = []
        phone = "09" + f"{uuid4().int % 100_000_000:08d}"
        self.customer_id = customer_service.create_customer(
            self.admin_id,
            {"full_name": "Khách test", "phone": phone, "address": ""},
        )
        self.customer_ids.append(self.customer_id)

    def tearDown(self):
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                for invoice_id in self.invoice_ids:
                    cursor.execute("DELETE FROM stock_movements WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
                for product_id in self.product_ids:
                    cursor.execute("DELETE FROM stock_movements WHERE product_id = %s", (product_id,))
                for pet_id in self.pet_ids:
                    cursor.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
                for customer_id in self.customer_ids:
                    cursor.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
                for product_id in self.product_ids:
                    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                connection.commit()
            finally:
                cursor.close()

    def _product(self, stock):
        suffix = uuid4().hex[:8].upper()
        product_id = product_service.create_product(
            self.admin_id,
            {"code": "T-" + suffix, "name": "Hàng test", "category": "Test",
             "unit_price": "100000", "stock_qty": str(stock)},
        )
        self.product_ids.append(product_id)
        return product_id

    def _pet(self):
        suffix = uuid4().hex[:8].upper()
        pet_id = pet_service.create_pet(
            self.admin_id,
            {"code": "P-" + suffix, "name": "Miu test", "species": "Mèo",
             "breed": "", "sex": "female", "birth_date": "", "weight_kg": "",
             "coat_color": "", "sale_price": "2000000"},
        )
        self.pet_ids.append(pet_id)
        return pet_id

    def _invoice(self, items):
        invoice_id = invoice_service.create_invoice(
            self.admin_id, {"customer_id": str(self.customer_id), "note": ""}, items
        )
        self.invoice_ids.append(invoice_id)
        return invoice_id

    def test_payment_updates_stock_pet_and_revenue_once(self):
        product_id = self._product(3)
        pet_id = self._pet()
        invoice_id = self._invoice([
            {"item_type": "product", "item_id": str(product_id), "quantity": "2"},
            {"item_type": "pet", "item_id": str(pet_id), "quantity": "1"},
        ])
        before = report_service.report(self.admin_id, date.today().isoformat(), date.today().isoformat())
        with get_connection() as connection:
            product_before = fetch_one(connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,))
            pet_before = fetch_one(connection, "SELECT sale_status, buyer_id FROM pets WHERE id = %s", (pet_id,))
        self.assertEqual(product_before["stock_qty"], 3)
        self.assertEqual(pet_before["sale_status"], "available")
        self.assertIsNone(pet_before["buyer_id"])

        self.assertEqual(invoice_service.pay_invoice(self.admin_id, invoice_id), "paid")
        after = report_service.report(self.admin_id, date.today().isoformat(), date.today().isoformat())
        self.assertEqual(after["summary"]["revenue"] - before["summary"]["revenue"], 2_200_000)
        self.assertEqual(invoice_service.pay_invoice(self.admin_id, invoice_id), "already_paid")
        repeated = report_service.report(self.admin_id, date.today().isoformat(), date.today().isoformat())
        self.assertEqual(repeated["summary"]["revenue"], after["summary"]["revenue"])
        with get_connection() as connection:
            product_after = fetch_one(connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,))
            pet_after = fetch_one(connection, "SELECT sale_status, buyer_id FROM pets WHERE id = %s", (pet_id,))
            movements = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM stock_movements WHERE product_id = %s AND invoice_id = %s",
                (product_id, invoice_id),
            )
        self.assertEqual(product_after["stock_qty"], 1)
        self.assertEqual(movements["total"], 1)
        self.assertEqual(pet_after["sale_status"], "sold")
        self.assertEqual(pet_after["buyer_id"], self.customer_id)

    def test_report_uses_store_local_day_across_dst_boundary(self):
        product_id = self._product(3)
        with transaction() as connection:
            tenant = fetch_one(connection, "SELECT id, timezone FROM tenants WHERE slug = 'main'")
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE tenants SET timezone = 'America/Los_Angeles' WHERE id = %s",
                    (tenant["id"],),
                )
            finally:
                cursor.close()
        try:
            invoice_id = self._invoice([
                {"item_type": "product", "item_id": str(product_id), "quantity": "1"}
            ])
            self.assertEqual(invoice_service.pay_invoice(self.admin_id, invoice_id), "paid")
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    # 10:30 UTC is 03:30 PDT on the spring-forward day.
                    cursor.execute(
                        "UPDATE invoices SET paid_at = %s WHERE id = %s",
                        (datetime(2026, 3, 8, 10, 30), invoice_id),
                    )
                finally:
                    cursor.close()

            local_day = report_service.report(self.admin_id, "2026-03-08", "2026-03-08")
            previous_day = report_service.report(self.admin_id, "2026-03-07", "2026-03-07")

            self.assertEqual(local_day["summary"]["revenue"], Decimal("100000.0000"))
            self.assertEqual(previous_day["summary"]["revenue"], Decimal("0.0000"))
        finally:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenants SET timezone = %s WHERE slug = 'main'",
                        (tenant["timezone"],),
                    )
                finally:
                    cursor.close()

    def test_usd_catalog_and_invoice_preserve_fractional_amounts_and_currency_snapshot(self):
        with transaction() as connection:
            tenant = fetch_one(connection, "SELECT id, default_currency FROM tenants WHERE slug = 'main'")
            cursor = connection.cursor()
            try:
                cursor.execute("UPDATE tenants SET default_currency = 'USD' WHERE id = %s", (tenant["id"],))
            finally:
                cursor.close()
        try:
            suffix = uuid4().hex[:8].upper()
            product_id = product_service.create_product(
                self.admin_id,
                {"code": "USD-" + suffix, "name": "USD item", "category": "Test",
                 "unit_price": "12.34", "stock_qty": "3"},
            )
            self.product_ids.append(product_id)
            invoice_id = self._invoice([
                {"item_type": "product", "item_id": str(product_id), "quantity": "2"}
            ])
            invoice = invoice_service.get_invoice(self.admin_id, invoice_id)
            self.assertEqual(invoice["currency_code"], "USD")
            self.assertEqual(invoice["total_amount"], Decimal("24.68"))
            self.assertEqual(invoice["items"][0]["unit_price"], Decimal("12.34"))
            with get_connection() as connection:
                row = fetch_one(
                    connection,
                    "SELECT unit_price, unit_price_vnd FROM products WHERE id = %s",
                    (product_id,),
                )
            self.assertEqual(row["unit_price"], Decimal("12.3400"))
            self.assertEqual(row["unit_price_vnd"], 0)
        finally:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenants SET default_currency = %s WHERE slug = 'main'",
                        (tenant["default_currency"],),
                    )
                finally:
                    cursor.close()

    def test_additive_currency_migration_backfills_legacy_vnd_price_columns(self):
        suffix = uuid4().hex[:8].upper()
        with transaction() as connection:
            tenant = fetch_one(connection, "SELECT id FROM tenants WHERE slug = 'main'")
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO products (tenant_id, code, name, category, unit_price_vnd) "
                    "VALUES (%s, %s, 'Legacy VND item', 'Test', 7654321)",
                    (tenant["id"], "LEGACY-" + suffix),
                )
                product_id = cursor.lastrowid
            finally:
                cursor.close()
        try:
            initialize_database()
            with get_connection() as connection:
                migrated = fetch_one(
                    connection, "SELECT unit_price FROM products WHERE id = %s", (product_id,)
                )
            self.assertEqual(migrated["unit_price"], Decimal("7654321.0000"))
        finally:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                finally:
                    cursor.close()

    def test_concurrent_payment_cannot_sell_last_unit_twice(self):
        product_id = self._product(1)
        invoice_ids = [
            self._invoice([{"item_type": "product", "item_id": str(product_id), "quantity": "1"}]),
            self._invoice([{"item_type": "product", "item_id": str(product_id), "quantity": "1"}]),
        ]
        barrier = threading.Barrier(2)

        def pay(invoice_id):
            barrier.wait(timeout=5)
            try:
                return invoice_service.pay_invoice(self.admin_id, invoice_id)
            except ConflictError:
                return "out_of_stock"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(pay, invoice_ids))
        self.assertCountEqual(results, ["paid", "out_of_stock"])
        with get_connection() as connection:
            product = fetch_one(connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,))
            paid = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM invoices WHERE id IN (%s, %s) AND status = 'paid'",
                tuple(invoice_ids),
            )
        self.assertEqual(product["stock_qty"], 0)
        self.assertEqual(paid["total"], 1)

    def test_concurrent_stock_adjustments_record_serialized_before_and_after_values(self):
        product_id = self._product(10)
        first_read = Event()
        second_attempt = Event()
        release_first = Event()
        errors = []
        results = []
        original_get_product = product_repo.get_product

        def pause_first_adjustment(connection, requested_product_id, lock=False):
            if current_thread().name == "stock-adjust-first":
                product = original_get_product(connection, requested_product_id, lock=lock)
                first_read.set()
                if not release_first.wait(10):
                    raise TimeoutError("Timed out waiting to release the first stock adjustment")
                return product
            if current_thread().name == "stock-adjust-second":
                second_attempt.set()
            return original_get_product(connection, requested_product_id, lock=lock)

        def adjust_stock():
            try:
                product_service.adjust_stock(
                    self.admin_id,
                    product_id,
                    {"quantity_delta": "5", "reason": "Concurrent stock audit test"},
                )
                results.append("ok")
            except Exception as exc:
                errors.append(exc)

        first_thread = Thread(target=adjust_stock, name="stock-adjust-first")
        second_thread = Thread(target=adjust_stock, name="stock-adjust-second")
        second_started = False
        try:
            with patch.object(product_repo, "get_product", side_effect=pause_first_adjustment):
                first_thread.start()
                self.assertTrue(first_read.wait(5))
                second_thread.start()
                second_started = True
                self.assertTrue(second_attempt.wait(5))
                release_first.set()
                first_thread.join(15)
                second_thread.join(15)
            self.assertFalse(first_thread.is_alive())
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(results, ["ok", "ok"])

            with get_connection() as connection:
                product = fetch_one(
                    connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,)
                )
                events = fetch_all(
                    connection,
                    "SELECT details FROM audit_events WHERE entity_type = 'product' "
                    "AND entity_id = %s AND event_type = 'stock.adjusted' ORDER BY id",
                    (product_id,),
                )
                movements = fetch_one(
                    connection,
                    "SELECT COUNT(*) total, SUM(quantity_delta) quantity "
                    "FROM stock_movements WHERE product_id = %s "
                    "AND reason = 'Concurrent stock audit test'",
                    (product_id,),
                )
            transitions = []
            for event in events:
                details = event["details"]
                if isinstance(details, str):
                    details = json.loads(details)
                transitions.append((details["stock_before"], details["stock_after"]))
            self.assertEqual(product["stock_qty"], 20)
            self.assertEqual(transitions, [(10, 15), (15, 20)])
            self.assertEqual(movements, {"total": 2, "quantity": 10})
        finally:
            release_first.set()
            if first_thread.is_alive():
                first_thread.join(15)
            if second_started and second_thread.is_alive():
                second_thread.join(15)
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type = 'product' "
                        "AND entity_id = %s AND event_type = 'stock.adjusted'",
                        (product_id,),
                    )
                    connection.commit()
                finally:
                    cursor.close()

    def test_stock_adjustment_rejects_int_overflow_without_database_error(self):
        product_id = self._product(1)
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE products SET stock_qty = 2147483640 WHERE id = %s",
                    (product_id,),
                )
            finally:
                cursor.close()

        with self.assertRaisesRegex(ValidationError, "2,147,483,647"):
            product_service.adjust_stock(
                self.admin_id,
                product_id,
                {"quantity_delta": "10", "reason": "Overflow boundary test"},
            )

        with get_connection() as connection:
            product = fetch_one(
                connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,)
            )
            audit = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM audit_events WHERE entity_type = 'product' "
                "AND entity_id = %s AND event_type = 'stock.adjusted'",
                (product_id,),
            )
            movement = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM stock_movements WHERE product_id = %s "
                "AND reason = 'Overflow boundary test'",
                (product_id,),
            )
        self.assertEqual(product["stock_qty"], 2_147_483_640)
        self.assertEqual(audit["total"], 0)
        self.assertEqual(movement["total"], 0)


if __name__ == "__main__":
    unittest.main()
