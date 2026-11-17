"""Deterministic species canonicalization and coat-color taxonomy for AI-4.0a image matching.

This module normalizes bilingual (Vietnamese/English) species labels and coat descriptions
without guessing or inferring unverified attributes.
"""

from __future__ import annotations

import re
import unicodedata

COAT_PROFILE_BUCKETS: tuple[str, ...] = (
    "orange_gold",
    "cream_tan",
    "brown",
    "black_dark",
    "gray_silver",
    "white_light",
    "other",
)

_CAT_ALIASES = frozenset({
    "cat", "cats", "feline", "kitten", "kittens",
    "meo", "meo con", "meo ta", "meo anh", "meo ba tu",
})
_DOG_ALIASES = frozenset({
    "dog", "dogs", "canine", "puppy", "puppies",
    "cho", "cho con", "cun", "cun con", "cho ta",
})
_RABBIT_ALIASES = frozenset({"rabbit", "rabbits", "bunny", "tho", "tho con"})
_HAMSTER_ALIASES = frozenset({"hamster", "hamsters", "chuot hamster"})
_BIRD_ALIASES = frozenset({"bird", "birds", "chim", "vet"})

_SQL_SPECIES_MAP: dict[str, tuple[str, ...]] = {
    "cat": ("Mèo", "mèo", "cat", "cats", "feline", "kitten", "Mèo con"),
    "dog": ("Chó", "chó", "dog", "dogs", "canine", "puppy", "Chó con"),
    "rabbit": ("Thỏ", "thỏ", "rabbit", "bunny", "Thỏ con", "rabbits", "tho"),
    "hamster": ("Hamster", "hamster", "Chuột hamster", "hamsters", "chuot hamster", "HAMSTER", "Hamster bear"),
    "bird": ("Chim", "chim", "bird", "birds", "Vẹt", "vẹt", "parrot"),
}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value or "").casefold().replace("đ", "d"))
    cleaned = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", cleaned))


def canonicalize_species(value: str | None) -> str | None:
    """Normalize free-text Vietnamese/English species strings into canonical tokens.

    Returns ``None`` when ``value`` is empty/whitespace. Unknown non-empty strings
    return ``'other:<normalized>'`` so explicit exotic filters never collide with
    ``'cat'`` or ``'dog'``.
    """
    if value is None:
        return None
    norm = _strip_accents(value)
    if not norm:
        return None
    if norm in _CAT_ALIASES or norm.startswith("meo ") or norm.endswith(" cat"):
        return "cat"
    if norm in _DOG_ALIASES or norm.startswith("cho ") or norm.endswith(" dog"):
        return "dog"
    if norm in _RABBIT_ALIASES or norm.startswith("tho "):
        return "rabbit"
    if norm in _HAMSTER_ALIASES or "hamster" in norm:
        return "hamster"
    if norm in _BIRD_ALIASES:
        return "bird"
    return f"other:{norm}"


def sql_species_aliases(raw_species: str) -> tuple[str, ...]:
    """Return a 7-tuple of SQL IN-clause aliases for ``iter_filtered_for_image_search``."""
    canon = canonicalize_species(raw_species)
    if canon in _SQL_SPECIES_MAP:
        return _SQL_SPECIES_MAP[canon]
    cleaned = (raw_species or "").strip()
    return (cleaned,) * 7


def extract_db_coat_groups(coat_color: str | None, appearance_tags: str | None = "") -> frozenset[str]:
    """Map verified store coat/tag descriptions into canonical coat-color families."""
    norm = _strip_accents(f"{coat_color or ''} {appearance_tags or ''}")
    if not norm:
        return frozenset()
    tokens = set(norm.split())
    groups: set[str] = set()
    if tokens & {"cam", "orange", "ginger", "vang", "yellow", "golden", "gung"} or "mat ong" in norm:
        groups.add("orange_gold")
    if tokens & {"kem", "cream", "beige"}:
        groups.add("cream_tan")
    if (
        tokens & {"nau", "brown", "tan", "do", "muop", "tabby", "ven"}
        or "so co la" in norm
        or "chocolate" in norm
        or "doi moi" in norm
    ):
        groups.add("brown")
    if tokens & {"den", "black", "tuxedo"}:
        groups.add("black_dark")
    if tokens & {"xam", "bac", "gray", "grey", "silver", "khoi"} or "xam xanh" in norm:
        groups.add("gray_silver")
    if tokens & {"trang", "white", "ivory"}:
        groups.add("white_light")
    return frozenset(groups)


def extract_query_chromatic_groups(coat_profile: tuple[float, ...]) -> frozenset[str]:
    """Extract dominant subject coat families from a 7-bucket backdrop-masked coat profile.

    Chromatic fur buckets take priority over ``white_light`` on bicolor pets so an
    orange-and-white cat prioritizes orange/cream/calico candidates rather than
    matching solid white or black-and-white cats on white chest fur alone.
    """
    if len(coat_profile) != len(COAT_PROFILE_BUCKETS):
        return frozenset()
    by_bucket = dict(zip(COAT_PROFILE_BUCKETS, coat_profile))
    chromatic: set[str] = set()
    for key in ("orange_gold", "cream_tan", "brown", "black_dark", "gray_silver"):
        if by_bucket[key] >= 0.20:
            chromatic.add(key)
    if by_bucket["orange_gold"] + by_bucket["cream_tan"] >= 0.34:
        chromatic.update({"orange_gold", "cream_tan"})
    if chromatic:
        return frozenset(chromatic)
    if by_bucket["white_light"] >= 0.28:
        return frozenset({"white_light"})
    return frozenset()


def coat_groups_compatible(
    query_profile: tuple[float, ...],
    pet_coat_color: str | None,
    pet_appearance_tags: str | None = "",
    candidate_profile: tuple[float, ...] = (),
) -> bool:
    """Return whether a candidate's coat color family is compatible with the query subject."""
    q_groups = extract_query_chromatic_groups(query_profile)
    c_groups = extract_db_coat_groups(pet_coat_color, pet_appearance_tags)
    if not c_groups and len(candidate_profile) == len(COAT_PROFILE_BUCKETS):
        c_groups = extract_query_chromatic_groups(candidate_profile)
    if not q_groups or not c_groups:
        return True
    # Treat warm orange_gold and cream_tan as mutually compatible ginger/cream shades
    expanded_q = set(q_groups)
    if expanded_q & {"orange_gold", "cream_tan"}:
        expanded_q.update({"orange_gold", "cream_tan"})
    return bool(expanded_q & c_groups)

