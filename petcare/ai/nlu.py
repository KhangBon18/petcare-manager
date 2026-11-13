"""Deterministic bilingual (VI/EN) NLU, safety guardrails, and preference slot extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re

from petcare.ai.contracts import PreferenceSlots
from petcare.services import assistant_capabilities
from petcare.services.assistant_query import PriceFilter, catalog_filters
from petcare.services.catalog_intent import _normalize, pet_filter_spec


_PRODUCT_CODE_RE = re.compile(r"\b([A-Z]{2,8}-\d{2,5})\b", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:kg|kilo|kilogram|ki\s*lo|ky)\b")
_AGE_MONTHS_RE = re.compile(r"\b(\d{1,2})\s*(?:thang|months?|mo)\b")
_AGE_YEARS_RE = re.compile(r"\b(\d{1,2})\s*(?:tuoi|nam|years?\s*old|yo|yr)\b")
_BARE_BUDGET_RE = re.compile(
    r"\b(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(trieu|million|tr|m|nghin|ngan|k|vnd|dong)\b"
)

# --- Safety & Policy Patterns ---

_PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all instructions",
    "ignore all rules",
    "disregard previous",
    "system prompt",
    "developer message",
    "reveal your prompt",
    "show hidden instructions",
    "print api_key",
    "reveal api key",
    "secret_key",
    "db_password",
    "jailbreak",
    "bo qua quy tac",
    "bo qua huong dan",
    "tiet lo system prompt",
    "tiet lo prompt",
    "hien thi prompt he thong",
    "cho xem khoa api",
    "mat khau database",
)

_SQL_OR_CODE_PATTERNS = (
    r"\bselect\s+.+\s+from\s+\w+",
    r"\bdrop\s+table\b",
    r"\bdelete\s+from\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\binsert\s+into\b",
    r"\balter\s+table\b",
    r"\bunion\s+select\b",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bimport\s+(?:os|subprocess|sys|socket)\b",
    r"\bchay\s+lenh\s+sql\b",
    r"\bviet\s+cau\s+lenh\s+sql\b",
    r"\bwrite\s+sql\b",
    r"\bgenerate\s+sql\b",
    r"\bexecute\s+python\b",
)

_WRITE_ACTION_PHRASES = (
    "create an invoice",
    "create invoice",
    "checkout now",
    "place an order",
    "place order",
    "buy this now",
    "complete purchase",
    "delete product",
    "delete pet",
    "remove customer",
    "adjust stock to",
    "update stock to",
    "set stock to",
    "issue a refund",
    "process refund",
    "approve purchase order",
    "tao hoa don",
    "lap hoa don ngay",
    "thanh toan ngay",
    "dat mua ngay",
    "chot don ngay",
    "xoa san pham",
    "xoa thu cung",
    "xoa khach hang",
    "sua ton kho",
    "cap nhat ton kho",
    "hoan tien ngay",
    "tao don nhap",
)

_VET_EMERGENCY_PHRASES = (
    "difficulty breathing",
    "hard to breathe",
    "gasping",
    "open mouth breathing",
    "seizure",
    "convulsion",
    "unconscious",
    "collapsed",
    "collapse",
    "vomiting blood",
    "blood in vomit",
    "bloody diarrhea",
    "blood in stool",
    "ate chocolate",
    "ate xylitol",
    "ate lily",
    "ate lilies",
    "lily leaf",
    "chewed on a lily",
    "chewed lily",
    "lily plant",
    "rat poison",
    "poisoned",
    "poisoning",
    "hit by a car",
    "severe bleeding",
    "cannot urinate",
    "straining to urinate",
    "bloated stomach",
    "kho tho",
    "tho gap",
    "ha mieng tho",
    "co giat",
    "bat tinh",
    "ngat xiu",
    "non ra mau",
    "oi ra mau",
    "di ngoai ra mau",
    "tieu chay ra mau",
    "an phai socola",
    "an socola",
    "an phai hoa ly",
    "nuot ba chuot",
    "ngo doc",
    "trung doc",
    "bi xe tong",
    "chay mau nhieu",
    "khong di tieu duoc",
    "bi tieu",
    "chuong bung cung",
)

_VET_MEDICAL_BOUNDARY_PHRASES = (
    "what dosage",
    "how many mg",
    "milligrams",
    "prescribe",
    "prescription",
    "which antibiotic",
    "amoxicillin",
    "metronidazole",
    "ivermectin",
    "prednisolone",
    "paracetamol",
    "ibuprofen",
    "diagnose my",
    "what disease does",
    "is it parvovirus",
    "is it panleukopenia",
    "what medicine should i give",
    "ke don",
    "lieu luong thuoc",
    "bao nhieu mg",
    "uong khang sinh",
    "tiem thuoc gi",
    "uong thuoc gi",
    "chan doan benh",
    "mac benh gi",
    "co phai benh parvo",
    "co phai benh giam bach cau",
    "cho uong paracetamol",
)

# --- Intent & Domain Phrases ---

_RESET_PHRASES = (
    "reset conversation",
    "new conversation",
    "start over",
    "clear preferences",
    "clear context",
    "xoa ngu canh",
    "cuoc tro chuyen moi",
    "bat dau lai",
    "dat lai tu dau",
)

_COMPARISON_PHRASES = (
    "compare",
    "comparison",
    "side by side",
    "difference between",
    "versus",
    " vs ",
    "so sanh",
    "khac nhau giua",
    "doi chieu",
)

_FORECAST_PHRASES = (
    "demand forecast",
    "inventory forecast",
    "8 week forecast",
    "8-week forecast",
    "stockout forecast",
    "weighted demand",
    "du bao nhu cau",
    "du bao ton kho",
    "du bao 8 tuan",
    "toc do tieu thu",
)

_KNOWLEDGE_SIGNALS = (
    "how often should i",
    "how to care",
    "how to groom",
    "how to brush",
    "how to introduce",
    "how to prepare",
    "feeding schedule",
    "feeding guide",
    "how many times a day",
    "litter box",
    "scratching",
    "enrichment",
    "mental stimulation",
    "socialization",
    "first time owner",
    "responsible adoption",
    "responsible pet",
    "apartment prep",
    "prepare my apartment",
    "prepare home",
    "unsafe foods",
    "toxic foods",
    "grooming basics",
    "coat care",
    "dental care",
    "cach cham soc",
    "huong dan cham soc",
    "cho an may bua",
    "lich cho an",
    "khau phan an",
    "chai long",
    "tam cho",
    "tam meo",
    "ve sinh rang",
    "ve sinh tai",
    "khay ve sinh",
    "chuan bi nha",
    "chuan bi can ho",
    "moi nuoi",
    "nuoi thu cung co trach nhiem",
    "do choi van dong",
    "giam cang thang",
    "cao mong",
    "thuc pham nguy hiem",
    "khong nen cho an gi",
    "luu y khi chon mua",
    "kinh nghiem nuoi",
)

_ADVISORY_VERBS = (
    "recommend",
    "suggest",
    "advise",
    "advice",
    "suitable",
    "good for",
    "fit for",
    "best for",
    "which food should",
    "what products are suitable",
    "i want a ",
    "i have a ",
    "looking for",
    "help me choose",
    "help me pick",
    "goi y",
    "tu van",
    "phu hop",
    "hop voi",
    "nen chon",
    "nen mua",
    "chon giup",
    "tim giup",
    "toi muon nuoi",
    "minh muon nuoi",
    "nha minh co",
    "toi co meo",
    "toi co cho",
)

_PRODUCT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "food": (
        "food", "kibble", "dry food", "wet food", "pate", "pouch", "treat", "treats",
        "snack", "supplement", "calcium", "nutrition", "feed",
        "thuc an", "hat kho", "hat cho", "hat meo", "banh thuong", "dinh duong", "bo sung canxi",
    ),
    "toy": (
        "toy", "toys", "feather wand", "teaser", "plaything", "chew toy",
        "do choi", "can cau meo", "bong do choi",
    ),
    "litter": (
        "litter", "clumping", "bentonite", "tofu litter", "soy litter",
        "cat ve sinh", "cat dau nanh", "cat vo cuc",
    ),
    "care": (
        "shampoo", "bath", "grooming", "toothpaste", "toothbrush", "dental",
        "ear cleaner", "eye cleaner", "wipes", "hygiene", "nail clipper",
        "sua tam", "cham soc", "ve sinh", "kem danh rang", "ban chai", "khan uot",
        "nho tai", "lau mat", "kiem cat mong", "cat mong",
    ),
    "accessory": (
        "leash", "collar", "harness", "bed", "cushion", "bowl", "stainless",
        "carrier", "backpack", "bag", "accessory", "accessories",
        "phu kien", "day dat", "vong co", "nem ngu", "bat an", "balo", "tui van chuyen",
    ),
}

_ALLERGY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chicken": ("allergic to chicken", "chicken allergy", "no chicken", "avoid chicken", "di ung ga", "khong an ga", "tranh thit ga"),
    "salmon": ("allergic to salmon", "allergic to fish", "no salmon", "no fish", "di ung ca", "di ung ca hoi", "tranh ca hoi"),
    "beef": ("allergic to beef", "no beef", "di ung bo", "tranh thit bo"),
    "grain": ("grain allergy", "allergic to grain", "grain free", "di ung ngu coc", "khong ngu coc"),
    "soy": ("allergic to soy", "soy allergy", "di ung dau nanh"),
}


@dataclass(slots=True)
class InterpretedTurn:
    """Result of deterministic NLU and safety classification for one user message."""

    intent: str
    safety_trigger: str | None = None
    slot_updates: PreferenceSlots = field(default_factory=PreferenceSlots)
    explicit_species_override: bool = False
    explicit_budget_override: bool = False
    comparison_codes: tuple[str, ...] = ()
    comparison_uses_context: bool = False
    comparison_count_hint: int = 3
    raw_query_normalized: str = ""


def _parse_price_bounds(text_normalized: str, raw_question: str) -> tuple[Decimal | None, Decimal | None, bool]:
    _, filters = catalog_filters(text_normalized)
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    found = False
    for price_filter in filters:
        if isinstance(price_filter, PriceFilter):
            found = True
            if price_filter.minimum is not None:
                budget_min = price_filter.minimum if budget_min is None else max(budget_min, price_filter.minimum)
            if price_filter.maximum is not None:
                budget_max = price_filter.maximum if budget_max is None else min(budget_max, price_filter.maximum)
    if found:
        return budget_min, budget_max, True

    # Support concise follow-ups like "8 million VND", "dưới 8tr", "tầm 300k", "500.000 vnd"
    bare_match = _BARE_BUDGET_RE.search(_normalize(raw_question))
    if bare_match:
        raw_num, unit = bare_match.groups()
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw_num):
            clean_num = raw_num.replace(".", "").replace(",", "")
        else:
            clean_num = raw_num.replace(",", ".")
        try:
            scale = (
                Decimal(1_000_000)
                if unit in {"trieu", "million", "tr", "m"}
                else (Decimal(1_000) if unit in {"nghin", "ngan", "k"} else Decimal(1))
            )
            amount = Decimal(clean_num) * scale
            if amount > 0:
                return None, amount, True
        except InvalidOperation:
            pass
    return None, None, False


def _extract_product_category(norm: str, raw_question: str) -> tuple[str | None, str | None]:
    # Strip explicit SKU codes (e.g. FOOD-999) before matching generic category words
    cleaned_norm = _normalize(_PRODUCT_CODE_RE.sub(" ", raw_question))

    # Vietnamese "cát" vs "cat" disambiguation
    if re.search(r"\bcát\b", raw_question, re.IGNORECASE) and not re.search(
        r"\bcát\s+lông\b", raw_question, re.IGNORECASE
    ):
        if "dau nanh" in cleaned_norm or "tofu" in cleaned_norm:
            return "litter", "tofu_litter"
        return "litter", "litter"

    for category, phrases in _PRODUCT_CATEGORY_KEYWORDS.items():
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", cleaned_norm):
                subtopic = phrase.replace(" ", "_")
                return category, subtopic
    return None, None


def _extract_species(norm: str, raw_question: str) -> str | None:
    tokens = set(re.findall(r"[a-z0-9]+", norm))
    has_cat = bool(tokens & {"meo", "cat", "cats", "kitten", "kittens", "feline"})
    # Guard against Vietnamese "cát vệ sinh" normalizing to "cat ve sinh"
    if has_cat and not (tokens & {"meo", "cats", "kitten", "kittens", "feline"}):
        if re.search(r"\bcát\b", raw_question, re.IGNORECASE) and not re.search(
            r"\b(?:mèo|cat|cats|kitten)\b", raw_question, re.IGNORECASE
        ):
            has_cat = False

    has_dog = bool(tokens & {"dog", "dogs", "puppy", "puppies", "canine", "cun"}) or bool(
        re.search(r"\bchó\b", raw_question, re.IGNORECASE)
    )
    if not has_dog and "cho" in tokens:
        # Unaccented Vietnamese: distinguish preposition "cho" ("for/give") from noun "cho" ("dog")
        if re.search(r"\b(?:con cho|nuoi cho|thuc an cho cho|do choi cho|giong cho|cho con|cho nho|cho lon)\b", norm):
            has_dog = True
    if has_cat and not has_dog:
        return "cat"
    if has_dog and not has_cat:
        return "dog"
    return None


def extract_preference_slots(raw_question: str) -> tuple[PreferenceSlots, bool, bool]:
    """Extract explicit preference slots from a single utterance without guessing."""
    norm = _normalize(raw_question)
    slots = PreferenceSlots()

    species = _extract_species(norm, raw_question)
    explicit_species = species is not None
    slots.species = species

    budget_min, budget_max, explicit_budget = _parse_price_bounds(norm, raw_question)
    slots.budget_min = budget_min
    slots.budget_max = budget_max

    # Living space
    if any(phrase in norm for phrase in ("apartment", "condo", "flat", "small space", "indoor", "can ho", "chung cu", "nha nho", "trong nha", "phong tro")):
        slots.living_space = "apartment"
    elif any(phrase in norm for phrase in ("house with yard", "big yard", "garden", "spacious house", "nha vuon", "co san", "nha rong")):
        slots.living_space = "house"

    # Temperament / energy level (exclude catalog SKU state phrases like "active products" / "products are active")
    is_sku_active_phrase = bool(
        re.search(r"\b(?:active\s+(?:products?|items?|customers?)|(?:products?|items?|customers?)\s+are\s+active)\b", norm)
    )
    if any(phrase in norm for phrase in ("calm", "quiet", "gentle", "low energy", "chill", "relaxed", "hien", "ngoan", "it van dong", "yen tinh", "on dinh", "it sua")):
        slots.temperament = "calm"
    elif not is_sku_active_phrase and any(phrase in norm for phrase in ("active", "energetic", "playful", "high energy", "nang dong", "nhanh nhen", "ham choi", "tinh nghich")):
        slots.temperament = "active"

    # Size preference
    if any(phrase in norm for phrase in ("small size", "small breed", "small dog", "small cat", "compact", "toy breed", "dang nho", "nho gon", "co nho", "giong nho")):
        slots.size_preference = "small"
    elif any(phrase in norm for phrase in ("medium size", "medium breed", "dang vua", "co vua", "trung binh")):
        slots.size_preference = "medium"
    elif any(phrase in norm for phrase in ("large size", "large breed", "big dog", "dang lon", "co lon", "giong lon")):
        slots.size_preference = "large"

    # Pet weight (e.g. "5 kg cat")
    weight_match = _WEIGHT_KG_RE.search(norm)
    if weight_match:
        try:
            weight_val = Decimal(weight_match.group(1).replace(",", "."))
            if Decimal("0.2") <= weight_val <= Decimal("90"):
                slots.pet_weight_kg = weight_val
        except InvalidOperation:
            pass

    # Life stage
    if any(phrase in norm for phrase in ("kitten", "kittens", "puppy", "puppies", "junior", "baby", "meo con", "cho con", "cun con", "thu non", "duoi 12 thang", "under 12 months")):
        slots.life_stage = "junior"
    elif any(phrase in norm for phrase in ("senior", "older", "elderly", "aging", "lon tuoi", "gia")):
        slots.life_stage = "senior"
    elif any(phrase in norm for phrase in ("adult", "grown", "truong thanh")):
        slots.life_stage = "adult"
    else:
        months_match = _AGE_MONTHS_RE.search(norm)
        years_match = _AGE_YEARS_RE.search(norm)
        if months_match:
            months = int(months_match.group(1))
            slots.life_stage = "junior" if months < 12 else "adult"
        elif years_match:
            years = int(years_match.group(1))
            slots.life_stage = "junior" if years < 1 else ("senior" if years >= 8 else "adult")

    # Coat / eye / sex / breed from existing pet_filter_spec
    # Strip Vietnamese "căn hộ" / "ủng hộ" before color parsing so "hộ" ("ho") never matches amber ("hổ phách").
    color_safe_question = re.sub(r"\b(?:căn\s+hộ|ủng\s+hộ|can\s+ho|ung\s+ho)\b", " ", raw_question, flags=re.IGNORECASE)
    pet_spec = pet_filter_spec(color_safe_question)
    if pet_spec.get("sex"):
        slots.sex = pet_spec["sex"]
    if pet_spec.get("coat_colors"):
        slots.coat_colors = tuple(tuple(group) for group in pet_spec["coat_colors"])
    if pet_spec.get("eye_colors"):
        slots.eye_colors = tuple(tuple(group) for group in pet_spec["eye_colors"])

    # Product category & subtopic
    prod_cat, prod_sub = _extract_product_category(norm, raw_question)
    slots.product_category = prod_cat
    slots.product_subtopic = prod_sub

    # Explicit session allergies
    detected_allergies: list[str] = []
    for allergen, phrases in _ALLERGY_KEYWORDS.items():
        if any(phrase in norm for phrase in phrases):
            detected_allergies.append(allergen)
    if detected_allergies:
        slots.allergies = tuple(detected_allergies)

    return slots, explicit_species, explicit_budget


def merge_preference_slots(
    current: PreferenceSlots,
    updates: PreferenceSlots,
    *,
    target_domain: str | None,
    explicit_species_override: bool,
    explicit_budget_override: bool,
) -> PreferenceSlots:
    """Merge turn slot updates into session context, handling overrides cleanly."""
    merged = current.clone()

    if target_domain in {"pet", "product"}:
        merged.active_domain = target_domain

    # When user switches species explicitly (e.g., from cat -> dog), clear species-specific coat/breed traits
    if explicit_species_override and updates.species and updates.species != merged.species:
        merged.species = updates.species
        merged.coat_colors = updates.coat_colors
        merged.eye_colors = updates.eye_colors
        merged.breed_terms = updates.breed_terms
    elif updates.species:
        merged.species = updates.species

    if explicit_budget_override:
        merged.budget_min = updates.budget_min
        merged.budget_max = updates.budget_max

    for attr in (
        "living_space",
        "temperament",
        "size_preference",
        "life_stage",
        "pet_weight_kg",
        "sex",
        "product_category",
        "product_subtopic",
    ):
        val = getattr(updates, attr)
        if val is not None:
            setattr(merged, attr, val)

    if updates.coat_colors:
        merged.coat_colors = updates.coat_colors
    if updates.eye_colors:
        merged.eye_colors = updates.eye_colors
    if updates.allergies:
        combined = list(dict.fromkeys([*merged.allergies, *updates.allergies]))
        merged.allergies = tuple(combined)

    return merged


def interpret_turn(raw_question: str, session_slots: PreferenceSlots | None = None) -> InterpretedTurn:
    """Classify safety boundaries, task intent, and preference slot updates."""
    norm = re.sub(r"\s+", " ", _normalize(raw_question)).strip()
    compact_norm = re.sub(r"[^a-z0-9]+", " ", norm).strip()

    # Allow bounded deterministic store capabilities (which never call LLMs or read history)
    # to answer legitimate embedded capability questions while ignoring adversarial prefixes.
    has_deterministic_store_cap = (
        assistant_capabilities.classify(raw_question) is not None
        or any(phrase in compact_norm for phrase in (
            "ban chay", "best selling", "best seller", "most sold", "sold the most",
            "top selling", "top product", "top item",
        ))
    )

    # 1. Safety & policy checks take highest precedence
    if not has_deterministic_store_cap and any(pattern in norm for pattern in _PROMPT_INJECTION_PATTERNS):
        return InterpretedTurn(
            intent="safety_refusal",
            safety_trigger="prompt_injection",
            raw_query_normalized=norm,
        )
    if any(re.search(pattern, norm) for pattern in _SQL_OR_CODE_PATTERNS):
        return InterpretedTurn(
            intent="safety_refusal",
            safety_trigger="sql_or_code",
            raw_query_normalized=norm,
        )
    if any(phrase in norm for phrase in _VET_EMERGENCY_PHRASES):
        slots, exp_sp, exp_bg = extract_preference_slots(raw_question)
        return InterpretedTurn(
            intent="vet_emergency",
            safety_trigger="vet_emergency",
            slot_updates=slots,
            explicit_species_override=exp_sp,
            explicit_budget_override=exp_bg,
            raw_query_normalized=norm,
        )
    if any(phrase in norm for phrase in _VET_MEDICAL_BOUNDARY_PHRASES):
        slots, exp_sp, exp_bg = extract_preference_slots(raw_question)
        return InterpretedTurn(
            intent="vet_medical_boundary",
            safety_trigger="vet_medical_boundary",
            slot_updates=slots,
            explicit_species_override=exp_sp,
            explicit_budget_override=exp_bg,
            raw_query_normalized=norm,
        )
    if any(phrase in norm for phrase in _WRITE_ACTION_PHRASES):
        return InterpretedTurn(
            intent="safety_refusal",
            safety_trigger="write_action",
            raw_query_normalized=norm,
        )

    # 2. Explicit reset request
    if any(phrase in norm for phrase in _RESET_PHRASES):
        return InterpretedTurn(intent="reset_context", raw_query_normalized=norm)

    slots, exp_species, exp_budget = extract_preference_slots(raw_question)

    # 3. Product Comparison intent
    codes = tuple(dict.fromkeys(code.upper() for code in _PRODUCT_CODE_RE.findall(raw_question)))
    has_compare_word = any(phrase in f" {norm} " for phrase in _COMPARISON_PHRASES)
    if has_compare_word and (
        len(codes) >= 2
        or slots.product_category is not None
        or any(word in norm for word in ("product", "products", "item", "items", "san pham", "mat hang", "loai nay", "ba san pham", "hai san pham", "these two", "these three", "top 3", "food", "thuc an", "cat ve sinh", "litter"))
    ):
        count_hint = 2 if any(w in norm for w in ("two", "2", "hai")) else (
            4 if any(w in norm for w in ("four", "4", "bon")) else 3
        )
        uses_context = len(codes) < 2 and any(
            phrase in norm
            for phrase in ("these", "those", "them", "above", "recommended", "nay", "tren", "vua goi y")
        )
        return InterpretedTurn(
            intent="product_comparison",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            comparison_codes=codes,
            comparison_uses_context=uses_context,
            comparison_count_hint=count_hint,
            raw_query_normalized=norm,
        )

    # 4. Operational Insights / Forecast (let deterministic store tools win before generic NLP)
    if any(phrase in compact_norm for phrase in _FORECAST_PHRASES):
        return InterpretedTurn(
            intent="inventory_forecast",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    if assistant_capabilities.classify(raw_question) is not None:
        return InterpretedTurn(
            intent="legacy_store_query",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    if any(phrase in compact_norm for phrase in (
        "ban chay", "best selling", "best seller", "most sold", "sold the most",
        "top selling", "top product", "top item", "doanh thu", "revenue",
    )):
        return InterpretedTurn(
            intent="legacy_store_query",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    # 5. Trusted Pet-Care Knowledge Base questions
    has_knowledge_signal = any(phrase in norm for phrase in _KNOWLEDGE_SIGNALS)
    has_explicit_shopping_intent = (
        exp_budget
        or any(
            phrase in norm
            for phrase in (
                "recommend", "suggest", "which food should", "what products", "suitable products",
                "product", "products", "san pham", "mat hang", "goi y", "chon mua san pham", "mua gi",
            )
        )
    )
    if has_knowledge_signal and not has_explicit_shopping_intent:
        return InterpretedTurn(
            intent="knowledge_qa",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    # 6. Follow-up continuation when session is awaiting clarification or has active domain
    has_advisory_signal = any(phrase in norm for phrase in _ADVISORY_VERBS)
    has_lifestyle_or_trait = any((
        slots.living_space,
        slots.temperament,
        slots.size_preference,
        slots.life_stage,
        slots.pet_weight_kg is not None,
        slots.allergies,
    ))

    # Determine whether utterance is about products vs pets
    mentions_product_nouns = slots.product_category is not None or any(
        re.search(rf"\b{re.escape(w)}\b", norm)
        for w in ("product", "products", "item", "items", "san pham", "mat hang", "do dung")
    )
    mentions_pet_adoption = (
        not mentions_product_nouns
        and (
            slots.species is not None
            or any(
                phrase in norm
                for phrase in (
                    "adopt", "pet suitable", "suitable pet", "choose a pet", "which pet",
                    "recommend a pet", "looking for a pet", "a pet to buy",
                    "nuoi thu cung", "chon thu cung", "thu cung phu hop", "muon nuoi", "tim thu cung",
                )
            )
        )
    )

    if session_slots is not None and session_slots.awaiting_clarification_for in {"pet", "product"}:
        target = session_slots.awaiting_clarification_for
        # If user answered with slot values (e.g. "Calm, below 8 million VND" or "Adult cat, under 400k")
        if mentions_product_nouns and target == "pet":
            target = "product"
        if slots.has_any_constraint() or exp_budget or exp_species:
            return InterpretedTurn(
                intent=f"{target}_recommendation",
                slot_updates=slots,
                explicit_species_override=exp_species,
                explicit_budget_override=exp_budget,
                raw_query_normalized=norm,
            )

    # Contextual follow-up refinement (e.g., "What about under 5 million?" or "Còn loại cho chó thì sao?")
    is_refinement = bool(
        session_slots is not None
        and session_slots.active_domain in {"pet", "product"}
        and not mentions_product_nouns
        and not mentions_pet_adoption
        and (exp_budget or has_lifestyle_or_trait)
    )
    if is_refinement and session_slots is not None:
        return InterpretedTurn(
            intent=f"{session_slots.active_domain}_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    if (
        session_slots is not None
        and session_slots.active_domain == "product"
        and exp_species
        and not any(p in norm for p in ("available", "dang ban", "muon nuoi", "want a "))
        and any(p in norm for p in ("what about", "how about", "con cho", "con meo", "the con", "doi sang"))
    ):
        return InterpretedTurn(
            intent="product_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    # 7. Personalized Product Recommendations
    if mentions_product_nouns and (has_advisory_signal or has_lifestyle_or_trait or exp_budget or exp_species):
        return InterpretedTurn(
            intent="product_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    # 8. Pet Matching & Adoption/Purchase Advice
    if mentions_pet_adoption and (has_advisory_signal or has_lifestyle_or_trait):
        return InterpretedTurn(
            intent="pet_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    # General care questions with "why / how / should / can my dog/cat..."
    if (exp_species or any(w in norm for w in ("pet", "thu cung"))) and any(
        phrase in norm
        for phrase in (
            "how ", "should i ", "can my ", "is it safe", "tips for", "guide",
            "lam sao", "nhu the nao", "co nen", "luu y", "cham soc", "nuoi ",
        )
    ) and not mentions_product_nouns:
        return InterpretedTurn(
            intent="knowledge_qa",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    return InterpretedTurn(
        intent="legacy_store_query",
        slot_updates=slots,
        explicit_species_override=exp_species,
        explicit_budget_override=exp_budget,
        raw_query_normalized=norm,
    )
