"""Structured data contracts for PetCare AI conversations, recommendations, and citations."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any


class ResponseType(str, Enum):
    """Canonical response contract types returned by PetCare AI."""

    ANSWER = "answer"
    CLARIFICATION = "clarification"
    PET_RECOMMENDATIONS = "pet_recommendations"
    PRODUCT_RECOMMENDATIONS = "product_recommendations"
    PRODUCT_COMPARISON = "product_comparison"
    KNOWLEDGE_ANSWER = "knowledge_answer"
    OPERATIONAL_INSIGHT = "operational_insight"
    UNSUPPORTED_REQUEST = "unsupported_request"
    PERMISSION_DENIED = "permission_denied"
    SERVICE_ERROR = "service_error"


class AssistantScope(str, Enum):
    """Execution scope controlling which tools and records are accessible."""

    WORKSPACE = "workspace"
    SHOPPER_PREVIEW = "shopper_preview"


class EngineMode(str, Enum):
    """Runtime execution mode for the assistant engine."""

    OFFLINE = "offline"
    REAL_LLM = "real_llm"


@dataclass(slots=True)
class PreferenceSlots:
    """Explicit session-scoped preference slots for multi-turn guidance."""

    active_domain: str | None = None  # "pet" | "product" | None
    species: str | None = None  # "cat" | "dog" | None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    living_space: str | None = None  # "apartment" | "house" | None
    temperament: str | None = None  # "calm" | "active" | None
    size_preference: str | None = None  # "small" | "medium" | "large" | None
    life_stage: str | None = None  # "junior" | "adult" | "senior" | None
    pet_weight_kg: Decimal | None = None
    sex: str | None = None  # "male" | "female" | None
    coat_colors: tuple[tuple[str, ...], ...] = ()
    eye_colors: tuple[tuple[str, ...], ...] = ()
    breed_terms: tuple[str, ...] = ()
    product_category: str | None = None  # "food" | "toy" | "litter" | "care" | "accessory" | None
    product_subtopic: str | None = None
    allergies: tuple[str, ...] = ()
    awaiting_clarification_for: str | None = None  # "pet" | "product" | None

    def has_any_constraint(self) -> bool:
        return any((
            self.species,
            self.budget_min is not None,
            self.budget_max is not None,
            self.living_space,
            self.temperament,
            self.size_preference,
            self.life_stage,
            self.pet_weight_kg is not None,
            self.sex,
            self.coat_colors,
            self.eye_colors,
            self.breed_terms,
            self.product_category,
            self.product_subtopic,
            self.allergies,
        ))

    def clone(self) -> PreferenceSlots:
        return PreferenceSlots(
            active_domain=self.active_domain,
            species=self.species,
            budget_min=self.budget_min,
            budget_max=self.budget_max,
            living_space=self.living_space,
            temperament=self.temperament,
            size_preference=self.size_preference,
            life_stage=self.life_stage,
            pet_weight_kg=self.pet_weight_kg,
            sex=self.sex,
            coat_colors=tuple(self.coat_colors),
            eye_colors=tuple(self.eye_colors),
            breed_terms=tuple(self.breed_terms),
            product_category=self.product_category,
            product_subtopic=self.product_subtopic,
            allergies=tuple(self.allergies),
            awaiting_clarification_for=self.awaiting_clarification_for,
        )

    def to_public_dict(self, locale: str = "vi") -> dict[str, Any]:
        """Serialize active preference slots and localized summary chips for the UI."""
        chips: list[dict[str, str]] = []
        vi = locale != "en"
        if self.species:
            label = (
                ("Mèo" if self.species == "cat" else "Chó")
                if vi else ("Cat" if self.species == "cat" else "Dog")
            )
            chips.append({"slot": "species", "label": label})
        if self.living_space:
            space_map = {
                "apartment": ("Căn hộ", "Apartment"),
                "house": ("Nhà rộng / có sân", "House / yard"),
            }
            pair = space_map.get(self.living_space, (self.living_space, self.living_space))
            chips.append({"slot": "living_space", "label": pair[0] if vi else pair[1]})
        if self.temperament:
            temp_map = {
                "calm": ("Hiền / ít vận động", "Calm"),
                "active": ("Năng động", "Active"),
            }
            pair = temp_map.get(self.temperament, (self.temperament, self.temperament))
            chips.append({"slot": "temperament", "label": pair[0] if vi else pair[1]})
        if self.size_preference:
            size_map = {
                "small": ("Dáng nhỏ", "Small size"),
                "medium": ("Dáng vừa", "Medium size"),
                "large": ("Dáng lớn", "Large size"),
            }
            pair = size_map.get(self.size_preference, (self.size_preference, self.size_preference))
            chips.append({"slot": "size_preference", "label": pair[0] if vi else pair[1]})
        if self.life_stage:
            stage_map = {
                "junior": ("Thú non (<12 tháng)", "Junior (<12m)"),
                "adult": ("Trưởng thành", "Adult"),
                "senior": ("Lớn tuổi", "Senior"),
            }
            pair = stage_map.get(self.life_stage, (self.life_stage, self.life_stage))
            chips.append({"slot": "life_stage", "label": pair[0] if vi else pair[1]})
        if self.pet_weight_kg is not None:
            chips.append({
                "slot": "pet_weight_kg",
                "label": f"{self.pet_weight_kg.normalize()} kg",
            })
        if self.budget_min is not None or self.budget_max is not None:
            if self.budget_min is not None and self.budget_max is not None:
                budget_text = f"{int(self.budget_min):,}–{int(self.budget_max):,} VND"
            elif self.budget_max is not None:
                prefix = "≤ "
                budget_text = f"{prefix}{int(self.budget_max):,} VND"
            else:
                budget_text = f"≥ {int(self.budget_min):,} VND"
            if vi:
                budget_text = budget_text.replace(",", ".")
            chips.append({"slot": "budget", "label": budget_text})
        if self.product_category:
            cat_map = {
                "food": ("Thức ăn & dinh dưỡng", "Food & nutrition"),
                "toy": ("Đồ chơi", "Toys"),
                "litter": ("Cát vệ sinh", "Litter"),
                "care": ("Chăm sóc & vệ sinh", "Care & grooming"),
                "accessory": ("Phụ kiện", "Accessories"),
            }
            pair = cat_map.get(self.product_category, (self.product_category, self.product_category))
            chips.append({"slot": "product_category", "label": pair[0] if vi else pair[1]})
        if self.allergies:
            joined = ", ".join(self.allergies)
            chips.append({
                "slot": "allergies",
                "label": (f"Tránh: {joined}" if vi else f"Avoid: {joined}"),
            })
        return {
            "active_domain": self.active_domain,
            "species": self.species,
            "budget_min": str(self.budget_min) if self.budget_min is not None else None,
            "budget_max": str(self.budget_max) if self.budget_max is not None else None,
            "living_space": self.living_space,
            "temperament": self.temperament,
            "size_preference": self.size_preference,
            "life_stage": self.life_stage,
            "pet_weight_kg": str(self.pet_weight_kg) if self.pet_weight_kg is not None else None,
            "sex": self.sex,
            "product_category": self.product_category,
            "product_subtopic": self.product_subtopic,
            "allergies": list(self.allergies),
            "awaiting_clarification_for": self.awaiting_clarification_for,
            "chips": chips,
        }


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """Transparent scoring factor for explainable pet or product ranking."""

    criterion: str
    label: str
    points: int
    max_points: int
    status: str  # "matched" | "partial" | "unknown" | "neutral"
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "label": self.label,
            "points": self.points,
            "max_points": self.max_points,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(slots=True)
class RecommendationCard:
    """Grounded pet or product recommendation card backed by live MySQL records."""

    kind: str  # "pet" | "product"
    entity_id: int
    code: str
    name: str
    subtitle: str
    price: Decimal
    currency_code: str
    availability_status: str
    score: int
    max_score: int = 100
    stock_qty: int | None = None
    package_size_display: str | None = None
    unit_price_display: str | None = None
    score_breakdown: tuple[ScoreComponent, ...] = ()
    verified_attributes: dict[str, str] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    photo_filename: str | None = None
    is_alternative: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.entity_id,
            "code": self.code,
            "name": self.name,
            "subtitle": self.subtitle,
            "price": str(self.price),
            "currency_code": self.currency_code,
            "availability_status": self.availability_status,
            "stock_qty": self.stock_qty,
            "package_size_display": self.package_size_display,
            "unit_price_display": self.unit_price_display,
            "score": self.score,
            "max_score": self.max_score,
            "score_breakdown": [component.to_dict() for component in self.score_breakdown],
            "verified_attributes": dict(self.verified_attributes),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "photo_filename": self.photo_filename,
            "is_alternative": self.is_alternative,
        }


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One attribute row in a side-by-side product comparison table."""

    key: str
    label: str
    values: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "values": list(self.values),
        }


@dataclass(slots=True)
class ComparisonTable:
    """Structured side-by-side comparison matrix for 2–4 products."""

    items: list[dict[str, Any]]
    rows: tuple[ComparisonRow, ...]
    summary: str
    missing_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "rows": [row.to_dict() for row in self.rows],
            "summary": self.summary,
            "missing_notes": list(self.missing_notes),
        }


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    """Metadata and attribution for a reviewed pet-care knowledge document."""

    doc_id: str
    title: str
    source_name: str
    source_url: str
    updated_at: str
    topic: str
    language: str
    review_status: str
    version: str
    relevance_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "updated_at": self.updated_at,
            "topic": self.topic,
            "language": self.language,
            "review_status": self.review_status,
            "version": self.version,
            "relevance_score": round(self.relevance_score, 3),
        }


@dataclass(frozen=True, slots=True)
class SafetyNotice:
    """Explicit veterinary or operational safety boundary banner."""

    severity: str  # "emergency" | "medical_boundary" | "policy_boundary" | "disclaimer"
    title: str
    message: str
    escalation_steps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "escalation_steps": list(self.escalation_steps),
        }


@dataclass(frozen=True, slots=True)
class ToolExecutionTrace:
    """Audit trace for allowlisted read-only tool invocations."""

    tool_name: str
    status: str  # "ok" | "denied" | "empty" | "error"
    duration_ms: float
    result_count: int
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "result_count": self.result_count,
            "scope": self.scope,
        }


@dataclass(slots=True)
class AssistantTurnResponse:
    """Complete structured response returned by the PetCare AI orchestrator."""

    reply: str
    response_type: ResponseType
    mode: str = "local"  # Legacy compatibility ("local" | "ai")
    engine_mode: EngineMode = EngineMode.OFFLINE
    scope: AssistantScope = AssistantScope.WORKSPACE
    status: str | None = None
    conversation_id: str | None = None
    currency_code: str = "VND"
    reasoning_summary: str | None = None
    cards: list[RecommendationCard] = field(default_factory=list)
    comparison: ComparisonTable | None = None
    citations: list[KnowledgeCitation] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    safety_notice: SafetyNotice | None = None
    context_state: dict[str, Any] | None = None
    tool_trace: list[ToolExecutionTrace] = field(default_factory=list)
    catalog: dict[str, Any] | None = None
    insight: dict[str, Any] | None = None

    def to_api_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reply": self.reply,
            "mode": self.mode,
            "response_type": self.response_type.value,
            "engine_mode": self.engine_mode.value,
            "scope": self.scope.value,
            "currency_code": self.currency_code,
        }
        if self.status is not None:
            payload["status"] = self.status
        if self.conversation_id is not None:
            payload["conversation_id"] = self.conversation_id
        if self.reasoning_summary:
            payload["reasoning_summary"] = self.reasoning_summary
        if self.cards:
            payload["cards"] = [card.to_dict() for card in self.cards]
        if self.comparison is not None:
            payload["comparison"] = self.comparison.to_dict()
        if self.citations:
            payload["citations"] = [citation.to_dict() for citation in self.citations]
        if self.follow_up_questions:
            payload["follow_up_questions"] = list(self.follow_up_questions)
        if self.missing_data:
            payload["missing_data"] = list(self.missing_data)
        if self.safety_notice is not None:
            payload["safety_notice"] = self.safety_notice.to_dict()
        if self.context_state is not None:
            payload["context_state"] = self.context_state
        if self.tool_trace:
            payload["tool_trace"] = [trace.to_dict() for trace in self.tool_trace]
        if self.catalog is not None:
            payload["catalog"] = self.catalog
        if self.insight is not None:
            payload["insight"] = self.insight
        return payload
