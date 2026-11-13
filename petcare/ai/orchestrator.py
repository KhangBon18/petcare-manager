"""Central PetCare AI Orchestrator: NLU -> Memory -> Safety/RBAC -> Tool Registry -> Composition."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from petcare.ai.contracts import (
    AssistantScope,
    AssistantTurnResponse,
    EngineMode,
    PreferenceSlots,
    RecommendationCard,
    ResponseType,
    SafetyNotice,
)
from petcare.ai.knowledge_base import (
    build_emergency_triage_response,
    build_medical_boundary_response,
)
from petcare.ai.memory import MEMORY_STORE, SessionState, sanitize_conversation_id
from petcare.ai.nlu import (
    InterpretedTurn,
    extract_preference_slots,
    interpret_turn,
    merge_preference_slots,
)
from petcare.ai.provider import get_provider_status, synthesize_approved_llm_reply
from petcare.ai.recommender_pets import localize_clarification, needs_pet_clarification
from petcare.ai.recommender_products import needs_product_clarification
from petcare.ai.tools import ActorContext, ToolPermissionError, execute_tool
from petcare.database.connection import read_connection
from petcare.services import assistant_capabilities
from petcare.services.catalog_intent import _normalize, _question_intent
from petcare.services.common import require_actor
from petcare.services.exceptions import ForbiddenError
from petcare.timezones import DEFAULT_TIMEZONE


def _fmt_price(amount: Decimal, currency_code: str, locale: str) -> str:
    rounded = int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    num = f"{rounded:,}"
    if locale != "en":
        num = num.replace(",", ".")
    return f"{num}\u00a0{currency_code}"


def _cards_to_legacy_catalog(cards: list[RecommendationCard]) -> dict[str, Any] | None:
    """Populate backward-compatible `catalog` list so both full workspace and mini widget navigate cleanly."""
    if not cards:
        return None
    kind = cards[0].kind
    items = []
    for card in cards:
        items.append({
            "kind": card.kind,
            "id": card.entity_id,
            "code": card.code,
            "name": card.name,
            "price": str(card.price),
            "status": "available" if card.kind == "pet" else ("active" if (card.stock_qty or 0) > 0 else "inactive"),
            "stock": card.stock_qty,
            "photo_filename": card.photo_filename,
        })
    return {"kind": kind, "total": len(items), "items": items}


def _hydrate_slots_from_history(history: Any) -> tuple[PreferenceSlots, bool]:
    """Reconstruct session preference slots from stateless client history when no conversation_id is supplied."""
    slots = PreferenceSlots()
    had_user_turns = False
    if not isinstance(history, list):
        return slots, False
    for entry in history[-6:]:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "user":
            had_user_turns = True
            upd, exp_sp, exp_bg = extract_preference_slots(content)
            domain = "product" if upd.product_category else ("pet" if upd.species and not slots.active_domain else slots.active_domain)
            slots = merge_preference_slots(
                slots,
                upd,
                target_domain=domain,
                explicit_species_override=exp_sp,
                explicit_budget_override=exp_bg,
            )
        elif role == "assistant":
            norm_a = _normalize(content)
            if any(p in norm_a for p in ("calm or active", "hien/it van dong hay nang dong", "what is your budget", "ngan sach du kien")):
                slots.awaiting_clarification_for = slots.active_domain or "pet"
    return slots, had_user_turns


def _resolve_actor_context(
    actor_id: int,
    tenant_id: int | None,
    scope: AssistantScope,
    locale: str,
) -> ActorContext:
    with read_connection() as connection:
        actor_row = require_actor(connection, actor_id, tenant_id=tenant_id)
    resolved_tenant = int(tenant_id if tenant_id is not None else actor_row.get("tenant_id") or 1)
    return ActorContext(
        user_id=int(actor_id),
        tenant_id=resolved_tenant,
        role=str(actor_row.get("role") or "staff"),
        scope=scope,
        locale=locale,
        currency_code=str(actor_row.get("default_currency") or "VND"),
        timezone=str(actor_row.get("timezone") or DEFAULT_TIMEZONE),
    )


def _safety_refusal_response(
    trigger: str,
    locale: str,
    scope: AssistantScope,
    conv_id: str | None,
    slots: PreferenceSlots,
) -> AssistantTurnResponse:
    vi = locale != "en"
    if trigger == "prompt_injection":
        notice = SafetyNotice(
            severity="policy_boundary",
            title="Chặn truy xuất chỉ dẫn nội bộ / khóa bí mật" if vi else "Prompt & Credential Boundary",
            message=(
                "PetCare AI không tiết lộ system prompt, khóa API, mật khẩu cơ sở dữ liệu hoặc bỏ qua quy tắc phân quyền."
                if vi else
                "PetCare AI never discloses system prompts, API keys, database credentials, or bypasses authorization policies."
            ),
        )
        reply = (
            "Tôi không thể tiết lộ chỉ dẫn hệ thống, khóa cấu hình hay bỏ qua quy tắc bảo mật. "
            "Tôi có thể hỗ trợ bạn tìm thú cưng đang bán, gợi ý/so sánh sản phẩm hoặc tra cứu kiến thức chăm sóc chó mèo."
            if vi else
            "I cannot reveal internal instructions, configuration secrets, or bypass security rules. "
            "I can help you match available pets, recommend or compare products, or look up reviewed pet-care guidance."
        )
    elif trigger == "sql_or_code":
        notice = SafetyNotice(
            severity="policy_boundary",
            title="Không sinh SQL hoặc thực thi mã tùy ý" if vi else "No Model-Generated SQL or Code Execution",
            message=(
                "Mọi truy vấn dữ liệu trong PetCare AI chỉ chạy qua các hàm Python chỉ-đọc (read-only tools) đã được định sẵn và kiểm soát quyền."
                if vi else
                "PetCare AI never generates SQL or executes arbitrary code; all lookups use pre-approved read-only Python services."
            ),
        )
        reply = (
            "Vì lý do an toàn dữ liệu, trợ lý không sinh câu lệnh SQL và không thực thi mã lệnh trực tiếp. "
            "Hãy cho biết nhu cầu tìm kiếm bằng ngôn ngữ tự nhiên (ví dụ: 'Gợi ý thức ăn mèo trưởng thành dưới 350k')."
            if vi else
            "For security reasons, PetCare AI does not generate SQL queries or execute code. "
            "Please ask in natural language (for example: 'Recommend adult cat food under 350,000 VND')."
        )
    else:
        # write_action — Human-in-the-Loop approval guardrail
        notice = SafetyNotice(
            severity="policy_boundary",
            title="Yêu cầu thao tác ghi cần xác nhận trực tiếp của con người" if vi else "Human Confirmation Required for Store Actions",
            message=(
                "PetCare AI hoạt động ở chế độ tư vấn chỉ-đọc (read-only): không tự động lập hóa đơn, đặt đơn hàng, hoàn tiền hoặc chỉnh sửa tồn kho."
                if vi else
                "PetCare AI operates strictly in read-only advisory mode and never creates invoices, places orders, processes refunds, or mutates inventory automatically."
            ),
        )
        reply = (
            "Trợ lý AI không tự động tạo hóa đơn, chốt đơn mua, hoàn tiền hay sửa tồn kho để đảm bảo kiểm soát vận hành (Human-in-the-Loop). "
            "Vui lòng mở mục **Hóa đơn (POS)**, **Nhập hàng** hoặc **Sản phẩm** trên thanh điều hướng để kiểm tra và xác nhận thao tác trực tiếp."
            if vi else
            "To preserve human-in-the-loop operational safety, PetCare AI does not automatically create sales, place orders, issue refunds, or alter stock. "
            "Please use the **Invoices (POS)**, **Purchasing**, or **Products** screen to review and confirm changes manually."
        )

    return AssistantTurnResponse(
        reply=reply,
        response_type=ResponseType.UNSUPPORTED_REQUEST,
        mode="local",
        engine_mode=EngineMode.OFFLINE,
        scope=scope,
        status="clarification",
        conversation_id=conv_id,
        safety_notice=notice,
        context_state=slots.to_public_dict(locale),
        follow_up_questions=(
            ["Gợi ý mèo hợp căn hộ dưới 7 triệu", "Gợi ý thức ăn cho mèo trưởng thành", "Cách chuẩn bị căn hộ khi đón thú cưng"]
            if vi else
            ["Recommend a calm apartment cat under 7 million VND", "Which food should I consider for my adult cat?", "How to prepare my apartment for a pet"]
        ),
    )


def _compose_pet_reply(
    cards: list[RecommendationCard],
    total_passed: int,
    locale: str,
) -> str:
    vi = locale != "en"
    if not cards:
        return (
            "Hiện chưa có hồ sơ thú cưng đang mở bán nào thỏa mãn đồng thời tất cả ràng buộc cứng bạn chọn "
            "(loài, trạng thái sẵn sàng và trần ngân sách). Bạn có thể nới ngân sách hoặc bỏ bớt tiêu chí lọc để xem thêm."
            if vi else
            "No currently available pet profile satisfies all active hard constraints simultaneously "
            "(species, availability, and budget ceiling). Try widening your budget or relaxing a trait filter."
        )
    lines = [
        (
            f"Tìm thấy **{total_passed}** hồ sơ thú cưng đang mở bán phù hợp ràng buộc cứng; dưới đây là **Top {len(cards)}** gợi ý có giải thích điểm:"
            if vi else
            f"Found **{total_passed}** available pet profiles matching your hard constraints; here are the **Top {len(cards)}** explainable matches:"
        )
    ]
    for idx, card in enumerate(cards, start=1):
        price_str = _fmt_price(card.price, card.currency_code, locale)
        reason_str = card.reasons[0] if card.reasons else ""
        warn_str = f" ⚠ {card.warnings[0]}" if card.warnings else ""
        lines.append(
            f"{idx}. {card.name} ({card.code}) — {card.subtitle} · {price_str} · Điểm phù hợp {card.score}/100. {reason_str}{warn_str}"
            if vi else
            f"{idx}. {card.name} ({card.code}) — {card.subtitle} · {price_str} · Fit score {card.score}/100. {reason_str}{warn_str}"
        )
    return "\n".join(lines)


def _compose_product_reply(
    cards: list[RecommendationCard],
    no_primary_match: bool,
    out_of_stock_names: list[str],
    locale: str,
) -> str:
    vi = locale != "en"
    if no_primary_match:
        if out_of_stock_names:
            oos = ", ".join(out_of_stock_names[:3])
            lead = (
                f"Sản phẩm khớp trực tiếp hiện đã tạm hết hàng ({oos})."
                if vi else f"Directly matching products are currently out of stock ({oos})."
            )
        else:
            lead = (
                "Danh mục hiện chưa có sản phẩm còn hàng khớp chính xác với nhóm sản phẩm và loài bạn yêu cầu "
                "(trợ lý không gợi ý sai sản phẩm của loài khác)."
                if vi else
                "No in-stock product in our catalog directly matches both the requested category and species "
                "(products meant for other species are excluded)."
            )
        if not cards:
            return lead + (
                " Hãy thử nới ngân sách hoặc chọn danh mục khác."
                if vi else " Try adjusting your budget or category."
            )
        alt_header = (
            "\nMột số sản phẩm **thay thế lân cận đang còn hàng** cho cùng loài trong ngân sách để bạn tham khảo:"
            if vi else
            "\nHere are **in-stock adjacent alternatives** verified for the same species within your budget:"
        )
        lines = [lead + alt_header]
        for idx, card in enumerate(cards, start=1):
            p_str = _fmt_price(card.price, card.currency_code, locale)
            u_str = f" ({card.unit_price_display})" if card.unit_price_display else ""
            lines.append(
                f"{idx}. [Thay thế] {card.name} ({card.code}) — {p_str}{u_str} · Tồn: {card.stock_qty}"
                if vi else
                f"{idx}. [Alternative] {card.name} ({card.code}) — {p_str}{u_str} · Stock: {card.stock_qty}"
            )
        return "\n".join(lines)

    lines = [
        (
            f"Dưới đây là **Top {len(cards)} sản phẩm đang còn hàng** được xếp hạng theo mức độ phù hợp và đơn giá quy đổi:"
            if vi else
            f"Here are the **Top {len(cards)} in-stock products** ranked by verified compatibility and normalized unit value:"
        )
    ]
    for idx, card in enumerate(cards, start=1):
        p_str = _fmt_price(card.price, card.currency_code, locale)
        u_str = f" · {card.unit_price_display}" if card.unit_price_display else ""
        r_str = card.reasons[0] if card.reasons else ""
        lines.append(
            f"{idx}. {card.name} ({card.code}) — {p_str}{u_str} · Còn {card.stock_qty} · Điểm {card.score}/100. {r_str}"
            if vi else
            f"{idx}. {card.name} ({card.code}) — {p_str}{u_str} · {card.stock_qty} in stock · Score {card.score}/100. {r_str}"
        )
    return "\n".join(lines)


def try_orchestrate_turn(
    actor_id: int,
    question: str,
    *,
    history: Any = None,
    locale: str = "vi",
    tenant_id: int | None = None,
    scope_raw: str | None = None,
    conversation_id_raw: object = None,
) -> dict[str, Any] | None:
    """Handle PetCare AI advisory, comparison, knowledge, forecast, memory, and shopper-scope turns.

    Returns a complete API dict when handled, or `None` when a workspace legacy store query
    should execute through `assistant_service`'s deterministic operational handlers.
    """
    vi = locale != "en"
    scope = (
        AssistantScope.SHOPPER_PREVIEW
        if scope_raw == AssistantScope.SHOPPER_PREVIEW.value
        else AssistantScope.WORKSPACE
    )
    has_persistent_conv = isinstance(conversation_id_raw, str) and bool(conversation_id_raw.strip())
    conv_id = sanitize_conversation_id(conversation_id_raw) if has_persistent_conv else None

    # Load or hydrate current preference slots
    session_state: SessionState | None = None
    if conv_id is not None and tenant_id is not None:
        session_state = MEMORY_STORE.get_or_create(
            tenant_id=int(tenant_id),
            user_id=int(actor_id),
            scope=scope,
            conversation_id=conv_id,
        )
        active_slots = session_state.slots.clone()
        prior_turn_count = session_state.turn_count
    else:
        active_slots, had_turns = _hydrate_slots_from_history(history)
        prior_turn_count = 1 if had_turns else 0

    interpreted: InterpretedTurn = interpret_turn(question, active_slots)

    # 1. Explicit Conversation Reset
    if interpreted.intent == "reset_context":
        if conv_id is not None and tenant_id is not None:
            MEMORY_STORE.reset(
                tenant_id=int(tenant_id),
                user_id=int(actor_id),
                scope=scope,
                conversation_id=conv_id,
            )
        empty_slots = PreferenceSlots()
        reply = (
            "Đã xóa ngữ cảnh ưu tiên của cuộc trò chuyện hiện tại. Bạn muốn tìm thú cưng, gợi ý sản phẩm hay hỏi kiến thức chăm sóc mới?"
            if vi else
            "Cleared your active conversation preferences. Would you like to match pets, get product recommendations, or explore pet-care advice?"
        )
        return AssistantTurnResponse(
            reply=reply,
            response_type=ResponseType.ANSWER,
            scope=scope,
            conversation_id=conv_id,
            context_state=empty_slots.to_public_dict(locale),
            follow_up_questions=(
                ["Tôi muốn nuôi mèo hợp căn hộ", "Gợi ý thức ăn cho mèo trưởng thành", "Cách chuẩn bị nhà đón cún mới"]
                if vi else
                ["I want a cat suitable for an apartment", "Which food should I consider for my adult cat?", "How to prepare home for a puppy"]
            ),
        ).to_api_dict()

    # 2. Safety & Policy Refusals (no DB queries needed!)
    if interpreted.intent == "safety_refusal":
        return _safety_refusal_response(
            interpreted.safety_trigger or "policy",
            locale,
            scope,
            conv_id,
            active_slots,
        ).to_api_dict()

    # 3. Veterinary Emergency & Medical Boundaries
    if interpreted.intent == "vet_emergency":
        kb_res = build_emergency_triage_response(locale)
        return AssistantTurnResponse(
            reply=kb_res.reply,
            response_type=ResponseType.KNOWLEDGE_ANSWER,
            scope=scope,
            conversation_id=conv_id,
            citations=kb_res.citations,
            safety_notice=kb_res.safety_notice,
            context_state=active_slots.to_public_dict(locale),
        ).to_api_dict()

    if interpreted.intent == "vet_medical_boundary":
        kb_res = build_medical_boundary_response(locale)
        return AssistantTurnResponse(
            reply=kb_res.reply,
            response_type=ResponseType.UNSUPPORTED_REQUEST,
            scope=scope,
            status="clarification",
            conversation_id=conv_id,
            citations=kb_res.citations,
            safety_notice=kb_res.safety_notice,
            follow_up_questions=kb_res.follow_up_questions,
            context_state=active_slots.to_public_dict(locale),
        ).to_api_dict()

    # 4. Legacy Store Queries: Enforce strict Shopper Preview boundary or delegate in Workspace
    if interpreted.intent == "legacy_store_query":
        if scope == AssistantScope.WORKSPACE:
            return None

        # In SHOPPER_PREVIEW, block all internal store operations (restock, POs, revenue, sales, customers, low stock)
        norm_q = interpreted.raw_query_normalized
        q_intent = _question_intent(question)
        is_internal_ask = (
            assistant_capabilities.classify(question) is not None
            or q_intent in {"revenue", "stock"}
            or any(
                phrase in norm_q
                for phrase in (
                    "doanh thu", "revenue", "ban chay", "best selling", "best seller",
                    "top selling", "top product", "top item", "most sold", "sold the most",
                    "khach hang", "customer", "hoa don", "invoice", "don nhap", "purchase",
                    "ton kho thap", "low stock", "restock", "tong quan", "overview", "supplier", "nha cung cap",
                )
            )
        )
        if is_internal_ask:
            reply = (
                "Đang ở chế độ **Xem thử khách mua (Shopper Preview)**: doanh thu, báo cáo bán chạy, tồn kho nội bộ, đơn nhập hàng và dữ liệu khách hàng được bảo vệ và không hiển thị cho khách mua."
                if vi else
                "**Shopper Preview** mode restricts internal store revenue, sales rankings, restock alerts, supplier purchase orders, and customer records."
            )
            return AssistantTurnResponse(
                reply=reply,
                response_type=ResponseType.PERMISSION_DENIED,
                scope=scope,
                status="forbidden",
                conversation_id=conv_id,
                context_state=active_slots.to_public_dict(locale),
                follow_up_questions=(
                    ["Gợi ý mèo hợp căn hộ", "Gợi ý thức ăn cho mèo trưởng thành", "Cách chăm sóc lông cho chó mèo"]
                    if vi else
                    ["Recommend a cat for an apartment", "Which food should I consider for my adult cat?", "Basic grooming tips for dogs and cats"]
                ),
            ).to_api_dict()

        # Public catalog browse inside Shopper Preview
        actor = _resolve_actor_context(actor_id, tenant_id, scope, locale)
        if q_intent in {"pet", "product"}:
            tool_name = "search_available_pets" if q_intent == "pet" else "search_products"
            cat_res, trace = execute_tool(actor, tool_name, query=question)
            count = cat_res["total"]
            names = ", ".join(r["name"] for r in cat_res["items"])
            reply = (
                (f"Tìm thấy {count} mục đang mở bán: {names}." if count else "Chưa có mục nào khớp điều kiện lọc.")
                if vi else
                (f"Found {count} available items: {names}." if count else "No available items matched these filters.")
            )
            return AssistantTurnResponse(
                reply=reply,
                response_type=ResponseType.ANSWER,
                scope=scope,
                conversation_id=conv_id,
                currency_code=actor.currency_code,
                catalog=cat_res,
                tool_trace=[trace],
                context_state=active_slots.to_public_dict(locale),
            ).to_api_dict()

        reply = (
            "Xin chào! Ở chế độ Tư vấn khách mua, bạn có thể nhờ gợi ý thú cưng theo lối sống/ngân sách, tư vấn & so sánh sản phẩm, hoặc hỏi kiến thức chăm sóc chó mèo có trích dẫn nguồn."
            if vi else
            "Welcome to PetCare AI Shopper Preview! Ask me to match available pets to your lifestyle/budget, recommend or compare products, or answer pet-care questions with reviewed citations."
        )
        return AssistantTurnResponse(
            reply=reply,
            response_type=ResponseType.ANSWER,
            scope=scope,
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            context_state=active_slots.to_public_dict(locale),
            follow_up_questions=(
                ["Tôi muốn nuôi mèo hợp căn hộ", "Gợi ý thức ăn cho mèo trưởng thành", "So sánh FOOD-001, FOOD-002 và FOOD-006"]
                if vi else
                ["I want a cat suitable for an apartment", "Which food should I consider for my adult cat?", "Compare FOOD-001, FOOD-002, and FOOD-006"]
            ),
        ).to_api_dict()

    # Resolve verified ActorContext for tool execution
    actor = _resolve_actor_context(actor_id, tenant_id, scope, locale)
    if session_state is None and conv_id is not None:
        session_state = MEMORY_STORE.get_or_create(
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            scope=scope,
            conversation_id=conv_id,
        )

    # 5. Inventory 8-Week Weighted Demand Forecast (Admin Workspace Tool)
    if interpreted.intent == "inventory_forecast":
        try:
            forecast_data, trace = execute_tool(actor, "get_inventory_forecast", limit=8)
        except ToolPermissionError as exc:
            denied_trace = exc.args[1] if len(exc.args) > 1 else None
            msg = (
                "Dự báo nhu cầu tồn kho 8 tuần chỉ dành cho quản trị viên trong Không gian cửa hàng."
                if vi else
                "The 8-week weighted inventory demand forecast is restricted to store administrators in Workspace mode."
            )
            return AssistantTurnResponse(
                reply=msg,
                response_type=ResponseType.PERMISSION_DENIED,
                scope=scope,
                status="forbidden",
                conversation_id=conv_id,
                currency_code=actor.currency_code,
                tool_trace=[denied_trace] if denied_trace else [],
                context_state=active_slots.to_public_dict(locale),
            ).to_api_dict()

        items = forecast_data["items"]
        lines = [
            (
                f"Dự báo nhu cầu 8 tuần có trọng số (mục tiêu tồn {forecast_data['horizon_days']} ngày): "
                f"có **{forecast_data['warning_count']}/{forecast_data['total_evaluated']}** mặt hàng cần chú ý nhập bổ sung."
                if vi else
                f"8-week weighted demand forecast ({forecast_data['horizon_days']}-day coverage target): "
                f"**{forecast_data['warning_count']}/{forecast_data['total_evaluated']}** active SKUs trigger restock warnings."
            )
        ]
        for row in items[:5]:
            rate_lbl = f"{row['daily_rate']}/ngày" if (vi and row["daily_rate"]) else (f"{row['daily_rate']}/day" if row["daily_rate"] else ("chưa có lịch sử bán" if vi else "no paid sales"))
            lines.append(
                f"• {row['name']} ({row['code']}): tồn {row['stock_qty']} (+đang về {row['incoming_qty']}), tốc độ {rate_lbl}, gợi ý nhập +{row['suggested_qty']}"
                if vi else
                f"• {row['name']} ({row['code']}): stock {row['stock_qty']} (+incoming {row['incoming_qty']}), velocity {rate_lbl}, suggested +{row['suggested_qty']}"
            )
        return AssistantTurnResponse(
            reply="\n".join(lines),
            response_type=ResponseType.OPERATIONAL_INSIGHT,
            scope=scope,
            status="ok",
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            reasoning_summary=(
                "Tính toán bằng mô hình bình quân gia quyền tuyến tính 8 tuần (estimate_weighted_demand) trên hóa đơn đã thanh toán trừ hàng hoàn kho."
                if vi else
                "Computed via 8-week linearly weighted demand estimation (estimate_weighted_demand) over net paid invoices minus restocked refunds."
            ),
            insight=forecast_data,
            tool_trace=[trace],
            context_state=active_slots.to_public_dict(locale),
        ).to_api_dict()

    # 6. Trusted Pet-Care Knowledge Base Retrieval
    if interpreted.intent == "knowledge_qa":
        merged_slots = merge_preference_slots(
            active_slots,
            interpreted.slot_updates,
            target_domain=active_slots.active_domain,
            explicit_species_override=interpreted.explicit_species_override,
            explicit_budget_override=interpreted.explicit_budget_override,
        )
        kb_res, trace = execute_tool(
            actor,
            "search_pet_care_knowledge",
            query=question,
            species_hint=merged_slots.species,
        )
        if session_state is not None:
            session_state.slots = merged_slots
            session_state.record_turn("user", question)
            session_state.record_turn("assistant", kb_res.reply)

        reply_text, engine_mode = synthesize_approved_llm_reply(
            question=question,
            locale=locale,
            grounded_facts={
                "matched": kb_res.matched,
                "citations": [c.to_dict() for c in kb_res.citations],
                "guidance": kb_res.reply,
            },
            fallback_reply=kb_res.reply,
        )
        return AssistantTurnResponse(
            reply=reply_text,
            response_type=ResponseType.KNOWLEDGE_ANSWER if kb_res.matched else ResponseType.UNSUPPORTED_REQUEST,
            mode="ai" if engine_mode == EngineMode.REAL_LLM else "local",
            engine_mode=engine_mode,
            scope=scope,
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            reasoning_summary=(
                f"Truy xuất BM25 trên kho tri thức đã duyệt ({len(kb_res.citations)} nguồn khớp ngưỡng tin cậy)."
                if vi else
                f"Okapi BM25 retrieval over reviewed pet-care corpus ({len(kb_res.citations)} sources above confidence threshold)."
            ),
            citations=kb_res.citations,
            safety_notice=kb_res.safety_notice,
            follow_up_questions=kb_res.follow_up_questions,
            tool_trace=[trace],
            context_state=merged_slots.to_public_dict(locale),
        ).to_api_dict()

    # 7. Side-by-Side Product Comparison
    if interpreted.intent == "product_comparison":
        merged_slots = merge_preference_slots(
            active_slots,
            interpreted.slot_updates,
            target_domain="product",
            explicit_species_override=interpreted.explicit_species_override,
            explicit_budget_override=interpreted.explicit_budget_override,
        )
        session_prod_ids = session_state.last_recommended_product_ids if session_state else []
        (table, summary_msg), trace = execute_tool(
            actor,
            "compare_products",
            explicit_codes=interpreted.comparison_codes,
            session_product_ids=session_prod_ids,
            slots=merged_slots,
            count_hint=interpreted.comparison_count_hint,
        )
        if session_state is not None:
            session_state.slots = merged_slots
            session_state.record_turn("user", question)
            session_state.record_turn("assistant", summary_msg)

        if table is None:
            return AssistantTurnResponse(
                reply=summary_msg,
                response_type=ResponseType.CLARIFICATION,
                scope=scope,
                status="clarification",
                conversation_id=conv_id,
                currency_code=actor.currency_code,
                follow_up_questions=(
                    ["So sánh FOOD-001, FOOD-002 và FOOD-006", "So sánh CARE-005 và CARE-001", "Gợi ý thức ăn cho mèo trưởng thành"]
                    if vi else
                    ["Compare FOOD-001, FOOD-002, and FOOD-006", "Compare CARE-005 and CARE-001", "Recommend food for an adult cat"]
                ),
                tool_trace=[trace],
                context_state=merged_slots.to_public_dict(locale),
            ).to_api_dict()

        names_str = " vs ".join(item["name"] for item in table.items)
        reply = (
            f"Bảng so sánh chi tiết ({names_str}):\n{summary_msg}"
            if vi else
            f"Side-by-side comparison ({names_str}):\n{summary_msg}"
        )
        return AssistantTurnResponse(
            reply=reply,
            response_type=ResponseType.PRODUCT_COMPARISON,
            scope=scope,
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            reasoning_summary=(
                "Chuẩn hóa đơn giá theo Decimal (VND/kg, VND/100g, VND/L) và đối chiếu trực tiếp dữ liệu tồn kho thực tế."
                if vi else
                "Normalized unit costs with exact Decimal arithmetic and compared verified MySQL stock and metadata."
            ),
            comparison=table,
            missing_data=list(table.missing_notes),
            follow_up_questions=(
                ["Chỉ giữ các sản phẩm dưới 200.000 VND", "Gợi ý thêm phụ kiện ăn uống phù hợp"]
                if vi else
                ["Filter to options under 200,000 VND", "Recommend matching feeding bowls"]
            ),
            tool_trace=[trace],
            context_state=merged_slots.to_public_dict(locale),
        ).to_api_dict()

    # 8. Pet Matching & Adoption/Purchase Advice
    if interpreted.intent == "pet_recommendation":
        merged_slots = merge_preference_slots(
            active_slots,
            interpreted.slot_updates,
            target_domain="pet",
            explicit_species_override=interpreted.explicit_species_override,
            explicit_budget_override=interpreted.explicit_budget_override,
        )
        effective_turn = prior_turn_count + 1
        should_clarify, packed_msg, packed_chips = needs_pet_clarification(merged_slots, effective_turn)
        if should_clarify:
            merged_slots.awaiting_clarification_for = "pet"
            msg, chips = localize_clarification(packed_msg, packed_chips, locale)
            if session_state is not None:
                session_state.slots = merged_slots
                session_state.record_turn("user", question)
                session_state.record_turn("assistant", msg)
            return AssistantTurnResponse(
                reply=msg,
                response_type=ResponseType.CLARIFICATION,
                scope=scope,
                status="clarification",
                conversation_id=conv_id,
                currency_code=actor.currency_code,
                follow_up_questions=chips,
                context_state=merged_slots.to_public_dict(locale),
            ).to_api_dict()

        merged_slots.awaiting_clarification_for = None
        match_res, trace = execute_tool(actor, "recommend_pets", slots=merged_slots)
        fallback_reply = _compose_pet_reply(
            match_res.cards,
            match_res.total_passing_hard_constraints,
            locale,
        )
        reply_text, engine_mode = synthesize_approved_llm_reply(
            question=question,
            locale=locale,
            grounded_facts={
                "preferences": merged_slots.to_public_dict(locale),
                "total_passing_hard_constraints": match_res.total_passing_hard_constraints,
                "top_matches": [c.to_dict() for c in match_res.cards],
            },
            fallback_reply=fallback_reply,
        )
        if session_state is not None:
            session_state.slots = merged_slots
            session_state.last_recommended_pet_ids = [c.entity_id for c in match_res.cards]
            session_state.record_turn("user", question)
            session_state.record_turn("assistant", reply_text)

        return AssistantTurnResponse(
            reply=reply_text,
            response_type=ResponseType.PET_RECOMMENDATIONS,
            mode="ai" if engine_mode == EngineMode.REAL_LLM else "local",
            engine_mode=engine_mode,
            scope=scope,
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            reasoning_summary=match_res.reasoning_summary,
            cards=match_res.cards,
            follow_up_questions=match_res.follow_up_questions,
            missing_data=match_res.missing_data_notes,
            tool_trace=[trace],
            catalog=_cards_to_legacy_catalog(match_res.cards),
            context_state=merged_slots.to_public_dict(locale),
        ).to_api_dict()

    # 9. Personalized Product Recommendations
    merged_slots = merge_preference_slots(
        active_slots,
        interpreted.slot_updates,
        target_domain="product",
        explicit_species_override=interpreted.explicit_species_override,
        explicit_budget_override=interpreted.explicit_budget_override,
    )
    effective_turn = prior_turn_count + 1
    should_clarify, packed_msg, packed_chips = needs_product_clarification(merged_slots, effective_turn)
    if should_clarify:
        merged_slots.awaiting_clarification_for = "product"
        msg, chips = localize_clarification(packed_msg, packed_chips, locale)
        if session_state is not None:
            session_state.slots = merged_slots
            session_state.record_turn("user", question)
            session_state.record_turn("assistant", msg)
        return AssistantTurnResponse(
            reply=msg,
            response_type=ResponseType.CLARIFICATION,
            scope=scope,
            status="clarification",
            conversation_id=conv_id,
            currency_code=actor.currency_code,
            follow_up_questions=chips,
            context_state=merged_slots.to_public_dict(locale),
        ).to_api_dict()

    merged_slots.awaiting_clarification_for = None
    prod_res, trace = execute_tool(actor, "recommend_products", slots=merged_slots)
    fallback_reply = _compose_product_reply(
        prod_res.cards,
        prod_res.no_primary_match,
        prod_res.out_of_stock_names,
        locale,
    )
    reply_text, engine_mode = synthesize_approved_llm_reply(
        question=question,
        locale=locale,
        grounded_facts={
            "preferences": merged_slots.to_public_dict(locale),
            "no_primary_match": prod_res.no_primary_match,
            "out_of_stock_names": prod_res.out_of_stock_names,
            "recommendations": [c.to_dict() for c in prod_res.cards],
        },
        fallback_reply=fallback_reply,
    )
    if session_state is not None:
        session_state.slots = merged_slots
        session_state.last_recommended_product_ids = [c.entity_id for c in prod_res.cards]
        session_state.record_turn("user", question)
        session_state.record_turn("assistant", reply_text)

    return AssistantTurnResponse(
        reply=reply_text,
        response_type=ResponseType.PRODUCT_RECOMMENDATIONS,
        mode="ai" if engine_mode == EngineMode.REAL_LLM else "local",
        engine_mode=engine_mode,
        scope=scope,
        conversation_id=conv_id,
        currency_code=actor.currency_code,
        reasoning_summary=prod_res.reasoning_summary,
        cards=prod_res.cards,
        follow_up_questions=prod_res.follow_up_questions,
        missing_data=prod_res.missing_data_notes,
        tool_trace=[trace],
        catalog=_cards_to_legacy_catalog(prod_res.cards),
        context_state=merged_slots.to_public_dict(locale),
    ).to_api_dict()


def enrich_legacy_response(
    legacy: dict[str, Any],
    *,
    scope_raw: str | None = None,
    conversation_id_raw: object = None,
    locale: str = "vi",
) -> dict[str, Any]:
    """Attach canonical PetCare AI contract metadata onto legacy deterministic responses."""
    enriched = dict(legacy)
    scope = (
        AssistantScope.SHOPPER_PREVIEW.value
        if scope_raw == AssistantScope.SHOPPER_PREVIEW.value
        else AssistantScope.WORKSPACE.value
    )
    enriched.setdefault("scope", scope)
    enriched.setdefault(
        "engine_mode",
        EngineMode.REAL_LLM.value if enriched.get("mode") == "ai" else EngineMode.OFFLINE.value,
    )
    if isinstance(conversation_id_raw, str) and conversation_id_raw.strip():
        enriched.setdefault("conversation_id", sanitize_conversation_id(conversation_id_raw))

    if "response_type" not in enriched:
        status = enriched.get("status")
        if status == "forbidden":
            enriched["response_type"] = ResponseType.PERMISSION_DENIED.value
        elif status == "unavailable":
            enriched["response_type"] = ResponseType.SERVICE_ERROR.value
        elif status == "clarification":
            enriched["response_type"] = ResponseType.CLARIFICATION.value
        elif "insight" in enriched:
            enriched["response_type"] = ResponseType.OPERATIONAL_INSIGHT.value
        else:
            enriched["response_type"] = ResponseType.ANSWER.value
    return enriched


def workspace_bootstrap_metadata(locale: str = "vi", is_admin: bool = False) -> dict[str, Any]:
    """Return provider status and curated categorized starter prompts for the AI workspace."""
    vi = locale != "en"
    provider = get_provider_status()
    categories = [
        {
            "id": "pet_matching",
            "title": "Tìm thú cưng phù hợp" if vi else "Pet Matching Advisor",
            "prompts": (
                [
                    "Tôi muốn nuôi mèo hợp căn hộ",
                    "Gợi ý chó dáng nhỏ, hiền, dưới 8 triệu VND",
                    "Tìm mèo trưởng thành dưới 5 triệu VND",
                ]
                if vi else
                [
                    "I want a cat suitable for an apartment.",
                    "Recommend a calm small dog under 8 million VND.",
                    "Show adult cats below 5 million VND.",
                ]
            ),
        },
        {
            "id": "product_advisor",
            "title": "Gợi ý & So sánh sản phẩm" if vi else "Product Advisor & Comparison",
            "prompts": (
                [
                    "Mèo trưởng thành nên chọn thức ăn nào?",
                    "Nhà mình có mèo 5 kg, những sản phẩm nào phù hợp?",
                    "Gợi ý đồ chơi cho chó dưới 300.000 VND",
                    "So sánh FOOD-001, FOOD-002 và FOOD-006",
                ]
                if vi else
                [
                    "Which food should I consider for my adult cat?",
                    "I have a 5 kg cat; what products are suitable?",
                    "Recommend dog toys under 300,000 VND.",
                    "Compare FOOD-001, FOOD-002, and FOOD-006.",
                ]
            ),
        },
        {
            "id": "care_knowledge",
            "title": "Kiến thức chăm sóc có nguồn duyệt" if vi else "Trusted Pet-Care Knowledge",
            "prompts": (
                [
                    "Cách chuẩn bị căn hộ và khay vệ sinh khi mới đón mèo?",
                    "Nguyên tắc chuyển đổi thức ăn mới trong 7–10 ngày?",
                    "Thực phẩm nào trong nhà gây ngộ độc cho chó mèo?",
                ]
                if vi else
                [
                    "How should I prepare my apartment and litter boxes for a new cat?",
                    "How do I safely transition my pet to new food over 7–10 days?",
                    "Which household foods are toxic to dogs and cats?",
                ]
            ),
        },
    ]
    ops_prompts = (
        ["Gợi ý nhập hàng", "Bán chạy tuần này"]
        if vi else ["Which products need restocking?", "Which products sold the most this week?"]
    )
    if is_admin:
        ops_prompts.extend(
            ["Tổng quan cần chú ý", "Dự báo nhu cầu tồn kho 8 tuần"]
            if vi else ["Give me an overview of what needs attention in my store.", "Show 8-week inventory demand forecast"]
        )
    categories.append({
        "id": "store_operations",
        "title": "Vận hành cửa hàng (Nội bộ)" if vi else "Store Operations (Internal)",
        "workspace_only": True,
        "prompts": ops_prompts,
    })
    return {
        "provider": provider.to_dict(),
        "prompt_categories": categories,
    }
