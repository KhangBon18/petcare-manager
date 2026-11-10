from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from petcare import create_app
from petcare.services.exceptions import NotFoundError, ValidationError


class PhaseOneWebRegressionTests(TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "phase-one-tests-only-key",
            }
        )
        self.client = self.app.test_client()
        self.user = {
            "id": 1,
            "role": "admin",
            "full_name": "Demo",
            "preferred_locale": "vi",
            "store_memberships": [],
            "tenant": {
                "id": 1,
                "slug": "main",
                "name": "Demo",
                "timezone": "Asia/Ho_Chi_Minh",
                "default_currency": "VND",
            },
        }
        with self.client.session_transaction() as session:
            session.update(user_id=1, tenant_id=1, session_version=0, locale="vi")
        self.patch(
            "petcare.auth.load_active_user",
            side_effect=lambda *args: deepcopy(self.user),
        )

    def patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def invoice_catalog(self):
        page = {
            "total": 50,
            "page": 1,
            "pages": 2,
            "page_size": 25,
            "has_next": True,
            "has_previous": False,
            "first": 1,
            "last": 25,
        }
        customer = {"id": 7, "full_name": "Khách đã chọn", "phone": "0901234567"}
        product = {
            "id": 9,
            "name": "Hạt mèo",
            "code": "P9",
            "stock_qty": 2,
            "unit_price": Decimal("150000"),
        }
        pet = {
            "id": 11,
            "name": "Miu",
            "code": "PET11",
            "sale_price": Decimal("2000000"),
        }
        for module, method in [
            ("customer", "customers"),
            ("product", "products"),
            ("pet", "pets"),
        ]:
            self.patch(
                f"petcare.routes.invoice_routes.{module}_service.list_{method}",
                side_effect=lambda *a, **kw: {"items": [], "pagination": dict(page)},
            )
        self.patch(
            "petcare.routes.invoice_routes.customer_service.get_customer",
            return_value=customer,
        )
        self.patch(
            "petcare.routes.invoice_routes.product_service.get_product",
            return_value=product,
        )
        self.patch(
            "petcare.routes.invoice_routes.pet_service.get_pet", return_value=pet
        )

    def test_new_customer_keeps_values_and_marks_every_invalid_field(self):
        # Use real service validation: failure occurs before opening a transaction.
        response = self.client.post(
            "/customers/new",
            data={
                "full_name": "Khách <demo>",
                "phone": "bad",
                "address": "Địa chỉ đang nhập",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('value="Khách &lt;demo&gt;"', html)
        self.assertIn("Địa chỉ đang nhập</textarea>", html)
        self.assertIn('id="phone-error"', html)
        self.assertIn('aria-describedby="phone-error"', html)
        self.assertIn("data-error-summary", html)
        self.assertNotIn("required autofocus", html)

    def test_edit_customer_retains_posted_values_instead_of_old_record(self):
        self.patch(
            "petcare.routes.customer_routes.customer_service.get_customer",
            return_value={
                "id": 7,
                "full_name": "Old name",
                "phone": "0901234567",
                "address": "Old address",
            },
        )
        response = self.client.post(
            "/customers/7/edit",
            data={"full_name": "New name", "phone": "bad", "address": "New address"},
        )
        html = response.get_data(as_text=True)
        self.assertIn('value="New name"', html)
        self.assertIn("New address</textarea>", html)
        self.assertNotIn('value="Old name"', html)

    def test_pet_create_keeps_submitted_values_after_server_validation_error(self):
        self.patch(
            "petcare.routes.pet_routes.pet_service.create_pet",
            side_effect=ValidationError("Date of birth cannot be in the future."),
        )
        response = self.client.post(
            "/pets/new",
            data={
                "code": "E2E-PET-01",
                "name": "QA Pet Browser",
                "species": "Cat",
                "breed": "Test Shorthair",
                "sex": "female",
                "birth_date": "2030-01-01",
                "weight_kg": "3.5",
                "coat_color": "black and white",
                "eye_color": "green",
                "appearance_tags": "synthetic QA profile",
                "sale_price": "1000000",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for value in (
            "E2E-PET-01", "QA Pet Browser", "Cat", "Test Shorthair",
            "2030-01-01", "3.5", "black and white", "green",
            "synthetic QA profile", "1000000",
        ):
            self.assertIn(value, html)
        self.assertIn('option value="female" selected', html)
        self.assertIn("Date of birth cannot be in the future.", html)

    def test_product_create_keeps_submitted_values_after_server_validation_error(self):
        self.patch(
            "petcare.routes.product_routes.product_service.create_product",
            side_effect=ValidationError("Product code already exists."),
        )
        response = self.client.post(
            "/products/new",
            data={
                "code": "FOOD-001",
                "name": "QA Duplicate Product",
                "category": "QA",
                "unit_price": "12500",
                "reorder_level": "5",
                "description": "Synthetic <duplicate-code> validation",
                "stock_qty": "7",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for value in ("FOOD-001", "QA Duplicate Product", "QA", "12500", "5", "7"):
            self.assertIn(value, html)
        self.assertIn(
            "Synthetic &lt;duplicate-code&gt; validation</textarea>", html
        )
        self.assertIn("Product code already exists.", html)

    def test_invoice_keeps_all_lines_note_and_selections_outside_first_page(self):
        self.invoice_catalog()
        self.patch(
            "petcare.routes.invoice_routes.invoice_service.create_invoice",
            side_effect=ValidationError(
                "Tồn kho vừa thay đổi; vui lòng tải lại hóa đơn.", field="quantity_0"
            ),
        )
        response = self.client.post(
            "/invoices/new",
            data={
                "customer_id": "7",
                "item_selection": ["product:9", "pet:11"],
                "quantity": ["4", "1"],
                "note": "Giữ ghi chú <demo>",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('value="7" selected', html)
        self.assertRegex(html, r'value="product:9"[^>]*selected')
        self.assertRegex(html, r'value="pet:11"[^>]*selected')
        self.assertIn('value="4"', html)
        self.assertIn("Giữ ghi chú &lt;demo&gt;</textarea>", html)
        self.assertIn('id="quantity_0-error"', html)
        self.assertIn('aria-describedby="quantity_0-error"', html)
        self.assertIn('<strong id="line-count">2</strong>', html)

    def test_invoice_real_validation_marks_bad_quantity_and_missing_customer(self):
        self.invoice_catalog()
        response = self.client.post(
            "/invoices/new",
            data={
                "customer_id": "",
                "item_selection": ["product:9", "pet:11"],
                "quantity": ["0", "3"],
                "note": "Keep",
            },
        )
        html = response.get_data(as_text=True)
        for field in ["customer_id", "quantity_0", "quantity_1"]:
            self.assertIn(f'aria-describedby="{field}-error"', html)
        self.assertIn('value="3"', html)
        self.assertIn("Keep</textarea>", html)

    def test_invalid_or_cross_tenant_selections_do_not_disclose_record_data(self):
        self.invoice_catalog()
        self.patch(
            "petcare.routes.invoice_routes.invoice_service.create_invoice",
            side_effect=ValidationError(
                "Thú cưng đã chọn không còn sẵn sàng để bán.", field="item_0"
            ),
        )
        get_pet = self.patch(
            "petcare.routes.invoice_routes.pet_service.get_pet",
            side_effect=NotFoundError("Không tìm thấy thú cưng."),
        )
        response = self.client.post(
            "/invoices/new",
            data={
                "customer_id": "7",
                "item_selection": "pet:999",
                "quantity": "1",
                "note": "",
            },
        )
        html = response.get_data(as_text=True)
        self.assertIn('value="pet:999" selected', html)
        self.assertNotIn("PET11", html)
        get_pet.assert_called_once_with(1, "999", tenant_id=1)

    def test_mismatched_post_arrays_keep_every_submitted_row(self):
        self.invoice_catalog()
        response = self.client.post(
            "/invoices/new",
            data={
                "customer_id": "7",
                "item_selection": ["product:9", "pet:11"],
                "quantity": "2",
            },
        )
        html = response.get_data(as_text=True)
        self.assertIn('<strong id="line-count">2</strong>', html)
        self.assertIn("Danh sách mặt hàng không hợp lệ.", html)
        self.assertRegex(html, r'value="pet:11"[^>]*selected')

    def test_assistant_rejects_wrong_json_message_types_without_calling_ai(self):
        self.patch(
            "petcare.routes.assistant_routes.request_throttle_service.consume_with_ip_limit",
            return_value=(True, 0),
        )
        answer = self.patch("petcare.routes.assistant_routes.assistant_service.answer")
        for message in [42, True, [], {}, None]:
            with self.subTest(message=message):
                response = self.client.post(
                    "/assistant/chat", json={"message": message}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["field"], "message")
                self.assertEqual(response.get_json()["expected"], "string")
        answer.assert_not_called()

    def test_assistant_rejects_non_object_payloads_and_handles_blank_text(self):
        self.patch(
            "petcare.routes.assistant_routes.request_throttle_service.consume_with_ip_limit",
            return_value=(True, 0),
        )
        for payload in [[], "hello", 42, {"message": "   "}]:
            with self.subTest(payload=payload):
                response = self.client.post("/assistant/chat", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_photo_result_progress_works_with_strict_style_csp(self):
        self.patch(
            "petcare.routes.pet_routes.request_throttle_service.consume_with_ip_limit",
            return_value=(True, 0),
        )
        self.patch(
            "petcare.routes.pet_routes.pet_image_service.search_similar",
            return_value={
                "results": [
                    {
                        "score": 73,
                        "pet": {
                            "id": 11,
                            "code": "P11",
                            "name": "Miu",
                            "species": "Mèo",
                            "breed": "Mèo ta",
                            "coat_color": "trắng",
                            "eye_color": "xanh",
                            "photo_filename": None,
                            "sale_price": Decimal("2000000"),
                        },
                    }
                ],
                "has_reference_photos": True,
                "dominant_colors": ["trắng"],
                "analysis": None,
                "warning": None,
                "search_scope": "full",
            },
        )
        response = self.client.post(
            "/pets/find-similar", data={"photo": (BytesIO(b"test"), "test.jpg")}
        )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(html, r'<progress[^>]*max="100" value="73"')
        self.assertNotIn('style="', html)
        self.assertIn("style-src 'self'", response.headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", response.headers["Content-Security-Policy"])

    def test_pos_field_errors_span_the_cart_row_instead_of_the_narrow_quantity_column(
        self,
    ):
        from html.parser import HTMLParser

        self.invoice_catalog()
        self.patch(
            "petcare.routes.invoice_routes.invoice_service.create_invoice",
            side_effect=ValidationError(
                "Thiếu tồn",
                field_errors={
                    "quantity_0": "Thiếu tồn",
                    "item_1": "Cá thể không còn bán",
                },
            ),
        )
        response = self.client.post(
            "/invoices/new",
            data={
                "customer_id": "7",
                "item_selection": ["product:9", "pet:11"],
                "quantity": ["3", "1"],
            },
        )

        class Parents(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.parents = {}

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get("id") in {"quantity_0-error", "item_1-error"}:
                    self.parents[attrs["id"]] = self.stack[-1]
                if tag not in {"input", "img", "br", "meta", "link", "hr"}:
                    self.stack.append((tag, attrs))

            def handle_endtag(self, tag):
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        break

        parser = Parents()
        parser.feed(response.get_data(as_text=True))
        for field in ("quantity_0-error", "item_1-error"):
            self.assertEqual(parser.parents[field][0], "div")
            self.assertEqual(parser.parents[field][1]["class"], "invoice-line")
