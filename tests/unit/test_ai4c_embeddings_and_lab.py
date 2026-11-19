"""Unit tests for AI-4.0c 1280-D penultimate visual embeddings, white-balanced CIE-Lab, storage, and ranking."""

from __future__ import annotations

from contextlib import nullcontext
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageOps
from werkzeug.datastructures import FileStorage

from petcare.database.seed import DEMO_PET_IMAGES, PETS
from petcare.services.pet_image_service import (
    MATCH_OUTCOME_NONE,
    MATCH_TIER_EXACT,
    MATCH_TIER_SIMILAR,
    rank_pet_candidates_ai4c,
)
from petcare.vision import reindex_pet_descriptors as reindexer
from petcare.vision.ai4c_benchmark import (
    _synthesize_lighting_or_bg_stress,
    build_ai4c_manifest_v3,
)
from petcare.vision.coat_color_lab import (
    EMBEDDING_DIM,
    EMBEDDING_VERSION,
    FG_LAB_BINS,
    FG_LAB_VERSION,
    compare_lab_histograms,
    compute_foreground_lab_coat,
    decode_embedding_f16_b64,
    embedding_cosine_similarity,
    encode_embedding_f16_b64,
    extract_lab_coat_groups,
    l2_normalize_embedding,
)
from petcare.vision.image_features import (
    describe_image,
    descriptor_from_json,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import (
    MODELS_DIR,
    analyze_pet_image,
    enrich_descriptor_with_local_vision,
    get_model_manifest_summary,
)
from petcare.vision.photo_storage import store_pet_photo
from petcare.vision.species_taxonomy import canonicalize_species
from scripts.build_mobilenetv2_feature_extractor import (
    EXPECTED_BASE_SHA256,
    EXPOSED_EMBEDDING_NAME,
    build_feature_extractor_bytes,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"


def _build_enriched_pet_row(pet_id: int, tuple_row: tuple) -> dict:
    code, name, species, breed, _sex, _bdate, _wt, coat, eyes, tags, price = tuple_row
    raw_bytes = (DEMO_PETS_DIR / DEMO_PET_IMAGES[code]).read_bytes()
    norm_bytes = normalize_image_bytes(raw_bytes)
    base_desc = describe_image(
        norm_bytes,
        raw_sha256=sha256_hex(raw_bytes),
        normalized_sha256=sha256_hex(norm_bytes),
    )
    enr_desc = enrich_descriptor_with_local_vision(norm_bytes, base_desc)
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
        "photo_descriptor": descriptor_to_json(enr_desc),
        "_saved_desc": enr_desc,
        "_raw_bytes": raw_bytes,
    }


class AI4CEmbeddingsAndLabUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        codes = {
            "PET-001",  # Miu - orange cream shorthair cat
            "PET-135",  # Gừng - ginger tabby shorthair cat
            "PET-142",  # Nếp - cream Scottish Fold cat
            "PET-148",  # Mây Xám - black/smoke longhair cat
            "PET-136",  # Tux - black/white tuxedo cat
            "PET-138",  # Bạch Tuyết - white Persian cat
            "PET-149",  # Bạch Kim - white Turkish Angora cat
            "PET-003",  # Mây - calico cat
            "PET-101",  # Sunny - Golden Retriever
            "PET-121",  # Bánh Bao - orange Pomeranian
            "PET-128",  # Lulu - honey Cocker Spaniel
            "PET-103",  # Gấu Mun - black Labrador Retriever
            "PET-116",  # Bão - Siberian Husky
            "PET-110",  # Còi - black/white Border Collie
            "PET-129",  # Mây Con - white Maltese
            "PET-130",  # Mim - white Bichon Frise
            "PET-113",  # Chấm - white/black spotted Dalmatian
        }
        cls.catalog = [
            _build_enriched_pet_row(idx, p)
            for idx, p in enumerate(PETS, start=1)
            if p[0] in codes
        ]
        cls.by_code = {r["code"]: r for r in cls.catalog}

    @staticmethod
    def _eval_query(raw_bytes: bytes):
        norm = normalize_image_bytes(raw_bytes)
        qd = describe_image(
            norm,
            raw_sha256=sha256_hex(raw_bytes),
            normalized_sha256=sha256_hex(norm),
        )
        gate = analyze_pet_image(norm, flat_pixel_ratio=qd.flat_pixel_ratio)
        return qd, gate

    def test_onnx_feature_extractor_variant_preserves_base_model_and_exposes_1280d_penultimate(self):
        base_path = MODELS_DIR / "mobilenetv2-12.onnx"
        variant_path = MODELS_DIR / "mobilenetv2-12-features.onnx"
        self.assertTrue(base_path.is_file())
        self.assertTrue(variant_path.is_file())
        base_bytes = base_path.read_bytes()
        self.assertEqual(sha256_hex(base_bytes), EXPECTED_BASE_SHA256)

        manifest = get_model_manifest_summary()
        self.assertIn("derived_variants", manifest)
        var_meta = manifest["derived_variants"][0]
        self.assertEqual(var_meta["embedding_dim"], EMBEDDING_DIM)
        self.assertEqual(var_meta["outputs"][1]["name"], EXPOSED_EMBEDDING_NAME)
        self.assertEqual(sha256_hex(variant_path.read_bytes()), var_meta["sha256"])

        # Rebuilding from upstream bytes is 100% deterministic byte-for-byte
        rebuilt_bytes, audit = build_feature_extractor_bytes(base_bytes)
        self.assertEqual(sha256_hex(rebuilt_bytes), var_meta["sha256"])
        self.assertEqual(audit["verification"]["max_abs_logit_diff_vs_original"], 0.0)
        self.assertLess(audit["verification"]["max_abs_gemm_reconstruction_error"], 1e-4)

    def test_embedding_codec_l2_normalization_and_corruption_handling(self):
        rng = np.random.default_rng(123)
        raw = np.abs(rng.standard_normal(EMBEDDING_DIM, dtype=np.float32)) + 0.1
        unit = l2_normalize_embedding(raw)
        self.assertIsNotNone(unit)
        self.assertAlmostEqual(float(np.linalg.norm(unit)), 1.0, places=5)

        b64 = encode_embedding_f16_b64(unit)
        decoded = decode_embedding_f16_b64(b64)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.shape, (EMBEDDING_DIM,))
        self.assertAlmostEqual(float(np.linalg.norm(decoded)), 1.0, places=5)
        self.assertGreater(embedding_cosine_similarity(unit, decoded), 0.9999)

        # Outdated version, zero vector, NaN, and truncated base64 all safely return None
        self.assertIsNone(decode_embedding_f16_b64(b64, actual_version="legacy_v0"))
        self.assertIsNone(decode_embedding_f16_b64(b64[:100]))
        self.assertIsNone(decode_embedding_f16_b64("!" * len(b64)))
        self.assertIsNone(l2_normalize_embedding(np.zeros(EMBEDDING_DIM, dtype=np.float32)))
        bad_nan = raw.copy()
        bad_nan[5] = np.nan
        self.assertIsNone(l2_normalize_embedding(bad_nan))

    def test_foreground_cie_lab_and_white_balance_across_five_lighting_and_background_scenarios(self):
        # 1 & 2: Orange cat on green grass backdrop & under 2850K warm indoor tungsten
        ginger_raw = self.by_code["PET-135"]["_raw_bytes"]
        bbox_135 = self.by_code["PET-135"]["_saved_desc"].fg_bbox
        green_bg_cat = _synthesize_lighting_or_bg_stress(ginger_raw, "green_grass_backdrop")
        tungsten_cat = _synthesize_lighting_or_bg_stress(ginger_raw, "tungsten_2850k")

        h_green, c7_green = compute_foreground_lab_coat(green_bg_cat, bbox_135)
        h_tung, c7_tung = compute_foreground_lab_coat(tungsten_cat, bbox_135)
        self.assertEqual(len(h_green), FG_LAB_BINS)
        self.assertIn("orange_gold", extract_lab_coat_groups(c7_green))
        self.assertIn("orange_gold", extract_lab_coat_groups(c7_tung))
        self.assertNotIn("gray_silver", extract_lab_coat_groups(c7_tung))
        self.assertGreater(compare_lab_histograms(h_green, self.by_code["PET-135"]["_saved_desc"].fg_lab_histogram), 0.75)

        # 3: Black cat against dark charcoal background
        dark_cat = _synthesize_lighting_or_bg_stress(
            self.by_code["PET-148"]["_raw_bytes"], "dark_charcoal_backdrop"
        )
        _h_dark, c7_dark = compute_foreground_lab_coat(
            dark_cat, self.by_code["PET-148"]["_saved_desc"].fg_bbox
        )
        self.assertTrue(extract_lab_coat_groups(c7_dark) & {"black_dark", "gray_silver"})

        # 4: White Samoyed dog in bright high-key AND 2850K warm tungsten (must stay white_light, not orange!)
        samoyed_raw = (DEMO_PETS_DIR / "demo-dog-20.png").read_bytes()
        with Image.open(io.BytesIO(normalize_image_bytes(samoyed_raw))) as im:
            samoyed_rgb = ImageOps.exif_transpose(im).convert("RGB")
        bright_dog = _synthesize_lighting_or_bg_stress(samoyed_raw, "bright_highkey")
        tungsten_dog = _synthesize_lighting_or_bg_stress(samoyed_raw, "tungsten_2850k")
        for variant_im in (samoyed_rgb, bright_dog, tungsten_dog):
            _hd, c7_dog = compute_foreground_lab_coat(variant_im)
            groups = extract_lab_coat_groups(c7_dog)
            self.assertIn("white_light", groups)
            self.assertNotIn("orange_gold", groups)

        # 5: Real Golden Retriever on coat-similar golden-brown autumn leaves
        real_golden_bytes = (REAL_PACK_DIR / "real-dog-golden-cal-01.jpg").read_bytes()
        _qd_g, gate_g = self._eval_query(real_golden_bytes)
        self.assertIn("orange_gold", extract_lab_coat_groups(gate_g.foreground_lab_coat_profile))

    def test_store_pet_photo_and_reindex_backfill_preserve_hashes_and_version_descriptors(self):
        raw_png = (DEMO_PETS_DIR / "demo-cat-03.png").read_bytes()
        expected_raw_sha = sha256_hex(raw_png)

        with tempfile.TemporaryDirectory() as tmpdir:
            stored = store_pet_photo(
                FileStorage(stream=io.BytesIO(raw_png), filename="ginger.png"),
                tmpdir,
                5 * 1024 * 1024,
                tenant_id=1,
            )
            self.assertEqual(stored.descriptor.raw_sha256, expected_raw_sha)
            self.assertEqual(stored.descriptor.embedding_version, EMBEDDING_VERSION)
            self.assertEqual(stored.descriptor.fg_lab_version, FG_LAB_VERSION)
            self.assertIsNotNone(decode_embedding_f16_b64(stored.descriptor.embedding_b64))
            self.assertEqual(len(stored.descriptor.fg_lab_histogram), FG_LAB_BINS)

            # Simulate a legacy pre-AI-4.0c descriptor missing embedding_version while retaining raw_sha256
            legacy_dict = json.loads(stored.descriptor_json)
            legacy_dict.pop("embedding_version", None)
            legacy_dict.pop("embedding_b64", None)
            legacy_dict.pop("fg_lab_version", None)
            legacy_dict.pop("fg_lab_histogram", None)
            legacy_json = json.dumps(legacy_dict)

            saved_jpeg_bytes = (Path(tmpdir) / stored.filename).read_bytes()
            storage = MagicMock()
            storage.read.return_value = saved_jpeg_bytes
            rows = [
                {
                    "id": 42,
                    "tenant_id": 1,
                    "photo_filename": stored.filename,
                    "photo_descriptor": legacy_json,
                }
            ]
            conn = MagicMock()
            conn.cursor.return_value.rowcount = 1
            conn.cursor.return_value.fetchall.return_value = [(42, 1, stored.descriptor_json)]

            with (
                patch.object(reindexer, "read_connection", side_effect=[nullcontext(object()), nullcontext(object())]),
                patch.object(reindexer, "fetch_all", side_effect=[rows, []]),
                patch.object(reindexer, "transaction", return_value=nullcontext(conn)),
                patch.object(reindexer.pet_repo, "replace_photo_search_indexes"),
            ):
                res = reindexer.reindex_pet_descriptors(apply=True, storage=storage)
            self.assertEqual(res, {"scanned": 1, "prepared": 1, "updated": 1, "skipped": 0})
            updated_json = conn.cursor.return_value.executemany.call_args.args[1][0][0]
            rebuilt = descriptor_from_json(updated_json)
            self.assertIsNotNone(rebuilt)
            self.assertEqual(rebuilt.raw_sha256, expected_raw_sha)
            self.assertEqual(rebuilt.embedding_version, EMBEDDING_VERSION)
            self.assertIsNotNone(decode_embedding_f16_b64(rebuilt.embedding_b64))

    def test_fine_grained_same_species_ranking_beats_ai40b_while_preserving_all_safety_gates(self):
        # 1. Real Golden Retriever -> AI-4.0c ranks Golden Retriever (PET-101) #1 ahead of Pomeranian (PET-121)!
        qd_gold, gate_gold = self._eval_query((REAL_PACK_DIR / "real-dog-golden-cal-01.jpg").read_bytes())
        out_4c_gold = rank_pet_candidates_ai4c(qd_gold, self.catalog, species_gate=gate_gold)
        self.assertEqual(out_4c_gold["results"][0]["pet"]["code"], "PET-101")
        self.assertEqual(out_4c_gold["results"][0]["match_tier"], MATCH_TIER_SIMILAR)
        self.assertLessEqual(out_4c_gold["results"][0]["score"], 89)
        self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "dog" for r in out_4c_gold["results"]))

        # 2. Fluffy white Samoyed (PET-120, absent from cls.catalog) -> ranks fluffy white Bichon/Maltese, NEVER spotted Dalmatian!
        qd_sam, gate_sam = self._eval_query((DEMO_PETS_DIR / "demo-dog-20.png").read_bytes())
        out_sam = rank_pet_candidates_ai4c(qd_sam, self.catalog, species_gate=gate_sam)
        sam_codes = [r["pet"]["code"] for r in out_sam["results"]]
        self.assertIn("PET-130", sam_codes[:2])
        self.assertNotIn("PET-113", sam_codes)  # Dalmatian excluded by solid-white CIE-Lab guard

        # 3. Real Siberian Husky -> ranks Siberian Husky (PET-116) #1 ahead of Border Collie (PET-110)!
        qd_husky, gate_husky = self._eval_query((REAL_PACK_DIR / "real-dog-other-cal-04.jpg").read_bytes())
        out_husky = rank_pet_candidates_ai4c(qd_husky, self.catalog, species_gate=gate_husky)
        self.assertEqual(out_husky["results"][0]["pet"]["code"], "PET-116")

        # 4. Real ginger tabby cat -> returns orange cats only, zero dogs, zero black/smoke cats, zero identity claims
        qd_cat, gate_cat = self._eval_query((REAL_PACK_DIR / "real-cat-orange-hold-01.jpg").read_bytes())
        out_cat = rank_pet_candidates_ai4c(qd_cat, self.catalog, species_gate=gate_cat)
        self.assertGreaterEqual(len(out_cat["results"]), 1)
        for item in out_cat["results"]:
            self.assertEqual(canonicalize_species(item["pet"]["species"]), "cat")
            self.assertEqual(item["match_tier"], MATCH_TIER_SIMILAR)
            self.assertNotIn(item["pet"]["code"], {"PET-136", "PET-148", "PET-138", "PET-149"})

        # 5. Tier-0 exact match priority and offline rollback flag preserved
        qd_ex, gate_ex = self._eval_query(self.by_code["PET-001"]["_raw_bytes"])
        out_ex = rank_pet_candidates_ai4c(qd_ex, self.catalog, species_gate=gate_ex)
        self.assertEqual(out_ex["results"][0]["pet"]["code"], "PET-001")
        self.assertEqual(out_ex["results"][0]["match_tier"], MATCH_TIER_EXACT)
        self.assertEqual(out_ex["results"][0]["score"], 100)

        fallback_out = rank_pet_candidates_ai4c(
            qd_gold, self.catalog, species_gate=gate_gold, use_foreground_embeddings=False
        )
        self.assertTrue(all(canonicalize_species(r["pet"]["species"]) == "dog" for r in fallback_out["results"]))

        # 6. Coat-resembling wool blanket & woven orange rug negatives remain 100% rejected
        for neg_name in ("real-neg-rug-cal-02.jpg", "real-neg-blanket-hold-02.jpg"):
            qd_n, gate_n = self._eval_query((REAL_PACK_DIR / neg_name).read_bytes())
            out_n = rank_pet_candidates_ai4c(qd_n, self.catalog, species_gate=gate_n)
            self.assertEqual(out_n["results"], [])
            self.assertEqual(out_n["match_outcome"], MATCH_OUTCOME_NONE)

    def test_manifest_v3_split_integrity(self):
        m3 = build_ai4c_manifest_v3()
        self.assertEqual(m3["schema_version"], 3)
        cal_codes = {s["pet_code"] for s in m3["pet_samples"] if s["split"] == "calibration"}
        hold_codes = {s["pet_code"] for s in m3["pet_samples"] if s["split"] == "acceptance_holdout"}
        self.assertEqual(cal_codes & hold_codes, set())


if __name__ == "__main__":
    unittest.main()

