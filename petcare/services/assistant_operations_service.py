"""Admin-only, read-only overview composed from existing business services."""

from __future__ import annotations

from decimal import Decimal

from flask import current_app

from petcare.services import purchase_service, report_service, restock_service
from petcare.services.exceptions import ForbiddenError


MAX_ITEMS = 5
PURCHASE_STATUSES = ("ordered", "partially_received")


def _unavailable(locale: str) -> dict:
    vi = "Chưa thể đọc tổng quan cửa hàng lúc này. Hãy thử lại sau."
    en = "The store overview is unavailable right now. Please try again."
    return {"reply": en if locale == "en" else vi, "mode": "local", "status": "unavailable"}


def _forbidden(locale: str) -> dict:
    vi = "Tổng quan vận hành chỉ dành cho quản trị viên cửa hàng."
    en = "The operations overview is available to store administrators only."
    return {"reply": en if locale == "en" else vi, "mode": "local", "status": "forbidden"}


def _serialize_order(row: dict) -> dict:
    created = row.get("created_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat(sep=" ", timespec="minutes") if hasattr(created, "hour") else created.isoformat()
    return {
        "purchase_order_id": int(row["id"]),
        "supplier_name": str(row["supplier_name_snapshot"]),
        "status": str(row["status"]),
        "created_at": str(created or ""),
        "item_count": int(row["item_count"]),
        "ordered_units": int(row["ordered_units"]),
        "received_units": int(row["received_units"]),
    }


def _overview_reply(insight: dict, locale: str, partial: bool) -> str:
    inventory = insight.get("inventory")
    purchasing = insight["purchasing"]
    sales = insight.get("sales")
    if locale == "en":
        parts = []
        if inventory and inventory.get("status") == "available":
            parts.append(f"{inventory['total']} products meet the current restock warning rules")
        else:
            parts.append("inventory warnings could not be loaded")
        parts.append(f"{purchasing['open_total']} purchase orders are ordered or partially received")
        if sales and sales.get("status") == "available":
            parts.append(f"sales context covers {sales['start_date']} to {sales['end_date']}")
        else:
            parts.append("the recent sales report could not be loaded")
        suffix = " Some sources are temporarily unavailable." if partial else ""
        return "Store overview: " + "; ".join(parts) + "." + suffix

    parts = []
    if inventory and inventory.get("status") == "available":
        parts.append(f"{inventory['total']} sản phẩm đạt quy tắc cảnh báo nhập hàng hiện tại")
    else:
        parts.append("chưa tải được cảnh báo tồn kho")
    parts.append(f"{purchasing['open_total']} đơn đang đặt hoặc nhận một phần")
    if sales and sales.get("status") == "available":
        parts.append(f"ngữ cảnh bán hàng từ {sales['start_date']} đến {sales['end_date']}")
    else:
        parts.append("chưa tải được báo cáo bán hàng gần đây")
    suffix = " Một số nguồn dữ liệu tạm thời chưa truy cập được." if partial else ""
    return "Tổng quan cửa hàng: " + "; ".join(parts) + "." + suffix


def answer(actor_id: int, locale: str = "vi", tenant_id: int | None = None) -> dict:
    """Aggregate bounded operational context without writing or using a provider.

    Purchase service authorization is checked first. No inventory or report data
    is returned to staff, even if a later read succeeds after an authorization
    denial. Each service retains its own tenant and role checks.
    """
    try:
        listings = {
            status: purchase_service.list_purchase_orders(
                actor_id, status=status, page="1", tenant_id=tenant_id
            )
            for status in PURCHASE_STATUSES
        }
    except ForbiddenError:
        return _forbidden(locale)
    except Exception as exc:
        current_app.logger.error("Assistant operations overview authorization/read failed (%s)", type(exc).__name__)
        return _unavailable(locale)

    status_counts = {
        status: int(listings[status]["pagination"]["total"])
        for status in PURCHASE_STATUSES
    }
    orders = [row for result in listings.values() for row in result["items"]]
    orders.sort(key=lambda row: (row.get("created_at"), int(row["id"])), reverse=True)
    purchasing = {
        "status": "available",
        "open_total": sum(status_counts.values()),
        "status_counts": status_counts,
        "items": [_serialize_order(row) for row in orders[:MAX_ITEMS]],
    }

    insight = {"kind": "operations_overview", "purchasing": purchasing}
    partial = False

    try:
        recommendations = restock_service.recommendations(actor_id, tenant_id=tenant_id)
        warnings = [row for row in recommendations if row["warning"]]
        insight["inventory"] = {
            "status": "available",
            "total": len(warnings),
            "target_days": restock_service.TARGET_DAYS,
            "warning_days": restock_service.WARNING_DAYS,
            "items": [
                {
                    "product_id": int(row["id"]),
                    "name": str(row["name"]),
                    "code": str(row["code"]),
                    "stock_qty": int(row["stock_qty"]),
                    "reorder_level": int(row["reorder_level"]),
                    "suggested_qty": int(row["suggested_qty"]),
                    "days_left": (
                        str(Decimal(row["days_left"]).quantize(Decimal("0.1")))
                        if row["days_left"] is not None else None
                    ),
                    "basis": str(row["basis"]),
                }
                for row in warnings[:MAX_ITEMS]
            ],
        }
    except ForbiddenError:
        return _forbidden(locale)
    except Exception as exc:
        current_app.logger.error("Assistant operations inventory read failed (%s)", type(exc).__name__)
        insight["inventory"] = {"status": "unavailable"}
        partial = True

    try:
        report = report_service.top_products_for_period(
            actor_id, "7d", tenant_id=tenant_id
        )
        insight["sales"] = {
            "status": "available",
            "period": report["period"],
            "start_date": report["start_date"].isoformat(),
            "end_date": report["end_date"].isoformat(),
            "currency_code": str(report["currency_code"]),
            "items": [
                {
                    "product_id": int(row["product_id"]),
                    "name": str(row["name"]),
                    "code": str(row["code"]),
                    "quantity_sold": int(row["quantity_sold"]),
                    "revenue": str(row["revenue"]),
                }
                for row in report["items"][:MAX_ITEMS]
            ],
        }
    except ForbiddenError:
        return _forbidden(locale)
    except Exception as exc:
        current_app.logger.error("Assistant operations sales read failed (%s)", type(exc).__name__)
        insight["sales"] = {"status": "unavailable"}
        partial = True

    return {
        "reply": _overview_reply(insight, locale, partial),
        "mode": "local",
        "status": "partial" if partial else "ok",
        "insight": insight,
    }
