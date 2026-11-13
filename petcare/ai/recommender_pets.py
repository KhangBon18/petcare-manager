"""Two-stage explainable Python Pet Matching Engine (Hard Constraints + Preference Scoring)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from petcare.ai.contracts import PreferenceSlots, RecommendationCard, ScoreComponent
from petcare.repositories.base import fetch_all
from petcare.services.catalog_intent import _normalize


MAX_PET_RECOMMENDATIONS = 5


@dataclass(slots=True)
class PetMatchResult:
    """Structured output of the two-stage pet matching algorithm."""

    total_available_for_species: int
    total_passing_hard_constraints: int
    cards: list[RecommendationCard]
    reasoning_summary: str
    missing_data_notes: list[str]
    follow_up_questions: list[str]


def needs_pet_clarification(slots: PreferenceSlots, turn_count: int) -> tuple[bool, str, list[str]]:
    """Determine if essential pet-matching preferences are missing on an initial turn."""
    vi_prompts: list[str] = []
    en_prompts: list[str] = []
    if slots.species is None:
        vi_q = (
            "Để gợi ý thú cưng chính xác từ hồ sơ đang bán, bạn muốn tìm **chó hay mèo**, "
            "không gian sống (căn hộ hay nhà có sân) và ngân sách dự kiến khoảng bao nhiêu?"
        )
        en_q = (
            "To match available pet profiles accurately, are you looking for a **dog or a cat**, "
            "what is your living space (apartment or house), and what is your target budget?"
        )
        vi_prompts = [
            "Mèo hợp căn hộ, dưới 6 triệu",
            "Chó dáng nhỏ, hiền, dưới 8 triệu",
            "Mèo trưởng thành dưới 5 triệu",
        ]
        en_prompts = [
            "Calm cat for an apartment, under 6 million VND",
            "Small gentle dog under 8 million VND",
            "Adult cat below 5 million VND",
        ]
        return True, f"{vi_q}||{en_q}", [*vi_prompts, "||", *en_prompts]

    # Classic guided-discovery check: user gave species + living_space (or only species with vague ask),
    # but gave neither budget nor temperament nor size nor age on the first turn.
    has_secondary = any((
        slots.budget_max is not None,
        slots.budget_min is not None,
        slots.temperament is not None,
        slots.size_preference is not None,
        slots.life_stage is not None,
        slots.sex is not None,
        bool(slots.coat_colors),
        bool(slots.eye_colors),
    ))
    if not has_secondary and turn_count <= 1:
        species_vi = "mèo" if slots.species == "cat" else "chó"
        species_en = "cat" if slots.species == "cat" else "dog"
        vi_q = (
            f"Bạn ưu tiên bé {species_vi} có tính cách **hiền/ít vận động hay năng động**, "
            f"và **ngân sách dự kiến** khoảng bao nhiêu? "
            f"(Lưu ý: mức năng lượng và độ hợp căn hộ chỉ chấm điểm trên dữ liệu hồ sơ đã xác minh.)"
        )
        en_q = (
            f"Do you prefer a **calm or active {species_en}**, and what is **your budget**? "
            f"(Note: energy level and apartment suitability are scored only from verified profile attributes.)"
        )
        vi_prompts = [
            "Hiền, dưới 8 triệu VND",
            "Năng động, dưới 6 triệu VND",
            "Dáng nhỏ, từ 3 đến 7 triệu VND",
        ]
        en_prompts = [
            "Calm, below 8 million VND",
            "Active, under 6 million VND",
            "Small size, between 3 and 7 million VND",
        ]
        return True, f"{vi_q}||{en_q}", [*vi_prompts, "||", *en_prompts]

    return False, "", []


def localize_clarification(packed_message: str, packed_chips: list[str], locale: str) -> tuple[str, list[str]]:
    vi_msg, _, en_msg = packed_message.partition("||")
    sep_idx = packed_chips.index("||") if "||" in packed_chips else len(packed_chips)
    vi_chips = packed_chips[:sep_idx]
    en_chips = packed_chips[sep_idx + 1 :] if sep_idx < len(packed_chips) else vi_chips
    if locale == "en":
        return en_msg or vi_msg, en_chips
    return vi_msg, vi_chips


def _age_months(birth_date: date | None, today: date) -> int | None:
    if birth_date is None or not isinstance(birth_date, date) or birth_date > today:
        return None
    months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
    if today.day < birth_date.day:
        months -= 1
    return max(0, months)


def _species_matches(row_species: str, requested_species: str | None) -> bool:
    if not requested_species:
        return True
    norm = _normalize(row_species or "")
    if requested_species == "cat":
        return any(w in norm for w in ("meo", "cat", "feline"))
    if requested_species == "dog":
        return any(w in norm for w in ("cho", "dog", "canine"))
    return True


def _passes_hard_constraints(row: dict[str, Any], slots: PreferenceSlots) -> bool:
    if row.get("sale_status") != "available":
        return False
    if not _species_matches(str(row.get("species") or ""), slots.species):
        return False
    price = Decimal(str(row.get("sale_price") or "0"))
    if slots.budget_min is not None and price < slots.budget_min:
        return False
    if slots.budget_max is not None and price > slots.budget_max:
        return False
    if slots.sex and row.get("sex") != slots.sex:
        # Unknown sex is not assumed to match an explicit male/female hard filter.
        return False
    for field_name, color_groups in (("coat_color", slots.coat_colors), ("eye_color", slots.eye_colors)):
        if color_groups:
            val_norm = _normalize(str(row.get(field_name) or ""))
            for aliases in color_groups:
                if not any(_normalize(alias) in val_norm for alias in aliases):
                    return False
    return True


def _score_pet(
    row: dict[str, Any],
    slots: PreferenceSlots,
    *,
    today: date,
    currency_code: str,
    locale: str,
) -> RecommendationCard:
    vi = locale != "en"
    price = Decimal(str(row.get("sale_price") or "0"))
    tags_raw = str(row.get("appearance_tags") or "").strip()
    tags_norm = _normalize(tags_raw)
    weight_raw = row.get("weight_kg")
    weight_kg = Decimal(str(weight_raw)) if weight_raw is not None else None
    months = _age_months(row.get("birth_date"), today)

    breakdown: list[ScoreComponent] = []
    reasons: list[str] = []
    warnings: list[str] = []

    # 1. Budget Fit (max 30)
    if slots.budget_max is not None and slots.budget_max > 0:
        ratio = price / slots.budget_max
        if ratio <= Decimal("0.75"):
            b_pts = 30
        elif ratio <= Decimal("0.90"):
            b_pts = 26
        else:
            b_pts = 22
        b_detail = (
            f"Giá niêm yết nằm trong trần ngân sách ({int(price):,} / {int(slots.budget_max):,} {currency_code}).".replace(",", ".")
            if vi
            else f"Listed price fits within your ceiling ({int(price):,} / {int(slots.budget_max):,} {currency_code})."
        )
        reasons.append(b_detail)
        breakdown.append(ScoreComponent(
            criterion="budget_fit",
            label="Phù hợp ngân sách" if vi else "Budget compatibility",
            points=b_pts,
            max_points=30,
            status="matched",
            detail=b_detail,
        ))
    elif slots.budget_min is not None:
        b_detail = (
            f"Đáp ứng mức ngân sách tối thiểu ≥ {int(slots.budget_min):,} {currency_code}.".replace(",", ".")
            if vi
            else f"Meets minimum budget ≥ {int(slots.budget_min):,} {currency_code}."
        )
        breakdown.append(ScoreComponent(
            criterion="budget_fit",
            label="Phù hợp ngân sách" if vi else "Budget compatibility",
            points=24,
            max_points=30,
            status="matched",
            detail=b_detail,
        ))
    else:
        breakdown.append(ScoreComponent(
            criterion="budget_fit",
            label="Phù hợp ngân sách" if vi else "Budget compatibility",
            points=18,
            max_points=30,
            status="neutral",
            detail="Chưa đặt trần ngân sách cụ thể." if vi else "No budget ceiling specified.",
        ))

    # 2. Space & Verified Size Fit (max 25) — NEVER infer from breed alone!
    has_small_tag = any(t in tags_norm for t in ("dang nho", "nho gon", "co nho"))
    has_large_tag = any(t in tags_norm for t in ("dang lon", "co lon", "to khoe"))
    has_apartment_tag = any(t in tags_norm for t in ("can ho", "trong nha", "apartment", "indoor"))

    if slots.living_space == "apartment" or slots.size_preference == "small":
        if has_apartment_tag:
            s_pts, s_status = 25, "matched"
            s_detail = (
                "Hồ sơ ghi nhận phù hợp nuôi trong nhà/căn hộ."
                if vi else "Profile explicitly documents indoor/apartment suitability."
            )
            reasons.append(s_detail)
        elif has_small_tag or (weight_kg is not None and weight_kg <= Decimal("6.0")):
            s_pts, s_status = 20, "partial"
            size_evidence = (
                f"cân nặng {weight_kg.normalize()} kg" if weight_kg is not None else "nhãn 'dáng nhỏ'"
            ) if vi else (
                f"verified weight {weight_kg.normalize()} kg" if weight_kg is not None else "documented 'small size' tag"
            )
            s_detail = (
                f"Kích thước nhỏ gọn đã xác minh ({size_evidence}), thuận lợi cho không gian gọn."
                if vi else f"Verified compact size ({size_evidence}) suits smaller living spaces."
            )
            reasons.append(s_detail)
            if slots.living_space == "apartment":
                warnings.append(
                    "Thuộc tính 'phù hợp căn hộ' chuyên biệt chưa được ghi nhận riêng trên hồ sơ; cần kiểm tra mức độ kêu/vận động thực tế."
                    if vi else
                    "Explicit apartment suitability is not separately recorded on this profile; verify vocalization and activity in store."
                )
        elif weight_kg is not None and weight_kg <= Decimal("12.0") and not has_large_tag:
            s_pts, s_status = 12, "partial"
            s_detail = (
                f"Cân nặng trung bình ({weight_kg.normalize()} kg); chưa có xác nhận độ hợp căn hộ."
                if vi else f"Medium verified weight ({weight_kg.normalize()} kg); apartment fit is undocumented."
            )
            warnings.append(s_detail)
        elif has_large_tag or (weight_kg is not None and weight_kg > Decimal("12.0")):
            s_pts, s_status = 3, "partial"
            s_detail = (
                f"Hồ sơ ghi nhận kích thước lớn ({weight_kg.normalize() if weight_kg else '?'} kg), cần cân nhắc kỹ diện tích căn hộ."
                if vi else f"Documented larger size ({weight_kg.normalize() if weight_kg else '?'} kg); evaluate apartment space carefully."
            )
            warnings.append(s_detail)
        else:
            # Unknown size/weight -> 0 bonus points, NEVER assumed favorable
            s_pts, s_status = 0, "unknown"
            s_detail = (
                "Chưa có dữ liệu cân nặng hoặc kích thước trên hồ sơ (không suy đoán từ giống)."
                if vi else "Size and weight are undocumented on this profile (never inferred from breed alone)."
            )
            warnings.append(s_detail)
        breakdown.append(ScoreComponent(
            criterion="space_size_fit",
            label="Không gian & kích thước xác minh" if vi else "Space & verified size fit",
            points=s_pts,
            max_points=25,
            status=s_status,
            detail=s_detail,
        ))
    elif slots.size_preference == "large" or slots.living_space == "house":
        if has_large_tag or (weight_kg is not None and weight_kg >= Decimal("10.0")):
            s_pts, s_status = 23, "matched"
            s_detail = (
                f"Kích thước tầm trung/lớn đã xác minh ({weight_kg.normalize() if weight_kg else ''} kg)."
                if vi else f"Verified medium/large build ({weight_kg.normalize() if weight_kg else ''} kg)."
            )
            reasons.append(s_detail)
        elif weight_kg is None and not has_small_tag:
            s_pts, s_status = 0, "unknown"
            s_detail = "Cân nặng và kích thước chưa được ghi nhận." if vi else "Weight and size are undocumented."
            warnings.append(s_detail)
        else:
            s_pts, s_status = 12, "partial"
            s_detail = "Kích thước nhỏ hơn mức ưu tiên nhưng có thể nuôi trong nhà rộng." if vi else "Smaller than preferred size."
        breakdown.append(ScoreComponent(
            criterion="space_size_fit",
            label="Không gian & kích thước xác minh" if vi else "Space & verified size fit",
            points=s_pts,
            max_points=25,
            status=s_status,
            detail=s_detail,
        ))
    else:
        if weight_kg is None:
            warnings.append("Hồ sơ chưa ghi nhận cân nặng hiện tại." if vi else "Current weight is not documented on this profile.")
        breakdown.append(ScoreComponent(
            criterion="space_size_fit",
            label="Không gian & kích thước xác minh" if vi else "Space & verified size fit",
            points=15 if weight_kg is not None else 8,
            max_points=25,
            status="neutral" if weight_kg is not None else "unknown",
            detail=(
                f"Cân nặng ghi nhận: {weight_kg.normalize()} kg." if (vi and weight_kg is not None)
                else (f"Verified weight: {weight_kg.normalize()} kg." if weight_kg is not None
                      else ("Chưa ghi nhận cân nặng." if vi else "Weight not documented."))
            ),
        ))

    # 3. Temperament & Care Fit (max 25) — ONLY from verified appearance_tags
    has_calm_tag = any(t in tags_norm for t in ("hien", "it van dong", "diem tinh", "calm", "gentle"))
    has_friendly_tag = any(t in tags_norm for t in ("than thien", "de gan", "friendly"))
    has_active_tag = any(t in tags_norm for t in ("nang dong", "nhanh nhen", "active", "playful"))
    has_long_coat = any(t in tags_norm for t in ("long dai", "long day", "long xu"))

    if slots.temperament == "calm":
        if has_calm_tag:
            t_pts, t_status = 25, "matched"
            t_detail = (
                "Hồ sơ ghi nhận trực tiếp đặc điểm 'hiền'."
                if vi else "Profile directly documents a gentle/calm trait ('hiền')."
            )
            reasons.append(t_detail)
        elif has_friendly_tag and not has_active_tag:
            t_pts, t_status = 12, "partial"
            t_detail = (
                "Hồ sơ ghi nhận 'thân thiện', nhưng mức năng lượng (ít vận động/hiền) chưa được kiểm chứng riêng."
                if vi else "Profile notes 'friendly', though low-energy temperament is not separately verified."
            )
            warnings.append(t_detail)
        elif has_active_tag:
            t_pts, t_status = 4, "partial"
            t_detail = (
                "Hồ sơ ghi nhận bé thiên về vận động/nhanh nhẹn, khác với ưu tiên yên tĩnh."
                if vi else "Profile notes active traits, which differs from a calm preference."
            )
            warnings.append(t_detail)
        else:
            t_pts, t_status = 0, "unknown"
            t_detail = (
                "Tính cách và mức năng lượng chưa được ghi nhận trên hồ sơ (không suy đoán theo giống)."
                if vi else "Temperament and energy level are undocumented (not assumed from breed)."
            )
            warnings.append(t_detail)
    elif slots.temperament == "active":
        if has_active_tag:
            t_pts, t_status = 25, "matched"
            t_detail = (
                "Hồ sơ ghi nhận đặc điểm năng động/nhanh nhẹn."
                if vi else "Profile documents active/energetic traits."
            )
            reasons.append(t_detail)
        elif has_friendly_tag:
            t_pts, t_status = 14, "partial"
            t_detail = (
                "Hồ sơ ghi nhận 'thân thiện'; mức độ vận động cao cần quan sát trực tiếp tại cửa hàng."
                if vi else "Profile notes 'friendly'; high play drive should be verified in person."
            )
            warnings.append(t_detail)
        else:
            t_pts, t_status = 0, "unknown"
            t_detail = (
                "Mức năng lượng chưa được ghi nhận trên hồ sơ (không giả định theo giống)."
                if vi else "Energy level is undocumented on this profile (not assumed from breed)."
            )
            warnings.append(t_detail)
    else:
        t_pts = 15 if (has_calm_tag or has_friendly_tag or has_active_tag) else 8
        t_status = "neutral" if t_pts == 15 else "unknown"
        t_detail = (
            f"Ghi chú quan sát hồ sơ: {tags_raw}." if (vi and tags_raw)
            else (f"Recorded profile observations: {tags_raw}." if tags_raw
                  else ("Chưa có ghi chú tính cách." if vi else "No temperament notes recorded."))
        )

    if has_long_coat:
        warnings.append(
            "Lông dài/dày/xù theo hồ sơ: cần chải lông thường xuyên để tránh rối."
            if vi else "Documented long/thick/curly coat requires regular brushing."
        )

    breakdown.append(ScoreComponent(
        criterion="temperament_care_fit",
        label="Tính cách & chăm sóc đã ghi nhận" if vi else "Documented temperament & care",
        points=t_pts,
        max_points=25,
        status=t_status,
        detail=t_detail,
    ))

    # 4. Age / Life-Stage & Profile Completeness (max 20)
    completeness_pts = (
        (4 if row.get("photo_filename") else 0)
        + (2 if weight_kg is not None else 0)
        + (2 if row.get("coat_color") else 0)
    )
    if months is None:
        age_pts, age_status = 0, "unknown"
        age_detail = "Chưa ghi nhận ngày sinh trên hồ sơ." if vi else "Birth date is not documented on this profile."
        warnings.append(age_detail)
    else:
        actual_stage = "junior" if months < 12 else ("senior" if months >= 96 else "adult")
        if slots.life_stage:
            if actual_stage == slots.life_stage:
                age_pts, age_status = 12, "matched"
                age_detail = (
                    f"Độ tuổi xác minh ({months} tháng) khớp giai đoạn yêu cầu."
                    if vi else f"Verified age ({months} months) matches requested life stage."
                )
                reasons.append(age_detail)
            else:
                age_pts, age_status = 4, "partial"
                age_detail = (
                    f"Độ tuổi hiện tại là {months} tháng (khác giai đoạn ưu tiên)."
                    if vi else f"Verified age is {months} months (differs from preferred stage)."
                )
        else:
            age_pts, age_status = 10, "neutral"
            age_detail = f"Độ tuổi xác minh: {months} tháng." if vi else f"Verified age: {months} months."

    total_age_comp = min(20, age_pts + completeness_pts)
    breakdown.append(ScoreComponent(
        criterion="age_profile_completeness",
        label="Độ tuổi & mức đầy đủ hồ sơ" if vi else "Verified age & profile completeness",
        points=total_age_comp,
        max_points=20,
        status=age_status,
        detail=age_detail,
    ))

    total_score = sum(c.points for c in breakdown)

    sex_val = str(row.get("sex") or "unknown")
    sex_label = (
        {"male": "Đực", "female": "Cái"}.get(sex_val, "Chưa rõ")
        if vi else {"male": "Male", "female": "Female"}.get(sex_val, "Unknown")
    )
    age_label = (
        (f"{months} tháng" if vi else f"{months} months")
        if months is not None
        else ("Chưa ghi nhận" if vi else "Undocumented")
    )
    weight_label = (
        f"{weight_kg.normalize()} kg"
        if weight_kg is not None
        else ("Chưa ghi nhận" if vi else "Undocumented")
    )

    verified_attrs: dict[str, str] = {
        "species": str(row.get("species") or ""),
        "breed": str(row.get("breed") or ("Chưa ghi nhận" if vi else "Undocumented")),
        "sex": sex_label,
        "age": age_label,
        "weight": weight_label,
        "coat_color": str(row.get("coat_color") or ("Chưa ghi nhận" if vi else "Undocumented")),
        "eye_color": str(row.get("eye_color") or ("Chưa ghi nhận" if vi else "Undocumented")),
        "observed_traits": tags_raw or ("Chưa ghi nhận" if vi else "Undocumented"),
    }

    if not reasons:
        reasons.append(
            "Đang mở bán tại cửa hàng với giá niêm yết và hồ sơ xác thực."
            if vi else "Currently available in store with verified pricing and profile."
        )

    subtitle_parts = [p for p in (row.get("species"), row.get("breed")) if p]
    return RecommendationCard(
        kind="pet",
        entity_id=int(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        subtitle=" · ".join(str(p) for p in subtitle_parts),
        price=price,
        currency_code=currency_code,
        availability_status=str(row.get("sale_status") or "available"),
        score=total_score,
        max_score=100,
        score_breakdown=tuple(breakdown),
        verified_attributes=verified_attrs,
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        photo_filename=row.get("photo_filename"),
    )


def match_available_pets(
    connection: Any,
    slots: PreferenceSlots,
    *,
    today: date,
    currency_code: str = "VND",
    locale: str = "vi",
    top_k: int = MAX_PET_RECOMMENDATIONS,
) -> PetMatchResult:
    """Query tenant-scoped available pets, enforce hard constraints, and rank transparently."""
    vi = locale != "en"
    rows = fetch_all(
        connection,
        "SELECT id, code, name, species, breed, sex, birth_date, weight_kg, "
        "coat_color, eye_color, appearance_tags, sale_price, sale_status, photo_filename "
        "FROM pets WHERE tenant_id = @petcare_tenant_id AND sale_status = 'available' "
        "ORDER BY id",
    )
    species_pool = [
        row for row in rows if _species_matches(str(row.get("species") or ""), slots.species)
    ]
    filtered = [row for row in species_pool if _passes_hard_constraints(row, slots)]

    scored = [
        _score_pet(row, slots, today=today, currency_code=currency_code, locale=locale)
        for row in filtered
    ]
    scored.sort(key=lambda card: (-card.score, card.price, card.entity_id))
    top_cards = scored[: max(1, min(top_k, MAX_PET_RECOMMENDATIONS))]

    missing_notes = [
        (
            "Hồ sơ thú cưng hiện không lưu trường chứng nhận 'apartment_suitable' hay điểm năng lượng định lượng riêng; "
            "mọi tiêu chí chưa ghi nhận đều nhận 0 điểm thưởng (không suy đoán theo giống)."
            if vi else
            "Pet records do not store dedicated quantitative energy or apartment-certification columns; "
            "undocumented traits receive 0 bonus points and are never inferred from breed alone."
        )
    ]

    if top_cards:
        summary = (
            f"Đã lọc {len(species_pool)} hồ sơ đang bán → {len(filtered)} bé đạt ràng buộc cứng "
            f"(loài, trạng thái sẵn sàng, trần ngân sách). Xếp hạng Top {len(top_cards)} theo thang 100 điểm minh bạch."
            if vi else
            f"Evaluated {len(species_pool)} available profiles → {len(filtered)} passed hard constraints "
            f"(species, availability, budget ceiling). Ranked Top {len(top_cards)} on an explainable 100-point scale."
        )
        follow_ups = (
            [
                "Chỉ xem các bé dưới 5 triệu VND",
                "Gợi ý thức ăn và đồ dùng khởi đầu cho bé này",
                "Lưu ý chuẩn bị căn hộ khi mới đón thú cưng",
            ]
            if vi else
            [
                "Filter to pets under 5 million VND",
                "Recommend starter food and supplies for this pet",
                "How should I prepare my apartment for a new pet?",
            ]
        )
    else:
        summary = (
            f"Đã kiểm tra {len(species_pool)} hồ sơ đang bán nhưng chưa có bé nào đạt đồng thời mọi ràng buộc cứng hiện tại."
            if vi else
            f"Checked {len(species_pool)} available pet profiles, and none satisfied all active hard constraints simultaneously."
        )
        follow_ups = (
            [
                "Nới ngân sách lên dưới 10 triệu VND",
                "Xem tất cả thú cưng đang mở bán",
                "Đặt lại bộ lọc tư vấn",
            ]
            if vi else
            [
                "Increase budget ceiling to 10 million VND",
                "Show all available pets",
                "Reset preferences",
            ]
        )

    return PetMatchResult(
        total_available_for_species=len(species_pool),
        total_passing_hard_constraints=len(filtered),
        cards=top_cards,
        reasoning_summary=summary,
        missing_data_notes=missing_notes,
        follow_up_questions=follow_ups,
    )
