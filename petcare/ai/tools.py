"""Allowlisted, read-only Python Tool Registry with server-side RBAC, scope, and tenant isolation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import time
from typing import Any, Callable

from petcare.ai.contracts import (
    AssistantScope,
    PreferenceSlots,
    ToolExecutionTrace,
)
from petcare.ai.knowledge_base import answer_from_knowledge_base
from petcare.ai.recommender_pets import MAX_PET_RECOMMENDATIONS, match_available_pets
from petcare.ai.recommender_products import (
    MAX_COMPARISON_ITEMS,
    MAX_PRODUCT_RECOMMENDATIONS,
    build_product_comparison,
    recommend_products,
)
from petcare.database.connection import read_connection
from petcare.repositories import pet_repo, product_repo
from petcare.services import (
    assistant_capabilities,
    assistant_operations_service,
    catalog_service,
    report_service,
    restock_service,
)
from petcare.services.common import require_actor
from petcare.services.exceptions import ForbiddenError, NotFoundError, ValidationError
from petcare.timezones import DEFAULT_TIMEZONE, tenant_today


class ToolPermissionError(ForbiddenError):
    """Raised when an actor or scope is not permitted to invoke a tool."""


class ToolNotAllowedError(ValidationError):
    """Raised when an unknown or unallowlisted tool name is requested."""


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Server-verified identity, tenant, role, and scope for tool execution."""

    user_id: int
    tenant_id: int
    role: str  # "admin" | "staff"
    scope: AssistantScope
    locale: str = "vi"
    currency_code: str = "VND"
    timezone: str = DEFAULT_TIMEZONE


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declarative metadata and access policy for one allowlisted read-only tool."""

    name: str
    description: str
    allowed_scopes: frozenset[AssistantScope]
    required_role: str  # "any" | "admin"
    max_items: int
    handler: Callable[..., tuple[Any, int]]


def _public_pet_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Strip buyer PII and internal fields from a pet record."""
    if row.get("sale_status") != "available":
        raise NotFoundError("Thú cưng hiện không mở bán.")
    return {
        "id": int(row["id"]),
        "code": str(row["code"]),
        "name": str(row["name"]),
        "species": str(row.get("species") or ""),
        "breed": str(row.get("breed") or ""),
        "sex": str(row.get("sex") or "unknown"),
        "birth_date": row["birth_date"].isoformat() if hasattr(row.get("birth_date"), "isoformat") else None,
        "weight_kg": str(row["weight_kg"]) if row.get("weight_kg") is not None else None,
        "coat_color": str(row.get("coat_color") or ""),
        "eye_color": str(row.get("eye_color") or ""),
        "appearance_tags": str(row.get("appearance_tags") or ""),
        "sale_price": str(row["sale_price"]),
        "sale_status": str(row["sale_status"]),
        "photo_filename": row.get("photo_filename"),
    }


def _public_product_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Return verified catalog product fields without internal audit columns."""
    if not row.get("active"):
        raise NotFoundError("Sản phẩm không còn hoạt động.")
    return {
        "id": int(row["id"]),
        "code": str(row["code"]),
        "name": str(row["name"]),
        "category": str(row.get("category") or ""),
        "description": str(row.get("description") or ""),
        "unit_price": str(row["unit_price"]),
        "stock_qty": int(row.get("stock_qty") or 0),
        "photo_filename": row.get("photo_filename"),
    }


def _tool_search_products(actor: ActorContext, *, query: str, limit: int = 12) -> tuple[dict[str, Any], int]:
    capped = max(1, min(int(limit), 12))
    with read_connection() as connection:
        require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        result = catalog_service.lookup(connection, str(query)[:500], "product")
    result["items"] = result["items"][:capped]
    return result, len(result["items"])


def _tool_get_product_details(actor: ActorContext, *, product_id: int) -> tuple[dict[str, Any], int]:
    if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
        raise ValidationError("Mã sản phẩm không hợp lệ.")
    with read_connection() as connection:
        require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        row = product_repo.get_product(connection, product_id)
        if not row:
            raise NotFoundError("Không tìm thấy sản phẩm trong cửa hàng.")
        projected = _public_product_projection(row)
    return projected, 1


def _tool_compare_products(
    actor: ActorContext,
    *,
    explicit_codes: tuple[str, ...] = (),
    session_product_ids: list[int] | None = None,
    slots: PreferenceSlots | None = None,
    count_hint: int = 3,
) -> tuple[tuple[Any, str], int]:
    with read_connection() as connection:
        actor_row = require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        table, summary = build_product_comparison(
            connection,
            explicit_codes=explicit_codes[:MAX_COMPARISON_ITEMS],
            session_product_ids=list(session_product_ids or []),
            slots=slots or PreferenceSlots(),
            count_hint=max(2, min(int(count_hint), MAX_COMPARISON_ITEMS)),
            currency_code=actor_row["default_currency"],
            locale=actor.locale,
        )
    count = len(table.items) if table is not None else 0
    return (table, summary), count


def _tool_search_available_pets(actor: ActorContext, *, query: str, limit: int = 12) -> tuple[dict[str, Any], int]:
    capped = max(1, min(int(limit), 12))
    with read_connection() as connection:
        require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        result = catalog_service.lookup(connection, str(query)[:500], "pet")
    result["items"] = result["items"][:capped]
    return result, len(result["items"])


def _tool_get_pet_public_details(actor: ActorContext, *, pet_id: int) -> tuple[dict[str, Any], int]:
    if isinstance(pet_id, bool) or not isinstance(pet_id, int) or pet_id <= 0:
        raise ValidationError("Mã thú cưng không hợp lệ.")
    with read_connection() as connection:
        require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        rows = pet_repo.list_pets(connection, status="available")
        row = next((r for r in rows if int(r["id"]) == pet_id), None)
        if not row:
            raise NotFoundError("Không tìm thấy hồ sơ thú cưng đang mở bán.")
        projected = _public_pet_projection(row)
    return projected, 1


def _tool_recommend_pets(
    actor: ActorContext,
    *,
    slots: PreferenceSlots,
    top_k: int = MAX_PET_RECOMMENDATIONS,
) -> tuple[Any, int]:
    with read_connection() as connection:
        actor_row = require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        today: date = tenant_today(actor_row["timezone"])
        result = match_available_pets(
            connection,
            slots,
            today=today,
            currency_code=actor_row["default_currency"],
            locale=actor.locale,
            top_k=max(1, min(int(top_k), MAX_PET_RECOMMENDATIONS)),
        )
    return result, len(result.cards)


def _tool_recommend_products(
    actor: ActorContext,
    *,
    slots: PreferenceSlots,
    top_k: int = MAX_PRODUCT_RECOMMENDATIONS,
) -> tuple[Any, int]:
    with read_connection() as connection:
        actor_row = require_actor(connection, actor.user_id, tenant_id=actor.tenant_id)
        result = recommend_products(
            connection,
            slots,
            currency_code=actor_row["default_currency"],
            locale=actor.locale,
            top_k=max(1, min(int(top_k), MAX_PRODUCT_RECOMMENDATIONS)),
        )
    return result, len(result.cards)


def _tool_search_pet_care_knowledge(
    actor: ActorContext,
    *,
    query: str,
    species_hint: str | None = None,
) -> tuple[Any, int]:
    result = answer_from_knowledge_base(
        str(query)[:500],
        species_hint=species_hint,
        locale=actor.locale,
    )
    return result, len(result.citations)


def _tool_get_restock_insights(actor: ActorContext, *, question: str = "restock") -> tuple[dict[str, Any], int]:
    res = assistant_capabilities.answer(
        actor.user_id, question, locale=actor.locale, tenant_id=actor.tenant_id
    )
    if res is None:
        res = assistant_capabilities.answer(
            actor.user_id, "restock", locale=actor.locale, tenant_id=actor.tenant_id
        ) or {"reply": "", "mode": "local"}
    items = (res.get("insight") or {}).get("items") or []
    return res, len(items)


def _tool_get_purchase_status(actor: ActorContext, *, question: str = "purchase order status") -> tuple[dict[str, Any], int]:
    res = assistant_capabilities.answer(
        actor.user_id, question, locale=actor.locale, tenant_id=actor.tenant_id
    )
    if res is None:
        res = assistant_capabilities.answer(
            actor.user_id, "purchase order status", locale=actor.locale, tenant_id=actor.tenant_id
        ) or {"reply": "", "mode": "local"}
    items = (res.get("insight") or {}).get("items") or []
    return res, len(items)


def _tool_get_sales_summary(actor: ActorContext, *, period: str = "7d") -> tuple[dict[str, Any], int]:
    insight = report_service.top_products_for_period(
        actor.user_id, period, tenant_id=actor.tenant_id
    )
    return insight, len(insight.get("items", []))


def _tool_get_inventory_forecast(actor: ActorContext, *, limit: int = 8) -> tuple[dict[str, Any], int]:
    capped = max(1, min(int(limit), 8))
    rows = restock_service.recommendations(actor.user_id, tenant_id=actor.tenant_id)
    ranked = sorted(
        rows,
        key=lambda r: (
            0 if r.get("warning") else 1,
            Decimal(str(r["days_after_incoming"])) if r.get("days_after_incoming") is not None else Decimal("9999"),
            -int(r.get("suggested_qty") or 0),
        ),
    )
    selected = []
    for row in ranked[:capped]:
        rate = row.get("forecast_rate") or row.get("rate")
        days_after = row.get("days_after_incoming") if "days_after_incoming" in row else row.get("days_left")
        selected.append({
            "product_id": int(row["id"]),
            "code": str(row["code"]),
            "name": str(row["name"]),
            "stock_qty": int(row["stock_qty"]),
            "incoming_qty": int(row.get("incoming_qty") or 0),
            "reorder_level": int(row["reorder_level"]),
            "daily_rate": str(Decimal(rate).quantize(Decimal("0.01"))) if rate is not None else None,
            "days_after_incoming": str(Decimal(days_after).quantize(Decimal("0.1"))) if days_after is not None else None,
            "expected_14d_units": int(row.get("expected_units") or 0),
            "suggested_qty": int(row.get("suggested_qty") or 0),
            "data_sufficiency": str(row.get("data_sufficiency") or row.get("basis") or "unknown"),
            "warning": bool(row.get("warning")),
        })
    return {
        "kind": "inventory_forecast",
        "horizon_days": restock_service.TARGET_DAYS,
        "history_window_days": 56,
        "total_evaluated": len(rows),
        "warning_count": sum(1 for r in rows if r.get("warning")),
        "items": selected,
    }, len(selected)


def _tool_get_operations_overview(actor: ActorContext) -> tuple[dict[str, Any], int]:
    res = assistant_operations_service.answer(
        actor.user_id, locale=actor.locale, tenant_id=actor.tenant_id
    )
    insight = res.get("insight") or {}
    count = (
        len((insight.get("purchasing") or {}).get("items") or [])
        + len((insight.get("inventory") or {}).get("items") or [])
        + len((insight.get("sales") or {}).get("items") or [])
    )
    return res, count


_BOTH_SCOPES = frozenset({AssistantScope.WORKSPACE, AssistantScope.SHOPPER_PREVIEW})
_WORKSPACE_ONLY = frozenset({AssistantScope.WORKSPACE})

TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_products": ToolSpec(
        name="search_products",
        description="Search active tenant catalog products with verified SQL filters.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=12,
        handler=_tool_search_products,
    ),
    "get_product_details": ToolSpec(
        name="get_product_details",
        description="Read verified public details of a single active catalog product.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=1,
        handler=_tool_get_product_details,
    ),
    "compare_products": ToolSpec(
        name="compare_products",
        description="Build a side-by-side comparison matrix for 2–4 active catalog products.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=MAX_COMPARISON_ITEMS,
        handler=_tool_compare_products,
    ),
    "search_available_pets": ToolSpec(
        name="search_available_pets",
        description="Search available tenant pet profiles without buyer PII.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=12,
        handler=_tool_search_available_pets,
    ),
    "get_pet_public_details": ToolSpec(
        name="get_pet_public_details",
        description="Read verified public attributes of a single available pet profile.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=1,
        handler=_tool_get_pet_public_details,
    ),
    "recommend_pets": ToolSpec(
        name="recommend_pets",
        description="Run two-stage hard-constraint + transparent preference pet matching.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=MAX_PET_RECOMMENDATIONS,
        handler=_tool_recommend_pets,
    ),
    "recommend_products": ToolSpec(
        name="recommend_products",
        description="Run personalized product ranking with Decimal unit-price normalization.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=MAX_PRODUCT_RECOMMENDATIONS,
        handler=_tool_recommend_products,
    ),
    "search_pet_care_knowledge": ToolSpec(
        name="search_pet_care_knowledge",
        description="Retrieve reviewed dog and cat care articles via Okapi BM25.",
        allowed_scopes=_BOTH_SCOPES,
        required_role="any",
        max_items=3,
        handler=_tool_search_pet_care_knowledge,
    ),
    "get_restock_insights": ToolSpec(
        name="get_restock_insights",
        description="Read internal store restock warnings (workspace staff/admin only).",
        allowed_scopes=_WORKSPACE_ONLY,
        required_role="any",
        max_items=8,
        handler=_tool_get_restock_insights,
    ),
    "get_purchase_status": ToolSpec(
        name="get_purchase_status",
        description="Read internal supplier purchase-order statuses (workspace admin only).",
        allowed_scopes=_WORKSPACE_ONLY,
        required_role="admin",
        max_items=8,
        handler=_tool_get_purchase_status,
    ),
    "get_sales_summary": ToolSpec(
        name="get_sales_summary",
        description="Read internal top-selling product metrics for an authorized period.",
        allowed_scopes=_WORKSPACE_ONLY,
        required_role="any",
        max_items=5,
        handler=_tool_get_sales_summary,
    ),
    "get_inventory_forecast": ToolSpec(
        name="get_inventory_forecast",
        description="Compute 8-week weighted demand forecast and stockout horizon (workspace admin only).",
        allowed_scopes=_WORKSPACE_ONLY,
        required_role="admin",
        max_items=8,
        handler=_tool_get_inventory_forecast,
    ),
    "get_operations_overview": ToolSpec(
        name="get_operations_overview",
        description="Combine purchasing, restock, and 7-day sales attention items (workspace admin only).",
        allowed_scopes=_WORKSPACE_ONLY,
        required_role="admin",
        max_items=15,
        handler=_tool_get_operations_overview,
    ),
}


def execute_tool(
    actor: ActorContext,
    tool_name: str,
    **kwargs: Any,
) -> tuple[Any, ToolExecutionTrace]:
    """Validate allowlist, scope, and RBAC before invoking a read-only Python tool."""
    started = time.perf_counter()
    if "tenant_id" in kwargs or "actor_id" in kwargs:
        raise ValidationError("Tool arguments cannot override server-bound tenant_id or actor_id.")

    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise ToolNotAllowedError(f"Tool '{tool_name}' is not in the allowlisted registry.")

    if actor.scope not in spec.allowed_scopes:
        elapsed = (time.perf_counter() - started) * 1000.0
        trace = ToolExecutionTrace(
            tool_name=tool_name,
            status="denied",
            duration_ms=elapsed,
            result_count=0,
            scope=actor.scope.value,
        )
        raise ToolPermissionError("Chế độ xem thử khách mua không được phép truy cập dữ liệu nội bộ cửa hàng.", trace)

    if spec.required_role == "admin" and actor.role != "admin":
        elapsed = (time.perf_counter() - started) * 1000.0
        trace = ToolExecutionTrace(
            tool_name=tool_name,
            status="denied",
            duration_ms=elapsed,
            result_count=0,
            scope=actor.scope.value,
        )
        raise ToolPermissionError("Tính năng này chỉ dành cho quản trị viên cửa hàng.", trace)

    result, count = spec.handler(actor, **kwargs)
    elapsed = (time.perf_counter() - started) * 1000.0
    trace = ToolExecutionTrace(
        tool_name=tool_name,
        status="ok" if count > 0 else "empty",
        duration_ms=elapsed,
        result_count=int(count),
        scope=actor.scope.value,
    )
    return result, trace
