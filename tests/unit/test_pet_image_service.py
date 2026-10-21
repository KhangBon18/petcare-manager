import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from petcare.services import pet_image_service


class PetImageServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask("pet-image-service-tests")
        self.app.config.update(AI_VISION_ENABLED=True)

    def test_malformed_model_json_falls_back_with_warning(self):
        with self.app.app_context(), patch(
            "petcare.services.pet_image_service.ai_client.is_configured", return_value=True
        ), patch(
            "petcare.services.pet_image_service.ai_client.complete", return_value="{not json}"
        ):
            analysis, warning = pet_image_service._analysis_from_model(b"image")

        self.assertIsNone(analysis)
        self.assertIn("JSON không hợp lệ", warning)

    def test_empty_model_analysis_is_not_reported_as_success(self):
        with self.app.app_context(), patch(
            "petcare.services.pet_image_service.ai_client.is_configured", return_value=True
        ), patch(
            "petcare.services.pet_image_service.ai_client.complete", return_value='{"species":""}'
        ):
            analysis, warning = pet_image_service._analysis_from_model(b"image")

        self.assertIsNone(analysis)
        self.assertIn("chưa trả về đặc điểm", warning)

    def test_shape_and_pattern_share_one_appearance_field_weight(self):
        score = pet_image_service._metadata_score(
            {"appearance_tags": "lông ngắn"},
            {"coat_pattern": "lông ngắn", "shape": "dáng nhỏ"},
            (),
        )

        self.assertAlmostEqual(score, 0.5)

    def test_english_vision_attributes_match_vietnamese_pet_metadata(self):
        score = pet_image_service._metadata_score(
            {
                "species": "Mèo",
                "coat_color": "đen",
                "eye_color": "xanh dương",
                "appearance_tags": "lông ngắn, sọc",
            },
            {
                "species": "cat",
                "coat_color": "black",
                "eye_color": "blue",
                "coat_pattern": "striped",
                "shape": "short-haired",
            },
            ("đen",),
        )

        self.assertEqual(score, 1.0)

    def test_search_streams_candidates_and_keeps_the_best_twelve(self):
        pets = [
            {
                "id": index,
                "name": "Shared" if index in {19, 20, 21} else f"Pet {index:02d}",
                "photo_descriptor": {
                    "score": 0.95 if index in {19, 20, 21} else index / 30,
                },
            }
            for index in range(1, 31)
        ]

        @contextmanager
        def fake_connection():
            yield object()

        with self.app.app_context(), patch(
            "petcare.services.pet_image_service.normalize_image_bytes", return_value=b"normalized"
        ), patch(
            "petcare.services.pet_image_service.describe_image",
            return_value=SimpleNamespace(dominant_colors=(), visual_hash="0123456789abcdef"),
        ), patch(
            "petcare.services.pet_image_service._analysis_from_model", return_value=(None, None)
        ), patch(
            "petcare.services.pet_image_service.read_connection", fake_connection
        ), patch(
            "petcare.services.pet_image_service.require_actor"
        ), patch(
            "petcare.services.pet_image_service.pet_repo.has_available_reference_photos",
            return_value=True,
        ), patch(
            "petcare.services.pet_image_service.pet_repo.find_available_image_search_candidates",
            return_value=pets,
        ), patch(
            "petcare.services.pet_image_service.compare_images_from_json",
            side_effect=lambda _query, descriptor: descriptor["score"],
        ):
            result = pet_image_service.search_similar(1, b"input")

        self.assertTrue(result["has_reference_photos"])
        self.assertEqual(result["search_scope"], "indexed")
        self.assertEqual(len(result["results"]), 12)
        self.assertEqual(
            [item["pet"]["id"] for item in result["results"]],
            [30, 29, 19, 20, 21, 28, 27, 26, 25, 24, 23, 22],
        )

    def test_search_falls_back_to_full_scan_when_index_candidates_are_too_broad(self):
        pet = {"id": 1, "name": "Miu", "photo_descriptor": {"score": 0.95}}

        @contextmanager
        def fake_connection():
            yield object()

        with self.app.app_context(), patch(
            "petcare.services.pet_image_service.normalize_image_bytes", return_value=b"normalized"
        ), patch(
            "petcare.services.pet_image_service.describe_image",
            return_value=SimpleNamespace(dominant_colors=(), visual_hash="0123456789abcdef"),
        ), patch(
            "petcare.services.pet_image_service._analysis_from_model", return_value=(None, None)
        ), patch(
            "petcare.services.pet_image_service.read_connection", fake_connection
        ), patch(
            "petcare.services.pet_image_service.require_actor"
        ), patch(
            "petcare.services.pet_image_service.pet_repo.has_available_reference_photos",
            return_value=True,
        ), patch(
            "petcare.services.pet_image_service.pet_repo.find_available_image_search_candidates",
            return_value=None,
        ), patch(
            "petcare.services.pet_image_service.pet_repo.iter_available_for_image_search",
            return_value=iter([pet]),
        ), patch(
            "petcare.services.pet_image_service.compare_images_from_json",
            return_value=0.95,
        ):
            result = pet_image_service.search_similar(1, b"input")

        self.assertEqual(result["search_scope"], "full")
        self.assertEqual(result["results"][0]["pet"]["id"], 1)


if __name__ == "__main__":
    unittest.main()
