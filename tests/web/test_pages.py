import ast
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet
from flask import g, render_template

from petcare import create_app
from petcare.i18n import translate
from petcare.routes.health_routes import (
    REQUIRED_COLUMNS,
    REQUIRED_GLOBAL_FOREIGN_KEYS,
    REQUIRED_TENANT_FOREIGN_KEYS,
    schema_contract_is_ready,
)
from petcare.services.worker_heartbeat import REQUIRED_WORKERS


class WebPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "web-tests-only-secret",
            "WTF_CSRF_ENABLED": False,
        })
        cls.app.add_url_rule(
            "/__test/private-cache",
            endpoint="private_cache_test",
            view_func=lambda: "private store response",
        )
        cls.client = cls.app.test_client()

    def test_login_page_renders_and_uses_local_assets(self):
        with self.client.session_transaction() as session:
            session["locale"] = "vi"
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Đăng nhập", body)
        self.assertIn("/static/css/app.css", body)
        self.assertNotIn("fonts.googleapis.com", body)

    def test_language_switch_is_allowlisted_and_keeps_redirect_same_origin(self):
        response = self.client.post(
            "/language", data={"locale": "en", "next": "//example.com/login"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))
        with self.client.session_transaction() as session:
            self.assertEqual(session["locale"], "en")

        response = self.client.get("/login")
        body = response.get_data(as_text=True)
        self.assertIn('<html lang="en">', body)
        self.assertIn("Sign in", body)
        self.assertIn("YOUR PET STORE", body)
        self.assertNotIn(">Đăng nhập<", body)

        response = self.client.post("/language", data={"locale": "fr", "next": "/login"})
        self.assertEqual(response.status_code, 400)
        with self.client.session_transaction() as session:
            self.assertEqual(session["locale"], "en")

    def test_accept_language_selects_english_when_no_preference_is_saved(self):
        response = self.app.test_client().get("/login", headers={"Accept-Language": "en-US,en;q=0.9"})
        body = response.get_data(as_text=True)
        self.assertIn('<html lang="en">', body)
        self.assertIn("Sign in", body)

    def test_english_invoice_feedback_keeps_payment_and_inventory_state_clear(self):
        cases = {
            "Danh sách mặt hàng không hợp lệ.": "The item list is invalid.",
            "Đã lập hóa đơn chưa thanh toán. Tồn kho sẽ đổi sau khi thu tiền.": (
                "Unpaid invoice created. Inventory will update after payment."
            ),
            "Hóa đơn đã được thanh toán trước đó; không ghi nhận lần hai.": (
                "This invoice was already paid; the payment was not recorded again."
            ),
            "Thanh toán thành công. Tồn kho và trạng thái thú cưng đã được cập nhật.": (
                "Payment successful. Inventory and pet status have been updated."
            ),
            "Hóa đơn đã hủy và không thể thanh toán.": "Cancelled invoices cannot be paid.",
            "Tồn kho vừa thay đổi; vui lòng tải lại hóa đơn.": (
                "Inventory changed while you were working. Reload the invoice and try again."
            ),
            "Hóa đơn đã thanh toán không thể hủy.": "Paid invoices cannot be cancelled.",
            "Khách hàng không tồn tại hoặc đã ngừng sử dụng.": (
                "The customer was not found or is inactive."
            ),
            "Tổng hóa đơn vượt giới hạn.": "The invoice total exceeds the supported limit.",
            "Tồn hiện tại của FOOD-001 không đủ; hóa đơn chưa giữ hàng.": (
                "Current stock for FOOD-001 is insufficient; the invoice has not reserved inventory."
            ),
            "Tồn kho FOOD-001 đã thay đổi; chưa thu tiền.": (
                "Inventory for FOOD-001 changed; no payment was recorded."
            ),
            "Tồn kho không thể vượt 1,000,000 đơn vị.": (
                "Inventory cannot exceed 1,000,000 units."
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(translate(source, "en"), expected)

    def test_static_user_facing_errors_and_flashes_have_english_translations(self):
        root = Path(__file__).resolve().parents[2]
        message_calls = {
            "flash", "ValidationError", "ConflictError", "ForbiddenError",
            "NotFoundError", "ServiceError",
        }
        for directory in (root / "petcare" / "routes", root / "petcare" / "services"):
            for source_path in directory.rglob("*.py"):
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
                for call in ast.walk(tree):
                    if (
                        not isinstance(call, ast.Call)
                        or not isinstance(call.func, ast.Name)
                        or call.func.id not in message_calls
                        or not call.args
                        or not isinstance(call.args[0], ast.Constant)
                        or not isinstance(call.args[0].value, str)
                    ):
                        continue
                    source_message = call.args[0].value
                    with self.subTest(path=source_path, line=call.lineno):
                        self.assertNotEqual(
                            translate(source_message, "en"),
                            source_message,
                            f"Missing English translation: {source_message}",
                        )

    def test_dynamic_validation_message_translates_its_field_label(self):
        self.assertEqual(
            translate("Câu hỏi không được để trống.", "en"),
            "Question is required.",
        )

    def test_login_preserves_selected_locale_when_rotating_session(self):
        user = {
            "id": 17, "tenant_id": 3, "session_version": 2, "full_name": "Test Owner"
        }
        with self.client.session_transaction() as session:
            session.clear()
            session["locale"] = "en"
        with patch("petcare.routes.auth_routes.auth_service.login_blocked", return_value=False), patch(
            "petcare.routes.auth_routes.auth_service.authenticate", return_value=user
        ), patch("petcare.routes.auth_routes.auth_service.clear_login_failures"), patch(
            "petcare.routes.auth_routes.auth_service.record_auth_event", return_value=True
        ):
            response = self.client.post("/login", data={
                "username": "owner", "password": "correct-password", "store_slug": "sample"
            })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["locale"], "en")
            self.assertEqual(session["user_id"], 17)
            session.clear()

    def test_english_dashboard_translates_core_navigation_and_content(self):
        with self.app.test_request_context("/dashboard"):
            from flask import g

            g.locale = "en"
            g.user = SimpleNamespace(
                id=1, role="staff", full_name="Sample User", store_memberships=[]
            )
            g.tenant = {
                "id": 1, "name": "Sample Store", "slug": "sample",
                "timezone": "UTC", "default_currency": "USD",
            }
            html = render_template("dashboard.html", metrics={
                "today": Decimal("1250.50"), "customers": 4, "products": 8,
                "low_stock": 1, "pets_available": 2, "low_stock_items":[SimpleNamespace(
                    id=1, name="Food", code="FOOD-1", reorder_level=5, stock_qty=2
                )],
                "recent_invoices": [],
            })

        self.assertIn("Dashboard", html)
        self.assertIn("STORE OVERVIEW", html)
        self.assertIn("Paid invoices today", html)
        self.assertIn("1,250.50\u00a0USD", html)
        self.assertIn("1 product low in stock", html)
        self.assertIn("1 item needs attention", html)
        self.assertIn("No transactions yet", html)
        self.assertNotIn("Khách hàng đang hoạt động", html)

    def test_protected_pages_redirect_anonymous_users(self):
        for path in (
            "/dashboard", "/customers/", "/pets/", "/pets/find-similar",
            "/products/", "/invoices/", "/invoices/lookups/customers",
            "/invoices/lookups/items", "/reports/", "/activity/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_authenticated_responses_are_not_cached(self):
        with self.client.session_transaction() as session:
            session.update(user_id=17, tenant_id=3, session_version=2)
        user = {
            "id": 17,
            "session_version": 2,
            "tenant": {"id": 3, "slug": "sample", "timezone": "UTC"},
        }
        with patch("petcare.auth.load_active_user", return_value=user):
            response = self.client.get("/__test/private-cache")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Cache-Control"), "private, no-store, max-age=0"
        )
        self.assertEqual(response.headers.get("Pragma"), "no-cache")
        with self.client.session_transaction() as session:
            session.clear()

    def test_legacy_clinic_service_routes_are_not_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertNotIn("/services/", rules)
        self.assertNotIn("/appointments/", rules)
        self.assertNotIn("/examinations/", rules)
        self.assertNotIn("/vaccinations/", rules)

    def test_assistant_discloses_question_scoped_data_sent_to_configured_ai(self):
        with patch.dict(self.app.config, {
            "AI_API_BASE_URL": "https://ai.example.test/v1",
            "AI_MODEL": "test-model",
        }), self.app.test_request_context("/"):
            g.user = SimpleNamespace(role="staff", full_name="Test User", store_memberships=[])
            g.tenant = SimpleNamespace(id=1, name="Test Store", slug="test-store")
            html = render_template("base.html")

        self.assertIn("tối đa 8 tin nhắn gần nhất", html)
        self.assertIn("dữ liệu cửa hàng liên quan", html)
        self.assertIn("Hồ sơ khách hàng không tự gửi", html)
        self.assertIn("thông tin bạn nhập vào chat vẫn được gửi", html)

    def test_assistant_discloses_local_only_mode_without_external_ai(self):
        with patch.dict(self.app.config, {"AI_API_BASE_URL": "", "AI_MODEL": ""}), self.app.test_request_context("/"):
            g.user = SimpleNamespace(role="staff", full_name="Test User", store_memberships=[])
            g.tenant = SimpleNamespace(id=1, name="Test Store", slug="test-store")
            html = render_template("base.html")

        self.assertIn("Không gọi endpoint AI bên ngoài", html)
        self.assertNotIn("tối đa 8 tin nhắn gần nhất", html)

    def test_image_search_explains_server_processing_and_missing_reference_photos(self):
        with self.app.test_request_context("/pets/find-similar"):
            g.user = SimpleNamespace(
                role="admin", full_name="Demo Admin", store_memberships=[]
            )
            g.tenant = None
            html = render_template(
                "pets/search_image.html",
                matches={
                    "results": [], "has_reference_photos": False,
                    "dominant_colors": [], "analysis": None, "warning": None,
                },
                phone_capture_enabled=False,
                phone_qr_data=None,
                vision_enabled=False,
            )

        self.assertIn("ảnh được gửi tới máy chủ ứng dụng để xử lý", html)
        self.assertIn("không được lưu thành hồ sơ", html)
        self.assertIn("Gợi ý theo đặc điểm hồ sơ", html)
        self.assertIn("chưa phải so khớp ảnh với ảnh", html)
        self.assertIn("So khớp ảnh cục bộ", html)
        self.assertIn('id="assistant-clear"', html)
        self.assertIn('aria-label="Xóa cuộc trò chuyện"', html)

    def test_image_search_labels_when_vision_analysis_was_used(self):
        with self.app.test_request_context("/pets/find-similar"):
            g.user = SimpleNamespace(
                role="admin", full_name="Demo Admin", store_memberships=[]
            )
            g.tenant = None
            html = render_template(
                "pets/search_image.html",
                matches={
                    "results": [], "has_reference_photos": False,
                    "dominant_colors": ["đen"], "analysis": {"species": "cat"},
                    "warning": None,
                },
                phone_capture_enabled=False,
                phone_qr_data=None,
                vision_enabled=True,
            )

        self.assertIn("AI Vision + so khớp cục bộ", html)
        self.assertIn("AI Vision đang bật", html)

    def test_catalog_edit_forms_render_currency_scaled_input_values_and_steps(self):
        product = SimpleNamespace(
            id=1,
            code="FOOD-001", name="Thức ăn", category="Thức ăn", description="",
            unit_price=Decimal("2400000.0000"), reorder_level=5, stock_qty=10,
            stock_history=[], photo_filename=None,
        )
        pet = SimpleNamespace(
            code="PET-001", name="Miu", species="Mèo", breed="Mèo ta", sex="female",
            birth_date=None, weight_kg=Decimal("3.80"), coat_color="",
            eye_color="", appearance_tags="", photo_filename=None,
            sale_price=Decimal("12.3400"),
        )
        with self.app.test_request_context("/products/1/edit"):
            g.user = SimpleNamespace(
                role="admin", full_name="Admin", store_memberships=[]
            )
            g.tenant = SimpleNamespace(
                id=1, name="Cửa hàng", slug="main", timezone="Asia/Ho_Chi_Minh",
                default_currency="VND",
            )
            product_html = render_template("products/form.html", product=product)
        with self.app.test_request_context("/pets/1/edit"):
            g.user = SimpleNamespace(
                role="admin", full_name="Admin", store_memberships=[]
            )
            g.tenant = SimpleNamespace(
                id=1, name="Cửa hàng", slug="main", timezone="Asia/Ho_Chi_Minh",
                default_currency="USD",
            )
            pet_html = render_template("pets/form.html", pet=pet)

        self.assertIn('name="unit_price" type="number" min="0" step="1"', product_html)
        self.assertIn('value="2400000"', product_html)
        self.assertIn("Không dùng phần thập phân.", product_html)
        self.assertIn('name="sale_price" type="number" min="0" step="0.01"', pet_html)
        self.assertIn('value="12.34"', pet_html)
        self.assertIn("Tối đa 2 chữ số thập phân.", pet_html)

    def test_post_without_csrf_token_is_rejected(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-tests-only-secret",
            "WTF_CSRF_ENABLED": True,
        })
        response = csrf_app.test_client().post("/login", data={"username": "x"})
        self.assertEqual(response.status_code, 400)

    def test_health_probe_is_public_and_has_security_headers(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_readiness_fails_when_required_schema_is_missing(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("petcare.routes.health_routes.read_connection") as read_connection:
            read_connection.return_value.__enter__.return_value = connection
            response = self.client.get("/readyz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "unavailable"})

    def test_worker_health_probe_does_not_load_a_browser_user_session(self):
        client = self.app.test_client()
        with client.session_transaction() as browser_session:
            browser_session.update(user_id=99, tenant_id=1, session_version=0)
        connection_scope = MagicMock()
        connection_scope.__enter__.return_value = object()
        connection_scope.__exit__.return_value = False
        with patch("petcare.auth.load_active_user") as load_user, patch(
            "petcare.routes.health_routes.read_connection", return_value=connection_scope
        ), patch(
            "petcare.routes.health_routes.healthy_worker_names",
            return_value=REQUIRED_WORKERS,
        ):
            response = client.get("/workersz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ready"})
        load_user.assert_not_called()

    def test_metrics_endpoint_is_hidden_without_token_and_rejects_weak_configuration(self):
        client = self.app.test_client()
        previous = self.app.config.get("OPS_METRICS_TOKEN", "")
        try:
            self.app.config["OPS_METRICS_TOKEN"] = ""
            response = client.get("/metrics")
            self.assertEqual(response.status_code, 404)

            self.app.config["OPS_METRICS_TOKEN"] = "m" * 40
            self.assertEqual(client.get("/metrics").status_code, 401)
            self.assertEqual(
                client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code,
                401,
            )
        finally:
            self.app.config["OPS_METRICS_TOKEN"] = previous

        with self.assertRaisesRegex(RuntimeError, "OPS_METRICS_TOKEN"):
            create_app({
                "TESTING": True,
                "SECRET_KEY": "weak-metrics-config-test",
                "OPS_METRICS_TOKEN": "too-short",
            })

    def test_schema_contract_requires_runtime_columns_and_tenant_foreign_keys(self):
        columns = [
            (table, column)
            for table, names in REQUIRED_COLUMNS.items()
            for column in names
        ]
        foreign_keys = list(REQUIRED_TENANT_FOREIGN_KEYS | REQUIRED_GLOBAL_FOREIGN_KEYS)
        cursor = MagicMock()
        cursor.fetchall.side_effect = [columns, foreign_keys]
        cursor.fetchone.return_value = (1,)
        self.assertTrue(schema_contract_is_ready(cursor))

        cursor.fetchall.side_effect = [
            [row for row in columns if row != ("pets", "photo_descriptor")]
        ]
        self.assertFalse(schema_contract_is_ready(cursor))

        cursor.fetchall.side_effect = [columns, foreign_keys[:-1]]
        self.assertFalse(schema_contract_is_ready(cursor))

    def test_production_refuses_a_generated_process_local_secret(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            create_app({
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,
                "SECRET_KEY_CONFIGURED": False,
            })

    def test_image_processing_concurrency_must_be_bounded_per_worker(self):
        for value in (0, 5):
            with self.subTest(value=value), self.assertRaisesRegex(
                RuntimeError, "IMAGE_PROCESSING_CONCURRENCY"
            ):
                create_app({
                    "TESTING": True,
                    "SECRET_KEY": "web-tests-only-secret",
                    "IMAGE_PROCESSING_CONCURRENCY": value,
                })

    def test_catalog_image_upload_quotas_must_be_bounded(self):
        settings = (
            ("CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE", 0),
            ("CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE", 1001),
        )
        for setting, value in settings:
            with self.subTest(setting=setting, value=value), self.assertRaisesRegex(
                RuntimeError, setting
            ):
                create_app({
                    "TESTING": True,
                    "SECRET_KEY": "web-tests-only-secret",
                    setting: value,
                })

    def test_production_invitation_origin_must_be_trusted_https(self):
        with self.assertRaisesRegex(RuntimeError, "PUBLIC_BASE_URL"):
            create_app({
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,
                "SECRET_KEY_CONFIGURED": True,
                "SESSION_COOKIE_SECURE": True,
                "DEBUG": False,
                "DB_PASSWORD": "dedicated-production-password",
                "DB_USER": "petcare_app",
                "DB_NAME": "petcare_shop_prod",
                "PUBLIC_BASE_URL": "http://untrusted.example",
            })

    def test_phone_camera_qr_requires_a_clean_http_origin_and_https_in_production(self):
        for base_url in (
            "ftp://192.168.1.20:5000",
            "http://user@192.168.1.20:5000",
            "http://192.168.1.20:5000/path",
            "http://192.168.1.20:5000/?next=https://evil.example",
            "http://192.168.1.20:70000",
        ):
            with self.subTest(base_url=base_url):
                with self.assertRaisesRegex(RuntimeError, "LAN_ACCESS_BASE_URL"):
                    create_app({
                        "TESTING": True,
                        "SECRET_KEY": "web-tests-only-secret",
                        "LAN_ACCESS_ENABLED": True,
                        "LAN_ACCESS_BASE_URL": base_url,
                    })

        with self.assertRaisesRegex(RuntimeError, "LAN_ACCESS_BASE_URL.*HTTPS"):
            create_app({
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,
                "SECRET_KEY_CONFIGURED": True,
                "SESSION_COOKIE_SECURE": True,
                "DEBUG": False,
                "DB_PASSWORD": "dedicated-production-password",
                "DB_USER": "petcare_app",
                "DB_NAME": "petcare_shop_prod",
                "PUBLIC_BASE_URL": "https://petcare.example",
                "LAN_ACCESS_ENABLED": True,
                "LAN_ACCESS_BASE_URL": "http://192.168.1.20:5000",
            })

    def test_production_requires_tls_mail_for_account_recovery(self):
        with self.assertRaisesRegex(RuntimeError, "MAIL_HOST and MAIL_FROM"):
            create_app({
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,
                "SECRET_KEY_CONFIGURED": True,
                "SESSION_COOKIE_SECURE": True,
                "DEBUG": False,
                "DB_PASSWORD": "dedicated-production-password",
                "DB_USER": "petcare_app",
                "DB_NAME": "petcare_shop_prod",
                "PUBLIC_BASE_URL": "https://petcare.example",
                "MAIL_HOST": "",
                "MAIL_FROM": "",
                "MEDIA_STORAGE_BACKEND": "local",
            })

    def test_production_requires_verified_mysql_tls(self):
        with self.assertRaisesRegex(RuntimeError, "DB_SSL_CA"):
            create_app({
                "APP_ENV": "production",
                "SECRET_KEY": "a" * 64,
                "SECRET_KEY_CONFIGURED": True,
                "SESSION_COOKIE_SECURE": True,
                "DEBUG": False,
                "DB_PASSWORD": "dedicated-production-password",
                "DB_USER": "petcare_app",
                "DB_NAME": "petcare_shop_prod",
                "DB_SSL_CA": "",
                "PUBLIC_BASE_URL": "https://petcare.example",
                "MAIL_HOST": "smtp.example.test",
                "MAIL_PORT": 587,
                "MAIL_FROM": "no-reply@example.test",
                "MAIL_STARTTLS": True,
                "MAIL_OUTBOX_KEY": Fernet.generate_key().decode("ascii"),
                "MEDIA_STORAGE_BACKEND": "local",
            })


if __name__ == "__main__":
    unittest.main()
