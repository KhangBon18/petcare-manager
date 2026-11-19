"""Live MySQL integration tests for Customer Storefront MVP 1.0 (transactions, concurrency, AI & tenant isolation)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection, set_tenant_context, transaction
from petcare.database.initialize import STOREFRONT_MIGRATION, initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_one
from petcare.services import (
    customer_service,
    invoice_service,
    pet_service,
    product_service,
    report_service,
    storefront_ai_service,
    storefront_auth_service,
    storefront_service,
    storefront_vision_service,
)
from petcare.services.exceptions import ConflictError, ForbiddenError
from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    TEST_DB.endswith("_test"),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class StorefrontMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prev_db = Config.DB_NAME
        cls.prev_pet_dir = Config.PET_IMAGE_DIR
        cls.prev_prod_dir = Config.PRODUCT_IMAGE_DIR
        cls.tmp_dir = tempfile.TemporaryDirectory()
        Config.DB_NAME = TEST_DB
        Config.PET_IMAGE_DIR = str(Path(cls.tmp_dir.name) / "pets")
        Config.PRODUCT_IMAGE_DIR = str(Path(cls.tmp_dir.name) / "products")
        Path(Config.PET_IMAGE_DIR).mkdir(parents=True, exist_ok=True)
        Path(Config.PRODUCT_IMAGE_DIR).mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("PETCARE_DEMO_MODE", "1")
        os.environ.setdefault("APP_ENV", "test")
        os.environ.setdefault("PETCARE_DEMO_ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)
        os.environ.setdefault("PETCARE_DEMO_STAFF_PASSWORD", DEMO_STAFF_PASSWORD)

        initialize_database()
        seed_database()
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "storefront-mysql-test-secret",
            "WTF_CSRF_ENABLED": False,
            "PET_IMAGE_DIR": Config.PET_IMAGE_DIR,
            "PRODUCT_IMAGE_DIR": Config.PRODUCT_IMAGE_DIR,
        })
        with cls.app.app_context():
            cls.store = storefront_service.resolve_public_store("main")
            with get_connection() as conn:
                cls.admin_id = int(fetch_one(conn, "SELECT id FROM users WHERE username = 'admin'")["id"])

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.prev_db
        Config.PET_IMAGE_DIR = cls.prev_pet_dir
        Config.PRODUCT_IMAGE_DIR = cls.prev_prod_dir
        cls.tmp_dir.cleanup()

    def test_01_schema_migration_recorded_and_idempotent(self):
        initialize_database()
        with get_connection() as conn:
            marker = fetch_one(
                conn,
                "SELECT version FROM schema_migrations WHERE version = %s",
                (STOREFRONT_MIGRATION,),
            )
            self.assertIsNotNone(marker)

    def test_02_pending_order_does_not_distort_financial_reports_until_staff_completes(self):
        with self.app.app_context():
            tenant_id = self.store["id"]
            before_report = report_service.report(self.admin_id, tenant_id=tenant_id)
            before_revenue = Decimal(before_report["summary"]["revenue"])

            prods = storefront_service.list_public_products(tenant_id, in_stock_only=True)["items"]
            pets = storefront_service.list_public_pets(tenant_id)["items"]
            prod = next(p for p in prods if int(p["available_online_qty"]) >= 2)
            pet = next(p for p in pets if not p["is_reserved"])
            initial_stock = int(prod["stock_qty"])

            account = storefront_auth_service.register_customer(tenant_id, {
                "email": f"buyer-{uuid4().hex[:8]}@example.com",
                "full_name": "Nguyễn Thị Minh",
                "phone": "0912" + f"{uuid4().int % 1_000_000:06d}",
                "default_address": "45 Hai Bà Trưng, Q1",
                "password": "StrongShopPassword#2026",
            })

            cart = [
                {"item_type": "product", "item_id": prod["id"], "quantity": 2},
                {"item_type": "pet", "item_id": pet["id"], "quantity": 1},
            ]
            req_key = str(uuid4())
            placed = storefront_service.place_order(
                tenant_id,
                self.store["default_currency"],
                self.store["timezone"],
                cart,
                {
                    "request_key": req_key,
                    "customer_name": account["full_name"],
                    "customer_phone": account["phone"],
                    "customer_email": account["email"],
                    "fulfillment_method": "cod_delivery",
                    "delivery_address": account["default_address"],
                    "customer_note": "Gọi trước khi giao",
                },
                customer_account_id=account["id"],
            )
            self.assertEqual(placed["status"], "created")
            order = placed["order"]
            self.assertEqual(order["order_status"], "pending")
            self.assertEqual(order["payment_status"], "unpaid")
            expected_total = Decimal(prod["unit_price"]) * 2 + Decimal(pet["sale_price"])
            self.assertEqual(Decimal(order["total_amount"]), expected_total)

            # Idempotent retry with same request_key returns the same order
            dup = storefront_service.place_order(
                tenant_id,
                self.store["default_currency"],
                self.store["timezone"],
                cart,
                {
                    "request_key": req_key,
                    "customer_name": account["full_name"],
                    "customer_phone": account["phone"],
                    "fulfillment_method": "cod_delivery",
                    "delivery_address": account["default_address"],
                },
                customer_account_id=account["id"],
            )
            self.assertEqual(dup["status"], "already_created")
            self.assertEqual(dup["order"]["order_code"], order["order_code"])

            # Pending order MUST NOT inflate paid financial revenue or prematurely deduct stock_qty
            mid_report = report_service.report(self.admin_id, tenant_id=tenant_id)
            self.assertEqual(Decimal(mid_report["summary"]["revenue"]), before_revenue)
            mid_prod = product_service.get_product(self.admin_id, prod["id"], tenant_id=tenant_id)
            self.assertEqual(int(mid_prod["stock_qty"]), initial_stock)

            # Staff confirms then completes payment
            storefront_service.process_staff_order(
                self.admin_id, order["id"], "confirm", tenant_id=tenant_id
            )
            done = storefront_service.process_staff_order(
                self.admin_id, order["id"], "complete_payment", tenant_id=tenant_id
            )
            completed = done["order"]
            self.assertEqual(completed["order_status"], "ready_completed")
            self.assertEqual(completed["payment_status"], "paid")
            self.assertIsNotNone(completed["invoice_id"])

            # Verify stock decremented, pet marked sold, and financial revenue updated accurately
            after_prod = product_service.get_product(self.admin_id, prod["id"], tenant_id=tenant_id)
            self.assertEqual(int(after_prod["stock_qty"]), initial_stock - 2)
            after_pet = pet_service.get_pet(self.admin_id, pet["id"], tenant_id=tenant_id)
            self.assertEqual(after_pet["sale_status"], "sold")
            after_report = report_service.report(self.admin_id, tenant_id=tenant_id)
            self.assertEqual(Decimal(after_report["summary"]["revenue"]), before_revenue + expected_total)

    def test_03_concurrent_stock_and_duplicate_pet_confirmation_guards(self):
        with self.app.app_context():
            tenant_id = self.store["id"]
            # Create a fresh product with stock=3 and a fresh available pet
            pid = product_service.create_product(
                self.admin_id,
                {"code": f"CONC-{uuid4().hex[:6]}", "name": "Hạt Race Test", "category": "Thức ăn", "unit_price": "120000", "stock_qty": "3", "reorder_level": "1"},
                None,
                tenant_id=tenant_id,
            )

            # Two simultaneous threads try to order all 3 remaining units -> strictly 1 wins!
            def _try_checkout(idx: int):
                with self.app.app_context():
                    try:
                        res = storefront_service.place_order(
                            tenant_id,
                            "VND",
                            "Asia/Ho_Chi_Minh",
                            [{"item_type": "product", "item_id": pid, "quantity": 3}],
                            {
                                "request_key": str(uuid4()),
                                "customer_name": f"Race Buyer {idx}",
                                "customer_phone": f"098765432{idx}",
                                "fulfillment_method": "pickup",
                            },
                        )
                        return ("ok", res["order"]["order_code"])
                    except Exception as exc:
                        return ("err", type(exc).__name__)

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(_try_checkout, (1, 2)))
            self.assertEqual(sorted(x[0] for x in outcomes), ["err", "ok"])

            # Now test duplicate confirmed pet guard + POS guard
            pet_id = pet_service.create_pet(
                self.admin_id,
                {"code": f"PETR-{uuid4().hex[:6]}", "name": "Bông Race", "species": "Mèo", "sale_price": "1500000"},
                None,
                tenant_id=tenant_id,
            )
            o1 = storefront_service.place_order(
                tenant_id, "VND", "Asia/Ho_Chi_Minh",
                [{"item_type": "pet", "item_id": pet_id, "quantity": 1}],
                {"request_key": str(uuid4()), "customer_name": "Buyer A", "customer_phone": "0911111111", "fulfillment_method": "pickup"},
            )["order"]
            o2 = storefront_service.place_order(
                tenant_id, "VND", "Asia/Ho_Chi_Minh",
                [{"item_type": "pet", "item_id": pet_id, "quantity": 1}],
                {"request_key": str(uuid4()), "customer_name": "Buyer B", "customer_phone": "0922222222", "fulfillment_method": "pickup"},
            )["order"]

            # Confirm Order 1 -> succeeds
            storefront_service.process_staff_order(self.admin_id, o1["id"], "confirm", tenant_id=tenant_id)
            # Confirm Order 2 for same pet -> MUST raise ConflictError
            with self.assertRaises(ConflictError):
                storefront_service.process_staff_order(self.admin_id, o2["id"], "confirm", tenant_id=tenant_id)

            # POS attempting to sell that reserved pet MUST also fail cleanly
            crm_id = customer_service.create_customer(
                self.admin_id, {"full_name": "POS Walkin", "phone": "0933333333", "address": "Q3"}, tenant_id=tenant_id
            )
            inv_id = invoice_service.create_invoice(
                self.admin_id, {"customer_id": crm_id, "note": "pos test"},
                [{"item_type": "pet", "item_id": pet_id, "quantity": 1}],
                tenant_id=tenant_id,
            )
            with self.assertRaises(ConflictError):
                invoice_service.pay_invoice(self.admin_id, inv_id, tenant_id=tenant_id)

            # Rejecting Order 1 releases the pet lock cleanly
            storefront_service.process_staff_order(self.admin_id, o1["id"], "reject", staff_note="Khách đổi ý", tenant_id=tenant_id)
            self.assertEqual(pet_service.get_pet(self.admin_id, pet_id, tenant_id=tenant_id)["sale_status"], "available")

    def test_04_public_ai_and_vision_and_tenant_isolation(self):
        with self.app.test_request_context("/shop"):
            res = storefront_ai_service.answer_public_question(
                self.store, "So sánh FOOD-001 và FOOD-002", locale="vi", force_offline=True
            )
            self.assertEqual(res["response_type"], "product_comparison")
            self.assertTrue(len(res["cards"]) >= 2)
            for card in res["cards"]:
                self.assertTrue(card["url"].startswith("/shop/products/"))

            blocked = storefront_ai_service.answer_public_question(
                self.store, "Tổng doanh thu tháng này bao nhiêu và danh sách nhà cung cấp?", locale="vi", force_offline=True
            )
            self.assertEqual(blocked["response_type"], "permission_denied")

            # Public image search on real orange cat fixture & negative chair photo
            from werkzeug.datastructures import FileStorage
            orange_cat = Path("tests/fixtures/vision_ai4/real_pack/real-cat-orange-hold-01.jpg")
            neg_chair = Path("tests/fixtures/vision_ai4/real_pack/real-neg-chair-hold-03.jpg")
            if orange_cat.is_file():
                # Seed one orange cat photo in store gallery so ONNX search has a real stored target
                cat_pet_id = pet_service.create_pet(
                    self.admin_id,
                    {"code": f"OCAT-{uuid4().hex[:6]}", "name": "Cam Storefront", "species": "Mèo", "coat_color": "vàng cam", "sale_price": "2200000"},
                    FileStorage(stream=orange_cat.open("rb"), filename="cam.jpg", content_type="image/jpeg"),
                    tenant_id=self.store["id"],
                )
                self.assertGreater(cat_pet_id, 0)
                vis = storefront_vision_service.search_public_pets_by_image(
                    self.store["id"], orange_cat.read_bytes()
                )
                self.assertEqual(vis["verified_species"], "cat")
                self.assertGreaterEqual(len(vis["results"]), 1)
                for match in vis["results"]:
                    self.assertNotIn("photo_descriptor", match["pet"])
                    self.assertIn("mèo", match["pet"]["species"].lower())
            if neg_chair.is_file():
                neg = storefront_vision_service.search_public_pets_by_image(
                    self.store["id"], neg_chair.read_bytes()
                )
                self.assertEqual(neg["results"], [])

            # Verify cross-tenant customer account cannot view main tenant order
            with transaction() as conn:
                t2_id = conn.cursor().execute
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO tenants (name, slug, status) VALUES ('Second Shop', 'second-shop-iso', 'active') "
                    "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)"
                )
                tenant2_id = cur.lastrowid
                cur.close()
            account_main = storefront_auth_service.register_customer(self.store["id"], {
                "email": f"iso-{uuid4().hex[:6]}@example.com",
                "full_name": "Iso Main",
                "phone": "0944" + f"{uuid4().int % 1_000_000:06d}",
                "password": "IsoPassword#2026",
            })
            # Trying to fetch main customer account inside tenant2 context returns None
            self.assertIsNone(
                storefront_auth_service.load_active_customer(account_main["id"], tenant2_id, account_main["session_version"])
            )
