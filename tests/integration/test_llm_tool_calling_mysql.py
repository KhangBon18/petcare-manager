"""End-to-end MySQL integration tests for AI-2 LLM Tool-Calling Orchestration via /assistant/chat."""

from __future__ import annotations

import os
import re
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

from petcare import create_app
from petcare.ai.contracts import EngineMode, ResponseType
from petcare.ai.llm_tool_agent import MockToolCallingAdapter, ModelTurnOutput, ProposedToolCall
from petcare.ai.memory import MEMORY_STORE
from petcare.config import Config
from petcare.database.connection import get_connection, transaction
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_one
from petcare.security import hash_password


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class LLMToolCallingMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        with transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE users SET password_hash = %s, active = 1 WHERE username = 'admin'",
                    (hash_password(DEMO_ADMIN_PASSWORD),),
                )
                cur.execute(
                    "UPDATE users SET password_hash = %s, active = 1 WHERE username = 'staff1'",
                    (hash_password(DEMO_STAFF_PASSWORD),),
                )
            finally:
                cur.close()
        MEMORY_STORE.clear_all()
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "petcare-ai2-mysql-integration-secret",
            "WTF_CSRF_ENABLED": True,
            "ASSISTANT_RATE_LIMIT_PER_MINUTE": 1000,
            "ASSISTANT_IP_RATE_LIMIT_PER_MINUTE": 1000,
            "AI_PROVIDER_APPROVED": False,
            "AI_TOOL_CALLING_ENABLED": False,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
        })

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            MEMORY_STORE.clear_all()
        finally:
            cls.app.config.pop("AI_TOOL_CALLING_ADAPTER", None)
            Config.DB_NAME = cls.previous_db_name

    def setUp(self) -> None:
        self.network_guard = patch(
            "petcare.ai.client.build_opener",
            side_effect=AssertionError("External network egress is strictly forbidden in MySQL integration tests!"),
        )
        self.network_guard.start()

    def tearDown(self) -> None:
        self.app.config.pop("AI_TOOL_CALLING_ADAPTER", None)
        self.network_guard.stop()

    def _login(self, username: str, password: str, *, store_slug: str = "main", locale: str = "vi"):
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

    def _chat(self, client, csrf: str, message: str, *, scope: str = "workspace", conv_id: str = "conv_ai2_it"):
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

    def test_multi_tool_chat_route_combines_live_mysql_products_and_reviewed_kb_citations(self) -> None:
        with get_connection() as conn:
            main_tenant = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", ("main",))
            food_row = fetch_one(
                conn,
                "SELECT id, code, unit_price FROM products WHERE tenant_id = %s AND code = 'FOOD-001'",
                (main_tenant["id"],),
            )
            self.assertIsNotNone(food_row)
            exact_price = int(food_row["unit_price"])
            formatted_price = f"{exact_price:,}".replace(",", ".")

        adapter = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(
                    ProposedToolCall(
                        call_id="it_kb_1",
                        tool_name="search_pet_care_knowledge",
                        raw_arguments={"query": "chuyển đổi thức ăn 7 10 ngày", "species_hint": "cat"},
                    ),
                    ProposedToolCall(
                        call_id="it_prod_2",
                        tool_name="recommend_products",
                        raw_arguments={"species": "cat", "life_stage": "adult", "product_category": "food"},
                    ),
                )
            ),
            ModelTurnOutput(
                assistant_text=(
                    f"Theo tài liệu KB-NUTR-001, bạn nên trộn thức ăn mới tăng dần trong 7–10 ngày. "
                    f"Sản phẩm phù hợp đang có tại cửa hàng là FOOD-001 giá {formatted_price} VND."
                )
            ),
        ])
        self.app.config["AI_TOOL_CALLING_ADAPTER"] = adapter

        client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="vi")
        csrf = self._workspace_csrf(client)
        payload = self._chat(
            client,
            csrf,
            "Cách đổi hạt mới cho mèo trong 7-10 ngày và gợi ý hạt cho mèo trưởng thành?",
            scope="shopper_preview",
            conv_id=f"conv_ai2_multi_{uuid4().hex[:6]}",
        )
        self.assertEqual(payload["engine_mode"], EngineMode.REAL_LLM.value)
        self.assertFalse(payload["fallback_used"])
        self.assertTrue(any(c["doc_id"] == "KB-NUTR-001" for c in payload.get("citations", [])))
        self.assertTrue(any(c["code"] == "FOOD-001" for c in payload.get("cards", [])))

    def test_cross_tenant_product_id_and_staff_rbac_enforced_by_mysql_and_tool_registry(self) -> None:
        rival_slug = f"rival-ai2-{uuid4().hex[:6]}"
        rival_user = f"rival_ai2_{uuid4().hex[:6]}"
        create_store(
            rival_slug,
            "Rival AI2 Store",
            rival_user,
            "Rival AI2 Admin",
            DEMO_ADMIN_PASSWORD,
        )
        with transaction() as conn:
            rival = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", (rival_slug,))
            cursor = conn.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (rival["id"],))
                cursor.execute(
                    """
                    INSERT INTO products (tenant_id, code, name, category, description, unit_price, stock_qty, reorder_level, active)
                    VALUES (%s, 'RIVAL-AI2-999', 'Secret Rival Salmon Bag', 'Thức ăn', 'Mật', 333000, 15, 2, 1)
                    """,
                    (rival["id"],),
                )
                rival_product_id = int(cursor.lastrowid)
            finally:
                cursor.close()

        # 1. Main-store admin session cannot read `rival_product_id` via `get_product_details`
        adapter_xtenant = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(
                    ProposedToolCall(
                        call_id="xt_1",
                        tool_name="get_product_details",
                        raw_arguments={"product_id": rival_product_id},
                    ),
                )
            ),
            ModelTurnOutput(assistant_text="Không tìm thấy mã sản phẩm đó trong cửa hàng hiện tại."),
        ])
        self.app.config["AI_TOOL_CALLING_ADAPTER"] = adapter_xtenant

        admin_client = self._login("admin", DEMO_ADMIN_PASSWORD, locale="vi")
        admin_csrf = self._workspace_csrf(admin_client)
        xt_payload = self._chat(
            admin_client,
            admin_csrf,
            f"Xem chi tiết sản phẩm ID {rival_product_id}",
            scope="workspace",
            conv_id=f"conv_ai2_xt_{uuid4().hex[:6]}",
        )
        self.assertEqual(xt_payload["tool_trace"][0]["status"], "not_found")
        self.assertNotIn("Secret Rival Salmon Bag", xt_payload["reply"])
        self.assertEqual(xt_payload.get("cards", []), [])

        # 2. Staff session cannot invoke admin-only `get_purchase_status` even when requested by the model
        adapter_rbac = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(
                    ProposedToolCall(
                        call_id="rbac_1",
                        tool_name="get_purchase_status",
                        raw_arguments={"question": "purchase order status"},
                    ),
                )
            ),
        ])
        self.app.config["AI_TOOL_CALLING_ADAPTER"] = adapter_rbac

        staff_client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="vi")
        staff_csrf = self._workspace_csrf(staff_client)
        rbac_payload = self._chat(
            staff_client,
            staff_csrf,
            "Cho xem đơn nhập hàng nhà cung cấp",
            scope="workspace",
            conv_id=f"conv_ai2_rbac_{uuid4().hex[:6]}",
        )
        self.assertEqual(rbac_payload["response_type"], ResponseType.PERMISSION_DENIED.value)
        self.assertEqual(rbac_payload["status"], "forbidden")
        self.assertEqual(rbac_payload["tool_trace"][0]["status"], "denied")

    def test_hallucinated_price_intercepted_on_live_chat_endpoint(self) -> None:
        adapter_halluc = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(
                    ProposedToolCall(
                        call_id="hal_1",
                        tool_name="compare_products",
                        raw_arguments={"explicit_codes": ["FOOD-001", "FOOD-002"]},
                    ),
                )
            ),
            # Model invents an ungrounded 12.000 VND promo price -> server replaces with verified comparison summary!
            ModelTurnOutput(assistant_text="FOOD-001 đang khuyến mãi sốc chỉ còn 12.000 VND so với FOOD-002!"),
        ])
        self.app.config["AI_TOOL_CALLING_ADAPTER"] = adapter_halluc

        client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="vi")
        csrf = self._workspace_csrf(client)
        payload = self._chat(
            client,
            csrf,
            "So sánh FOOD-001 và FOOD-002",
            scope="shopper_preview",
            conv_id=f"conv_ai2_hal_{uuid4().hex[:6]}",
        )
        self.assertTrue(payload["fallback_used"])
        self.assertIn("ungrounded_or_contradictory_price:12000", payload["fallback_reason"])
        self.assertNotIn("12.000", payload["reply"])
        self.assertEqual(payload["response_type"], ResponseType.PRODUCT_COMPARISON.value)
        self.assertIsNotNone(payload.get("comparison"))

    def test_vet_safety_triage_blocks_malicious_llm_shopping_and_offline_multi_ops_enforces_rbac(self) -> None:
        # 1. Even with a MockToolCallingAdapter trying to recommend cat litter, descriptive urinary blockage escalates pre-LLM
        bypass_adapter = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(
                    ProposedToolCall("evil_1", "recommend_products", {"species": "cat", "product_category": "litter"}),
                )
            ),
            ModelTurnOutput(assistant_text="Hãy đổi sang cát vệ sinh CARE-001 nhé!"),
        ])
        self.app.config["AI_TOOL_CALLING_ADAPTER"] = bypass_adapter

        shopper_client = self._login("staff1", DEMO_STAFF_PASSWORD, locale="en")
        shopper_csrf = self._workspace_csrf(shopper_client)
        vet_payload = self._chat(
            shopper_client,
            shopper_csrf,
            "My male cat keeps straining in the litter box but has produced no urine since last night.",
            scope="shopper_preview",
            conv_id=f"conv_ai21_vet_{uuid4().hex[:6]}",
        )
        self.assertEqual(bypass_adapter.call_count, 0)
        self.assertEqual(vet_payload["safety_notice"]["severity"], "emergency")
        self.assertEqual(vet_payload.get("cards", []), [])

        # 2. Offline multi-intent operational workflow: staff gets sales ranking + partial-success omission on admin-only 8-week forecast
        self.app.config.pop("AI_TOOL_CALLING_ADAPTER", None)
        staff_vi = self._login("staff1", DEMO_STAFF_PASSWORD, locale="vi")
        staff_vi_csrf = self._workspace_csrf(staff_vi)
        partial_ops = self._chat(
            staff_vi,
            staff_vi_csrf,
            "Trong 7 ngày qua mặt hàng nào bán chạy nhất và đồng thời cho xem dự báo nhu cầu 8 tuần?",
            scope="workspace",
            conv_id=f"conv_ai21_ops_{uuid4().hex[:6]}",
        )
        self.assertEqual(partial_ops["response_type"], ResponseType.OPERATIONAL_INSIGHT.value)
        self.assertEqual(partial_ops["insight"]["kind"], "combined_operational")
        self.assertEqual(len(partial_ops["insight"]["sections"]), 1)
        self.assertEqual(partial_ops["insight"]["sections"][0]["kind"], "top_products")
        self.assertEqual(
            [(t["tool_name"], t["status"]) for t in partial_ops["tool_trace"]],
            [("get_sales_summary", "ok"), ("get_inventory_forecast", "denied")],
        )
        self.assertTrue(len(partial_ops.get("missing_data", [])) >= 1)


if __name__ == "__main__":
    unittest.main()
