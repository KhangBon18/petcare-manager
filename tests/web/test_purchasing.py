from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare import create_app


class PurchasingWebTests(TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "purchasing-web-tests-only-key",
        })
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=9, tenant_id=4, session_version=0, locale="vi")
        self.user = {
            "id": 9,
            "role": "admin",
            "full_name": "Demo Admin",
            "preferred_locale": "vi",
            "store_memberships": [],
            "tenant": {
                "id": 4,
                "slug": "demo",
                "name": "Demo Store",
                "timezone": "Asia/Ho_Chi_Minh",
                "default_currency": "VND",
            },
        }
        self.load_user = patch(
            "petcare.auth.load_active_user",
            side_effect=lambda *_args, **_kwargs: {
                **self.user,
                "tenant": dict(self.user["tenant"]),
                "store_memberships": list(self.user["store_memberships"]),
            },
        )
        self.load_user.start()
        self.addCleanup(self.load_user.stop)

    def test_purchase_order_list_has_clear_supplier_and_create_actions(self):
        listing = {
            "items": [{
                "id": 42,
                "supplier_name_snapshot": "Pet Supply Co.",
                "created_at": datetime(2026, 10, 31, 9, 30),
                "received_units": 4,
                "ordered_units": 10,
                "item_count": 2,
                "total_amount": Decimal("250000"),
                "currency_code": "VND",
                "status": "partially_received",
            }],
            "pagination": {"page": 1, "pages": 1, "total": 1, "first": 1, "last": 1,
                           "has_previous": False, "has_next": False, "page_size": 25},
        }
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.list_purchase_orders",
            return_value=listing,
        ) as list_orders:
            response = self.client.get("/purchasing")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Đơn nhập hàng", html)
        self.assertIn("Pet Supply Co.", html)
        self.assertIn("4 / 10", html)
        self.assertIn("/purchasing/42", html)
        self.assertIn("/purchasing/suppliers", html)
        self.assertIn("/purchasing/new", html)
        list_orders.assert_called_once_with(9, None, "1", tenant_id=4)

    def test_create_form_renders_search_and_partial_receipt_explanation(self):
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.list_active_suppliers",
            return_value=[{"id": 3, "name": "Pet Supply Co."}],
        ):
            response = self.client.get("/purchasing/new")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/purchasing/products", html)
        self.assertIn("Nhập từ khóa để tìm sản phẩm đang bán", html)
        self.assertIn("tồn kho sau khi bạn xác nhận", html)
        self.assertIn("purchase-line-template", html)

    def test_create_route_passes_repeated_form_lines_to_service(self):
        with (
            patch(
                "petcare.routes.purchasing_routes.purchase_service.list_active_suppliers",
                return_value=[{"id": 3, "name": "Pet Supply Co."}],
            ),
            patch(
                "petcare.routes.purchasing_routes.purchase_service.create_purchase_order",
                return_value=42,
            ) as create_order,
        ):
            response = self.client.post("/purchasing/new", data={
                "supplier_id": "3",
                "note": "Deliver Monday",
                "product_id[]": ["15", "16"],
                "product_label[]": ["Food", "Toy"],
                "quantity[]": ["6", "2"],
                "unit_cost[]": ["25000", "10000"],
            })

        self.assertEqual(response.status_code, 302)
        self.assertIn("/purchasing/42", response.headers["Location"])
        self.assertEqual(create_order.call_args.args[0], 9)
        self.assertEqual(create_order.call_args.args[1]["supplier_id"], "3")
        self.assertEqual(create_order.call_args.args[2], [
            {"product_id": "15", "label": "Food", "quantity": "6", "unit_cost": "25000"},
            {"product_id": "16", "label": "Toy", "quantity": "2", "unit_cost": "10000"},
        ])

    def test_product_search_endpoint_returns_json_catalog_rows(self):
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.search_active_products",
            return_value=[{"id": 1, "code": "FOOD-1", "name": "Cat food"}],
        ) as search:
            response = self.client.get("/purchasing/products?q=food")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"items": [{"id": 1, "code": "FOOD-1", "name": "Cat food"}]})
        search.assert_called_once_with(9, "food", tenant_id=4)

    def test_supplier_listing_and_create_routes_work(self):
        empty_page = {"page": 1, "pages": 1, "total": 0, "first": 0, "last": 0,
                      "has_previous": False, "has_next": False, "page_size": 25}
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.list_suppliers",
            return_value={"items": [], "pagination": empty_page},
        ):
            response = self.client.get("/purchasing/suppliers")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Chưa có nhà cung cấp phù hợp", response.get_data(as_text=True))

        with patch("petcare.routes.purchasing_routes.purchase_service.create_supplier", return_value=5) as create:
            response = self.client.post("/purchasing/suppliers/new", data={"name": "Vendor"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/purchasing/suppliers", response.headers["Location"])
        create.assert_called_once()

    def test_staff_cannot_open_admin_purchase_pages(self):
        self.user["role"] = "staff"
        with patch("petcare.routes.purchasing_routes.purchase_service.list_purchase_orders") as list_orders:
            response = self.client.get("/purchasing")
        self.assertEqual(response.status_code, 403)
        list_orders.assert_not_called()

    def test_receive_route_calls_service_and_redirects_to_order(self):
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.receive_purchase_order",
            return_value="partially_received",
        ) as receive:
            response = self.client.post("/purchasing/42/receive", data={
                "item_id[]": ["88", "89"],
                "quantity[]": ["4", "0"],
                "receipt_request_key": "53c8cb27-5ad2-43fb-9b28-8fd292d983a1",
            })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/purchasing/42", response.headers["Location"])
        receive.assert_called_once_with(
            9,
            42,
            [
                {"item_id": "88", "quantity": "4"},
                {"item_id": "89", "quantity": "0"},
            ],
            tenant_id=4,
            request_key="53c8cb27-5ad2-43fb-9b28-8fd292d983a1",
        )

    def test_purchase_order_detail_renders_receiving_controls_until_complete(self):
        order = {
            "id": 42,
            "supplier_name_snapshot": "Pet Supply Co.",
            "created_at": datetime(2026, 10, 31, 9, 30),
            "creator_name": "Demo Admin",
            "status": "partially_received",
            "currency_code": "VND",
            "total_amount": Decimal("100000"),
            "ordered_units": 10,
            "received_units": 4,
            "note": "Morning delivery",
            "items": [{
                "id": 88,
                "product_name_snapshot": "Cat food",
                "product_code_snapshot": "FOOD-1",
                "product_active": 1,
                "unit_cost": Decimal("10000"),
                "quantity_ordered": 10,
                "quantity_received": 4,
                "current_stock": 7,
                "line_total": Decimal("100000"),
            }],
        }
        with patch(
            "petcare.routes.purchasing_routes.purchase_service.get_purchase_order_detail",
            return_value=order,
        ):
            response = self.client.get("/purchasing/42")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Ghi số lượng thực nhận", html)
        self.assertIn("/purchasing/42/receive", html)
        self.assertIn("/purchasing/42/cancel", html)
        self.assertIn('name="receipt_request_key"', html)
        self.assertIn("Cat food", html)
        self.assertIn("4 / 10", html)
