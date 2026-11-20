import json
import os
import re
import unittest
from uuid import uuid4

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.repositories.base import execute, fetch_one


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class StorePublicPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "store-policy-tests-only",
            "WTF_CSRF_ENABLED": True,
        })

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.previous_db_name

    def _login(self, username, password, store_slug="main"):
        client = self.app.test_client()
        html = client.get("/login").get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        resp = client.post(
            "/login",
            data={"csrf_token": csrf, "store_slug": store_slug, "username": username, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        return client

    def _csrf(self, client, path):
        html = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def test_public_policy_crud_security_validation_isolation_and_storefront_render(self):
        slug = "s2pol-" + uuid4().hex[:8]
        admin_user = "s2admin_" + uuid4().hex[:6]
        staff_user = "s2staff_" + uuid4().hex[:6]
        password = "PolicyTest@123"
        tenant_id, admin_id = create_store(slug, "Policy Test Shop", admin_user, "Owner Policy", password)

        # Create a staff member inside this store to verify RBAC enforcement.
        with get_connection() as connection:
            from petcare.security import hash_password
            staff_id = execute(
                connection,
                "INSERT INTO users (username, password_hash, full_name, role, active) VALUES (%s, %s, %s, 'staff', 1)",
                (staff_user, hash_password(password), "Staff Policy"),
            )[0]
            execute(
                connection,
                "INSERT INTO tenant_users (tenant_id, user_id, role, active) VALUES (%s, %s, 'staff', 1)",
                (tenant_id, staff_id),
            )
            connection.commit()

        admin_client = self._login(admin_user, password, slug)
        staff_client = self._login(staff_user, password, slug)
        try:
            # 1. Staff cannot GET or POST /store/settings/public-policies (403).
            self.assertEqual(staff_client.get("/store/settings").status_code, 403)
            self.assertEqual(
                staff_client.post(
                    "/store/settings/public-policies",
                    data={"csrf_token": self._csrf(staff_client, "/dashboard"), "pickup_address": "Hack"},
                ).status_code,
                403,
            )

            # 2. Validation rejects javascript: URL, invalid email, invalid hotline and preserves input.
            bad_resp = admin_client.post(
                "/store/settings/public-policies",
                data={
                    "csrf_token": self._csrf(admin_client, "/store/settings"),
                    "pickup_address": "18 Nguyen Hue <script>alert(1)</script>",
                    "support_hotline": "abc-invalid",
                    "support_email": "not-an-email",
                    "privacy_terms_url": "javascript:alert(1)",
                },
            )
            self.assertEqual(bad_resp.status_code, 200)
            bad_html = bad_resp.get_data(as_text=True)
            self.assertIn("aria-invalid=\"true\"", bad_html)
            self.assertIn("privacy_terms_url-error", bad_html)
            self.assertIn("support_email-error", bad_html)
            self.assertIn("support_hotline-error", bad_html)

            # 3. Valid save + HTML XSS escape + audit event recorded without sensitive values.
            save_resp = admin_client.post(
                "/store/settings/public-policies",
                data={
                    "csrf_token": self._csrf(admin_client, "/store/settings"),
                    "pickup_address": "18 Nguyễn Huệ <b>Quận 1</b>",
                    "opening_hours": "08:30 – 20:30",
                    "cod_service_area_fees": "Nội thành TP.HCM · báo phí thực tế trước khi xuất đơn",
                    "order_confirmation_sla": "Liên hệ trong 30 phút giờ mở cửa",
                    "return_refund_policy": "Đổi trả trong 3 ngày với bao bì còn nguyên tem",
                    "cancellation_instructions": "Gọi hotline trước khi đơn giao",
                    "pet_handover_policy": "Xem bé trực tiếp và bàn giao sổ tiêm phòng",
                    "support_hotline": "0909 111 222",
                    "support_zalo": "https://zalo.me/petcaretest",
                    "support_email": "CSKH@Example.COM",
                    "privacy_terms_url": "https://example.com/terms",
                    "privacy_terms_summary": "Chính sách bảo mật thử nghiệm đã duyệt",
                },
                follow_redirects=False,
            )
            self.assertEqual(save_resp.status_code, 302)

            with get_connection() as connection:
                saved = fetch_one(
                    connection,
                    "SELECT * FROM tenant_public_policies WHERE tenant_id = %s",
                    (tenant_id,),
                )
                event = fetch_one(
                    connection,
                    "SELECT event_type, details FROM audit_events WHERE tenant_id = %s AND actor_user_id = %s AND event_type = 'tenant.public_policies_updated' ORDER BY id DESC LIMIT 1",
                    (tenant_id, admin_id),
                )
            self.assertEqual(saved["support_email"], "cskh@example.com")
            details = json.loads(event["details"]) if isinstance(event["details"], str) else event["details"]
            self.assertIn("pickup_address", details["changed_fields"])

            # 4. Public storefront for this store renders escaped values; main store remains isolated!
            self.app.config["PUBLIC_STORE_SLUG"] = slug
            shop_html = self.app.test_client().get("/shop").get_data(as_text=True)
            self.assertIn("18 Nguyễn Huệ &lt;b&gt;Quận 1&lt;/b&gt;", shop_html)
            self.assertIn("https://example.com/terms", shop_html)
            self.assertIn("0909 111 222", shop_html)

            # Tenant isolation: main store does NOT get s2pol policies.
            self.app.config["PUBLIC_STORE_SLUG"] = "main"
            main_shop_html = self.app.test_client().get("/shop").get_data(as_text=True)
            self.assertNotIn("0909 111 222", main_shop_html)
            self.assertNotIn("https://example.com/terms", main_shop_html)

            # 5. Clearing all fields restores preview placeholder without fabricating data.
            self.app.config["PUBLIC_STORE_SLUG"] = slug
            clear_resp = admin_client.post(
                "/store/settings/public-policies",
                data={"csrf_token": self._csrf(admin_client, "/store/settings")},
                follow_redirects=False,
            )
            self.assertEqual(clear_resp.status_code, 302)
            cleared_shop_html = self.app.test_client().get("/shop").get_data(as_text=True)
            self.assertIn("đang chờ chủ cửa hàng xác nhận", cleared_shop_html)
        finally:
            self.app.config["PUBLIC_STORE_SLUG"] = "main"
            with get_connection() as connection:
                with connection.cursor() as cur:
                    cur.execute("DELETE FROM tenant_public_policies WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (staff_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (admin_id,))
                    cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                connection.commit()


if __name__ == "__main__":
    unittest.main()
