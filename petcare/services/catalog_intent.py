"""Deterministic assistant intent parsing and catalog filters."""

from __future__ import annotations

import re
import unicodedata

from petcare.services.assistant_query import catalog_filters


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return "".join(char for char in folded if unicodedata.category(char) != "Mn")


def _catalog_preview_truncated(context: dict, catalog: str) -> bool:
    return bool(context.get("catalog_preview_truncated", {}).get(catalog, False))


_PET_STOPWORDS = {
    "ai", "animal", "animals", "are", "available", "bao", "ban", "breed", "co", "con", "cung",
    "dang", "danh", "dog", "dogs", "dong", "duoc", "find", "for", "gia", "gi", "hay",
    "have", "how", "is", "la", "long", "many", "mau", "mat", "much", "nao", "nhieu", "of", "or", "pet", "pets", "sale",
    "sach", "show", "the", "toi", "thu", "tim", "to", "va", "which", "with", "cho", "meo",
    "cun", "cat", "cats", "puppy", "puppies", "kitten", "kittens", "feline", "canine", "fur",
    "coat", "color", "colour", "eye", "eyes", "giong", "khong", "male", "female", "duc", "truc", "cai", "under", "below", "less",
    "toida", "upto", "budget", "million", "m", "trieu", "tr", "nghin", "ngan", "k",
}


_COLOR_WORDS = {
    "den", "black", "trang", "white", "ivory", "xam", "gray", "grey", "silver", "bac",
    "nau", "brown", "tan", "socola", "chocolate", "vang", "yellow", "golden", "cam",
    "orange", "ginger", "kem", "cream", "beige", "xanh", "blue", "green", "la", "duong",
    "hong", "pink", "amber", "ho", "phach",
}


_COAT_COLOR_ALIASES = {
    "den": ("den", "black"),
    "trang": ("trang", "white", "ivory"),
    "xam": ("xam", "gray", "grey", "silver", "bac"),
    "nau": ("nau", "brown", "tan", "socola", "chocolate"),
    "vang": ("vang", "yellow", "gold", "golden"),
    "phach": ("phach", "ho", "amber", "hazel"),
    "cam": ("cam", "orange", "ginger"),
    "kem": ("kem", "cream", "beige"),
    "xanh": ("xanh", "blue", "green"),
    "hong": ("hong", "pink"),
}


_PRODUCT_STOPWORDS = {
    "bao", "can", "co", "con", "cua", "danh", "gia", "gi", "hang", "kho", "la", "mat",
    "nao", "nhieu", "san", "sach", "stock", "product", "products", "catalog", "item", "items",
    "the", "ton", "toi", "tim", "va", "xem", "cho", "duoi", "tren", "loai", "muc", "pham",
    "active", "all", "are", "any", "at", "below", "biet", "budget", "cost", "costs", "find", "for", "have", "het", "how", "in", "is", "k", "level", "less", "list", "low", "m", "me", "million", "much", "ngan", "nghin", "nguong", "price", "please", "reached", "reorder", "restock", "sap", "show", "tell", "threshold", "toida", "tr", "trieu", "under", "upto", "which",
}


_PRODUCT_INTENT_PHRASES = (
    "san pham", "mat hang", "product", "catalog", "item", "thuc an", "cat food", "dog food",
    "pate", "phu kien", "do choi", "cham soc", "cat ve sinh", "cat dau nanh",
    "pet supplies", "cat litter", "litter",
    "food", "accessory", "accessories", "toy", "toys",
)


_STOCK_INTENT_PHRASES = (
    "ton kho", "sap het", "con bao nhieu", "con may", "inventory", "stock", "low", "restock", "remaining",
)


_PET_QUERY_PHRASES = (
    "thu cung", "dong vat", "con meo", "con cho", "meo nao", "cho nao", "mau long", "mau mat",
    "breed", "giong", "dog breed", "cat breed", "pets for sale", "available pets",
)


def _product_intent(query: str, raw_query: str | None = None) -> bool:
    vietnamese_litter = bool(
        raw_query
        and re.search(r"\bcát\b", raw_query, re.IGNORECASE)
        and not re.search(r"\b(mèo|chó|thú cưng)\b", raw_query, re.IGNORECASE)
    )
    return vietnamese_litter or any(phrase in query for phrase in _PRODUCT_INTENT_PHRASES)


def _pet_intent(query: str, raw_query: str | None = None) -> bool:
    explicit_pet_query = any(phrase in query for phrase in _PET_QUERY_PHRASES)
    if _product_intent(query, raw_query) and not explicit_pet_query:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", query))
    vietnamese_dog = bool(raw_query and re.search(r"\bchó\b", raw_query, re.IGNORECASE))
    unaccented_dog_traits = "cho" in tokens and bool(
        tokens & (_COLOR_WORDS | {"long", "fur", "coat", "giong", "breed"})
    )
    return explicit_pet_query or vietnamese_dog or unaccented_dog_traits or bool(
        tokens & {"pet", "pets", "animal", "animals", "kitten", "kittens", "puppy", "puppies",
                  "meo", "dog", "dogs", "cat", "cats", "cun", "feline", "canine", "tho", "rabbit", "hamster"}
    ) or query.strip() == "cho"


def _question_intent(question):
    """Classify the requested subject independently of its time filters."""
    query = _normalize(question)
    if any(phrase in query for phrase in ("doanh thu", "ban duoc", "thu duoc", "revenue", "sales")):
        return "revenue"
    if any(phrase in query for phrase in ("tim bang anh", "quet anh", "scan", "camera", "similar image", "photo search")):
        return "image"
    if _pet_intent(query, question):
        return "pet"
    if any(phrase in query for phrase in _STOCK_INTENT_PHRASES):
        return "stock"
    if _product_intent(query, question):
        return "product"
    return "other"


def pet_filter_spec(question: str) -> dict:
    """Compile visible traits independently of the catalog or its preview size."""
    query, price_filters = catalog_filters(_normalize(question))
    ordered_tokens = re.findall(r"[a-z0-9]+", query)
    tokens = set(ordered_tokens)
    species = None
    if tokens & {"meo", "cat", "cats", "kitten", "kittens", "feline"}:
        species = "cat"
    elif tokens & {"dog", "dogs", "puppy", "puppies", "canine", "cun"} or (
        "cho" in tokens and not query.startswith("cho toi")
    ):
        species = "dog"

    coat_markers = {"long", "coat", "fur"}
    eye_markers = {"mat", "eye", "eyes"}
    attribute_markers = coat_markers | eye_markers
    coat_colors, eye_colors = [], []
    color_candidates = []
    for index, token in enumerate(ordered_tokens):
        aliases = next(
            (aliases for word, aliases in _COAT_COLOR_ALIASES.items()
             if token == word or any(_normalize(alias) == token for alias in aliases)),
            None,
        )
        if aliases:
            color_candidates.append((index, aliases))
    markers = [
        (index, "coat" if token in coat_markers else "eye")
        for index, token in enumerate(ordered_tokens) if token in attribute_markers
    ]

    def add_color(field, aliases):
        (eye_colors if field == "eye" else coat_colors).append(aliases)

    assigned = set()
    # Prefer color words that follow their attribute ("lông trắng", "mắt xanh").
    for color_index, aliases in color_candidates:
        previous = next((marker for marker in reversed(markers) if marker[0] < color_index), None)
        following = next((marker for marker in markers if marker[0] > color_index), None)
        if previous and color_index - previous[0] <= 2 and (
            not following or color_index - previous[0] <= following[0] - color_index
        ):
            add_color(previous[1], aliases)
            assigned.add(color_index)

    for color_index, aliases in color_candidates:
        if color_index in assigned:
            continue
        following = next((marker for marker in markers if marker[0] > color_index), None)
        if following and following[0] - color_index <= 1:
            target_colors = eye_colors if following[1] == "eye" else coat_colors
            # In "mèo trắng mắt xanh", the post-marker eye color is the better match;
            # the preceding bare color stays a coat color.
            if following[1] != "eye" or not target_colors:
                add_color(following[1], aliases)
                assigned.add(color_index)
        if color_index not in assigned:
            coat_colors.append(aliases)
    sex = "male" if tokens & {"male", "duc", "truc"} else (
        "female" if tokens & {"female", "cai"} else None
    )
    # Do not infer meaningful search terms from the bounded preview itself: a
    # breed absent from the first 250 records must not silently turn into a
    # broad species-only query.
    specific_terms = sorted({token for token in tokens
        if token.isalpha() and token not in _PET_STOPWORDS and token not in _COLOR_WORDS}
        | set(re.findall(r"\bpet-\d+\b", query)))

    return {"species": species, "sex": sex, "coat_colors": coat_colors,
            "eye_colors": eye_colors, "terms": specific_terms, "prices": price_filters}


def _pet_search(question: str, context: dict) -> tuple[list[dict], bool]:
    spec = pet_filter_spec(question)
    species, sex = spec["species"], spec["sex"]
    coat_colors, eye_colors = spec["coat_colors"], spec["eye_colors"]
    specific_terms, price_filters = spec["terms"], spec["prices"]
    pets = context.get("available_pets", [])
    def matches(pet):
        pet_species = _normalize(pet.get("species", ""))
        if species == "cat" and not any(word in pet_species for word in ("meo", "cat", "feline")):
            return False
        if species == "dog" and not any(word in pet_species for word in ("cho", "dog", "canine")):
            return False
        if sex and pet.get("sex") not in {sex, "unknown", None, ""}:
            return False
        if not all(price.matches(pet.get("sale_price")) for price in price_filters):
            return False
        for color_field, requested in (("coat_color", coat_colors), ("eye_color", eye_colors)):
            if requested:
                color_value = _normalize(pet.get(color_field, ""))
                if not all(
                    any(_normalize(alias) in color_value for alias in aliases)
                    for aliases in requested
                ):
                    return False
        searchable = " ".join(
            _normalize(pet.get(key, ""))
            for key in ("name", "breed", "species", "coat_color", "eye_color", "appearance_tags")
        )
        return all(term in searchable for term in specific_terms)

    selected = [pet for pet in pets if matches(pet)]
    narrowed = bool(species or coat_colors or eye_colors or sex or specific_terms or price_filters)
    return selected, narrowed


def _product_search(question: str, context: dict) -> tuple[list[dict], bool]:
    query, price_filters = catalog_filters(_normalize(question))
    query_tokens = set(re.findall(r"[a-z0-9]+", query))
    products = context.get("products", [])
    # Search terms must come from the question, not from the capped catalog
    # preview, or a new product name can be silently dropped from the filter.
    terms = sorted(query_tokens - _PRODUCT_STOPWORDS)
    if not terms and not price_filters:
        return products, False
    return [
        item for item in products
        if all(price.matches(item.get("unit_price")) for price in price_filters) and all(
            term in " ".join(_normalize(item.get(key, "")) for key in ("name", "code", "category"))
            for term in terms
        )
    ], True
