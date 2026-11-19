"""Unit tests for AI-4.0a precision-first pet image matching and evaluation manifest."""

from __future__ import annotations

from pathlib import Path
import unittest

from petcare.database.seed import DEMO_PET_IMAGES, PETS
from petcare.services.pet_image_service import (
    MATCH_OUTCOME_NONE,
    MATCH_TIER_EXACT,
    MATCH_TIER_NEAR_DUP,
    MATCH_TIER_SIMILAR,
    rank_pet_candidates_ai4a,
)
from petcare.vision.ai4_benchmark import (
    build_ai4a_manifest,
     generate_procedural_negative_bytes,
    make_near_duplicate_variant,
    run_ai4a_evaluation,
)
from petcare.vision.image_features import (
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.species_taxonomy import (
    canonicalize_species,
    coat_groups_compatible,
    sql_species_aliases,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"


def _build_pet_row(pet_id: int, tuple_row: tuple) -> dict:
    code, name, species, breed, _sex, _bdate, _wt, coat, eyes, tags, price = tuple_row
    asset = DEMO_PET_IMAGES[code]
    raw_bytes = (DEMO_PETS_DIR / asset).read_bytes()
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


class AI4ImageMatchingUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected_codes = {
            "PET-001",  # Miu - orange cream cat (classic AI-3.4 rank-inversion failure)
            "PET-002",  # Nori - brown tabby cat
            "PET-133",  # Mèo xám xanh
            "PET-134",  # Mèo trắng
            "PET-135",  # Gừng - orange tabby cat
            "PET-142",  # Mật Ong - orange cream cat
            "PET-148",  # Đêm - black cat
            "PET-157",  # Cam - orange white cat (used for absent-from-DB tests)
            "PET-161",  # Mèo trắng xám
            "PET-101",  # Golden Retriever dog (vàng kem)
            "PET-105",  # Pomeranian dog (cam vàng)
            "PET-111",  # Corgi dog (vàng trắng - AI-3.4 rank-inversion failure)
        }
        cls.catalog_all = [
            _build_pet_row(idx, p)
            for idx, p in enumerate(PETS, start=1)
            if p[0] in selected_codes
        ]
        cls.by_code = {r["code"]: r for r in cls.catalog_all}

    @staticmethod
    def _query_descriptor(raw_bytes: bytes):
        norm = normalize_image_bytes(raw_bytes)
        return describe_image(
            norm,
            raw_sha256=sha256_hex(raw_bytes),
            normalized_sha256=sha256_hex(norm),
        )

    def test_species_canonicalization_and_sql_aliases(self):
        for cat_label in ("Mèo", "mèo", "Mèo con", "cat", "Cats", "feline", "kitten"):
            self.assertEqual(canonicalize_species(cat_label), "cat")
        for dog_label in ("Chó", "chó", "cún con", "dog", "Dogs", "canine", "puppy"):
            self.assertEqual(canonicalize_species(dog_label), "dog")
        self.assertEqual(canonicalize_species("Thỏ"), "rabbit")
        self.assertEqual(canonicalize_species("Hamster"), "hamster")
        self.assertEqual(canonicalize_species("Rùa cạn"), "other:rua can")
        self.assertIsNone(canonicalize_species(""))
        self.assertIsNone(canonicalize_species("   "))
        self.assertIsNone(canonicalize_species(None))
        self.assertEqual(len(sql_species_aliases("Mèo")), 7)
        self.assertIn("cat", sql_species_aliases("Mèo"))
        self.assertIn("Chó", sql_species_aliases("dog"))

    def test_exact_sha256_match_ranks_first_despite_metadata_inversion(self):
        for code in ("PET-001", "PET-111"):
            q_desc = self._query_descriptor(self.by_code[code]["_raw_bytes"])
            outcome = rank_pet_candidates_ai4a(q_desc, self.catalog_all)
            self.assertEqual(outcome["match_outcome"], MATCH_TIER_EXACT)
            self.assertGreaterEqual(len(outcome["results"]), 1)
            top = outcome["results"][0]
            self.assertEqual(top["pet"]["code"], code)
            self.assertEqual(top["score"], 100)
            self.assertEqual(top["match_tier"], MATCH_TIER_EXACT)

    def test_reencoded_jpeg_matches_normalized_sha256_as_exact(self):
        reencoded = normalize_image_bytes(self.by_code["PET-135"]["_raw_bytes"])
        self.assertNotEqual(sha256_hex(reencoded), sha256_hex(self.by_code["PET-135"]["_raw_bytes"]))
        q_desc = self._query_descriptor(reencoded)
        outcome = rank_pet_candidates_ai4a(q_desc, self.catalog_all)
        self.assertEqual(outcome["results"][0]["pet"]["code"], "PET-135")
        self.assertEqual(outcome["results"][0]["match_tier"], MATCH_TIER_EXACT)

    def test_resized_q70_copy_triggers_near_duplicate_with_zero_false_positives(self):
        resized = make_near_duplicate_variant(self.by_code["PET-134"]["_raw_bytes"], "near_dup_resize_480_q70")
        q_desc = self._query_descriptor(resized)
        outcome = rank_pet_candidates_ai4a(q_desc, self.catalog_all)
        self.assertEqual(outcome["match_outcome"], MATCH_TIER_NEAR_DUP)
        self.assertEqual(outcome["results"][0]["pet"]["code"], "PET-134")
        self.assertEqual(outcome["results"][0]["match_tier"], MATCH_TIER_NEAR_DUP)
        # Distinct white-gray cat PET-161 must NEVER be claimed as near_duplicate_image
        nd_codes = [r["pet"]["code"] for r in outcome["results"] if r["match_tier"] == MATCH_TIER_NEAR_DUP]
        self.assertEqual(nd_codes, ["PET-134"])

    def test_hard_species_filtering_blocks_cat_dog_cross_contamination(self):
        cat_out = rank_pet_candidates_ai4a(
            self._query_descriptor(self.by_code["PET-135"]["_raw_bytes"]),
            self.catalog_all,
        )
        self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "cat" for r in cat_out["results"]))

        dog_out = rank_pet_candidates_ai4a(
            self._query_descriptor(self.by_code["PET-105"]["_raw_bytes"]),
            self.catalog_all,
        )
        self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "dog" for r in dog_out["results"]))

    def test_absent_pet_abstains_unfiltered_and_never_claims_identity_when_filtered(self):
        catalog_without_157 = [r for r in self.catalog_all if r["code"] != "PET-157"]
        q_desc = self._query_descriptor(self.by_code["PET-157"]["_raw_bytes"])

        unfiltered = rank_pet_candidates_ai4a(q_desc, catalog_without_157, explicit_species=None)
        self.assertEqual(unfiltered["results"], [])
        self.assertEqual(unfiltered["match_outcome"], MATCH_OUTCOME_NONE)
        self.assertEqual(unfiltered["abstention_reason"], "species_unverified")

        cat_filtered = rank_pet_candidates_ai4a(q_desc, catalog_without_157, explicit_species="cat")
        self.assertGreaterEqual(len(cat_filtered["results"]), 1)
        for item in cat_filtered["results"]:
            self.assertEqual(canonicalize_species(item["pet"]["species"]), "cat")
            self.assertEqual(item["match_tier"], MATCH_TIER_SIMILAR)
            self.assertLessEqual(item["score"], 89)
            self.assertTrue(
                coat_groups_compatible(
                    q_desc.subject_coat_profile,
                    item["pet"]["coat_color"],
                    item["pet"]["appearance_tags"],
                )
            )

    def test_non_animal_invoice_and_solid_orange_graphic_are_rejected(self):
        invoice_bytes = (ROOT / "docs" / "assets" / "phase62" / "classroom-invoice.png").read_bytes()
        solid_orange = generate_procedural_negative_bytes("solid_warm_orange")
        for neg_bytes in (invoice_bytes, solid_orange):
            q_desc = self._query_descriptor(neg_bytes)
            for sp in (None, "cat", "dog"):
                out = rank_pet_candidates_ai4a(q_desc, self.catalog_all, explicit_species=sp)
                self.assertEqual(out["results"], [])
                self.assertEqual(out["match_outcome"], MATCH_OUTCOME_NONE)
                self.assertEqual(out["abstention_reason"], "non_photographic_or_low_texture")

    def test_manifest_splits_are_disjoint_and_multi_view_marked_not_evaluated(self):
        manifest = build_ai4a_manifest()
        cal = {s["pet_code"] for s in manifest["pet_samples"] if s["split"] == "calibration"}
        hold = {s["pet_code"] for s in manifest["pet_samples"] if s["split"] == "acceptance_holdout"}
        self.assertEqual(cal & hold, set())
        self.assertEqual(len(cal) + len(hold), 68)

        # Quick check of unevaluated_capabilities contract without running full 68-pet loop twice
        mini_manifest = dict(manifest)
        mini_manifest["pet_samples"] = manifest["pet_samples"][:6]
        mini_manifest["negative_samples"] = manifest["negative_samples"][:2]
        report = run_ai4a_evaluation(mini_manifest)
        by_cap = {c["capability"]: c["status"] for c in report["unevaluated_capabilities"]}
        self.assertEqual(by_cap["same_pet_multi_view_reidentification"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()

