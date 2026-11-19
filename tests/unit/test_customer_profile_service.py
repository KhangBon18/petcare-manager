from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from petcare.services import customer_service
from petcare.services.exceptions import ValidationError


class CustomerProfileServiceTests(TestCase):
    def test_profile_sums_counts_and_paginates_without_merging_currencies(self):
        customer = {"id": 7, "full_name": "Customer", "active": 1}
        currency_rows = [
            {
                "currency_code": "USD",
                "invoice_count": 3,
                "paid_invoice_count": 2,
                "unpaid_invoice_count": 1,
                "paid_total": Decimal("120.50"),
                "unpaid_total": Decimal("30"),
            },
            {
                "currency_code": "VND",
                "invoice_count": 24,
                "paid_invoice_count": 20,
                "unpaid_invoice_count": 2,
                "paid_total": Decimal("900000"),
                "unpaid_total": Decimal("150000"),
            },
        ]
        invoice_rows = [{"id": 200}]
        purchased_pet_rows = [{"id": 12, "name": "Miu"}]
        with (
            patch("petcare.services.customer_service.read_connection") as read,
            patch("petcare.services.customer_service.require_actor") as require_actor,
            patch(
                "petcare.services.customer_service.customer_repo.get_customer",
                return_value=customer,
            ),
            patch(
                "petcare.services.customer_service.customer_repo.count_customer_invoices",
                return_value=27,
            ),
            patch(
                "petcare.services.customer_service.customer_repo.summarize_customer_invoices",
                return_value=currency_rows,
            ),
            patch(
                "petcare.services.customer_service.customer_repo.list_customer_invoices_page",
                return_value=invoice_rows,
            ) as list_page,
            patch(
                "petcare.services.customer_service.customer_repo.count_customer_pets",
                return_value=13,
            ),
            patch(
                "petcare.services.customer_service.customer_repo.list_customer_pets",
                return_value=purchased_pet_rows,
            ) as list_pets,
        ):
            connection = object()
            read.return_value.__enter__.return_value = connection
            result = customer_service.get_customer_profile(
                1, 7, page="2", pet_page="2", tenant_id=42
            )

        require_actor.assert_called_once_with(connection, 1, tenant_id=42)
        list_page.assert_called_once_with(connection, 7, 25, 25)
        list_pets.assert_called_once_with(connection, 7, 12, 12)
        self.assertIs(result["customer"], customer)
        self.assertEqual(result["invoices"], invoice_rows)
        self.assertEqual(result["purchased_pets"], purchased_pet_rows)
        self.assertEqual(result["pagination"]["page"], 2)
        self.assertEqual(result["pet_pagination"]["page"], 2)
        self.assertEqual(result["pet_pagination"]["total"], 13)
        self.assertEqual(result["summary"]["invoice_count"], 27)
        self.assertEqual(result["summary"]["paid_invoice_count"], 22)
        self.assertEqual(result["summary"]["unpaid_invoice_count"], 3)
        self.assertEqual(result["summary"]["currencies"], currency_rows)

    def test_invalid_customer_id_is_rejected_before_opening_database(self):
        with patch("petcare.services.customer_service.read_connection") as read:
            with self.assertRaises(ValidationError):
                customer_service.get_customer_profile(1, "not-an-id")
        read.assert_not_called()
