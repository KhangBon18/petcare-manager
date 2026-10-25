import unittest
from decimal import Decimal
from unittest.mock import patch

from petcare.services import assistant_service, customer_service, invoice_service
from petcare.services.assistant_query import catalog_filters, query_period
from petcare.services.exceptions import ValidationError


class AssistantQueryRegressionTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "summary": {"available_pets": 3, "active_products": 1,
                        "active_customers": 1, "revenue_today": 500000},
            "currency_code": "VND", "low_stock": [],
            "products": [{"name": "Hạt mèo", "code": "P1", "category": "Thức ăn",
                          "unit_price": 150000, "stock_qty": 5}],
            "available_pets": [
                {"name": name, "species": "Mèo", "breed": "Mèo ta",
                 "coat_color": "trắng", "eye_color": "xanh", "sale_price": price}
                for name, price in [("Miu", 2000000), ("May", 3000000), ("Nori", 5000000)]
            ],
        }

    def test_time_phrase_does_not_change_pet_intent_or_provider_scope(self):
        for question in ["Hôm nay còn mèo nào?", "Hom nay con meo nao?",
                         "Which cats are available today?", "Tháng này còn mèo nào?"]:
            with self.subTest(question=question):
                self.assertEqual(assistant_service._question_intent(question), "pet")
                reply = assistant_service.local_answer(question, self.context)
                self.assertIn("Miu", reply)
                self.assertNotIn("Doanh thu", reply)
                context = assistant_service._provider_context(question, self.context)
                self.assertIn("available_pets", context)
                self.assertNotIn("revenue_today", str(context))

    def test_price_operators_ranges_and_shared_units(self):
        cases = {
            "dưới 3 triệu": ["Miu"],
            "trên 3 triệu": ["Nori"],
            "tối đa 3 triệu": ["Miu", "May"],
            "tối thiểu 3 triệu": ["May", "Nori"],
            "từ 2 đến 3 triệu": ["Miu", "May"],
            "từ 2 triệu đến 3 triệu": ["Miu", "May"],
            "khoảng 2 đến 3 triệu": ["Miu", "May"],
            "khoảng 3 triệu": ["May"],
            "từ 2 triệu": ["Miu", "May", "Nori"],
            "đến 3 triệu": ["Miu", "May"],
            "không quá 3 triệu": ["Miu", "May"],
            "trên 1,5 triệu dưới 3 triệu": ["Miu"],
            "từ 3000k đến 2 triệu": [],
            "under 3 million": ["Miu"],
            "at least 3 million": ["May", "Nori"],
            "from 2 to 3 million": ["Miu", "May"],
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                rows, narrowed = assistant_service._pet_search(
                    f"Tìm mèo lông trắng {phrase}", self.context
                )
                self.assertTrue(narrowed)
                self.assertEqual([row["name"] for row in rows], expected)

    def test_product_prices_and_currency_formatting(self):
        for amount in ["200.000", "200,000", "200k", "0,2 triệu", "0.2 million"]:
            with self.subTest(amount=amount):
                rows, _ = assistant_service._product_search(f"Tìm sản phẩm hạt dưới {amount} VND", self.context)
                self.assertEqual(len(rows), 1)
        rows, _ = assistant_service._product_search("Tìm sản phẩm hạt trên 200k", self.context)
        self.assertEqual(rows, [])

    def test_filters_keep_real_search_terms_and_reject_missing_prices(self):
        text, filters = catalog_filters("husky long trang duoi 3 trieu")
        self.assertIn("husky", text)
        self.assertNotIn("duoi", text)
        self.assertFalse(filters[0].matches(None))
        self.assertFalse(filters[0].matches("NaN"))
        self.assertTrue(filters[0].matches(Decimal("2999999")))
        rows, _ = assistant_service._pet_search("Tìm mèo Husky dưới 3 triệu", self.context)
        self.assertEqual(rows, [])

    def test_revenue_period_is_independent_of_subject(self):
        self.assertEqual(query_period("doanh thu thang nay"), "month")
        self.assertEqual(query_period("revenue this week"), "week")
        self.assertEqual(query_period("doanh thu hom nay"), "today")
        self.assertEqual(assistant_service._question_intent("Doanh thu bán mèo hôm nay?"), "revenue")

    def test_non_string_question_fails_before_database_access(self):
        with patch.object(assistant_service, "read_connection") as connect:
            for message in [42, True, [], {}]:
                with self.subTest(message=message), self.assertRaises(ValidationError):
                    assistant_service.answer(1, message)
            connect.assert_not_called()


class FormValidationRegressionTests(unittest.TestCase):
    def test_customer_reports_all_invalid_fields_before_writing(self):
        with patch.object(customer_service, "transaction") as transaction:
            with self.assertRaises(ValidationError) as caught:
                customer_service.create_customer(1, {"full_name": "", "phone": "bad", "address": "x" * 256})
            self.assertEqual(set(caught.exception.field_errors), {"full_name", "phone", "address"})
            transaction.assert_not_called()

    def test_invoice_reports_customer_note_and_per_line_fields(self):
        with patch.object(invoice_service, "transaction") as transaction:
            with self.assertRaises(ValidationError) as caught:
                invoice_service.create_invoice(1, {"customer_id": "bad", "note": "x" * 501}, [
                    {"item_type": "product", "item_id": "1", "quantity": "0"},
                    {"item_type": "pet", "item_id": "bad", "quantity": "1"},
                ])
            self.assertEqual(set(caught.exception.field_errors), {"customer_id", "note", "quantity_0", "item_1"})
            transaction.assert_not_called()

    def test_pet_quantity_and_duplicate_errors_point_to_the_right_row(self):
        for items, field in [
            ([{"item_type": "pet", "item_id": "1", "quantity": "3"}], "quantity_0"),
            ([{"item_type": "pet", "item_id": "1", "quantity": "1"}] * 2, "item_1"),
        ]:
            with self.subTest(field=field), self.assertRaises(ValidationError) as caught:
                invoice_service._normalize_items(items)
            self.assertIn(field, caught.exception.field_errors)
