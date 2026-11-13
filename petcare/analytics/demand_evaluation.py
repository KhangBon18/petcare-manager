"""Time-ordered holdout evaluation for the weighted-demand estimator."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
from statistics import mean
from typing import Mapping, Sequence

from petcare.analytics.demand_forecast import DemandBucket, estimate_weighted_demand


class DemandEvaluationError(ValueError):
    """Raised when an evaluation series is malformed or too short."""


def _mae(errors: list[int]) -> float:
    return round(mean(errors), 6) if errors else 0.0


def evaluate_rolling_holdout(
    series_by_group: Mapping[str, Mapping[str, Sequence[int]]],
    *,
    training_weeks: int = 8,
    horizon_weeks: int = 2,
) -> dict:
    """Compare weighted moving average to an eight-week simple-average baseline.

    Each forecast is made using only observations before its rolling origin;
    the next ``horizon_weeks`` are held out. Series are explicitly synthetic
    or otherwise caller-labeled and should not be used as business evidence.
    """
    if (
        isinstance(training_weeks, bool)
        or not isinstance(training_weeks, int)
        or not 2 <= training_weeks <= 52
        or isinstance(horizon_weeks, bool)
        or not isinstance(horizon_weeks, int)
        or not 1 <= horizon_weeks <= 26
    ):
        raise DemandEvaluationError("training and horizon weeks are outside supported bounds")

    errors: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"weighted": [], "baseline": []}
    )
    total_origins = 0
    for group, products in series_by_group.items():
        if not isinstance(group, str) or not group or not products:
            raise DemandEvaluationError("each demand group needs a name and product series")
        for product_id, raw_series in products.items():
            if not isinstance(product_id, str) or not product_id:
                raise DemandEvaluationError("product IDs must be non-empty strings")
            values = tuple(raw_series)
            if len(values) <= training_weeks + horizon_weeks - 1:
                raise DemandEvaluationError("series is too short for a time-ordered holdout")
            if any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 2_000_000_000
                for value in values
            ):
                raise DemandEvaluationError("weekly demand must be bounded non-negative integers")

            for origin in range(training_weeks, len(values) - horizon_weeks + 1):
                history = values[origin - training_weeks:origin]
                actual = sum(values[origin:origin + horizon_weeks])
                buckets = tuple(DemandBucket(net_units=value, days_observed=7) for value in history)
                weighted = estimate_weighted_demand(
                    buckets, target_days=7 * horizon_weeks
                ).expected_units
                baseline_daily_rate = Decimal(sum(history)) / Decimal(7 * training_weeks)
                baseline = int(
                    (baseline_daily_rate * 7 * horizon_weeks).to_integral_value(
                        rounding=ROUND_CEILING
                    )
                )
                errors[group]["weighted"].append(abs(weighted - actual))
                errors[group]["baseline"].append(abs(baseline - actual))
                total_origins += 1

    if not total_origins:
        raise DemandEvaluationError("no forecast origins were evaluated")
    weighted_all = [error for item in errors.values() for error in item["weighted"]]
    baseline_all = [error for item in errors.values() for error in item["baseline"]]
    return {
        "forecast_horizon_days": 7 * horizon_weeks,
        "training_window_weeks": training_weeks,
        "rolling_origins": total_origins,
        "weighted_moving_average_mae_units": _mae(weighted_all),
        "simple_moving_average_mae_units": _mae(baseline_all),
        "by_group": {
            group: {
                "origins": len(values["weighted"]),
                "weighted_moving_average_mae_units": _mae(values["weighted"]),
                "simple_moving_average_mae_units": _mae(values["baseline"]),
            }
            for group, values in sorted(errors.items())
        },
        "evaluation_scope": "Synthetic time-ordered rolling holdout; not historical store sales.",
    }


def synthetic_weekly_scenarios(*, weeks: int = 52) -> dict[str, dict[str, list[int]]]:
    """Build fixed and transparent demand patterns with no random seed state."""
    if isinstance(weeks, bool) or not isinstance(weeks, int) or not 12 <= weeks <= 104:
        raise DemandEvaluationError("weeks must be from 12 to 104")
    groups: dict[str, dict[str, list[int]]] = {
        "stable": {}, "growing": {}, "declining": {}, "intermittent": {}
    }
    for index in range(3):
        groups["stable"][f"stable-{index + 1}"] = [7 * (index + 1)] * weeks
        groups["growing"][f"growing-{index + 1}"] = [
            7 * (index + 1) + week * (index + 1) for week in range(weeks)
        ]
        groups["declining"][f"declining-{index + 1}"] = [
            max(0, 7 * (weeks - week) * (index + 1)) for week in range(weeks)
        ]
        groups["intermittent"][f"intermittent-{index + 1}"] = [
            7 * (index + 1) * 4 if (week + index) % (4 + index) == 0 else 0
            for week in range(weeks)
        ]
    return groups
