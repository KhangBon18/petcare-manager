"""Unit tests for AI-4.0e real dataset intake validation, anti-crop safeguards, 5-state identity decisions, and gallery update guards."""

from __future__ import annotations

from contextlib import contextmanager
import copy
import io
from pathlib import Path
import secrets
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.services import pet_image_service, pet_service
from petcare.services.exceptions import ValidationError
from petcare.vision.ai4_benchmark import make_near_duplicate_variant
from petcare.vision.ai4e_validation import (
    build_real_identity_manifest_v4,
    evaluate_enrolled_multi_view_pack,
    validate_real_identity_manifest,
    verify_onnx_models_integrity,
)
from petcare.vision.image_features import (
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import analyze_pet_image, enrich_descriptor_with_local_vision

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"


class AI4EIdentitySafetyAndIntakeUnitTests(unittest.TestCase):
    def test_onnx_model_manifest_checksums_and_sizes_verified(self):
        res = verify_onnx_models_integrity()
        self.assertTrue(res["all_verified"], f"ONNX integrity check failed: {res}")
        self.assertTrue(res["dual_output_1280d_active"])
        self.assertEqual(len(res["files"]), 3)

    def test_default_manifest_v4_validates_and_marks_multi_view_not_evaluated(self):
        m4 = build_real_identity_manifest_v4()
        report = validate_real_identity_manifest(m4, root_dir=ROOT)
        self.assertTrue(report["valid"], f"Validation errors: {report['errors']}")
        self.assertEqual(report["multi_view_evaluation_status"], "MULTI_VIEW_IDENTITY_NOT_EVALUATED")
        self.assertEqual(report["counts"]["enrolled_multi_view_identities"], 0)
        self.assertEqual(report["counts"]["absent_open_set_identities"], 16)

        mv_eval = evaluate_enrolled_multi_view_pack(m4, root_dir=ROOT)
        self.assertEqual(mv_eval["status"], "MULTI_VIEW_IDENTITY_NOT_EVALUATED")
        self.assertIsNone(mv_eval["recall_at_1"])
        self.assertIsNone(mv_eval["recall_at_5"])
        self.assertIsNone(mv_eval["map"])

    def test_intake_validator_blocks_cropped_resized_duplicates_and_cross_split_leakage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            orig_bytes = (REAL_PACK_DIR / "real-cat-orange-cal-01.jpg").read_bytes()
            resized_dup = make_near_duplicate_variant(orig_bytes, "near_dup_resize_480_q70")
            distinct_bytes = (REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes()

            (tmp_root / "p1.jpg").write_bytes(orig_bytes)
            (tmp_root / "p2_resized.jpg").write_bytes(resized_dup)
            (tmp_root / "p3_other.jpg").write_bytes(distinct_bytes)

            def _photo_entry(pid: str, rel: str, assign: str) -> dict:
                return {
                    "photo_id": pid,
                    "image_relpath": rel,
                    "assignment": assign,
                    "source_and_usage_rights": {"owner_consent_or_open_license": True},
                    "capture_session": {"session_id": pid, "independent_capture": True},
                }

            # 1. Disguised resized/recompressed copy rejected as non-independent capture
            bad_dup_manifest = {
                "schema_version": 4,
                "enrolled_multi_view_identities": [
                    {
                        "identity_id": "cat_id_1",
                        "species": "cat",
                        "evaluation_split": "calibration_identities",
                        "photos": [
                            _photo_entry("p1", "p1.jpg", "gallery_primary"),
                            _photo_entry("p2", "p2_resized.jpg", "gallery_secondary"),
                            _photo_entry("p3", "p3_other.jpg", "query"),
                        ],
                    }
                ],
                "absent_open_set_identities": [],
                "real_negative_photographs": [],
            }
            res_dup = validate_real_identity_manifest(bad_dup_manifest, root_dir=tmp_root)
            self.assertFalse(res_dup["valid"])
            self.assertTrue(any("near-duplicate" in e or "duplicate" in e for e in res_dup["errors"]))

            # 2. Missing unregistered query photo & cross-split identity leakage rejected
            shutil.copyfile(DEMO_PETS_DIR / "demo-cat-03.png", tmp_root / "p2_distinct.png")
            bad_split_manifest = {
                "schema_version": 4,
                "enrolled_multi_view_identities": [
                    {
                        "identity_id": "leaked_id",
                        "species": "cat",
                        "evaluation_split": "calibration_identities",
                        "photos": [
                            _photo_entry("p1", "p1.jpg", "gallery_primary"),
                            _photo_entry("p2", "p2_distinct.png", "gallery_secondary"),
                            _photo_entry("p3", "p3_other.jpg", "gallery_secondary"),
                        ],
                    }
                ],
                "absent_open_set_identities": [
                    {
                        "identity_id": "leaked_id",
                        "species": "cat",
                        "evaluation_split": "acceptance_identities",
                        "photos": [_photo_entry("q1", "p3_other.jpg", "query")],
                    }
                ],
                "real_negative_photographs": [],
            }
            res_leak = validate_real_identity_manifest(bad_split_manifest, root_dir=tmp_root)
            self.assertFalse(res_leak["valid"])
            self.assertTrue(any("unregistered held-out query" in e for e in res_leak["errors"]))
            self.assertTrue(any("leakage" in e or "duplicate" in e for e in res_leak["errors"]))

    def test_pilot_multi_view_evaluator_computes_metrics_without_confirming_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            shutil.copyfile(DEMO_PETS_DIR / "demo-cat-03.png", tmp_root / "c1.png")
            shutil.copyfile(DEMO_PETS_DIR / "demo-cat-25.png", tmp_root / "c2.png")
            shutil.copyfile(REAL_PACK_DIR / "real-cat-orange-hold-01.jpg", tmp_root / "c3_query.jpg")

            def _p(pid: str, rel: str, assign: str) -> dict:
                return {
                    "photo_id": pid,
                    "image_relpath": rel,
                    "assignment": assign,
                    "source_and_usage_rights": {"owner_consent_or_open_license": True},
                    "capture_session": {"session_id": pid, "independent_capture": True},
                }

            pilot_manifest = {
                "schema_version": 4,
                "enrolled_multi_view_identities": [
                    {
                        "identity_id": "pilot_ginger_cat_01",
                        "display_name": "Gừng Pilot",
                        "species": "cat",
                        "coat_color": "cam vằn",
                        "evaluation_split": "acceptance_identities",
                        "photos": [
                            _p("p1", "c1.png", "gallery_primary"),
                            _p("p2", "c2.png", "gallery_secondary"),
                            _p("p3", "c3_query.jpg", "query"),
                        ],
                    }
                ],
                "absent_open_set_identities": [],
                "real_negative_photographs": [],
            }
            out = evaluate_enrolled_multi_view_pack(
                pilot_manifest,
                split_filter="acceptance_identities",
                root_dir=tmp_root,
            )
            self.assertEqual(out["status"], "PILOT_SAMPLE_SIZE_LIMITED")
            self.assertEqual(out["identities_evaluated"], 1)
            self.assertEqual(out["independent_queries_evaluated"], 1)
            self.assertEqual(out["false_confirmed_identity_claims"], 0)
            self.assertIsNotNone(out["recall_at_1"])
            self.assertIsNotNone(out["recall_at_1_wilson_95_ci"])

    def test_five_allowed_identity_decisions_and_update_pet_gallery_guards(self):
        cat03_raw = (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes()
        cat03_norm = normalize_image_bytes(cat03_raw)
        cat03_desc = enrich_descriptor_with_local_vision(
            cat03_norm,
            describe_image(cat03_norm, raw_sha256=sha256_hex(cat03_raw), normalized_sha256=sha256_hex(cat03_norm)),
        )
        cat03_json = descriptor_to_json(cat03_desc)

        cat_cand = {
            "id": 1,
            "code": "PET-135",
            "name": "Gừng",
            "species": "Mèo",
            "breed": "British Shorthair",
            "coat_color": "cam vằn",
            "eye_color": "vàng",
            "appearance_tags": "mướp cam",
            "sale_price": 3500000,
            "sale_status": "available",
            "photo_filename": "p1.jpg",
            "photo_descriptor": cat03_json,
            "reference_photos": [],
        }

        # 1. Exact stored image -> exact_stored_image_match
        gate_exact = analyze_pet_image(cat03_norm, flat_pixel_ratio=cat03_desc.flat_pixel_ratio)
        res_ex = pet_image_service.rank_pet_candidates_ai4e(cat03_desc, [cat_cand], species_gate=gate_exact)
        self.assertEqual(res_ex["identity_decision"], "exact_stored_image_match")
        self.assertEqual(res_ex["results"][0]["identity_decision"], "exact_stored_image_match")

        # 2. Near-duplicate -> near_duplicate_image
        nd_raw = make_near_duplicate_variant(cat03_raw, "near_dup_resize_480_q70")
        nd_norm = normalize_image_bytes(nd_raw)
        nd_desc = describe_image(nd_norm, raw_sha256=sha256_hex(nd_raw), normalized_sha256=sha256_hex(nd_norm))
        gate_nd = analyze_pet_image(nd_norm, flat_pixel_ratio=nd_desc.flat_pixel_ratio)
        res_nd = pet_image_service.rank_pet_candidates_ai4e(nd_desc, [cat_cand], species_gate=gate_nd)
        self.assertEqual(res_nd["identity_decision"], "near_duplicate_image")
        self.assertEqual(res_nd["results"][0]["identity_decision"], "near_duplicate_image")

        # 3. Non-animal -> no_confident_match
        inv_raw = (ROOT / "docs" / "assets" / "phase62" / "classroom-invoice.png").read_bytes()
        inv_norm = normalize_image_bytes(inv_raw)
        inv_desc = describe_image(inv_norm, raw_sha256=sha256_hex(inv_raw), normalized_sha256=sha256_hex(inv_norm))
        gate_inv = analyze_pet_image(inv_norm, flat_pixel_ratio=inv_desc.flat_pixel_ratio)
        res_no = pet_image_service.rank_pet_candidates_ai4e(inv_desc, [cat_cand], species_gate=gate_inv)
        self.assertEqual(res_no["identity_decision"], "no_confident_match")
        self.assertEqual(res_no["results"], [])

        # 4. update_pet guards: block species change & duplicate SHA-256 primary upload when reference photos exist
        with tempfile.TemporaryDirectory() as tmpdir:
            img_dir = Path(tmpdir)
            app = create_app({
                "TESTING": True,
                "SECRET_KEY": secrets.token_urlsafe(32),
                "PET_IMAGE_DIR": str(img_dir),
                "AI_VISION_ENABLED": False,
                "AI_PROVIDER_APPROVED": False,
            })

            @contextmanager
            def fake_conn():
                yield MagicMock()

            current_pet = {
                "id": 9,
                "code": "PET-009",
                "name": "Gừng",
                "species": "Mèo",
                "breed": "Mèo ta",
                "sex": "female",
                "birth_date": None,
                "weight_kg": None,
                "coat_color": "cam",
                "eye_color": "vàng",
                "appearance_tags": "",
                "photo_filename": "prim.jpg",
                "photo_descriptor": cat03_json,
                "sale_price": 2000000,
                "sale_status": "available",
            }
            actor_dict = {
                "id": 1,
                "role": "admin",
                "tenant_id": 1,
                "default_currency": "VND",
                "timezone": "Asia/Ho_Chi_Minh",
            }
            ref_list = [{"id": 50, "photo_filename": "sec.jpg", "photo_descriptor": cat03_json}]

            with app.app_context():
                # 4a. Block changing species from Mèo -> Chó while verified cat reference photos exist
                with (
                    patch.object(pet_service, "read_connection", fake_conn),
                    patch.object(pet_service, "transaction", fake_conn),
                    patch.object(pet_service, "require_actor", return_value=actor_dict),
                    patch.object(pet_service.pet_repo, "get_pet", return_value=current_pet),
                    patch.object(pet_service.pet_repo, "list_reference_photos", return_value=ref_list),
                ):
                    with self.assertRaises(ValidationError):
                        pet_service.update_pet(
                            1,
                            9,
                            {
                                "code": "PET-009",
                                "name": "Gừng",
                                "species": "Chó",
                                "sale_price": "2000000",
                            },
                            image_upload=None,
                            tenant_id=1,
                        )

                # 4b. Block uploading a primary photo identical to an existing secondary gallery photo, cleaning up file
                with (
                    patch.object(pet_service, "read_connection", fake_conn),
                    patch.object(pet_service, "transaction", fake_conn),
                    patch.object(pet_service, "require_actor", return_value=actor_dict),
                    patch.object(pet_service.pet_repo, "get_pet", return_value=current_pet),
                    patch.object(pet_service.pet_repo, "list_reference_photos", return_value=ref_list),
                ):
                    with self.assertRaises(ValidationError):
                        pet_service.update_pet(
                            1,
                            9,
                            {
                                "code": "PET-009",
                                "name": "Gừng",
                                "species": "Mèo",
                                "sale_price": "2000000",
                            },
                            image_upload=FileStorage(
                                stream=io.BytesIO(cat03_raw),
                                filename="dup.png",
                                content_type="image/png",
                            ),
                            tenant_id=1,
                        )
                    self.assertEqual(list(img_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
