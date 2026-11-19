"""Public Customer Storefront AI Shopping Assistant (strictly isolated from internal ERP tools)."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

from flask import url_for

from petcare.ai.contracts import (
    AssistantScope,
    AssistantTurnResponse,
    EngineMode,
    PreferenceSlots,
    ResponseType,
    SafetyNotice,
)
from petcare.ai.knowledge_base import (
    answer_from_knowledge_base,
    build_emergency_triage_response,
    build_medical_boundary_response,
    build_nonurgent_vet_referral_response,
)
from petcare.ai.nlu import interpret_turn
from petcare.ai.provider import get_provider_status, synthesize_approved_llm_reply
from petcare.ai.recommender_pets import localize_clarification, match_available_pets, needs_pet_clarification
from petcare.ai.recommender_products import build_product_comparison, needs_product_clarification, recommend_products
from petcare.database.connection import read_connection, set_tenant_context
from petcare.i18n import translate
from petcare.money import format_money
from petcare.repositories import storefront_repo
from petcare.services.catalog_intent import _normalize
from petcare.services.catalog_visuals import pet_visual, product_visual
from petcare.services.common import text_value
from petcare.timezones import DEFAULT_TIMEZONE, tenant_today


_INTERNAL_BUSINESS_PATTERNS = (
    r"\b(?:revenue|profit|margin|doanh thu|loi nhuan|lai|von|gia nhap|nhap hang|restock|sap het|nguong canh bao|"
    r"purchase order|supplier|nha cung cap|ton kho noi bo|du bao|forecast|nhat ky|audit|hoa don noi bo|"
    r"khach hang cua cua hang|customer list|danh sach khach|report|bao cao)\b",
)


def _asks_internal_store_data(question: str) -> bool:
    norm = _normalize(question)
    return any(re.search(pat, norm) for pat in _INTERNAL_BUSINESS_PATTERNS)


def _format_public_cards(cards: list, currency_code: str, locale: str, reserved_pets: set[int]) -> list[dict[str, Any]]:
    formatted = []
    for card in cards:
        item = card.to_dict() if hasattr(card, "to_dict") else dict(card)
        kind = item.get("kind") or "product"
        entity_id = int(item.get("id") or item.get("entity_id") or 0)
        is_pet = kind == "pet"
        photo_filename = item.get("photo_filename")
        attrs = item.get("verified_attributes") or {}
        vis = (
            pet_visual({
                "code": item.get("code"),
                "species": item.get("species") or attrs.get("species") or "",
                "photo_filename": photo_filename,
            }, public=True)
            if is_pet
            else product_visual({
                "code": item.get("code"),
                "category": item.get("category") or attrs.get("category") or "",
                "photo_filename": photo_filename,
            }, public=True)
        )
        stock = item.get("stock_qty")
        is_reserved = is_pet and entity_id in reserved_pets
        vi = locale != "en"
        status_label = (
            ("Tạm giữ" if vi else "Reserved") if is_reserved
            else ("Đang bán" if vi else "Available") if (is_pet or (stock is None or int(stock) > 0))
            else ("Tạm hết hàng" if vi else "Out of stock")
        )
        formatted.append({
            "kind": kind,
            "id": entity_id,
            "code": item.get("code") or "",
            "name": item.get("name") or "",
            "subtitle": item.get("subtitle") or "",
            "price": str(item.get("price") or "0"),
            "price_label": format_money(Decimal(str(item.get("price") or "0")), currency_code, locale),
            "url": url_for("storefront.pet_detail", pet_id=entity_id) if is_pet else url_for("storefront.product_detail", product_id=entity_id),
            "photo_url": vis["url"],
            "fallback_url": vis["fallback_url"],
            "is_illustrative": vis["is_illustrative"],
            "status_label": status_label,
            "can_add_to_cart": (not is_reserved) and (is_pet or (stock is None or int(stock) > 0)),
            "reasons": list(item.get("reasons") or []),
            "cautions": list(item.get("cautions") or []),
        })
    return formatted


def answer_public_question(
    store: dict,
    question: str,
    *,
    history: list | None = None,
    locale: str = "vi",
    force_offline: bool = False,
) -> dict[str, Any]:
    """Answer shopper queries using only public storefront catalog data and reviewed pet-care docs."""
    clean_question = text_value(question, "Câu hỏi", 1000)
    vi = locale != "en"
    tenant_id = int(store["id"])
    currency = str(store.get("default_currency") or "VND")
    tz = str(store.get("timezone") or DEFAULT_TIMEZONE)

    # Reconstruct slots from bounded turn history
    slots = PreferenceSlots()
    had_turns = False
    if isinstance(history, list):
        from petcare.ai.orchestrator import _hydrate_slots_from_history
        slots, had_turns = _hydrate_slots_from_history(history)
    prior_turn_count = 1 if had_turns else 0

    interpreted = interpret_turn(clean_question, slots)

    if interpreted.intent == "safety_refusal":
        reply = (
            "Tôi không thể tiết lộ cấu hình nội bộ hay thực thi thao tác ngoài phạm vi tư vấn mua sắm. "
            "Tôi có thể gợi ý thú cưng đang mở bán, sản phẩm phù hợp hoặc kiến thức chăm sóc chó mèo."
            if vi else
            "I cannot share internal configuration details or perform restricted actions. "
            "I can help recommend available pets, products, or verified pet-care guidance."
        )
        return {
            "reply": reply,
            "response_type": ResponseType.PERMISSION_DENIED.value,
            "mode": "local",
            "cards": [],
            "citations": [],
            "follow_up_questions": [],
            "safety_notice": {
                "severity": "policy_boundary",
                "title": "Giới hạn an toàn trợ lý mua sắm" if vi else "Shopping assistant policy boundary",
                "message": reply,
            },
        }

    # Explicit boundary against internal business / CRM / supplier / operational queries
    if interpreted.intent in {
        "multi_operational", "inventory_forecast", "ops_restock", "ops_purchase", "ops_sales", "ops_forecast", "ops_overview"
    } or _asks_internal_store_data(clean_question):
        reply = (
            "Trợ lý mua sắm công khai chỉ hỗ trợ thông tin sản phẩm, thú cưng đang mở bán, giá niêm yết và kiến thức chăm sóc thú cưng; "
            "không có quyền truy cập doanh thu, giá nhập, tồn kho nội bộ hay thông tin khách hàng khác."
            if vi else
            "The public shopping assistant only accesses listed pets, active products, public prices, and reviewed care guides; "
            "internal sales revenue, supplier costs, forecasts, and private customer records are strictly restricted."
        )
        return {
            "reply": reply,
            "response_type": ResponseType.PERMISSION_DENIED.value,
            "mode": "local",
            "cards": [],
            "citations": [],
            "follow_up_questions": [
                "Gợi ý mèo phù hợp căn hộ" if vi else "Recommend cats suitable for an apartment",
                "Thức ăn cho mèo trưởng thành dưới 250.000 VND" if vi else "Cat food under 250,000 VND",
            ],
            "safety_notice": {
                "severity": "policy_boundary",
                "title": "Bảo mật dữ liệu cửa hàng" if vi else "Store data isolation",
                "message": reply,
            },
        }

    if interpreted.intent == "vet_emergency":
        kb = build_emergency_triage_response(locale, category=interpreted.safety_category)
        return {
            "reply": kb.reply,
            "response_type": ResponseType.KNOWLEDGE_ANSWER.value,
            "mode": "local",
            "cards": [],
            "citations": [c.to_dict() for c in kb.citations],
            "follow_up_questions": [],
            "safety_notice": kb.safety_notice.to_dict() if kb.safety_notice else None,
        }

    if interpreted.intent == "vet_medical_boundary":
        kb = build_medical_boundary_response(locale, category=interpreted.safety_category)
        return {
            "reply": kb.reply,
            "response_type": ResponseType.KNOWLEDGE_ANSWER.value,
            "mode": "local",
            "cards": [],
            "citations": [c.to_dict() for c in kb.citations],
            "follow_up_questions": [],
            "safety_notice": kb.safety_notice.to_dict() if kb.safety_notice else None,
        }

    if interpreted.intent == "vet_nonurgent_referral":
        kb = build_nonurgent_vet_referral_response(locale)
        return {
            "reply": kb.reply,
            "response_type": ResponseType.KNOWLEDGE_ANSWER.value,
            "mode": "local",
            "cards": [],
            "citations": [c.to_dict() for c in kb.citations],
            "follow_up_questions": [],
            "safety_notice": kb.safety_notice.to_dict() if kb.safety_notice else None,
        }

    if interpreted.intent in {"knowledge_qa", "multi_knowledge_and_shopping"}:
        kb = answer_from_knowledge_base(clean_question, locale=locale)
        reply = kb.reply
        engine_mode = EngineMode.OFFLINE
        if not force_offline:
            reply, engine_mode = synthesize_approved_llm_reply(
                question=clean_question,
                locale=locale,
                grounded_facts={
                    "knowledge_answer": kb.reply,
                    "citations": [c.to_dict() for c in kb.citations],
                },
                fallback_reply=kb.reply,
            )
        return {
            "reply": reply,
            "response_type": ResponseType.KNOWLEDGE_ANSWER.value,
            "mode": "ai" if engine_mode == EngineMode.REAL_LLM else "local",
            "cards": [],
            "citations": [c.to_dict() for c in kb.citations],
            "follow_up_questions": [],
            "safety_notice": kb.safety_notice.to_dict() if kb.safety_notice else None,
        }

    from petcare.ai.orchestrator import _merge_turn_slots

    target_domain = (
        "pet" if interpreted.intent == "pet_recommendation"
        else ("product" if interpreted.intent in {"product_recommendation", "product_comparison"} else slots.active_domain)
    )
    merged = _merge_turn_slots(slots, interpreted, target_domain=target_domain)
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        today = tenant_today(tz)

        if interpreted.intent == "product_comparison":
            table, summary = build_product_comparison(
                connection,
                explicit_codes=interpreted.comparison_codes,
                session_product_ids=[],
                slots=merged,
                count_hint=interpreted.comparison_count_hint,
                currency_code=currency,
                locale=locale,
            )
            cards_raw = []
            if table is not None:
                for p in table.items:
                    if isinstance(p, dict):
                        cards_raw.append({
                            "kind": "product",
                            "entity_id": int(p.get("id") or p.get("entity_id") or 0),
                            "code": p.get("code", ""),
                            "name": p.get("name", ""),
                            "category": p.get("category", ""),
                            "price": p.get("unit_price", p.get("price", 0)),
                            "stock_qty": p.get("stock_qty", 0),
                            "photo_filename": p.get("photo_filename"),
                            "subtitle": p.get("category") or p.get("subtitle") or "",
                            "reasons": [],
                            "cautions": [],
                        })
                    else:
                        cards_raw.append(p)
            return {
                "reply": summary,
                "response_type": ResponseType.PRODUCT_COMPARISON.value,
                "mode": "local",
                "cards": _format_public_cards(cards_raw, currency, locale, set()),
                "comparison_table": table.to_dict() if table else None,
                "citations": [],
                "follow_up_questions": [],
                "safety_notice": None,
            }

        if interpreted.intent == "pet_recommendation" or merged.active_domain == "pet":
            clar = needs_pet_clarification(merged, prior_turn_count=prior_turn_count)
            if clar:
                msg, sugg = localize_clarification(clar, locale)
                return {
                    "reply": msg,
                    "response_type": ResponseType.CLARIFICATION.value,
                    "mode": "local",
                    "cards": [],
                    "citations": [],
                    "follow_up_questions": sugg,
                    "safety_notice": None,
                }
            pet_res = match_available_pets(
                connection,
                merged,
                today=today,
                currency_code=currency,
                locale=locale,
                top_k=5,
            )
            pet_ids = [int(c.entity_id) for c in pet_res.cards if c.kind == "pet"]
            reserved = storefront_repo.locked_pet_ids(connection, pet_ids) if pet_ids else set()
            if pet_res.cards:
                lines = [
                    f"Mình tìm thấy {len(pet_res.cards)} bé phù hợp đang mở bán:"
                    if vi else
                    f"Found {len(pet_res.cards)} matching pets currently available:"
                ]
                for c in pet_res.cards[:3]:
                    lines.append(f"- {c.name} ({c.code}) — {format_money(Decimal(str(c.price)), currency, locale)}")
                fallback_reply = "\n".join(lines)
            else:
                fallback_reply = (
                    "Hiện chưa có thú cưng đang mở bán khớp hoàn toàn tiêu chí bạn nêu. Bạn có thể mở rộng mức giá hoặc xem toàn bộ danh sách thú cưng."
                    if vi else
                    "No available pets currently match every filter. Try widening your budget or browsing the full pet catalog."
                )
            reply, engine_mode = (
                (fallback_reply, EngineMode.OFFLINE)
                if force_offline
                else synthesize_approved_llm_reply(
                    question=clean_question,
                    locale=locale,
                    grounded_facts={"recommendations": [c.to_dict() for c in pet_res.cards]},
                    fallback_reply=fallback_reply,
                )
            )
            return {
                "reply": reply,
                "response_type": ResponseType.PET_RECOMMENDATIONS.value,
                "mode": "ai" if engine_mode == EngineMode.REAL_LLM else "local",
                "cards": _format_public_cards(pet_res.cards, currency, locale, reserved),
                "citations": [],
                "follow_up_questions": pet_res.follow_up_questions,
                "safety_notice": None,
            }

        clar = needs_product_clarification(merged, prior_turn_count=prior_turn_count)
        if clar and not interpreted.comparison_codes:
            msg, sugg = localize_clarification(clar, locale)
            return {
                "reply": msg,
                "response_type": ResponseType.CLARIFICATION.value,
                "mode": "local",
                "cards": [],
                "citations": [],
                "follow_up_questions": sugg,
                "safety_notice": None,
            }
        prod_res = recommend_products(
            connection,
            merged,
            currency_code=currency,
            locale=locale,
            top_k=5,
        )
        if prod_res.cards:
            lines = [
                f"Mình gợi ý {len(prod_res.cards)} sản phẩm phù hợp cho bạn:"
                if vi else
                f"Here are {len(prod_res.cards)} recommended products:"
            ]
            for c in prod_res.cards[:3]:
                lines.append(f"- {c.name} ({c.code}) — {format_money(Decimal(str(c.price)), currency, locale)}")
            fallback_reply = "\n".join(lines)
        else:
            fallback_reply = (
                "Chưa có sản phẩm khớp chính xác tiêu chí lọc. Bạn hãy thử từ khóa khác hoặc xem toàn bộ danh mục sản phẩm."
                if vi else
                "No products matched your exact filters. Try another keyword or browse all products."
            )
        reply, engine_mode = (
            (fallback_reply, EngineMode.OFFLINE)
            if force_offline
            else synthesize_approved_llm_reply(
                question=clean_question,
                locale=locale,
                grounded_facts={"recommendations": [c.to_dict() for c in prod_res.cards]},
                fallback_reply=fallback_reply,
            )
        )
        return {
            "reply": reply,
            "response_type": ResponseType.PRODUCT_RECOMMENDATIONS.value,
            "mode": "ai" if engine_mode == EngineMode.REAL_LLM else "local",
            "cards": _format_public_cards(prod_res.cards, currency, locale, set()),
            "citations": [],
            "follow_up_questions": prod_res.follow_up_questions,
            "safety_notice": None,
        }


def public_assistant_prompts(locale: str = "vi") -> list[str]:
    if locale == "en":
        return [
            "Recommend a calm cat suitable for an apartment",
            "Which adult cat food should I pick?",
            "Compare FOOD-001, FOOD-002 and FOOD-006",
            "Which household foods are toxic to dogs and cats?",
        ]
    return [
        "Tôi muốn tìm bé mèo phù hợp căn hộ",
        "Mèo trưởng thành nên chọn thức ăn nào?",
        "So sánh FOOD-001, FOOD-002 và FOOD-006",
        "Thực phẩm nào trong nhà gây ngộ độc cho chó mèo?",
    ]
