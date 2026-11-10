from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare import create_app


class CustomerProfileWebTests(TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "customer-profile-tests-only-key",
            }
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=1, tenant_id=1, session_version=0, locale="vi")
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
        self.load_user = patch(
            "petcare.auth.load_active_user", return_value=self.user
        )
        self.load_user.start()
        self.addCleanup(self.load_user.stop)

    @staticmethod
    def profile():
        page = {
            "page": 1,
            "page_size": 25,
            "pages": 2,
            "total": 27,
            "first": 1,
            "last": 25,
            "has_previous": False,
            "has_next": True,
        }
        return {
            "customer": {
                "id": 7,
                "full_name": "Nguyễn An",
                "phone": "+84 901234567",
                "address": "Quận 1",
                "active": 1,
                "created_at": datetime(2026, 10, 1, 8, 30),
            },
            "summary": {
                "invoice_count": 27,
                "paid_invoice_count": 22,
                "unpaid_invoice_count": 3,
                "currencies": [
                    {
                        "currency_code": "USD",
                        "paid_total": Decimal("80.5"),
                        "unpaid_total": Decimal("10"),
                    },
                    {
                        "currency_code": "VND",
                        "paid_total": Decimal("1250000"),
                        "unpaid_total": Decimal("200000"),
                    },
                ],
            },
            "invoices": [
                {
                    "id": 38,
                    "created_at": datetime(2026, 10, 2, 11, 0),
                    "paid_at": datetime(2026, 10, 2, 11, 5),
                    "status": "paid",
                    "currency_code": "VND",
                    "total_amount": Decimal("125000"),
                    "item_count": 2,
                }
            ],
            "purchased_pets": [
                {
                    "id": 41,
                    "code": "PET-041",
                    "name": "Mochi",
                    "species": "Mèo",
                    "breed": "Mèo ta",
                    "sale_status": "sold",
                    "sold_at": datetime(2026, 10, 2, 11, 5),
                    "photo_filename": None,
                    "total_count": 1,
                }
            ],
            "pagination": page,
            "pet_pagination": {
                "page": 1, "page_size": 12, "pages": 1, "total": 1,
                "first": 1, "last": 1, "has_previous": False, "has_next": False,
            },
        }

    def test_customer_detail_renders_history_and_keeps_currency_totals_separate(self):
        with patch(
            "petcare.routes.customer_routes.customer_service.get_customer_profile",
            return_value=self.profile(),
        ):
            response = self.client.get("/customers/7")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Nguyễn An", html)
        self.assertIn("+84 901234567", html)
        self.assertIn("USD", html)
        self.assertIn("VND", html)
        self.assertIn("#000038", html)
        self.assertIn("/invoices/38", html)
        self.assertIn("/pets/41", html)
        self.assertIn("Thú cưng đã mua", html)
        self.assertIn('aria-label="Vị trí hiện tại"', html)
        self.assertIn("/invoices/new?customer_id=7", html)
        self.assertIn("/customers/7?page=2", html)
        self.assertIn("Không quy đổi giữa các loại tiền.", html)
        self.assertIn("Hiển thị 1–1 trong tổng số 1 thú cưng", html)

    def test_profile_pagination_query_is_passed_to_service(self):
        get_profile = patch(
            "petcare.routes.customer_routes.customer_service.get_customer_profile",
            return_value=self.profile(),
        )
        with get_profile as mocked:
            self.client.get("/customers/7?page=2")
        mocked.assert_called_once_with(1, 7, page="2", pet_page="1", tenant_id=1)

    def test_purchased_pet_pagination_preserves_invoice_history_page(self):
        profile = self.profile()
        profile["pet_pagination"] = {
            "page": 2, "page_size": 12, "pages": 2, "total": 13,
            "first": 13, "last": 13, "has_previous": True, "has_next": False,
        }
        profile["purchased_pets"] = [
            {"id": 54, "code": "PET-054", "name": "Luna", "species": "Mèo",
             "breed": "Mèo ta", "sale_status": "sold", "total_count": 13}
        ]
        with patch(
            "petcare.routes.customer_routes.customer_service.get_customer_profile",
            return_value=profile,
        ):
            response = self.client.get("/customers/7?page=2&pet_page=2")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="/customers/7?page=2&amp;pet_page=1"', html)
        self.assertIn("13–13 trong tổng số 13 thú cưng", html)
        self.assertIn("Luna", html)

    def test_customer_profile_has_english_labels_when_locale_is_english(self):
        self.user["preferred_locale"] = "en"
        with patch(
            "petcare.routes.customer_routes.customer_service.get_customer_profile",
            return_value=self.profile(),
        ):
            response = self.client.get("/customers/7")

        html = response.get_data(as_text=True)
        self.assertIn("CUSTOMER PROFILE", html)
        self.assertIn("Contact information", html)
        self.assertIn("Invoice history", html)
        self.assertIn("Purchased pets", html)
        self.assertIn('aria-label="Current location"', html)
        self.assertIn("Currencies are not converted.", html)

    def test_customer_list_renders_mobile_record_actions_and_accessible_breadcrumb(self):
        listing = {
            "items": [{
                "id": 7, "full_name": "Nguyễn An", "phone": "0901234567",
                "address": "Quận 1", "invoice_count": 3, "active": 1,
            }],
            "pagination": {
                "page": 1, "page_size": 25, "pages": 1, "total": 1,
                "first": 1, "last": 1, "has_previous": False, "has_next": False,
            },
        }
        with patch(
            "petcare.routes.customer_routes.customer_service.list_customers",
            return_value=listing,
        ):
            response = self.client.get("/customers/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('aria-label="Vị trí hiện tại"', html)
        self.assertIn('class="customer-mobile-list"', html)
        self.assertIn('href="/customers/7"', html)
        self.assertIn('action="/customers/7/deactivate"', html)
        self.assertIn("Nguyễn An", html)

    def test_pet_detail_links_back_to_the_recorded_buyer(self):
        pet = {
            "id": 21, "code": "PET-021", "name": "Miu", "species": "Mèo",
            "breed": "Mèo ta", "sex": "unknown", "birth_date": None,
            "weight_kg": None, "coat_color": "", "eye_color": "",
            "appearance_tags": "", "sale_price": Decimal("2000000"),
            "sale_status": "sold", "buyer_id": 7, "buyer_name": "Nguyễn An",
            "sold_at": datetime(2026, 10, 2, 11, 5), "photo_filename": None,
        }
        with patch(
            "petcare.routes.pet_routes.pet_service.get_pet", return_value=pet
        ):
            response = self.client.get("/pets/21")

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/customers/7"', response.get_data(as_text=True))

    def test_invoice_create_link_prefills_customer_selection(self):
        empty_page = {
            "page": 1,
            "page_size": 25,
            "pages": 1,
            "total": 0,
            "first": 0,
            "last": 0,
            "has_previous": False,
            "has_next": False,
        }
        customers = {"items": [], "pagination": dict(empty_page)}
        catalog = {"items": [], "pagination": dict(empty_page)}
        with (
            patch(
                "petcare.routes.invoice_routes.customer_service.list_customers",
                return_value=customers,
            ),
            patch(
                "petcare.routes.invoice_routes.customer_service.get_customer",
                return_value=self.profile()["customer"],
            ),
            patch(
                "petcare.routes.invoice_routes.product_service.list_products",
                return_value=catalog,
            ),
            patch(
                "petcare.routes.invoice_routes.pet_service.list_pets",
                return_value=catalog,
            ),
        ):
            response = self.client.get("/invoices/new?customer_id=7")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.get_data(as_text=True), r'value="7" selected')

    def test_invoice_detail_links_back_to_customer_profile(self):
        invoice = {
            "id": 38,
            "customer_id": 7,
            "customer_name": "Nguyễn An",
            "customer_phone": "+84 901234567",
            "created_at": datetime(2026, 10, 2, 11, 0),
            "status": "paid",
            "currency_code": "VND",
            "total_amount": Decimal("125000"),
            "items": [],
            "created_by_name": "Demo",
            "paid_at": datetime(2026, 10, 2, 11, 5),
            "note": "",
        }
        with patch(
            "petcare.routes.invoice_routes.invoice_service.get_invoice",
            return_value=invoice,
        ):
            response = self.client.get("/invoices/38")

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/customers/7"', response.get_data(as_text=True))
