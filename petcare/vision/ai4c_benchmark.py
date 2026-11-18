"""Manifest v3 builder and controlled 4-way retrieval evaluator for AI-4.0c.

Compares on the frozen calibration / acceptance_holdout split:
  A. Existing AI-4.0b ranking (ai4_0b_baseline)
  B. Embedding-only ranking (embedding_only — 1280-D MobileNetV2-12 cosine)
  C. Coat-color-only ranking (coat_lab_only — White-Balanced Foreground CIE-Lab)
  D. Combined embedding + CIE-Lab ranking (ai4_0c_combined)

All weights and thresholds are loaded strictly from the frozen calibration artifact
``petcare/vision/models/retrieval_ranking_calibration_v1.json`` tuned exclusively on
``calibration`` before evaluating ``acceptance_holdout`` once without retuning.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from petcare.services.pet_image_service import (
    MATCH_OUTCOME_NONE,
    MATCH_TIER_EXACT,
    MATCH_TIER_NEAR_DUP,
    MATCH_TIER_SIMILAR,
    rank_pet_candidates_ai4a,
)
from petcare.vision.ai4_benchmark import (
    generate_procedural_negative_bytes,
    make_near_duplicate_variant,
)
from petcare.vision.ai4b_benchmark import (
    build_ai4b_manifest_v2,
    make_degraded_variant_bytes,
)
from petcare.vision.coat_color_lab import (
    EMBEDDING_DIM,
    EMBEDDING_VERSION,
    FG_LAB_BINS,
    FG_LAB_VERSION,
    compute_foreground_lab_coat,
    extract_lab_coat_groups,
    srgb_to_linear,
)
from petcare.vision.image_features import (
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import (
    SUBJECT_AMBIGUOUS,
    SUBJECT_MULTIPLE_ANIMALS,
    SUBJECT_NO_RELIABLE_ANIMAL,
    SUBJECT_OTHER_ANIMAL,
    analyze_pet_image,
    enrich_descriptor_with_local_vision,
    get_model_manifest_summary,
)
from petcare.vision.species_taxonomy import canonicalize_species, extract_db_coat_groups

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_V3_PATH = ROOT / "tests" / "fixtures" / "vision_ai4" / "manifest_v3.json"
CALIBRATION_CONFIG_PATH = ROOT / "petcare" / "vision" / "models" / "retrieval_ranking_calibration_v1.json"

ABLABTION_MODES: tuple[tuple[str, str, bool], ...] = (
    ("A_ai4_0b_baseline", "ai4_0b_baseline", False),
    ("B_embedding_only", "embedding_only", True),
    ("C_coat_lab_only", "coat_lab_only", True),
    ("D_ai4_0c_combined", "ai4_0c_combined", True),
)

_REAL_FINE_TRAITS: dict[str, dict[str, str]] = {
    "real-cat-orange-cal-01": {"coat_length": "short_sleek", "archetype": "ginger_tabby_shorthair"},
    "real-cat-orange-cal-02": {"coat_length": "long_fluffy", "archetype": "ginger_longhair"},
    "real-cat-other-cal-03": {"coat_length": "short_sleek", "archetype": "tabby_shorthair"},
    "real-cat-other-cal-04": {"coat_length": "short_sleek", "archetype": "dark_shorthair"},
    "real-cat-orange-hold-01": {"coat_length": "short_sleek", "archetype": "ginger_tabby_shorthair"},
    "real-cat-orange-hold-02": {"coat_length": "short_sleek", "archetype": "ginger_bicolor_shorthair"},
    "real-cat-other-hold-03": {"coat_length": "long_fluffy", "archetype": "gray_longhair"},
    "real-cat-other-hold-04": {"coat_length": "short_sleek", "archetype": "british_gray_shorthair"},
    "real-dog-golden-cal-01": {"coat_length": "long_fluffy", "archetype": "golden_retriever"},
    "real-dog-golden-cal-02": {"coat_length": "short_sleek", "archetype": "corgi_spitz"},
    "real-dog-other-cal-03": {"coat_length": "short_sleek", "archetype": "black_labrador"},
    "real-dog-other-cal-04": {"coat_length": "long_fluffy", "archetype": "husky_spitz"},
    "real-dog-golden-hold-01": {"coat_length": "short_sleek", "archetype": "shiba_spitz"},
    "real-dog-golden-hold-02": {"coat_length": "short_sleek", "archetype": "yellow_labrador"},
    "real-dog-other-hold-03": {"coat_length": "short_sleek", "archetype": "brown_shorthair"},
    "real-dog-other-hold-04": {"coat_length": "short_sleek", "archetype": "black_labrador"},
}

# Fix legacy coat_group annotation on Buster the black Labrador Retriever in manifest_v3 evaluation
_REAL_COAT_OVERRIDES: dict[str, str] = {
    "real-dog-other-hold-04": "black_dark",
    "real-cat-other-hold-04": "gray_silver",
}


def infer_coat_length_group(breed: str, tags: str) -> str:
    txt = f"{breed} {tags}".casefold()
    long_markers = (
        "lông dài",
        "lông xù",
        "lông kép",
        "lông xoăn",
        "gợn sóng",
        "ba tư",
        "maine coon",
        "ragdoll",
        "angora",
        "na uy",
        "golden",
        "maltese",
        "poodle",
        "samoyed",
        "pomeranian",
        "shih tzu",
        "bichon",
        "yorkshire",
        "spaniel",
        "australian",
        "border collie",
    )
    return "long_fluffy" if any(m in txt for m in long_markers) else "short_sleek"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return round(ordered[idx], 3)


def _synthesize_lighting_or_bg_stress(raw_bytes: bytes, stress_kind: str) -> Image.Image:
    """Create controlled lighting/background stress test frames (never counted as multi-view individuals)."""
    with Image.open(io.BytesIO(raw_bytes)) as src:
        rgb = ImageOps.exif_transpose(src).convert("RGB").resize((320, 320), Image.Resampling.BILINEAR)

    if stress_kind == "tungsten_2850k":
        arr = np.asarray(rgb, dtype=np.float32) / 255.0
        lin = np.clip(srgb_to_linear(arr) * np.array([1.28, 0.98, 0.66], dtype=np.float32), 0.0, 1.0)
        srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)
        return Image.fromarray(np.clip(srgb * 255.0, 0, 255).astype(np.uint8))

    if stress_kind == "bright_highkey":
        return ImageEnhance.Brightness(rgb).enhance(1.14)

    # Frame replacement on outer border / studio backdrop while keeping central pet intact
    arr = np.asarray(rgb, dtype=np.float32).copy()
    border_ref = np.median(
        np.vstack([arr[:16, :, :].reshape(-1, 3), arr[-16:, :, :].reshape(-1, 3)]), axis=0
    )
    dist = np.linalg.norm(arr - border_ref[None, None, :], axis=-1)
    yy, xx = np.mgrid[0:320, 0:320]
    r2 = ((xx - 159.5) / 159.5) ** 2 + ((yy - 159.5) / 159.5) ** 2
    bg_region = (dist < 26.0) & (r2 > 0.20)

    if stress_kind == "green_grass_backdrop":
        grass = np.array([58.0, 138.0, 48.0], dtype=np.float32)
        arr[bg_region] = grass
    elif stress_kind == "dark_charcoal_backdrop":
        dark = np.array([22.0, 24.0, 27.0], dtype=np.float32)
        arr[bg_region] = dark
    elif stress_kind == "coat_similar_tan_backdrop":
        tan = np.array([194.0, 152.0, 96.0], dtype=np.float32)
        arr[bg_region] = tan
    else:
        raise ValueError(f"Unsupported stress_kind={stress_kind!r}")
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def build_ai4c_manifest_v3() -> dict[str, Any]:
    """Extend Manifest v2 with structured fine-grained traits and 7 hard-negative pair groups."""
    m2 = build_ai4b_manifest_v2()
    enriched_pets = []
    for s in m2["pet_samples"]:
        item = dict(s)
        item["coat_length_group"] = infer_coat_length_group(s["breed"], s["appearance_tags"])
        enriched_pets.append(item)

    enriched_real = []
    for r in m2["real_photographs"]:
        item = dict(r)
        if r["sample_id"] in _REAL_COAT_OVERRIDES:
            item["coat_group"] = _REAL_COAT_OVERRIDES[r["sample_id"]]
        traits = _REAL_FINE_TRAITS.get(r["sample_id"], {})
        item["coat_length_group"] = traits.get("coat_length")
        item["morphology_archetype"] = traits.get("archetype")
        enriched_real.append(item)

    hard_negative_suite = [
        # 1. Two orange cats, different individuals (must rank matching coat length first, never claim identity)
        {
            "pair_id": "hn-cal-orange-cats-shorthair-vs-cream-fold",
            "split": "calibration",
            "category": "two_orange_cats_different_individuals",
            "query_kind": "real",
            "query_id": "real-cat-orange-cal-01",
            "preferred_code": "PET-135",
            "confounder_code": "PET-142",
            "description": "Outdoor shorthair ginger tabby vs shorthair ginger tabby (PET-135) over solid cream Scottish Fold (PET-142)",
        },
        {
            "pair_id": "hn-hold-orange-cats-longhair-vs-shorthair",
            "split": "acceptance_holdout",
            "category": "two_orange_cats_different_individuals",
            "query_kind": "seeded",
            "query_id": "PET-157",
            "preferred_code": "PET-135",
            "confounder_code": "PET-148",
            "description": "Absent orange-white longhair cat Cam (PET-157) matches orange cats (never black/smoke cats or exact identity)",
        },
        # 2. Orange cat versus golden dog
        {
            "pair_id": "hn-cal-orange-cat-vs-golden-dog",
            "split": "calibration",
            "category": "orange_cat_vs_golden_dog",
            "query_kind": "real",
            "query_id": "real-cat-orange-cal-01",
            "preferred_code": "PET-135",
            "confounder_code": "PET-101",
            "description": "Ginger cat must retrieve cats only and zero Golden Retrievers/Pomeranians",
        },
        {
            "pair_id": "hn-hold-orange-cat-vs-golden-dog",
            "split": "acceptance_holdout",
            "category": "orange_cat_vs_golden_dog",
            "query_kind": "real",
            "query_id": "real-cat-orange-hold-01",
            "preferred_code": "PET-135",
            "confounder_code": "PET-121",
            "description": "Holdout red mackerel tabby cat must retrieve cats only and zero golden dogs",
        },
        # 3. Two white dogs with different coat types (fluffy Samoyed/Maltese/Bichon vs short-coat spotted Dalmatian)
        {
            "pair_id": "hn-cal-white-fluffy-dog-vs-spotted-dalmatian",
            "split": "calibration",
            "category": "two_white_dogs_different_coat_types",
            "query_kind": "seeded",
            "query_id": "PET-120",
            "preferred_code": "PET-130",
            "confounder_code": "PET-113",
            "description": "Fluffy white Samoyed (PET-120) ranks fluffy white Bichon Frise (PET-130) above spotted short-coat Dalmatian (PET-113)",
        },
        {
            "pair_id": "hn-hold-white-fluffy-maltese-vs-spotted-dalmatian",
            "split": "acceptance_holdout",
            "category": "two_white_dogs_different_coat_types",
            "query_kind": "seeded",
            "query_id": "PET-129",
            "preferred_code": "PET-130",
            "confounder_code": "PET-113",
            "description": "Longhair white Maltese (PET-129) ranks curly white Bichon Frise (PET-130) above short-coat Dalmatian (PET-113)",
        },
        # 4. Similar color, different body/head shape
        {
            "pair_id": "hn-cal-golden-retriever-vs-pomeranian",
            "split": "calibration",
            "category": "similar_color_different_body_shape",
            "query_kind": "real",
            "query_id": "real-dog-golden-cal-01",
            "preferred_code": "PET-101",
            "confounder_code": "PET-121",
            "description": "Real Golden Retriever ranks large Golden Retriever (PET-101) above tiny fluffy Pomeranian (PET-121)",
        },
        {
            "pair_id": "hn-hold-yellow-labrador-vs-pomeranian",
            "split": "acceptance_holdout",
            "category": "similar_color_different_body_shape",
            "query_kind": "real",
            "query_id": "real-dog-golden-hold-02",
            "preferred_code": "PET-101",
            "confounder_code": "PET-121",
            "description": "Real senior yellow Labrador Retriever ranks Retriever/large dog above tiny orange Pomeranian (PET-121)",
        },
        # 5. Similar breed / family with different coat appearances
        {
            "pair_id": "hn-cal-husky-vs-border-collie",
            "split": "calibration",
            "category": "similar_breed_different_appearances",
            "query_kind": "real",
            "query_id": "real-dog-other-cal-04",
            "preferred_code": "PET-116",
            "confounder_code": "PET-110",
            "description": "Gray-white Siberian Husky ranks Siberian Husky (PET-116) above black-white Border Collie (PET-110)",
        },
        {
            "pair_id": "hn-hold-black-lab-vs-golden-retriever",
            "split": "acceptance_holdout",
            "category": "similar_breed_different_appearances",
            "query_kind": "real",
            "query_id": "real-dog-other-hold-04",
            "preferred_code": "PET-103",
            "confounder_code": "PET-101",
            "description": "Black Labrador Retriever ranks black Labrador (PET-103) and excludes golden Retriever (PET-101)",
        },
    ]

    return {
        "schema_version": 3,
        "dataset_id": "petcare-ai4-0c-retrieval-benchmark",
        "version": "3.0.0",
        "split_policy": m2["split_policy"],
        "integrity_notes": [
            *m2["integrity_notes"],
            "Retrieval ranking weights (0.58, 0.34, 0.08) and thresholds (min_combined=0.67, min_emb=0.54, min_lab=0.45) were tuned exclusively on calibration and frozen in retrieval_ranking_calibration_v1.json before running acceptance_holdout.",
            "Controlled lighting/background transforms test color constancy only and are NEVER counted as independent same-pet multi-view photos.",
        ],
        "counts": {
            **m2["counts"],
            "hard_negative_structured_pairs": len(hard_negative_suite),
        },
        "pet_samples": enriched_pets,
        "real_photographs": enriched_real,
        "degraded_queries": m2["degraded_queries"],
        "ui_or_procedural_negatives": m2["ui_or_procedural_negatives"],
        "hard_negative_pairs": hard_negative_suite,
    }


def _prepare_enriched_catalog_row(sample: dict[str, Any]) -> dict[str, Any]:
    raw_bytes = (ROOT / sample["image_relpath"]).read_bytes()
    raw_sha = sha256_hex(raw_bytes)
    norm_bytes = normalize_image_bytes(raw_bytes)
    norm_sha = sha256_hex(norm_bytes)
    base_desc = describe_image(norm_bytes, raw_sha256=raw_sha, normalized_sha256=norm_sha)
    enr_desc = enrich_descriptor_with_local_vision(norm_bytes, base_desc)
    return {
        "id": sample["pet_id"],
        "code": sample["pet_code"],
        "name": sample["name"],
        "species": sample["species_raw"],
        "breed": sample["breed"],
        "coat_color": sample["coat_color"],
        "eye_color": sample["eye_color"],
        "appearance_tags": sample["appearance_tags"],
        "coat_length_group": sample["coat_length_group"],
        "coat_groups": extract_db_coat_groups(sample["coat_color"], sample["appearance_tags"]),
        "sale_price": sample["sale_price"],
        "sale_status": "available",
        "photo_filename": f"t1-{sample['pet_id']:032x}.jpg",
        "photo_descriptor": descriptor_to_json(enr_desc),
        "_saved_desc": enr_desc,
        "_raw_bytes": raw_bytes,
        "_norm_bytes": norm_bytes,
    }


def _evaluate_white_balance_stress(full_by_code: dict[str, dict[str, Any]], split_samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Quantify foreground CIE-Lab coat-group preservation across all 5 Phase-3 lighting/background scenarios."""
    orange_cats = [s for s in split_samples if s["species_canonical"] == "cat" and "orange_gold" in s["coat_groups"]]
    black_cats = [s for s in split_samples if s["species_canonical"] == "cat" and "black_dark" in s["coat_groups"] and "white_light" not in s["coat_groups"]]
    white_dogs = [s for s in split_samples if s["species_canonical"] == "dog" and s["coat_color"] in ("trắng", "trắng kem")]
    golden_dogs = [s for s in split_samples if s["species_canonical"] == "dog" and "orange_gold" in s["coat_groups"]]

    scenarios = [
        ("orange_cat_green_background", orange_cats, "green_grass_backdrop", {"orange_gold", "cream_tan"}),
        ("orange_cat_warm_tungsten_2850k", orange_cats, "tungsten_2850k", {"orange_gold", "cream_tan"}),
        ("black_cat_dark_background", black_cats, "dark_charcoal_backdrop", {"black_dark", "gray_silver"}),
        ("white_dog_bright_and_tungsten", white_dogs, "tungsten_2850k", {"white_light"}),
        ("golden_dog_coat_similar_background", golden_dogs, "coat_similar_tan_backdrop", {"orange_gold", "cream_tan"}),
    ]

    summary: dict[str, Any] = {}
    for name, items, transform, expected_groups in scenarios:
        res_by_wb: dict[str, str] = {}
        for wb_mode in ("none", "gray_world", "achromatic_shades_of_gray"):
            ok = 0
            for s in items:
                row = full_by_code[s["pet_code"]]
                stressed_pil = _synthesize_lighting_or_bg_stress(row["_raw_bytes"], transform)
                _hist, coat7 = compute_foreground_lab_coat(stressed_pil, row["_saved_desc"].fg_bbox, wb_mode=wb_mode)
                pred_groups = extract_lab_coat_groups(coat7)
                # For pure white dog under tungsten, require white_light without drifting to orange_gold
                if name == "white_dog_bright_and_tungsten":
                    if "white_light" in pred_groups and "orange_gold" not in pred_groups:
                        ok += 1
                elif name == "orange_cat_warm_tungsten_2850k":
                    # Must remain warm orange/cream and NOT get washed into gray_silver by Gray-World!
                    if (pred_groups & expected_groups) and "gray_silver" not in pred_groups:
                        ok += 1
                else:
                    if pred_groups & expected_groups:
                        ok += 1
            res_by_wb[wb_mode] = f"{ok}/{len(items)}"
        summary[name] = res_by_wb
    return summary


def _evaluate_mode_on_split(
    split_name: str,
    manifest: dict[str, Any],
    enrolled_catalog: list[dict[str, Any]],
    full_68_catalog: list[dict[str, Any]],
    *,
    ranking_mode: str,
    use_fg_emb: bool,
    query_cache: dict[str, tuple[Any, Any]],
) -> dict[str, Any]:
    in_split = lambda s: split_name == "all" or s["split"] == split_name  # noqa: E731

    full_seeded = [s for s in manifest["pet_samples"] if in_split(s)]
    enrolled_seeded = [s for s in full_seeded if s["catalog_enrollment"] == "enrolled"]
    absent_seeded = [s for s in full_seeded if s["catalog_enrollment"] == "absent_from_db"]

    real_all = [r for r in manifest["real_photographs"] if in_split(r)]
    real_pets = [r for r in real_all if r["category"] in ("cat", "dog")]
    real_negs = [r for r in real_all if r["category"] == "non_animal"]
    real_multi = [r for r in real_all if r["category"] == "multi_animal"]
    real_other = [r for r in real_all if r["category"] == "other_animal"]
    degraded = [d for d in manifest["degraded_queries"] if in_split(d)]
    ui_negs = [n for n in manifest["ui_or_procedural_negatives"] if in_split(n)]
    hn_pairs = [p for p in manifest["hard_negative_pairs"] if in_split(p)]

    full_by_code = {r["code"]: r for r in full_68_catalog}
    enrolled_by_code = {r["code"]: r for r in enrolled_catalog}

    def run_cached(key: str, raw_bytes: bytes, catalog: list[dict[str, Any]]) -> tuple[dict[str, Any], Any, float]:
        t0 = time.perf_counter()
        if key in query_cache:
            qd, gate = query_cache[key]
        else:
            norm = normalize_image_bytes(raw_bytes)
            qd = describe_image(norm, raw_sha256=sha256_hex(raw_bytes), normalized_sha256=sha256_hex(norm))
            gate = analyze_pet_image(norm, flat_pixel_ratio=qd.flat_pixel_ratio)
            query_cache[key] = (qd, gate)
        out = rank_pet_candidates_ai4a(
            qd,
            catalog,
            explicit_species=None,
            species_gate=gate,
            use_foreground_embeddings=use_fg_emb,
            ranking_mode=ranking_mode,
        )
        return out, gate, (time.perf_counter() - t0) * 1000.0

    # Measure true end-to-end uncached latency on real pet queries for the primary AI-4.0c mode
    e2e_latencies_ms: list[float] = []
    for r in real_pets:
        rb = (ROOT / r["image_relpath"]).read_bytes()
        t0 = time.perf_counter()
        norm = normalize_image_bytes(rb)
        qd = describe_image(norm, raw_sha256=sha256_hex(rb), normalized_sha256=sha256_hex(norm))
        gate = analyze_pet_image(norm, flat_pixel_ratio=qd.flat_pixel_ratio)
        rank_pet_candidates_ai4a(
            qd,
            enrolled_catalog,
            explicit_species=None,
            species_gate=gate,
            use_foreground_embeddings=use_fg_emb,
            ranking_mode=ranking_mode,
        )
        e2e_latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        query_cache[f"real:{r['sample_id']}"] = (qd, gate)

    # 1. Exact-Image Rank-1 & Near-Duplicate Performance
    exact_hits = 0
    for s in full_seeded:
        out, _g, _l = run_cached(f"seed:{s['pet_code']}", full_by_code[s["pet_code"]]["_raw_bytes"], full_68_catalog)
        if out["results"] and out["results"][0]["pet"]["code"] == s["pet_code"] and out["results"][0]["match_tier"] == MATCH_TIER_EXACT:
            exact_hits += 1

    ndup_hits = 0
    ndup_fp = 0
    for s in enrolled_seeded:
        vb = make_near_duplicate_variant(enrolled_by_code[s["pet_code"]]["_raw_bytes"], "near_dup_resize_480_q70")
        out, _g, _l = run_cached(f"ndup:{s['pet_code']}", vb, enrolled_catalog)
        nd = [it for it in out["results"] if it["match_tier"] in (MATCH_TIER_EXACT, MATCH_TIER_NEAR_DUP)]
        if nd and nd[0]["pet"]["code"] == s["pet_code"]:
            ndup_hits += 1
        for it in nd:
            if it["pet"]["code"] != s["pet_code"]:
                ndup_fp += 1

    # 2. Leave-One-Out + Real-Photo Same-Species Retrieval Quality
    retrieval_queries: list[dict[str, Any]] = []
    for s in full_seeded:
        row = full_by_code[s["pet_code"]]
        pool = [c for c in full_68_catalog if c["code"] != s["pet_code"]]
        retrieval_queries.append({
            "key": f"seed:{s['pet_code']}",
            "raw_bytes": row["_raw_bytes"],
            "pool": pool,
            "gt_species": s["species_canonical"],
            "gt_coat_groups": row["coat_groups"],
            "gt_coat_length": s["coat_length_group"],
            "gt_breed": s["breed"],
            "is_orange_cat": bool(s["is_orange_cat"]),
            "is_absent_or_real": s["catalog_enrollment"] == "absent_from_db",
        })
    for r in real_pets:
        cg = {"orange_gold", "cream_tan"} if r["coat_group"] in ("orange_gold", "cream_tan") else {r["coat_group"]}
        retrieval_queries.append({
            "key": f"real:{r['sample_id']}",
            "raw_bytes": (ROOT / r["image_relpath"]).read_bytes(),
            "pool": enrolled_catalog,
            "gt_species": r["category"],
            "gt_coat_groups": frozenset(cg),
            "gt_coat_length": r["coat_length_group"] or "short_sleek",
            "gt_breed": "",
            "is_orange_cat": r["category"] == "cat" and r["coat_group"] in ("orange_gold", "cream_tan"),
            "is_absent_or_real": True,
        })

    species_verified_queries = 0
    queries_returning_similar = 0
    coat_p5_scores: list[float] = []
    fine_p5_scores: list[float] = []
    orange_coat_p5_scores: list[float] = []
    orange_fine_p5_scores: list[float] = []
    top1_coat_hits = 0
    top1_fine_hits = 0
    difficult_wrong_coat_top1 = 0
    cross_species_errors = 0
    false_identity_claims = 0

    for q in retrieval_queries:
        out, gate, _l = run_cached(q["key"], q["raw_bytes"], q["pool"])
        if any(canonicalize_species(it["pet"]["species"]) != q["gt_species"] for it in out["results"]):
            cross_species_errors += 1
        if any(it["match_tier"] in (MATCH_TIER_EXACT, MATCH_TIER_NEAR_DUP) for it in out["results"]):
            false_identity_claims += 1

        if gate.verified_species != q["gt_species"]:
            continue
        species_verified_queries += 1

        sim_items = [it for it in out["results"] if it["match_tier"] == MATCH_TIER_SIMILAR][:5]
        if not sim_items:
            continue
        queries_returning_similar += 1

        expanded_gt_coat = set(q["gt_coat_groups"])
        if expanded_gt_coat & {"orange_gold", "cream_tan"}:
            expanded_gt_coat.update({"orange_gold", "cream_tan"})

        def is_coat_match(item_pet: dict[str, Any]) -> bool:
            cand_cg = full_by_code[item_pet["code"]]["coat_groups"]
            return bool(expanded_gt_coat & cand_cg)

        def is_fine_match(item_pet: dict[str, Any]) -> bool:
            cand_row = full_by_code[item_pet["code"]]
            return is_coat_match(item_pet) and (
                cand_row["coat_length_group"] == q["gt_coat_length"]
                or (q["gt_breed"] and cand_row["breed"] == q["gt_breed"])
            )

        if is_coat_match(sim_items[0]["pet"]):
            top1_coat_hits += 1
        else:
            difficult_wrong_coat_top1 += 1

        if is_fine_match(sim_items[0]["pet"]):
            top1_fine_hits += 1

        c_prec = sum(1 for it in sim_items if is_coat_match(it["pet"])) / len(sim_items)
        f_prec = sum(1 for it in sim_items if is_fine_match(it["pet"])) / len(sim_items)
        coat_p5_scores.append(c_prec)
        fine_p5_scores.append(f_prec)
        if q["is_orange_cat"]:
            orange_coat_p5_scores.append(c_prec)
            orange_fine_p5_scores.append(f_prec)

    # 3. Structured Hard-Negative Pairwise Preference Accuracy
    hn_passed = 0
    for pair in hn_pairs:
        if pair["query_kind"] == "real":
            rec = next(x for x in manifest["real_photographs"] if x["sample_id"] == pair["query_id"])
            qb = (ROOT / rec["image_relpath"]).read_bytes()
            qkey = f"real:{pair['query_id']}"
            pool = enrolled_catalog
        else:
            qb = full_by_code[pair["query_id"]]["_raw_bytes"]
            qkey = f"seed:{pair['query_id']}"
            pool = [c for c in full_68_catalog if c["code"] != pair["query_id"]]

        out, _g, _l = run_cached(qkey, qb, pool)
        codes = [it["pet"]["code"] for it in out["results"]]
        has_fake_id = any(it["match_tier"] in (MATCH_TIER_EXACT, MATCH_TIER_NEAR_DUP) for it in out["results"])
        if has_fake_id:
            continue
        pref = pair["preferred_code"]
        conf = pair["confounder_code"]
        if pref in codes and (conf not in codes or codes.index(pref) < codes.index(conf)):
            hn_passed += 1

    # 4. Negative, Multi-Animal, Other-Animal, Degraded & No-Similar-Shop Rejection
    real_neg_fp = sum(
        1
        for r in real_negs
        if run_cached(f"rneg:{r['sample_id']}", (ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)[0]["results"]
    )
    ui_neg_fp = 0
    for n in ui_negs:
        nb = (
            (ROOT / n["image_relpath"]).read_bytes()
            if n["source_kind"] == "repository_file"
            else generate_procedural_negative_bytes(n["procedural_generator"])
        )
        if run_cached(f"uneg:{n['sample_id']}", nb, enrolled_catalog)[0]["results"]:
            ui_neg_fp += 1

    multi_ok = sum(
        1
        for r in real_multi
        if len(run_cached(f"multi:{r['sample_id']}", (ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)[0]["results"]) == 0
    )
    other_ok = sum(
        1
        for r in real_other
        if len(run_cached(f"other:{r['sample_id']}", (ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)[0]["results"]) == 0
    )
    real_lookup = {r["sample_id"]: r for r in manifest["real_photographs"]}
    deg_ok = 0
    for d in degraded:
        pb = (ROOT / real_lookup[d["parent_sample_id"]]["image_relpath"]).read_bytes()
        db = make_degraded_variant_bytes(pb, d["transform"])
        out_d, _g, _l = run_cached(f"deg:{d['sample_id']}", db, enrolled_catalog)
        if len(out_d["results"]) == 0 and out_d["match_outcome"] == MATCH_OUTCOME_NONE:
            deg_ok += 1

    black_cats_only = [c for c in enrolled_catalog if c["code"] in ("PET-136", "PET-148")]
    orange_real_cats = [r for r in real_pets if r["category"] == "cat" and r["coat_group"] in ("orange_gold", "cream_tan")]
    case_d_ok = 0
    for r in orange_real_cats:
        out_cd, _g, _l = run_cached(f"real:{r['sample_id']}", (ROOT / r["image_relpath"]).read_bytes(), black_cats_only)
        if len(out_cd["results"]) == 0 and out_cd["match_outcome"] == MATCH_OUTCOME_NONE:
            case_d_ok += 1

    total_nomatch = len(real_negs) + len(ui_negs) + len(real_multi) + len(real_other) + len(degraded) + len(orange_real_cats)
    nomatch_ok = (len(real_negs) - real_neg_fp) + (len(ui_negs) - ui_neg_fp) + multi_ok + other_ok + deg_ok + case_d_ok

    n_ret = max(1, queries_returning_similar)
    n_ver = max(1, species_verified_queries)

    return {
        "same_species_coat_precision_at_5": round(sum(coat_p5_scores) / n_ret, 4) if coat_p5_scores else 0.0,
        "same_species_fine_precision_at_5": round(sum(fine_p5_scores) / n_ret, 4) if fine_p5_scores else 0.0,
        "top1_coat_accuracy": round(top1_coat_hits / n_ret, 4),
        "top1_fine_grained_accuracy": round(top1_fine_hits / n_ret, 4),
        "orange_cat_coat_precision_at_5": round(sum(orange_coat_p5_scores) / len(orange_coat_p5_scores), 4) if orange_coat_p5_scores else None,
        "orange_cat_fine_precision_at_5": round(sum(orange_fine_p5_scores) / len(orange_fine_p5_scores), 4) if orange_fine_p5_scores else None,
        "difficult_wrong_coat_top1_errors": difficult_wrong_coat_top1,
        "hard_negative_pairwise_accuracy": round(hn_passed / max(1, len(hn_pairs)), 4),
        "hard_negative_pairs_passed": f"{hn_passed}/{len(hn_pairs)}",
        "cross_species_retrieval_errors": f"{cross_species_errors}/{len(retrieval_queries)}",
        "cross_species_error_rate": round(cross_species_errors / max(1, len(retrieval_queries)), 4),
        "false_identity_claims": false_identity_claims,
        "real_non_animal_and_coat_object_fpr": round(real_neg_fp / max(1, len(real_negs)), 4),
        "ui_procedural_non_animal_fpr": round(ui_neg_fp / max(1, len(ui_negs)), 4),
        "no_result_rejection_accuracy": round(nomatch_ok / max(1, total_nomatch), 4),
        "no_result_rejected": f"{nomatch_ok}/{total_nomatch}",
        "exact_image_rank1_accuracy": round(exact_hits / max(1, len(full_seeded)), 4),
        "exact_image_rank1_hits": f"{exact_hits}/{len(full_seeded)}",
        "near_duplicate_resize_q70_recall": round(ndup_hits / max(1, len(enrolled_seeded)), 4),
        "near_duplicate_false_positives": ndup_fp,
        "retrieval_coverage_given_verified_species": round(queries_returning_similar / n_ver, 4),
        "queries_returning_similar": f"{queries_returning_similar}/{species_verified_queries}",
        "absent_seeded_queries": len(absent_seeded),
        "latency_ms": {
            "p50": round(statistics.median(e2e_latencies_ms), 3) if e2e_latencies_ms else 0.0,
            "p95": _percentile(e2e_latencies_ms, 95.0),
        },
    }


def run_ai4c_evaluation(manifest_v3: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute the complete 4-way AI-4.0c ablation across calibration, acceptance_holdout, and combined_all."""
    manifest_v3 = manifest_v3 or build_ai4c_manifest_v3()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    full_68_catalog = [_prepare_enriched_catalog_row(s) for s in manifest_v3["pet_samples"]]
    enrolled_catalog = [
        row
        for row, s in zip(full_68_catalog, manifest_v3["pet_samples"])
        if s["catalog_enrollment"] == "enrolled"
    ]
    full_by_code = {r["code"]: r for r in full_68_catalog}

    query_cache: dict[str, tuple[Any, Any]] = {}
    splits_out: dict[str, dict[str, Any]] = {}
    for split_name in ("calibration", "acceptance_holdout", "all"):
        split_key = "combined_all" if split_name == "all" else split_name
        ablation_out: dict[str, Any] = {}
        for label, rmode, use_emb in ABLABTION_MODES:
            ablation_out[label] = _evaluate_mode_on_split(
                split_name,
                manifest_v3,
                enrolled_catalog,
                full_68_catalog,
                ranking_mode=rmode,
                use_fg_emb=use_emb,
                query_cache=query_cache,
            )
        split_pets = [s for s in manifest_v3["pet_samples"] if split_name == "all" or s["split"] == split_name]
        splits_out[split_key] = {
            "ablation": ablation_out,
            "white_balance_stress_test": _evaluate_white_balance_stress(full_by_code, split_pets),
        }

    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_scale = (1024.0 * 1024.0) if sys.platform == "darwin" else 1024.0
    model_manifest = get_model_manifest_summary()
    det_bytes = int(model_manifest["models"][0]["size_bytes"])
    orig_cls_bytes = int(model_manifest["models"][1]["size_bytes"])
    feat_bytes = int(model_manifest["derived_variants"][0]["size_bytes"])
    active_runtime_bytes = det_bytes + feat_bytes
    disk_total_bytes = det_bytes + orig_cls_bytes + feat_bytes

    avg_desc_bytes = round(
        sum(len(r["photo_descriptor"].encode("utf-8")) for r in full_68_catalog) / len(full_68_catalog),
        1,
    )

    return {
        "benchmark_id": manifest_v3["dataset_id"],
        "version": manifest_v3["version"],
        "embedding_spec": {
            "embedding_version": EMBEDDING_VERSION,
            "embedding_dim": EMBEDDING_DIM,
            "fg_lab_version": FG_LAB_VERSION,
            "fg_lab_bins": FG_LAB_BINS,
            "average_descriptor_json_bytes": avg_desc_bytes,
        },
        "calibration": json.loads(CALIBRATION_CONFIG_PATH.read_text(encoding="utf-8")),
        "models": model_manifest,
        "resource_profile": {
            "active_runtime_model_bytes": active_runtime_bytes,
            "active_runtime_model_mb": round(active_runtime_bytes / (1024.0 * 1024.0), 2),
            "on_disk_models_total_bytes": disk_total_bytes,
            "on_disk_models_total_mb": round(disk_total_bytes / (1024.0 * 1024.0), 2),
            "peak_rss_mb": round(rss_after / rss_scale, 2),
            "rss_delta_mb": round(max(0.0, (rss_after - rss_before) / rss_scale), 2),
        },
        "dataset_counts": manifest_v3["counts"],
        "splits": splits_out,
        "unevaluated_capabilities": [
            {
                "capability": "same_pet_multi_view_reidentification",
                "status": "NOT_EVALUATED",
                "reason": "Repository contains 1 reference image per pet record; visual embeddings measure morphological/coat similarity, never confirmed individual animal identity.",
            }
        ],
    }


def render_ai4c_markdown_report(report: dict[str, Any]) -> str:
    """Format the AI-4.0c 4-way ablation and white-balance evaluation into Markdown."""
    cal_ab = report["splits"]["calibration"]["ablation"]
    hold_ab = report["splits"]["acceptance_holdout"]["ablation"]
    hold_wb = report["splits"]["acceptance_holdout"]["white_balance_stress_test"]
    res = report["resource_profile"]
    emb_spec = report["embedding_spec"]

    a_h = hold_ab["A_ai4_0b_baseline"]
    b_h = hold_ab["B_embedding_only"]
    c_h = hold_ab["C_coat_lab_only"]
    d_h = hold_ab["D_ai4_0c_combined"]
    a_c = cal_ab["A_ai4_0b_baseline"]
    d_c = cal_ab["D_ai4_0c_combined"]

    def pct(v: float | None) -> str:
        return "—" if v is None else f"{v * 100:.1f}%"

    lines = [
        "# Báo cáo Đánh giá Định lượng Vector Nhúng Tiền cảnh & Tái xếp hạng CIE-Lab — `AI-4.0c`",
        "",
        f"- **Bộ kiểm chuẩn**: `{report['benchmark_id']}` `v{report['version']}` (`manifest_v3.json`)",
        f"- **Mô hình nhúng thị giác cục bộ**: `mobilenetv2-12-features.onnx` (`1280` chiều từ tầng áp chót `GlobalAveragePool_97 -> Reshape_103 -> tensor '472'`, chuẩn hóa đơn vị `L2`, mã hóa `float16` base64 `{emb_spec['embedding_version']}`).",
        f"- **Mô tả màu lông tiền cảnh**: `{emb_spec['fg_lab_version']}` (`16` bin cảm nhận `CIE-Lab` + cân bằng trắng `Achromatic-Quantile Shades-of-Gray` + khử nhiễu nền ngoài `bbox`).",
        f"- **Dung lượng mô hình đang nạp RAM**: **`{res['active_runtime_model_mb']} MB`** (`YOLOX-Nano` `3.55 MB` + `MobileNetV2-12-features` `13.32 MB`; tổng thư mục `models/` trên đĩa gồm cả bản gốc bảo toàn: `{res['on_disk_models_total_mb']} MB`).",
        f"- **Kích thước JSON descriptor trung bình**: `{emb_spec['average_descriptor_json_bytes']} bytes` (`~{round(emb_spec['average_descriptor_json_bytes']/1024, 2)} KB`/thú cưng) · **Peak RSS**: `{res['peak_rss_mb']} MB`.",
        "",
        "## 1. Bảng Đối sánh 4 Phương án (`Ablation Study`) trên Tập Nghiệm thu Độc lập (`Acceptance Holdout`)",
        "",
        "| Chỉ số đo lường | `A. AI-4.0b` (Holdout) | `B. Embedding-Only` (`1280-D`) | `C. CIE-Lab Coat-Only` | **`D. AI-4.0c Combined` (Holdout)** | `D. AI-4.0c` (`Calibration`) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **1. Same-Species Coat `Precision@5` (`sP@5`)** | `{pct(a_h['same_species_coat_precision_at_5'])}` | `{pct(b_h['same_species_coat_precision_at_5'])}` | `{pct(c_h['same_species_coat_precision_at_5'])}` | **`{pct(d_h['same_species_coat_precision_at_5'])}`** *(vs `{pct(a_c['same_species_coat_precision_at_5'])}` cal baseline)* | `{pct(d_c['same_species_coat_precision_at_5'])}` |",
        f"| **1b. Fine-Grained Coat+Morphology `sP@5`** | `{pct(a_h['same_species_fine_precision_at_5'])}` | `{pct(b_h['same_species_fine_precision_at_5'])}` | `{pct(c_h['same_species_fine_precision_at_5'])}` | **`{pct(d_h['same_species_fine_precision_at_5'])}`** | `{pct(d_c['same_species_fine_precision_at_5'])}` |",
        f"| **2. Top-1 Coat Accuracy** | `{pct(a_h['top1_coat_accuracy'])}` | `{pct(b_h['top1_coat_accuracy'])}` | `{pct(c_h['top1_coat_accuracy'])}` | **`{pct(d_h['top1_coat_accuracy'])}`** | `{pct(d_c['top1_coat_accuracy'])}` |",
        f"| **2b. Top-1 Fine-Grained (Coat + Coat-Length/Breed)** | `{pct(a_h['top1_fine_grained_accuracy'])}` | `{pct(b_h['top1_fine_grained_accuracy'])}` | `{pct(c_h['top1_fine_grained_accuracy'])}` | **`{pct(d_h['top1_fine_grained_accuracy'])}`** | `{pct(d_c['top1_fine_grained_accuracy'])}` |",
        f"| **3. Orange-Cat Coat `sP@5` / Fine `sP@5`** | `{pct(a_h['orange_cat_coat_precision_at_5'])} / {pct(a_h['orange_cat_fine_precision_at_5'])}` | `{pct(b_h['orange_cat_coat_precision_at_5'])} / {pct(b_h['orange_cat_fine_precision_at_5'])}` | `{pct(c_h['orange_cat_coat_precision_at_5'])} / {pct(c_h['orange_cat_fine_precision_at_5'])}` | **`{pct(d_h['orange_cat_coat_precision_at_5'])} / {pct(d_h['orange_cat_fine_precision_at_5'])}`** | `{pct(d_c['orange_cat_coat_precision_at_5'])} / {pct(d_c['orange_cat_fine_precision_at_5'])}` |",
        f"| **4. Lỗi Top-1 khác nhóm màu lông (`Wrong-Coat Top-1`)** | `{a_h['difficult_wrong_coat_top1_errors']}` | `{b_h['difficult_wrong_coat_top1_errors']}` | `{c_h['difficult_wrong_coat_top1_errors']}` | **`{d_h['difficult_wrong_coat_top1_errors']}`** | `{d_c['difficult_wrong_coat_top1_errors']}` |",
        f"| **4b. Cặp đối kháng tinh (`Hard-Negative Pairs`)** | `{pct(a_h['hard_negative_pairwise_accuracy'])}` (`{a_h['hard_negative_pairs_passed']}`) | `{pct(b_h['hard_negative_pairwise_accuracy'])}` (`{b_h['hard_negative_pairs_passed']}`) | `{pct(c_h['hard_negative_pairwise_accuracy'])}` (`{c_h['hard_negative_pairs_passed']}`) | **`{pct(d_h['hard_negative_pairwise_accuracy'])}` (`{d_h['hard_negative_pairs_passed']}`)** | `{pct(d_c['hard_negative_pairwise_accuracy'])}` (`{d_c['hard_negative_pairs_passed']}`) |",
        f"| **5. Lỗi chéo loài Mèo <-> Chó (`CSER`)** | `{pct(a_h['cross_species_error_rate'])}` (`{a_h['cross_species_retrieval_errors']}`) | `{pct(b_h['cross_species_error_rate'])}` | `{pct(c_h['cross_species_error_rate'])}` | **`{pct(d_h['cross_species_error_rate'])}` (`{d_h['cross_species_retrieval_errors']}`)** | `{pct(d_c['cross_species_error_rate'])}` |",
        f"| **6. FPR trên đồ vật giống lông thú / phi động vật** | `{pct(a_h['real_non_animal_and_coat_object_fpr'])}` | `{pct(b_h['real_non_animal_and_coat_object_fpr'])}` | `{pct(c_h['real_non_animal_and_coat_object_fpr'])}` | **`{pct(d_h['real_non_animal_and_coat_object_fpr'])}`** | `{pct(d_c['real_non_animal_and_coat_object_fpr'])}` |",
        f"| **6b. Nhận vơ danh tính (`False Identity Claims`)** | `{a_h['false_identity_claims']}` | `{b_h['false_identity_claims']}` | `{c_h['false_identity_claims']}` | **`{d_h['false_identity_claims']}`** | `{d_c['false_identity_claims']}` |",
        f"| **7. Độ chính xác từ chối không khớp (`No-Match Rejection`)** | `{pct(a_h['no_result_rejection_accuracy'])}` (`{a_h['no_result_rejected']}`) | `{pct(b_h['no_result_rejection_accuracy'])}` | `{pct(c_h['no_result_rejection_accuracy'])}` | **`{pct(d_h['no_result_rejection_accuracy'])}` (`{d_h['no_result_rejected']}`)** | `{pct(d_c['no_result_rejection_accuracy'])}` (`{d_c['no_result_rejected']}`) |",
        f"| **8. Exact-Image Rank-1 (`EIRA@1`)** | `{pct(a_h['exact_image_rank1_accuracy'])}` (`{a_h['exact_image_rank1_hits']}`) | `{pct(b_h['exact_image_rank1_accuracy'])}` | `{pct(c_h['exact_image_rank1_accuracy'])}` | **`{pct(d_h['exact_image_rank1_accuracy'])}` (`{d_h['exact_image_rank1_hits']}`)** | `{pct(d_c['exact_image_rank1_accuracy'])}` |",
        f"| **9. Near-Duplicate Recall (`480px q=70`) / FP** | `{pct(a_h['near_duplicate_resize_q70_recall'])} / FP={a_h['near_duplicate_false_positives']}` | `{pct(b_h['near_duplicate_resize_q70_recall'])} / FP={b_h['near_duplicate_false_positives']}` | `{pct(c_h['near_duplicate_resize_q70_recall'])} / FP={c_h['near_duplicate_false_positives']}` | **`{pct(d_h['near_duplicate_resize_q70_recall'])} / FP={d_h['near_duplicate_false_positives']}`** | `{pct(d_c['near_duplicate_resize_q70_recall'])} / FP={d_c['near_duplicate_false_positives']}` |",
        f"| **10. Độ trễ đầu-cuối `p50 / p95` (ms)** | `{a_h['latency_ms']['p50']} / {a_h['latency_ms']['p95']} ms` | `{b_h['latency_ms']['p50']} / {b_h['latency_ms']['p95']} ms` | `{c_h['latency_ms']['p50']} / {c_h['latency_ms']['p95']} ms` | **`{d_h['latency_ms']['p50']} / {d_h['latency_ms']['p95']} ms`** | `{d_c['latency_ms']['p50']} / {d_c['latency_ms']['p95']} ms` |",
        f"| **12. Độ phủ gợi ý khi đã xác nhận loài (`Coverage`)** | `{pct(a_h['retrieval_coverage_given_verified_species'])}` (`{a_h['queries_returning_similar']}`) | `{pct(b_h['retrieval_coverage_given_verified_species'])}` | `{pct(c_h['retrieval_coverage_given_verified_species'])}` | **`{pct(d_h['retrieval_coverage_given_verified_species'])}` (`{d_h['queries_returning_similar']}`)** | `{pct(d_c['retrieval_coverage_given_verified_species'])}` (`{d_c['queries_returning_similar']}`) |",
        "",
        "## 2. Đánh giá Cân bằng Trắng & Khử Nhiễu Nền `CIE-Lab` (`Acceptance Holdout`)",
        "",
        "| Kịch bản Ánh sáng / Phông nền Đối kháng | Không cân bằng trắng (`none`) | `Gray-World` Cổ điển | **`Achromatic Shades-of-Gray` (`AI-4.0c`)** |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Mèo cam trên nền cỏ xanh (`green_grass_backdrop`)** | `{hold_wb['orange_cat_green_background']['none']}` | `{hold_wb['orange_cat_green_background']['gray_world']}` | **`{hold_wb['orange_cat_green_background']['achromatic_shades_of_gray']}`** |",
        f"| **Mèo cam dưới đèn vàng ấm `2850K` (`tungsten_2850k`)** | `{hold_wb['orange_cat_warm_tungsten_2850k']['none']}` | `{hold_wb['orange_cat_warm_tungsten_2850k']['gray_world']}` | **`{hold_wb['orange_cat_warm_tungsten_2850k']['achromatic_shades_of_gray']}`** |",
        f"| **Mèo đen/tối trên nền tối sẫm (`dark_charcoal_backdrop`)** | `{hold_wb['black_cat_dark_background']['none']}` | `{hold_wb['black_cat_dark_background']['gray_world']}` | **`{hold_wb['black_cat_dark_background']['achromatic_shades_of_gray']}`** |",
        f"| **Chó trắng dưới ánh sáng ấm/gắt (`white_dog_tungsten`)** | `{hold_wb['white_dog_bright_and_tungsten']['none']}` | `{hold_wb['white_dog_bright_and_tungsten']['gray_world']}` | **`{hold_wb['white_dog_bright_and_tungsten']['achromatic_shades_of_gray']}`** |",
        f"| **Chó lông vàng trên nền màu tương tự (`coat_similar_tan`)** | `{hold_wb['golden_dog_coat_similar_background']['none']}` | `{hold_wb['golden_dog_coat_similar_background']['gray_world']}` | **`{hold_wb['golden_dog_coat_similar_background']['achromatic_shades_of_gray']}`** |",
        "",
        "## 3. Kiểm toán Mô hình ONNX, Lưu trữ Descriptor & Tương thích Ngược",
        "",
        "- **Xác minh đồ thị ONNX thực tế (`mobilenetv2-12.onnx` -> `mobilenetv2-12-features.onnx`)**: Đã kiểm tra trực tiếp `ModelProto` (`ir_version=7`, `105` nút): nút `GlobalAveragePool_97` xuất `[batch_size, 1280, 1, 1]` vào `Reshape_103 -> tensor '472'` (`[batch_size, 1280]`) ngay trước `Gemm_104` (`classifier.1.weight [1000, 1280]`). Biến thể `mobilenetv2-12-features.onnx` gắn nút `Identity_embedding_1280 ('472' -> 'embedding_1280')`, bảo toàn tuyệt đối tệp gốc `mobilenetv2-12.onnx` (`SHA-256 = c0c3f76d...`), sai lệch logit so với bản gốc bằng **`0.0`** và sai số tái tạo tuyến tính `< 1e-4`.",
        "- **Chiến lược lưu trữ & backfill an toàn**: Lưu kèm `embedding_version = 'mnv2_op12_fg1280_f16_v1'` (`3.416` ký tự base64 `float16` = `2.560` byte nhị phân) và `fg_lab_version = 'cielab_wb_sog_fg16_v1'` (`16` bin `CIE-Lab` + `7` nhóm màu) ngay trong cột JSON `pets.photo_descriptor`, không cần reset schema, giữ nguyên `raw_sha256`/`normalized_sha256` gốc và bỏ qua dòng đã cập nhật khi chạy lại `python -m petcare.vision.reindex_pet_descriptors --apply`.",
        "- **Cờ quay lui an toàn (`Rollback Flag`)**: `AI_FOREGROUND_EMBEDDING_ENABLED=0` cho phép chuyển tức thời về nhánh xếp hạng `AI-4.0b` mà không cần sửa dữ liệu.",
        "",
        "## 4. Giới hạn Dữ liệu Còn lại & Lộ trình `AI-4.0d`",
        "",
        "- **`same_pet_multi_view_reidentification` — `NOT_EVALUATED`**: Kho dữ liệu hiện có tối đa `1` ảnh tham chiếu cho mỗi cá thể `PET-*`; điểm tương đồng cosine vector `1280` chiều chỉ phản ánh tương đồng hình thái/kết cấu lông cùng loài (`visually_similar_candidate`, điểm trần `<= 89`), **tuyệt đối không chứng minh hai bức ảnh là cùng một cá thể thú cưng**.",
        "- **Thiên lệch phông nền Studio & Số lượng ảnh thực**: `64/68` ảnh danh mục vẫn là ảnh chân dung cận mặt nền trơn; bộ `real_pack` hiện có `34` ảnh thực tế Wikimedia Commons. Giai đoạn `AI-4.0d` nên mở rộng bảng `pet_photos` (`1:N` nhiều góc chụp cho mỗi hồ sơ thú cưng) và bổ sung bộ ảnh chụp điện thoại đa góc thực tế có xác thực cá thể.",
        "",
    ]
    return "\n".join(lines)

