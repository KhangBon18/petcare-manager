"""Provider-neutral scoring for explicitly labeled Vision evaluations.

This module never loads or sends images. It scores prediction records supplied
by a separate, approved runner so local/mock and real-provider evidence remain
separate and auditable.
"""

from __future__ import annotations

import json
import math
import statistics
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
FORM_FIELDS = {"species", "breed", "coat_color", "eye_color", "appearance_tags"}
MODEL_FIELDS = {
    "species", "breed", "coat_color", "coat_pattern", "coat_length",
    "eye_color", "size", "shape",
}
KNOWN_FIELDS = FORM_FIELDS | MODEL_FIELDS
ALLOWED_USAGE = {"synthetic_test_only", "approved_human_labeled"}
ALLOWED_LABEL_SOURCES = {"verified_construction", "independent_human_annotation"}


class EvaluationInputError(ValueError):
    """Raised for malformed, unsafe, or mismatched evaluation inputs."""


def normalize_label(value: str | None) -> str | None:
    """Normalize whitespace/case only; do not apply model-driven synonyms."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise EvaluationInputError("Labels and predictions must be strings or null.")
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
    return normalized or None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationInputError(f"Cannot read JSON input: {path.name}") from exc


def load_dataset(path: str | Path) -> tuple[dict, list[dict]]:
    """Validate manifest metadata and return only scored samples.

    Image references are checked for safe, existing in-dataset files. Pending
    coverage slots are intentionally stored outside ``samples`` and are never
    treated as labeled observations.
    """
    manifest_path = Path(path).resolve()
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationInputError("Unsupported dataset manifest schema.")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"].strip():
        raise EvaluationInputError("dataset_id is required.")
    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        raise EvaluationInputError("dataset version is required.")
    if not isinstance(manifest.get("supported_attribute_fields"), list):
        raise EvaluationInputError("supported_attribute_fields must be a list.")
    if any(not isinstance(field, str) or field not in KNOWN_FIELDS for field in manifest["supported_attribute_fields"]):
        raise EvaluationInputError("Manifest contains an unsupported attribute field.")
    image_root_ref = manifest.get("image_root", ".")
    if not isinstance(image_root_ref, str):
        raise EvaluationInputError("image_root must be a relative path.")
    dataset_root = (manifest_path.parent / image_root_ref).resolve()
    if not manifest_path.parent.is_relative_to(dataset_root):
        raise EvaluationInputError("image_root must contain the manifest directory.")

    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise EvaluationInputError("samples must be a list.")
    seen: set[str] = set()
    scored: list[dict] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise EvaluationInputError("Each sample must be an object.")
        sample_id = sample.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip() or sample_id in seen:
            raise EvaluationInputError("Sample IDs must be non-empty and unique.")
        seen.add(sample_id)
        if sample.get("evaluation_eligible") is not True:
            continue
        if sample.get("approved_usage_status") not in ALLOWED_USAGE:
            raise EvaluationInputError(f"Sample {sample_id} is not approved for evaluation.")
        if sample.get("ground_truth_source") not in ALLOWED_LABEL_SOURCES:
            raise EvaluationInputError(f"Sample {sample_id} lacks an independent label source.")
        if not isinstance(sample.get("ground_truth_source_note"), str) or not sample["ground_truth_source_note"].strip():
            raise EvaluationInputError(f"Sample {sample_id} needs a documented ground-truth source.")
        if not isinstance(sample.get("split"), str) or not sample["split"].strip():
            raise EvaluationInputError(f"Sample {sample_id} needs a dataset split.")
        if not isinstance(sample.get("scenario"), str) or not sample["scenario"].strip():
            raise EvaluationInputError(f"Sample {sample_id} needs a scenario label.")
        image_ref = sample.get("image_reference")
        if not isinstance(image_ref, str) or not image_ref:
            raise EvaluationInputError(f"Sample {sample_id} needs an image reference.")
        image_path = (dataset_root / image_ref).resolve()
        if not image_path.is_relative_to(dataset_root) or not image_path.is_file():
            raise EvaluationInputError(f"Sample {sample_id} image reference is unsafe or missing.")
        fields = sample.get("supported_fields")
        labels = sample.get("ground_truth")
        if (
            not isinstance(fields, list) or not fields or any(not isinstance(field, str) for field in fields)
            or len(fields) != len(set(fields))
            or any(field not in KNOWN_FIELDS or field not in manifest["supported_attribute_fields"] for field in fields)
        ):
            raise EvaluationInputError(f"Sample {sample_id} has invalid supported_fields.")
        if not isinstance(labels, dict) or not set(labels).issubset(fields):
            raise EvaluationInputError(f"Sample {sample_id} has invalid ground_truth fields.")
        for value in labels.values():
            normalize_label(value)
        scored.append(sample)
    if not scored:
        raise EvaluationInputError("Dataset has no eligible labeled samples.")
    return manifest, scored


def load_predictions(path: str | Path, expected_ids: set[str]) -> list[dict]:
    payload = _read_json(Path(path))
    if not isinstance(payload, dict) or not isinstance(payload.get("predictions"), list):
        raise EvaluationInputError("Predictions file must contain a predictions list.")
    records = payload["predictions"]
    by_id: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise EvaluationInputError("Each prediction record must be an object.")
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or sample_id in by_id:
            raise EvaluationInputError("Prediction sample IDs must be unique strings.")
        if not isinstance(record.get("output_valid"), bool):
            raise EvaluationInputError(f"Prediction {sample_id} needs output_valid boolean.")
        values = record.get("values")
        if not isinstance(values, dict) or not set(values).issubset(KNOWN_FIELDS):
            raise EvaluationInputError(f"Prediction {sample_id} has invalid values.")
        for value in values.values():
            normalize_label(value)
        for key in ("latency_ms", "input_tokens", "output_tokens", "estimated_cost_usd", "attempt_count"):
            value = record.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise EvaluationInputError(f"Prediction {sample_id} has invalid {key}.")
            if key in {"input_tokens", "output_tokens", "attempt_count"} and not isinstance(value, int):
                raise EvaluationInputError(f"Prediction {sample_id} has invalid integer {key}.")
            if key == "attempt_count" and value < 1:
                raise EvaluationInputError(f"Prediction {sample_id} attempt_count must be positive.")
        for key in ("initial_error", "recovered"):
            if not isinstance(record.get(key), bool):
                raise EvaluationInputError(f"Prediction {sample_id} needs {key} boolean.")
        if record["recovered"] and not record["initial_error"]:
            raise EvaluationInputError(f"Prediction {sample_id} cannot recover without an initial error.")
        by_id[sample_id] = record
    if set(by_id) != expected_ids:
        raise EvaluationInputError("Prediction IDs must exactly match the eligible dataset samples.")
    return [by_id[sample_id] for sample_id in sorted(by_id)]


def _divide(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _score_field(samples: list[dict], predictions: dict[str, dict], field: str) -> dict:
    tp = fp = fn = exact = abstained = suggested = 0
    annotated = incorrect_suggestions = 0
    for sample in samples:
        labels = sample["ground_truth"]
        if field not in labels:
            continue
        annotated += 1
        expected = normalize_label(labels[field])
        actual = normalize_label(predictions[sample["sample_id"]]["values"].get(field))
        if actual == expected:
            exact += 1
        if actual is None:
            abstained += 1
        else:
            suggested += 1
        if expected is None:
            if actual is not None:
                fp += 1
                incorrect_suggestions += 1
        elif actual == expected:
            tp += 1
        elif actual is None:
            fn += 1
        else:
            fp += 1
            fn += 1
            incorrect_suggestions += 1
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else (0.0 if precision == 0 or recall == 0 else None)
    return {
        "annotated": annotated,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match_accuracy": _divide(exact, annotated),
        "abstention_rate": _divide(abstained, annotated),
        "field_coverage": _divide(suggested, annotated),
        "incorrect_suggestion_rate": _divide(incorrect_suggestions, suggested),
        "expected_unknown_false_suggestions": sum(
            1 for sample in samples
            if field in sample["ground_truth"]
            and normalize_label(sample["ground_truth"][field]) is None
            and normalize_label(predictions[sample["sample_id"]]["values"].get(field)) is not None
        ),
    }


def evaluate(manifest: dict, samples: list[dict], records: list[dict]) -> dict:
    """Score an exact prediction set and report only supplied telemetry."""
    predictions = {record["sample_id"]: record for record in records}
    fields = sorted({field for sample in samples for field in sample["ground_truth"]})
    valid_count = sum(record["output_valid"] for record in records)
    errors = [record for record in records if record["initial_error"]]
    attempts = [record.get("attempt_count") for record in records if record.get("attempt_count") is not None]
    latencies = [float(record["latency_ms"]) for record in records if record.get("latency_ms") is not None]
    input_tokens = [record["input_tokens"] for record in records if record.get("input_tokens") is not None]
    output_tokens = [record["output_tokens"] for record in records if record.get("output_tokens") is not None]
    costs = [float(record["estimated_cost_usd"]) for record in records if record.get("estimated_cost_usd") is not None]
    return {
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "version": manifest["version"],
            "evaluation_category": manifest.get("evaluation_category", "unspecified"),
            "eligible_samples": len(samples),
            "annotated_field_values": sum(len(sample["ground_truth"]) for sample in samples),
        },
        "real_model_accuracy": "NOT_MEASURED",
        "per_field": {field: _score_field(samples, predictions, field) for field in fields},
        "output_quality": {
            "records": len(records),
            "valid_structured_outputs": valid_count,
            "invalid_structured_output_rate": _divide(len(records) - valid_count, len(records)),
        },
        "recovery": {
            "initial_failures": len(errors),
            "recovered_failures": sum(record["recovered"] and record["output_valid"] for record in errors),
            "error_recovery_rate": _divide(
                sum(record["recovered"] and record["output_valid"] for record in errors), len(errors)
            ),
            "attempt_count_max": max(attempts) if attempts else None,
        },
        "latency_ms": {
            "sample_count": len(latencies),
            "p50_nearest_rank": _percentile(latencies, 0.50),
            "p95_nearest_rank": _percentile(latencies, 0.95),
            "median": statistics.median(latencies) if latencies else None,
        },
        "usage": {
            "input_tokens": sum(input_tokens) if input_tokens else None,
            "input_token_records": len(input_tokens),
            "output_tokens": sum(output_tokens) if output_tokens else None,
            "output_token_records": len(output_tokens),
            "estimated_cost_usd": round(sum(costs), 8) if costs else None,
            "cost_records": len(costs),
            "cost_complete": len(costs) == len(records),
        },
    }


def evaluate_files(manifest_path: str | Path, predictions_path: str | Path) -> dict:
    manifest, samples = load_dataset(manifest_path)
    records = load_predictions(predictions_path, {sample["sample_id"] for sample in samples})
    return evaluate(manifest, samples, records)


def render_markdown(report: dict) -> str:
    """Render a concise human-readable report from machine-readable results."""
    lines = [
        f"# Vision evaluation — {report['dataset']['dataset_id']} v{report['dataset']['version']}",
        "",
        f"Category: `{report['dataset']['evaluation_category']}`; real model accuracy: **{report['real_model_accuracy']}**.",
        f"Eligible samples: {report['dataset']['eligible_samples']}; annotated values: {report['dataset']['annotated_field_values']}.",
        "",
        "| Field | n | Precision | Recall | F1 | Exact match | Abstention | Coverage | Incorrect suggestion |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def fmt(value):
        return "—" if value is None else f"{value:.3f}"
    for field, metrics in report["per_field"].items():
        lines.append("| " + " | ".join([
            field, str(metrics["annotated"]), fmt(metrics["precision"]), fmt(metrics["recall"]),
            fmt(metrics["f1"]), fmt(metrics["exact_match_accuracy"]), fmt(metrics["abstention_rate"]),
            fmt(metrics["field_coverage"]), fmt(metrics["incorrect_suggestion_rate"]),
        ]) + " |")
    lines.extend([
        "",
        f"Invalid structured output rate: {fmt(report['output_quality']['invalid_structured_output_rate'])}.",
        f"Error recovery: {report['recovery']['recovered_failures']}/{report['recovery']['initial_failures']}.",
        f"Latency p50/p95: {fmt(report['latency_ms']['p50_nearest_rank'])}/{fmt(report['latency_ms']['p95_nearest_rank'])} ms.",
        f"Supplied token totals: input={report['usage']['input_tokens']}, output={report['usage']['output_tokens']}; "
        f"estimated cost={report['usage']['estimated_cost_usd']} USD (complete={report['usage']['cost_complete']}).",
        "",
        "Metrics cover only the records and annotations above. Synthetic/mock results do not establish real-provider recognition quality.",
        "",
    ])
    return "\n".join(lines)
