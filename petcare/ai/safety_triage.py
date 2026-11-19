"""Dedicated Server-Side Veterinary Safety Triage Engine (AI-2.1 / AI-2.2 / AI-3).

Executes deterministically BEFORE shopping intent routing, catalog search, product
recommendations, or LLM tool selection. Separates four explicit safety/care tiers:
1. `"none"` — General pet-care knowledge, safe ingredient exclusions, dietary allergies,
   resolved historical conditions, negated symptoms, and routine shopping.
2. `"vet_nonurgent_referral"` — Active subacute or unrecognized clinical concerns
   (e.g., multi-day anorexia with lethargy/fever, purulent swelling/abscess/mass,
   acute non-weight-bearing lameness, persistent repeated vomiting/watery diarrhea)
   where safe veterinary referral/clarification is preferred over retail shopping.
3. `"vet_emergency"` — Urgent symptoms & acute incidents:
   - Urinary obstruction / prolonged straining without urine output.
   - Breathing difficulty / open-mouth breathing / orthopnea posture.
   - Suspected poisoning & acute ingestion of toxic foods, plants, chemicals, or foreign bodies.
   - Accidental therapeutic medication overdose / double administration (e.g., double insulin + neuro signs).
   - Post-operative surgical wound dehiscence / ripped sutures / exposed underlying tissue.
   - Severe neurological (seizures, head-pressing, acute ataxia), icterus/jaundice,
     mucous-membrane pallor / circulatory shock, hemorrhagic, bloat (GDV), or trauma symptoms.
4. `"vet_medical_boundary"` — Unsafe medical instructions: human OTC drugs, unsafe home
   emetics, prescription requests, mg/kg drug dosing, or clinical disease diagnosis.

Limitation notice: Rule-based and compositional symptom/incident triage improves recall on
clinically documented red flags in Vietnamese and English (referenced against AVMA, ASPCA Poison
Control, AAHA Diabetes Management Guidelines, and Cornell Feline Health Center public guidance),
but has not undergone independent clinical sign-off by a licensed veterinarian (DVM), cannot
recognize every atypical veterinary presentation, and never diagnoses disease.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from petcare.services.catalog_intent import _normalize


@dataclass(frozen=True, slots=True)
class SafetyTriageDecision:
    """Structured output of the server-side pre-routing veterinary safety check."""

    outcome: str  # "none" | "vet_nonurgent_referral" | "vet_emergency" | "vet_medical_boundary"
    category: str | None = None
    matched_signals: tuple[str, ...] = ()
    bypass_attempt_detected: bool = False

    @property
    def is_triggered(self) -> bool:
        return self.outcome in {
            "vet_emergency",
            "vet_medical_boundary",
            "vet_nonurgent_referral",
        }


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
    re.compile(r"\bkhong\s+(?:di\s+)?(?:tieu|dai)\s+(?:duoc|ra|noi)\b"),
    re.compile(r"\b(?:tieu|dai)\s+khong\s+(?:ra|duoc|noi)\b"),
    re.compile(
        r"\bkhong\s+(?:ra|ri|nho|co|thay\s+ra)\s+(?:duoc\s+)?"
        r"(?:giot\s+|ti\s+|chut\s+|mieng\s+)?(?:nuoc\s+)?(?:tieu|dai)(?:\s+nao)?\b"
    ),
    re.compile(r"\b(?:cannot|can t|cant|unable\s+to|failed\s+to)\s+(?:urinate|pee|pass(?:\s+any)?\s+urine)\b"),
    re.compile(r"\b(?:produced|passing|passed|producing)\s+(?:no|zero|little|almost\s+no|scant)\s+(?:urine|pee)\b"),
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

# Compositional urinary concepts: (a) straining / repeated agitated litter-box visits + (b) absent/scant urine or vocal pain
_LITTER_OR_POSTURE_STRAIN_RE = re.compile(
    r"\b(?:ngoi\s+ran|cu\s+ran|ran\s+mai|ran\s+hoai|co\s+ran|ran\s+dau|ran\s+tieu|ran\s+dai|ran\s+nay\s+gio|"
    r"(?:vao|ra\s+vao|nhay\s+ra\s+nhay\s+(?:vo|vao)|chui\s+ra\s+chui\s+(?:vo|vao)|leo\s+ra\s+leo\s+(?:vo|vao)|"
    r"di\s+ra\s+di\s+vao|leo\s+vo|leo\s+vao|chui\s+vo|chui\s+vao|ngoi\s+trong)\s+"
    r"(?:khay|chau|thau|hop|bon|nha)\s+(?:cat|ve\s+sinh)"
    r"(?:[^.!?]{0,45}\b(?:lien\s+tuc|mai|hoai|nhieu\s+lan|gao|khoc|keu|ren|ran))?|"
    r"straining(?:\s+hard|\s+repeatedly)?(?:\s+in\s+(?:the\s+)?(?:litter\s*box|box))?|"
    r"squatting\s+(?:repeatedly\s+)?in\s+(?:the\s+)?(?:litter|box)|"
    r"(?:repeated\s+trips\s+to|in\s+and\s+out\s+of|keeps?\s+(?:going|jumping|visiting)(?:\s+into|\s+to)?|"
    r"crying\s+in|yowling\s+in)\s+(?:the\s+|his\s+|her\s+)?(?:litter\s*box|litter\s+tray|box))\b"
)
_LOW_URINE_OR_DISTRESS_RE = re.compile(
    r"\b(?:khong\s+(?:ra|ri|nho|co|thay)(?:\s+duoc)?(?:\s+(?:giot|ti|chut|mieng))?|chua\s+ra|"
    r"chi\s+(?:ra|ri)\s+(?:vai\s+giot|nho\s+giot|tung\s+giot)|nho\s+giot|tung\s+giot|"
    r"cat\s+(?:van\s+)?kho|cat\s+kho\s+cong|khong\s+thay\s+uot|"
    r"gao\s+khoc|keu\s+gao|keu\s+dau|keu\s+ren|dau\s+bung|liem\s+bo\s+phan\s+sinh\s+duc|"
    r"no\s+(?:urine|pee)|nothing\s+(?:comes?|came|is\s+coming)\s+out|"
    r"without\s+(?:passing\s+)?(?:any\s+)?(?:urine|pee|a\s+drop)|not\s+a\s+(?:single\s+)?drop|"
    r"only\s+a\s+few\s+drops|just\s+a\s+drop|drops\s+of\s+urine|dry\s+(?:litter|clumps?)|completely\s+dry|"
    r"yowling|crying\s+in\s+pain|howling\s+in\s+pain|licking\s+(?:his\s+|her\s+|its\s+)?genitals)\b"
)


# --- 2. Breathing / Respiratory Distress Rules (Direct + Order-Independent Compositional) ---
_RESPIRATORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:kho tho|tho gap|tho doc|ha mieng tho|ha mom tho|meo tho bang mieng|tho bung|tho rut lom bung|ngat tho|nghet tho|ngop tho|hoc xuong.*tho)\b"),
    re.compile(r"\b(?:luoi tim|loi tim|nuou tim|niem mac tim tai|tim tai)\b"),
    re.compile(r"\bkhong\s+tho\s+(?:duoc|noi)\b"),
    re.compile(r"\b(?:difficulty|trouble|hard(?:\s+time)?|struggling)\s+(?:to\s+)?breath(?:e|ing)\b"),
    re.compile(r"\b(?:labored|open[-\s]mouth)\s+breathing\b"),
    re.compile(
        r"\b(?:cat|kitten)\s+(?:is\s+)?panting\s+with\s+(?:its\s+|his\s+|her\s+)?"
        r"mouth\s+(?:wide\s+|fully\s+|still\s+|constantly\s+)?open\b"
    ),
    re.compile(
        r"\bbreathing\s+(?:heavily\s+|rapidly\s+|fast\s+|hard\s+)?with\s+(?:its\s+|his\s+|her\s+)?"
        r"mouth\s+(?:wide\s+|fully\s+|still\s+|constantly\s+)?open\b"
    ),
    re.compile(r"\b(?:gasping\s+for\s+air|gasping|choking|blue\s+gums|purple\s+tongue|cyanotic|respiratory\s+distress)\b"),
    re.compile(r"\b(?:cannot|can t|cant)\s+breathe\b"),
)

# Compositional respiratory concepts (word-order independent across clauses)
_RESPIRATORY_ACTIVITY_CONCEPT_RE = re.compile(
    r"\b(?:breath(?:e|es|ing)|pant(?:s|ing)|wheez(?:e|es|ing)|respirations?|tho)\b"
)
_OPEN_MOUTH_CONCEPT_RE = re.compile(
    r"\bmouth\s+(?:is\s+|stays?\s+|kept\s+|wide\s+|fully\s+|constantly\s+|still\s+|hanging\s+)*open\b"
    r"|\bopen[-\s]+(?:wide\s+)?mouth\b"
    r"|\b(?:ha|mo)\s+(?:rong\s+|to\s+)?(?:mieng|mom)\b"
    r"|\b(?:mieng|mom)\s+(?:ha|mo)\s+(?:rong|to|lien\s+tuc)\b"
)
_ORTHOPNEA_POSTURE_CONCEPT_RE = re.compile(
    r"\b(?:neck\s+(?:stretched|extended)(?:\s+out)?|sitting\s+hunched|crouched\s+with\s+elbows|"
    r"elbows?\s+(?:abducted|out)|(?:abdomen|belly|sides?|chest)\s+heaving|nostrils?\s+flaring|"
    r"vuon\s+(?:dai\s+)?co|duoi\s+thang\s+co|ngoi\s+co\s+ro|bung\s+phap\s+phong|canh\s+mui\s+phap\s+phong)\b"
)
_BENIGN_DENTAL_OR_POST_EXERCISE_RE = re.compile(
    r"\b(?:brush(?:ing)?\s+teeth|tooth\s*brush|toothpaste|kem\s+danh\s+rang|danh\s+rang|"
    r"after\s+(?:playing\s+fetch|running\s+at\s+the\s+park|vigorous\s+play)|sau\s+khi\s+chay\s+choi)\b"
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

# --- 6. Therapeutic Medication Overdose / Double Administration & Post-Operative Wound Dehiscence ---
_THERAPEUTIC_OVERDOSE_EVENT_RE = re.compile(
    r"\b(?:twice|two\s+doses|double\s+(?:the\s+)?(?:dose|dosed|shot|injection|amount)|2x\s+(?:the\s+)?dose|"
    r"overdosed?|overdose\s+of|too\s+much\s+(?:insulin|medication|medicine|sedative)|"
    r"accidentally\s+(?:gave|injected|administered|dosed)[^.!?]{0,45}\b(?:again|twice|double|extra|two\s+times)|"
    r"second\s+(?:dose|shot|injection)\s+by\s+mistake|"
    r"(?:tiem|chich|cho\s+uong|nho|dung)\s+(?:nham|lo|lap\s+lai)?[^.!?]{0,35}"
    r"\b(?:hai\s+lan|2\s+lan|hai\s+mui|2\s+mui|gap\s+doi|qua\s+lieu|them\s+mot\s+(?:lieu|mui)\s+nua)|"
    r"qua\s+lieu\s+thuoc|tiem\s+qua\s+lieu|uong\s+qua\s+lieu)\b"
)
_THERAPEUTIC_AGENT_RE = re.compile(
    r"\b(?:insulin|insuline|thuoc\s+tieu\s+duong|medication|medicine|prescription|dose|injection|shot|"
    r"sedative|anesthetic|phenobarbital|gabapentin|furosemide|heart\s+meds?|seizure\s+meds?|thyroid\s+meds?|"
    r"thuoc|mui\s+tiem|vien\s+thuoc|lieu\s+thuoc)\b"
)
_INSULIN_AGENT_RE = re.compile(r"\b(?:insulin|insuline|thuoc\s+tieu\s+duong)\b")
_HYPOGLYCEMIC_OR_TOXIC_NEURO_RE = re.compile(
    r"\b(?:wobbling|wobbly|staggering|ataxia|staring\s+blankly|glassy[-\s]eyed|dazed|disoriented|"
    r"trembling|shaking|twitching|weak|lethargic|limp|acting\s+drunk|"
    r"loang\s+choang|lao\s+dao|do\s+dan|nhin\s+vo\s+hon|mat\s+phuong\s+huong|run\s+ray|met\s+la|ha\s+duong\s+huyet)\b"
)

_SURGICAL_OR_SUTURE_SITE_RE = re.compile(
    r"\b(?:spay(?:ed)?|neuter(?:ed)?|castrat(?:ed|ion)|c[-\s]?section|surgery|surgical|post[-\s]?op(?:erative)?|"
    r"stitches|sutures|staples|incision|belly\s+wound|abdominal\s+wound|"
    r"triet\s+san|mo\s+de|phau\s+thuat|hau\s+phau|chi\s+khau|chi\s+mo|vet\s+mo|vet\s+khau|mui\s+khau)\b"
)
_WOUND_DEHISCENCE_OR_EXPOSED_TISSUE_RE = re.compile(
    r"\b(?:chewed\s+(?:open|out|through|off)|ripped\s+(?:open|out)|pulled\s+out|popped\s+open|split\s+open|"
    r"came\s+(?:open|undone|apart)|opened\s+up|gaping(?:\s+open)?|dehiscence|bleeding\s+heavily|oozing\s+pus|"
    r"(?:pink\s+|red\s+|raw\s+)?(?:tissue|flesh|organ|organs|intestines?|bowels?|guts?|fat)\s+"
    r"(?:is\s+|are\s+)?(?:poking|sticking|hanging|bulging|protruding|coming|exposed)|"
    r"exposed\s+(?:tissue|flesh|muscle|bone|organs?)|"
    r"bung\s+chi|dut\s+chi|tuot\s+chi|can\s+(?:dut|bung|rach)(?:\s+(?:chi|vet\s+mo|vet\s+khau))?|"
    r"ho\s+(?:mieng|vet\s+mo|vet\s+khau|toac)|rach\s+(?:vet\s+mo|vet\s+khau)|bung\s+vet\s+mo|"
    r"loi\s+(?:thit|mo|ruot|noi\s+tang)|thit\s+(?:do|hong)\s+loi\s+ra)\b"
)
_STANDALONE_SEVERE_WOUND_RE = re.compile(
    r"\b(?:exposed\s+(?:bone|organs?|intestines?)|(?:intestines?|organs?|guts?)\s+(?:hanging|protruding|poking)\s+out|"
    r"deep\s+gaping\s+wound|vet\s+thuong\s+ho\s+sau|loi\s+(?:ruot|noi\s+tang|xuong)\s+ra\s+ngoai)\b"
)

# --- 7. Nonurgent / Unrecognized Potentially Serious Clinical Concerns (Vet Referral Before Shopping) ---
_PREVENTIVE_OR_DIETARY_CONTEXT_RE = re.compile(
    r"\b(?:de\s+khong|tranh\s+bi|han\s+che|phong\s+ngua|prevent(?:ing)?|avoid(?:ing)?|"
    r"khi\s+doi\s+(?:hat|thuc\s+an)|transition(?:ing)?\s+food|sensitive\s+stomach|bung\s+yeu|"
    r"bui\s+long|hairballs?|di\s+ung|allergic|allergy)\b"
)
_NONURGENT_CLINICAL_CONCERN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "prolonged_anorexia_or_lethargy",
        re.compile(
            r"\b(?:bo\s+an|khong\s+an\s+gi|nhin\s+an|stopped\s+eating|not\s+eating|refuses?\s+to\s+eat|hasn\s+t\s+eaten)\b"
            r"[^.!?]{0,45}\b(?:\d+\s*(?:ngay|hom|days?)|may\s+ngay|tu\s+hom\s+qua|since\s+yesterday|"
            r"nam\s+u\s+ru|met\s+moi|sot|fever|lethargic|hiding|sut\s+can|losing\s+weight)\b"
        ),
    ),
    (
        "purulent_discharge_or_swelling",
        re.compile(
            r"\b(?:chay\s+mu|co\s+mu|ap\s+xe|khoi\s+u\s+sung|cuc\s+u\s+to|mat\s+sung\s+hip|tai\s+chay\s+mu|"
            r"oozing\s+pus|yellow\s+pus|green\s+pus|abscess|swollen\s+shut|foul[-\s]smelling\s+discharge|"
            r"rapidly\s+growing\s+lump|bleeding\s+ulcer)\b"
        ),
    ),
    (
        "acute_pain_or_lameness",
        re.compile(
            r"\b(?:di\s+khap\s+khieng|co\s+chan\s+khong\s+cham\s+dat|keu\s+dau\s+khi\s+cham|"
            r"limping\s+badly|won\s+t\s+put\s+weight\s+on|cannot\s+bear\s+weight|yelping\s+in\s+pain)\b"
        ),
    ),
    (
        "persistent_gi_or_febrile_illness",
        re.compile(
            r"\b(?:non\s+nhieu\s+lan|non\s+lien\s+tuc|tieu\s+chay\s+phan\s+nuoc|sot\s+cao|"
            r"vomiting\s+repeatedly|throwing\s+up\s+all\s+(?:morning|day|night)|watery\s+diarrhea\s+for|"
            r"high\s+fever)\b"
        ),
    ),
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
    r"\b(?:khong(?!\s+(?:phan\s+ung|di\s+duoc|an\s+gi|cham\s+dat)\b)|chua|not(?!\s+(?:sure|eating)\b)|no|never|neither|nor|without)\b"
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


def _has_non_negated_concept(clauses: list[str], pattern: re.Pattern[str], *, check_span: bool = False) -> str | None:
    """Return the first non-negated match across active clauses, or `None`."""
    for clause in clauses:
        for m in pattern.finditer(clause):
            if not _is_match_negated_in_clause(clause, m.start(), m.group(0) if check_span else ""):
                return m.group(0)
    return None


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

            strain_sig = _has_non_negated_concept(clauses, _LITTER_OR_POSTURE_STRAIN_RE)
            if strain_sig and _LOW_URINE_OR_DISTRESS_RE.search(sanitized_full):
                return SafetyTriageDecision(
                    outcome="vet_emergency",
                    category="urinary_obstruction",
                    matched_signals=(strain_sig, "low_or_absent_urine_or_pain"),
                    bypass_attempt_detected=bypass_attempt,
                )

        # 2. Breathing / Respiratory Distress Check (Direct patterns + order-independent compositional posture/mouth)
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

        if not _BENIGN_DENTAL_OR_POST_EXERCISE_RE.search(sanitized_full):
            resp_verb = _has_non_negated_concept(clauses, _RESPIRATORY_ACTIVITY_CONCEPT_RE)
            if resp_verb is not None:
                open_mouth_sig = _has_non_negated_concept(clauses, _OPEN_MOUTH_CONCEPT_RE)
                orthopnea_sig = _has_non_negated_concept(clauses, _ORTHOPNEA_POSTURE_CONCEPT_RE)
                if open_mouth_sig is not None or orthopnea_sig is not None:
                    return SafetyTriageDecision(
                        outcome="vet_emergency",
                        category="respiratory_distress",
                        matched_signals=tuple(s for s in (resp_verb, open_mouth_sig, orthopnea_sig) if s),
                        bypass_attempt_detected=bypass_attempt,
                    )

        # 3a. Therapeutic Medication Overdose / Double Administration Incident (e.g., double insulin + neuro signs)
        overdose_sig = _has_non_negated_concept(clauses, _THERAPEUTIC_OVERDOSE_EVENT_RE)
        agent_sig = _has_non_negated_concept(clauses, _THERAPEUTIC_AGENT_RE)
        if overdose_sig is not None and agent_sig is not None:
            return SafetyTriageDecision(
                outcome="vet_emergency",
                category="medication_overdose_or_adverse_event",
                matched_signals=(overdose_sig, agent_sig),
                bypass_attempt_detected=bypass_attempt,
            )
        insulin_sig = _has_non_negated_concept(clauses, _INSULIN_AGENT_RE)
        hypoglycemic_sig = _has_non_negated_concept(clauses, _HYPOGLYCEMIC_OR_TOXIC_NEURO_RE)
        if insulin_sig is not None and hypoglycemic_sig is not None:
            return SafetyTriageDecision(
                outcome="vet_emergency",
                category="medication_overdose_or_adverse_event",
                matched_signals=(insulin_sig, hypoglycemic_sig),
                bypass_attempt_detected=bypass_attempt,
            )

        # 3b. Post-Operative Surgical Wound Dehiscence / Exposed Underlying Tissue
        standalone_wound = _has_non_negated_concept(clauses, _STANDALONE_SEVERE_WOUND_RE)
        if standalone_wound is not None:
            return SafetyTriageDecision(
                outcome="vet_emergency",
                category="post_operative_or_wound_emergency",
                matched_signals=(standalone_wound,),
                bypass_attempt_detected=bypass_attempt,
            )
        surg_site = _has_non_negated_concept(clauses, _SURGICAL_OR_SUTURE_SITE_RE)
        dehiscence_sig = _has_non_negated_concept(clauses, _WOUND_DEHISCENCE_OR_EXPOSED_TISSUE_RE)
        if surg_site is not None and dehiscence_sig is not None:
            return SafetyTriageDecision(
                outcome="vet_emergency",
                category="post_operative_or_wound_emergency",
                matched_signals=(surg_site, dehiscence_sig),
                bypass_attempt_detected=bypass_attempt,
            )

        # 3c. Acute Poisoning, Toxic Substance, or Swallowed Human Drug Check
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

    # 6. Nonurgent / Unrecognized Potentially Serious Clinical Concerns -> Safe Vet Referral Over Shopping
    if not is_resolved_history and not _PREVENTIVE_OR_DIETARY_CONTEXT_RE.search(sanitized_full):
        for concern_cat, concern_pat in _NONURGENT_CLINICAL_CONCERN_PATTERNS:
            sig = _has_non_negated_concept(clauses, concern_pat, check_span=True)
            if sig is not None:
                return SafetyTriageDecision(
                    outcome="vet_nonurgent_referral",
                    category=concern_cat,
                    matched_signals=(sig,),
                    bypass_attempt_detected=bypass_attempt,
                )

    return SafetyTriageDecision(outcome="none", bypass_attempt_detected=bypass_attempt)
