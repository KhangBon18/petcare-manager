"""Explainable, read-only suggestions. No purchase order or stock mutation."""

from datetime import timedelta
from decimal import Decimal
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
    start30, end = utc_window_for_local_dates(
        today - timedelta(days=29), today + timedelta(days=1), actor["timezone"]
    )
    start14, _ = utc_window_for_local_dates(
        today - timedelta(days=13), today + timedelta(days=1), actor["timezone"]
    )
    result = [
        estimate(row)
        for row in restock_repo.sales_inventory(connection, start30, start14, end)
    ]
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
