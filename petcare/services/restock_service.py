"""Explainable, read-only suggestions. No purchase order or stock mutation."""

from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from petcare.analytics.demand_forecast import DemandBucket, estimate_weighted_demand
from petcare.database.connection import read_connection
from petcare.repositories import restock_repo
from petcare.services.common import require_actor
from petcare.timezones import tenant_today, utc_window_for_local_dates

TARGET_DAYS = 14
WARNING_DAYS = 7


def estimate(row):
    item = dict(row)
    stock, level = int(row["stock_qty"]), int(row["reorder_level"])
    sold14, sold30 = int(row["sold_14"]), int(row["sold_30"])
    rate14, rate30 = Decimal(sold14) / 14, Decimal(sold30) / 30

    if "demand_buckets" in row:
        history_days = int(row.get("history_days", 0))
        demand = estimate_weighted_demand(row["demand_buckets"], target_days=TARGET_DAYS)
        forecast_rate = demand.rate_per_day
        incoming = int(row.get("incoming_qty") or 0)
        if incoming < 0:
            raise ValueError("incoming_qty cannot be negative")
        days_left = Decimal(stock) / forecast_rate if forecast_rate else None
        days_after_incoming = (
            Decimal(stock + incoming) / forecast_rate if forecast_rate else None
        )
        target = max(level + 1, demand.expected_units)
        quantity = max(0, target - stock - incoming)
        if history_days >= 42:
            sufficiency = "sufficient"
        elif history_days >= 21:
            sufficiency = "limited"
        elif history_days:
            sufficiency = "sparse"
        else:
            sufficiency = "no_history"
        if forecast_rate is None and history_days:
            sufficiency = "no_sales"
        warning = (
            stock + incoming <= level
            or (days_after_incoming is not None and days_after_incoming <= WARNING_DAYS)
        )
        item.update(
            rate_14=rate14,
            rate_30=rate30,
            rate=forecast_rate,
            forecast_rate=forecast_rate,
            window=56,
            days_left=days_left,
            days_after_incoming=days_after_incoming,
            incoming_qty=incoming,
            suggested_qty=quantity,
            target=target,
            expected_units=demand.expected_units,
            weighted_units=demand.weighted_units,
            weighted_days=demand.weighted_days,
            target_days=TARGET_DAYS,
            warning_days=WARNING_DAYS,
            warning=warning,
            history_days=history_days,
            data_sufficiency=sufficiency,
            basis="forecast" if forecast_rate is not None else "reorder_level",
        )
        return item

    window = 14 if sold14 else (30 if sold30 else None)
    rate = rate14 if window == 14 else rate30
    sold = sold14 if window == 14 else sold30
    days_left = Decimal(stock * window) / sold if window else None
    # Exact integer ceiling avoids Decimal division such as 5/14*14 rounding
    # slightly above five and suggesting one unnecessary unit.
    horizon_units = (sold * TARGET_DAYS + window - 1) // window if window else 0
    target = max(level + 1, horizon_units)
    quantity = max(0, target - stock)
    warning = stock <= level or (days_left is not None and days_left <= WARNING_DAYS)
    item.update(
        rate_14=rate14,
        rate_30=rate30,
        rate=rate,
        window=window,
        days_left=days_left,
        suggested_qty=quantity,
        target=target,
        target_days=TARGET_DAYS,
        warning_days=WARNING_DAYS,
        warning=warning,
        basis="sales" if window else "reorder_level",
    )
    return item


def for_connection(connection, actor):
    today = tenant_today(actor["timezone"])
    history_start_date = today - timedelta(days=55)
    history_start, end = utc_window_for_local_dates(
        history_start_date, today + timedelta(days=1), actor["timezone"]
    )
    start30, end = utc_window_for_local_dates(
        today - timedelta(days=29), today + timedelta(days=1), actor["timezone"]
    )
    start14, _ = utc_window_for_local_dates(
        today - timedelta(days=13), today + timedelta(days=1), actor["timezone"]
    )
    weekly_windows = []
    for index in range(8):
        week_start = history_start_date + timedelta(days=index * 7)
        weekly_windows.append(
            utc_window_for_local_dates(
                week_start, week_start + timedelta(days=7), actor["timezone"]
            )
        )
    rows = restock_repo.sales_inventory(
        connection,
        start30,
        start14,
        end,
        history_start=history_start,
        weekly_windows=weekly_windows,
    )
    zone = ZoneInfo(actor["timezone"])
    result = []
    for row in rows:
        item = dict(row)
        created_at = item.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = None
        if isinstance(created_at, datetime):
            created_utc = (
                created_at.replace(tzinfo=datetime_timezone.utc)
                if created_at.tzinfo is None
                else created_at.astimezone(datetime_timezone.utc)
            )
            created_day = created_utc.astimezone(zone).date()
        else:
            # Unknown creation time is treated as the full queried interval,
            # while the UI still reports the exact covered days as an estimate.
            created_day = history_start_date

        buckets = []
        for index in range(8):
            bucket_start = history_start_date + timedelta(days=index * 7)
            bucket_end = min(bucket_start + timedelta(days=7), today + timedelta(days=1))
            observed_start = max(bucket_start, created_day)
            observed_days = max(0, (bucket_end - observed_start).days)
            buckets.append(
                DemandBucket(
                    net_units=int(item.get(f"week_{index}") or 0),
                    days_observed=min(7, observed_days),
                )
            )
        item["demand_buckets"] = tuple(buckets)
        item["history_days"] = sum(bucket.days_observed for bucket in buckets)
        result.append(estimate(item))
    return sorted(
        result,
        key=lambda item: (
            not item["warning"],
            item["days_left"] if item["days_left"] is not None else Decimal("Infinity"),
            item["name"],
        ),
    )


def recommendations(actor_id, tenant_id=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, tenant_id=tenant_id)
        return for_connection(connection, actor)
