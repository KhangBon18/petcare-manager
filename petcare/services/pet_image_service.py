"""Rank currently available pets against an uploaded reference image."""

from __future__ import annotations

import base64
import heapq
import json
from pathlib import Path
import re
import unicodedata

from flask import current_app

from petcare.ai import client as ai_client
from petcare.database.connection import read_connection
from petcare.i18n import current_locale
from petcare.repositories import pet_repo
from petcare.services.common import require_actor, text_value
from petcare.services.ui_text import ui_text
from petcare.services.exceptions import ValidationError
from petcare.vision.coat_color_lab import (
    compare_lab_histograms,
    decode_embedding_f16_b64,
    embedding_cosine_similarity,
    lab_coat_groups_compatible,
)
from petcare.vision.image_features import (
    ImageDescriptor,
    InvalidImage,
    compare_coat_profiles,
    compare_images,
    compare_images_from_json,
    describe_image,
    descriptor_from_json,
    hamming_hex64,
    normalize_image_bytes,
    sha256_hex,
    similarity_components,
)
from petcare.vision.local_pet_detector import (
    SUBJECT_AMBIGUOUS,
    SUBJECT_MULTIPLE_ANIMALS,
    SUBJECT_NO_RELIABLE_ANIMAL,
    SUBJECT_ONE_CAT,
    SUBJECT_ONE_DOG,
    SUBJECT_OTHER_ANIMAL,
    SpeciesGateDecision,
    analyze_pet_image,
)
from petcare.vision.species_taxonomy import (
    canonicalize_species,
    coat_groups_compatible,
)


_VISION_PROMPT = (
    "Quan sát ngoại hình con vật trong ảnh và chỉ trả về một JSON hợp lệ bằng tiếng Việt "
    "với các khóa: species, breed, coat_color, coat_pattern, coat_length, eye_color, size, shape. "
    "species chỉ ghi loài như mèo, chó, thỏ, chim; breed chỉ ghi giống khi có dấu hiệu đủ rõ, "
    "không chắc thì để trống. Các trường còn lại mô tả ngắn những gì nhìn thấy; không suy đoán "
    "tuổi, sức khỏe hay danh tính. Nếu không nhìn rõ, ghi chuỗi rỗng."
)
_VISION_PROMPT_EN = (
    "Inspect only the animal's visible appearance and return valid JSON in English with "
    "these keys: species, breed, coat_color, coat_pattern, coat_length, eye_color, size, shape. "
    "Use a short species name (cat, dog, rabbit, bird). Give a breed only when visual evidence "
    "is strong; otherwise leave it empty. Keep other values brief, use an empty string when "
    "unclear, and do not infer age, health, or identity."
)
_RESULT_LIMIT = 12
_RESULT_MIN_SCORE = 0.12

# AI-4.0a evidence-backed match tiers and outcomes
MATCH_TIER_EXACT = "exact_image_match"
MATCH_TIER_NEAR_DUP = "near_duplicate_image"
MATCH_TIER_SIMILAR = "visually_similar_candidate"
MATCH_OUTCOME_NONE = "no_confident_match"

# Thresholds derived strictly from the identity-disjoint AI-4.0a calibration split
# (see scripts/evaluate_ai4_pet_image_matching.py):
# - Resized/re-encoded JPEG copies (480px q=70): dHash <= 1, pHash <= 2, vis >= 0.9526, structure >= 0.9993
# - Centered studio portraits of distinct cats can drop to dHash=7, pHash=8, vis=0.9288 under crops.
#   We therefore enforce a conservative precision-first near-duplicate gate (0 false positives on calibration).
NEAR_DUP_MAX_DHASH = 5
NEAR_DUP_MAX_PHASH = 6
NEAR_DUP_MAX_COMBINED_HASH = 9
NEAR_DUP_MIN_VISUAL_SCORE = 0.94
NEAR_DUP_MIN_STRUCTURE_SCORE = 0.96

# - Natural calibration pet portraits flat_pixel_ratio: 0.265 .. 0.592
# - UI/document/solid/cartoon calibration negatives flat_pixel_ratio: 0.754 .. 1.000
SIMILAR_MAX_FLAT_PIXEL_RATIO = 0.68
SIMILAR_MIN_COMBINED_SCORE = 0.68
SIMILAR_MIN_DETECTOR_BBOX_SCORE = 0.60
MAX_SIMILAR_CANDIDATES = 5

_RETRIEVAL_CALIBRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "vision"
    / "models"
    / "retrieval_ranking_calibration_v1.json"
)
_RETRIEVAL_CALIBRATION_CACHE: dict | None = None


def _get_retrieval_calibration() -> dict:
    global _RETRIEVAL_CALIBRATION_CACHE
    if _RETRIEVAL_CALIBRATION_CACHE is not None:
        return _RETRIEVAL_CALIBRATION_CACHE
    try:
        raw = json.loads(_RETRIEVAL_CALIBRATION_PATH.read_text(encoding="utf-8"))
        _RETRIEVAL_CALIBRATION_CACHE = dict(raw["parameters"])
    except Exception:
        _RETRIEVAL_CALIBRATION_CACHE = {
            "embedding_weight": 0.58,
            "lab_coat_weight": 0.34,
            "structure_weight": 0.08,
            "min_combined_similarity": 0.67,
            "min_embedding_cosine": 0.54,
            "min_lab_coat_similarity": 0.45,
            "max_similar_candidates": MAX_SIMILAR_CANDIDATES,
        }
    return _RETRIEVAL_CALIBRATION_CACHE
_VISION_FIELD_LIMITS = {
    "species": 80,
    "breed": 100,
    "coat_color": 80,
    "coat_pattern": 100,
    "coat_length": 60,
    "eye_color": 60,
    "size": 60,
    "shape": 80,
}
_VISION_ABSTENTION_VALUES = {
    "unknown", "uncertain", "not sure", "n/a", "na", "none",
    "khong ro", "chua ro", "khong xac dinh", "khong biet", "khong chac",
}
_ATTRIBUTE_ALIASES = {
    "cat": "species_cat",
    "cats": "species_cat",
    "feline": "species_cat",
    "kitten": "species_cat",
    "kittens": "species_cat",
    "meo": "species_cat",
    "dog": "species_dog",
    "dogs": "species_dog",
    "canine": "species_dog",
    "puppy": "species_dog",
    "puppies": "species_dog",
    "cho": "species_dog",
    "rabbit": "species_rabbit",
    "bunny": "species_rabbit",
    "tho": "species_rabbit",
    "bird": "species_bird",
    "chim": "species_bird",
    "black": "den",
    "white": "trang",
    "ivory": "trang",
    "gray": "xam",
    "grey": "xam",
    "silver": "xam",
    "brown": "nau",
    "tan": "nau",
    "orange": "cam",
    "ginger": "cam",
    "yellow": "vang",
    "golden": "vang",
    "amber": "vang",
    "cream": "kem",
    "beige": "kem",
    "blue": "bluecolor",
    "green": "greencolor",
    "tabby": "pattern_tabby",
    "muop": "pattern_tabby",
    "calico": "patterncalico",
    "tortoiseshell": "patterntortoiseshell",
    "tortie": "patterntortoiseshell",
    "bicolor": "patternbicolor",
    "shorthair": "coatshort",
    "longhair": "coatlong",
    "striped": "pattern_striped",
    "stripe": "pattern_striped",
    "soc": "pattern_striped",
    "spotted": "pattern_spotted",
    "spotty": "pattern_spotted",
    "dom": "pattern_spotted",
    "small": "nho",
    "tiny": "nho",
    "large": "lon",
    "big": "lon",
    "lon": "lon",
    "nho": "nho",
    "medium": "vua",
    "average": "vua",
    "vua": "vua",
}
_PHRASE_REPLACEMENTS = (
    (re.compile(r"\bshort[\s-]*haired\b|\bshort[\s-]+coat\b|l[oô]ng\s+ng[aă]n"), "coatshort"),
    (re.compile(r"\blong[\s-]*haired\b|\blong[\s-]+coat\b|l[oô]ng\s+d[aà]i"), "coatlong"),
    (re.compile(r"xanh[\s-]+d[uư][oơ]ng"), "bluecolor"),
    (re.compile(r"xanh\s+l[aá](?:\s+c[aâ]y)?"), "greencolor"),
    (re.compile(r"tam\s+th[eể]"), "patterncalico"),
    (re.compile(r"[dđ][oồ]i\s+m[oồ]i"), "patterntortoiseshell"),
    (re.compile(r"round\s+(?:face|head)|m[aặ]t\s+tr[oò]n"), "faceround"),
    (re.compile(r"folded\s+ears?|tai\s+c[uụ]p"), "earsfolded"),
    (re.compile(r"upright\s+ears?|erect\s+ears?|tai\s+d[uự]ng"), "earsupright"),
    (re.compile(r"pointed\s+ears?|tai\s+nh[oọ]n"), "earspointed"),
    (re.compile(r"fluffy|l[oô]ng\s+x[uù]"), "coatfluffy"),
)


def _normalize(text) -> str:
    value = unicodedata.normalize("NFD", str(text or "").casefold().replace("đ", "d"))
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def _tokens(text) -> set[str]:
    normalized = _normalize(text)
    for pattern, replacement in _PHRASE_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    return {
        _ATTRIBUTE_ALIASES.get(token, token)
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1
    }


def _species_tokens(text) -> set[str]:
    """Keep species scoring independent from coat and breed words in a model label."""
    species = {token for token in _tokens(text) if token.startswith("species_")}
    return species


def _coat_length_tokens(text) -> set[str]:
    tokens = _tokens(text)
    if "short" in tokens:
        tokens.discard("short")
        tokens.add("coatshort")
    if "long" in tokens:
        tokens.discard("long")
        tokens.add("coatlong")
    return tokens


def _clean_vision_value(value: str, maximum: int) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        " " if unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char
        for char in value
    )
    return " ".join(value.split())[:maximum]


def _analysis_from_model(image_bytes: bytes):
    if not current_app.config.get("AI_VISION_ENABLED") or not ai_client.is_configured():
        return None, None, "disabled"
    try:
        english = current_locale() == "en"
        response = ai_client.complete_vision(
            [
                {
                    "role": "system",
                    "content": (
                        "Analyze visible animal appearance carefully and avoid unsupported claims."
                        if english else "Bạn phân tích đặc điểm ngoại hình động vật từ ảnh."
                    ),
                },
                {"role": "user", "content": _VISION_PROMPT_EN if english else _VISION_PROMPT},
            ],
            image_bytes=image_bytes,
        )
        if not isinstance(response, str):
            return None, "Mô hình ảnh chưa trả về văn bản có cấu trúc; vẫn dùng xử lý cục bộ.", "invalid_output"
        start, end = response.find("{"), response.rfind("}")
        if start < 0 or end <= start:
            return None, "Mô hình ảnh chưa trả về mô tả có cấu trúc; vẫn dùng xử lý cục bộ.", "invalid_output"
        try:
            analysis = json.loads(response[start : end + 1])
        except json.JSONDecodeError:
            return None, "Mô hình ảnh trả về JSON không hợp lệ; vẫn dùng xử lý cục bộ.", "invalid_output"
        if not isinstance(analysis, dict):
            return None, "Mô hình ảnh chưa trả về mô tả có cấu trúc; vẫn dùng xử lý cục bộ.", "invalid_output"
        cleaned = {}
        invalid_fields = False
        for key, maximum in _VISION_FIELD_LIMITS.items():
            value = analysis.get(key, "")
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                invalid_fields = True
                continue
            normalized = _clean_vision_value(value, maximum)
            if _normalize(normalized) in _VISION_ABSTENTION_VALUES:
                continue
            if normalized:
                cleaned[key] = normalized
        if not any(cleaned.values()):
            if invalid_fields:
                return None, "Mô hình ảnh trả về thuộc tính không hợp lệ; vẫn dùng xử lý cục bộ.", "invalid_output"
            return None, "Mô hình ảnh chưa trả về đặc điểm có thể dùng; vẫn dùng xử lý cục bộ.", "ambiguous"
        if invalid_fields:
            return cleaned, "Một số thuộc tính ảnh không hợp lệ đã được bỏ qua.", "partial"
        return cleaned, None, "used"
    except ai_client.AIProviderError:
        return None, "Không kết nối được mô hình ảnh; vẫn dùng xử lý cục bộ.", "unavailable"


def _metadata_score(pet: dict, analysis: dict | None, dominant_colors: tuple[str, ...]) -> float:
    pet_values = {
        "species": pet.get("species", ""),
        "coat_color": pet.get("coat_color", ""),
        "eye_color": pet.get("eye_color", ""),
    }
    weights = {
        "species": 0.28,
        "breed": 0.20,
        "coat_color": 0.24,
        "eye_color": 0.12,
    }
    score, total_weight = 0.0, 0.0
    if analysis:
        for key, weight in weights.items():
            if key == "breed":
                query_tokens = _tokens(analysis.get(key, ""))
                pet_tokens = _tokens(pet.get("breed", ""))
            elif key == "species":
                query_tokens = _species_tokens(analysis.get(key, ""))
                pet_tokens = _species_tokens(pet_values[key])
            else:
                query_tokens = _tokens(analysis.get(key, ""))
                pet_tokens = _tokens(pet_values[key])
            if query_tokens:
                field_match = len(query_tokens & pet_tokens) / len(query_tokens)
                score += weight * field_match
                total_weight += weight
        # Pattern and shape are stored together in appearance_tags. Compare
        # their combined query tokens once so the same pet field is not counted
        # twice when the model describes both.
        appearance_tokens = set().union(*(
            token_fn(analysis.get(key, ""))
            for key, token_fn in (
                ("coat_pattern", _tokens),
                ("coat_length", _coat_length_tokens),
                ("size", _tokens),
                ("shape", _tokens),
            )
        ))
        pet_appearance_tokens = _tokens(pet.get("appearance_tags", ""))
        if appearance_tokens:
            appearance_match = len(appearance_tokens & pet_appearance_tokens) / len(appearance_tokens)
            score += 0.34 * appearance_match
            total_weight += 0.34
    color_tokens = set().union(*(_tokens(color) for color in dominant_colors)) if dominant_colors else set()
    pet_color_tokens = _tokens(pet.get("coat_color", ""))
    if color_tokens and pet_color_tokens:
        color_match = 1.0 if color_tokens & pet_color_tokens else 0.0
        score += 0.26 * color_match
        total_weight += 0.26
    return score / total_weight if total_weight else 0.0


def _is_exact_descriptor_match(query: ImageDescriptor, saved: ImageDescriptor | None, visual_score: float | None) -> bool:
    if saved is None:
        return False
    q_hashes = {h for h in (query.raw_sha256, query.normalized_sha256) if len(h) == 64}
    s_hashes = {h for h in (saved.raw_sha256, saved.normalized_sha256) if len(h) == 64}
    if q_hashes and s_hashes:
        return bool(q_hashes & s_hashes)
    # Backward compatibility for pre-AI-4.0a rows stored without SHA-256 digests
    if not s_hashes and visual_score is not None and visual_score >= 0.999999:
        if not saved.visual_hash or saved.visual_hash == query.visual_hash:
            return True
    return False


def _is_near_duplicate_match(
    query: ImageDescriptor,
    saved: ImageDescriptor | None,
    visual_score: float | None,
) -> bool:
    if saved is None or visual_score is None or visual_score < NEAR_DUP_MIN_VISUAL_SCORE:
        return False
    d_dist = hamming_hex64(query.dhash64, saved.dhash64)
    p_dist = hamming_hex64(query.phash64, saved.phash64)
    if d_dist is None or p_dist is None:
        return False
    if not (
        d_dist <= NEAR_DUP_MAX_DHASH
        and p_dist <= NEAR_DUP_MAX_PHASH
        and (d_dist + p_dist) <= NEAR_DUP_MAX_COMBINED_HASH
    ):
        return False
    parts = similarity_components(query, saved)
    return bool(parts and parts["structure"] >= NEAR_DUP_MIN_STRUCTURE_SCORE)


def rank_pet_candidates_ai4a(
    query: ImageDescriptor,
    candidates,
    *,
    explicit_species: str | None = None,
    analysis: dict | None = None,
    include_similar: bool = True,
    species_gate: SpeciesGateDecision | None = None,
    use_foreground_embeddings: bool = True,
    ranking_mode: str = "ai4_0c_combined",
) -> dict:
    """Precision-first AI-4.0c/b/a pet photo matcher with exact priority, species gate, 1280-D embeddings, and CIE-Lab reranking."""
    has_reference_photos = False
    materialized: list[tuple[dict, ImageDescriptor | None, float | None]] = []

    for pet in candidates:
        if pet.get("photo_filename"):
            has_reference_photos = True
        raw_desc = pet.get("photo_descriptor")
        saved = descriptor_from_json(raw_desc) if raw_desc else None
        visual_score = compare_images(query, saved) if saved is not None else compare_images_from_json(query, raw_desc)
        materialized.append((pet, saved, visual_score))

    subject_status = species_gate.subject_status if species_gate is not None else None

    # Guardrail (Phase 6): A manual species filter must NEVER override a verified species contradiction
    if (
        species_gate is not None
        and explicit_species is not None
        and species_gate.verified_species is not None
        and explicit_species != species_gate.verified_species
    ):
        return {
            "results": [],
            "has_reference_photos": has_reference_photos,
            "match_outcome": MATCH_OUTCOME_NONE,
            "abstention_reason": "species_contradiction",
            "verified_species": species_gate.verified_species,
            "verified_species_source": "local_detector",
            "subject_status": subject_status,
        }

    # Pass 1: Tier 0 (Exact SHA-256) and Tier 1 (Calibrated near-duplicate)
    exact_hits: list[dict] = []
    near_dup_hits: list[dict] = []

    for pet, saved, visual_score in materialized:
        pet_species = canonicalize_species(pet.get("species"))
        if _is_exact_descriptor_match(query, saved, visual_score):
            if explicit_species is not None and pet_species != explicit_species:
                return {
                    "results": [],
                    "has_reference_photos": has_reference_photos,
                    "match_outcome": MATCH_OUTCOME_NONE,
                    "abstention_reason": "species_contradiction",
                    "verified_species": pet_species,
                    "verified_species_source": "matched_store_photo",
                    "subject_status": subject_status,
                }
            metadata_score = _metadata_score(pet, analysis, query.dominant_colors)
            exact_hits.append({
                "pet": pet,
                "saved": saved,
                "score": 100,
                "sort_score": 1.0,
                "visual_score": 100,
                "attribute_score": round(metadata_score * 100),
                "match_tier": MATCH_TIER_EXACT,
            })
        elif _is_near_duplicate_match(query, saved, visual_score) and visual_score is not None:
            if explicit_species is not None and pet_species != explicit_species:
                continue
            metadata_score = _metadata_score(pet, analysis, query.dominant_colors)
            bounded = max(0.90, min(0.99, visual_score))
            near_dup_hits.append({
                "pet": pet,
                "saved": saved,
                "score": max(90, min(99, round(bounded * 100))),
                "sort_score": bounded,
                "visual_score": round(visual_score * 100),
                "attribute_score": round(metadata_score * 100),
                "match_tier": MATCH_TIER_NEAR_DUP,
            })

    exact_hits.sort(key=lambda r: (r["sort_score"], str(r["pet"].get("name", "")), -int(r["pet"]["id"])), reverse=True)
    near_dup_hits.sort(key=lambda r: (r["sort_score"], str(r["pet"].get("name", "")), -int(r["pet"]["id"])), reverse=True)

    # Resolve verified query species using exact/near-dup store match, local species gate, or safe manual fallback
    verified_species: str | None = None
    verified_species_source: str | None = None

    if exact_hits:
        verified_species = canonicalize_species(exact_hits[0]["pet"].get("species"))
        verified_species_source = "matched_store_photo"
    elif near_dup_hits:
        verified_species = canonicalize_species(near_dup_hits[0]["pet"].get("species"))
        verified_species_source = "matched_store_photo"
    elif species_gate is not None:
        if species_gate.subject_status in (SUBJECT_ONE_CAT, SUBJECT_ONE_DOG):
            verified_species = species_gate.verified_species
            verified_species_source = "local_detector"
        elif species_gate.subject_status == SUBJECT_MULTIPLE_ANIMALS:
            return {
                "results": [],
                "has_reference_photos": has_reference_photos,
                "match_outcome": MATCH_OUTCOME_NONE,
                "abstention_reason": "multiple_animals_detected",
                "verified_species": None,
                "verified_species_source": None,
                "subject_status": subject_status,
            }
        elif species_gate.subject_status == SUBJECT_NO_RELIABLE_ANIMAL:
            return {
                "results": [],
                "has_reference_photos": has_reference_photos,
                "match_outcome": MATCH_OUTCOME_NONE,
                "abstention_reason": species_gate.detail_reason,
                "verified_species": None,
                "verified_species_source": None,
                "subject_status": subject_status,
            }
        elif species_gate.subject_status == SUBJECT_OTHER_ANIMAL:
            if explicit_species in (None, "cat", "dog"):
                return {
                    "results": [],
                    "has_reference_photos": has_reference_photos,
                    "match_outcome": MATCH_OUTCOME_NONE,
                    "abstention_reason": "unsupported_other_animal",
                    "verified_species": None,
                    "verified_species_source": None,
                    "subject_status": subject_status,
                }
            verified_species = explicit_species
            verified_species_source = "user_filter"
        elif species_gate.subject_status == SUBJECT_AMBIGUOUS:
            if explicit_species is None:
                return {
                    "results": [],
                    "has_reference_photos": has_reference_photos,
                    "match_outcome": MATCH_OUTCOME_NONE,
                    "abstention_reason": "ambiguous_subject",
                    "verified_species": None,
                    "verified_species_source": None,
                    "subject_status": subject_status,
                }
            if (
                explicit_species in ("cat", "dog")
                and species_gate.candidate_species_support
                and explicit_species not in species_gate.candidate_species_support
            ):
                return {
                    "results": [],
                    "has_reference_photos": has_reference_photos,
                    "match_outcome": MATCH_OUTCOME_NONE,
                    "abstention_reason": "species_contradiction",
                    "verified_species": None,
                    "verified_species_source": None,
                    "subject_status": subject_status,
                }
            verified_species = explicit_species
            verified_species_source = "user_filter"
        elif explicit_species is not None:
            verified_species = explicit_species
            verified_species_source = "user_filter"
    elif explicit_species is not None:
        verified_species = explicit_species
        verified_species_source = "user_filter"

    if verified_species is not None:
        near_dup_hits = [
            r for r in near_dup_hits
            if canonicalize_species(r["pet"].get("species")) == verified_species
        ]

    if verified_species is None:
        abstention_reason = (
            "non_photographic_or_low_texture"
            if query.flat_pixel_ratio > SIMILAR_MAX_FLAT_PIXEL_RATIO
            else "species_unverified"
        )
        return {
            "results": [],
            "has_reference_photos": has_reference_photos,
            "match_outcome": MATCH_OUTCOME_NONE,
            "abstention_reason": abstention_reason,
            "verified_species": None,
            "verified_species_source": None,
            "subject_status": subject_status,
        }

    direct_ids = {int(r["pet"]["id"]) for r in (*exact_hits, *near_dup_hits)}
    similar_hits: list[dict] = []
    non_photo_rejected = query.flat_pixel_ratio > SIMILAR_MAX_FLAT_PIXEL_RATIO

    use_fg_bbox = bool(
        species_gate is not None
        and species_gate.foreground_coat_profile
        and species_gate.foreground_descriptor is not None
    )
    active_coat_profile = (
        species_gate.foreground_coat_profile
        if use_fg_bbox and species_gate is not None
        else query.subject_coat_profile
    )
    min_sim_threshold = (
        SIMILAR_MIN_DETECTOR_BBOX_SCORE if use_fg_bbox else SIMILAR_MIN_COMBINED_SCORE
    )
    rcal = _get_retrieval_calibration()
    w_emb = float(rcal["embedding_weight"])
    w_lab = float(rcal["lab_coat_weight"])
    w_struct = float(rcal["structure_weight"])
    min_comb_4c = float(rcal["min_combined_similarity"])
    min_emb_cos = float(rcal["min_embedding_cosine"])
    min_lab_sim = float(rcal["min_lab_coat_similarity"])

    active_mode = ranking_mode if use_foreground_embeddings else "ai4_0b_baseline"
    q_emb_b64 = (
        species_gate.foreground_embedding_b64
        if species_gate is not None and species_gate.foreground_embedding_b64
        else query.embedding_b64
    )
    q_emb_vec = decode_embedding_f16_b64(q_emb_b64) if q_emb_b64 else None
    q_lab_hist = (
        species_gate.foreground_lab_histogram
        if species_gate is not None and species_gate.foreground_lab_histogram
        else query.fg_lab_histogram
    )
    q_lab_coat7 = (
        species_gate.foreground_lab_coat_profile
        if species_gate is not None and species_gate.foreground_lab_coat_profile
        else query.fg_coat_profile
    )

    if include_similar and not non_photo_rejected:
        for pet, saved, visual_score in materialized:
            pet_id = int(pet["id"])
            if pet_id in direct_ids:
                continue
            if canonicalize_species(pet.get("species")) != verified_species:
                continue
            if saved is None or visual_score is None:
                continue
            best_vis = visual_score
            if use_fg_bbox and species_gate is not None and species_gate.foreground_descriptor is not None:
                bbox_vis = compare_images(species_gate.foreground_descriptor, saved)
                best_vis = max(visual_score, bbox_vis)

            c_emb_vec = (
                decode_embedding_f16_b64(saved.embedding_b64, actual_version=saved.embedding_version)
                if saved.embedding_b64
                else None
            )
            c_lab_hist = saved.fg_lab_histogram
            has_4c_pair = bool(
                q_emb_vec is not None
                and c_emb_vec is not None
                and q_lab_hist
                and c_lab_hist
            )

            emb_sim: float | None = None
            lab_sim: float | None = None

            if active_mode == "embedding_only" and q_emb_vec is not None and c_emb_vec is not None:
                emb_sim = embedding_cosine_similarity(q_emb_vec, c_emb_vec)
                if emb_sim is None or emb_sim < min_comb_4c:
                    continue
                combined_sim = emb_sim
                effective_coat_sim = emb_sim
            elif active_mode == "coat_lab_only" and q_lab_hist and c_lab_hist:
                if not lab_coat_groups_compatible(
                    q_lab_coat7,
                    pet.get("coat_color"),
                    pet.get("appearance_tags"),
                    saved.fg_coat_profile,
                ):
                    continue
                lab_sim = compare_lab_histograms(q_lab_hist, c_lab_hist)
                if lab_sim is None or lab_sim < min_comb_4c:
                    continue
                combined_sim = lab_sim
                effective_coat_sim = lab_sim
            elif active_mode == "ai4_0c_combined" and has_4c_pair:
                if not lab_coat_groups_compatible(
                    q_lab_coat7,
                    pet.get("coat_color"),
                    pet.get("appearance_tags"),
                    saved.fg_coat_profile,
                ):
                    continue
                emb_sim = embedding_cosine_similarity(q_emb_vec, c_emb_vec)
                lab_sim = compare_lab_histograms(q_lab_hist, c_lab_hist)
                if (
                    emb_sim is None
                    or lab_sim is None
                    or emb_sim < min_emb_cos
                    or lab_sim < min_lab_sim
                ):
                    continue
                ref_fg = (
                    species_gate.foreground_descriptor
                    if species_gate is not None and species_gate.foreground_descriptor is not None
                    else query
                )
                fg_parts = similarity_components(ref_fg, saved)
                struct_sim = float(fg_parts["structure"]) if fg_parts else 0.5
                combined_sim = w_emb * emb_sim + w_lab * lab_sim + w_struct * struct_sim
                if combined_sim < min_comb_4c:
                    continue
                effective_coat_sim = lab_sim
            else:
                # Safe per-candidate fallback when AI-4.0c is disabled or candidate row awaits reindex
                coat_sim = compare_coat_profiles(active_coat_profile, saved.subject_coat_profile)
                effective_coat_sim = coat_sim if coat_sim is not None else best_vis
                if not coat_groups_compatible(
                    active_coat_profile,
                    pet.get("coat_color"),
                    pet.get("appearance_tags"),
                    saved.subject_coat_profile,
                ):
                    continue
                if use_fg_bbox:
                    combined_sim = 0.45 * best_vis + 0.55 * effective_coat_sim
                else:
                    combined_sim = 0.55 * best_vis + 0.45 * effective_coat_sim
                if combined_sim < min_sim_threshold:
                    continue

            metadata_score = _metadata_score(pet, analysis, query.dominant_colors)
            capped_score = min(89, max(1, round(combined_sim * 100)))
            similar_hits.append({
                "pet": pet,
                "saved": saved,
                "score": capped_score,
                "sort_score": combined_sim,
                "visual_score": round((emb_sim if emb_sim is not None else best_vis) * 100),
                "embedding_score": round(emb_sim * 100) if emb_sim is not None else None,
                "coat_score": round(effective_coat_sim * 100),
                "attribute_score": round(metadata_score * 100),
                "match_tier": MATCH_TIER_SIMILAR,
            })

    similar_hits.sort(
        key=lambda r: (r["sort_score"], str(r["pet"].get("name", "")), -int(r["pet"]["id"])),
        reverse=True,
    )
    combined_results = [*exact_hits, *near_dup_hits, *similar_hits[:MAX_SIMILAR_CANDIDATES]]

    for result in combined_results:
        saved = result.pop("saved", None)
        result.pop("sort_score", None)
        emb_pct = result.get("embedding_score")
        coat_pct = result.get("coat_score")
        parts = similarity_components(query, saved) if saved else None
        result["components"] = {
            key: round(value * 100) for key, value in (parts or {}).items()
        }
        if emb_pct is not None:
            result["components"]["morphology"] = emb_pct
        if coat_pct is not None and result["match_tier"] == MATCH_TIER_SIMILAR:
            result["components"]["color"] = coat_pct
        result["components"]["attributes"] = result["attribute_score"]
        result["reasons"] = []
        matched_colors = [
            color
            for color in query.dominant_colors
            if _tokens(color) & _tokens(result["pet"].get("coat_color", ""))
        ]
        if result["match_tier"] == MATCH_TIER_EXACT:
            result["reasons"].append({"kind": "exact_photo", "value": ""})
        elif result["match_tier"] == MATCH_TIER_NEAR_DUP:
            result["reasons"].append({"kind": "near_duplicate", "value": ""})
        else:
            if emb_pct is not None and emb_pct >= 70:
                result["reasons"].append({"kind": "appearance_embedding", "value": ""})
            if coat_pct is not None and coat_pct >= 74:
                result["reasons"].append({"kind": "lab_coat", "value": ""})
        if matched_colors:
            result["reasons"].append({"kind": "coat", "value": ", ".join(matched_colors)})
        if parts and parts["color"] >= 0.8 and not any(r["kind"] == "lab_coat" for r in result["reasons"]):
            result["reasons"].append({"kind": "color", "value": ""})
        if parts and parts["structure"] >= 0.8:
            result["reasons"].append({"kind": "structure", "value": ""})

    if exact_hits:
        outcome = MATCH_TIER_EXACT
        abstention = None
    elif near_dup_hits:
        outcome = MATCH_TIER_NEAR_DUP
        abstention = None
    elif combined_results:
        outcome = "visually_similar_only"
        abstention = None
    else:
        outcome = MATCH_OUTCOME_NONE
        if non_photo_rejected:
            abstention = "non_photographic_or_low_texture"
        else:
            abstention = "below_similarity_threshold"

    return {
        "results": combined_results,
        "has_reference_photos": has_reference_photos,
        "match_outcome": outcome,
        "abstention_reason": abstention,
        "verified_species": verified_species,
        "verified_species_source": verified_species_source,
        "subject_status": subject_status,
    }


rank_pet_candidates_ai4b = rank_pet_candidates_ai4a
rank_pet_candidates_ai4c = rank_pet_candidates_ai4a


def _legacy_stream_rank(query, candidates, analysis) -> list[dict]:
    """Compatibility heap path retained for synthetic unit-test stubs lacking ImageDescriptor."""
    top_results = []
    for pet in candidates:
        visual_score = compare_images_from_json(query, pet.get("photo_descriptor"))
        metadata_score = _metadata_score(pet, analysis, query.dominant_colors)
        if visual_score is None:
            score = (0.5 if analysis else 0.35) * metadata_score
        else:
            score = 0.82 * visual_score + 0.18 * metadata_score
        if score < _RESULT_MIN_SCORE:
            continue
        pet_id = int(pet["id"])
        result = {
            "pet": pet,
            "score": round(max(0.0, min(1.0, score)) * 100),
            "visual_score": round(visual_score * 100) if visual_score is not None else None,
            "attribute_score": round(metadata_score * 100),
            "match_tier": MATCH_TIER_SIMILAR,
        }
        rank = (score, str(pet["name"]), -pet_id)
        if len(top_results) < _RESULT_LIMIT:
            heapq.heappush(top_results, (rank, result))
        elif rank > top_results[0][0]:
            heapq.heapreplace(top_results, (rank, result))
    results = [item[1] for item in sorted(top_results, key=lambda item: item[0], reverse=True)]
    for result in results:
        saved = descriptor_from_json(result["pet"].get("photo_descriptor"))
        parts = similarity_components(query, saved) if saved else None
        result["components"] = {key: round(value * 100) for key, value in (parts or {}).items()}
        result["components"]["attributes"] = result["attribute_score"]
        result["reasons"] = []
    return results[:12]


def search_similar(
    actor_id: int,
    image_bytes: bytes,
    species="",
    status="available",
    tenant_id=None,
    *,
    include_similar: bool = True,
) -> dict:
    """Precision-first local pet photo matcher with SHA-256 exact priority and hard species filtering."""
    species = text_value(species, "Loài", 80, required=False)
    if status not in {"available", "sold", "inactive", ""}:
        raise ValidationError(
            ui_text(
                "Trạng thái tìm ảnh không hợp lệ.",
                "The image search status is invalid.",
            )
        )
    # Validate membership before spending model quota or sending the uploaded
    # image to an external vision endpoint.
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
    raw_sha = sha256_hex(image_bytes)
    normalized = normalize_image_bytes(image_bytes)
    norm_sha = sha256_hex(normalized)
    query = describe_image(normalized, raw_sha256=raw_sha, normalized_sha256=norm_sha)
    analysis, warning, _provider_status = _analysis_from_model(normalized)
    explicit_species = canonicalize_species(species)
    local_gate_enabled = bool(current_app.config.get("AI_LOCAL_SPECIES_GATE_ENABLED", True))
    fg_emb_enabled = bool(current_app.config.get("AI_FOREGROUND_EMBEDDING_ENABLED", True))
    species_gate = (
        analyze_pet_image(normalized, flat_pixel_ratio=query.flat_pixel_ratio)
        if isinstance(query, ImageDescriptor) and local_gate_enabled
        else None
    )
    search_scope = "full"

    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        # Note: When explicit species is provided, still scan available candidates if we need to detect
        # an exact stored photo contradiction when local_gate_enabled is False, otherwise iter_filtered_for_image_search.
        filtered = bool(species or status != "available")
        has_reference_photos = (
            False if filtered else pet_repo.has_available_reference_photos(connection)
        )
        if filtered:
            candidates = pet_repo.iter_filtered_for_image_search(
                connection, species, status
            )
        else:
            available_count = pet_repo.count_available_for_image_search(connection)
            if available_count <= pet_repo.MAX_IMAGE_SEARCH_CANDIDATES:
                candidates = pet_repo.iter_available_for_image_search(connection)
            else:
                indexed_candidates = pet_repo.find_available_image_search_candidates(
                    connection, query.visual_hash
                )
                if indexed_candidates is None:
                    candidates = pet_repo.iter_available_for_image_search(connection)
                else:
                    candidates = iter(indexed_candidates)
                    search_scope = "indexed"

        if isinstance(query, ImageDescriptor):
            outcome = rank_pet_candidates_ai4a(
                query,
                candidates,
                explicit_species=explicit_species,
                analysis=analysis,
                include_similar=include_similar,
                species_gate=species_gate,
                use_foreground_embeddings=fg_emb_enabled,
            )
            results = outcome["results"]
            has_reference_photos = has_reference_photos or outcome["has_reference_photos"]
            match_outcome = outcome["match_outcome"]
            abstention_reason = outcome["abstention_reason"]
            verified_species = outcome["verified_species"]
            verified_species_source = outcome["verified_species_source"]
            subject_status = outcome["subject_status"]
        else:
            results = _legacy_stream_rank(query, candidates, analysis)
            match_outcome = "visually_similar_only" if results else MATCH_OUTCOME_NONE
            abstention_reason = None if results else "below_similarity_threshold"
            verified_species = explicit_species
            verified_species_source = "user_filter" if explicit_species else None
            subject_status = None

    return {
        "filters": {"species": species, "status": status},
        "results": results,
        "dominant_colors": query.dominant_colors,
        "analysis": analysis,
        "vision_enabled": bool(
            current_app.config.get("AI_VISION_ENABLED") and ai_client.is_configured()
        ),
        "warning": warning,
        "has_reference_photos": has_reference_photos,
        "search_scope": search_scope,
        "match_outcome": match_outcome,
        "abstention_reason": abstention_reason,
        "verified_species": verified_species,
        "verified_species_source": verified_species_source,
        "subject_status": subject_status,
        "species_gate": (
            {
                "subject_status": species_gate.subject_status,
                "verified_species": species_gate.verified_species,
                "detail_reason": species_gate.detail_reason,
                "animal_count": species_gate.animal_count,
                "detector_label": species_gate.detector_label,
                "inference_ms": species_gate.inference_ms,
            }
            if species_gate is not None
            else None
        ),
        # The normalized query is rendered only in this authenticated response;
        # it is not persisted with pet records or sent to a remote provider.
        "query_preview": "data:image/jpeg;base64," + base64.b64encode(normalized).decode("ascii"),
    }


def suggest_attributes(actor_id, image_bytes, tenant_id=None):
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
    normalized = normalize_image_bytes(image_bytes)
    descriptor = describe_image(normalized)
    analysis, warning, provider_status = _analysis_from_model(normalized)
    suggestions = {}
    if analysis:
        for key, maximum in (
            ("species", 80), ("breed", 120), ("coat_color", 80), ("eye_color", 60)
        ):
            if analysis.get(key):
                suggestions[key] = analysis[key][:maximum]
        tags = ", ".join(
            analysis.get(key, "")
            for key in ("coat_pattern", "coat_length", "size", "shape")
            if analysis.get(key)
        )
        if tags:
            suggestions["appearance_tags"] = tags[:255]
    elif descriptor.dominant_colors:
        # A color estimate can include the background; the user reviews it.
        suggestions["coat_color"] = " / ".join(descriptor.dominant_colors)[:80]
    if analysis:
        result_status = "observations"
    elif suggestions:
        result_status = "uncertain"
    elif provider_status == "unavailable":
        result_status = "provider_unavailable"
    else:
        result_status = "unrecognized"
    return {
        "status": result_status,
        "suggestions": suggestions,
        "colors": descriptor.dominant_colors,
        "mode": "vision" if analysis else "local",
        "provider_status": provider_status,
        "warning": warning,
    }
