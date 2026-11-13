"""End-to-end MySQL integration tests for PetCare AI multi-turn memory, RBAC, scope, and tenant isolation."""

from __future__ import annotations

from decimal import Decimal
import os
import re
import unittest
from uuid import uuid4

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

from petcare import create_app
from petcare.ai.contracts import ResponseType
from petcare.ai.memory import MEMORY_STORE
from petcare.config import Config
from petcare.database.connection import get_connection, transaction
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_all, fetch_one


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class PetCareAIMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        MEMORY_STORE.clear_all()
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "petcare-ai-mysql-integration-secret",
            "WTF_CSRF_ENABLED": True,
            "ASSISTANT_RATE_LIMIT_PER_MINUTE": 1000,
            "ASSISTANT_IP_RATE_LIMIT_PER_MINUTE": 1000,
            "AI_PROVIDER_APPROVED": False,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
        })

    @classmethod
    def tearDownClass(cls):
        try:
            with transaction() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE users SET preferred_locale = 'vi' WHERE username IN ('admin', 'staff1')")
                finally:
                    cur.close()
        finally:
            MEMORY_STORE.clear_all()
            Config.DB_NAME = cls.previous_db_name

    def _login(self, username: str, password: str, *, store_slug: str = "main", locale: str = "en"):
        client = self.app.test_client()
        client.post("/language", data={"locale": locale, "next": "/login"})
        login_page = client.get("/login")
        html = login_page.get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(token)
        resp = client.post(
            "/login",
            data={
                "csrf_token": token.group(1),
                "store_slug": store_slug,
                "username": username,
                "password": password,
            },
        )
        self.assertEqual(resp.status_code, 302)
        return client

    def _workspace_csrf(self, client) -> str:
        resp = client.get("/assistant/chat")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        match = re.search(r'data-csrf-token="([^"]+)"', html)
        self.assertIsNotNone(match)
        return match.group(1)

    def _chat(self, client, csrf: str, message: str, *, scope: str = "workspace", conv_id: str = "conv_it_1"):
        resp = client.post(
            "/assistant/chat",
            headers={"X-CSRFToken": csrf},
            json={
                "message": message,
                "scope": scope,
                "conversation_id": conv_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_multiturn_apartment_cat_matching_and_budget_update_persist_in_session(self):
        client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="en")
        csrf = self._workspace_csrf(client)
        conv_id = f"conv_pet_{uuid4().hex[:8]}"

        # Turn 1: Missing budget & temperament -> asks guided clarification
        t1 = self._chat(
            client,
            csrf,
            "I want a cat suitable for an apartment.",
            scope="shopper_preview",
            conv_id=conv_id,
        )
        self.assertEqual(t1["response_type"], ResponseType.CLARIFICATION.value)
        self.assertTrue(len(t1["follow_up_questions"]) >= 2)

        # Turn 2: Supplies temperament + 8M VND ceiling -> merges with cat + apartment from Turn 1
        t2 = self._chat(
            client,
            csrf,
            "Calm, below 8 million VND.",
            scope="shopper_preview",
            conv_id=conv_id,
        )
        self.assertEqual(t2["response_type"], ResponseType.PET_RECOMMENDATIONS.value)
        self.assertTrue(len(t2["cards"]) >= 1)

        with get_connection() as conn:
            main_tenant = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", ("main",))
            db_pets = {
                row["code"]: row
                for row in fetch_all(
                    conn,
                    "SELECT code, species, sale_price, sale_status FROM pets WHERE tenant_id = %s",
                    (main_tenant["id"],),
                )
            }

        for card in t2["cards"]:
            self.assertIn(card["code"], db_pets)
            db_row = db_pets[card["code"]]
            self.assertEqual(db_row["sale_status"], "available")
            self.assertLessEqual(Decimal(str(db_row["sale_price"])), Decimal("8000000"))
            self.assertTrue(card["url"].startswith("/pets/"))

        # Turn 3: Tightens budget to 6 million VND while retaining cat + apartment + calm
        t3 = self._chat(
            client,
            csrf,
            "What about below 6 million VND?",
            scope="shopper_preview",
            conv_id=conv_id,
        )
        self.assertEqual(t3["response_type"], ResponseType.PET_RECOMMENDATIONS.value)
        for card in t3["cards"]:
            self.assertLessEqual(Decimal(str(db_pets[card["code"]]["sale_price"])), Decimal("6000000"))

        # Reset clears context chips cleanly
        reset_resp = client.post(
            "/assistant/reset",
            headers={"X-CSRFToken": csrf},
            json={"scope": "shopper_preview", "conversation_id": conv_id},
        )
        self.assertEqual(reset_resp.status_code, 200)
        self.assertEqual(reset_resp.get_json()["context_state"]["chips"], [])

    def test_product_recommendation_unit_prices_and_contextual_comparison_match_mysql_catalog(self):
        client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="en")
        csrf = self._workspace_csrf(client)
        conv_id = f"conv_prod_{uuid4().hex[:8]}"

        rec = self._chat(
            client,
            csrf,
            "Which food should I consider for my adult cat?",
            scope="shopper_preview",
            conv_id=conv_id,
        )
        self.assertEqual(rec["response_type"], ResponseType.PRODUCT_RECOMMENDATIONS.value)
        self.assertGreaterEqual(len(rec["cards"]), 2)
        self.assertTrue(any(card.get("unit_price_display") for card in rec["cards"]))

        cmp_res = self._chat(
            client,
            csrf,
            "Compare these three products",
            scope="shopper_preview",
            conv_id=conv_id,
        )
        self.assertEqual(cmp_res["response_type"], ResponseType.PRODUCT_COMPARISON.value)
        self.assertIsNotNone(cmp_res["comparison"])
        self.assertGreaterEqual(len(cmp_res["comparison"]["items"]), 2)

        with get_connection() as conn:
            main_tenant = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", ("main",))
            db_products = {
                row["code"]: row
                for row in fetch_all(
                    conn,
                    "SELECT code, unit_price, stock_qty, active FROM products WHERE tenant_id = %s",
                    (main_tenant["id"],),
                )
            }

        for item in cmp_res["comparison"]["items"]:
            self.assertIn(item["code"], db_products)
            self.assertEqual(db_products[item["code"]]["active"], 1)
            self.assertTrue(item["url"].startswith("/products/"))

    def test_rbac_shopper_preview_isolation_and_cross_tenant_catalog_boundary(self):
        rival_slug = f"rival-{uuid4().hex[:6]}"
        create_store(
            rival_slug,
            "Rival Isolated Pet Shop",
            "rival_admin",
            "Rival Admin",
            DEMO_ADMIN_PASSWORD,
        )
        with transaction() as conn:
            rival = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", (rival_slug,))
            cursor = conn.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (rival["id"],))
                cursor.execute(
                    """
                    INSERT INTO pets (tenant_id, code, name, species, breed, sex, sale_price, sale_status, appearance_tags)
                    VALUES (%s, 'PET-RIVAL-999', 'SecretRivalCat', 'Mèo', 'Anh lông ngắn', 'female', 4500000, 'available', 'hiền, nhỏ gọn')
                    """,
                    (rival["id"],),
                )
                cursor.execute(
                    """
                    INSERT INTO products (tenant_id, code, name, category, description, unit_price, stock_qty, reorder_level, active)
                    VALUES (%s, 'FOOD-RIVAL-999', 'Secret Rival Cat Food 2kg', 'Thức ăn', 'Thức ăn mèo trưởng thành', 200000, 20, 3, 1)
                    """,
                    (rival["id"],),
                )
            finally:
                cursor.close()

        admin_client = self._login("admin", DEMO_ADMIN_PASSWORD, locale="en")
        admin_csrf = self._workspace_csrf(admin_client)
        staff_client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="en")
        staff_csrf = self._workspace_csrf(staff_client)

        # 1. Admin in workspace CAN run 8-week demand forecast
        admin_forecast = self._chat(
            admin_client,
            admin_csrf,
            "Show 8-week inventory demand forecast",
            scope="workspace",
            conv_id="conv_rbac_admin",
        )
        self.assertEqual(admin_forecast["response_type"], ResponseType.OPERATIONAL_INSIGHT.value)
        self.assertEqual(admin_forecast["insight"]["kind"], "inventory_forecast")

        # 2. Staff in workspace is DENIED 8-week demand forecast & purchase order status
        staff_forecast = self._chat(
            staff_client,
            staff_csrf,
            "Show 8-week inventory demand forecast",
            scope="workspace",
            conv_id="conv_rbac_staff",
        )
        self.assertEqual(staff_forecast["response_type"], ResponseType.PERMISSION_DENIED.value)

        # 3. Admin in Shopper Preview is DENIED internal restock / sales / forecast tools
        shopper_denied = self._chat(
            admin_client,
            admin_csrf,
            "Which products sold the most this week?",
            scope="shopper_preview",
            conv_id="conv_shopper_rbac",
        )
        self.assertEqual(shopper_denied["response_type"], ResponseType.PERMISSION_DENIED.value)

        # 4. Cross-tenant isolation: main tenant NEVER sees PET-RIVAL-999 or FOOD-RIVAL-999
        cross_cmp = self._chat(
            admin_client,
            admin_csrf,
            "Compare FOOD-001 and FOOD-RIVAL-999",
            scope="workspace",
            conv_id="conv_cross_tenant",
        )
        self.assertEqual(cross_cmp["response_type"], ResponseType.CLARIFICATION.value)
        self.assertIsNone(cross_cmp.get("comparison"))

        cross_pets = self._chat(
            admin_client,
            admin_csrf,
            "Recommend a calm cat for an apartment under 8 million VND",
            scope="shopper_preview",
            conv_id="conv_cross_pets",
        )
        returned_pet_codes = [c["code"] for c in cross_pets.get("cards", [])]
        self.assertNotIn("PET-RIVAL-999", returned_pet_codes)

        # 5. Missing CSRF token on POST /assistant/chat is rejected with 400
        no_csrf = admin_client.post("/assistant/chat", json={"message": "Hello"})
        self.assertEqual(no_csrf.status_code, 400)


if __name__ == "__main__":
    unittest.main()
