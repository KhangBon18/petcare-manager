"""Strict server-side JSON schemas and argument validators for PetCare AI tool calling (AI-2)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any

from petcare.ai.contracts import PreferenceSlots
from petcare.ai.recommender_pets import MAX_PET_RECOMMENDATIONS
from petcare.ai.recommender_products import MAX_COMPARISON_ITEMS, MAX_PRODUCT_RECOMMENDATIONS
from petcare.ai.tools import TOOL_REGISTRY, ActorContext, ToolNotAllowedError
from petcare.services.exceptions import ValidationError

_SKU_CODE_RE = re.compile(r"^[A-Z]{2,8}-\d{2,5}$", re.IGNORECASE)
_FORBIDDEN_ARG_KEYS = frozenset({
    "tenant_id",
    "actor_id",
    "user_id",
    "role",
    "scope",
    "sql",
    "raw_sql",
    "query_sql",
    "connection",
    "cursor",
    "python_code",
})
_SQL_FRAGMENT_RE = re.compile(
    r"\b(?:select\s+.+\s+from|drop\s+table|delete\s+from|update\s+\w+\s+set|insert\s+into|union\s+select)\b",
    re.IGNORECASE,
)

_ALLOWED_SPECIES = frozenset({"cat", "dog"})
_ALLOWED_LIVING_SPACES = frozenset({"apartment", "house"})
_ALLOWED_TEMPERAMENTS = frozenset({"calm", "active"})
_ALLOWED_SIZES = frozenset({"small", "medium", "large"})
_ALLOWED_LIFE_STAGES = frozenset({"junior", "adult", "senior"})
_ALLOWED_SEX = frozenset({"male", "female"})
_ALLOWED_CATEGORIES = frozenset({"food", "toy", "litter", "care", "accessory"})
_ALLOWED_ALLERGENS = frozenset({"chicken", "salmon", "beef", "grain", "soy"})
_ALLOWED_PERIODS = frozenset({"today", "7d", "30d", "week", "last_week", "month", "last_month"})
_MAX_BUDGET_VND = Decimal("500000000")


def _slot_properties_schema(*, include_product_fields: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        "species": {"type": "string", "enum": ["cat", "dog"]},
        "living_space": {"type": "string", "enum": ["apartment", "house"]},
        "temperament": {"type": "string", "enum": ["calm", "active"]},
        "size_preference": {"type": "string", "enum": ["small", "medium", "large"]},
        "life_stage": {"type": "string", "enum": ["junior", "adult", "senior"]},
        "pet_weight_kg": {"type": "number", "minimum": 0.2, "maximum": 90.0},
        "budget_min": {"type": "number", "minimum": 0, "maximum": 500000000},
        "budget_max": {"type": "number", "minimum": 1, "maximum": 500000000},
        "clear_budget": {"type": "boolean"},
        "sex": {"type": "string", "enum": ["male", "female"]},
    }
    if include_product_fields:
        props.update({
            "product_category": {
                "type": "string",
                "enum": ["food", "toy", "litter", "care", "accessory"],
            },
            "product_subtopic": {"type": "string", "maxLength": 48},
            "allergies": {
                "type": "array",
                "items": {"type": "string", "enum": ["chicken", "salmon", "beef", "grain", "soy"]},
                "maxItems": 5,
            },
            "remove_allergies": {
                "type": "array",
                "items": {"type": "string", "enum": ["chicken", "salmon", "beef", "grain", "soy"]},
                "maxItems": 5,
            },
            "clear_allergies": {"type": "boolean"},
        })
    return props


TOOL_JSON_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_products": {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "limit": {"type": "integer", "minimum": 1, "maximum": 12},
        },
    },
    "get_product_details": {
        "type": "object",
        "additionalProperties": False,
        "required": ["product_id"],
        "properties": {
            "product_id": {"type": "integer", "minimum": 1, "maximum": 2147483647},
        },
    },
    "compare_products": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "explicit_codes": {
                "type": "array",
                "items": {"type": "string", "pattern": "^[A-Za-z]{2,8}-\\d{2,5}$"},
                "maxItems": MAX_COMPARISON_ITEMS,
            },
            "use_session_products": {"type": "boolean"},
            "count_hint": {"type": "integer", "minimum": 2, "maximum": MAX_COMPARISON_ITEMS},
            **_slot_properties_schema(include_product_fields=True),
        },
    },
    "search_available_pets": {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "limit": {"type": "integer", "minimum": 1, "maximum": 12},
        },
    },
    "get_pet_public_details": {
        "type": "object",
        "additionalProperties": False,
        "required": ["pet_id"],
        "properties": {
            "pet_id": {"type": "integer", "minimum": 1, "maximum": 2147483647},
        },
    },
    "recommend_pets": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_PET_RECOMMENDATIONS},
            **_slot_properties_schema(include_product_fields=False),
        },
    },
    "recommend_products": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_PRODUCT_RECOMMENDATIONS},
            **_slot_properties_schema(include_product_fields=True),
        },
    },
    "search_pet_care_knowledge": {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 240},
            "species_hint": {"type": "string", "enum": ["cat", "dog"]},
        },
    },
    "get_restock_insights": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question": {"type": "string", "minLength": 2, "maxLength": 160},
        },
    },
    "get_purchase_status": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question": {"type": "string", "minLength": 2, "maxLength": 160},
        },
    },
    "get_sales_summary": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "period": {
                "type": "string",
                "enum": ["today", "7d", "30d", "week", "last_week", "month", "last_month"],
            },
        },
    },
    "get_inventory_forecast": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 8},
        },
    },
    "get_operations_overview": {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    },
}


def list_openai_tools_for_actor(actor: ActorContext) -> list[dict[str, Any]]:
    """Return OpenAI function-calling tool definitions permitted for `actor`."""
    definitions: list[dict[str, Any]] = []
    for name, spec in TOOL_REGISTRY.items():
        if actor.scope not in spec.allowed_scopes:
            continue
        if spec.required_role == "admin" and actor.role != "admin":
            continue
        schema = TOOL_JSON_SCHEMAS.get(name)
        if schema is None:
            continue
        definitions.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec.description,
                "parameters": schema,
            },
        })
    return definitions


def _coerce_strict_int(value: Any, field_name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"Parameter '{field_name}' must be an integer.")
    if value < minimum or value > maximum:
        raise ValidationError(f"Parameter '{field_name}' must be between {minimum} and {maximum}.")
    return value


def _coerce_strict_str(
    value: Any,
    field_name: str,
    *,
    min_len: int = 1,
    max_len: int = 240,
    allowed: frozenset[str] | None = None,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Parameter '{field_name}' must be a string.")
    cleaned = value.strip()
    if len(cleaned) < min_len or len(cleaned) > max_len:
        raise ValidationError(f"Parameter '{field_name}' length must be {min_len}..{max_len}.")
    if _SQL_FRAGMENT_RE.search(cleaned):
        raise ValidationError(f"Parameter '{field_name}' contains disallowed SQL syntax.")
    if allowed is not None and cleaned not in allowed:
        raise ValidationError(f"Parameter '{field_name}' must be one of {sorted(allowed)}.")
    return cleaned


def _coerce_decimal(
    value: Any,
    field_name: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValidationError(f"Parameter '{field_name}' must be numeric.")
    try:
        dec = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError(f"Parameter '{field_name}' is not a valid decimal.") from exc
    if not dec.is_finite() or dec < minimum or dec > maximum:
        raise ValidationError(f"Parameter '{field_name}' is outside allowed bounds [{minimum}, {maximum}].")
    return dec


def _merge_validated_slots(
    base_slots: PreferenceSlots,
    raw: dict[str, Any],
    *,
    target_domain: str,
    include_product_fields: bool,
) -> PreferenceSlots:
    merged = base_slots.clone()
    merged.active_domain = target_domain

    if "species" in raw and raw["species"] is not None:
        sp = _coerce_strict_str(raw["species"], "species", allowed=_ALLOWED_SPECIES)
        if sp != merged.species:
            merged.coat_colors = ()
            merged.eye_colors = ()
            merged.breed_terms = ()
        merged.species = sp

    if raw.get("clear_budget") is True:
        merged.budget_min = None
        merged.budget_max = None

    if "budget_min" in raw and raw["budget_min"] is not None:
        merged.budget_min = _coerce_decimal(raw["budget_min"], "budget_min", minimum=Decimal("0"), maximum=_MAX_BUDGET_VND)
    if "budget_max" in raw and raw["budget_max"] is not None:
        merged.budget_max = _coerce_decimal(raw["budget_max"], "budget_max", minimum=Decimal("1"), maximum=_MAX_BUDGET_VND)
        if merged.budget_min is not None and merged.budget_min > merged.budget_max:
            raise ValidationError("Parameter 'budget_min' cannot exceed 'budget_max'.")

    if "living_space" in raw and raw["living_space"] is not None:
        merged.living_space = _coerce_strict_str(raw["living_space"], "living_space", allowed=_ALLOWED_LIVING_SPACES)
    if "temperament" in raw and raw["temperament"] is not None:
        merged.temperament = _coerce_strict_str(raw["temperament"], "temperament", allowed=_ALLOWED_TEMPERAMENTS)
    if "size_preference" in raw and raw["size_preference"] is not None:
        merged.size_preference = _coerce_strict_str(raw["size_preference"], "size_preference", allowed=_ALLOWED_SIZES)
    if "life_stage" in raw and raw["life_stage"] is not None:
        merged.life_stage = _coerce_strict_str(raw["life_stage"], "life_stage", allowed=_ALLOWED_LIFE_STAGES)
    if "sex" in raw and raw["sex"] is not None:
        merged.sex = _coerce_strict_str(raw["sex"], "sex", allowed=_ALLOWED_SEX)
    if "pet_weight_kg" in raw and raw["pet_weight_kg"] is not None:
        merged.pet_weight_kg = _coerce_decimal(
            raw["pet_weight_kg"], "pet_weight_kg", minimum=Decimal("0.2"), maximum=Decimal("90")
        )

    if include_product_fields:
        if "product_category" in raw and raw["product_category"] is not None:
            merged.product_category = _coerce_strict_str(
                raw["product_category"], "product_category", allowed=_ALLOWED_CATEGORIES
            )
        if "product_subtopic" in raw and raw["product_subtopic"] is not None:
            sub = _coerce_strict_str(raw["product_subtopic"], "product_subtopic", min_len=1, max_len=48)
            merged.product_subtopic = re.sub(r"[^a-z0-9_]+", "_", sub.lower()).strip("_") or None

        if raw.get("clear_allergies") is True:
            merged.allergies = ()
        if "remove_allergies" in raw and raw["remove_allergies"] is not None:
            if not isinstance(raw["remove_allergies"], list) or len(raw["remove_allergies"]) > 5:
                raise ValidationError("Parameter 'remove_allergies' must be a list of at most 5 allergens.")
            to_remove = {
                _coerce_strict_str(item, "remove_allergies[]", allowed=_ALLOWED_ALLERGENS)
                for item in raw["remove_allergies"]
            }
            merged.allergies = tuple(a for a in merged.allergies if a not in to_remove)
        if "allergies" in raw and raw["allergies"] is not None:
            if not isinstance(raw["allergies"], list) or len(raw["allergies"]) > 5:
                raise ValidationError("Parameter 'allergies' must be a list of at most 5 allergens.")
            cleaned_allergies = [
                _coerce_strict_str(item, "allergies[]", allowed=_ALLOWED_ALLERGENS)
                for item in raw["allergies"]
            ]
            if raw.get("clear_allergies") is True:
                merged.allergies = tuple(dict.fromkeys(cleaned_allergies))
            else:
                merged.allergies = tuple(dict.fromkeys([*merged.allergies, *cleaned_allergies]))

    return merged


def parse_raw_tool_arguments(raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    """Decode JSON arguments from a model tool call and reject non-object payloads."""
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        parsed = raw_arguments
    elif isinstance(raw_arguments, str):
        if len(raw_arguments) > 4096:
            raise ValidationError("Tool argument JSON exceeds 4096-character safety limit.")
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ValidationError("Malformed JSON in model tool arguments.") from exc
    else:
        raise ValidationError("Model tool arguments must be a JSON object.")

    if not isinstance(parsed, dict):
        raise ValidationError("Model tool arguments root must be a JSON object.")
    return parsed


def validate_and_build_tool_kwargs(
    tool_name: str,
    raw_arguments: str | dict[str, Any] | None,
    *,
    session_slots: PreferenceSlots,
    session_product_ids: list[int] | None = None,
) -> tuple[dict[str, Any], PreferenceSlots | None]:
    """Validate `tool_name` and `raw_arguments` strictly against allowlisted server schemas.

    Returns `(kwargs_for_execute_tool, updated_slots_or_none)`.
    """
    if not isinstance(tool_name, str) or tool_name not in TOOL_REGISTRY or tool_name not in TOOL_JSON_SCHEMAS:
        raise ToolNotAllowedError(f"Tool '{tool_name}' is not in the allowlisted registry.")

    args = parse_raw_tool_arguments(raw_arguments)

    forbidden_used = sorted(set(args.keys()) & _FORBIDDEN_ARG_KEYS)
    if forbidden_used:
        raise ValidationError(
            f"Tool arguments cannot supply server-controlled or unsafe keys: {', '.join(forbidden_used)}."
        )

    schema = TOOL_JSON_SCHEMAS[tool_name]
    allowed_keys = set((schema.get("properties") or {}).keys())
    extra_keys = sorted(set(args.keys()) - allowed_keys)
    if extra_keys:
        raise ValidationError(f"Unexpected arguments for '{tool_name}': {', '.join(extra_keys)}.")

    for req_key in schema.get("required") or ():
        if req_key not in args or args[req_key] is None:
            raise ValidationError(f"Missing required argument '{req_key}' for '{tool_name}'.")

    if tool_name == "search_products":
        kwargs: dict[str, Any] = {
            "query": _coerce_strict_str(args["query"], "query", min_len=1, max_len=200),
        }
        if "limit" in args and args["limit"] is not None:
            kwargs["limit"] = _coerce_strict_int(args["limit"], "limit", minimum=1, maximum=12)
        return kwargs, None

    if tool_name == "get_product_details":
        return {
            "product_id": _coerce_strict_int(args["product_id"], "product_id", minimum=1, maximum=2_147_483_647),
        }, None

    if tool_name == "search_available_pets":
        kwargs = {
            "query": _coerce_strict_str(args["query"], "query", min_len=1, max_len=200),
        }
        if "limit" in args and args["limit"] is not None:
            kwargs["limit"] = _coerce_strict_int(args["limit"], "limit", minimum=1, maximum=12)
        return kwargs, None

    if tool_name == "get_pet_public_details":
        return {
            "pet_id": _coerce_strict_int(args["pet_id"], "pet_id", minimum=1, maximum=2_147_483_647),
        }, None

    if tool_name == "recommend_pets":
        updated_slots = _merge_validated_slots(
            session_slots, args, target_domain="pet", include_product_fields=False
        )
        kwargs = {"slots": updated_slots}
        if "top_k" in args and args["top_k"] is not None:
            kwargs["top_k"] = _coerce_strict_int(args["top_k"], "top_k", minimum=1, maximum=MAX_PET_RECOMMENDATIONS)
        return kwargs, updated_slots

    if tool_name == "recommend_products":
        updated_slots = _merge_validated_slots(
            session_slots, args, target_domain="product", include_product_fields=True
        )
        kwargs = {"slots": updated_slots}
        if "top_k" in args and args["top_k"] is not None:
            kwargs["top_k"] = _coerce_strict_int(
                args["top_k"], "top_k", minimum=1, maximum=MAX_PRODUCT_RECOMMENDATIONS
            )
        return kwargs, updated_slots

    if tool_name == "compare_products":
        updated_slots = _merge_validated_slots(
            session_slots, args, target_domain="product", include_product_fields=True
        )
        codes: list[str] = []
        if "explicit_codes" in args and args["explicit_codes"] is not None:
            if not isinstance(args["explicit_codes"], list) or len(args["explicit_codes"]) > MAX_COMPARISON_ITEMS:
                raise ValidationError(f"Parameter 'explicit_codes' must be a list of <= {MAX_COMPARISON_ITEMS} SKUs.")
            for raw_code in args["explicit_codes"]:
                code_str = _coerce_strict_str(raw_code, "explicit_codes[]", min_len=4, max_len=16).upper()
                if not _SKU_CODE_RE.fullmatch(code_str):
                    raise ValidationError(f"Invalid SKU code format: '{code_str}'.")
                if code_str not in codes:
                    codes.append(code_str)
        use_sess = args.get("use_session_products", len(codes) == 0)
        if not isinstance(use_sess, bool):
            raise ValidationError("Parameter 'use_session_products' must be a boolean.")
        count_hint = 3
        if "count_hint" in args and args["count_hint"] is not None:
            count_hint = _coerce_strict_int(args["count_hint"], "count_hint", minimum=2, maximum=MAX_COMPARISON_ITEMS)
        return {
            "explicit_codes": tuple(codes),
            "session_product_ids": list(session_product_ids or []) if use_sess else [],
            "slots": updated_slots,
            "count_hint": count_hint,
        }, updated_slots

    if tool_name == "search_pet_care_knowledge":
        kwargs = {
            "query": _coerce_strict_str(args["query"], "query", min_len=2, max_len=240),
        }
        if "species_hint" in args and args["species_hint"] is not None:
            kwargs["species_hint"] = _coerce_strict_str(
                args["species_hint"], "species_hint", allowed=_ALLOWED_SPECIES
            )
        elif session_slots.species in _ALLOWED_SPECIES:
            kwargs["species_hint"] = session_slots.species
        return kwargs, None

    if tool_name in {"get_restock_insights", "get_purchase_status"}:
        default_q = "restock" if tool_name == "get_restock_insights" else "purchase order status"
        q = default_q
        if "question" in args and args["question"] is not None:
            q = _coerce_strict_str(args["question"], "question", min_len=2, max_len=160)
        return {"question": q}, None

    if tool_name == "get_sales_summary":
        period = "7d"
        if "period" in args and args["period"] is not None:
            period = _coerce_strict_str(args["period"], "period", allowed=_ALLOWED_PERIODS)
        return {"period": period}, None

    if tool_name == "get_inventory_forecast":
        limit = 8
        if "limit" in args and args["limit"] is not None:
            limit = _coerce_strict_int(args["limit"], "limit", minimum=1, maximum=8)
        return {"limit": limit}, None

    if tool_name == "get_operations_overview":
        return {}, None

    raise ToolNotAllowedError(f"Tool '{tool_name}' is not supported.")
