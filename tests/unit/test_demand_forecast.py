from decimal import Decimal
from datetime import date, datetime
import unittest
from unittest.mock import patch

from petcare.analytics.demand_forecast import (
    DemandBucket,
    ForecastInputError,
    estimate_weighted_demand,
)
from petcare.analytics.demand_evaluation import (
    DemandEvaluationError,
    evaluate_rolling_holdout,
    synthetic_weekly_scenarios,
)
from petcare.services.restock_service import estimate


class WeightedDemandTests(unittest.TestCase):
    def test_constant_demand_is_stable_and_ceil_target_is_explainable(self):
        result = estimate_weighted_demand([DemandBucket(14, 7) for _ in range(8)])
        self.assertEqual(result.rate_per_day, Decimal(2))
        self.assertEqual(result.expected_units, 28)
        self.assertEqual(result.weighted_units, 14 * sum(range(1, 9)))
        self.assertEqual(result.weighted_days, 7 * sum(range(1, 9)))

    def test_newer_week_gets_more_weight_and_zero_sale_days_stay_in_denominator(self):
        result = estimate_weighted_demand(
            [DemandBucket(0, 7) for _ in range(7)] + [DemandBucket(14, 7)]
        )
        self.assertEqual(result.rate_per_day, Decimal(4) / Decimal(9))
        self.assertEqual(result.expected_units, 7)

    def test_partial_week_and_negative_refund_only_net_demand_are_bounded(self):
        result = estimate_weighted_demand(
            [DemandBucket(-4, 7), DemandBucket(3, 2), DemandBucket(0, 0)]
        )
        self.assertEqual(result.rate_per_day, Decimal(6) / Decimal(11))
        self.assertEqual(result.expected_units, 8)
        self.assertEqual(result.observations, 2)

    def test_empty_history_and_zero_demand_do_not_divide_by_zero(self):
        self.assertIsNone(estimate_weighted_demand([]).rate_per_day)
        zero = estimate_weighted_demand([DemandBucket(0, 7) for _ in range(8)])
        self.assertIsNone(zero.rate_per_day)
        self.assertEqual(zero.expected_units, 0)

    def test_rejects_invalid_values_and_resource_horizons(self):
        for buckets, target in (
            ([DemandBucket(True, 7)], 14),
            ([DemandBucket(1, 8)], 14),
            ([DemandBucket(1, 7)], 0),
            ([DemandBucket(1, 7)], 367),
            ([DemandBucket(1, 7)] * 105, 14),
        ):
            with self.subTest(buckets=len(buckets), target=target):
                with self.assertRaises(ForecastInputError):
                    estimate_weighted_demand(buckets, target_days=target)

    def test_restock_recommendation_accounts_for_open_orders_without_mutation(self):
        item = estimate({
            "id": 9,
            "name": "Food",
            "stock_qty": 5,
            "reorder_level": 2,
            "sold_14": 14,
            "sold_30": 30,
            "incoming_qty": 4,
            "history_days": 56,
            "demand_buckets": tuple(DemandBucket(7, 7) for _ in range(8)),
        })
        self.assertEqual(item["forecast_rate"], Decimal(1))
        self.assertEqual(item["days_left"], Decimal(5))
        self.assertEqual(item["days_after_incoming"], Decimal(9))
        self.assertEqual(item["expected_units"], 14)
        self.assertEqual(item["suggested_qty"], 5)
        self.assertEqual(item["data_sufficiency"], "sufficient")
        self.assertEqual(item["incoming_qty"], 4)

    def test_time_ordered_synthetic_holdout_compares_against_simple_baseline(self):
        result = evaluate_rolling_holdout(synthetic_weekly_scenarios(weeks=16))
        self.assertEqual(result["rolling_origins"], 84)
        self.assertIn("stable", result["by_group"])
        self.assertEqual(result["forecast_horizon_days"], 14)
        with self.assertRaises(DemandEvaluationError):
            evaluate_rolling_holdout({"stable": {"one": [1] * 9}})

    def test_repository_windows_and_product_age_use_store_local_dates(self):
        from petcare.services import restock_service

        row = {
            "id": 17,
            "name": "Recent product",
            "stock_qty": 1,
            "reorder_level": 1,
            "sold_14": 0,
            "sold_30": 0,
            "incoming_qty": 0,
            "created_at": datetime(2026, 11, 10, 0, 0),  # UTC-naive DB timestamp
            **{f"week_{index}": 0 for index in range(8)},
            "week_7": 2,
        }
        actor = {"timezone": "Asia/Ho_Chi_Minh"}
        with patch.object(restock_service, "tenant_today", return_value=date(2026, 11, 13)), patch.object(
            restock_service.restock_repo,
            "sales_inventory",
            return_value=[row],
        ) as query:
            result = restock_service.for_connection(object(), actor)[0]
        self.assertEqual(result["history_days"], 4)
        self.assertEqual(result["data_sufficiency"], "sparse")
        self.assertEqual(result["forecast_rate"], Decimal("0.5"))
        self.assertEqual(result["expected_units"], 7)
        weekly_windows = query.call_args.kwargs["weekly_windows"]
        self.assertEqual(len(weekly_windows), 8)
        self.assertEqual(weekly_windows[-1][0], datetime(2026, 11, 6, 17, 0))
        self.assertEqual(weekly_windows[-1][1], datetime(2026, 11, 13, 17, 0))


if __name__ == "__main__":
    unittest.main()
