import unittest
from unittest.mock import patch

from petcare.repositories import assistant_repo


class AssistantRepositoryTests(unittest.TestCase):
    def test_shop_context_uses_static_period_sql_and_marks_truncated_catalogs(self):
        connection = object()
        day_start, day_end = "day-start", "day-end"
        week_start, week_end = "week-start", "week-end"
        single_product = {
            "code": "FOOD-1", "name": "Hạt mèo", "category": "Thức ăn",
            "unit_price": 100, "stock_qty": 2, "reorder_level": 3,
        }
        single_pet = {
            "code": "CAT-1", "name": "Miu", "species": "Mèo", "breed": "Mèo ta",
            "coat_color": "vàng", "eye_color": "xanh", "appearance_tags": "",
            "sale_price": 1_000,
        }
        summary_rows = [
            {"total": 4}, {"total": 101}, {"total": 251}, {"total": 7},
            {"total": 1_500},
            {"revenue_week": 12_000, "revenue_month": 99_000},
        ]

        with patch("petcare.repositories.assistant_repo.fetch_one", side_effect=summary_rows) as fetch_one, patch(
            "petcare.repositories.assistant_repo.fetch_all",
            side_effect=[[], [single_product], [single_pet]],
        ):
            context = assistant_repo.shop_context(
                connection, day_start, day_end, {"week": (week_start, week_end)}
            )

        period_query = fetch_one.call_args_list[-1].args[1]
        period_params = fetch_one.call_args_list[-1].args[2]
        self.assertIn("AS revenue_week", period_query)
        self.assertIn("AS revenue_month", period_query)
        self.assertEqual(period_params, (week_start, week_end, day_start, day_end))
        self.assertEqual(context["summary"]["revenue_week"], 12_000)
        self.assertNotIn("revenue_month", context["summary"])
        self.assertEqual(
            context["catalog_preview_truncated"],
            {"products": True, "available_pets": True},
        )


if __name__ == "__main__":
    unittest.main()
