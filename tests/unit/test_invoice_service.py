from contextlib import contextmanager
from decimal import Decimal
import unittest
from unittest.mock import patch

from petcare.services import invoice_service
from petcare.services.exceptions import ConflictError


@contextmanager
def _connection_scope(connection):
    yield connection


class InvoiceServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = object()
        self.actor = {"id": 9, "tenant_id": 4, "default_currency": "VND"}
        self.invoice = {"id": 27, "customer_id": 7, "status": "unpaid", "currency_code": "VND"}
        self.line = {
            "id": 101,
            "item_type": "product",
            "product_id": 6,
            "pet_id": None,
            "quantity": 2,
            "line_total": Decimal("2500"),
        }

    def _transaction(self):
        patcher = patch(
            "petcare.services.invoice_service.transaction",
            side_effect=lambda: _connection_scope(self.connection),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_invoice_uses_catalog_repositories_and_saves_server_snapshot(self):
        self._transaction()
        product = {
            "id": 6, "code": "FOOD-1", "name": "Cat food",
            "unit_price": Decimal("1250"), "stock_qty": 8, "active": 1,
        }
        with (
            patch("petcare.services.invoice_service.require_actor", return_value=self.actor),
            patch("petcare.services.invoice_service.customer_repo.get_customer", return_value={"id": 7, "active": 1}),
            patch("petcare.services.invoice_service.product_repo.get_product", return_value=product) as get_product,
            patch("petcare.services.invoice_service.invoice_repo.create_invoice", return_value=27) as create_invoice,
            patch("petcare.services.invoice_service.invoice_repo.add_item") as add_item,
            patch("petcare.services.invoice_service.audit_repo.add_event"),
        ):
            result = invoice_service.create_invoice(
                9,
                {"customer_id": "7", "note": ""},
                [{"item_type": "product", "item_id": "6", "quantity": "2"}],
            )

        self.assertEqual(result, 27)
        get_product.assert_called_once_with(self.connection, 6)
        create_invoice.assert_called_once_with(self.connection, 7, 9, "", "VND")
        saved_line = add_item.call_args.args[2]
        self.assertEqual(saved_line["code"], "FOOD-1")
        self.assertEqual(saved_line["name"], "Cat food")
        self.assertEqual(saved_line["unit_price"], Decimal("1250"))
        self.assertEqual(saved_line["line_total"], Decimal("2500"))

    def test_payment_locks_catalog_rows_then_updates_inventory_and_invoice(self):
        self._transaction()
        with (
            patch("petcare.services.invoice_service.require_actor", return_value=self.actor),
            patch("petcare.services.invoice_service.invoice_repo.get_invoice", return_value=self.invoice),
            patch("petcare.services.invoice_service.invoice_repo.get_items_for_update", return_value=[self.line]),
            patch("petcare.services.invoice_service.product_repo.get_products_by_ids", return_value=[{
                "id": 6, "name": "Cat food", "stock_qty": 5, "active": 1,
            }]) as locked_products,
            patch("petcare.services.invoice_service.product_repo.reserve_stock_for_sale", return_value=1) as reserve,
            patch("petcare.services.invoice_service.product_repo.add_stock_movement") as movement,
            patch("petcare.services.invoice_service.invoice_repo.update_paid", return_value=1) as update_paid,
            patch("petcare.services.invoice_service.audit_repo.add_event"),
        ):
            result = invoice_service.pay_invoice(9, 27)

        self.assertEqual(result, "paid")
        locked_products.assert_called_once_with(self.connection, {6: 2}, lock=True)
        reserve.assert_called_once_with(self.connection, 6, 2)
        movement.assert_called_once_with(
            self.connection, 6, -2, "Bán theo hóa đơn #27", 9, 27
        )
        update_paid.assert_called_once_with(self.connection, 27)

    def test_stock_race_aborts_payment_before_marking_invoice_paid(self):
        self._transaction()
        with (
            patch("petcare.services.invoice_service.require_actor", return_value=self.actor),
            patch("petcare.services.invoice_service.invoice_repo.get_invoice", return_value=self.invoice),
            patch("petcare.services.invoice_service.invoice_repo.get_items_for_update", return_value=[self.line]),
            patch("petcare.services.invoice_service.product_repo.get_products_by_ids", return_value=[{
                "id": 6, "name": "Cat food", "stock_qty": 5, "active": 1,
            }]),
            patch("petcare.services.invoice_service.product_repo.reserve_stock_for_sale", return_value=0),
            patch("petcare.services.invoice_service.invoice_repo.update_paid") as update_paid,
            self.assertRaises(ConflictError),
        ):
            invoice_service.pay_invoice(9, 27)
        update_paid.assert_not_called()


if __name__ == "__main__":
    unittest.main()
