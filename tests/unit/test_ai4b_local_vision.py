"""Unit tests for AI-4.0b real local ONNX pet detection, calibrated species gate, and matching integration."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from petcare.database.seed import DEMO_PET_IMAGES, PETS
from petcare.services.pet_image_service import (
    MATCH_OUTCOME_NONE,
    MATCH_TIER_EXACT,
    MATCH_TIER_SIMILAR,
    rank_pet_candidates_ai4a,
)
from petcare.vision.ai4b_benchmark import (
    build_ai4b_manifest_v2,
    make_degraded_variant_bytes,
)
from petcare.vision.image_features import (
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import (
    MODELS_DIR,
    SUBJECT_AMBIGUOUS,
    SUBJECT_GATE_UNAVAILABLE,
    SUBJECT_MULTIPLE_ANIMALS,
    SUBJECT_NO_RELIABLE_ANIMAL,
    SUBJECT_ONE_CAT,
    SUBJECT_ONE_DOG,
    SUBJECT_OTHER_ANIMAL,
    _LocalVisionRuntime,
    analyze_pet_image,
    get_model_manifest_summary,
)
from petcare.vision.species_taxonomy import canonicalize_species

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"


def _build_pet_row(pet_id: int, tuple_row: tuple) -> dict:
    code, name, species, breed, _sex, _bdate, _wt, coat, eyes, tags, price = tuple_row
    raw_bytes = (DEMO_PETS_DIR / DEMO_PET_IMAGES[code]).read_bytes()
    norm_bytes = normalize_image_bytes(raw_bytes)
    desc = describe_image(
        norm_bytes,
        raw_sha256=sha256_hex(raw_bytes),
        normalized_sha256=sha256_hex(norm_bytes),
    )
    return {
        "id": pet_id,
        "code": code,
        "name": name,
        "species": species,
        "breed": breed,
        "coat_color": coat,
        "eye_color": eyes,
        "appearance_tags": tags,
        "sale_price": price,
        "sale_status": "available",
        "photo_filename": f"t1-{pet_id:032x}.jpg",
        "photo_descriptor": descriptor_to_json(desc),
        "_raw_bytes": raw_bytes,
    }


class AI4BLocalVisionUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        codes = {
            "PET-001",  # Orange cream cat
            "PET-135",  # Orange tabby cat
            "PET-142",  # Orange cream cat
            "PET-136",  # Tuxedo black-white cat
            "PET-148",  # Solid black cat
            "PET-101",  # Golden Retriever dog
            "PET-102",  # Light tan Terrier dog
            "PET-105",  # Orange Pomeranian dog
            "PET-116",  # Gray-white Husky dog
            "PET-118",  # Cream French Bulldog
            "PET-121",  # Orange-yellow Pomeranian dog
            "PET-103",  # Black dog
        }
        cls.catalog = [
            _build_pet_row(idx, p)
            for idx, p in enumerate(PETS, start=1)
            if p[0] in codes
        ]
        cls.by_code = {r["code"]: r for r in cls.catalog}

    @staticmethod
    def _eval_image(raw_bytes: bytes):
        norm = normalize_image_bytes(raw_bytes)
        qd = describe_image(
            norm,
            raw_sha256=sha256_hex(raw_bytes),
            normalized_sha256=sha256_hex(norm),
        )
        gate = analyze_pet_image(norm, flat_pixel_ratio=qd.flat_pixel_ratio)
        return qd, gate

    def test_bundled_models_have_permissive_licenses_and_verified_sha256(self):
        manifest = get_model_manifest_summary()
        self.assertFalse(manifest["runtime"]["pytorch_required_at_runtime"])
        self.assertFalse(manifest["runtime"]["network_access_at_runtime"])
        self.assertEqual(len(manifest["models"]), 2)
        for m in manifest["models"]:
            self.assertEqual(m["license"], "Apache-2.0")
            fpath = MODELS_DIR / m["filename"]
            self.assertTrue(fpath.is_file())
            self.assertEqual(sha256_hex(fpath.read_bytes()), m["sha256"])

    def test_corrupted_model_checksum_fails_safely_without_crashing(self):
        broken_runtime = _LocalVisionRuntime()
        with patch("petcare.vision.local_pet_detector._RUNTIME", broken_runtime), patch(
            "petcare.vision.local_pet_detector.sha256_hex", return_value="0" * 64
        ):
            norm = normalize_image_bytes((REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes())
            gate = analyze_pet_image(norm)
            self.assertEqual(gate.subject_status, SUBJECT_GATE_UNAVAILABLE)
            self.assertIsNone(gate.verified_species)

    def test_automatic_new_orange_cat_detection_excludes_golden_dogs_and_claims_no_identity(self):
        qd, gate = self._eval_image((REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes())
        self.assertEqual(gate.subject_status, SUBJECT_ONE_CAT)
        self.assertEqual(gate.verified_species, "cat")
        self.assertEqual(gate.animal_count, 1)

        out = rank_pet_candidates_ai4a(qd, self.catalog, explicit_species=None, species_gate=gate)
        self.assertEqual(out["verified_species"], "cat")
        self.assertEqual(out["verified_species_source"], "local_detector")
        self.assertGreaterEqual(len(out["results"]), 1)
        for item in out["results"]:
            self.assertEqual(canonicalize_species(item["pet"]["species"]), "cat")
            self.assertEqual(item["match_tier"], MATCH_TIER_SIMILAR)
            self.assertNotIn(item["pet"]["code"], {"PET-136", "PET-148"})

    def test_automatic_new_golden_dog_detection_excludes_all_cats(self):
        for img_path in (
            REAL_PACK_DIR / "real-dog-golden-cal-01.jpg",
            DEMO_PETS_DIR / "demo-dog-31.png",
        ):
            qd, gate = self._eval_image(img_path.read_bytes())
            self.assertEqual(gate.subject_status, SUBJECT_ONE_DOG)
            self.assertEqual(gate.verified_species, "dog")

            out = rank_pet_candidates_ai4a(qd, self.catalog, explicit_species=None, species_gate=gate)
            self.assertEqual(out["verified_species"], "dog")
            self.assertEqual(out["verified_species_source"], "local_detector")
            self.assertGreaterEqual(len(out["results"]), 1)
            for item in out["results"]:
                self.assertEqual(canonicalize_species(item["pet"]["species"]), "dog")
                self.assertEqual(item["match_tier"], MATCH_TIER_SIMILAR)

        # Holdout real black Labrador with red fence / bright tongue: verified as dog, zero cats returned
        qd_hold, gate_hold = self._eval_image((REAL_PACK_DIR / "real-dog-other-hold-04.jpg").read_bytes())
        self.assertEqual(gate_hold.subject_status, SUBJECT_ONE_DOG)
        self.assertEqual(gate_hold.verified_species, "dog")
        out_hold = rank_pet_candidates_ai4a(qd_hold, self.catalog, explicit_species=None, species_gate=gate_hold)
        self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "dog" for r in out_hold["results"]))

    def test_manual_species_filter_never_turns_dog_photo_into_cat_match(self):
        qd, gate = self._eval_image((REAL_PACK_DIR / "real-dog-golden-hold-02.jpg").read_bytes())
        self.assertEqual(gate.verified_species, "dog")
        contradicted = rank_pet_candidates_ai4a(
            qd, self.catalog, explicit_species="cat", species_gate=gate
        )
        self.assertEqual(contradicted["results"], [])
        self.assertEqual(contradicted["match_outcome"], MATCH_OUTCOME_NONE)
        self.assertEqual(contradicted["abstention_reason"], "species_contradiction")

        # Exact stored dog photo with contradictory manual species='cat' must ALSO reject!
        qd_stored, gate_stored = self._eval_image(self.by_code["PET-101"]["_raw_bytes"])
        contradicted_stored = rank_pet_candidates_ai4a(
            qd_stored, self.catalog, explicit_species="cat", species_gate=gate_stored
        )
        self.assertEqual(contradicted_stored["results"], [])
        self.assertEqual(contradicted_stored["abstention_reason"], "species_contradiction")

    def test_exact_stored_orange_cat_preserves_tier0_priority(self):
        qd, gate = self._eval_image(self.by_code["PET-001"]["_raw_bytes"])
        out = rank_pet_candidates_ai4a(qd, self.catalog, explicit_species=None, species_gate=gate)
        self.assertEqual(out["results"][0]["pet"]["code"], "PET-001")
        self.assertEqual(out["results"][0]["match_tier"], MATCH_TIER_EXACT)
        self.assertEqual(out["results"][0]["score"], 100)

    def test_plush_toy_natural_non_animal_other_animal_and_multi_animal_are_rejected(self):
        # Plush teddy bear
        qd_toy, gate_toy = self._eval_image((REAL_PACK_DIR / "real-neg-toy-cal-01.jpg").read_bytes())
        self.assertEqual(gate_toy.subject_status, SUBJECT_NO_RELIABLE_ANIMAL)
        self.assertEqual(gate_toy.detail_reason, "stuffed_toy_or_figurine")
        self.assertEqual(
            rank_pet_candidates_ai4a(qd_toy, self.catalog, explicit_species="dog", species_gate=gate_toy)["results"],
            [],
        )

        # Living room sofa natural non-animal
        qd_sofa, gate_sofa = self._eval_image((REAL_PACK_DIR / "real-neg-sofa-cal-03.jpg").read_bytes())
        self.assertEqual(gate_sofa.subject_status, SUBJECT_NO_RELIABLE_ANIMAL)
        self.assertEqual(
            rank_pet_candidates_ai4a(qd_sofa, self.catalog, explicit_species="cat", species_gate=gate_sofa)["results"],
            [],
        )

        # Multi-animal real photo (cat + dog cuddling)
        qd_multi, gate_multi = self._eval_image((REAL_PACK_DIR / "real-multi-catdog-hold-01.jpg").read_bytes())
        self.assertEqual(gate_multi.subject_status, SUBJECT_MULTIPLE_ANIMALS)
        self.assertGreaterEqual(gate_multi.animal_count, 2)
        out_multi = rank_pet_candidates_ai4a(qd_multi, self.catalog, explicit_species=None, species_gate=gate_multi)
        self.assertEqual(out_multi["results"], [])
        self.assertEqual(out_multi["abstention_reason"], "multiple_animals_detected")

        # Other animal (sheep in pasture)
        qd_sheep, gate_sheep = self._eval_image((REAL_PACK_DIR / "real-other-sheep-hold-02.jpg").read_bytes())
        self.assertEqual(gate_sheep.subject_status, SUBJECT_OTHER_ANIMAL)
        out_sheep = rank_pet_candidates_ai4a(qd_sheep, self.catalog, explicit_species="cat", species_gate=gate_sheep)
        self.assertEqual(out_sheep["results"], [])
        self.assertEqual(out_sheep["abstention_reason"], "unsupported_other_animal")

    def test_ambiguous_and_heavily_blurred_images_abstain_safely(self):
        # Silhouetted cat on rocks (stage disagreement -> ambiguous_subject)
        qd_amb, gate_amb = self._eval_image((REAL_PACK_DIR / "real-cat-other-cal-04.jpg").read_bytes())
        self.assertEqual(gate_amb.subject_status, SUBJECT_AMBIGUOUS)
        out_amb = rank_pet_candidates_ai4a(qd_amb, self.catalog, explicit_species=None, species_gate=gate_amb)
        self.assertEqual(out_amb["results"], [])
        self.assertEqual(out_amb["abstention_reason"], "ambiguous_subject")

        # Severely blurred photo -> abstains
        blurred = make_degraded_variant_bytes(
            (REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes(),
            "gaussian_blur_r16",
        )
        qd_deg, gate_deg = self._eval_image(blurred)
        out_deg = rank_pet_candidates_ai4a(qd_deg, self.catalog, explicit_species=None, species_gate=gate_deg)
        self.assertEqual(out_deg["results"], [])
        self.assertEqual(out_deg["match_outcome"], MATCH_OUTCOME_NONE)

    def test_case_d_verified_cat_with_no_similar_shop_cats_returns_empty(self):
        black_cats_only = [c for c in self.catalog if c["code"] in {"PET-136", "PET-148"}]
        qd, gate = self._eval_image((REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes())
        self.assertEqual(gate.verified_species, "cat")
        out = rank_pet_candidates_ai4a(qd, black_cats_only, explicit_species=None, species_gate=gate)
        self.assertEqual(out["verified_species"], "cat")
        self.assertEqual(out["results"], [])
        self.assertEqual(out["abstention_reason"], "below_similarity_threshold")

    def test_manifest_v2_integrity_and_split_disjointness(self):
        m2 = build_ai4b_manifest_v2()
        self.assertEqual(m2["schema_version"], 2)
        self.assertEqual(m2["counts"]["real_photographs_total"], 34)
        cal_real = {r["sample_id"] for r in m2["real_photographs"] if r["split"] == "calibration"}
        hold_real = {r["sample_id"] for r in m2["real_photographs"] if r["split"] == "acceptance_holdout"}
        self.assertEqual(cal_real & hold_real, set())
        self.assertEqual(len(cal_real), 17)
        self.assertEqual(len(hold_real), 17)


if __name__ == "__main__":
    unittest.main()
