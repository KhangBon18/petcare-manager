"""Unit tests for AI-4.0d multi-photo pet galleries, species consistency, crop-robust matching, and rollback cleanup."""

from __future__ import annotations

from contextlib import contextmanager
import io
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.services import pet_image_service, pet_service
from petcare.services.exceptions import ValidationError
from petcare.vision.ai4_benchmark import make_near_duplicate_variant
from petcare.vision.coat_color_lab import EMBEDDING_VERSION, FG_LAB_VERSION
from petcare.vision.image_features import (
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import analyze_pet_image, enrich_descriptor_with_local_vision
from petcare.vision.reindex_pet_descriptors import reindex_pet_descriptors

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"


def _make_enriched_desc_json(raw_bytes: bytes) -> tuple[str, object]:
    norm = normalize_image_bytes(raw_bytes)
    base = describe_image(norm, raw_sha256=sha256_hex(raw_bytes), normalized_sha256=sha256_hex(norm))
    enr = enrich_descriptor_with_local_vision(norm, base)
    return descriptor_to_json(enr), enr


class AI4DGalleryAndCropMatchingUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat03_raw = (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes()
        cls.cat03_json, cls.cat03_desc = _make_enriched_desc_json(cls.cat03_raw)

        cls.cat10_raw = (DEMO_PETS_DIR / "demo-cat-10.png").read_bytes()
        cls.cat10_json, cls.cat10_desc = _make_enriched_desc_json(cls.cat10_raw)

        cls.cat16_raw = (DEMO_PETS_DIR / "demo-cat-16.png").read_bytes()
        cls.cat16_json, cls.cat16_desc = _make_enriched_desc_json(cls.cat16_raw)

        cls.dog01_raw = (DEMO_PETS_DIR / "demo-dog-01.png").read_bytes()
        cls.dog01_json, cls.dog01_desc = _make_enriched_desc_json(cls.dog01_raw)

        cls.real_orange_cat_raw = (REAL_PACK_DIR / "real-cat-orange-cal-01.jpg").read_bytes()
        cls.real_orange_cat_json, cls.real_orange_cat_desc = _make_enriched_desc_json(cls.real_orange_cat_raw)

    def _make_app(self, image_dir: Path):
        return create_app({
            "TESTING": True,
            "SECRET_KEY": secrets.token_urlsafe(32),
            "PET_IMAGE_DIR": str(image_dir),
            "AI_VISION_ENABLED": False,
            "AI_PROVIDER_APPROVED": False,
        })

    def test_five_photo_pet_returns_single_unique_card_and_secondary_exact_photo_ranks_first(self):
        # Pet #101 has 1 primary photo + 4 secondary reference photos (= 5 total)
        sec3_raw = (DEMO_PETS_DIR / "demo-cat-25.png").read_bytes()
        sec3_json, _ = _make_enriched_desc_json(sec3_raw)

        cat_with_5_photos = {
            "id": 101,
            "code": "PET-135",
            "name": "Gừng",
            "species": "Mèo",
            "breed": "British Shorthair",
            "coat_color": "cam vằn",
            "eye_color": "vàng đồng",
            "appearance_tags": "mèo mướp cam",
            "sale_price": 3500000,
            "sale_status": "available",
            "photo_filename": "t1-primary.jpg",
            "photo_descriptor": self.cat03_json,
            "reference_photos": [
                {"id": 11, "photo_filename": "t1-sec2.jpg", "photo_descriptor": self.cat10_json, "image_role": "front_view"},
                {"id": 12, "photo_filename": "t1-sec3.jpg", "photo_descriptor": sec3_json, "image_role": "side_view"},
                {"id": 13, "photo_filename": "t1-sec4.jpg", "photo_descriptor": self.cat03_json, "image_role": "coat_detail"},
                {"id": 14, "photo_filename": "t1-sec5.jpg", "photo_descriptor": self.cat10_json, "image_role": "lighting_variant"},
            ],
        }
        other_cat = {
            "id": 102,
            "code": "PET-142",
            "name": "Mật",
            "species": "Mèo",
            "breed": "Scottish Fold",
            "coat_color": "vàng kem",
            "eye_color": "vàng đồng",
            "appearance_tags": "tai cụp lông cam kem",
            "sale_price": 3800000,
            "sale_status": "available",
            "photo_filename": "t1-other.jpg",
            "photo_descriptor": self.cat10_json,
            "reference_photos": [],
        }

        # 1. Exact secondary photo (#3) query
        norm_q = normalize_image_bytes(sec3_raw)
        q_desc = describe_image(norm_q, raw_sha256=sha256_hex(sec3_raw), normalized_sha256=sha256_hex(norm_q))
        gate = analyze_pet_image(norm_q, flat_pixel_ratio=q_desc.flat_pixel_ratio)

        out_hybrid = pet_image_service.rank_pet_candidates_ai4a(
            q_desc,
            [other_cat, cat_with_5_photos],
            species_gate=gate,
            gallery_mode="calibrated_gallery_hybrid",
        )
        self.assertEqual(out_hybrid["results"][0]["pet"]["code"], "PET-135")
        self.assertEqual(out_hybrid["results"][0]["match_tier"], "exact_image_match")
        self.assertEqual(out_hybrid["results"][0]["score"], 100)
        self.assertEqual(out_hybrid["results"][0]["matched_photo_index"], 3)
        self.assertEqual(out_hybrid["results"][0]["matched_photo_filename"], "t1-sec3.jpg")
        self.assertEqual(out_hybrid["results"][0]["gallery_photo_count"], 5)

        # Must NEVER emit duplicate cards for PET-135 despite 5 stored photos!
        returned_ids = [r["pet"]["id"] for r in out_hybrid["results"]]
        self.assertEqual(len(returned_ids), len(set(returned_ids)))

        # In primary_only baseline mode, secondary photo #3 is NOT matched as exact_image_match
        out_primary_only = pet_image_service.rank_pet_candidates_ai4a(
            q_desc,
            [other_cat, cat_with_5_photos],
            species_gate=gate,
            gallery_mode="primary_only",
        )
        self.assertNotEqual(out_primary_only["match_outcome"], "exact_image_match")

        # 2. New real orange cat query against 5-photo pet: still appears at most once and never claims identity
        norm_real = normalize_image_bytes(self.real_orange_cat_raw)
        q_real = describe_image(
            norm_real,
            raw_sha256=sha256_hex(self.real_orange_cat_raw),
            normalized_sha256=sha256_hex(norm_real),
        )
        gate_real = analyze_pet_image(norm_real, flat_pixel_ratio=q_real.flat_pixel_ratio)
        for mode in ("primary_only", "max_photo", "mean_gallery", "calibrated_gallery_hybrid"):
            res = pet_image_service.rank_pet_candidates_ai4a(
                q_real,
                [cat_with_5_photos, other_cat],
                species_gate=gate_real,
                gallery_mode=mode,
            )
            ids = [r["pet"]["id"] for r in res["results"]]
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate pet IDs in mode={mode}")
            for item in res["results"]:
                self.assertEqual(item["match_tier"], "visually_similar_candidate")
                self.assertLessEqual(item["score"], 89)

    def test_five_black_cat_photos_do_not_inflate_score_above_no_match_threshold_for_orange_cat(self):
        # Anti-gallery-size-bias invariant: 5 black cat photos must still return 0 results for an orange cat query!
        black_cat_5photos = {
            "id": 201,
            "code": "PET-148",
            "name": "Mực",
            "species": "Mèo",
            "breed": "Bombay",
            "coat_color": "đen tuyền",
            "eye_color": "vàng đồng",
            "appearance_tags": "lông đen bóng",
            "sale_price": 3000000,
            "sale_status": "available",
            "photo_filename": "t1-b1.jpg",
            "photo_descriptor": self.cat16_json,
            "reference_photos": [
                {"id": 20 + i, "photo_filename": f"t1-b{i}.jpg", "photo_descriptor": self.cat16_json, "image_role": "additional"}
                for i in range(2, 6)
            ],
        }
        norm_real = normalize_image_bytes(self.real_orange_cat_raw)
        q_real = describe_image(
            norm_real,
            raw_sha256=sha256_hex(self.real_orange_cat_raw),
            normalized_sha256=sha256_hex(norm_real),
        )
        gate_real = analyze_pet_image(norm_real, flat_pixel_ratio=q_real.flat_pixel_ratio)
        out = pet_image_service.rank_pet_candidates_ai4a(
            q_real,
            [black_cat_5photos],
            species_gate=gate_real,
            gallery_mode="calibrated_gallery_hybrid",
        )
        self.assertEqual(out["results"], [])
        self.assertEqual(out["match_outcome"], "no_confident_match")

    def test_crop_robust_near_duplicate_vs_potential_same_pet_verification_flag(self):
        pet_cat03 = {
            "id": 301,
            "code": "PET-135",
            "name": "Gừng",
            "species": "Mèo",
            "breed": "British Shorthair",
            "coat_color": "cam vằn",
            "eye_color": "vàng đồng",
            "appearance_tags": "mèo mướp cam",
            "sale_price": 3500000,
            "sale_status": "available",
            "photo_filename": "t1-cat03.jpg",
            "photo_descriptor": self.cat03_json,
            "reference_photos": [],
        }
        pet_cat10 = {
            "id": 302,
            "code": "PET-142",
            "name": "Mật",
            "species": "Mèo",
            "breed": "Scottish Fold",
            "coat_color": "vàng kem",
            "eye_color": "vàng đồng",
            "appearance_tags": "lông cam kem",
            "sale_price": 3600000,
            "sale_status": "available",
            "photo_filename": "t1-cat10.jpg",
            "photo_descriptor": self.cat10_json,
            "reference_photos": [],
        }

        # 1. Slight crop + brightness + JPEG recompress of PET-135 -> near_duplicate_image for PET-135 ONLY
        cropped_bytes = make_near_duplicate_variant(self.cat03_raw, "near_dup_crop4_bright106_q82")
        norm_c = normalize_image_bytes(cropped_bytes)
        q_c = describe_image(norm_c, raw_sha256=sha256_hex(cropped_bytes), normalized_sha256=sha256_hex(norm_c))
        gate_c = analyze_pet_image(norm_c, flat_pixel_ratio=q_c.flat_pixel_ratio)
        out_c = pet_image_service.rank_pet_candidates_ai4a(
            q_c,
            [pet_cat10, pet_cat03],
            species_gate=gate_c,
            crop_robust_near_dup=True,
        )
        self.assertEqual(out_c["results"][0]["pet"]["code"], "PET-135")
        self.assertEqual(out_c["results"][0]["match_tier"], "near_duplicate_image")
        self.assertGreaterEqual(out_c["results"][0]["score"], 90)
        # PET-142 must NOT be promoted to near_duplicate_image!
        for r in out_c["results"][1:]:
            self.assertEqual(r["match_tier"], "visually_similar_candidate")

        # 2. When crop_robust_near_dup=False (simulating non-duplicate different view with high embedding similarity),
        # candidate stays visually_similar_candidate (<= 89) and sets potential_same_pet_review=True!
        out_non_dup = pet_image_service.rank_pet_candidates_ai4a(
            q_c,
            [pet_cat03],
            species_gate=gate_c,
            crop_robust_near_dup=False,
        )
        self.assertEqual(out_non_dup["results"][0]["match_tier"], "visually_similar_candidate")
        self.assertLessEqual(out_non_dup["results"][0]["score"], 89)
        self.assertTrue(out_non_dup["results"][0]["potential_same_pet_review"])

    def test_add_reference_photo_enforces_confirmation_limit_species_and_rollback_cleanup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_dir = Path(tmpdir)
            app = self._make_app(img_dir)

            @contextmanager
            def fake_conn():
                yield MagicMock()

            cat_record = {
                "id": 7,
                "code": "PET-007",
                "name": "Miu",
                "species": "Mèo",
                "breed": "Mèo ta",
                "sex": "female",
                "birth_date": None,
                "weight_kg": None,
                "coat_color": "cam",
                "eye_color": "vàng",
                "appearance_tags": "mướp cam",
                "photo_filename": "primary007.jpg",
                "photo_descriptor": self.cat03_json,
                "sale_price": 2500000,
                "sale_status": "available",
            }

            with app.app_context():
                # 1. Missing verified_same_pet confirmation checkbox -> rejected immediately
                with self.assertRaises(ValidationError):
                    pet_service.add_reference_photo(
                        1,
                        7,
                        FileStorage(stream=io.BytesIO(self.cat10_raw), filename="c.png", content_type="image/png"),
                        verified_same_pet=False,
                        tenant_id=1,
                    )

                # 2. Over 5-photo gallery limit -> rejected safely
                with (
                    patch.object(pet_service, "read_connection", fake_conn),
                    patch.object(pet_service, "require_actor", return_value={"id": 1, "role": "admin", "tenant_id": 1}),
                    patch.object(pet_service.pet_repo, "get_pet", return_value=cat_record),
                    patch.object(pet_service.pet_repo, "count_reference_photos", return_value=4),
                ):
                    with self.assertRaises(ValidationError) as ctx_lim:
                        pet_service.add_reference_photo(
                            1,
                            7,
                            FileStorage(stream=io.BytesIO(self.cat10_raw), filename="c.png", content_type="image/png"),
                            verified_same_pet=True,
                            tenant_id=1,
                        )
                    self.assertIn("5", str(ctx_lim.exception))
                    self.assertEqual(list(img_dir.iterdir()), [])

                # 3. Uploading a DOG photo onto a CAT record -> rejected by species gate & file cleaned up!
                with (
                    patch.object(pet_service, "read_connection", fake_conn),
                    patch.object(pet_service, "require_actor", return_value={"id": 1, "role": "admin", "tenant_id": 1}),
                    patch.object(pet_service.pet_repo, "get_pet", return_value=cat_record),
                    patch.object(pet_service.pet_repo, "count_reference_photos", return_value=1),
                ):
                    with self.assertRaises(ValidationError):
                        pet_service.add_reference_photo(
                            1,
                            7,
                            FileStorage(stream=io.BytesIO(self.dog01_raw), filename="dog.png", content_type="image/png"),
                            verified_same_pet=True,
                            tenant_id=1,
                        )
                    # Zero orphan files left behind after species-mismatch rejection!
                    self.assertEqual(list(img_dir.iterdir()), [])

                # 4. TEST 13: DB insert failure mid-transaction -> rolls back and cleans up stored image file!
                with (
                    patch.object(pet_service, "read_connection", fake_conn),
                    patch.object(pet_service, "transaction", fake_conn),
                    patch.object(pet_service, "require_actor", return_value={"id": 1, "role": "admin", "tenant_id": 1}),
                    patch.object(pet_service.pet_repo, "get_pet", return_value=cat_record),
                    patch.object(pet_service.pet_repo, "count_reference_photos", return_value=1),
                    patch.object(pet_service.pet_repo, "list_reference_photos", return_value=[]),
                    patch.object(
                        pet_service.pet_repo,
                        "add_reference_photo",
                        side_effect=RuntimeError("Simulated MySQL write failure"),
                    ),
                ):
                    with self.assertRaises(RuntimeError):
                        pet_service.add_reference_photo(
                            1,
                            7,
                            FileStorage(stream=io.BytesIO(self.cat10_raw), filename="cat2.png", content_type="image/png"),
                            verified_same_pet=True,
                            tenant_id=1,
                        )
                    # Stored image file MUST be deleted when DB transaction fails!
                    self.assertEqual(list(img_dir.iterdir()), [])

    def test_reindex_pet_descriptors_updates_both_primary_and_reference_rows(self):
        from petcare.vision.media_storage import LocalMediaStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            img_dir = Path(tmpdir)
            norm_p = normalize_image_bytes(self.cat03_raw)
            norm_r = normalize_image_bytes(self.cat10_raw)
            fn_p = "a" * 32 + ".jpg"
            fn_r = "b" * 32 + ".jpg"
            (img_dir / fn_p).write_bytes(norm_p)
            (img_dir / fn_r).write_bytes(norm_r)

            legacy_p = json.loads(self.cat03_json)
            legacy_p.pop("embedding_version", None)
            legacy_r = json.loads(self.cat10_json)
            legacy_r.pop("embedding_version", None)

            rows = [
                {
                    "photo_source": "primary",
                    "sort_cursor": 10,
                    "id": 10,
                    "tenant_id": 1,
                    "pet_id": 10,
                    "photo_filename": fn_p,
                    "photo_descriptor": json.dumps(legacy_p),
                },
                {
                    "photo_source": "reference",
                    "sort_cursor": 55,
                    "id": 55,
                    "tenant_id": 1,
                    "pet_id": 10,
                    "photo_filename": fn_r,
                    "photo_descriptor": json.dumps(legacy_r),
                },
            ]

            executed_batches: list[tuple[str, list[tuple]]] = []
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor.executemany.side_effect = lambda sql, params: executed_batches.append((sql, list(params)))
            mock_cursor.fetchall.return_value = [(10, 1, self.cat03_json)]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            @contextmanager
            def fake_tx():
                yield mock_conn

            with (
                patch("petcare.vision.reindex_pet_descriptors.read_connection", fake_tx),
                patch("petcare.vision.reindex_pet_descriptors.transaction", fake_tx),
                patch("petcare.vision.reindex_pet_descriptors.fetch_all", side_effect=[rows, []]),
                patch("petcare.vision.reindex_pet_descriptors.pet_repo.sync_pet_gallery_search_index"),
            ):
                stats = reindex_pet_descriptors(apply=True, storage=LocalMediaStorage(img_dir))

            self.assertEqual(stats["scanned"], 2)
            self.assertEqual(stats["updated"], 2)
            update_batches = [(s, p) for s, p in executed_batches if s.strip().startswith("UPDATE")]
            self.assertEqual(len(update_batches), 2)
            self.assertTrue(any("UPDATE pets" in s for s, _p in update_batches))
            self.assertTrue(any("UPDATE pet_reference_photos" in s for s, _p in update_batches))
            for _s, param_rows in update_batches:
                parsed = json.loads(param_rows[0][0])
                self.assertEqual(parsed["embedding_version"], EMBEDDING_VERSION)
                self.assertEqual(parsed["fg_lab_version"], FG_LAB_VERSION)


if __name__ == "__main__":
    unittest.main()
