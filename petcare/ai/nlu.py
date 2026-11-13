"""Deterministic bilingual (VI/EN) NLU, safety guardrails, and preference slot extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re

from petcare.ai.contracts import PreferenceSlots
from petcare.ai.safety_triage import evaluate_veterinary_safety
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

# Non-monetary numeric spans stripped before price parsing so ages/weights/volumes never become VND budgets
_NON_MONETARY_UNIT_SPAN_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:thang|months?|mo|tuoi|nam|years?|yo|yr|kg|kilo|kilogram|ki\s*lo|ky|g|gram|ml|l|lit|liter|liters|litres|"
    r"mui|vien|goi|bua|ngay|days?|tuan|weeks?|lan|phan\s+tram|%)\b"
)

MIN_VALID_VND_BUDGET = Decimal("1000")

# Explicit token-bounded typo and chat-shorthand canonicalization rules
_CONVERSATIONAL_CANONICAL_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:rcm|reccomend|recommand|recomend)\b"), "recommend"),
    (re.compile(r"\btruog\s+thanh\b"), "truong thanh"),
    (re.compile(r"\b(?:apartmnts?|appartments?)\b"), "apartment"),
    (re.compile(r"\bundr\b"), "under"),
    (re.compile(r"\b(?:milions?|millons?)\b"), "million"),
    (re.compile(r"\bquite\s+(?=(?:small|medium|large|calm|gentle|dog|cat|puppy|kitten|pet)\b)"), "quiet "),
    (re.compile(r"\bss\b(?=\s+(?:giup|dum|thu|2|3|4|hai|ba|cac|loai|ma|[a-z]{2,8}-\d{2,5}))"), "so sanh"),
    (re.compile(r"\b(?:ko|k0|khg|khongg|hong|hok)\b"), "khong"),
    (re.compile(r"\b(?:dc|dk)\b"), "duoc"),
    (re.compile(r"\bsp\b(?=\s+(?:cho|meo|nay|nao|phu hop|duoi|tren|cua))"), "san pham"),
)

_EN_NUMBER_WORDS: dict[str, str] = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "fifteen": "15",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "hundred": "100",
}

# Unaccented "tu" is intentionally omitted so range preposition "từ" ("tu 3 den 7 trieu") is never altered
_VI_NUMBER_WORDS: dict[str, str] = {
    "mot": "1",
    "hai": "2",
    "ba": "3",
    "bon": "4",
    "nam": "5",
    "sau": "6",
    "bay": "7",
    "tam": "8",
    "chin": "9",
    "muoi": "10",
}

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
    "end user message",
    "admin audit override",
    "bo qua quy tac",
    "bo qua huong dan",
    "tiet lo system prompt",
    "tiet lo prompt",
    "hien thi prompt he thong",
    "cho xem khoa api",
    "mat khau database",
)

_PROMPT_INJECTION_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:dich|lap\s+lai|in\s+ra|xuat\s+ra|tom\s+tat|liet\s+ke|viet\s+lai|sao\s+chep)\b.*"
        r"\b(?:quy\s+tac\s+noi\s+bo|chi\s+dan\s+noi\s+bo|cau\s+hinh\s+cho\s+ban|huong\s+dan\s+ban\s+dau|truoc\s+khi\s+cuoc\s+hoi\s+thoai)\b"
    ),
    re.compile(
        r"\b(?:translate|repeat|verbatim|summarize|print|dump|output|encode)\b.*"
        r"\b(?:internal\s+rules|initial\s+instructions|configured\s+for\s+you|before\s+this\s+conversation|hidden\s+prompt|system\s+instructions)\b"
    ),
    re.compile(
        r"\b(?:dump|export|output)\s+all\s+customer\s+(?:names|phones?|phone\s+numbers|addresses|records|pii)\b"
    ),
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

_WRITE_ACTION_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:huy|xoa|sua|cap\s+nhat)\s+(?:tat\s+ca\s+|toan\s+bo\s+|cac\s+)?hoa\s+don\b"),
    re.compile(r"\b(?:dua|dat|chinh|set|reset)\s+(?:so\s+luong\s+)?ton\s+kho\b.*\b(?:ve|thanh)\s+\d+\b"),
    re.compile(r"\b(?:cancel|void|delete)\s+(?:all\s+|today\s+s\s+)?invoices?\b"),
    re.compile(r"\b(?:zero\s+out|wipe|reset)\s+(?:all\s+)?(?:stock|inventory)\b"),
)

# Unsupported non-dog/cat exotic species
_EXOTIC_SPECIES_RE = re.compile(
    r"\b(?:iguana|reptiles?|snakes?|turtles?|tortoises?|parrots?|aquariums?|hamsters?|rabbits?|bunnies|"
    r"sugar\s+gliders?|chinchillas?|hedgehogs?|ferrets?|guinea\s+pigs?|tarantulas?|"
    r"bo\s+sat|ky\s+nhong|nuoi\s+ran|con\s+ran|nuoi\s+rua|rua\s+canh|con\s+rua|chim\s+vet|con\s+vet|nuoi\s+chim|"
    r"ca\s+canh|be\s+ca|chuot\s+hamster|chuot\s+lang|soc\s+bay|nhim\s+kieng|chon\s+suong|tho\s+kieng|nuoi\s+tho)\b"
)

# Specific laboratory, clinical-record, batch/expiry, or factory fields not stored in catalog/pet schemas
_UNDOCUMENTED_ATTRIBUTE_RE = re.compile(
    r"\b(?:dam\s+tho|chat\s+beo(?:\s+tho)?|chat\s+xo(?:\s+tho)?|tro\s+tho|"
    r"crude\s+(?:protein|fat|fiber|fibre|ash)|moisture\s+percentage|guaranteed\s+analysis|kcal\s+per\s+(?:kg|cup|100g)|"
    r"phan\s+tram\s+(?:dam|beo|chat\s+beo|chat\s+xo|do\s+am|canxi|photpho)|"
    r"ham\s+luong\s+(?:dam|beo|taurine|canxi|photpho|omega|tro)|taurine|"
    r"bao\s+nhieu\s+(?:mg|%|phan\s+tram)\s+(?:taurine|dam|chat\s+beo|chat\s+xo|canxi|omega|glucosamine)|"
    r"tiem\s+du\s+\d*\s*mui|mui\s+vaccine|vaccine\s+\d+\s+benh|ngay\s+tiem|lich\s+su\s+tiem\s+chung|vaccination\s+dates?|vaccine\s+records?|"
    r"thuoc\s+tay\s+giun\s+hang|dewormer\s+brand|so\s+tiem|microchip|gia\s+pha|pedigree|"
    r"han\s+su\s+dung|ngay\s+het\s+han|so\s+lo\s+san\s+xuat|expiration\s+date|expiry\s+date|batch\s+number|lot\s+number|"
    r"what\s+factory|country\s+manufactured|nha\s+may\s+san\s+xuat|silica\s+dust|dust\s+percentage|phan\s+tram\s+bui\s+min|lab[-\s]certified)\b"
)

# Slot removal / correction patterns
_CLEAR_BUDGET_RE = re.compile(
    r"\b(?:bo|xoa|huy|go|khong\s+can|khong\s+dat)\s+(?:gioi\s+han\s+|muc\s+|tran\s+|rang\s+buoc\s+|loc\s+)?(?:gia|ngan\s+sach|chi\s+phi)\b"
    r"|\b(?:bo|xoa|huy|go)\s+(?:muc\s+|tran\s+|gioi\s+han\s+)\d+(?:[.,]\d+)?\s*(?:trieu|tr|cu|xi|nghin|ngan|k|vnd|dong)\b"
    r"|\b(?:khong\s+gioi\s+han|khong\s+quan\s+trong|bat\s+ke)\s+(?:muc\s+)?(?:gia|ngan\s+sach)\b"
    r"|\bgia\s+nao\s+cung\s+duoc\b"
    r"|\b(?:scratch|remove|clear|drop|lift|no)\s+(?:the\s+|my\s+|any\s+|old\s+|previous\s+)?(?:\d+(?:[.,]\d+)?\s*(?:million|thousand|m|k|vnd)\s+)?(?:budget|price)?\s*(?:limit|cap|ceiling|filter|constraint|restriction)\b"
    r"|\b(?:scratch|remove|clear|drop|lift|no)\s+(?:the\s+|my\s+|any\s+)?(?:budget|price)\b"
    r"|\bregardless\s+of\s+price\b|\bany\s+price\s+is\s+fine\b"
)

# Strips only the removal clause (including any explicitly cited old cap like "drop the 200k limit")
# while preserving any replacement clause ("... to under 8 million VND", "... nâng lên dưới 500k").
_OLD_BUDGET_REMOVAL_SPAN_RE = re.compile(
    r"\b(?:bo|xoa|huy|go|khong\s+can|khong\s+dat)\s+(?:gioi\s+han\s+|muc\s+|tran\s+|rang\s+buoc\s+|loc\s+)?(?:gia|ngan\s+sach|chi\s+phi)?"
    r"(?:\s*\d+(?:[.,]\d+)?\s*(?:trieu|tr|cu|xi|nghin|ngan|k|vnd|dong))?(?:\s+(?:cu|do|nay|kia|truoc|ban\s+dau))?\b"
    r"|\b(?:khong\s+gioi\s+han|khong\s+quan\s+trong|bat\s+ke)\s+(?:muc\s+)?(?:gia|ngan\s+sach)\b"
    r"|\bgia\s+nao\s+cung\s+duoc\b"
    r"|\b(?:scratch|remove|clear|drop|lift|no)\s+(?:the\s+|my\s+|any\s+|old\s+|previous\s+)?"
    r"(?:\d+(?:[.,]\d+)?\s*(?:million|thousand|m|k|vnd)\s+)?(?:budget|price)?\s*(?:limit|cap|ceiling|filter|constraint|restriction)?\b"
    r"|\bregardless\s+of\s+price\b|\bany\s+price\s+is\s+fine\b"
)

_CLEAR_ALL_ALLERGIES_RE = re.compile(
    r"\b(?:bo|xoa|huy|go)\s+(?:bo\s+loc\s+|tat\s+ca\s+)?di\s+ung\b"
    r"|\bkhong\s+(?:bi\s+|con\s+|he\s+)?di\s+ung\s+(?:gi|nao|thuc\s+an\s+nao)\b"
    r"|\b(?:remove|clear|drop)\s+(?:all\s+|the\s+)?allergy\s+(?:filters?|restrictions?)\b"
    r"|\bno\s+food\s+allergies\b"
)

_ALLERGEN_TOKENS: dict[str, str] = {
    "chicken": r"(?:thit\s+ga|vi\s+ga|ga|chicken)",
    "salmon": r"(?:ca\s+hoi|ca|salmon|fish)",
    "beef": r"(?:thit\s+bo|vi\s+bo|beef)",
    "grain": r"(?:ngu\s+coc|grain)",
    "soy": r"(?:dau\s+nanh|soy)",
}

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
    "head to head",
    "head-to-head",
    "cost per liter",
    "cost per litre",
    "cost per kg",
    "cost per 100g",
    "price per kg",
    "price per liter",
    "better unit value",
    "so sanh",
    "khac nhau giua",
    "doi chieu",
    "dat len ban can",
    "loi tien hon",
    "kinh te hon tren moi",
    "tinh ra re hon",
    "tren moi ky",
    "tren moi lit",
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
    "how many litter boxes",
    "new diet",
    "transition",
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
    "chuyen doi thuc an",
    "7-10 ngay",
    "7 10 ngay",
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
    "gay ngo doc",
    "ngo doc thuc pham",
    "khong nen cho",
    "khong nen cho an gi",
    "luu y khi chon mua",
    "kinh nghiem nuoi",
)

# General care / hazard predicate-question patterns (handles word-order variations like "foods ... are toxic")
_KNOWLEDGE_QUESTION_RE = re.compile(
    r"\b(?:foods?|plants?|flowers?|items?|substances?|ingredients?|things?|thuc\s+pham|do\s+an|mon\s+an|cay|hoa|chat)\b"
    r".*\b(?:toxic|poisonous|unsafe|dangerous|harmful|bad\s+for|gay\s+ngo\s+doc|doc\s+hai|nguy\s+hiem|can\s+tranh|khong\s+nen\s+cho)\b"
    r"|\b(?:toxic|poisonous|unsafe|dangerous|harmful)\s+(?:household\s+|human\s+|common\s+)?(?:foods?|plants?|items?|substances?)\b"
    r"|\b(?:how\s+often|how\s+many\s+litter\s+boxes|n\s*\+\s*1|7[-\s]*10\s*(?:days?|ngay))\b"
)

# Explicit instructional / safety-question markers required when pairing KB retrieval with shopping in one turn
_EXPLICIT_CARE_QUESTION_RE = re.compile(
    r"\b(?:how\s+to|how\s+many|how\s+often|how\s+do\s+i|how\s+should\s+i|explain\s+how|introduce\s+a\s+new\s+diet|"
    r"transition.*food|7[-\s]*10\s*(?:days?|ngay)|n\s*\+\s*1|"
    r"cach\s+(?:chuyen\s+doi|cham\s+soc|chuan\s+bi|tap|cho\s+an|ve\s+sinh)|nhu\s+the\s+nao|can\s+bao\s+nhieu\s+khay|may\s+khay|"
    r"quy\s+tac\s+khay|co\s+nguy\s+hiem\s+khong|co\s+doc\s+khong|co\s+an\s+duoc\s+khong|"
    r"(?:which|what)\s+(?:household\s+|human\s+|common\s+)?(?:foods?|plants?|items?)\s+(?:are|is)\s+(?:toxic|poisonous|unsafe|dangerous)|"
    r"(?:is|are)\s+[a-z0-9\s]{1,20}\s+(?:toxic|poisonous|unsafe|dangerous))\b"
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
    "moi nhan nuoi",
    "nha minh co",
    "nha em co",
    "boss nha",
    "ben shop co",
    "on ap",
    "toi co meo",
    "toi co cho",
)

_PRODUCT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "food": (
        "food", "foods", "kibble", "dry food", "wet food", "pate", "pouch", "treat", "treats",
        "snack", "snacks", "supplement", "calcium", "nutrition", "feed",
        "thuc an", "hat kho", "hat cho", "hat meo", "bich hat", "hat ca hoi", "hat ga",
        "an dam", "banh thuong", "dinh duong", "bo sung canxi",
    ),
    "toy": (
        "toy", "toys", "feather wand", "teaser", "plaything", "chew toy",
        "do choi", "can cau meo", "bong do choi",
    ),
    "litter": (
        "litter", "litters", "clumping", "bentonite", "tofu litter", "soy litter",
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
    "chicken": ("allergic to chicken", "chicken allergy", "no chicken", "avoid chicken", "di ung ga", "di ung thit ga", "khong an ga", "tranh thit ga"),
    "salmon": ("allergic to salmon", "allergic to fish", "no salmon", "no fish", "di ung ca", "di ung ca hoi", "tranh ca hoi"),
    "beef": ("allergic to beef", "no beef", "di ung bo", "di ung thit bo", "tranh thit bo"),
    "grain": ("grain allergy", "allergic to grain", "grain free", "di ung ngu coc", "khong ngu coc"),
    "soy": ("allergic to soy", "soy allergy", "di ung dau nanh"),
}

_ALLERGY_REACTION_CUE_RE = re.compile(
    r"\b(?:di\s+ung|bi\s+ngua|noi\s+man|kich\s+ung|rung\s+long\s+man|khong\s+hop|itchy|itching|rash|hives|intolerant|sensitive\s+to)\b"
)


@dataclass(slots=True)
class InterpretedTurn:
    """Result of deterministic NLU and safety classification for one user message."""

    intent: str
    safety_trigger: str | None = None
    safety_category: str | None = None
    slot_updates: PreferenceSlots = field(default_factory=PreferenceSlots)
    explicit_species_override: bool = False
    explicit_budget_override: bool = False
    clear_budget: bool = False
    removed_allergies: tuple[str, ...] = ()
    clear_all_allergies: bool = False
    comparison_codes: tuple[str, ...] = ()
    comparison_uses_context: bool = False
    comparison_count_hint: int = 3
    operational_period: str | None = None
    secondary_operational_tool: str | None = None
    raw_query_normalized: str = ""


def _canonicalize_for_nlu(raw_question: str) -> str:
    norm = re.sub(r"\s+", " ", _normalize(raw_question)).strip()
    for pattern, replacement in _CONVERSATIONAL_CANONICAL_RULES:
        norm = pattern.sub(replacement, norm)
    return re.sub(r"\s+", " ", norm).strip()


def _quantize_vnd(value: Decimal | None) -> Decimal | None:
    """Normalize integral VND Decimal values so `Decimal('5500000.0')` becomes `Decimal('5500000')`."""
    if value is None:
        return None
    if value == value.to_integral_value():
        return Decimal(int(value))
    return value.normalize()


def _normalize_conversational_money_text(norm_canon: str, raw_question: str) -> str:
    """Convert informal VI/EN monetary expressions into canonical `<number> <unit>` strings."""
    txt = _NON_MONETARY_UNIT_SPAN_RE.sub(" ", norm_canon)

    # Accented Vietnamese "tư triệu" / "tư củ" -> 4 (without touching unaccented "từ" in ranges)
    if re.search(r"\btư\s*(?:triệu|củ|xị|trăm)\b", raw_question, re.IGNORECASE):
        txt = re.sub(r"\btu\s+(?=(?:trieu|cu|xi|tram)\b)", "4 ", txt)

    # Quantity idioms ("nửa chục triệu" -> 5 triệu, "một chục triệu" -> 10 triệu, "nửa triệu" -> 500 k)
    txt = re.sub(r"\bnua\s+chuc\s+(?:trieu|tr|cu)\b", "5 trieu", txt)
    txt = re.sub(r"\bnua\s+chuc\s+(?:ngan|nghin|k|canh)\b", "50 k", txt)
    txt = re.sub(r"\bmot\s+chuc\s+(?:trieu|tr|cu)\b", "10 trieu", txt)
    txt = re.sub(r"\bnua\s+(?:trieu|cu)\b", "500 k", txt)

    # Convert VI/EN number words BEFORE half-unit ("rưỡi" / "and a half") rules so "năm củ rưỡi" -> 5.5 trieu
    en_words_alt = "|".join(_EN_NUMBER_WORDS.keys())
    txt = re.sub(
        rf"\b({en_words_alt})\s+and\s+a\s+half\s+million\b",
        lambda m: f"{int(_EN_NUMBER_WORDS[m.group(1)])}.5 million",
        txt,
    )
    txt = re.sub(r"\ba\s+million\s+and\s+a\s+half\b", "1.5 million", txt)
    txt = re.sub(
        rf"\b({en_words_alt})\s+(to|and|-)\s+({en_words_alt})\s+(million|thousand|m|k)\b",
        lambda m: f"{_EN_NUMBER_WORDS[m.group(1)]} {m.group(2)} {_EN_NUMBER_WORDS[m.group(3)]} {'k' if m.group(4) == 'thousand' else m.group(4)}",
        txt,
    )
    txt = re.sub(
        rf"\b({en_words_alt})\s+hundred\s+thousand\b",
        lambda m: f"{int(_EN_NUMBER_WORDS[m.group(1)]) * 100} k",
        txt,
    )
    txt = re.sub(
        rf"\b({en_words_alt})\s+(million|thousand)\b",
        lambda m: f"{_EN_NUMBER_WORDS[m.group(1)]} {'k' if m.group(2) == 'thousand' else 'million'}",
        txt,
    )

    vi_words_alt = "|".join(_VI_NUMBER_WORDS.keys())
    txt = re.sub(
        rf"\b({vi_words_alt})\s+(trieu|tr|cu|xi|tram)\b",
        lambda m: f"{_VI_NUMBER_WORDS[m.group(1)]} {m.group(2)}",
        txt,
    )

    # Half-unit suffixes ("5 củ rưỡi" -> 5.5 trieu, "3 xị rưỡi" -> 350 k, "2 trăm rưỡi" -> 250 k, "trăm rưỡi" -> 150 k)
    txt = re.sub(
        r"\b(\d+)\s*(?:trieu|tr|cu)\s+ruoi\b",
        lambda m: f"{int(m.group(1))}.5 trieu",
        txt,
    )
    txt = re.sub(
        r"\b(\d+)\s*(?:xi|tram)\s+ruoi\b",
        lambda m: f"{int(m.group(1)) * 100 + 50} k",
        txt,
    )
    txt = re.sub(r"(?<!\d\s)\btram\s+ruoi\b", "150 k", txt)
    txt = re.sub(
        r"\b(\d+)\s+tram\s+(?:nghin|ngan|k|canh)\b",
        lambda m: f"{int(m.group(1)) * 100} k",
        txt,
    )

    # Slang units: "xị" = 100,000 VND (100k), "củ" = 1,000,000 VND (1 triệu), "cành" = 1,000 VND (1k)
    def _replace_xi(match: re.Match[str]) -> str:
        val = Decimal(match.group(1).replace(",", ".")) * Decimal(100)
        num_str = str(int(val)) if val == int(val) else format(val, "f").rstrip("0").rstrip(".")
        return f"{num_str} k"

    txt = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*xi\b", _replace_xi, txt)
    txt = re.sub(r"\b(\d+(?:[.,]\d+)?)\s*cu\b", r"\1 trieu", txt)
    txt = re.sub(r"\b(\d{2,4})\s*canh\b", r"\1 k", txt)

    # Suffix floor/ceiling idioms ("3 triệu trở lên" -> "tu 3 trieu", "5 triệu quay đầu / đổ lại" -> "toi da 5 trieu")
    txt = re.sub(
        r"\b(\d+(?:[.,]\d+)?\s*(?:trieu|million|tr|m|nghin|ngan|k))\s+(?:tro\s+len|do\s+len|upwards|or\s+more)\b",
        r"tu \1",
        txt,
    )
    txt = re.sub(
        r"\b(\d+(?:[.,]\d+)?\s*(?:trieu|million|tr|m|nghin|ngan|k))\s+(?:quay\s+dau|do\s+lai|tro\s+xuong|do\s+xuong)\b",
        r"toi da \1",
        txt,
    )

    # Canonicalize "around 5 to 7 million" / "tam 3 den 5 trieu" into "between ... and ..."
    txt = re.sub(
        r"\b(?:around|about|tam|co|loanh\s+quanh)\s+(\d+(?:[.,]\d+)?(?:\s*(?:trieu|million|tr|m|nghin|ngan|k))?\s*(?:to|and|den|toi|-)\s*\d+(?:[.,]\d+)?\s*(?:trieu|million|tr|m|nghin|ngan|k))\b",
        r"between \1",
        txt,
    )

    return re.sub(r"\s+", " ", txt).strip()


def _parse_price_bounds(text_normalized: str, raw_question: str) -> tuple[Decimal | None, Decimal | None, bool]:
    money_text = _normalize_conversational_money_text(text_normalized, raw_question)
    _, filters = catalog_filters(money_text)
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    found = False
    for price_filter in filters:
        if isinstance(price_filter, PriceFilter):
            min_ok = price_filter.minimum is not None and price_filter.minimum >= MIN_VALID_VND_BUDGET
            max_ok = price_filter.maximum is not None and price_filter.maximum >= MIN_VALID_VND_BUDGET
            if not (min_ok or max_ok):
                continue
            found = True
            if min_ok and price_filter.minimum is not None:
                budget_min = price_filter.minimum if budget_min is None else max(budget_min, price_filter.minimum)
            if max_ok and price_filter.maximum is not None:
                budget_max = price_filter.maximum if budget_max is None else min(budget_max, price_filter.maximum)
    if found:
        return _quantize_vnd(budget_min), _quantize_vnd(budget_max), True

    # Support concise follow-ups & bare ceiling amounts ("tầm 7tr", "8 million VND")
    bare_match = _BARE_BUDGET_RE.search(money_text)
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
            if amount >= MIN_VALID_VND_BUDGET:
                return None, _quantize_vnd(amount), True
        except InvalidOperation:
            pass
    return None, None, False


def detect_slot_removals(raw_question: str) -> tuple[bool, tuple[str, ...], bool]:
    """Detect explicit requests to remove budget caps or clear previously declared allergies."""
    norm = _canonicalize_for_nlu(raw_question)
    clear_budget = bool(_CLEAR_BUDGET_RE.search(norm))
    clear_all_allergies = bool(_CLEAR_ALL_ALLERGIES_RE.search(norm))
    removed: list[str] = []

    for allergen, tok_pat in _ALLERGEN_TOKENS.items():
        if (
            re.search(rf"\b(?:khong|chua\s+tung|het)\s+(?:bi\s+|con\s+|he\s+)?di\s+ung\s+(?:voi\s+)?{tok_pat}\b", norm)
            or re.search(rf"\bnot\s+allergic\s+to\s+{tok_pat}\b", norm)
            or re.search(rf"\b(?:bo|xoa|huy|go)\s+(?:loc\s+|bo\s+loc\s+|han\s+che\s+|di\s+ung\s+)*(?:di\s+ung\s+)?{tok_pat}\b", norm)
            or re.search(rf"\b(?:remove|clear|drop|scratch)\s+(?:the\s+|my\s+)?{tok_pat}\s+(?:allergy|filter|restriction)\b", norm)
            or re.search(rf"\b{tok_pat}\s+(?:is\s+fine|is\s+ok|is\s+okay|is\s+safe|an\s+duoc|khong\s+sao|binh\s+thuong)\b", norm)
            or re.search(rf"\ban\s+{tok_pat}\s+(?:binh\s+thuong|duoc\s+roi|khong\s+sao)\b", norm)
        ):
            removed.append(allergen)

    return clear_budget, tuple(dict.fromkeys(removed)), clear_all_allergies


def _extract_product_category(norm: str, raw_question: str) -> tuple[str | None, str | None]:
    # Strip explicit SKU codes (e.g. FOOD-999) before matching generic category words
    cleaned_norm = _canonicalize_for_nlu(_PRODUCT_CODE_RE.sub(" ", raw_question))

    # Vietnamese "cát" vs "cat" disambiguation (excluding exotic dust-baths like "tắm cát")
    if re.search(r"\bcát\b", raw_question, re.IGNORECASE) and not re.search(
        r"\b(?:cát\s+lông|tắm\s+cát)\b", raw_question, re.IGNORECASE
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
    has_cat_slang = bool(re.search(r"\b(?:hoang\s+thuong|quang\s+thuong|mon\s+leo)\b", norm))
    has_cat = has_cat_slang or bool(tokens & {"meo", "cat", "cats", "kitten", "kittens", "feline"})
    # Guard against Vietnamese "cát vệ sinh" normalizing to "cat ve sinh"
    if has_cat and not has_cat_slang and not (tokens & {"meo", "cats", "kitten", "kittens", "feline"}):
        if re.search(r"\bcát\b", raw_question, re.IGNORECASE) and not re.search(
            r"\b(?:mèo|cat|cats|kitten)\b", raw_question, re.IGNORECASE
        ):
            has_cat = False

    has_dog = bool(tokens & {"dog", "dogs", "puppy", "puppies", "canine", "cun"}) or bool(
        re.search(r"\bchó\b", raw_question, re.IGNORECASE)
    )
    if not has_dog and "cho" in tokens:
        # Unaccented Vietnamese: distinguish preposition "cho" ("for/give") from noun "cho" ("dog")
        if re.search(
            r"\b(?:con\s+cho|nuoi\s+cho|thuc\s+an\s+cho\s+cho|banh\s+thuong.*cho\s+cho|do\s+choi\s+cho\s+cho|giong\s+cho|cho\s+con|cho\s+nho|cho\s+lon|cho\s+an\s+nho)\b",
            norm,
        ):
            has_dog = True
    if has_cat and not has_dog:
        return "cat"
    if has_dog and not has_cat:
        return "dog"
    return None


def extract_preference_slots(raw_question: str) -> tuple[PreferenceSlots, bool, bool]:
    """Extract explicit preference slots from a single utterance without guessing."""
    norm = _canonicalize_for_nlu(raw_question)
    slots = PreferenceSlots()

    species = _extract_species(norm, raw_question)
    explicit_species = species is not None
    slots.species = species

    clear_budget, removed_allergies, clear_all_allergies = detect_slot_removals(raw_question)
    budget_source_norm = _OLD_BUDGET_REMOVAL_SPAN_RE.sub(" ", norm) if clear_budget else norm
    budget_min, budget_max, explicit_budget = _parse_price_bounds(budget_source_norm, raw_question)
    slots.budget_min = budget_min
    slots.budget_max = budget_max

    # Living space (check apartment vs house-with-yard/spacious townhouse)
    if re.search(
        r"\b(?:nha\s+vuon|co\s+san|san\s+vuon|nha\s+rong|nha\s+pho\s+rong|rong\s+rai|nha\s+mat\s+dat|"
        r"house\s+with\s+yard|big\s+yard|garden|spacious\s+house|townhouse)\b",
        norm,
    ):
        slots.living_space = "house"
    elif re.search(
        r"\b(?:apartment|condo|studio\s+flat|flat|small\s+space|indoor|can\s+ho|chung\s+cu|nha\s+nho|"
        r"trong\s+nha|phong\s+tro|nha\s+tro|o\s+tro|tro\s+nho|khong\s+gian\s+hep)\b",
        norm,
    ):
        slots.living_space = "apartment"

    # Temperament / energy level (exclude catalog SKU state phrases like "active products")
    is_sku_active_phrase = bool(
        re.search(r"\b(?:active\s+(?:products?|items?|customers?)|(?:products?|items?|customers?)\s+are\s+active)\b", norm)
    )
    if not is_sku_active_phrase and re.search(
        r"\b(?:active|energetic|playful|high\s+energy|nang\s+dong|hieu\s+dong|chay\s+nhay|nhanh\s+nhen|ham\s+choi|tinh\s+nghich)\b",
        norm,
    ):
        slots.temperament = "active"
    elif re.search(
        r"\b(?:calm|quiet|gentle|low\s+energy|chill|relaxed|hien|ngoan|diem\s+dam|it\s+van\s+dong|yen\s+tinh|"
        r"on\s+dinh|it\s+sua|ngai\s+tieng\s+sua|ngai\s+tieng\s+on|em\s+be\s+so\s+sinh|ngu\s+nhay)\b",
        norm,
    ):
        slots.temperament = "calm"

    # Size preference (token-bounded)
    if re.search(
        r"\b(?:small\s+size|small\s+breed|small\s+(?:\w+\s+)?(?:dog|cat|puppy|kitten|pet)|compact|toy\s+breed|"
        r"dang\s+nho|nho\s+gon|co\s+nho|giong\s+nho|cho\s+nho|cun\s+nho|meo\s+nho)\b",
        norm,
    ):
        slots.size_preference = "small"
    elif re.search(r"\b(?:medium\s+size|medium\s+breed|dang\s+vua|co\s+vua|trung\s+binh)\b", norm):
        slots.size_preference = "medium"
    elif re.search(r"\b(?:large\s+size|large\s+breed|big\s+dog|dang\s+lon|co\s+lon|giong\s+lon)\b", norm):
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

    # Life stage — avoid substring collision ("giá" -> "gia" MUST NEVER match "già" = senior!)
    has_diacritics = any(ord(ch) > 127 for ch in raw_question)
    is_senior = bool(
        re.search(r"\b(?:già|lớn\s+tuổi|cao\s+tuổi)\b", raw_question, re.IGNORECASE)
        or re.search(r"\b(?:senior|elderly|aging|older\s+(?:cat|dog|pet)|lon\s+tuoi|cao\s+tuoi)\b", norm)
        or (
            not has_diacritics
            and re.search(
                r"\b(?:meo|cho|cun|thu)\s+gia(?!\s+(?:re|tot|sinh\s+vien|hat\s+de|mem|duoi|tren|tam|khoang|bao\s+nhieu|\d))\b",
                norm,
            )
        )
    )
    if re.search(
        r"\b(?:kittens?|puppies|puppy|junior|meo\s+con|meo\s+nhi|cho\s+con|cun\s+con|cun\s+nhi|thu\s+non|"
        r"an\s+dam|duoi\s+12\s+thang|under\s+12\s+months)\b",
        norm,
    ):
        slots.life_stage = "junior"
    elif is_senior:
        slots.life_stage = "senior"
    elif re.search(r"\b(?:adult|grown|truong\s+thanh|meo\s+lon)\b", norm):
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
    color_safe_question = re.sub(
        r"\b(?:căn\s+hộ|ủng\s+hộ|can\s+ho|ung\s+ho)\b", " ", raw_question, flags=re.IGNORECASE
    )
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

    # Explicit & symptom-described session allergies (excluding allergens explicitly removed in this turn)
    if not clear_all_allergies:
        detected_allergies: list[str] = []
        for allergen, phrases in _ALLERGY_KEYWORDS.items():
            if allergen in removed_allergies:
                continue
            if any(phrase in norm for phrase in phrases):
                detected_allergies.append(allergen)
                continue
            tok_pat = _ALLERGEN_TOKENS[allergen]
            if re.search(rf"\b{tok_pat}\b", norm) and _ALLERGY_REACTION_CUE_RE.search(norm):
                detected_allergies.append(allergen)
        if detected_allergies:
            slots.allergies = tuple(dict.fromkeys(detected_allergies))

    return slots, explicit_species, explicit_budget


def merge_preference_slots(
    current: PreferenceSlots,
    updates: PreferenceSlots,
    *,
    target_domain: str | None,
    explicit_species_override: bool,
    explicit_budget_override: bool,
    clear_budget: bool = False,
    removed_allergies: tuple[str, ...] = (),
    clear_all_allergies: bool = False,
) -> PreferenceSlots:
    """Merge turn slot updates into session context, handling overrides and constraint removals cleanly."""
    merged = current.clone()

    if target_domain in {"pet", "product"}:
        merged.active_domain = target_domain

    if explicit_species_override and updates.species and updates.species != merged.species:
        merged.species = updates.species
        merged.coat_colors = updates.coat_colors
        merged.eye_colors = updates.eye_colors
        merged.breed_terms = updates.breed_terms
    elif updates.species:
        merged.species = updates.species

    if clear_budget:
        merged.budget_min = None
        merged.budget_max = None
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

    if clear_all_allergies:
        merged.allergies = ()
    elif removed_allergies:
        merged.allergies = tuple(a for a in merged.allergies if a not in removed_allergies)

    if updates.allergies:
        combined = list(dict.fromkeys([*merged.allergies, *updates.allergies]))
        merged.allergies = tuple(combined)

    return merged


def _detect_sales_ranking_period(compact_norm: str) -> str | None:
    has_ranking = any(
        phrase in compact_norm
        for phrase in (
            "ban chay",
            "best selling",
            "best seller",
            "most sold",
            "sold the most",
            "top selling",
            "top product",
            "top item",
        )
    )
    if not has_ranking:
        return None
    if re.search(r"\b(?:last week|previous week|tuan truoc)\b", compact_norm):
        return "last_week"
    if re.search(r"\b(?:last month|previous month|thang truoc)\b", compact_norm):
        return "last_month"
    if re.search(r"\b(?:today|hom nay)\b", compact_norm):
        return "today"
    if re.search(r"\b(?:this month|thang nay|monthly)\b", compact_norm):
        return "month"
    if re.search(r"\b(?:this week|tuan nay|weekly)\b", compact_norm):
        return "week"
    if re.search(r"\b(?:yesterday|hom qua|last year|this year|last quarter|quy nay|quy truoc)\b", compact_norm):
        return None
    return "7d"


def interpret_turn(raw_question: str, session_slots: PreferenceSlots | None = None) -> InterpretedTurn:
    """Classify safety boundaries, task intent, multi-intent workflows, and preference slot updates."""
    norm = _canonicalize_for_nlu(raw_question)
    compact_norm = re.sub(r"[^a-z0-9]+", " ", norm).strip()

    # 1. Server-side Veterinary Safety Triage executes BEFORE any shopping, operational, or LLM routing
    triage = evaluate_veterinary_safety(raw_question)
    if triage.is_triggered:
        slots, exp_sp, exp_bg = extract_preference_slots(raw_question)
        return InterpretedTurn(
            intent=triage.outcome,
            safety_trigger=triage.outcome,
            safety_category=triage.category,
            slot_updates=slots,
            explicit_species_override=exp_sp,
            explicit_budget_override=exp_bg,
            raw_query_normalized=norm,
        )

    has_deterministic_store_cap = (
        assistant_capabilities.classify(raw_question) is not None
        or any(
            phrase in compact_norm
            for phrase in (
                "ban chay",
                "best selling",
                "best seller",
                "most sold",
                "sold the most",
                "top selling",
                "top product",
                "top item",
            )
        )
    )

    # 2. Security & Policy Refusals (Prompt Injection, SQL/Code, Read-Only Write Refusal)
    is_injection = (
        any(pattern in norm for pattern in _PROMPT_INJECTION_PATTERNS)
        or any(rx.search(norm) for rx in _PROMPT_INJECTION_REGEXES)
        or triage.bypass_attempt_detected
    )
    if not has_deterministic_store_cap and is_injection:
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
    if any(phrase in norm for phrase in _WRITE_ACTION_PHRASES) or any(rx.search(norm) for rx in _WRITE_ACTION_REGEXES):
        return InterpretedTurn(
            intent="safety_refusal",
            safety_trigger="write_action",
            raw_query_normalized=norm,
        )

    # 3. Explicit reset request
    if any(phrase in norm for phrase in _RESET_PHRASES):
        return InterpretedTurn(intent="reset_context", raw_query_normalized=norm)

    clear_budget, removed_allergies, clear_all_allergies = detect_slot_removals(raw_question)
    slots, exp_species, exp_budget = extract_preference_slots(raw_question)

    # 4. Unsupported Non-Dog/Cat Exotic Species Guard
    if _EXOTIC_SPECIES_RE.search(norm) and slots.species is None:
        return InterpretedTurn(
            intent="unsupported_species",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    # 5. Undocumented Attribute Inquiry (nutrient %, vaccination logs, factory/dust %)
    has_recommendation_verb = any(
        w in norm for w in ("recommend", "suggest", "goi y", "tu van chon", "nen mua")
    )
    if _UNDOCUMENTED_ATTRIBUTE_RE.search(norm) and not has_recommendation_verb:
        codes = tuple(dict.fromkeys(code.upper() for code in _PRODUCT_CODE_RE.findall(raw_question)))
        return InterpretedTurn(
            intent="undocumented_attribute_inquiry",
            slot_updates=slots,
            comparison_codes=codes,
            raw_query_normalized=norm,
        )

    # 6. Product Comparison intent (explicit or idiomatic value-per-unit comparison)
    codes = tuple(dict.fromkeys(code.upper() for code in _PRODUCT_CODE_RE.findall(raw_question)))
    has_compare_word = any(phrase in f" {norm} " for phrase in _COMPARISON_PHRASES)
    if has_compare_word and (
        len(codes) >= 2
        or slots.product_category is not None
        or any(
            word in norm
            for word in (
                "product", "products", "item", "items", "san pham", "mat hang",
                "loai nay", "ba san pham", "hai san pham", "these two", "these three",
                "top 3", "food", "thuc an", "cat ve sinh", "litter", "litters",
            )
        )
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
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
            comparison_codes=codes,
            comparison_uses_context=uses_context,
            comparison_count_hint=count_hint,
            raw_query_normalized=norm,
        )

    # 7. Operational Insights: Bounded Multi-Tool Merchandising (Sales + Restock/Forecast) vs Single Tool
    sales_period = _detect_sales_ranking_period(compact_norm)
    cap_kind = assistant_capabilities.classify(raw_question)
    has_forecast_ask = any(phrase in compact_norm for phrase in _FORECAST_PHRASES)
    has_conjunction = bool(re.search(r"\b(?:va|dong thoi|kem|cung|and|also|plus|as well as)\b", compact_norm))

    if sales_period is not None and has_conjunction and (cap_kind == "inventory_restock" or has_forecast_ask):
        return InterpretedTurn(
            intent="multi_operational",
            slot_updates=slots,
            operational_period=sales_period,
            secondary_operational_tool="get_inventory_forecast" if has_forecast_ask else "get_restock_insights",
            raw_query_normalized=norm,
        )

    if has_forecast_ask:
        return InterpretedTurn(
            intent="inventory_forecast",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    if cap_kind is not None:
        return InterpretedTurn(
            intent="legacy_store_query",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    if any(
        phrase in compact_norm
        for phrase in (
            "ban chay", "best selling", "best seller", "most sold", "sold the most",
            "top selling", "top product", "top item", "doanh thu", "revenue",
        )
    ):
        return InterpretedTurn(
            intent="legacy_store_query",
            slot_updates=slots,
            raw_query_normalized=norm,
        )

    # Determine product vs pet signals
    has_advisory_signal = any(phrase in norm for phrase in _ADVISORY_VERBS)
    has_lifestyle_or_trait = any((
        slots.living_space,
        slots.temperament,
        slots.size_preference,
        slots.life_stage,
        slots.pet_weight_kg is not None,
        slots.allergies,
    ))
    has_slot_removal = clear_budget or bool(removed_allergies) or clear_all_allergies

    mentions_product_nouns = slots.product_category is not None or any(
        re.search(rf"\b{re.escape(w)}\b", norm)
        for w in ("product", "products", "item", "items", "san pham", "mat hang", "do dung", "do cho meo", "do cho cho")
    )
    mentions_pet_adoption = (
        not mentions_product_nouns
        and (
            slots.species is not None
            or bool(
                re.search(
                    r"\b(?:adopt|pet\s+suitable|suitable\s+pet|choose\s+a\s+pet|which\s+pet|"
                    r"recommend\s+a\s+pet|looking\s+for\s+a\s+pet|a\s+pet\s+to\s+buy|"
                    r"nuoi\s+thu\s+cung|chon\s+thu\s+cung|tim\s+thu\s+cung|muon\s+nuoi|"
                    r"(?:tu\s+van|goi\s+y)\s+(?:chon\s+)?thu\s+cung|thu\s+cung\s+(?:hien\s+)?phu\s+hop)\b",
                    norm,
                )
            )
        )
    )

    # 8. Multi-Intent Care Knowledge + Shopping vs Single-Intent Knowledge Base
    has_knowledge_signal = any(phrase in norm for phrase in _KNOWLEDGE_SIGNALS) or bool(
        _KNOWLEDGE_QUESTION_RE.search(norm)
    )
    has_explicit_care_question = bool(_EXPLICIT_CARE_QUESTION_RE.search(norm))
    has_explicit_shopping_intent = (
        exp_budget
        or any(
            phrase in norm
            for phrase in (
                "recommend", "suggest", "which food should", "what products", "suitable products",
                "in stock", "con hang", "ben shop co", "cua shop", "product", "products",
                "san pham", "mat hang", "goi y", "chon mua san pham", "mua gi",
            )
        )
    )

    if has_explicit_care_question and has_explicit_shopping_intent and (mentions_product_nouns or mentions_pet_adoption):
        return InterpretedTurn(
            intent="multi_knowledge_and_shopping",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
            raw_query_normalized=norm,
        )

    if has_knowledge_signal and not has_explicit_shopping_intent:
        return InterpretedTurn(
            intent="knowledge_qa",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            raw_query_normalized=norm,
        )

    # 9. Follow-up continuation when session is awaiting clarification or has active domain
    if session_slots is not None and session_slots.awaiting_clarification_for in {"pet", "product"}:
        target = session_slots.awaiting_clarification_for
        if mentions_product_nouns and target == "pet":
            target = "product"
        if slots.has_any_constraint() or exp_budget or exp_species or has_slot_removal:
            return InterpretedTurn(
                intent=f"{target}_recommendation",
                slot_updates=slots,
                explicit_species_override=exp_species,
                explicit_budget_override=exp_budget,
                clear_budget=clear_budget,
                removed_allergies=removed_allergies,
                clear_all_allergies=clear_all_allergies,
                raw_query_normalized=norm,
            )

    is_refinement = bool(
        session_slots is not None
        and session_slots.active_domain in {"pet", "product"}
        and not mentions_product_nouns
        and not mentions_pet_adoption
        and (exp_budget or has_lifestyle_or_trait or has_slot_removal)
    )
    if is_refinement and session_slots is not None:
        return InterpretedTurn(
            intent=f"{session_slots.active_domain}_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
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
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
            raw_query_normalized=norm,
        )

    # 10. Personalized Product Recommendations
    if mentions_product_nouns and (has_advisory_signal or has_lifestyle_or_trait or exp_budget or exp_species or has_slot_removal):
        return InterpretedTurn(
            intent="product_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
            raw_query_normalized=norm,
        )

    # 11. Pet Matching & Adoption/Purchase Advice
    if mentions_pet_adoption and (has_advisory_signal or has_lifestyle_or_trait or has_slot_removal):
        return InterpretedTurn(
            intent="pet_recommendation",
            slot_updates=slots,
            explicit_species_override=exp_species,
            explicit_budget_override=exp_budget,
            clear_budget=clear_budget,
            removed_allergies=removed_allergies,
            clear_all_allergies=clear_all_allergies,
            raw_query_normalized=norm,
        )

    # 12. General care questions with "why / how / should / can my dog/cat..."
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
        clear_budget=clear_budget,
        removed_allergies=removed_allergies,
        clear_all_allergies=clear_all_allergies,
        raw_query_normalized=norm,
    )
