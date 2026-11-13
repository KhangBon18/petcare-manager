"""Dedicated Server-Side Veterinary Safety Triage Engine (AI-2.1 / AI-2.2).

Executes deterministically BEFORE shopping intent routing, catalog search, product
recommendations, or LLM tool selection. Uses clause-level compositional rules,
negation/historical-resolution scope checks, and typo/slang canonicalization to catch:
1. Urinary obstruction warning signs (e.g., straining in litter box with little/no urine).
2. Breathing difficulty / respiratory distress.
3. Suspected poisoning & acute ingestion of toxic foods, plants, chemicals, or foreign bodies.
4. Dangerous human medications (OTC painkillers, antidiarrheals, human antibiotics) & unsafe home emetics.
5. Severe or rapidly worsening neurological (seizures, head-pressing, acute ataxia), icterus/jaundice,
   mucous-membrane pallor / circulatory shock, hemorrhagic, bloat (GDV), or trauma symptoms.
6. Requests for prescription medications, mg/kg dosing, or clinical disease diagnosis (excluding
   purely nutritional feed-label composition questions such as taurine/calcium mg in packaged food).

Limitation notice: Rule-based triage improves recall on clinically documented red flags in Vietnamese
and English (referenced against AVMA, ASPCA Poison Control, and Cornell Feline Health Center public
triage guidance), but has not undergone independent clinical sign-off by a licensed veterinarian,
cannot recognize every atypical veterinary presentation, and never diagnoses disease.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from petcare.services.catalog_intent import _normalize


@dataclass(frozen=True, slots=True)
class SafetyTriageDecision:
    """Structured output of the server-side pre-routing veterinary safety check."""

    outcome: str  # "none" | "vet_emergency" | "vet_medical_boundary"
    category: str | None = None
    matched_signals: tuple[str, ...] = ()
    bypass_attempt_detected: bool = False

    @property
    def is_triggered(self) -> bool:
        return self.outcome in {"vet_emergency", "vet_medical_boundary"}


_CLAUSE_SPLIT_RE = re.compile(
    r"[.!?;:\n]+|,\s+(?=(?:nhung|ma|con|tuy nhien|hien|gio|bay gio|khong|no|not|without|but|however|though|yet|and now|now)\b)"
    r"|\b(?:nhung ma|nhung|tuy nhien|but|however|although|though)\b",
    re.IGNORECASE,
)

# Common Vietnamese & English spelling variations normalized on token boundaries
_TYPO_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:ko|k0|khg|khongg|hong|hok)\b"), "khong"),
    (re.compile(r"\b(?:dc|dk)\b"), "duoc"),
    (re.compile(r"\bxilitol\b"), "xylitol"),
    (re.compile(r"\b(?:so\s+co\s+la|choclate|chocolat)\b"), "socola"),
    (re.compile(r"\b(?:paracetamon|paracetamoll)\b"), "paracetamol"),
    (re.compile(r"\b(?:ibuprophen|ibupofen)\b"), "ibuprofen"),
    (re.compile(r"\bberberine\b"), "berberin"),
    (re.compile(r"\bamoxicilin\b"), "amoxicillin"),
    (re.compile(r"\b(?:tiu|tỉu)\b"), "tieu"),
    (re.compile(r"\blitterbox\b"), "litter box"),
)

_BYPASS_ATTEMPT_RE = re.compile(
    r"\b(?:ignore|disregard|skip|bypass|override)\s+(?:all\s+|any\s+|previous\s+|your\s+)?(?:safety|vet|veterinary|medical|triage|emergency|rules|instructions|warnings)\b"
    r"|\b(?:bo qua|phot lo|tat)\s+(?:moi\s+|tat ca\s+)?(?:canh bao|quy tac|an toan|thu y)\b"
    r"|\b(?:dung|khong)\s+(?:khuyen|bao|nhac)\s+(?:di\s+)?(?:kham|thu y|bac si)\b"
    r"|\b(?:do not|don t|dont)\s+(?:tell|advise|warn)\s+me\s+to\s+(?:see|visit|call)\s+a\s+vet",
    re.IGNORECASE,
)

# Safe product-attribute exclusions that mention a toxin word negatively ("không chứa xylitol", "xylitol-free")
_SAFE_INGREDIENT_EXCLUSION_RE = re.compile(
    r"\b(?:khong\s+(?:chua|co|dung|pha)|free\s+of|without|non)\s+(?:chat\s+tao\s+ngot\s+)?(?:xylitol|socola|chocolate|fluoride|alcohol|con|hanh|toi)\b"
    r"|\b(?:xylitol|chocolate|socola|fluoride)[-\s]+free\b",
    re.IGNORECASE,
)

# Educational / general care inquiries ("Thực phẩm nào gây ngộ độc?", "Chó ăn nho khô có nguy hiểm không?")
# Only treated as educational when NO acute exposure verb or active distress symptom is present.
_GENERAL_EDUCATIONAL_TOXIN_RE = re.compile(
    r"\b(?:thuc pham nao|nhung thuc pham nao|cay nao|cay gi|chat nao|do an nao|mon nao|hoa nao)\b.*\b(?:gay ngo doc|ngo doc|doc hai|nguy hiem|khong nen cho an|can tranh)\b"
    r"|\b(?:which|what)\s+(?:household\s+|human\s+|common\s+)?(?:foods?|plants?|items?|substances?|things?)\s+(?:are|is|can be)\s+(?:toxic|poisonous|unsafe|dangerous|harmful)\b"
    r"|\b(?:cho|meo|thu cung|cun)\s+an\s+[a-z0-9\s]{1,25}\b(?:co sao khong|co nguy hiem khong|co doc khong|duoc khong)\b"
    r"|\b(?:can|may)\s+(?:dogs?|cats?|puppies|kittens|pets?)\s+(?:eat|have)\s+[a-z0-9\s]{1,25}"
    r"|\b(?:is|are)\s+[a-z0-9\s]{1,25}\s+(?:toxic|poisonous|safe|dangerous|bad)\s+for\s+(?:dogs?|cats?|pets?)\b",
    re.IGNORECASE,
)

# Past/resolved medical history markers
_HISTORICAL_TIME_RE = re.compile(
    r"\b(?:nam ngoai|nam truoc|thang truoc|hoi nho|luc truoc|truoc day|cach day \d+\s*(?:thang|nam)|"
    r"last year|last month|\d+\s*(?:months?|years?)\s+ago|in the past|previously|used to have)\b"
)
_RESOLVED_STATE_RE = re.compile(
    r"\b(?:da khoi|khoi han|da phau thuat xong|da mo xong|da dieu tri khoi|gio khoe|hien tai khoe|binh thuong roi|on dinh roi|"
    r"recovered|fully healed|healthy now|fine now|doing well now|resolved)\b"
)
_ACTIVE_RECURRENCE_RE = re.compile(
    r"\b(?:hom nay|toi nay|sang nay|chieu nay|tu toi qua|tu dem qua|tu sang|vua moi|dang bi|lai bi|tai phat|ngay luc nay|"
    r"tonight|today|this morning|since last night|since yesterday|right now|currently|just now|started again|acting sick)\b"
)

# Presence-of-symptom negation prefix within a clause (e.g., "không bị khó thở", "no vomiting, no seizures")
# Excludes epistemic prefixes like "không biết" / "không rõ" / "not sure" so genuine questions are never suppressed.
_SYMPTOM_NEGATION_PREFIX_RE = re.compile(
    r"\b(?:"
    r"khong\s+(?!biet\b|ro\b|chac\b|hieu\b)(?:bi\s+|co\s+|he\s+|con\s+|thay\s+)?"
    r"|chua\s+(?:bi\s+|co\s+|thay\s+|tung\s+)?"
    r"|no\s+|not\s+(?!sure\b|certain\b)|without\s+|zero\s+|neither\s+|nor\s+|free\s+of\s+|never\s+(?:had\s+)?|did\s+not\s+|didn\s+t\s+|hasn\s+t\s+|haven\s+t\s+"
    r")"
    r"(?:bi\s+|co\s+|thay\s+|dau\s+|trieu\s+chung\s+|cho\s+uong\s+|dung\s+|uong\s+|giving\s+|given\s+|using\s+|any\s+|signs?\s+of\s+|ever\s+)?"
    r"(?:[a-z]+\s+(?:[a-z]+\s+)?(?:or|nor|hay|hoac|va)\s+)?$"
)


# --- 1. Urinary Obstruction Rules ---
# Patterns whose own phrasing inherently expresses inability/absence of urine (must NOT be skipped by internal "khong"/"no")
_URINARY_INHERENT_ABSENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bkhong\s+(?:di\s+)?(?:tieu|dai)\s+(?:duoc|ra)\b"),
    re.compile(r"\b(?:tieu|dai)\s+khong\s+(?:ra|duoc)\b"),
    re.compile(r"\bkhong\s+ra\s+(?:giot\s+|ti\s+|chut\s+)?nuoc\s+tieu\b"),
    re.compile(r"\b(?:cannot|can t|cant|unable to)\s+(?:urinate|pee|pass urine)\b"),
    re.compile(r"\b(?:produced|passing|passed|producing)\s+(?:no|zero|little|almost no)\s+urine\b"),
)

# Presence-of-symptom urinary patterns (must respect clause-level negation such as "không bị bí tiểu", "no blood in urine")
_URINARY_PRESENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:bi tieu|bi dai|tac tieu|tac dai|tac duong tieu|tac nieu dao|vo nieu)\b"),
    re.compile(r"\b(?:urinary|urethral)\s+(?:blockage|obstruction)\b"),
    re.compile(r"\bblocked\s+(?:cat|tomcat|urethra|bladder)\b"),
    re.compile(r"\b(?:straining|trying)\s+to\s+(?:urinate|pee)\b"),
    re.compile(r"\b(?:tieu|dai)\s+ra\s+mau\b"),
    re.compile(r"\b(?:tieu|dai)\s+(?:dat|ắt|rat)\s+.*(?:mau|keu|dau)\b"),
    re.compile(r"\b(?:blood\s+in\s+(?:the\s+)?urine|bloody\s+urine|peeing\s+blood|hematuria)\b"),
)

_URINARY_META_NEGATION_RE = re.compile(
    r"\b(?:khong\s+(?:bi|he|con)\s+(?:bi tieu|tac tieu|bi dai|ran)|di tieu binh thuong|van tieu binh thuong|"
    r"not\s+straining|no\s+urinary\s+(?:issues?|blockage|problems?)|urinating\s+normally|peeing\s+normally)\b"
)

_LITTER_OR_POSTURE_STRAIN_RE = re.compile(
    r"\b(?:ngoi ran|cu ran|ran mai|co ran|ran dau|ran tieu|ran dai|"
    r"(?:vao|ra vao)\s+(?:khay|chau|thau|hop|bon)\s+cat\s+(?:lien tuc|mai|nhieu lan|hoai)|"
    r"(?:vao|ngoi trong)\s+(?:khay|chau|thau|hop)\s+cat.*ran|"
    r"straining\s+in\s+(?:the\s+)?(?:litter\s*box|box)|squatting\s+(?:repeatedly\s+)?in\s+(?:the\s+)?(?:litter|box)|"
    r"repeated\s+trips\s+to\s+(?:the\s+)?litter\s*box|in\s+and\s+out\s+of\s+(?:the\s+)?litter\s*box|"
    r"crying\s+in\s+(?:the\s+)?litter\s*box)\b"
)
_LOW_URINE_OR_DISTRESS_RE = re.compile(
    r"\b(?:khong ra|khong co|chua ra|chi ra vai giot|nho giot|tung giot|cat van kho|cat kho cong|khong thay uot|"
    r"keu gao|keu dau|keu ren|dau bung|liem bo phan sinh duc|"
    r"no urine|nothing comes out|nothing came out|only a few drops|just a drop|drops of urine|dry litter|completely dry|"
    r"yowling|crying in pain|howling in pain|licking genitals)\b"
)


# --- 2. Breathing / Respiratory Distress Rules ---
_RESPIRATORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:kho tho|tho gap|tho doc|ha mieng tho|ha mom tho|meo tho bang mieng|tho bung|tho rut lom bung|ngat tho|nghet tho|ngop tho|hoc xuong.*tho)\b"),
    re.compile(r"\b(?:luoi tim|loi tim|nuou tim|niem mac tim tai|tim tai)\b"),
    re.compile(r"\bkhong\s+tho\s+(?:duoc|noi)\b"),
    re.compile(r"\b(?:difficulty|trouble|hard(?:\s+time)?|struggling)\s+(?:to\s+)?breath(?:e|ing)\b"),
    re.compile(r"\b(?:labored|open[-\s]mouth)\s+breathing\b"),
    re.compile(r"\b(?:cat|kitten)\s+(?:is\s+)?panting\s+with\s+(?:its\s+|his\s+|her\s+)?mouth\s+open\b"),
    re.compile(r"\bbreathing\s+with\s+(?:its\s+|his\s+|her\s+)?mouth\s+open\b"),
    re.compile(r"\b(?:gasping\s+for\s+air|gasping|choking|blue\s+gums|purple\s+tongue|cyanotic|respiratory\s+distress)\b"),
    re.compile(r"\b(?:cannot|can t|cant)\s+breathe\b"),
)


# --- 3. Acute Toxin / Poison / Foreign-Body Ingestion Rules ---
_DIRECT_POISONING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:bi ngo doc|nghi ngo doc|trung doc|an ba chuot|nuot ba chuot|an phai ba|thuoc diet chuot|uong thuoc tay|uong nuoc lau san|uong nuoc javel|nuoc lam mat)\b"),
    re.compile(r"\b(?:nho\s+nham|xit\s+nham|boi\s+nham|dung\s+nham)\s+thuoc\s+(?:tri\s+|diet\s+)?(?:ve|ran|bo\s+chet|nho\s+gay)\b.*\bcua\s+cho\b.*\bmeo\b"),
    re.compile(r"\b(?:rat\s+poison|rodenticide|antifreeze|ethylene\s+glycol|bleach\s+poisoning|snail\s+bait|slug\s+bait|permethrin\s+on\s+(?:my\s+|a\s+)?cat|dog\s+flea\s+(?:medicine|treatment|drops)\s+on\s+(?:my\s+|a\s+)?cat)\b"),
    re.compile(r"\b(?:my\s+(?:dog|cat|puppy|kitten|pet)\s+(?:was\s+|is\s+)?poisoned|suspected\s+poisoning)\b"),
)

_ACUTE_INGESTION_VERB_RE = re.compile(
    r"\b(?:vua an|lo an|moi an|an phai|an nham|an mat|an het|an nguyen|vua nuot|lo nuot|moi nuot|nuot phai|nuot nguyen|nuot chung|nuot mat|"
    r"nhai phai|vua nhai|can phai|can nat|liem phai|vua liem|uong nham|uong phai|"
    r"just ate|ate|swallowed|ingested|chewed on|chewed up|chewed|got into|licked)\b"
)

_TOXIC_SUBSTANCES_RE = re.compile(
    r"\b(?:socola|chocolate|dark chocolate|cacao|cocoa|brownies?|xylitol|keo cao su khong duong|sugar[-\s]free gum|"
    r"nho kho|qua nho|chum nho|grapes?|raisins?|hoa ly|bong ly|cay hoa ly|la hoa ly|lily|lilies|van tue|sago palm|cycad|"
    r"hanh tay|cu toi|bot toi|onion|onions|garlic|mac ca|macadamia|ba chuot|thuoc chuot|thuoc xit muoi|thuoc diet con trung|permethrin|"
    r"long nao|bang phien|mothballs?|tinh dau tram tra|tea tree oil|cuc pin|vien pin|button battery|kim khau|luoi cau|day ruy bang|string|ribbon)\b"
)


# --- 4. Severe Neurological, Icterus/Jaundice, Pallor/Shock, Hemorrhagic, Bloat (GDV), or Trauma Rules ---
_SEVERE_ACUTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:co giat|sui bot mep|bat tinh|ngat xiu|lim di|hon me|liet hai chan|khong dung day noi|lo do khong phan ung)\b"),
    re.compile(r"\b(?:non ra mau|oi ra mau|di ngoai ra mau|tieu chay ra mau|phan den nhu ba ca phe|non lien tuc khong cam)\b"),
    re.compile(r"\b(?:chuong bung cung|bung phinh to cung|non khan.*bung to)\b"),
    re.compile(r"\b(?:bi xe tong|bi xe can|nga tu ban cong|nga tu tang|chay mau nhieu|chay mau khong cam|soc nhiet)\b"),
    re.compile(r"\b(?:seizures?|convulsions?|unconscious|unresponsive|collapsed|collapse|sudden\s+paralysis|cannot\s+stand)\b"),
    re.compile(r"\b(?:vomiting\s+blood|blood\s+in\s+vomit|bloody\s+diarrhea|blood\s+in\s+stool|nonstop\s+vomiting)\b"),
    re.compile(r"\b(?:bloated\s+(?:hard\s+)?stomach|distended\s+abdomen|retching\s+nothing\s+comes\s+up)\b"),
    re.compile(r"\b(?:hit\s+by\s+a\s+car|fell\s+from\s+(?:balcony|window)|severe\s+bleeding|heatstroke)\b"),
)

# Forebrain dysfunction (head-pressing, compulsive circling/falling) & mucous-membrane/scleral icterus (jaundice).
# Scoped strictly to anatomical mucous-membrane/scleral/pinna/skin sites or acute color transition verbs so
# normal shopping queries ("mèo lông vàng", "mèo mắt vàng", "yellow cat toy") never trigger false alarms.
_NEUROLOGICAL_OR_JAUNDICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bhead[-\s]pressing\b"),
    re.compile(
        r"\b(?:press(?:es|ing|ed)?|push(?:es|ing|ed)?|lean(?:s|ing|ed)?|jam(?:s|ming|med)?|rest(?:s|ing|ed)?)\s+"
        r"(?:its\s+|his\s+|her\s+|the\s+)?(?:head|forehead|skull)\s+"
        r"(?:flat\s+|hard\s+|tightly\s+)?(?:against|into|onto|on)\s+"
        r"(?:the\s+|a\s+)?(?:wall|corner|door|floor|furniture|cabinet|couch|sofa)\b"
    ),
    re.compile(
        r"\b(?:an|ap|ti|tuy|dui|cham|tua|dap|uc|di)\s+(?:chat\s+|sat\s+|manh\s+)?(?:dau|tran)\s+"
        r"(?:vao|vo|len|sat)\s+(?:tuong|goc\s+tuong|goc\s+nha|goc\s+phong|canh\s+cua|cua|chan\s+tuong|san\s+nha|tu|ghe)\b"
    ),
    re.compile(
        r"\b(?:dung|ngoi)\s+(?:im\s+|do\s+)?(?:trong\s+|o\s+)?goc\s+(?:nha|tuong|phong)\b.*"
        r"\b(?:ap\s+dau|ti\s+dau|an\s+dau|dui\s+dau|tran\s+vao|khong\s+phan\s+ung|mat\s+phuong\s+huong)\b"
    ),
    re.compile(
        r"\b(?:di\s+loang\s+choang\s+nga|di\s+xoay\s+vong\s+lien\s+tuc|nghieng\s+dau\s+nga\s+nhao|"
        r"walking\s+in\s+circles\s+nonstop|stumbling\s+and\s+falling\s+over)\b"
    ),
    re.compile(r"\b(?:jaundiced?|icterus|icteric|vang\s+da|hoang\s+dan)\b"),
    re.compile(
        r"\b(?:whites?\s+of\s+(?:the\s+|its\s+|his\s+|her\s+)?eyes?|sclerae?|gums?|mucous\s+membranes?|"
        r"inner\s+ears?|ear\s+flaps?|pinnae|belly\s+skin)\b[^.!?]{0,35}\b(?:yellow|yellowish|orange[-\s]yellow)\b"
    ),
    re.compile(
        r"\b(?:yellow|yellowish)\s+(?:sclerae?|whites?\s+of\s+(?:the\s+|its\s+|his\s+|her\s+)?eyes?|"
        r"gums?|mucous\s+membranes?|inner\s+ears?|ear\s+flaps?|skin)\b"
    ),
    re.compile(
        r"\b(?:yellow\s+discoloration|yellowing)\s+(?:of|around|in|on)\s+"
        r"(?:the\s+|its\s+|his\s+|her\s+)?(?:eyes?|gums?|ears?|skin|mouth)\b"
    ),
    re.compile(
        r"\b(?:around|under|inside)\s+(?:its\s+|his\s+|her\s+|the\s+)?(?:eyes?|ears?|mouth)\b"
        r"[^.!?]{0,25}\b(?:turned|turning|became|become|looks?)\s+(?:bright\s+|pale\s+)?yellow\b"
    ),
    re.compile(
        r"\b(?:trong\s+trang|long\s+trang(?:\s+mat)?|ket\s+mac|nuou(?:\s+rang)?|loi|niem\s+mac|"
        r"vanh\s+tai(?:\s+trong)?|tai\s+trong|da\s+bung|vung\s+quanh\s+mat)\b"
        r"[^.!?]{0,35}\b(?:vang\s+khe|vang\s+ong|vang\s+nhat|nga\s+vang|chuyen\s+vang|bi\s+vang|mau\s+vang|vang)\b"
    ),
    re.compile(
        r"\b(?:mat|nuou|loi|tai|da)\b[^.!?]{0,20}\b(?:bong\s+nhien|tu\s+nhien|dot\s+ngot|chuyen\s+sang|nga\s+sang)\s+(?:mau\s+)?vang\b"
    ),
)

# Mucous-membrane pallor & circulatory shock / hypoperfusion / saddle-thrombus warning signs
_PALLOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:pale|very\s+pale|white|paper[-\s]white|porcelain[-\s]white|ghost[-\s]white|chalky|ashy|gray|grey|muddy|bloodless|colorless)\s+"
        r"(?:gums?|gingiva|tongue|mucous\s+membranes?|lips?)\b"
    ),
    re.compile(
        r"\b(?:gums?|gingiva|tongue|mucous\s+membranes?)\s+"
        r"(?:are|is|look|looks|turned|turning|went|feel|seem|appeared?)\s+"
        r"(?:very\s+|extremely\s+|super\s+|so\s+)?(?:pale|white|paper[-\s]white|porcelain[-\s]white|chalky|gray|grey|muddy|bloodless|colorless)\b"
    ),
    re.compile(
        r"\b(?:nuou(?:\s+rang)?|loi|luoi|niem\s+mac|moi\s+trong)\b[^.!?]{0,28}"
        r"\b(?:trang\s+bech|trang\s+nhot|nhot\s+nhat|tai\s+nhot|trang\s+nhu\s+(?:giay|to\s+giay|su|voi)|xam\s+xit|mat\s+mau)\b"
    ),
    re.compile(
        r"\b(?:trang\s+bech|nhot\s+nhat|tai\s+nhot|mat\s+mau)\s+(?:o\s+|vung\s+)?(?:nuou(?:\s+rang)?|loi|luoi|niem\s+mac)\b"
    ),
)

_WINTER_APPAREL_CONTEXT_RE = re.compile(
    r"\b(?:ao\s+am|ao\s+len|ao\s+khoac|giay|tat|vo|chan\s+am|nem\s+am|mua\s+dong|troi\s+lanh|ret\s+dam|"
    r"sweater|coat|jacket|booties|boots|socks|winter|cold\s+weather|snow)\b"
)

_COLD_EXTREMITIES_RE = re.compile(
    r"\b(?:paws?|feet|foot\s+pads?|legs?|limbs?|extremities|ears?)\b[^.!?]{0,25}"
    r"\b(?:ice[-\s]cold|freezing(?:\s+cold)?|unusually\s+cold|stone[-\s]cold|cold\s+to\s+the\s+touch|very\s+cold)\b"
    r"|\b(?:ice[-\s]cold|freezing(?:\s+cold)?|unusually\s+cold|stone[-\s]cold|very\s+cold)\s+"
    r"(?:paws?|feet|foot\s+pads?|legs?|limbs?|extremities|ears?)\b"
    r"|\b(?:ban\s+chan|chan|tu\s+chi|chi\s+sau|hai\s+chan\s+sau|bon\s+chan|bon\s+ban\s+chan|vanh\s+tai|tai|nguoi|than\s+nhiet)\b"
    r"[^.!?]{0,25}\b(?:lanh\s+ngat|lanh\s+toat|lanh\s+buot|lanh\s+nhu\s+da|ha\s+than\s+nhiet)\b"
)

_SHOCK_SYSTEMIC_WEAKNESS_RE = re.compile(
    r"\b(?:nam\s+im|nam\s+bet|nam\s+li|lu\s+du|met\s+la|la\s+nguoi|yeu\s+ot|run\s+cam\s+cap|keo\s+le|liet|"
    r"khong\s+di\s+duoc|tho\s+yeu|mach\s+yeu|"
    r"limp|lethargic|listless|weak|shaking|trembling|dragging\s+(?:its\s+|his\s+|her\s+)?(?:back|hind)\s+legs?|weak\s+pulse)\b"
)


# --- 5. Dangerous Human Medications, Unsafe Home Emetics & Prescription / Dosing / Diagnosis Boundary ---
_HUMAN_MEDICATION_NAMES_RE = re.compile(
    r"\b(?:tylenol|panadol|efferalgan|hapacol|paracetamol|acetaminophen|"
    r"ibuprofen|advil|motrin|nurofen|aspirin|naproxen|aleve|meloxicam|diclofenac|voltaren|"
    r"smecta|berberin|imodium|loperamide|pepto[-\s]?bismol|"
    r"amoxicillin|augmentin|metronidazole|flagyl|doxycycline|cephalexin|cefuroxime|azithromycin|ciprofloxacin|clindamycin|"
    r"ivermectin|prednisolone|prednisone|dexamethasone|medrol|"
    r"benadryl|diphenhydramine|cetirizine|zyrtec|loratadine|claritin|pseudoephedrine|"
    r"thuoc cam cua nguoi|thuoc ha sot cua nguoi|thuoc dau bung cua nguoi|thuoc tieu chay cua nguoi|thuoc nguoi)\b"
)

_UNSAFE_HOME_EMETIC_RE = re.compile(
    r"\b(?:oxy\s+gia|hydrogen\s+peroxide|nuoc\s+muoi\s+dac|salt\s+water)\b.*"
    r"\b(?:gay\s+non|cho\s+non|oi\s+ra|induce\s+vomiting|make\s+(?:him|her|it|my\s+(?:cat|dog|pet))\s+vomit|throw\s+up)\b"
    r"|\b(?:gay\s+non|induce\s+vomiting)\b.*\b(?:oxy\s+gia|hydrogen\s+peroxide|nuoc\s+muoi|salt)\b"
)

_DOSING_OR_PRESCRIPTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d+(?:[.,]\d+)?\s*mg(?:\s*/\s*kg)?\b"),
    re.compile(r"\b(?:what\s+dosage|how\s+many\s+(?:mg|milligrams|pills|tablets|ml)|safe\s+dose|dosing\s+chart|milligrams)\b"),
    re.compile(r"\b(?:prescribe|prescription|which\s+antibiotic|what\s+medicine\s+should\s+i\s+give|can\s+i\s+give\s+(?:my\s+)?(?:dog|cat|puppy|kitten)\s+.*\b(?:tablet|pill|medicine|medication|antibiotic))\b"),
    re.compile(r"\b(?:diagnose\s+my|what\s+disease\s+does|is\s+it\s+parvovirus|is\s+it\s+panleukopenia)\b"),
    re.compile(r"\b(?:ke\s+don|lieu\s+luong|lieu\s+dung|bao\s+nhieu\s+mg|cho\s+uong\s+may\s+vien|pha\s+may\s+goi\s+thuoc)\b"),
    re.compile(r"\b(?:uong\s+khang\s+sinh|tiem\s+thuoc\s+gi|tiem\s+khang\s+sinh|uong\s+thuoc\s+gi|nho\s+thuoc\s+khang\s+sinh)\b"),
    re.compile(r"\b(?:chan\s+doan\s+benh|mac\s+benh\s+gi|bi\s+benh\s+gi|co\s+phai\s+benh\s+parvo|co\s+phai\s+benh\s+giam\s+bach\s+cau|co\s+phai\s+care)\b"),
)

_DIETARY_NUTRIENT_RE = re.compile(
    r"\b(?:taurine|canxi|calcium|omega|epa|dha|glucosamine|chondroitin|phosphorus|photpho|"
    r"magnesium|magie|sodium|natri|zinc|kem|iron|sat|biotin|lysine|dam\s+tho|chat\s+beo|crude\s+protein|crude\s+fat)\b"
)
_FEED_PRODUCT_LABEL_CONTEXT_RE = re.compile(
    r"\b(?:tui\s+hat|goi\s+hat|bich\s+hat|hat|thuc\s+an|pate|san\s+pham|bao\s+bi|nhan|thanh\s+phan|ham\s+luong|"
    r"food|kibble|bag|pouch|can|product|label|formula|guaranteed\s+analysis|[a-z]{2,8}-\d{2,5})\b"
)
_MEDICATION_ADMINISTRATION_CUE_RE = re.compile(
    r"\b(?:cho\s+uong|uong\s+may|tiem|nho\s+thuoc|ke\s+don|lieu\s+luong|lieu\s+dung|vien|thuoc|khang\s+sinh|"
    r"tri\s+benh|bi\s+benh|give|dose|dosage|administer|tablet|pill|capsule|antibiotic|medicine|medication|mg\s*/\s*kg|per\s+kg)\b"
)


def _normalize_for_triage(raw_text: str) -> str:
    norm = re.sub(r"[^a-z0-9/.?\s-]+", " ", _normalize(raw_text))
    norm = re.sub(r"\s+", " ", norm).strip()
    for pattern, replacement in _TYPO_SUBSTITUTIONS:
        norm = pattern.sub(replacement, norm)
    return norm


_INTERNAL_PREDICATE_NEGATION_RE = re.compile(
    r"\b(?:khong(?!\s+(?:phan\s+ung|di\s+duoc)\b)|chua|not(?!\s+sure\b)|no|never|neither|nor|without)\b"
)


def _is_match_negated_in_clause(clause: str, match_start: int, matched_span: str = "") -> bool:
    """Return True if a presence-of-symptom match is negated before `match_start` or inside a noun->predicate span."""
    window_start = max(0, match_start - 40)
    prefix = clause[window_start:match_start]
    if _SYMPTOM_NEGATION_PREFIX_RE.search(prefix):
        return True
    if matched_span and _INTERNAL_PREDICATE_NEGATION_RE.search(matched_span):
        return True
    return False


def _is_resolved_historical_mention(full_norm: str) -> bool:
    """Return True when past illness is explicitly described as resolved with zero active recurrence cues."""
    if not (_HISTORICAL_TIME_RE.search(full_norm) and _RESOLVED_STATE_RE.search(full_norm)):
        return False
    if _ACTIVE_RECURRENCE_RE.search(full_norm):
        return False
    return True


def _has_non_negated_acute_ingestion(clauses: list[str]) -> bool:
    for clause in clauses:
        for m in _ACUTE_INGESTION_VERB_RE.finditer(clause):
            if not _is_match_negated_in_clause(clause, m.start()):
                return True
    return False


def _is_nutritional_label_composition_query(sanitized_full: str) -> bool:
    """Return True when `mg` / `milligrams` refers strictly to feed-label nutrient content, not drug dosing."""
    if not _DIETARY_NUTRIENT_RE.search(sanitized_full):
        return False
    if not _FEED_PRODUCT_LABEL_CONTEXT_RE.search(sanitized_full):
        return False
    if _MEDICATION_ADMINISTRATION_CUE_RE.search(sanitized_full):
        return False
    return True


def evaluate_veterinary_safety(raw_question: str) -> SafetyTriageDecision:
    """Run conservative, evidence-based veterinary triage BEFORE any shopping or LLM routing."""
    if not isinstance(raw_question, str) or not raw_question.strip():
        return SafetyTriageDecision(outcome="none")

    norm_full = _normalize_for_triage(raw_question)
    if not norm_full:
        return SafetyTriageDecision(outcome="none")

    bypass_attempt = bool(_BYPASS_ATTEMPT_RE.search(norm_full))

    # Strip safe negative ingredient filters (e.g., "kem đánh răng không chứa xylitol", "xylitol-free")
    sanitized_full = _SAFE_INGREDIENT_EXCLUSION_RE.sub(" ", norm_full)
    sanitized_full = re.sub(r"\s+", " ", sanitized_full).strip()

    is_resolved_history = _is_resolved_historical_mention(sanitized_full)

    clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(sanitized_full) if c and c.strip()]
    if not clauses:
        clauses = [sanitized_full]

    if not is_resolved_history:
        # 1. Urinary Obstruction Check (Inherent anuria, clause-checked dysuria/hematuria, OR strain + low/no urine)
        if not _URINARY_META_NEGATION_RE.search(sanitized_full):
            for pat in _URINARY_INHERENT_ABSENCE_PATTERNS:
                m = pat.search(sanitized_full)
                if m:
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="urinary_obstruction",
                        matched_signals=(m.group(0),),
                        bypass_attempt_detected=bypass_attempt,
                    )

            for clause in clauses:
                for pat in _URINARY_PRESENCE_PATTERNS:
                    m = pat.search(clause)
                    if m and not _is_match_negated_in_clause(clause, m.start()):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="urinary_obstruction",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )

            has_non_negated_strain = any(
                (m := _LITTER_OR_POSTURE_STRAIN_RE.search(clause)) is not None
                and not _is_match_negated_in_clause(clause, m.start())
                for clause in clauses
            )
            if has_non_negated_strain and _LOW_URINE_OR_DISTRESS_RE.search(sanitized_full):
                return SafetyTriageDecision(
                    outcome="vet_emergency",
                    category="urinary_obstruction",
                    matched_signals=("litter_straining", "low_or_absent_urine_or_pain"),
                    bypass_attempt_detected=bypass_attempt,
                )

        # 2. Breathing / Respiratory Distress Check (Clause-level negation aware)
        for clause in clauses:
            for pat in _RESPIRATORY_PATTERNS:
                m = pat.search(clause)
                if m:
                    if m.group(0).startswith(("khong ", "cannot", "can t", "cant")):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="respiratory_distress",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )
                    if not _is_match_negated_in_clause(clause, m.start()):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="respiratory_distress",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )

        # 3. Acute Poisoning, Toxic Substance, or Swallowed Human Drug Check
        has_acute_exposure = _has_non_negated_acute_ingestion(clauses)
        is_educational_query = bool(_GENERAL_EDUCATIONAL_TOXIN_RE.search(sanitized_full)) and not has_acute_exposure

        if not is_educational_query:
            for clause in clauses:
                for pat in _DIRECT_POISONING_PATTERNS:
                    m = pat.search(clause)
                    if m and not _is_match_negated_in_clause(clause, m.start()):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="toxin_or_foreign_body_ingestion",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )

            if has_acute_exposure:
                tox_match = _TOXIC_SUBSTANCES_RE.search(sanitized_full)
                if tox_match:
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="toxin_or_foreign_body_ingestion",
                        matched_signals=("acute_ingestion", tox_match.group(0)),
                        bypass_attempt_detected=bypass_attempt,
                    )
                med_ingested = _HUMAN_MEDICATION_NAMES_RE.search(sanitized_full)
                if med_ingested and not re.search(r"\b(?:duoc khong|co sao khong|co nen|can i give|should i give|is it safe)\b", sanitized_full):
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="human_medication_toxicity_or_dosing",
                        matched_signals=("acute_medication_ingestion", med_ingested.group(0)),
                        bypass_attempt_detected=bypass_attempt,
                    )

        # 4a. Forebrain Neurological Red Flags (Head-Pressing, Acute Circling/Falling) & Jaundice / Icterus
        for clause in clauses:
            for pat in _NEUROLOGICAL_OR_JAUNDICE_PATTERNS:
                m = pat.search(clause)
                if m and not _is_match_negated_in_clause(clause, m.start(), m.group(0)):
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="acute_neurological_or_jaundice",
                        matched_signals=(m.group(0),),
                        bypass_attempt_detected=bypass_attempt,
                    )

        # 4b. Mucous-Membrane Pallor & Circulatory Shock / Cold Extremities
        for clause in clauses:
            for pat in _PALLOR_PATTERNS:
                m = pat.search(clause)
                if m and not _is_match_negated_in_clause(clause, m.start(), m.group(0)):
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="mucous_membrane_or_shock",
                        matched_signals=(m.group(0),),
                        bypass_attempt_detected=bypass_attempt,
                    )

        if not _WINTER_APPAREL_CONTEXT_RE.search(sanitized_full):
            has_cold_extremities = any(
                (m := _COLD_EXTREMITIES_RE.search(clause)) is not None
                and not _is_match_negated_in_clause(clause, m.start(), m.group(0))
                for clause in clauses
            )
            has_systemic_weakness = any(
                (m := _SHOCK_SYSTEMIC_WEAKNESS_RE.search(clause)) is not None
                and not _is_match_negated_in_clause(clause, m.start(), m.group(0))
                for clause in clauses
            )
            if has_cold_extremities and has_systemic_weakness:
                return SafetyTriageDecision(
                    outcome="vet_emergency",
                    category="mucous_membrane_or_shock",
                    matched_signals=("cold_extremities", "systemic_weakness_or_shock"),
                    bypass_attempt_detected=bypass_attempt,
                )

        # 4c. Severe Neurological, Hemorrhage, Bloat (GDV), or Trauma Symptoms
        for clause in clauses:
            for pat in _SEVERE_ACUTE_PATTERNS:
                m = pat.search(clause)
                if m:
                    if m.group(0).startswith(("khong ", "cannot")):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="acute_neurological_or_collapse",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )
                    if not _is_match_negated_in_clause(clause, m.start()):
                        return SafetyTriageDecision(
                            outcome="vet_emergency",
                            category="hemorrhage_trauma_or_bloat",
                            matched_signals=(m.group(0),),
                            bypass_attempt_detected=bypass_attempt,
                        )

    # 5. Dangerous Human Medication Inquiry, Unsafe Home Emetics & Prescription / Dosage / Diagnosis Boundary
    for clause in clauses:
        emetic_match = _UNSAFE_HOME_EMETIC_RE.search(clause)
        if emetic_match and not _is_match_negated_in_clause(clause, emetic_match.start()):
            return SafetyTriageDecision(
                outcome="vet_medical_boundary",
                category="human_medication_toxicity_or_dosing",
                matched_signals=(emetic_match.group(0),),
                bypass_attempt_detected=bypass_attempt,
            )

    asks_permission = bool(
        re.search(r"\b(?:duoc khong|co nen|co sao khong|can i|should i|is it ok|is it safe)\b", sanitized_full)
    )
    for clause in clauses:
        med_match = _HUMAN_MEDICATION_NAMES_RE.search(clause)
        if med_match and (asks_permission or not _is_match_negated_in_clause(clause, med_match.start())):
            if not re.search(r"\b(?:tai sao khong|why shouldn t|why never)\b", sanitized_full):
                return SafetyTriageDecision(
                    outcome="vet_medical_boundary",
                    category="human_medication_toxicity_or_dosing",
                    matched_signals=(med_match.group(0),),
                    bypass_attempt_detected=bypass_attempt,
                )

    is_feed_nutrient_label_query = _is_nutritional_label_composition_query(sanitized_full)
    if not is_feed_nutrient_label_query:
        for clause in clauses:
            for pat in _DOSING_OR_PRESCRIPTION_PATTERNS:
                m = pat.search(clause)
                if m and not _is_match_negated_in_clause(clause, m.start()):
                    return SafetyTriageDecision(
                        outcome="vet_medical_boundary",
                        category="prescription_or_diagnosis_boundary",
                        matched_signals=(m.group(0),),
                        bypass_attempt_detected=bypass_attempt,
                    )

    return SafetyTriageDecision(outcome="none", bypass_attempt_detected=bypass_attempt)
