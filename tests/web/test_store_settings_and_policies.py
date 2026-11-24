import json
import os
from pathlib import Path
import re
import unittest
from uuid import uuid4

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.i18n import translate
from petcare.repositories.base import execute, fetch_one
from petcare.services import tenant_settings_service
from petcare.services.exceptions import ValidationError


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")
REPO_ROOT = Path(__file__).resolve().parents[2]


class StorePublicPolicyUnitContractTests(unittest.TestCase):
    def test_url_validator_rejects_malformed_brackets_bad_ports_and_invalid_hostnames(self):
        invalid_urls = [
            "https://[broken",
            "http://[::1",
            "https://[2001:db8::1/terms",
            "https://example.test:99999",
            "https://example.test:0",
            "https://example.test:65536",
            "https://example.test:abc",
            "https://:443/terms",
            "https://[]:443/terms",
            "https://bad..example.com/terms",
            "https://.example.com/terms",
            "https://example.com./terms",
            "https://foo[bar]/terms",
            "https://-bad.example.com/terms",
        ]
        for raw in invalid_urls:
            with self.subTest(url=raw):
                with self.assertRaises(ValidationError) as ctx:
                    tenant_settings_service._validated_http_url(raw, "Liên kết điều khoản / bảo mật")
                self.assertEqual(tenant_settings_service._is_safe_http_href(raw), "")
                en_msg = translate(str(ctx.exception), "en")
                self.assertNotEqual(en_msg, str(ctx.exception))

        valid_urls = [
            "https://example.com/terms",
            "https://example.com:8443/terms",
            "http://zalo.me/petcare",
            "https://[2001:db8::1]/terms",
            "https://192.0.2.10/privacy",
        ]
        for raw in valid_urls:
            with self.subTest(valid_url=raw):
                self.assertEqual(tenant_settings_service._validated_http_url(raw, "Liên kết Zalo"), raw)
                self.assertEqual(tenant_settings_service._is_safe_http_href(raw), raw)

    def test_schema_service_template_and_docs_contract_stay_in_sync(self):
        sql_text = (REPO_ROOT / "petcare/database/storefront.sql").read_text(encoding="utf-8")
        table_match = re.search(
            r"CREATE TABLE IF NOT EXISTS tenant_public_policies\s*\((.*?)\)\s*ENGINE=InnoDB",
            sql_text,
            re.DOTALL,
        )
        self.assertIsNotNone(table_match)
        table_body = table_match.group(1)

        sql_lengths = {
            col: int(length)
            for col, length in re.findall(r"^\s*([a-z_]+)\s+VARCHAR\((\d+)\)\s+NOT NULL", table_body, re.MULTILINE)
        }
        service_lengths = {col: limit for col, (_label, limit) in tenant_settings_service.PUBLIC_POLICY_LIMITS.items()}
        self.assertEqual(sql_lengths, service_lengths)
        self.assertEqual(len(sql_lengths), 12)

        self.assertRegex(table_body, r"tenant_id\s+BIGINT UNSIGNED NOT NULL PRIMARY KEY")
        self.assertRegex(table_body, r"updated_by\s+BIGINT UNSIGNED NULL")
        self.assertRegex(
            table_body,
            r"updated_at\s+DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )
        self.assertRegex(
            table_body,
            r"CONSTRAINT\s+fk_tenant_public_policies_tenant\s+FOREIGN KEY\s*\(tenant_id\)\s+REFERENCES tenants\(id\)\s+ON DELETE RESTRICT",
        )
        self.assertRegex(
            table_body,
            r"CONSTRAINT\s+fk_tenant_public_policies_updater\s+FOREIGN KEY\s*\(tenant_id,\s*updated_by\)\s+REFERENCES tenant_users\(tenant_id,\s*user_id\)\s+ON DELETE RESTRICT",
        )

        template_html = (REPO_ROOT / "petcare/templates/store/settings.html").read_text(encoding="utf-8")
        for col, limit in service_lengths.items():
            pattern = rf'name="{col}"[^>]*maxlength="{limit}"'
            self.assertRegex(template_html, pattern, f"Template maxlength mismatch for {col}")

        contract_doc = (REPO_ROOT / "docs/STORE_SETTINGS_POLICIES.md").read_text(encoding="utf-8")
        for col, limit in service_lengths.items():
            self.assertIn(f"`{col}`", contract_doc)
            self.assertIn(f"`VARCHAR({limit})`", contract_doc)
        self.assertIn("tenant_users(tenant_id, user_id)", contract_doc)
        self.assertIn("`storefront_public_policies_v1`", contract_doc)
        self.assertIn("`updated_at`", contract_doc)

        migrations_doc = (REPO_ROOT / "docs/DATABASE_MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertIn("32 Tables", migrations_doc)
        self.assertIn("storefront_public_policies_v1", migrations_doc)


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

            # 2. Validation rejects javascript:, malformed IPv6, out-of-range port, invalid email/hotline with HTTP 200 (never 500).
            for bad_terms_url, bad_zalo in (
                ("javascript:alert(1)", "https://zalo.me/ok"),
                ("https://[broken", "https://example.test:99999/zalo"),
                ("https://:443/terms", "https://bad..example.com/zalo"),
            ):
                bad_resp = admin_client.post(
                    "/store/settings/public-policies",
                    data={
                        "csrf_token": self._csrf(admin_client, "/store/settings"),
                        "pickup_address": "18 Nguyen Hue <script>alert(1)</script>",
                        "support_hotline": "abc-invalid",
                        "support_email": "not-an-email",
                        "support_zalo": bad_zalo,
                        "privacy_terms_url": bad_terms_url,
                    },
                )
                self.assertEqual(bad_resp.status_code, 200)
                bad_html = bad_resp.get_data(as_text=True)
                self.assertIn('aria-invalid="true"', bad_html)
                self.assertIn("privacy_terms_url-error", bad_html)
                if bad_zalo != "https://zalo.me/ok":
                    self.assertIn("support_zalo-error", bad_html)
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

            # 4. Public storefront for this store renders escaped values; checkout compacts policy details & dedups footer!
            self.app.config["PUBLIC_STORE_SLUG"] = slug
            shop_client = self.app.test_client()
            shop_html = shop_client.get("/shop").get_data(as_text=True)
            self.assertIn("18 Nguyễn Huệ &lt;b&gt;Quận 1&lt;/b&gt;", shop_html)
            self.assertIn("https://example.com/terms", shop_html)
            self.assertIn("0909 111 222", shop_html)

            with get_connection() as connection:
                prod_id = execute(
                    connection,
                    "INSERT INTO products (tenant_id, code, name, category, unit_price, unit_price_vnd, stock_qty, reorder_level, active) "
                    "VALUES (%s, 'RC-CHK-01', 'Sản phẩm kiểm thử Checkout', 'Thức ăn', 120000, 120000, 5, 1, 1)",
                    (tenant_id,),
                )[0]
                connection.commit()

            add_csrf = re.search(
                r'name="csrf_token" value="([^"]+)"',
                shop_client.get(f"/shop/products/{prod_id}").get_data(as_text=True),
            ).group(1)
            add_resp = shop_client.post(
                "/shop/cart/add",
                data={"csrf_token": add_csrf, "item_type": "product", "item_id": str(prod_id), "quantity": "1"},
                follow_redirects=False,
            )
            self.assertEqual(add_resp.status_code, 302)

            checkout_html = shop_client.get("/shop/checkout").get_data(as_text=True)
            main_part, footer_part = checkout_html.split('<footer class="sf-footer">', 1)
            self.assertIn("sf-policy-summary", main_part)
            self.assertIn("sf-policy-details", main_part)
            self.assertIn("sf-policy-toggle", main_part)
            self.assertIn("Nội thành TP.HCM · báo phí thực tế trước khi xuất đơn", main_part)
            self.assertIn("Liên hệ trong 30 phút giờ mở cửa", main_part)
            self.assertIn("Đổi trả trong 3 ngày với bao bì còn nguyên tem", main_part)
            # Checkout footer suppresses repetitive pickup address, hours, and privacy summary
            self.assertNotIn("18 Nguyễn Huệ", footer_part)
            self.assertNotIn("08:30 – 20:30", footer_part)
            self.assertNotIn("Chính sách bảo mật thử nghiệm đã duyệt", footer_part)
            # Footer retains direct support contacts and Terms link
            self.assertIn("0909 111 222", footer_part)
            self.assertIn("https://example.com/terms", footer_part)

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
            cleared_checkout_html = shop_client.get("/shop/checkout").get_data(as_text=True)
            self.assertIn("CHỜ CHỦ SHOP XÁC NHẬN", cleared_checkout_html)
        finally:
            self.app.config["PUBLIC_STORE_SLUG"] = "main"
            with get_connection() as connection:
                with connection.cursor() as cur:
                    cur.execute("DELETE FROM products WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM tenant_public_policies WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (staff_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (admin_id,))
                    cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                connection.commit()


if __name__ == "__main__":
    unittest.main()
