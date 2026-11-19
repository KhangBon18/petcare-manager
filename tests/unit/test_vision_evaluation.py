"""Deterministic Vision scoring tests; no provider or image egress."""

from __future__ import annotations

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from petcare.vision.evaluation import (
    EvaluationInputError,
    evaluate,
    evaluate_files,
    load_dataset,
    load_predictions,
    normalize_label,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "vision" / "evaluation" / "manifest.json"
PREDICTIONS = ROOT / "fixtures" / "vision" / "evaluation" / "mock_predictions.json"


class VisionEvaluationTests(unittest.TestCase):
    def test_synthetic_mock_report_is_mechanics_only_and_reproducible(self):
        first = evaluate_files(MANIFEST, PREDICTIONS)
        second = evaluate_files(MANIFEST, PREDICTIONS)
        self.assertEqual(first, second)
        self.assertEqual(first["real_model_accuracy"], "NOT_MEASURED")
        self.assertEqual(first["dataset"]["evaluation_category"], "mock_integration_mechanics_only")
        self.assertEqual(first["dataset"]["eligible_samples"], 2)
        self.assertEqual(first["per_field"]["species"]["exact_match_accuracy"], 1.0)
        self.assertEqual(first["per_field"]["coat_color"]["precision"], 1.0)
        self.assertIsNone(first["usage"]["estimated_cost_usd"])
        self.assertIn("NOT_MEASURED", render_markdown(first))

    def test_metrics_count_wrong_values_as_false_positive_and_false_negative(self):
        samples = [
            {"sample_id": "a", "ground_truth": {"species": "cat"}},
            {"sample_id": "b", "ground_truth": {"species": "dog"}},
            {"sample_id": "c", "ground_truth": {"species": "dog"}},
            {"sample_id": "d", "ground_truth": {"species": None}},
        ]
        records = [
            {"sample_id": "a", "values": {"species": "cat"}, "output_valid": True, "initial_error": False, "recovered": False},
            {"sample_id": "b", "values": {"species": "cat"}, "output_valid": True, "initial_error": False, "recovered": False},
            {"sample_id": "c", "values": {"species": None}, "output_valid": True, "initial_error": False, "recovered": False},
            {"sample_id": "d", "values": {"species": "dog"}, "output_valid": True, "initial_error": False, "recovered": False},
        ]
        metrics = evaluate({"dataset_id": "unit", "version": "1", "evaluation_category": "unit"}, samples, records)["per_field"]["species"]
        self.assertEqual((metrics["tp"], metrics["fp"], metrics["fn"]), (1, 2, 2))
        self.assertEqual(metrics["precision"], 1 / 3)
        self.assertEqual(metrics["recall"], 1 / 3)
        self.assertEqual(metrics["f1"], 1 / 3)
        self.assertEqual(metrics["exact_match_accuracy"], 1 / 4)
        self.assertEqual(metrics["abstention_rate"], 1 / 4)
        self.assertEqual(metrics["field_coverage"], 3 / 4)
        self.assertEqual(metrics["incorrect_suggestion_rate"], 2 / 3)
        self.assertEqual(metrics["expected_unknown_false_suggestions"], 1)

    def test_null_ground_truth_rewards_abstention_and_omitted_field_is_excluded(self):
        samples = [
            {"sample_id": "a", "ground_truth": {"species": None}},
            {"sample_id": "b", "ground_truth": {}},
        ]
        records = [
            {"sample_id": "a", "values": {"species": None}, "output_valid": True, "initial_error": False, "recovered": False},
            {"sample_id": "b", "values": {}, "output_valid": True, "initial_error": False, "recovered": False},
        ]
        result = evaluate({"dataset_id": "unit", "version": "1"}, samples, records)
        self.assertEqual(result["per_field"]["species"]["annotated"], 1)
        self.assertEqual(result["per_field"]["species"]["exact_match_accuracy"], 1.0)

    def test_invalid_output_rate_and_recovery_are_explicit(self):
        samples = [{"sample_id": "a", "ground_truth": {"species": "cat"}}]
        records = [{
            "sample_id": "a", "values": {"species": "cat"}, "output_valid": False,
            "initial_error": True, "recovered": True, "attempt_count": 2,
            "latency_ms": 110, "input_tokens": 50, "output_tokens": 12,
            "estimated_cost_usd": 0.001,
        }]
        result = evaluate({"dataset_id": "unit", "version": "1"}, samples, records)
        self.assertEqual(result["output_quality"]["invalid_structured_output_rate"], 1.0)
        self.assertEqual(result["recovery"]["error_recovery_rate"], 0.0)
        self.assertEqual(result["latency_ms"]["p95_nearest_rank"], 110)
        self.assertEqual(result["usage"]["input_tokens"], 50)
        self.assertEqual(result["usage"]["estimated_cost_usd"], 0.001)

    def test_normalization_is_exact_without_synonym_mapping(self):
        self.assertEqual(normalize_label("  CAT\n"), "cat")
        self.assertNotEqual(normalize_label("kitty"), normalize_label("cat"))
        self.assertIsNone(normalize_label("   "))

    def test_dataset_contains_unscored_pending_scenarios(self):
        manifest, samples = load_dataset(MANIFEST)
        self.assertEqual(len(samples), 2)
        self.assertEqual(manifest["real_model_accuracy"], "NOT_MEASURED")
        scenarios = {item["scenario"] for item in manifest["coverage_requirements"]}
        self.assertTrue({
            "ambiguous_appearance", "poor_lighting", "occlusion", "multiple_animals",
            "non_pet_images", "missing_visual_evidence_expected_abstention", "conflicting_attributes",
        }.issubset(scenarios))

    def test_prediction_sample_ids_must_match_scored_set(self):
        with self.assertRaises(EvaluationInputError):
            load_predictions(PREDICTIONS, {"only-one-sample"})

    def test_dataset_rejects_image_references_outside_its_root(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["samples"][0]["image_reference"] = "../../../../etc/passwd"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(EvaluationInputError, "unsafe or missing"):
                load_dataset(path)

    def test_prediction_telemetry_requires_finite_integer_counts(self):
        payload = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
        payload["predictions"][0]["attempt_count"] = 1.5
        with TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(EvaluationInputError, "integer attempt_count"):
                load_predictions(path, {item["sample_id"] for item in payload["predictions"]})


if __name__ == "__main__":
    unittest.main()
