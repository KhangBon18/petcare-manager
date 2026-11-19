"""Explainable weighted-average demand estimates for inventory planning.

The input units are paid product sales minus refunds that physically returned
to stock. Negative net buckets are clipped to zero demand; they never imply
negative consumption. This module is deterministic and has no database or
network dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Iterable


class ForecastInputError(ValueError):
    """Raised when demand observations are malformed or outside safe bounds."""


@dataclass(frozen=True, slots=True)
class DemandBucket:
    """Net units for a historical bucket and the number of observed days."""

    net_units: int
    days_observed: int


@dataclass(frozen=True, slots=True)
class DemandEstimate:
    """Weighted daily rate and integer target for a requested horizon."""

    rate_per_day: Decimal | None
    expected_units: int
    weighted_units: int
    weighted_days: int
    observations: int


def estimate_weighted_demand(
    buckets: Iterable[DemandBucket], *, target_days: int = 14
) -> DemandEstimate:
    """Estimate demand with linearly increasing recency weights.

    The oldest supplied bucket receives weight 1 and the newest receives the
    largest weight. Only observed days contribute to the denominator, so a
    product created part way through a bucket is not treated as unavailable
    stock for the earlier days. Runtime and additional memory are O(n) and O(1)
    respectively, where n is the number of buckets.
    """
    if isinstance(target_days, bool) or not isinstance(target_days, int) or target_days <= 0:
        raise ForecastInputError("target_days must be a positive integer")
    if target_days > 366:
        raise ForecastInputError("target_days exceeds the supported horizon")

    observations = tuple(buckets)
    if len(observations) > 104:
        raise ForecastInputError("at most 104 weekly observations are supported")

    weighted_units = 0
    weighted_days = 0
    usable = 0
    for weight, bucket in enumerate(observations, start=1):
        if not isinstance(bucket, DemandBucket):
            raise ForecastInputError("observations must be DemandBucket values")
        if (
            isinstance(bucket.net_units, bool)
            or not isinstance(bucket.net_units, int)
            or abs(bucket.net_units) > 2_000_000_000
        ):
            raise ForecastInputError("net_units must be a bounded integer")
        if (
            isinstance(bucket.days_observed, bool)
            or not isinstance(bucket.days_observed, int)
            or not 0 <= bucket.days_observed <= 7
        ):
            raise ForecastInputError("days_observed must be an integer from 0 to 7")
        if not bucket.days_observed:
            continue
        usable += 1
        weighted_units += max(0, bucket.net_units) * weight
        weighted_days += bucket.days_observed * weight

    if not weighted_days or not weighted_units:
        return DemandEstimate(None, 0, weighted_units, weighted_days, usable)

    rate = Decimal(weighted_units) / Decimal(weighted_days)
    expected = int(
        (rate * target_days).to_integral_value(rounding=ROUND_CEILING)
    )
    return DemandEstimate(rate, expected, weighted_units, weighted_days, usable)
