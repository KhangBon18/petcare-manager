from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest import TestCase
from unittest.mock import ANY, patch

from petcare import create_app


class RefundPageTests(TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "refund-page-tests-only",
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.user = {
            "id": 9, "role": "admin", "full_name": "Store Admin",
            "preferred_locale": "vi", "store_memberships": [],
            "tenant": {
                "id": 4, "slug": "main", "name": "Demo Store",
                "default_currency": "VND", "timezone": "Asia/Ho_Chi_Minh",
            },
        }
        with self.client.session_transaction() as session:
            session.update(user_id=9, tenant_id=4, session_version=0)
        self.user_loader = patch(
            "petcare.auth.load_active_user", side_effect=lambda *args: deepcopy(self.user)
        )
        self.user_loader.start()
        self.addCleanup(self.user_loader.stop)

    def invoice(self):
        return {
            "id": 11,
            "customer_id": 7,
            "customer_name": "Linh Nguyen",
            "customer_phone": "0901234567",
            "created_at": None,
            "status": "paid",
            "currency_code": "VND",
            "paid_at": None,
            "created_by_name": "Store Admin",
            "note": "",
            "total_amount": Decimal("200000"),
            "total_refunded": Decimal("50000"),
            "net_paid": Decimal("150000"),
            "refund_complete": False,
            "items": [{
                "id": 31, "item_type": "product", "name_snapshot": "Cat food",
                "item_code_snapshot": "FOOD-1", "unit_price": Decimal("100000"),
                "quantity": 2, "line_total": Decimal("200000"),
                "refunded_quantity": 1, "refundable_quantity": 1,
            }],
            "refunds": [{
                "id": 40, "created_at": None, "method": "cash", "creator_name": "Store Admin",
                "refund_total": Decimal("50000"), "currency_code": "VND", "note": "",
                "items": [{
                    "item_name_snapshot": "Cat food", "quantity": 1,
                    "disposition": "resell", "refund_amount": Decimal("50000"),
                }],
            }],
        }

    def test_admin_invoice_page_shows_refund_balance_form_and_history(self):
        with patch(
            "petcare.routes.invoice_routes.invoice_service.get_invoice",
            return_value=self.invoice(),
        ):
            response = self.client.get("/invoices/11")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Doanh thu thuần", html)
        self.assertIn("Trả hàng và hoàn tiền", html)
        self.assertIn('name="quantity_31"', html)
        self.assertIn("Lịch sử trả hàng và hoàn tiền", html)
        self.assertIn('id="refund-40"', html)
        self.assertIn('class="app-body invoice-detail-page"', html)
        self.assertEqual(html.count('data-assistant-open'), 1)
        stylesheet = Path(__file__).resolve().parents[2] / "petcare/static/css/app.css"
        self.assertIn(
            ".invoice-detail-page .assistant-launcher { display: none; }",
            stylesheet.read_text(encoding="utf-8"),
        )

    def test_admin_refund_post_passes_only_selected_server_parsed_lines(self):
        with patch(
            "petcare.routes.invoice_routes.refund_service.refund_invoice",
            return_value={"status": "refunded", "refund_id": 41},
        ) as refund:
            response = self.client.post("/invoices/11/refund", data={
                "request_key": "9cdbb1a7-1fc0-4b31-b1dd-f5ff6ca49d0d",
                "method": "bank_transfer",
                "note": "Return checked",
                "invoice_item_id": ["31"],
                "quantity_31": "1",
                "disposition_31": "quarantine",
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/invoices/11")
        refund.assert_called_once_with(
            9,
            11,
            ANY,
            [{"invoice_item_id": "31", "quantity": "1", "disposition": "quarantine"}],
        )
        self.assertEqual(refund.call_args.args[2]["method"], "bank_transfer")

    def test_staff_is_blocked_from_refund_route(self):
        self.user["role"] = "staff"
        with patch(
            "petcare.routes.invoice_routes.refund_service.refund_invoice"
        ) as refund:
            response = self.client.post("/invoices/11/refund", data={})
        self.assertEqual(response.status_code, 403)
        refund.assert_not_called()
