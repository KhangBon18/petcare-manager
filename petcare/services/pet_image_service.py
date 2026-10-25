"""Rank currently available pets against an uploaded reference image."""

from __future__ import annotations

import heapq
import json
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
from petcare.vision.image_features import (
    InvalidImage,
    descriptor_from_json,
    similarity_components,
    compare_images_from_json,
    describe_image,
    normalize_image_bytes,
)


_VISION_PROMPT = (
    "Quan sát ảnh và chỉ trả về một JSON hợp lệ bằng tiếng Việt với các khóa: "
    "species, coat_color, coat_pattern, eye_color, shape. Mỗi giá trị là mô tả ngắn; "
    "nếu không nhìn rõ hãy ghi chuỗi rỗng. Không đoán giống cụ thể khi không đủ căn cứ."
)
_VISION_PROMPT_EN = (
    "Inspect the animal's visible appearance and return only valid JSON in English "
    "with these keys: species, coat_color, coat_pattern, eye_color, shape. Keep each "
    "value brief; use an empty string when it is unclear. Do not guess a specific breed "
    "without enough visual evidence."
)
_RESULT_LIMIT = 12
_RESULT_MIN_SCORE = 0.12
_ATTRIBUTE_ALIASES = {
    "cat": "meo",
    "cats": "meo",
    "feline": "meo",
    "kitten": "meo",
    "kittens": "meo",
    "dog": "cho",
    "dogs": "cho",
    "canine": "cho",
    "puppy": "cho",
    "puppies": "cho",
    "rabbit": "tho",
    "bunny": "tho",
    "bird": "chim",
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
    "blue": "xanh",
    "green": "xanh",
    "tabby": "muop",
    "striped": "soc",
    "stripe": "soc",
    "spotted": "dom",
    "spotty": "dom",
    "small": "nho",
    "tiny": "nho",
    "large": "lon",
    "big": "lon",
}


def _normalize(text) -> str:
    value = unicodedata.normalize("NFD", str(text or "").casefold().replace("đ", "d"))
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def _tokens(text) -> set[str]:
    normalized = _normalize(text)
    normalized = re.sub(r"\bshort[\s-]+haired\b", "ngan", normalized)
    normalized = re.sub(r"\blong[\s-]+haired\b", "dai", normalized)
    return {
        _ATTRIBUTE_ALIASES.get(token, token)
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1
    }


def _analysis_from_model(image_bytes: bytes):
    if not current_app.config.get("AI_VISION_ENABLED") or not ai_client.is_configured():
        return None, None
    try:
        english = current_locale() == "en"
        response = ai_client.complete(
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
        start, end = response.find("{"), response.rfind("}")
        if start < 0 or end <= start:
            return None, "Mô hình ảnh chưa trả về mô tả có cấu trúc; vẫn dùng tìm kiếm cục bộ."
        try:
            analysis = json.loads(response[start : end + 1])
        except json.JSONDecodeError:
            return None, "Mô hình ảnh trả về JSON không hợp lệ; vẫn dùng tìm kiếm cục bộ."
        if not isinstance(analysis, dict):
            return None, "Mô hình ảnh chưa trả về mô tả có cấu trúc; vẫn dùng tìm kiếm cục bộ."
        allowed = ("species", "coat_color", "coat_pattern", "eye_color", "shape")
        cleaned = {
            key: str(analysis.get(key, "")).strip()[:100]
            for key in allowed
            if isinstance(analysis.get(key, ""), str)
        }
        if not any(cleaned.values()):
            return None, "Mô hình ảnh chưa trả về đặc điểm có thể dùng; vẫn dùng tìm kiếm cục bộ."
        return cleaned, None
    except ai_client.AIProviderError:
        return None, "Không kết nối được mô hình ảnh; vẫn dùng tìm kiếm cục bộ."


def _metadata_score(pet: dict, analysis: dict | None, dominant_colors: tuple[str, ...]) -> float:
    pet_values = {
        "species": pet.get("species", ""),
        "coat_color": pet.get("coat_color", ""),
        "eye_color": pet.get("eye_color", ""),
    }
    weights = {"species": 0.28, "coat_color": 0.26, "eye_color": 0.12}
    score, total_weight = 0.0, 0.0
    if analysis:
        for key, weight in weights.items():
            query_tokens = _tokens(analysis.get(key, ""))
            pet_tokens = _tokens(pet_values[key])
            if query_tokens:
                field_match = len(query_tokens & pet_tokens) / len(query_tokens)
                score += weight * field_match
                total_weight += weight
        # Pattern and shape are stored together in appearance_tags. Compare
        # their combined query tokens once so the same pet field is not counted
        # twice when the model describes both.
        appearance_tokens = _tokens(analysis.get("coat_pattern", "")) | _tokens(
            analysis.get("shape", "")
        )
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


def search_similar(
    actor_id: int, image_bytes: bytes, species="", status="available"
) -> dict:
    """Use a local visual descriptor, optionally refined by a configured vision model."""
    species = text_value(species, "Loài", 80, required=False)
    if status not in {"available", "sold", "inactive", ""}:
        raise ValidationError(
            ui_text(
                "Trạng thái tìm ảnh không hợp lệ.",
                "The image search status is invalid.",
            )
        )
    normalized = normalize_image_bytes(image_bytes)
    query = describe_image(normalized)
    analysis, warning = _analysis_from_model(normalized)
    top_results = []
    search_scope = "full"
    with read_connection() as connection:
        require_actor(connection, actor_id)
        filtered = bool(species or status != "available")
        has_reference_photos = (
            False if filtered else pet_repo.has_available_reference_photos(connection)
        )
        if filtered:
            candidates = pet_repo.iter_filtered_for_image_search(
                connection, species, status
            )
        else:
            indexed_candidates = pet_repo.find_available_image_search_candidates(
                connection, query.visual_hash
            )
            if indexed_candidates is None:
                candidates = pet_repo.iter_available_for_image_search(connection)
            else:
                candidates = iter(indexed_candidates)
                search_scope = "indexed"
        for pet in candidates:
            if pet.get("photo_filename"):
                has_reference_photos = True
            visual_score = compare_images_from_json(query, pet.get("photo_descriptor"))
            metadata_score = _metadata_score(pet, analysis, query.dominant_colors)
            if visual_score is None:
                # Metadata-only matches are intentionally conservative. Without a
                # saved reference photo the ranking is a hint, not visual matching.
                score = (0.5 if analysis else 0.35) * metadata_score
            else:
                score = 0.82 * visual_score + 0.18 * metadata_score
            if score < _RESULT_MIN_SCORE:
                continue

            pet_id = int(pet["id"])
            result = {
                "pet": pet,
                "score": round(max(0.0, min(1.0, score)) * 100),
                "visual_score": (
                    round(visual_score * 100) if visual_score is not None else None
                ),
                "attribute_score": round(metadata_score * 100),
            }
            # The old display order is descending score/name with ascending id
            # for ties. Keep that exact ordering while bounding memory at top-k.
            rank = (score, str(pet["name"]), -pet_id)
            if len(top_results) < _RESULT_LIMIT:
                heapq.heappush(top_results, (rank, result))
            elif rank > top_results[0][0]:
                heapq.heapreplace(top_results, (rank, result))
    results = [
        item[1] for item in sorted(top_results, key=lambda item: item[0], reverse=True)
    ]
    for result in results:
        saved = descriptor_from_json(result["pet"].get("photo_descriptor"))
        parts = similarity_components(query, saved) if saved else None
        result["components"] = {
            key: round(value * 100) for key, value in (parts or {}).items()
        }
        result["components"]["attributes"] = result["attribute_score"]
        result["reasons"] = []
        matched_colors = [
            color
            for color in query.dominant_colors
            if _tokens(color) & _tokens(result["pet"].get("coat_color", ""))
        ]
        if matched_colors:
            result["reasons"].append(
                {"kind": "coat", "value": ", ".join(matched_colors)}
            )
        if parts and parts["color"] >= 0.8:
            result["reasons"].append({"kind": "color", "value": ""})
        if parts and parts["structure"] >= 0.8:
            result["reasons"].append({"kind": "structure", "value": ""})
    return {
        "filters": {"species": species, "status": status},
        "results": results[:12],
        "dominant_colors": query.dominant_colors,
        "analysis": analysis,
        "vision_enabled": bool(
            current_app.config.get("AI_VISION_ENABLED") and ai_client.is_configured()
        ),
        "warning": warning,
        "has_reference_photos": has_reference_photos,
        "search_scope": search_scope,
    }


def suggest_attributes(actor_id, image_bytes):
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True)
    normalized = normalize_image_bytes(image_bytes)
    descriptor = describe_image(normalized)
    analysis, warning = _analysis_from_model(normalized)
    suggestions = {}
    if analysis:
        for key, maximum in (("species", 80), ("coat_color", 80), ("eye_color", 60)):
            if analysis.get(key):
                suggestions[key] = analysis[key][:maximum]
        tags = ", ".join(
            analysis.get(key, "")
            for key in ("coat_pattern", "shape")
            if analysis.get(key)
        )
        if tags:
            suggestions["appearance_tags"] = tags[:255]
    elif descriptor.dominant_colors:
        # A color estimate can include the background; the user reviews it.
        suggestions["coat_color"] = " / ".join(descriptor.dominant_colors)[:80]
    return {
        "suggestions": suggestions,
        "colors": descriptor.dominant_colors,
        "mode": "vision" if analysis else "local",
        "warning": warning,
    }
