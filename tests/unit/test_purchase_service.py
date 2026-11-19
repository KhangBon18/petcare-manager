from contextlib import contextmanager
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare.services import purchase_service
from petcare.services.exceptions import ConflictError, ValidationError


@contextmanager
def _connection_scope(connection):
    yield connection


class PurchaseServiceTests(TestCase):
    def setUp(self):
        self.connection = object()
        self.actor = {"id": 9, "tenant_id": 4, "default_currency": "VND"}

    def _patch_transaction(self):
        patcher = patch(
            "petcare.services.purchase_service.transaction",
            side_effect=lambda: _connection_scope(self.connection),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for target, return_value in (
            ("purchase_repo.find_receipt_request", None),
            ("purchase_repo.create_receipt_request", 1),
        ):
            patcher = patch(
                f"petcare.services.purchase_service.{target}",
                return_value=return_value,
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supplier_validation_normalizes_optional_contact_fields(self):
        values = purchase_service._supplier_data({
            "name": "  Pet Supply Co. ",
            "contact_name": " Linh ",
            "phone": "+84 901234567",
            "email": " SALES@Example.COM ",
            "address": "  District 1 ",
        })

        self.assertEqual(values, {
            "name": "Pet Supply Co.",
            "contact_name": "Linh",
            "phone": "+84 901234567",
            "email": "sales@example.com",
            "address": "District 1",
        })

    def test_invalid_supplier_email_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "Email nhà cung cấp"):
            purchase_service._supplier_data({"name": "Vendor", "email": "not-an-email"})

    def test_create_purchase_order_snapshots_products_and_currency(self):
        self._patch_transaction()
        product_rows = [
            {"id": 3, "code": "FOOD-1", "name": "Cat food"},
            {"id": 7, "code": "TOY-1", "name": "Toy"},
        ]
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor) as actor,
            patch(
                "petcare.services.purchase_service.purchase_repo.get_supplier",
                return_value={"id": 5, "name": "Wholesaler", "active": 1},
            ) as get_supplier,
            patch(
                "petcare.services.purchase_service.product_repo.get_products_by_ids",
                return_value=product_rows,
            ) as get_products,
            patch(
                "petcare.services.purchase_service.purchase_repo.create_purchase_order",
                return_value=31,
            ) as create_order,
            patch("petcare.services.purchase_service.purchase_repo.add_purchase_order_items") as add_items,
            patch("petcare.services.purchase_service.audit_repo.add_event") as add_event,
        ):
            order_id = purchase_service.create_purchase_order(
                9,
                {"supplier_id": "5", "note": "Morning delivery"},
                [
                    {"product_id": "3", "quantity": "4", "unit_cost": "1250"},
                    {"product_id": "7", "quantity": "2", "unit_cost": "500"},
                ],
                tenant_id=4,
            )

        self.assertEqual(order_id, 31)
        actor.assert_called_once_with(self.connection, 9, admin=True, tenant_id=4)
        get_supplier.assert_called_once_with(self.connection, 5, lock=True)
        get_products.assert_called_once_with(self.connection, [3, 7], lock=True, active_only=True)
        create_order.assert_called_once_with(
            self.connection, 5, "Wholesaler", 9, "VND", Decimal("6000"), "Morning delivery"
        )
        inserted = add_items.call_args.args[2]
        self.assertEqual(
            [(line["product_id"], line["code"], line["name"], line["quantity"], line["line_total"])
             for line in inserted],
            [(3, "FOOD-1", "Cat food", 4, Decimal("5000")),
             (7, "TOY-1", "Toy", 2, Decimal("1000"))],
        )
        add_event.assert_called_once()

    def test_duplicate_products_are_rejected_before_order_insertion(self):
        self._patch_transaction()
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_supplier") as get_supplier,
            patch("petcare.services.purchase_service.purchase_repo.create_purchase_order") as create_order,
        ):
            with self.assertRaisesRegex(ValidationError, "chỉ được xuất hiện một lần"):
                purchase_service.create_purchase_order(
                    9,
                    {"supplier_id": "5"},
                    [
                        {"product_id": "3", "quantity": "1", "unit_cost": "1"},
                        {"product_id": "3", "quantity": "2", "unit_cost": "1"},
                    ],
                )
        get_supplier.assert_not_called()
        create_order.assert_not_called()

    def test_partial_receipt_updates_stock_ledger_and_order_status_atomically(self):
        self._patch_transaction()
        order = {"id": 31, "status": "ordered"}
        items = [
            {"id": 70, "product_id": 3, "product_name_snapshot": "Food", "quantity_ordered": 10, "quantity_received": 0},
            {"id": 71, "product_id": 7, "product_name_snapshot": "Toy", "quantity_ordered": 2, "quantity_received": 0},
        ]
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_purchase_order", return_value=order) as get_order,
            patch("petcare.services.purchase_service.purchase_repo.lock_purchase_order_items", return_value=items),
            patch(
                "petcare.services.purchase_service.product_repo.get_products_by_ids",
                return_value=[{"id": 3, "name": "Food", "stock_qty": 4}],
            ) as get_products,
            patch("petcare.services.purchase_service.product_repo.adjust_stock", return_value=1) as adjust_stock,
            patch("petcare.services.purchase_service.purchase_repo.add_received_quantity", return_value=1) as update_received,
            patch("petcare.services.purchase_service.product_repo.add_stock_movement") as movement,
            patch("petcare.services.purchase_service.purchase_repo.set_purchase_order_status", return_value=1) as set_status,
            patch("petcare.services.purchase_service.audit_repo.add_event") as add_event,
        ):
            status = purchase_service.receive_purchase_order(
                9, 31, [{"item_id": "70", "quantity": "3"}, {"item_id": "71", "quantity": "0"}]
            )

        self.assertEqual(status, "partially_received")
        get_order.assert_called_once_with(self.connection, 31, lock=True)
        get_products.assert_called_once_with(self.connection, [3], lock=True)
        adjust_stock.assert_called_once_with(self.connection, 3, 3)
        update_received.assert_called_once_with(self.connection, 31, 70, 3)
        movement.assert_called_once_with(
            self.connection, 3, 3, "Nhận theo đơn nhập #31", 9,
            purchase_order_id=31, purchase_order_item_id=70,
        )
        set_status.assert_called_once_with(self.connection, 31, "partially_received")
        add_event.assert_called_once()

    def test_receipt_over_ordered_quantity_does_not_touch_stock(self):
        self._patch_transaction()
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_purchase_order", return_value={"id": 31, "status": "partially_received"}),
            patch(
                "petcare.services.purchase_service.purchase_repo.lock_purchase_order_items",
                return_value=[{"id": 70, "product_id": 3, "product_name_snapshot": "Food", "quantity_ordered": 10, "quantity_received": 8}],
            ),
            patch("petcare.services.purchase_service.product_repo.adjust_stock") as adjust_stock,
        ):
            with self.assertRaisesRegex(ValidationError, "vượt số còn lại"):
                purchase_service.receive_purchase_order(9, 31, [{"item_id": "70", "quantity": "3"}])
        adjust_stock.assert_not_called()

    def test_receipt_checks_stock_limit_before_any_stock_update(self):
        self._patch_transaction()
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_purchase_order", return_value={"id": 31, "status": "ordered"}),
            patch(
                "petcare.services.purchase_service.purchase_repo.lock_purchase_order_items",
                return_value=[{"id": 70, "product_id": 3, "product_name_snapshot": "Food", "quantity_ordered": 2, "quantity_received": 0}],
            ),
            patch(
                "petcare.services.purchase_service.product_repo.get_products_by_ids",
                return_value=[{"id": 3, "name": "Food", "stock_qty": purchase_service.MAX_STOCK_QTY}],
            ),
            patch("petcare.services.purchase_service.product_repo.adjust_stock") as adjust_stock,
        ):
            with self.assertRaisesRegex(ValidationError, "sẽ vượt"):
                purchase_service.receive_purchase_order(9, 31, [{"item_id": "70", "quantity": "1"}])
        adjust_stock.assert_not_called()

    def test_closed_orders_cannot_receive_again(self):
        self._patch_transaction()
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_purchase_order", return_value={"id": 31, "status": "cancelled"}),
            patch("petcare.services.purchase_service.purchase_repo.lock_purchase_order_items") as lock_items,
        ):
            with self.assertRaises(ConflictError):
                purchase_service.receive_purchase_order(9, 31, [{"item_id": "70", "quantity": "1"}])
        lock_items.assert_not_called()

    def test_last_receipt_closes_order_as_received(self):
        self._patch_transaction()
        with (
            patch("petcare.services.purchase_service.require_actor", return_value=self.actor),
            patch("petcare.services.purchase_service.purchase_repo.get_purchase_order", return_value={"id": 31, "status": "partially_received"}),
            patch(
                "petcare.services.purchase_service.purchase_repo.lock_purchase_order_items",
                return_value=[{"id": 70, "product_id": 3, "product_name_snapshot": "Food", "quantity_ordered": 10, "quantity_received": 8}],
            ),
            patch("petcare.services.purchase_service.product_repo.get_products_by_ids", return_value=[{"id": 3, "name": "Food", "stock_qty": 4}]),
            patch("petcare.services.purchase_service.product_repo.adjust_stock", return_value=1),
            patch("petcare.services.purchase_service.purchase_repo.add_received_quantity", return_value=1),
            patch("petcare.services.purchase_service.product_repo.add_stock_movement"),
            patch("petcare.services.purchase_service.purchase_repo.set_purchase_order_status", return_value=1) as set_status,
            patch("petcare.services.purchase_service.audit_repo.add_event"),
        ):
            status = purchase_service.receive_purchase_order(9, 31, [{"item_id": "70", "quantity": "2"}])
        self.assertEqual(status, "received")
        set_status.assert_called_once_with(self.connection, 31, "received")

    def test_invalid_purchase_order_id_is_rejected_before_opening_database(self):
        with patch("petcare.services.purchase_service.transaction") as transaction:
            with self.assertRaises(ValidationError):
                purchase_service.receive_purchase_order(9, "nope", [{"item_id": "1", "quantity": "1"}])
        transaction.assert_not_called()
