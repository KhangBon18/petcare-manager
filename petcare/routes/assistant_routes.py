from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from petcare.ai import orchestrator as ai_orchestrator
from petcare.ai.contracts import AssistantScope, PreferenceSlots
from petcare.ai.memory import MEMORY_STORE, sanitize_conversation_id
from petcare.auth import login_required
from petcare.i18n import translate
from petcare.money import format_money
from petcare.services import assistant_service, request_throttle_service
from petcare.services.exceptions import ServiceError
from petcare.timezones import DEFAULT_TIMEZONE, format_tenant_datetime

bp = Blueprint("assistant", __name__, url_prefix="/assistant")


@bp.get("/")
@login_required
def index():
    return redirect(url_for("assistant.workspace"))


@bp.get("/chat")
@login_required
def workspace():
    initial_scope = (
        AssistantScope.SHOPPER_PREVIEW.value
        if request.args.get("scope") == AssistantScope.SHOPPER_PREVIEW.value
        else AssistantScope.WORKSPACE.value
    )
    is_admin = bool(g.user and g.user.get("role") == "admin")
    meta = ai_orchestrator.workspace_bootstrap_metadata(
        locale=g.locale,
        is_admin=is_admin,
    )
    initial_prompt = str(request.args.get("q") or "").strip()[:300]
    return render_template(
        "assistant/chat.html",
        workspace_meta=meta,
        initial_scope=initial_scope,
        initial_conversation_id=sanitize_conversation_id(None),
        initial_prompt=initial_prompt,
    )


@bp.post("/reset")
@login_required
def reset():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error=translate("Nội dung gửi lên chưa hợp lệ.")), 400
    scope = (
        AssistantScope.SHOPPER_PREVIEW
        if payload.get("scope") == AssistantScope.SHOPPER_PREVIEW.value
        else AssistantScope.WORKSPACE
    )
    raw_conv = payload.get("conversation_id")
    conv_id = sanitize_conversation_id(raw_conv) if isinstance(raw_conv, str) and raw_conv.strip() else None
    MEMORY_STORE.reset(
        tenant_id=g.tenant_id,
        user_id=g.user["id"],
        scope=scope,
        conversation_id=conv_id,
    )
    return jsonify(
        ok=True,
        conversation_id=sanitize_conversation_id(None),
        scope=scope.value,
        context_state=PreferenceSlots().to_public_dict(g.locale),
    )


def _format_card_urls_and_money(response: dict, locale_code: str, default_currency: str) -> None:
    currency = response.get("currency_code", default_currency)
    for item in response.get("catalog", {}).get("items", []):
        pet = item["kind"] == "pet"
        item["url"] = (
            url_for("pets.detail", pet_id=item["id"])
            if pet
            else url_for("products.detail", product_id=item["id"])
        )
        item["price_label"] = format_money(item["price"], currency, locale_code)
        item["status_label"] = translate(
            "Đang bán"
            if item["status"] in {"available", "active"}
            else "Đã bán"
            if item["status"] == "sold"
            else "Đã ngừng"
        )
        filename = item.pop("photo_filename", None)
        item["photo_url"] = (
            url_for("pets.photo" if pet else "products.photo", filename=filename)
            if filename
            else None
        )

    for card in response.get("cards", []):
        is_pet = card.get("kind") == "pet"
        entity_id = card.get("id")
        if isinstance(entity_id, int) and not isinstance(entity_id, bool) and entity_id > 0:
            card["url"] = (
                url_for("pets.detail", pet_id=entity_id)
                if is_pet
                else url_for("products.detail", product_id=entity_id)
            )
        else:
            card["url"] = None
        card["price_label"] = format_money(
            card.get("price", 0),
            card.get("currency_code", currency),
            locale_code,
        )
        status = card.get("availability_status")
        card["status_label"] = translate(
            "Đang bán"
            if status in {"available", "active"}
            else ("Tạm hết hàng" if status == "out_of_stock" else "Đã ngừng")
        )
        filename = card.pop("photo_filename", None)
        card["photo_url"] = (
            url_for("pets.photo" if is_pet else "products.photo", filename=filename)
            if filename
            else None
        )

    comparison = response.get("comparison")
    if isinstance(comparison, dict) and isinstance(comparison.get("items"), list):
        for comp_item in comparison["items"]:
            pid = comp_item.get("id")
            comp_item["url"] = (
                url_for("products.detail", product_id=pid)
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
                else None
            )
            comp_item["price_label"] = format_money(
                comp_item.get("price", 0),
                comp_item.get("currency_code", currency),
                locale_code,
            )
            filename = comp_item.pop("photo_filename", None)
            comp_item["photo_url"] = (
                url_for("products.photo", filename=filename) if filename else None
            )


@bp.post("/chat")
@login_required
def chat():
    allowed, retry_after = request_throttle_service.consume_with_ip_limit(
        g.user["id"], request.remote_addr, "assistant"
    )
    if not allowed:
        return (
            jsonify(
                error=translate(
                    "Đã gửi nhiều câu hỏi từ tài khoản hoặc mạng này. Vui lòng thử lại sau."
                )
            ),
            429,
            {"Retry-After": str(retry_after)},
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error=translate("Nội dung gửi lên chưa hợp lệ.")), 400
    if not isinstance(payload.get("message"), str):
        return (
            jsonify(
                error=translate("Nội dung gửi lên chưa hợp lệ."),
                field="message",
                expected="string",
            ),
            400,
        )

    extra_kwargs = {}
    if isinstance(payload.get("scope"), str):
        extra_kwargs["scope"] = payload["scope"]
    if isinstance(payload.get("conversation_id"), str):
        extra_kwargs["conversation_id"] = payload["conversation_id"]

    try:
        response = assistant_service.answer(
            g.user["id"],
            payload.get("message"),
            payload.get("history"),
            locale=g.locale,
            tenant_id=g.tenant_id,
            **extra_kwargs,
        )
    except ServiceError as exc:
        return jsonify(error=translate(str(exc))), 400

    locale_code = "en_US" if g.locale == "en" else "vi_VN"
    default_currency = (g.tenant or {}).get("default_currency", "VND")
    _format_card_urls_and_money(response, locale_code, default_currency)

    insight = response.get("insight")
    if isinstance(insight, dict) and insight.get("kind") == "operations_overview":
        inventory = insight.get("inventory")
        if isinstance(inventory, dict):
            for item in inventory.get("items", []):
                product_id = item.get("product_id")
                item["url"] = (
                    url_for("products.detail", product_id=product_id)
                    if isinstance(product_id, int)
                    and not isinstance(product_id, bool)
                    and product_id > 0
                    else None
                )
        purchasing = insight.get("purchasing")
        if isinstance(purchasing, dict):
            purchasing["url"] = url_for("purchasing.index")
            for item in purchasing.get("items", []):
                order_id = item.get("purchase_order_id")
                item["url"] = (
                    url_for("purchasing.detail", purchase_order_id=order_id)
                    if isinstance(order_id, int)
                    and not isinstance(order_id, bool)
                    and order_id > 0
                    else None
                )
                item["created_at_label"] = format_tenant_datetime(
                    item.get("created_at"),
                    (g.tenant or {}).get("timezone", DEFAULT_TIMEZONE),
                    locale=g.locale,
                )
        sales = insight.get("sales")
        if isinstance(sales, dict) and sales.get("status") == "available":
            sales["url"] = url_for(
                "reports.index", start=sales["start_date"], end=sales["end_date"]
            )
            for item in sales.get("items", []):
                product_id = item.get("product_id")
                item["url"] = (
                    url_for("products.detail", product_id=product_id)
                    if isinstance(product_id, int)
                    and not isinstance(product_id, bool)
                    and product_id > 0
                    else None
                )
                item["revenue_label"] = format_money(
                    item.get("revenue", 0),
                    sales.get("currency_code", default_currency),
                    locale_code,
                )
    elif isinstance(insight, dict) and insight.get("kind") == "top_products":
        for item in insight.get("items", []):
            product_id = item.get("product_id")
            item["url"] = (
                url_for("products.detail", product_id=product_id)
                if isinstance(product_id, int)
                and not isinstance(product_id, bool)
                and product_id > 0
                else None
            )
            item["revenue_label"] = format_money(
                item.get("revenue", 0),
                insight.get("currency_code", default_currency),
                locale_code,
            )
    elif isinstance(insight, dict) and insight.get("kind") in {"inventory_restock", "inventory_forecast"}:
        for item in insight.get("items", []):
            product_id = item.get("product_id")
            item["url"] = (
                url_for("products.detail", product_id=product_id)
                if isinstance(product_id, int)
                and not isinstance(product_id, bool)
                and product_id > 0
                else None
            )
    elif isinstance(insight, dict) and insight.get("kind") == "purchase_status":
        for item in insight.get("items", []):
            order_id = item.get("purchase_order_id")
            item["url"] = (
                url_for("purchasing.detail", purchase_order_id=order_id)
                if isinstance(order_id, int)
                and not isinstance(order_id, bool)
                and order_id > 0
                else None
            )
            item["amount_label"] = format_money(
                item.get("total_amount", 0),
                item.get("currency_code", default_currency),
                locale_code,
            )
            item["created_at_label"] = format_tenant_datetime(
                item.get("created_at"),
                (g.tenant or {}).get("timezone", DEFAULT_TIMEZONE),
                locale=g.locale,
            )
    response["mode"] = response.get("mode", "local")
    return jsonify(response)
