"""Explainable Python Product Recommendation & Side-by-Side Comparison Engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

from petcare.ai.contracts import (
    ComparisonRow,
    ComparisonTable,
    PreferenceSlots,
    RecommendationCard,
    ScoreComponent,
)
from petcare.repositories.base import fetch_all
from petcare.services.catalog_intent import _normalize


MAX_PRODUCT_RECOMMENDATIONS = 5
MAX_COMPARISON_ITEMS = 4

_UNIT_EXTRACT_RE = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|tờ|to|miếng|mieng|viên|vien|m)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ParsedPackageUnit:
    """Normalized package quantity and unit-price metrics derived from verified text."""

    amount: Decimal
    unit: str  # "kg" | "g" | "L" | "ml" | "sheet" | "tablet" | "m"
    package_label_vi: str
    package_label_en: str
    unit_price_vi: str | None
    unit_price_en: str | None
    comparable_group: str | None  # "mass_kg" | "vol_l" | "count" | None
    comparable_cost: Decimal | None


@dataclass(frozen=True, slots=True)
class VerifiedProductMeta:
    """Strictly verified attributes parsed from product name, category, and description."""

    species: str  # "cat" | "dog" | "both" | "unspecified"
    life_stage: str  # "junior" | "adult" | "all" | "unspecified"
    normalized_category: str  # "food" | "toy" | "litter" | "care" | "accessory"
    subtopics: tuple[str, ...]
    ingredients: tuple[str, ...]
    indoor_noted: bool
    small_pet_noted: bool


@dataclass(slots=True)
class ProductRecommendationResult:
    """Structured output of the personalized product recommendation engine."""

    cards: list[RecommendationCard]
    out_of_stock_names: list[str]
    no_primary_match: bool
    reasoning_summary: str
    missing_data_notes: list[str]
    follow_up_questions: list[str]


def _fmt_int(amount: Decimal, vi: bool) -> str:
    rounded = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    text = f"{rounded:,}"
    return text.replace(",", ".") if vi else text


def parse_package_unit(
    name: str,
    description: str | None,
    unit_price: Decimal,
    currency_code: str = "VND",
) -> ParsedPackageUnit | None:
    """Extract verified weight/volume/count unit and compute exact Decimal unit prices."""
    combined = f"{name or ''} {description or ''}"
    match = _UNIT_EXTRACT_RE.search(combined)
    if not match:
        return None
    raw_num, raw_unit = match.groups()
    amount = Decimal(raw_num.replace(",", "."))
    if amount <= 0:
        return None

    u_lower = _normalize(raw_unit)
    amt_str = str(amount.normalize())

    if u_lower == "kg":
        per_kg = unit_price / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="kg",
            package_label_vi=f"{amt_str} kg",
            package_label_en=f"{amt_str} kg",
            unit_price_vi=f"{_fmt_int(per_kg, True)} {currency_code}/kg",
            unit_price_en=f"{_fmt_int(per_kg, False)} {currency_code}/kg",
            comparable_group="mass_kg",
            comparable_cost=per_kg,
        )
    if u_lower == "g":
        per_100g = (unit_price * Decimal(100)) / amount
        per_kg = (unit_price * Decimal(1000)) / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="g",
            package_label_vi=f"{amt_str} g",
            package_label_en=f"{amt_str} g",
            unit_price_vi=f"{_fmt_int(per_100g, True)} {currency_code}/100g ({_fmt_int(per_kg, True)} {currency_code}/kg)",
            unit_price_en=f"{_fmt_int(per_100g, False)} {currency_code}/100g ({_fmt_int(per_kg, False)} {currency_code}/kg)",
            comparable_group="mass_kg",
            comparable_cost=per_kg,
        )
    if u_lower == "l":
        per_l = unit_price / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="L",
            package_label_vi=f"{amt_str} L",
            package_label_en=f"{amt_str} L",
            unit_price_vi=f"{_fmt_int(per_l, True)} {currency_code}/L",
            unit_price_en=f"{_fmt_int(per_l, False)} {currency_code}/L",
            comparable_group="vol_l",
            comparable_cost=per_l,
        )
    if u_lower == "ml":
        per_100ml = (unit_price * Decimal(100)) / amount
        per_l = (unit_price * Decimal(1000)) / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="ml",
            package_label_vi=f"{amt_str} ml",
            package_label_en=f"{amt_str} ml",
            unit_price_vi=f"{_fmt_int(per_100ml, True)} {currency_code}/100ml",
            unit_price_en=f"{_fmt_int(per_100ml, False)} {currency_code}/100ml",
            comparable_group="vol_l",
            comparable_cost=per_l,
        )
    if u_lower in {"to", "mieng"}:
        per_sheet = unit_price / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="sheet",
            package_label_vi=f"{amt_str} tờ",
            package_label_en=f"{amt_str} sheets",
            unit_price_vi=f"{_fmt_int(per_sheet, True)} {currency_code}/tờ",
            unit_price_en=f"{_fmt_int(per_sheet, False)} {currency_code}/sheet",
            comparable_group="count",
            comparable_cost=per_sheet,
        )
    if u_lower == "vien":
        per_tab = unit_price / amount
        return ParsedPackageUnit(
            amount=amount,
            unit="tablet",
            package_label_vi=f"{amt_str} viên",
            package_label_en=f"{amt_str} tablets",
            unit_price_vi=f"{_fmt_int(per_tab, True)} {currency_code}/viên",
            unit_price_en=f"{_fmt_int(per_tab, False)} {currency_code}/tablet",
            comparable_group="count",
            comparable_cost=per_tab,
        )
    if u_lower == "m":
        return ParsedPackageUnit(
            amount=amount,
            unit="m",
            package_label_vi=f"{amt_str} m",
            package_label_en=f"{amt_str} m",
            unit_price_vi=None,
            unit_price_en=None,
            comparable_group=None,
            comparable_cost=None,
        )
    return None


def extract_verified_product_meta(row: dict[str, Any]) -> VerifiedProductMeta:
    """Derive strictly verified product tags from category, name, and description."""
    raw_name = str(row.get("name") or "")
    raw_cat = str(row.get("category") or "")
    raw_desc = str(row.get("description") or "")
    combined_raw = f"{raw_name} {raw_cat} {raw_desc}"
    norm = _normalize(combined_raw)
    cat_norm = _normalize(raw_cat)

    # Normalized category (check product name/description for cat litter stored under generic Care category)
    is_litter_item = (
        "cat ve sinh" in cat_norm
        or "litter" in cat_norm
        or bool(re.search(r"\bcát\b", raw_name, re.IGNORECASE))
        or any(
            k in norm
            for k in ("cat ve sinh", "cat dau nanh", "cat dat set", "cat von cuc", "bentonite", "litter")
        )
    )
    if "do choi" in cat_norm or "toy" in cat_norm:
        norm_cat = "toy"
    elif is_litter_item:
        norm_cat = "litter"
    elif any(k in cat_norm for k in ("thuc an", "dinh duong", "food", "nutrition")):
        norm_cat = "food"
    elif any(k in cat_norm for k in ("cham soc", "ve sinh", "care", "grooming", "hygiene")):
        norm_cat = "care"
    else:
        norm_cat = "accessory"

    # Verified species compatibility
    mentions_cat = bool(
        re.search(r"\b(?:mèo|cat|cats|kitten|feline)\b", combined_raw, re.IGNORECASE)
    ) or norm_cat == "litter"
    mentions_dog = bool(
        re.search(r"\b(?:chó|dog|dogs|puppy|canine|cún)\b", combined_raw, re.IGNORECASE)
    )
    if mentions_cat and mentions_dog:
        species = "both"
    elif mentions_cat:
        species = "cat"
    elif mentions_dog:
        species = "dog"
    else:
        species = "unspecified"

    # Verified life stage
    if any(p in norm for p in ("moi lua tuoi", "all life stages")):
        life_stage = "all"
    elif any(p in norm for p in ("meo con", "cho con", "duoi 12 thang", "kitten", "puppy", "dang lon")):
        life_stage = "junior"
    elif any(p in norm for p in ("truong thanh", "adult")):
        life_stage = "adult"
    else:
        life_stage = "unspecified"

    # Subtopics
    subtopics: list[str] = []
    for tag, keywords in (
        ("dry_food", ("hat cho", "hat meo", "hat kho", "kibble", "dry food")),
        ("wet_food", ("pate", "sot", "wet food", "pouch")),
        ("treat", ("banh thuong", "snack", "treat")),
        ("supplement", ("canxi", "bo sung", "supplement", "vitamin")),
        ("litter", ("cat dau nanh", "cat vo cuc", "bentonite", "litter")),
        ("toy", ("can cau", "do choi", "toy", "feather")),
        ("leash_collar", ("day dat", "vong co", "leash", "collar")),
        ("carrier", ("balo", "tui van chuyen", "carrier")),
        ("bed_bowl", ("nem ngu", "bat an", "bowl", "bed")),
    ):
        if any(k in norm for k in keywords):
            subtopics.append(tag)

    # Verified stated ingredients (for session allergy exclusion only)
    ingredients: list[str] = []
    for ing, words in (
        ("chicken", ("vi ga", "thit ga", "chicken")),
        ("salmon", ("ca hoi", "salmon", "fish")),
        ("beef", ("vi bo", "thit bo", "beef")),
        ("soy", ("dau nanh", "soy", "tofu")),
        ("grain", ("yen mach", "oat", "ngu coc", "grain")),
    ):
        if any(w in norm for w in words):
            ingredients.append(ing)

    indoor_noted = any(p in norm for p in ("trong nha", "indoor", "it mui"))
    small_pet_noted = any(p in norm for p in ("giong nho", "cho meo nho", "small breed", "small dog", "small cat"))

    return VerifiedProductMeta(
        species=species,
        life_stage=life_stage,
        normalized_category=norm_cat,
        subtopics=tuple(subtopics),
        ingredients=tuple(ingredients),
        indoor_noted=indoor_noted,
        small_pet_noted=small_pet_noted,
    )


def needs_product_clarification(slots: PreferenceSlots, turn_count: int) -> tuple[bool, str, list[str]]:
    """Ask a focused clarification when neither species nor category is known."""
    if slots.species is None and slots.product_category is None and turn_count <= 1:
        vi_q = (
            "Để gợi ý sản phẩm chính xác theo tồn kho và giá thực tế, bạn đang tìm đồ cho **chó hay mèo**, "
            "thuộc nhóm nào (**thức ăn, cát vệ sinh, chăm sóc, đồ chơi hay phụ kiện**) và ngân sách khoảng bao nhiêu?"
        )
        en_q = (
            "To recommend suitable in-stock products, is this for a **dog or a cat**, "
            "which category (**food, litter, grooming/care, toys, or accessories**), and what is your budget?"
        )
        vi_chips = [
            "Thức ăn cho mèo trưởng thành dưới 350.000 VND",
            "Đồ dùng phù hợp cho mèo 5 kg",
            "Phụ kiện và bánh thưởng cho chó dưới 300.000 VND",
        ]
        en_chips = [
            "Adult cat food under 350,000 VND",
            "Suitable products for a 5 kg cat",
            "Dog accessories and treats under 300,000 VND",
        ]
        return True, f"{vi_q}||{en_q}", [*vi_chips, "||", *en_chips]
    return False, "", []


def _species_compatible(meta: VerifiedProductMeta, target_species: str | None, *, strict: bool) -> bool:
    if not target_species:
        return True
    if meta.species in {target_species, "both"}:
        return True
    if not strict and meta.species == "unspecified" and meta.normalized_category in {"accessory", "care"}:
        return True
    return False


def _category_matches(meta: VerifiedProductMeta, requested_category: str | None) -> bool:
    if not requested_category:
        return True
    return meta.normalized_category == requested_category


def _allergy_conflict(meta: VerifiedProductMeta, allergies: tuple[str, ...]) -> str | None:
    if not allergies:
        return None
    for allergen in allergies:
        if allergen in meta.ingredients:
            return allergen
    return None


def _score_product(
    row: dict[str, Any],
    meta: VerifiedProductMeta,
    pkg: ParsedPackageUnit | None,
    slots: PreferenceSlots,
    *,
    median_unit_cost: Decimal | None,
    currency_code: str,
    locale: str,
    is_alternative: bool = False,
) -> RecommendationCard:
    vi = locale != "en"
    price = Decimal(str(row.get("unit_price") or "0"))
    stock_qty = int(row.get("stock_qty") or 0)
    breakdown: list[ScoreComponent] = []
    reasons: list[str] = []
    warnings: list[str] = []

    # 1. Species Compatibility (max 30)
    if slots.species:
        if meta.species == slots.species:
            sp_pts, sp_status = 30, "matched"
            sp_label_val = ("mèo" if slots.species == "cat" else "chó") if vi else slots.species
            sp_detail = (
                f"Mô tả sản phẩm xác nhận dành riêng cho {sp_label_val}."
                if vi else f"Verified product metadata targets {sp_label_val}s specifically."
            )
            reasons.append(sp_detail)
        elif meta.species == "both":
            sp_pts, sp_status = 26, "matched"
            sp_detail = (
                "Sản phẩm xác nhận dùng chung cho cả chó và mèo."
                if vi else "Verified for both dogs and cats."
            )
            reasons.append(sp_detail)
        else:
            sp_pts, sp_status = 14, "unknown"
            sp_detail = (
                "Phụ kiện dùng chung chưa ghi giới hạn loài riêng trên mô tả."
                if vi else "General-use item without species restriction in description."
            )
            warnings.append(sp_detail)
    else:
        sp_pts, sp_status = 22, "neutral"
        sp_detail = "Phù hợp tra cứu chung." if vi else "General catalog match."
    breakdown.append(ScoreComponent(
        criterion="species_fit",
        label="Tương thích loài" if vi else "Species compatibility",
        points=sp_pts,
        max_points=30,
        status=sp_status,
        detail=sp_detail,
    ))

    # 2. Category & Subtopic Match (max 25)
    if slots.product_category:
        if meta.normalized_category == slots.product_category:
            cat_pts, cat_status = 25, "matched"
            cat_detail = (
                f"Thuộc đúng danh mục '{row.get('category')}'."
                if vi else f"Matches requested category ('{row.get('category')}')."
            )
            reasons.append(cat_detail)
        else:
            cat_pts, cat_status = 10, "partial"
            cat_detail = (
                f"Gợi ý thay thế cùng loài thuộc nhóm '{row.get('category')}'."
                if vi else f"Adjacent in-stock alternative in '{row.get('category')}'."
            )
            warnings.append(cat_detail)
    else:
        cat_pts, cat_status = 20, "neutral"
        cat_detail = f"Danh mục: {row.get('category')}." if vi else f"Category: {row.get('category')}."
    breakdown.append(ScoreComponent(
        criterion="category_fit",
        label="Khớp danh mục & nhu cầu" if vi else "Category & use-case fit",
        points=cat_pts,
        max_points=25,
        status=cat_status,
        detail=cat_detail,
    ))

    # 3. Life-Stage, Weight & Lifestyle Fit (max 20)
    effective_stage = slots.life_stage
    if effective_stage is None and slots.pet_weight_kg is not None and slots.species == "cat":
        # A 5 kg cat is adult-sized in body mass; keep explicit note without inventing medical claims
        if slots.pet_weight_kg >= Decimal("3.5"):
            effective_stage = "adult"

    stage_pts = 13
    stage_status = "neutral"
    stage_detail = (
        "Không giới hạn độ tuổi riêng trong mô tả."
        if vi else "No stage restriction noted in product description."
    )
    if effective_stage == "adult":
        if meta.life_stage in {"adult", "all"}:
            stage_pts, stage_status = 20, "matched"
            stage_detail = (
                "Phù hợp giai đoạn trưởng thành / mọi lứa tuổi theo mô tả."
                if vi else "Verified for adult / all life stages."
            )
            reasons.append(stage_detail)
        elif meta.life_stage == "junior":
            stage_pts, stage_status = 4, "partial"
            stage_detail = (
                "Sản phẩm ghi nhận ưu tiên thú non (<12 tháng), kém phù hợp hơn cho thú trưởng thành."
                if vi else "Formulated for junior pets (<12 months) rather than adults."
            )
            warnings.append(stage_detail)
    elif effective_stage == "junior":
        if meta.life_stage in {"junior", "all"}:
            stage_pts, stage_status = 20, "matched"
            stage_detail = (
                "Khớp giai đoạn thú non đang lớn theo mô tả."
                if vi else "Verified for growing junior pets."
            )
            reasons.append(stage_detail)
        elif meta.life_stage == "adult":
            stage_pts, stage_status = 5, "partial"
            stage_detail = (
                "Công thức ghi cho thú trưởng thành; cần kiểm tra kỹ cho thú non."
                if vi else "Labeled for adult pets; verify suitability for juniors."
            )
            warnings.append(stage_detail)

    if slots.pet_weight_kg is not None:
        w_val = slots.pet_weight_kg.normalize()
        if meta.normalized_category == "accessory" and "carrier" in meta.subtopics and slots.pet_weight_kg >= Decimal("5"):
            warnings.append(
                f"Mô tả ghi dành cho chó mèo nhỏ; cần kiểm tra tải trọng thực tế cho bé {w_val} kg trước khi mua."
                if vi else
                f"Labeled for small pets; verify physical weight capacity for a {w_val} kg pet before purchase."
            )
            stage_pts = max(8, stage_pts - 4)
        else:
            warnings.append(
                f"Bảng khẩu phần/cỡ chi tiết theo mốc {w_val} kg không lưu trong CSDL; hãy đối chiếu hướng dẫn in trên bao bì."
                if vi else
                f"Exact feeding/sizing chart for {w_val} kg is not stored in catalog metadata; check the printed package label."
            )

    if slots.living_space == "apartment" and meta.indoor_noted:
        stage_pts = min(20, stage_pts + 3)
        reasons.append(
            "Mô tả ghi nhận tối ưu cho nuôi trong nhà / ít mùi."
            if vi else "Description highlights indoor / low-odor suitability."
        )

    breakdown.append(ScoreComponent(
        criterion="stage_lifestyle_fit",
        label="Độ tuổi, cân nặng & môi trường" if vi else "Life-stage, weight & indoor fit",
        points=stage_pts,
        max_points=20,
        status=stage_status,
        detail=stage_detail,
    ))

    # 4. Budget & Unit-Price Value (max 15)
    val_pts = 10
    val_status = "neutral"
    unit_disp = (pkg.unit_price_vi if vi else pkg.unit_price_en) if pkg else None
    pkg_disp = (pkg.package_label_vi if vi else pkg.package_label_en) if pkg else None

    if slots.budget_max is not None and slots.budget_max > 0:
        val_pts = 13 if price <= slots.budget_max * Decimal("0.85") else 11
        val_status = "matched"
    if pkg and pkg.comparable_cost is not None and median_unit_cost is not None and median_unit_cost > 0:
        if pkg.comparable_cost <= median_unit_cost:
            val_pts = min(15, val_pts + 2)
            val_status = "matched"
            if unit_disp:
                reasons.append(
                    f"Đơn giá quy đổi kinh tế ({unit_disp})."
                    if vi else f"Competitive normalized unit price ({unit_disp})."
                )
    val_detail = (
        (f"Quy cách {pkg_disp} · {unit_disp}." if unit_disp else f"Giá niêm yết {_fmt_int(price, vi)} {currency_code}.")
        if vi else
        (f"Pack {pkg_disp} · {unit_disp}." if unit_disp else f"Listed at {_fmt_int(price, False)} {currency_code}.")
    )
    breakdown.append(ScoreComponent(
        criterion="budget_unit_value",
        label="Ngân sách & đơn giá quy đổi" if vi else "Budget & unit-price efficiency",
        points=val_pts,
        max_points=15,
        status=val_status,
        detail=val_detail,
    ))

    # 5. Stock Availability Health (max 10)
    reorder = int(row.get("reorder_level") or 0)
    if stock_qty > max(reorder, 3):
        st_pts, st_status = 10, "matched"
        st_detail = f"Còn sẵn {stock_qty} đơn vị trong kho." if vi else f"In stock ({stock_qty} units available)."
    elif stock_qty > 0:
        st_pts, st_status = 7, "partial"
        st_detail = (
            f"Còn {stock_qty} đơn vị (sắp chạm ngưỡng nhập lại)."
            if vi else f"Limited stock ({stock_qty} units remaining)."
        )
        warnings.append(st_detail)
    else:
        st_pts, st_status = 0, "unknown"
        st_detail = "Tạm hết hàng (tồn kho = 0)." if vi else "Currently out of stock (0 units)."
        warnings.append(st_detail)

    breakdown.append(ScoreComponent(
        criterion="stock_health",
        label="Tồn kho thực tế" if vi else "Real-time stock health",
        points=st_pts,
        max_points=10,
        status=st_status,
        detail=st_detail,
    ))

    if slots.allergies:
        warnings.append(
            "Đã lọc tránh thành phần dị ứng ghi trong mô tả tóm tắt; bắt buộc kiểm tra bảng thành phần chi tiết trên bao bì."
            if vi else
            "Filtered against summary descriptions for stated session allergies; always verify the full ingredient panel on packaging."
        )

    total_score = sum(c.points for c in breakdown)
    species_label = {
        "cat": ("Mèo", "Cat"),
        "dog": ("Chó", "Dog"),
        "both": ("Chó & Mèo", "Dog & Cat"),
        "unspecified": ("Dùng chung / Chưa ghi riêng", "General / Unspecified"),
    }[meta.species][0 if vi else 1]
    stage_label = {
        "junior": ("Thú non (<12 tháng)", "Junior (<12m)"),
        "adult": ("Trưởng thành", "Adult"),
        "all": ("Mọi lứa tuổi", "All life stages"),
        "unspecified": ("Chưa ghi giới hạn", "Unspecified"),
    }[meta.life_stage][0 if vi else 1]

    verified_attrs: dict[str, str] = {
        "category": str(row.get("category") or ""),
        "species_fit": species_label,
        "life_stage": stage_label,
        "package_size": pkg_disp or ("Chưa ghi quy cách" if vi else "Unit size not stated"),
        "unit_price": unit_disp or ("Không áp dụng" if vi else "N/A"),
        "description": str(row.get("description") or ("Chưa có mô tả" if vi else "No description")),
    }

    return RecommendationCard(
        kind="product",
        entity_id=int(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        subtitle=str(row.get("category") or ""),
        price=price,
        currency_code=currency_code,
        availability_status="active" if stock_qty > 0 else "out_of_stock",
        stock_qty=stock_qty,
        package_size_display=pkg_disp,
        unit_price_display=unit_disp,
        score=total_score,
        max_score=100,
        score_breakdown=tuple(breakdown),
        verified_attributes=verified_attrs,
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        photo_filename=row.get("photo_filename"),
        is_alternative=is_alternative,
    )


def recommend_products(
    connection: Any,
    slots: PreferenceSlots,
    *,
    currency_code: str = "VND",
    locale: str = "vi",
    top_k: int = MAX_PRODUCT_RECOMMENDATIONS,
) -> ProductRecommendationResult:
    """Filter active tenant products by verified metadata, compute unit prices, and rank Top-K."""
    vi = locale != "en"
    rows = fetch_all(
        connection,
        "SELECT id, code, name, category, description, unit_price, stock_qty, reorder_level, photo_filename "
        "FROM products WHERE tenant_id = @petcare_tenant_id AND active = 1 ORDER BY id",
    )

    annotated: list[tuple[dict[str, Any], VerifiedProductMeta, ParsedPackageUnit | None]] = []
    for row in rows:
        price = Decimal(str(row.get("unit_price") or "0"))
        meta = extract_verified_product_meta(row)
        pkg = parse_package_unit(str(row.get("name") or ""), row.get("description"), price, currency_code)
        annotated.append((row, meta, pkg))

    # Primary candidates: strict species (when category is food/toy/litter), category, budget, and allergy check
    strict_species = slots.product_category in {"food", "toy", "litter"}
    primary_in_stock: list[tuple[dict[str, Any], VerifiedProductMeta, ParsedPackageUnit | None]] = []
    out_of_stock_matches: list[str] = []

    for row, meta, pkg in annotated:
        price = Decimal(str(row.get("unit_price") or "0"))
        if not _category_matches(meta, slots.product_category):
            continue
        if not _species_compatible(meta, slots.species, strict=strict_species):
            continue
        if _allergy_conflict(meta, slots.allergies) is not None:
            continue
        if slots.budget_min is not None and price < slots.budget_min:
            continue
        if slots.budget_max is not None and price > slots.budget_max:
            continue

        if int(row.get("stock_qty") or 0) > 0:
            primary_in_stock.append((row, meta, pkg))
        else:
            out_of_stock_matches.append(f"{row['name']} ({row['code']})")

    # Compute median unit cost per comparable_group for fair value scoring
    group_costs: dict[str, list[Decimal]] = {}
    for _, _, pkg in primary_in_stock:
        if pkg and pkg.comparable_group and pkg.comparable_cost is not None:
            group_costs.setdefault(pkg.comparable_group, []).append(pkg.comparable_cost)
    medians: dict[str, Decimal] = {}
    for grp, vals in group_costs.items():
        s_vals = sorted(vals)
        medians[grp] = s_vals[len(s_vals) // 2]

    cards = [
        _score_product(
            row,
            meta,
            pkg,
            slots,
            median_unit_cost=medians.get(pkg.comparable_group) if pkg and pkg.comparable_group else None,
            currency_code=currency_code,
            locale=locale,
            is_alternative=False,
        )
        for row, meta, pkg in primary_in_stock
    ]
    cards.sort(key=lambda c: (-c.score, c.price, c.entity_id))
    top_cards = cards[: max(1, min(top_k, MAX_PRODUCT_RECOMMENDATIONS))]

    no_primary_match = len(top_cards) == 0

    # When primary matches are empty (either out-of-stock or missing category like dog toys),
    # surface clearly-labeled in-stock alternatives for the same species & budget!
    if no_primary_match and slots.species:
        alt_candidates: list[RecommendationCard] = []
        for row, meta, pkg in annotated:
            if int(row.get("stock_qty") or 0) <= 0:
                continue
            price = Decimal(str(row.get("unit_price") or "0"))
            if slots.budget_max is not None and price > slots.budget_max:
                continue
            if _allergy_conflict(meta, slots.allergies) is not None:
                continue
            if meta.species not in {slots.species, "both"}:
                continue
            alt_candidates.append(
                _score_product(
                    row,
                    meta,
                    pkg,
                    slots,
                    median_unit_cost=None,
                    currency_code=currency_code,
                    locale=locale,
                    is_alternative=True,
                )
            )
        alt_candidates.sort(key=lambda c: (-c.score, c.price, c.entity_id))
        top_cards = alt_candidates[:3]

    missing_notes = [
        (
            "Cơ sở dữ liệu sản phẩm hiện lưu tên, danh mục, mô tả tóm tắt, giá và tồn kho; "
            "không lưu bảng thành phần dinh dưỡng chi tiết (% đạm/béo) hay chứng nhận thú y."
            if vi else
            "Product records store name, category, summary description, price, and live stock; "
            "guaranteed nutrient percentages and veterinary certifications are not stored in DB."
        )
    ]

    if not no_primary_match:
        summary = (
            f"Tìm thấy {len(primary_in_stock)} sản phẩm còn hàng khớp tiêu chí. "
            f"Xếp hạng Top {len(top_cards)} dựa trên tương thích loài, danh mục, độ tuổi, đơn giá quy đổi và tồn kho."
            if vi else
            f"Found {len(primary_in_stock)} matching in-stock products. "
            f"Ranked Top {len(top_cards)} by verified species compatibility, category, life stage, normalized unit price, and stock."
        )
        if len(top_cards) >= 2:
            codes_str = ", ".join(c.code for c in top_cards[:3])
            follow_ups = (
                [
                    f"So sánh {codes_str}",
                    "Lọc các sản phẩm dưới 200.000 VND",
                    "Hướng dẫn khẩu phần và cách chuyển đổi thức ăn an toàn",
                ]
                if vi else
                [
                    f"Compare {codes_str}",
                    "Filter to products under 200,000 VND",
                    "How should I transition my pet to new food safely?",
                ]
            )
        else:
            follow_ups = (
                ["Xem thêm sản phẩm chăm sóc cùng loài", "Đặt lại bộ lọc tư vấn"]
                if vi else
                ["Show grooming and care products for this pet", "Reset preferences"]
            )
    else:
        if out_of_stock_matches:
            oos_text = ", ".join(out_of_stock_matches[:3])
            summary = (
                f"Các sản phẩm khớp trực tiếp hiện đã tạm hết hàng ({oos_text}). "
                f"Hệ thống hiển thị {len(top_cards)} lựa chọn thay thế đang còn hàng trong ngân sách."
                if vi else
                f"Directly matching items are currently out of stock ({oos_text}). "
                f"Showing {len(top_cards)} in-stock alternatives within budget."
            )
        else:
            summary = (
                "Danh mục hiện chưa có sản phẩm khớp chính xác đồng thời với nhóm hàng, loài và ngân sách yêu cầu "
                "(trợ lý không gán sai sản phẩm của loài khác)."
                if vi else
                "No active in-stock product in the catalog matches all requested species, category, and budget constraints "
                "(products for other species are never mislabeled as matches)."
            )
        follow_ups = (
            [
                "Xem tất cả sản phẩm cho chó đang còn hàng",
                "Xem tất cả sản phẩm cho mèo đang còn hàng",
                "Nới ngân sách lên dưới 500.000 VND",
            ]
            if vi else
            [
                "Show all in-stock dog products",
                "Show all in-stock cat products",
                "Increase budget to under 500,000 VND",
            ]
        )

    return ProductRecommendationResult(
        cards=top_cards,
        out_of_stock_names=out_of_stock_matches,
        no_primary_match=no_primary_match,
        reasoning_summary=summary,
        missing_data_notes=missing_notes,
        follow_up_questions=follow_ups,
    )


def build_product_comparison(
    connection: Any,
    *,
    explicit_codes: tuple[str, ...],
    session_product_ids: list[int],
    slots: PreferenceSlots,
    count_hint: int = 3,
    currency_code: str = "VND",
    locale: str = "vi",
) -> tuple[ComparisonTable | None, str]:
    """Build a verified side-by-side comparison matrix for 2–4 active tenant products."""
    vi = locale != "en"
    rows = fetch_all(
        connection,
        "SELECT id, code, name, category, description, unit_price, stock_qty, reorder_level, photo_filename "
        "FROM products WHERE tenant_id = @petcare_tenant_id AND active = 1 ORDER BY id",
    )
    by_code = {str(r["code"]).upper(): r for r in rows}
    by_id = {int(r["id"]): r for r in rows}

    selected: list[dict[str, Any]] = []
    missing_explicit_codes: list[str] = []
    if explicit_codes:
        for code in explicit_codes:
            if code.upper() in by_code and by_code[code.upper()] not in selected:
                selected.append(by_code[code.upper()])
            elif code.upper() not in by_code:
                missing_explicit_codes.append(code.upper())
        if len(selected) < 2:
            missing_str = f" ({', '.join(missing_explicit_codes)})" if missing_explicit_codes else ""
            msg = (
                f"Không đủ mã sản phẩm hợp lệ trong danh mục đang bán{missing_str}. "
                "Vui lòng cung cấp ít nhất 2 mã sản phẩm hợp lệ (ví dụ: 'So sánh FOOD-001, FOOD-002 và FOOD-006')."
                if vi else
                f"Fewer than 2 valid active catalog SKUs were found{missing_str}. "
                "Please specify at least 2 valid product codes (for example: 'Compare FOOD-001, FOOD-002, and FOOD-006')."
            )
            return None, msg
    if len(selected) < 2 and session_product_ids:
        for pid in session_product_ids:
            if pid in by_id and by_id[pid] not in selected:
                selected.append(by_id[pid])
                if len(selected) >= max(2, min(count_hint, MAX_COMPARISON_ITEMS)):
                    break
    if len(selected) < 2 and (slots.product_category or slots.species):
        rec = recommend_products(
            connection,
            slots,
            currency_code=currency_code,
            locale=locale,
            top_k=max(2, min(count_hint, MAX_COMPARISON_ITEMS)),
        )
        for card in rec.cards:
            if not card.is_alternative and card.entity_id in by_id and by_id[card.entity_id] not in selected:
                selected.append(by_id[card.entity_id])
                if len(selected) >= max(2, min(count_hint, MAX_COMPARISON_ITEMS)):
                    break

    selected = selected[:MAX_COMPARISON_ITEMS]
    if len(selected) < 2:
        msg = (
            "Cần ít nhất 2 sản phẩm xác định để lập bảng so sánh đối chiếu (ví dụ: 'So sánh FOOD-001, FOOD-002 và FOOD-006' "
            "hoặc yêu cầu gợi ý sản phẩm trước rồi bấm So sánh)."
            if vi else
            "Please specify at least 2 valid products to compare (for example: 'Compare FOOD-001, FOOD-002, and FOOD-006', "
            "or request product recommendations first and compare them)."
        )
        return None, msg

    items_payload: list[dict[str, Any]] = []
    codes_vals: list[str] = []
    cat_vals: list[str] = []
    price_vals: list[str] = []
    pkg_vals: list[str] = []
    unit_vals: list[str] = []
    stock_vals: list[str] = []
    species_vals: list[str] = []
    stage_vals: list[str] = []
    desc_vals: list[str] = []
    missing_vals: list[str] = []

    lowest_price_item: tuple[Decimal, str] | None = None
    lowest_unit_item: tuple[Decimal, str, str] | None = None
    comparable_groups_seen: set[str] = set()

    for row in selected:
        price = Decimal(str(row.get("unit_price") or "0"))
        stock_qty = int(row.get("stock_qty") or 0)
        meta = extract_verified_product_meta(row)
        pkg = parse_package_unit(str(row.get("name") or ""), row.get("description"), price, currency_code)

        items_payload.append({
            "id": int(row["id"]),
            "code": str(row["code"]),
            "name": str(row["name"]),
            "price": str(price),
            "currency_code": currency_code,
            "stock_qty": stock_qty,
            "photo_filename": row.get("photo_filename"),
        })

        codes_vals.append(str(row["code"]))
        cat_vals.append(str(row.get("category") or ""))
        price_vals.append(f"{_fmt_int(price, vi)} {currency_code}")
        pkg_vals.append(
            (pkg.package_label_vi if vi else pkg.package_label_en)
            if pkg else ("Chưa ghi quy cách" if vi else "Not documented")
        )
        u_text = (pkg.unit_price_vi if vi else pkg.unit_price_en) if pkg else None
        unit_vals.append(u_text or ("Không áp dụng / Thiếu quy cách" if vi else "N/A (unit size absent)"))
        stock_vals.append(
            (f"Còn {stock_qty}" if stock_qty > 0 else "Hết hàng (0)")
            if vi else (f"{stock_qty} in stock" if stock_qty > 0 else "Out of stock (0)")
        )
        species_vals.append({
            "cat": ("Mèo", "Cat"),
            "dog": ("Chó", "Dog"),
            "both": ("Chó & Mèo", "Dog & Cat"),
            "unspecified": ("Chưa ghi riêng", "Unspecified"),
        }[meta.species][0 if vi else 1])
        stage_vals.append({
            "junior": ("Thú non (<12 tháng)", "Junior (<12m)"),
            "adult": ("Trưởng thành", "Adult"),
            "all": ("Mọi lứa tuổi", "All life stages"),
            "unspecified": ("Chưa ghi giới hạn", "Not specified"),
        }[meta.life_stage][0 if vi else 1])
        desc_vals.append(str(row.get("description") or ("Chưa có mô tả" if vi else "No description")))
        missing_vals.append(
            "Chưa lưu % dinh dưỡng & chứng nhận"
            if vi else "Nutrient % & certs not in DB"
        )

        if stock_qty > 0 and (lowest_price_item is None or price < lowest_price_item[0]):
            lowest_price_item = (price, str(row["name"]))
        if pkg and pkg.comparable_group and pkg.comparable_cost is not None and stock_qty > 0:
            comparable_groups_seen.add(pkg.comparable_group)
            if lowest_unit_item is None or pkg.comparable_cost < lowest_unit_item[0]:
                lowest_unit_item = (pkg.comparable_cost, str(row["name"]), u_text or "")

    summary_parts: list[str] = []
    if lowest_price_item:
        summary_parts.append(
            f"Giá gói thấp nhất đang còn hàng: {lowest_price_item[1]} ({_fmt_int(lowest_price_item[0], vi)} {currency_code})."
            if vi else
            f"Lowest upfront in-stock price: {lowest_price_item[1]} ({_fmt_int(lowest_price_item[0], False)} {currency_code})."
        )
    if lowest_unit_item and len(comparable_groups_seen) == 1:
        summary_parts.append(
            f"Đơn giá quy đổi tiết kiệm nhất: {lowest_unit_item[1]} ({lowest_unit_item[2]})."
            if vi else
            f"Best normalized unit-price value: {lowest_unit_item[1]} ({lowest_unit_item[2]})."
        )
    summary_text = " ".join(summary_parts) or (
        f"So sánh trực tiếp {len(selected)} sản phẩm từ dữ liệu danh mục đã xác thực."
        if vi else f"Side-by-side comparison of {len(selected)} verified catalog products."
    )

    table = ComparisonTable(
        items=items_payload,
        rows=(
            ComparisonRow("code", "Mã SP" if vi else "SKU Code", tuple(codes_vals)),
            ComparisonRow("category", "Danh mục" if vi else "Category", tuple(cat_vals)),
            ComparisonRow("price", "Giá niêm yết" if vi else "Listed Price", tuple(price_vals)),
            ComparisonRow("package_size", "Quy cách đóng gói" if vi else "Package Size", tuple(pkg_vals)),
            ComparisonRow("unit_price", "Đơn giá quy đổi" if vi else "Normalized Unit Price", tuple(unit_vals)),
            ComparisonRow("stock_qty", "Tồn kho hiện tại" if vi else "Current Stock", tuple(stock_vals)),
            ComparisonRow("species_fit", "Loài phù hợp" if vi else "Verified Species", tuple(species_vals)),
            ComparisonRow("life_stage", "Độ tuổi ghi nhận" if vi else "Life Stage", tuple(stage_vals)),
            ComparisonRow("description", "Mô tả đã xác minh" if vi else "Verified Description", tuple(desc_vals)),
            ComparisonRow("missing", "Thuộc tính chưa lưu" if vi else "Undocumented Data", tuple(missing_vals)),
        ),
        summary=summary_text,
        missing_notes=(
            (
                "Bảng so sánh chỉ đối chiếu thông tin xác thực trong CSDL cửa hàng; "
                "tỷ lệ đạm/béo/chất xơ chi tiết cần xem trực tiếp trên bao bì nhà sản xuất."
                if vi else
                "Comparison reflects verified store database attributes only; "
                "consult manufacturer packaging for guaranteed nutrient percentages."
            ),
        ),
    )
    return table, summary_text
