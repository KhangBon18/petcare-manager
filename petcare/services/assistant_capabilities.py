"""Small registry of deterministic, read-only assistant business capabilities."""

from __future__ import annotations

import re
from decimal import Decimal

from flask import current_app

from petcare.services import purchase_service, restock_service
from petcare.services.exceptions import ForbiddenError
from petcare.services.catalog_intent import _normalize


MAX_ITEMS = 8
PURCHASE_STATUSES = (
    "ordered",
    "partially_received",
    "received",
    "cancelled",
)


def _query_text(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize(question)).strip()


def _inventory_request(query: str) -> bool:
    return any(phrase in query for phrase in (
        "restock", "reorder", "low stock", "inventory insight", "inventory status",
        "inventory risk", "sap het", "ton kho thap", "can nhap hang", "can nhap them",
        "hang can nhap", "goi y nhap", "goi y san pham can nhap", "bo sung ton", "san pham can bo sung",
    ))


def _purchase_request(query: str) -> bool:
    return any(phrase in query for phrase in (
        "purchase order", "purchase orders", "purchase status", "purchase orders status",
        "don nhap", "don mua hang", "phieu nhap",
    ))


# Keep this registry explicit. Each entry states its user-facing scope, access
# boundary and output cap; user text is never used to construct SQL.
CAPABILITY_REGISTRY = {
    "inventory_restock": {
        "recognize": _inventory_request,
        "permission": "authenticated tenant member",
        "max_items": MAX_ITEMS,
    },
    "purchase_status": {
        "recognize": _purchase_request,
        "permission": "tenant administrator",
        "max_items": MAX_ITEMS,
    },
}


def classify(question: str) -> str | None:
    query = _query_text(question)
    matches = [
        kind for kind, capability in CAPABILITY_REGISTRY.items()
        if capability["recognize"](query)
    ]
    if len(matches) > 1:
        return "ambiguous"
    if matches:
        return matches[0]
    return None


def _requested_limit(query: str) -> int | None:
    match = re.search(r"\b(?:show|list|top|display|hien thi|liet ke)\s+(\d{1,6})\b", query)
    if not match:
        return None
    return int(match.group(1))


def _unsupported_range(query: str) -> bool:
    return bool(re.search(
        r"\b(?:last|past|previous)\s+\d+\s+(?:days?|weeks?|months?|years?)\b"
        r"|\b(?:since|between|from)\s+\d{4}\s+\d{1,2}\s+\d{1,2}\b"
        r"|\b20\d{2}\s+\d{1,2}\s+\d{1,2}\b"
        r"|\b(?:today|yesterday|this week|last week|this month|last month|this year|last year|hom nay|hom qua|tuan nay|tuan truoc|thang nay|thang truoc|nam nay|nam truoc)\b"
        r"|\b(?:trong|qua)\s+\d+\s+ngay\b"
        r"|\btu\s+ngay\s+\d{1,2}\s+\d{1,2}(?:\s+\d{2,4})?\b",
        query,
    ))


def _clarification(kind: str, locale: str) -> dict:
    if kind == "ambiguous":
        vi = "Câu hỏi gồm nhiều yêu cầu. Hãy hỏi riêng từng việc để trợ lý trả lời đúng dữ liệu."
        en = "This question combines multiple requests. Please ask about one topic at a time."
    elif kind == "inventory_restock":
        vi = "Gợi ý tồn kho dùng doanh số 14/30 ngày và mục tiêu tồn 14 ngày; trợ lý chưa nhận khoảng ngày tùy chỉnh."
        en = "Inventory suggestions use 14/30-day sales and a 14-day target; custom date ranges are not supported."
    else:
        vi = "Trợ lý chỉ đọc trạng thái đơn nhập hiện tại; hãy hỏi theo trạng thái có sẵn, không theo khoảng ngày tùy chỉnh."
        en = "The assistant reads current purchase-order statuses only; custom date ranges are not supported."
    return {"reply": en if locale == "en" else vi, "mode": "local", "status": "clarification"}


def _unavailable(kind: str, locale: str) -> dict:
    if kind == "inventory_restock":
        vi, en = "Chưa thể đọc dữ liệu tồn kho lúc này. Hãy thử lại sau.", "Inventory data is unavailable right now. Please try again."
    else:
        vi, en = "Chưa thể đọc trạng thái đơn nhập lúc này. Hãy thử lại sau.", "Purchase-order status is unavailable right now. Please try again."
    return {"reply": en if locale == "en" else vi, "mode": "local", "status": "unavailable"}


def _inventory(actor_id: int, tenant_id: int, locale: str, query: str) -> dict:
    requested = _requested_limit(query)
    try:
        recommendations = restock_service.recommendations(actor_id, tenant_id=tenant_id)
    except ForbiddenError:
        message = "Tài khoản không còn quyền truy cập cửa hàng này." if locale != "en" else "Your account no longer has access to this store."
        return {"reply": message, "mode": "local"}
    except Exception as exc:
        current_app.logger.error("Assistant inventory capability failed (%s)", type(exc).__name__)
        return _unavailable("inventory_restock", locale)

    warnings = [row for row in recommendations if row["warning"]]
    items = []
    for row in warnings[:MAX_ITEMS]:
        days_left = row["days_left"]
        items.append({
            "product_id": int(row["id"]),
            "name": str(row["name"]),
            "code": str(row["code"]),
            "stock_qty": int(row["stock_qty"]),
            "reorder_level": int(row["reorder_level"]),
            "sold_14": int(row["sold_14"]),
            "sold_30": int(row["sold_30"]),
            "days_left": str(Decimal(days_left).quantize(Decimal("0.1"))) if days_left is not None else None,
            "suggested_qty": int(row["suggested_qty"]),
            "basis": row["basis"],
        })
    insight = {
        "kind": "inventory_restock",
        "total": len(warnings),
        "target_days": restock_service.TARGET_DAYS,
        "warning_days": restock_service.WARNING_DAYS,
        "items": items,
    }
    if locale == "en":
        lead = f"{len(warnings)} products need attention under the current restock rules."
        cap = f" Showing at most {MAX_ITEMS}." if len(warnings) > MAX_ITEMS or (requested and requested > MAX_ITEMS) else ""
        empty = " No products currently meet the warning rules."
        rows = [
            f"{item['name']} ({item['code']}): stock {item['stock_qty']}, reorder level {item['reorder_level']}, suggested add {item['suggested_qty']}"
            + (f", about {item['days_left']} days left" if item["days_left"] is not None else ", no recent paid sales")
            for item in items
        ]
        reply = lead + ("\n" + "\n".join(rows) if rows else empty) + cap
    else:
        lead = f"Theo quy tắc nhập hiện tại, có {len(warnings)} sản phẩm cần chú ý."
        cap = f" Chỉ hiển thị tối đa {MAX_ITEMS} mục." if len(warnings) > MAX_ITEMS or (requested and requested > MAX_ITEMS) else ""
        empty = " Hiện không có sản phẩm nào đạt ngưỡng cảnh báo."
        rows = [
            f"{item['name']} ({item['code']}): tồn {item['stock_qty']}, ngưỡng {item['reorder_level']}, gợi ý nhập thêm {item['suggested_qty']}"
            + (f", còn khoảng {item['days_left']} ngày" if item["days_left"] is not None else ", chưa có doanh số đã thanh toán gần đây")
            for item in items
        ]
        reply = lead + ("\n" + "\n".join(rows) if rows else empty) + cap
    return {"reply": reply, "mode": "local", "insight": insight}


def _purchase_status_filter(query: str) -> set[str] | None:
    selections = _purchase_status_selections(query)
    if len(selections) > 1:
        return None
    return selections[0] if selections else None


def _purchase_status_selections(query: str) -> list[set[str]]:
    """Find explicit status filters while excluding nested status phrases."""
    text = f" {query} "
    if any(f" {phrase} " in text for phrase in (
        "not fully received", "not completed", "chua nhan du", "chua nhan het"
    )):
        # The current read view cannot reliably translate a negated completion
        # request into a single persisted state; ask before querying.
        return [{"ordered"}, {"received"}]
    partial_phrases = ("partially received", "partial receipt", "nhan mot phan", "nhap mot phan")
    not_received_phrases = ("not received", "awaiting receipt", "chua nhan")
    partial = any(f" {phrase} " in text for phrase in partial_phrases)
    not_received = any(f" {phrase} " in text for phrase in not_received_phrases)
    selections = []

    if partial:
        selections.append({"partially_received"})
        for phrase in partial_phrases:
            text = text.replace(f" {phrase} ", " ")
    if any(f" {phrase} " in text for phrase in ("cancelled", "canceled", "da huy", "don da huy")):
        selections.append({"cancelled"})
    if not_received:
        selections.append({"ordered"})
        for phrase in not_received_phrases:
            text = text.replace(f" {phrase} ", " ")
    if any(f" {phrase} " in text for phrase in (
        "fully received", "received", "complete", "completed", "da nhan", "don da nhan", "hoan tat", "hoan thanh"
    )):
        selections.append({"received"})
    # "ordered" is checked after removing "not received" above, so a negated
    # receipt request never becomes the completed/received state.
    if any(f" {phrase} " in text for phrase in ("ordered", "dang dat")):
        selections.append({"ordered"})
    if any(f" {phrase} " in text for phrase in ("open", "pending", "outstanding", "chua hoan tat", "dang xu ly")):
        selections.append({"ordered", "partially_received"})
    return selections


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
        "total_amount": str(row["total_amount"]),
        "currency_code": str(row["currency_code"]),
    }


def _purchase_status(actor_id: int, tenant_id: int, locale: str, query: str) -> dict:
    requested = _requested_limit(query)
    selected_statuses = _purchase_status_filter(query)
    try:
        listings = {
            status: purchase_service.list_purchase_orders(
                actor_id, status=status, page="1", tenant_id=tenant_id
            )
            for status in PURCHASE_STATUSES
        }
    except ForbiddenError:
        vi = "Trạng thái đơn nhập chỉ dành cho quản trị viên cửa hàng."
        en = "Purchase-order status is available to store administrators only."
        return {"reply": en if locale == "en" else vi, "mode": "local", "status": "forbidden"}
    except Exception as exc:
        current_app.logger.error("Assistant purchase-status capability failed (%s)", type(exc).__name__)
        return _unavailable("purchase_status", locale)

    counts = {status: int(listings[status]["pagination"]["total"]) for status in PURCHASE_STATUSES}
    if selected_statuses is None:
        rows = [row for status in PURCHASE_STATUSES for row in listings[status]["items"]]
    else:
        rows = [row for status in selected_statuses for row in listings[status]["items"]]
    rows.sort(key=lambda row: (row.get("created_at"), int(row["id"])), reverse=True)
    items = [_serialize_order(row) for row in rows[:MAX_ITEMS]]
    selected_total = sum(counts[status] for status in (selected_statuses or set(PURCHASE_STATUSES)))
    insight = {
        "kind": "purchase_status",
        "total": selected_total,
        "status_counts": counts,
        "selected_statuses": sorted(selected_statuses) if selected_statuses else [],
        "items": items,
    }
    cap = requested is not None and requested > MAX_ITEMS
    if locale == "en":
        counts_text = ", ".join(f"{status.replace('_', ' ')} {counts[status]}" for status in PURCHASE_STATUSES)
        lead = f"{selected_total} purchase orders match this view. Status counts: {counts_text}."
        tail = f" Showing at most {MAX_ITEMS}." if cap or selected_total > MAX_ITEMS else ""
        empty = " No matching purchase orders were found."
        rows_text = [
            f"PO #{item['purchase_order_id']} · {item['supplier_name']} · {item['status'].replace('_', ' ')} · {item['received_units']}/{item['ordered_units']} units received"
            for item in items
        ]
    else:
        counts_text = ", ".join(f"{_status_label(status, locale)} {counts[status]}" for status in PURCHASE_STATUSES)
        lead = f"Có {selected_total} đơn nhập trong phạm vi này. Số lượng theo trạng thái: {counts_text}."
        tail = f" Chỉ hiển thị tối đa {MAX_ITEMS}." if cap or selected_total > MAX_ITEMS else ""
        empty = " Không tìm thấy đơn nhập phù hợp."
        rows_text = [
            f"Đơn #{item['purchase_order_id']} · {item['supplier_name']} · {_status_label(item['status'], locale)} · đã nhận {item['received_units']}/{item['ordered_units']} sản phẩm"
            for item in items
        ]
    reply = lead + ("\n" + "\n".join(rows_text) if rows_text else empty) + tail
    return {"reply": reply, "mode": "local", "insight": insight}


def _status_label(status: str, locale: str) -> str:
    labels = {
        "ordered": ("đang đặt", "ordered"),
        "partially_received": ("nhận một phần", "partially received"),
        "received": ("đã nhận", "received"),
        "cancelled": ("đã hủy", "cancelled"),
    }
    vi, en = labels[status]
    return en if locale == "en" else vi


def answer(actor_id: int, question: str, locale: str = "vi", tenant_id: int | None = None) -> dict | None:
    """Return a deterministic response when a registered capability matches."""
    kind = classify(question)
    if kind is None:
        return None
    query = _query_text(question)
    if kind == "ambiguous":
        return _clarification(kind, locale)
    if _unsupported_range(query):
        return _clarification(kind, locale)
    if kind == "inventory_restock":
        return _inventory(actor_id, tenant_id, locale, query)
    if len(_purchase_status_selections(query)) > 1:
        return _clarification("purchase_status", locale)
    return _purchase_status(actor_id, tenant_id, locale, query)
