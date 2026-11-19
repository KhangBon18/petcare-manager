from contextlib import contextmanager
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare.services import refund_service
from petcare.services.exceptions import ConflictError, ForbiddenError, ValidationError


REQUEST_KEY = "9cdbb1a7-1fc0-4b31-b1dd-f5ff6ca49d0d"


@contextmanager
def _connection_scope(connection):
    yield connection


class RefundServiceTests(TestCase):
    def setUp(self):
        self.connection = object()
        self.invoice = {
            "id": 11,
            "customer_id": 7,
            "status": "paid",
            "currency_code": "VND",
        }
        self.product_line = {
            "id": 101,
            "item_type": "product",
            "product_id": 6,
            "pet_id": None,
            "quantity": 3,
            "unit_price": Decimal("1250"),
            "item_code_snapshot": "FOOD-1",
            "name_snapshot": "Cat food",
        }

    def _transaction(self):
        patcher = patch(
            "petcare.services.refund_service.transaction",
            side_effect=lambda: _connection_scope(self.connection),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _common_patches(self, *, items=None, refunded=None, previous=None):
        patches = [
            patch("petcare.services.refund_service.require_actor", return_value={"id": 9}),
            patch("petcare.services.refund_service.invoice_repo.get_invoice", return_value=self.invoice),
            patch("petcare.services.refund_service.refund_repo.get_refund_by_request_key", return_value=previous),
            patch("petcare.services.refund_service.invoice_repo.get_items_for_update", return_value=items or [self.product_line]),
            patch("petcare.services.refund_service.refund_repo.refunded_quantities", return_value=refunded or {}),
        ]
        mocks = [item.start() for item in patches]
        for item in patches:
            self.addCleanup(item.stop)
        return mocks

    def _request(self, lines, **values):
        return refund_service.refund_invoice(
            9,
            11,
            {"request_key": REQUEST_KEY, "method": "cash", "note": "Checked at counter", **values},
            lines,
            tenant_id=4,
        )

    def test_partial_product_refund_restocks_and_links_inventory_ledger(self):
        self._transaction()
        actor, get_invoice, get_key, get_items, get_quantities = self._common_patches()
        with (
            patch(
                "petcare.services.refund_service.product_repo.get_products_by_ids",
                return_value=[{"id": 6, "name": "Cat food", "stock_qty": 2}],
            ) as products,
            patch("petcare.services.refund_service.refund_repo.create_refund", return_value=18) as create_refund,
            patch("petcare.services.refund_service.refund_repo.create_refund_item", return_value=19) as create_line,
            patch("petcare.services.refund_service.product_repo.adjust_stock", return_value=1) as adjust_stock,
            patch("petcare.services.refund_service.product_repo.add_stock_movement") as movement,
            patch("petcare.services.refund_service.audit_repo.add_event") as audit,
        ):
            result = self._request([{
                "invoice_item_id": "101", "quantity": "1", "disposition": "resell",
            }])

        self.assertEqual(result, {"status": "refunded", "refund_id": 18})
        actor.assert_called_once_with(self.connection, 9, admin=True, tenant_id=4)
        get_invoice.assert_called_once_with(self.connection, 11, lock=True)
        get_key.assert_called_once_with(self.connection, REQUEST_KEY)
        get_items.assert_called_once_with(self.connection, 11)
        get_quantities.assert_called_once_with(self.connection, 11)
        products.assert_called_once_with(self.connection, [6], lock=True)
        create_refund.assert_called_once_with(
            self.connection, 11, 9, REQUEST_KEY, "cash", "Checked at counter", "VND", Decimal("1250")
        )
        create_line.assert_called_once_with(
            self.connection, 11, 18, self.product_line, 1, Decimal("1250"), "resell"
        )
        adjust_stock.assert_called_once_with(self.connection, 6, 1)
        movement.assert_called_once_with(
            self.connection, 6, 1, "Nhận trả theo hoàn #18", 9,
            invoice_id=11, refund_id=18, refund_item_id=19,
        )
        audit.assert_called_once()

    def test_cumulative_refund_cannot_exceed_original_quantity(self):
        self._transaction()
        self._common_patches(refunded={101: 2})
        with (
            patch("petcare.services.refund_service.product_repo.get_products_by_ids") as products,
            patch("petcare.services.refund_service.refund_repo.create_refund") as create_refund,
        ):
            with self.assertRaisesRegex(ConflictError, "vượt số còn có thể hoàn"):
                self._request([{
                    "invoice_item_id": "101", "quantity": "2", "disposition": "resell",
                }])
        products.assert_not_called()
        create_refund.assert_not_called()

    def test_idempotency_key_returns_existing_refund_without_writing_again(self):
        self._transaction()
        self._common_patches(previous={"invoice_id": 11, "id": 44})
        with patch("petcare.services.refund_service.refund_repo.create_refund") as create_refund:
            result = self._request([{
                "invoice_item_id": "101", "quantity": "1", "disposition": "resell",
            }])
        self.assertEqual(result, {"status": "already_recorded", "refund_id": 44})
        create_refund.assert_not_called()

    def test_staff_cannot_refund_even_when_endpoint_is_bypassed(self):
        self._transaction()
        with (
            patch(
                "petcare.services.refund_service.require_actor",
                side_effect=ForbiddenError("admin only"),
            ) as actor,
            patch("petcare.services.refund_service.invoice_repo.get_invoice") as get_invoice,
        ):
            with self.assertRaises(ForbiddenError):
                self._request([{
                    "invoice_item_id": "101", "quantity": "1", "disposition": "resell",
                }])
        actor.assert_called_once_with(self.connection, 9, admin=True, tenant_id=4)
        get_invoice.assert_not_called()

    def test_returned_pet_changes_status_only_after_customer_ownership_is_checked(self):
        self._transaction()
        pet_line = {
            "id": 102,
            "item_type": "pet",
            "product_id": None,
            "pet_id": 29,
            "quantity": 1,
            "unit_price": Decimal("5000000"),
            "item_code_snapshot": "PET-29",
            "name_snapshot": "Miu",
        }
        self._common_patches(items=[pet_line])
        with (
            patch("petcare.services.refund_service.product_repo.get_products_by_ids", return_value=[]),
            patch(
                "petcare.services.refund_service.pet_repo.get_pets_by_ids",
                return_value=[{"id": 29, "sale_status": "sold", "buyer_id": 7}],
            ) as lock_pets,
            patch("petcare.services.refund_service.refund_repo.create_refund", return_value=21),
            patch("petcare.services.refund_service.refund_repo.create_refund_item", return_value=22),
            patch("petcare.services.refund_service.pet_repo.return_sold_pet", return_value=1) as return_pet,
            patch("petcare.services.refund_service.audit_repo.add_event"),
        ):
            result = self._request([{
                "invoice_item_id": "102", "quantity": "1", "disposition": "quarantine",
            }])
        self.assertEqual(result["status"], "refunded")
        lock_pets.assert_called_once()
        lock_pets.assert_called_once_with(self.connection, [29], lock=True)
        return_pet.assert_called_once_with(self.connection, 29, 7, "inactive")

    def test_invalid_key_and_zero_refund_are_rejected(self):
        with self.assertRaises(ValidationError):
            self._request([], request_key="invalid")
        with self.assertRaises(ValidationError):
            self._request([{
                "invoice_item_id": "101", "quantity": "0", "disposition": "resell",
            }])
