"""MySQL integration tests for AI-4.0a precision-first pet image matching, species filtering, and tenant isolation."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import secrets
import unittest
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection, transaction
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_one
from petcare.services import pet_image_service, pet_service
from petcare.vision.ai4_benchmark import make_near_duplicate_variant
from petcare.vision.coat_color_lab import EMBEDDING_VERSION, FG_LAB_VERSION
from petcare.vision.reindex_pet_descriptors import reindex_pet_descriptors
from petcare.vision.species_taxonomy import canonicalize_species
from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class AI4ImageMatchingMySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        Path(Config.PET_IMAGE_DIR).mkdir(parents=True, exist_ok=True, mode=0o700)

        initialize_database()
        seed_database()

        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": secrets.token_urlsafe(32),
            "WTF_CSRF_ENABLED": True,
            "PET_IMAGE_DIR": Config.PET_IMAGE_DIR,
            "VISION_RATE_LIMIT_PER_MINUTE": 1000,
            "VISION_IP_RATE_LIMIT_PER_MINUTE": 1000,
            "AI_VISION_ENABLED": False,
            "AI_PROVIDER_APPROVED": False,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
        })

        with get_connection() as conn:
            cls.main_tenant_id = fetch_one(conn, "SELECT id FROM tenants WHERE slug = 'main'")["id"]
            cls.admin_id = fetch_one(conn, "SELECT id FROM users WHERE username = 'admin'")["id"]
            cls.staff_id = fetch_one(conn, "SELECT id FROM users WHERE username = 'staff1'")["id"]
            cls.main_pet157_photo = fetch_one(
                conn,
                "SELECT photo_filename FROM pets WHERE tenant_id = %s AND code = 'PET-157'",
                (cls.main_tenant_id,),
            )["photo_filename"]

        # Provision an isolated secondary store where PET-157 (demo-cat-25.png) is genuinely absent
        suffix = uuid4().hex[:8]
        cls.branch_slug = f"ai4-branch-{suffix}"
        cls.branch_user = f"ai4owner_{suffix}"
        cls.branch_pw = secrets.token_urlsafe(24)
        cls.branch_tenant_id, cls.branch_user_id = create_store(
            cls.branch_slug,
            "PetCare AI4 Branch QA",
            cls.branch_user,
            "AI4 Branch Owner",
            cls.branch_pw,
        )

        branch_seed = (
            ("BR-CAT-01", "Gừng Nhánh", "Mèo", "British Shorthair", "cam vằn", "vàng đồng", "mèo mướp cam", "demo-cat-03.png"),
            ("BR-CAT-02", "Mật Nhánh", "Mèo", "Scottish Fold", "vàng kem", "vàng đồng", "tai cụp lông cam kem", "demo-cat-10.png"),
            ("BR-CAT-03", "Đêm Nhánh", "Mèo", "Bombay", "đen tuyền", "vàng đồng", "lông đen bóng", "demo-cat-16.png"),
            ("BR-CAT-04", "Khói Nhánh", "Mèo", "British Shorthair", "xám xanh", "vàng hổ phách", "lông ngắn dày", "demo-cat-01.png"),
            ("BR-DOG-01", "Bắp Nhánh", "Chó", "Golden Retriever", "vàng kim", "nâu ấm", "lông dài vàng, dáng lớn", "demo-dog-01.png"),
            ("BR-DOG-02", "Cam Nhánh", "Chó", "Pomeranian", "cam vàng", "nâu đậm", "lông xù dày, dáng nhỏ", "demo-dog-21.png"),
        )
        cls.branch_pet_ids: list[int] = []
        with cls.app.app_context():
            for code, name, species, breed, coat, eyes, tags, asset in branch_seed:
                raw = (DEMO_PETS_DIR / asset).read_bytes()
                pid = pet_service.create_pet(
                    cls.branch_user_id,
                    {
                        "code": code,
                        "name": name,
                        "species": species,
                        "breed": breed,
                        "sex": "female",
                        "coat_color": coat,
                        "eye_color": eyes,
                        "appearance_tags": tags,
                        "sale_price": "3500000",
                    },
                    image_upload=FileStorage(stream=io.BytesIO(raw), filename=asset, content_type="image/png"),
                    tenant_id=cls.branch_tenant_id,
                )
                cls.branch_pet_ids.append(pid)

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.previous_db_name

    def _login_client(self, username: str, password: str, store_slug: str = "main"):
        client = self.app.test_client()
        page = client.get("/login")
        m = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
        self.assertIsNotNone(m)
        resp = client.post(
            "/login",
            data={
                "csrf_token": m.group(1),
                "store_slug": store_slug,
                "username": username,
                "password": password,
            },
        )
        self.assertEqual(resp.status_code, 302)
        return client

    def test_exact_stored_orange_cat_and_corgi_rank_first_at_100(self):
        with self.app.app_context():
            for code, asset, expected_sp in (
                ("PET-001", "miu-orange-cream.png", "cat"),
                ("PET-111", "demo-dog-11.png", "dog"),
            ):
                out = pet_image_service.search_similar(
                    self.admin_id,
                    (DEMO_PETS_DIR / asset).read_bytes(),
                    tenant_id=self.main_tenant_id,
                )
                self.assertEqual(out["match_outcome"], "exact_image_match")
                self.assertEqual(out["results"][0]["pet"]["code"], code)
                self.assertEqual(out["results"][0]["score"], 100)
                self.assertEqual(out["results"][0]["match_tier"], "exact_image_match")
                self.assertTrue(
                    all(canonicalize_species(r["pet"]["species"]) == expected_sp for r in out["results"])
                )

    def test_cat_and_dog_queries_never_cross_species_including_resized_near_duplicate(self):
        with self.app.app_context():
            cat_resized = make_near_duplicate_variant(
                (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes(),
                "near_dup_resize_480_q70",
            )
            cat_out = pet_image_service.search_similar(
                self.admin_id,
                cat_resized,
                tenant_id=self.main_tenant_id,
            )
            self.assertEqual(cat_out["results"][0]["pet"]["code"], "PET-135")
            self.assertEqual(cat_out["results"][0]["match_tier"], "near_duplicate_image")
            self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "cat" for r in cat_out["results"]))

            dog_out = pet_image_service.search_similar(
                self.admin_id,
                (DEMO_PETS_DIR / "demo-dog-01.png").read_bytes(),
                tenant_id=self.main_tenant_id,
            )
            self.assertEqual(dog_out["results"][0]["pet"]["code"], "PET-101")
            self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "dog" for r in dog_out["results"]))

    def test_non_animal_invoice_rejected_unfiltered_and_with_species_filter(self):
        invoice_bytes = (ROOT / "docs" / "assets" / "phase62" / "classroom-invoice.png").read_bytes()
        with self.app.app_context():
            for sp in ("", "Mèo", "cat", "Chó", "dog"):
                out = pet_image_service.search_similar(
                    self.admin_id,
                    invoice_bytes,
                    species=sp,
                    tenant_id=self.main_tenant_id,
                )
                self.assertEqual(out["results"], [])
                self.assertEqual(out["match_outcome"], "no_confident_match")
                self.assertEqual(out["abstention_reason"], "non_photographic_or_low_texture")

    def test_absent_orange_cat_and_cross_tenant_isolation(self):
        absent_orange_bytes = (DEMO_PETS_DIR / "demo-cat-25.png").read_bytes()
        real_dog_bytes = (ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack" / "real-dog-golden-cal-01.jpg").read_bytes()
        real_multi_bytes = (ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack" / "real-multi-catdog-hold-01.jpg").read_bytes()
        with self.app.app_context():
            # AI-4.0b: Even though demo-cat-25.png is PET-157 in 'main', branch tenant NEVER sees PET-157,
            # automatically detects one_cat without manual species, and returns only branch orange cats!
            auto_out = pet_image_service.search_similar(
                self.branch_user_id,
                absent_orange_bytes,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(auto_out["verified_species"], "cat")
            self.assertEqual(auto_out["verified_species_source"], "local_detector")
            self.assertGreaterEqual(len(auto_out["results"]), 1)
            returned_codes = {r["pet"]["code"] for r in auto_out["results"]}
            self.assertTrue(returned_codes.issubset({"BR-CAT-01", "BR-CAT-02"}))
            for item in auto_out["results"]:
                self.assertEqual(item["match_tier"], "visually_similar_candidate")
                self.assertEqual(item["pet"]["species"], "Mèo")

            # Phase 6 guardrail: manual species='Mèo' on a verified dog photo must reject as species_contradiction
            contradicted = pet_image_service.search_similar(
                self.branch_user_id,
                real_dog_bytes,
                species="Mèo",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(contradicted["results"], [])
            self.assertEqual(contradicted["abstention_reason"], "species_contradiction")

            # Multi-animal photo is rejected cleanly
            multi_out = pet_image_service.search_similar(
                self.branch_user_id,
                real_multi_bytes,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(multi_out["results"], [])
            self.assertEqual(multi_out["abstention_reason"], "multiple_animals_detected")

            # When AI_LOCAL_SPECIES_GATE_ENABLED=False, preserves AI-4.0a species_unverified abstention
            self.app.config["AI_LOCAL_SPECIES_GATE_ENABLED"] = False
            try:
                gate_off = pet_image_service.search_similar(
                    self.branch_user_id,
                    absent_orange_bytes,
                    species="",
                    tenant_id=self.branch_tenant_id,
                )
                self.assertEqual(gate_off["results"], [])
                self.assertEqual(gate_off["abstention_reason"], "species_unverified")
            finally:
                self.app.config["AI_LOCAL_SPECIES_GATE_ENABLED"] = True

        # HTTP check: branch owner cannot download main store's pet photo
        branch_client = self._login_client(self.branch_user, self.branch_pw, store_slug=self.branch_slug)
        photo_resp = branch_client.get(f"/pets/photo/{self.main_pet157_photo}")
        self.assertEqual(photo_resp.status_code, 404)

    def test_status_authorization_and_staff_rbac_preserved(self):
        # Mark BR-CAT-01 inactive and verify status='available' excludes its exact photo match
        with self.app.app_context():
            pet_service.set_inactive(
                self.branch_user_id,
                self.branch_pet_ids[0],
                True,
                tenant_id=self.branch_tenant_id,
            )
            try:
                avail_out = pet_image_service.search_similar(
                    self.branch_user_id,
                    (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes(),
                    status="available",
                    tenant_id=self.branch_tenant_id,
                )
                self.assertNotIn("BR-CAT-01", [r["pet"]["code"] for r in avail_out["results"]])

                inact_out = pet_image_service.search_similar(
                    self.branch_user_id,
                    (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes(),
                    status="inactive",
                    tenant_id=self.branch_tenant_id,
                )
                self.assertEqual(inact_out["results"][0]["pet"]["code"], "BR-CAT-01")
                self.assertEqual(inact_out["results"][0]["match_tier"], "exact_image_match")
            finally:
                pet_service.set_inactive(
                    self.branch_user_id,
                    self.branch_pet_ids[0],
                    False,
                    tenant_id=self.branch_tenant_id,
                )

        staff_client = self._login_client("staff1", DEMO_STAFF_PASSWORD, store_slug="main")
        self.assertEqual(staff_client.get("/pets/find-similar").status_code, 200)
        self.assertEqual(staff_client.get("/pets/new").status_code, 403)

    def test_ai4c_reindex_backfill_idempotency_and_fine_grained_ranking(self):
        # 1. Strip AI-4.0c embedding_version from BR-CAT-01 to simulate a legacy pre-AI-4.0c row
        target_pet_id = self.branch_pet_ids[0]
        with get_connection() as conn:
            orig_row = fetch_one(
                conn,
                "SELECT photo_filename, photo_descriptor FROM pets WHERE id = %s AND tenant_id = %s",
                (target_pet_id, self.branch_tenant_id),
            )
            orig_dict = json.loads(orig_row["photo_descriptor"])
            orig_raw_sha = orig_dict["raw_sha256"]
            legacy_dict = dict(orig_dict)
            legacy_dict.pop("embedding_version", None)
            legacy_dict.pop("embedding_b64", None)
            legacy_dict.pop("fg_lab_version", None)
            legacy_dict.pop("fg_lab_histogram", None)

        with transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SET @petcare_tenant_id = %s", (self.branch_tenant_id,))
                cur.execute(
                    "UPDATE pets SET photo_descriptor = %s WHERE id = %s AND tenant_id = %s",
                    (json.dumps(legacy_dict), target_pet_id, self.branch_tenant_id),
                )
            finally:
                cur.close()

        # Dry-run previews without writing; apply=True backfills AI-4.0c fields while preserving raw_sha256
        dry = reindex_pet_descriptors(apply=False)
        self.assertGreaterEqual(dry["prepared"], 1)
        self.assertEqual(dry["updated"], 0)

        applied = reindex_pet_descriptors(apply=True)
        self.assertGreaterEqual(applied["updated"], 1)

        # Second immediate run skips already up-to-date cached descriptors (0 redundant ONNX calls)
        second = reindex_pet_descriptors(apply=True)
        self.assertEqual(second["scanned"], 0)
        self.assertEqual(second["updated"], 0)

        with get_connection() as conn:
            rebuilt_row = fetch_one(
                conn,
                "SELECT photo_filename, photo_descriptor FROM pets WHERE id = %s AND tenant_id = %s",
                (target_pet_id, self.branch_tenant_id),
            )
            rebuilt_dict = json.loads(rebuilt_row["photo_descriptor"])
            self.assertEqual(rebuilt_row["photo_filename"], orig_row["photo_filename"])
            self.assertEqual(rebuilt_dict["raw_sha256"], orig_raw_sha)
            self.assertEqual(rebuilt_dict["embedding_version"], EMBEDDING_VERSION)
            self.assertEqual(rebuilt_dict["fg_lab_version"], FG_LAB_VERSION)

        # 2. Fine-grained ranking: real Golden Retriever ranks BR-DOG-01 (Golden Retriever) #1 ahead of BR-DOG-02 (Pomeranian)
        real_golden_bytes = (
            ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack" / "real-dog-golden-cal-01.jpg"
        ).read_bytes()
        real_tabby_bytes = (
            ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack" / "real-cat-orange-hold-01.jpg"
        ).read_bytes()
        with self.app.app_context():
            dog_out = pet_image_service.search_similar(
                self.branch_user_id,
                real_golden_bytes,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(dog_out["results"][0]["pet"]["code"], "BR-DOG-01")
            self.assertEqual(dog_out["results"][0]["match_tier"], "visually_similar_candidate")
            self.assertIn("morphology", dog_out["results"][0]["components"])

            cat_out = pet_image_service.search_similar(
                self.branch_user_id,
                real_tabby_bytes,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(cat_out["results"][0]["pet"]["code"], "BR-CAT-01")
            self.assertEqual(cat_out["results"][0]["match_tier"], "visually_similar_candidate")

            # Offline rollback flag AI_FOREGROUND_EMBEDDING_ENABLED=False falls back cleanly
            self.app.config["AI_FOREGROUND_EMBEDDING_ENABLED"] = False
            try:
                rb_out = pet_image_service.search_similar(
                    self.branch_user_id,
                    real_golden_bytes,
                    species="",
                    tenant_id=self.branch_tenant_id,
                )
                self.assertTrue(all(r["pet"]["species"] == "Chó" for r in rb_out["results"]))
            finally:
                self.app.config["AI_FOREGROUND_EMBEDDING_ENABLED"] = True

    def test_ai4d_multi_photo_gallery_crud_secondary_rank1_limit_tenancy_and_rollback(self):
        from unittest.mock import patch
        from petcare.database.readiness import schema_contract_is_ready
        from petcare.services.exceptions import ValidationError

        # 1. Repeatable migration & readiness check (non-destructive on existing pets)
        initialize_database()
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                self.assertTrue(schema_contract_is_ready(cur))
            finally:
                cur.close()

        cat_pet_id = self.branch_pet_ids[0]  # BR-CAT-01 (primary: demo-cat-03.png)
        sec_assets = (
            ("demo-cat-25.png", "front_view"),
            ("demo-cat-05.png", "side_view"),
            ("demo-cat-07.png", "coat_detail"),
            ("demo-cat-12.png", "lighting_variant"),
        )
        added_ref_ids: list[int] = []
        media_dir = Path(Config.PET_IMAGE_DIR)

        with self.app.app_context():
            # Reject uploading a dog photo onto a cat record (species consistency + zero orphan files)
            before_files = set(os.listdir(media_dir))
            dog_bytes = (DEMO_PETS_DIR / "demo-dog-02.png").read_bytes()
            with self.assertRaises(ValidationError):
                pet_service.add_reference_photo(
                    self.branch_user_id,
                    cat_pet_id,
                    FileStorage(stream=io.BytesIO(dog_bytes), filename="wrong_dog.png", content_type="image/png"),
                    image_role="side_view",
                    verified_same_pet=True,
                    tenant_id=self.branch_tenant_id,
                )
            self.assertEqual(set(os.listdir(media_dir)), before_files)

            # TEST 13: Simulated DB error during add_reference_photo cleans up stored file without orphans
            cat_rollback_bytes = (DEMO_PETS_DIR / "demo-cat-25.png").read_bytes()
            with patch(
                "petcare.services.pet_service.pet_repo.add_reference_photo",
                side_effect=RuntimeError("Simulated DB failure"),
            ):
                with self.assertRaises(RuntimeError):
                    pet_service.add_reference_photo(
                        self.branch_user_id,
                        cat_pet_id,
                        FileStorage(stream=io.BytesIO(cat_rollback_bytes), filename="rb.png", content_type="image/png"),
                        image_role="front_view",
                        verified_same_pet=True,
                        tenant_id=self.branch_tenant_id,
                    )
            self.assertEqual(set(os.listdir(media_dir)), before_files)

            # Add 4 verified cat reference photos -> reaches 5/5 total gallery photos
            for fname, role in sec_assets:
                raw = (DEMO_PETS_DIR / fname).read_bytes()
                rid = pet_service.add_reference_photo(
                    self.branch_user_id,
                    cat_pet_id,
                    FileStorage(stream=io.BytesIO(raw), filename=fname, content_type="image/png"),
                    image_role=role,
                    verified_same_pet=True,
                    tenant_id=self.branch_tenant_id,
                )
                added_ref_ids.append(rid)

            pet_full = pet_service.get_pet(self.branch_user_id, cat_pet_id, tenant_id=self.branch_tenant_id)
            self.assertEqual(pet_full["gallery_photo_count"], 5)
            self.assertEqual(len(pet_full["reference_photos"]), 4)
            sec2_filename = pet_full["reference_photos"][0]["photo_filename"]

            # TEST 9: 6th photo over 5-photo limit fails safely with zero orphan files
            files_at_5 = set(os.listdir(media_dir))
            extra_cat = (DEMO_PETS_DIR / "demo-cat-14.png").read_bytes()
            with self.assertRaises(ValidationError):
                pet_service.add_reference_photo(
                    self.branch_user_id,
                    cat_pet_id,
                    FileStorage(stream=io.BytesIO(extra_cat), filename="over.png", content_type="image/png"),
                    image_role="additional",
                    verified_same_pet=True,
                    tenant_id=self.branch_tenant_id,
                )
            self.assertEqual(set(os.listdir(media_dir)), files_at_5)

            # TEST 2 & TEST 4: Search using exact secondary photo (#2) -> ranks BR-CAT-01 at Rank 1 and appears ONLY ONCE!
            sec2_query = (DEMO_PETS_DIR / "demo-cat-25.png").read_bytes()
            sec_out = pet_image_service.search_similar(
                self.branch_user_id,
                sec2_query,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(sec_out["match_outcome"], "exact_image_match")
            self.assertEqual(sec_out["results"][0]["pet"]["code"], "BR-CAT-01")
            self.assertEqual(sec_out["results"][0]["match_tier"], "exact_image_match")
            self.assertEqual(sec_out["results"][0]["matched_photo_index"], 2)
            self.assertEqual(sec_out["results"][0]["gallery_photo_count"], 5)
            codes_in_res = [r["pet"]["code"] for r in sec_out["results"]]
            self.assertEqual(codes_in_res.count("BR-CAT-01"), 1)

            # Crop-robust near-duplicate of secondary photo #2 also resolves to BR-CAT-01 without duplicate cards
            crop_sec2 = make_near_duplicate_variant(sec2_query, "near_dup_crop4_bright106_q82")
            crop_out = pet_image_service.search_similar(
                self.branch_user_id,
                crop_sec2,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertEqual(crop_out["results"][0]["pet"]["code"], "BR-CAT-01")
            self.assertEqual(crop_out["results"][0]["match_tier"], "near_duplicate_image")
            self.assertEqual([r["pet"]["code"] for r in crop_out["results"]].count("BR-CAT-01"), 1)

        # TEST 8: Cross-tenant HTTP access to branch store's secondary gallery photo is blocked (404)
        main_admin_client = self._login_client("admin", DEMO_ADMIN_PASSWORD, store_slug="main")
        self.assertEqual(main_admin_client.get(f"/pets/photo/{sec2_filename}").status_code, 404)

        # TEST 10: Remove all 4 added reference photos and confirm search descriptors & files stay consistent
        with self.app.app_context():
            # Test reorder make_primary + swap back first
            pet_service.reorder_reference_photo(
                self.branch_user_id,
                cat_pet_id,
                added_ref_ids[0],
                "make_primary",
                tenant_id=self.branch_tenant_id,
            )
            swapped = pet_service.get_pet(self.branch_user_id, cat_pet_id, tenant_id=self.branch_tenant_id)
            self.assertEqual(swapped["photo_filename"], sec2_filename)
            pet_service.reorder_reference_photo(
                self.branch_user_id,
                cat_pet_id,
                added_ref_ids[0],
                "make_primary",
                tenant_id=self.branch_tenant_id,
            )

            for rid in added_ref_ids:
                pet_service.remove_reference_photo(
                    self.branch_user_id,
                    cat_pet_id,
                    rid,
                    tenant_id=self.branch_tenant_id,
                )

            restored = pet_service.get_pet(self.branch_user_id, cat_pet_id, tenant_id=self.branch_tenant_id)
            self.assertEqual(restored["gallery_photo_count"], 1)
            self.assertEqual(restored["reference_photos"], [])
            self.assertFalse((media_dir / sec2_filename).exists())

            # Secondary photo #2 is no longer an exact match in branch store after removal!
            after_rm = pet_image_service.search_similar(
                self.branch_user_id,
                sec2_query,
                species="",
                tenant_id=self.branch_tenant_id,
            )
            self.assertNotEqual(after_rm["match_outcome"], "exact_image_match")


if __name__ == "__main__":
    unittest.main()
