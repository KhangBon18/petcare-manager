"""Metrics for explicitly labeled, deterministic image retrieval experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


class RetrievalEvaluationError(ValueError):
    """Raised when a retrieval ranking cannot be matched to its labels."""


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    queries: int
    precision_at_k: float
    recall_at_k: float
    mean_reciprocal_rank: float


def evaluate_rankings(
    rankings: Mapping[str, Sequence[str]],
    relevant: Mapping[str, Iterable[str]],
    *,
    k: int = 5,
) -> RetrievalMetrics:
    """Compute P@K, R@K, and MRR using caller-supplied relevance labels."""
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 100:
        raise RetrievalEvaluationError("k must be an integer from 1 to 100")
    if not rankings or set(rankings) != set(relevant):
        raise RetrievalEvaluationError("every ranking must have one relevance label")

    precisions: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    for query_id, ranking in rankings.items():
        if not isinstance(query_id, str) or not query_id:
            raise RetrievalEvaluationError("query IDs must be non-empty strings")
        if isinstance(ranking, (str, bytes)):
            raise RetrievalEvaluationError("a ranking must be a sequence of candidate IDs")
        ordered = tuple(ranking)
        if any(not isinstance(candidate, str) or not candidate for candidate in ordered):
            raise RetrievalEvaluationError("candidate IDs must be non-empty strings")
        if len(set(ordered)) != len(ordered):
            raise RetrievalEvaluationError("candidate IDs must be unique per ranking")
        labels = frozenset(relevant[query_id])
        if not labels or any(not isinstance(label, str) or not label for label in labels):
            raise RetrievalEvaluationError("each query must have at least one relevance label")
        top = ordered[:k]
        hits = len(labels.intersection(top))
        precisions.append(hits / k)
        recalls.append(hits / len(labels))
        reciprocal_ranks.append(
            next((1.0 / rank for rank, candidate in enumerate(ordered, start=1) if candidate in labels), 0.0)
        )

    count = len(rankings)
    return RetrievalMetrics(
        queries=count,
        precision_at_k=sum(precisions) / count,
        recall_at_k=sum(recalls) / count,
        mean_reciprocal_rank=sum(reciprocal_ranks) / count,
    )
