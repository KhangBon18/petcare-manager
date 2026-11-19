from copy import deepcopy
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare import create_app


class POSWebRegressionTests(TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "pos-web-tests-only",
                               "WTF_CSRF_ENABLED": False})
        self.client = self.app.test_client()
        self.user = {"id": 1, "role": "staff", "full_name": "POS Staff", "preferred_locale": "vi",
                     "store_memberships": [], "tenant": {"id": 1, "slug": "main", "name": "Demo",
                     "default_currency": "VND", "timezone": "Asia/Ho_Chi_Minh"}}
        with self.client.session_transaction() as session:
            session.update(user_id=1, tenant_id=1, session_version=0)
        self.patch("petcare.auth.load_active_user", side_effect=lambda *a: deepcopy(self.user))

    def patch(self, target, **kwargs):
        patcher = patch(target, **kwargs); self.addCleanup(patcher.stop); return patcher.start()

    def catalog(self):
        page = {"total": 1, "page": 1, "pages": 1, "page_size": 25,
                "has_next": False, "has_previous": False, "first": 1, "last": 1}
        products = [{"id": 9, "code": "P9", "name": "Hạt <demo>", "unit_price": Decimal("100000"),
                     "stock_qty": 3, "photo_filename": "t1-" + "a" * 32 + ".jpg"}]
        pets = [{"id": 11, "code": "PET11", "name": "Miu", "sale_price": Decimal("2000000"),
                 "photo_filename": "t1-" + "b" * 32 + ".jpg"}]
        for name, items in [("customer", []), ("product", products), ("pet", pets)]:
            plural = {"customer": "customers", "product": "products", "pet": "pets"}[name]
            self.patch(f"petcare.routes.invoice_routes.{name}_service.list_{plural}",
                       return_value={"items": items, "pagination": page})

    def test_pos_catalog_includes_photos_price_stock_and_safe_labels(self):
        self.catalog()
        response = self.client.get("/invoices/new")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-pos="true"', html)
        self.assertIn('data-selection="product:9"', html)
        self.assertIn('data-selection="pet:11"', html)
        self.assertIn('data-stock="3"', html)
        self.assertIn('data-stock="1"', html)
        self.assertIn("Hạt &lt;demo&gt;", html)
        self.assertIn('/products/photo/t1-', html)
        self.assertIn('/pets/photo/t1-', html)
        self.assertIn('id="quick-customer-dialog"', html)
        self.assertIn('class="pos-mobile-cart" href="#pos-order"', html)
        self.assertIn('data-pos-mobile-count', html)
        self.assertIn('data-pos-mobile-total', html)
        self.assertIn('id="pos-order" tabindex="-1"', html)
        self.assertIn('/static/js/pos.js', html)
        self.assertIn("style-src 'self'", response.headers["Content-Security-Policy"])
        self.assertNotIn('style="', html)

    def test_catalog_lookup_returns_private_photo_routes_and_decimal_strings(self):
        self.catalog()
        payload = self.client.get("/invoices/lookups/items?q=cat").get_json()
        self.assertEqual(payload["products"][0]["unit_price"], "100000")
        self.assertTrue(payload["products"][0]["photo_url"].startswith("/products/photo/"))
        self.assertTrue(payload["pets"][0]["photo_url"].startswith("/pets/photo/"))

    def test_quick_customer_returns_field_errors_without_opening_transaction(self):
        transaction = self.patch("petcare.services.customer_service.transaction")
        response = self.client.post("/invoices/customers/quick", json={"full_name": "Demo", "phone": "bad", "address": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.get_json()["errors"])
        transaction.assert_not_called()

    def test_quick_customer_uses_existing_service_and_only_returns_picker_fields(self):
        create = self.patch("petcare.routes.invoice_routes.customer_service.create_customer", return_value=77)
        get = self.patch("petcare.routes.invoice_routes.customer_service.get_customer", return_value={
            "id": 77, "full_name": "New", "phone": "0901234567", "address": "private", "tenant_id": 1})
        response = self.client.post("/invoices/customers/quick", json={"full_name": "New", "phone": "0901234567"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.get_json()["customer"]), {"id", "full_name", "phone"})
        self.assertEqual(create.call_args.args[0], 1)
        get.assert_called_once_with(1, 77, tenant_id=1)

    def test_quick_customer_validates_payload_and_requires_login(self):
        for payload in [[], 42, "wrong", {"full_name": [], "phone": {}}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/invoices/customers/quick", json=payload).status_code, 400)
        response = self.app.test_client().post("/invoices/customers/quick", json={})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_quick_customer_requires_csrf_when_enabled(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post("/invoices/customers/quick", json={"full_name": "New", "phone": "0901234567"})
        self.assertEqual(response.status_code, 400)
