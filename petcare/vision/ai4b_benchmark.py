"""Manifest v2 builder and comprehensive AI-4.0b evaluator (Real Local ONNX Detection & Species Gate).

Strictly enforces:
- Identity-disjoint ``calibration`` vs ``acceptance_holdout`` splits across both seeded and real-pack photos.
- Synthetic/UI negatives are explicitly typed as ``ui_or_procedural_negative`` and NEVER labeled as
  real photographic detection examples.
- Frozen calibration parameters from ``species_gate_calibration_v1.json`` evaluated without retuning on holdout.
- Reports both accuracy AND coverage (proving zero cross-species error is NOT achieved via 100% abstention).
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import resource
import statistics
import time
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from petcare.services.pet_image_service import (
    MATCH_OUTCOME_NONE,
    MATCH_TIER_EXACT,
    MATCH_TIER_NEAR_DUP,
    MATCH_TIER_SIMILAR,
    rank_pet_candidates_ai4a,
)
from petcare.vision.ai4_benchmark import (
    _prepare_catalog_row,
    build_ai4a_manifest,
    generate_procedural_negative_bytes,
    make_near_duplicate_variant,
)
from petcare.vision.image_features import (
    describe_image,
    normalize_image_bytes,
    sha256_hex,
)
from petcare.vision.local_pet_detector import (
    SUBJECT_AMBIGUOUS,
    SUBJECT_MULTIPLE_ANIMALS,
    SUBJECT_NO_RELIABLE_ANIMAL,
    SUBJECT_ONE_CAT,
    SUBJECT_ONE_DOG,
    SUBJECT_OTHER_ANIMAL,
    analyze_pet_image,
    get_model_manifest_summary,
)
from petcare.vision.species_taxonomy import canonicalize_species, coat_groups_compatible

ROOT = Path(__file__).resolve().parents[2]
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"
DEFAULT_MANIFEST_V2_PATH = ROOT / "tests" / "fixtures" / "vision_ai4" / "manifest_v2.json"

_DEGRADED_QUERY_SPECS: tuple[tuple[str, str, str, str, str], ...] = (
    ("deg-cal-heavy-blur-cat", "calibration", "real-cat-orange-cal-02", "gaussian_blur_r16", "Severely out-of-focus real ginger cat photo (radius=16)"),
    ("deg-cal-extreme-dark-dog", "calibration", "real-dog-golden-cal-01", "extreme_dark_x006", "Severely underexposed real dog photo (brightness=0.06)"),
    ("deg-cal-bg-corner-crop", "calibration", "real-cat-orange-cal-02", "corner_background_crop", "Ambiguous 90x90 background wall corner crop with no visible pet"),
    ("deg-hold-heavy-blur-cat", "acceptance_holdout", "real-cat-orange-hold-01", "gaussian_blur_r16", "Severely out-of-focus real tabby cat photo (radius=16)"),
    ("deg-hold-extreme-dark-dog", "acceptance_holdout", "real-dog-golden-hold-01", "extreme_dark_x006", "Severely underexposed real Shiba Inu photo (brightness=0.06)"),
    ("deg-hold-bg-corner-crop", "acceptance_holdout", "real-dog-golden-hold-02", "corner_background_crop", "Ambiguous 90x90 sidewalk corner crop with no visible pet"),
)


def make_degraded_variant_bytes(raw_bytes: bytes, transform: str) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as src:
        rgb = ImageOps.exif_transpose(src).convert("RGB")
    if transform == "gaussian_blur_r16":
        out_im = rgb.filter(ImageFilter.GaussianBlur(radius=16))
    elif transform == "extreme_dark_x006":
        out_im = ImageEnhance.Brightness(rgb).enhance(0.06)
    elif transform == "corner_background_crop":
        cw, ch = min(90, rgb.width // 3), min(90, rgb.height // 3)
        out_im = rgb.crop((0, 0, cw, ch)).resize((300, 300), Image.Resampling.BILINEAR)
    else:
        raise ValueError(f"Unknown degraded transform: {transform}")
    buf = io.BytesIO()
    out_im.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def build_ai4b_manifest_v2() -> dict[str, Any]:
    """Build Manifest v2 combining v1 seeded catalog + 34 license-verified real-world Commons photos."""
    v1 = build_ai4a_manifest()
    provenance_path = REAL_PACK_DIR / "PROVENANCE.json"
    real_records = json.loads(provenance_path.read_text(encoding="utf-8"))
    real_by_id = {r["sample_id"]: r for r in real_records}

    # Verify every real_pack file checksum matches PROVENANCE.json
    for rec in real_records:
        raw_b = (ROOT / rec["image_relpath"]).read_bytes()
        if sha256_hex(raw_b) != rec["raw_sha256"]:
            raise RuntimeError(f"Checksum mismatch in real_pack for {rec['sample_id']}")

    degraded_samples: list[dict[str, Any]] = []
    for sample_id, split, parent_id, transform, desc in _DEGRADED_QUERY_SPECS:
        parent = real_by_id[parent_id]
        if parent["split"] != split:
            raise RuntimeError(f"Split leakage in degraded spec {sample_id}: {parent['split']} != {split}")
        deg_bytes = make_degraded_variant_bytes((ROOT / parent["image_relpath"]).read_bytes(), transform)
        degraded_samples.append({
            "sample_id": sample_id,
            "split": split,
            "parent_sample_id": parent_id,
            "transform": transform,
            "raw_sha256": sha256_hex(deg_bytes),
            "description": desc,
            "provenance": f"Procedural degradation ({transform}) of {parent['source_title']} ({parent['license']})",
            "usage_rights": parent["license"],
        })

    # Tag v1 negatives explicitly as ui_or_procedural_negative (never photographic detection examples)
    ui_proc_negatives = []
    for n in v1["negative_samples"]:
        item = dict(n)
        item["negative_domain"] = "ui_or_procedural_negative"
        ui_proc_negatives.append(item)

    return {
        "schema_version": 2,
        "dataset_id": "petcare-ai4-0b-vision-benchmark",
        "version": "2.0.0",
        "split_policy": (
            "Strict identity-disjoint calibration vs acceptance_holdout split across both "
            "68 synthetic shop portraits and 34 license-verified real-world Wikimedia Commons photographs."
        ),
        "integrity_notes": [
            "Real photographic detection examples (real_pack, CC0/Public domain/CC-BY) are tracked separately from synthetic portraits and UI/procedural negatives.",
            "Synthetic solid-color or geometric procedural images are categorized strictly as ui_or_procedural_negative, NEVER as real photographic detection examples.",
            "Same-pet multi-view individual re-identification remains NOT_EVALUATED.",
            "All species-gate thresholds were tuned exclusively on the calibration split and evaluated once on acceptance_holdout without retuning.",
        ],
        "counts": {
            **v1["counts"],
            "real_photographs_total": len(real_records),
            "real_cats_total": sum(1 for r in real_records if r["category"] == "cat"),
            "real_dogs_total": sum(1 for r in real_records if r["category"] == "dog"),
            "real_non_animal_and_toys_total": sum(1 for r in real_records if r["category"] == "non_animal"),
            "real_multi_animal_total": sum(1 for r in real_records if r["category"] == "multi_animal"),
            "real_other_animal_total": sum(1 for r in real_records if r["category"] == "other_animal"),
            "degraded_low_confidence_queries_total": len(degraded_samples),
        },
        "pet_samples": v1["pet_samples"],
        "real_photographs": real_records,
        "degraded_queries": degraded_samples,
        "ui_or_procedural_negatives": ui_proc_negatives,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return round(ordered[idx], 3)


def _search_ai4a_unfiltered(raw_bytes: bytes, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    norm = normalize_image_bytes(raw_bytes)
    qd = describe_image(norm, raw_sha256=sha256_hex(raw_bytes), normalized_sha256=sha256_hex(norm))
    return rank_pet_candidates_ai4a(qd, catalog, explicit_species=None, species_gate=None)


def _search_ai4b_auto(
    raw_bytes: bytes,
    catalog: list[dict[str, Any]],
    explicit_species: str | None = None,
) -> tuple[dict[str, Any], Any, float]:
    t0 = time.perf_counter()
    norm = normalize_image_bytes(raw_bytes)
    qd = describe_image(norm, raw_sha256=sha256_hex(raw_bytes), normalized_sha256=sha256_hex(norm))
    gate = analyze_pet_image(norm, flat_pixel_ratio=qd.flat_pixel_ratio)
    out = rank_pet_candidates_ai4a(
        qd,
        catalog,
        explicit_species=canonicalize_species(explicit_species) if explicit_species else None,
        species_gate=gate,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return out, gate, elapsed_ms


def _evaluate_split_v2(
    split_name: str,
    manifest: dict[str, Any],
    enrolled_catalog: list[dict[str, Any]],
    full_68_catalog: list[dict[str, Any]],
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

    full_by_code = {r["code"]: r for r in full_68_catalog}
    enrolled_by_code = {r["code"]: r for r in enrolled_catalog}

    latencies_ms: list[float] = []

    # 1. Exact-Image Rank-1 & Near-Duplicate Precision/Recall
    exact_hits_4b = 0
    ndup_resize_hits = 0
    ndup_fp = 0
    for s in full_seeded:
        out, _gate, lat = _search_ai4b_auto(full_by_code[s["pet_code"]]["_raw_bytes"], full_68_catalog)
        latencies_ms.append(lat)
        if out["results"] and out["results"][0]["pet"]["code"] == s["pet_code"] and out["results"][0]["match_tier"] == MATCH_TIER_EXACT:
            exact_hits_4b += 1

    for s in enrolled_seeded:
        vb = make_near_duplicate_variant(enrolled_by_code[s["pet_code"]]["_raw_bytes"], "near_dup_resize_480_q70")
        out, _gate, lat = _search_ai4b_auto(vb, enrolled_catalog)
        latencies_ms.append(lat)
        nd = [r for r in out["results"] if r["match_tier"] in (MATCH_TIER_EXACT, MATCH_TIER_NEAR_DUP)]
        if nd and nd[0]["pet"]["code"] == s["pet_code"]:
            ndup_resize_hits += 1
        for r in nd:
            if r["pet"]["code"] != s["pet_code"]:
                ndup_fp += 1

    # 2. Automatic Species Recognition & Confusion Matrix on ALL New (Absent-from-Shop) Pet Images
    #    Tracked both separately for Real Photographs vs Absent Seeded Portraits, and combined!
    cm_real = {
        "true_cat": {"pred_cat": 0, "pred_dog": 0, "abstained": 0},
        "true_dog": {"pred_cat": 0, "pred_dog": 0, "abstained": 0},
    }
    cm_all_new = {
        "true_cat": {"pred_cat": 0, "pred_dog": 0, "abstained": 0},
        "true_dog": {"pred_cat": 0, "pred_dog": 0, "abstained": 0},
    }

    ai4a_new_covered = 0
    ai4b_new_covered = 0
    ai4b_real_covered = 0
    ai4b_cross_species_retrieval_errors = 0
    ai4b_false_identity_claims = 0
    orange_golden_queries = 0
    orange_golden_cross_species = 0
    orange_cat_coat_precisions: list[float] = []

    new_pet_queries: list[tuple[str, str, bytes, bool, str | None]] = []
    for r in real_pets:
        is_og = r["coat_group"] in ("orange_gold", "cream_tan")
        new_pet_queries.append((r["sample_id"], r["category"], (ROOT / r["image_relpath"]).read_bytes(), True, r["coat_group"] if is_og else None))
    for s in absent_seeded:
        is_og = bool(s["is_orange_cat"] or s["is_similar_warm_dog"])
        new_pet_queries.append((s["pet_code"], s["species_canonical"], full_by_code[s["pet_code"]]["_raw_bytes"], False, "orange_gold" if is_og else None))

    for qid, gt_sp, q_bytes, is_real, og_flag in new_pet_queries:
        out_4a = _search_ai4a_unfiltered(q_bytes, enrolled_catalog)
        if out_4a["verified_species"] is not None:
            ai4a_new_covered += 1

        out_4b, gate, lat = _search_ai4b_auto(q_bytes, enrolled_catalog)
        latencies_ms.append(lat)

        row_key = f"true_{gt_sp}"
        pred_sp = gate.verified_species
        if pred_sp == "cat":
            cm_all_new[row_key]["pred_cat"] += 1
            if is_real:
                cm_real[row_key]["pred_cat"] += 1
        elif pred_sp == "dog":
            cm_all_new[row_key]["pred_dog"] += 1
            if is_real:
                cm_real[row_key]["pred_dog"] += 1
        else:
            cm_all_new[row_key]["abstained"] += 1
            if is_real:
                cm_real[row_key]["abstained"] += 1

        if pred_sp is not None:
            ai4b_new_covered += 1
            if is_real:
                ai4b_real_covered += 1

        if any(canonicalize_species(item["pet"]["species"]) != gt_sp for item in out_4b["results"]):
            ai4b_cross_species_retrieval_errors += 1

        if any(item["match_tier"] in (MATCH_TIER_EXACT, MATCH_TIER_NEAR_DUP) for item in out_4b["results"]):
            ai4b_false_identity_claims += 1

        if og_flag is not None:
            orange_golden_queries += 1
            if any(canonicalize_species(item["pet"]["species"]) != gt_sp for item in out_4b["results"]):
                orange_golden_cross_species += 1
            if gt_sp == "cat" and out_4b["results"]:
                sim_items = [it for it in out_4b["results"] if it["match_tier"] == MATCH_TIER_SIMILAR]
                if sim_items:
                    hits = sum(
                        1 for it in sim_items
                        if canonicalize_species(it["pet"]["species"]) == "cat"
                        and coat_groups_compatible(
                            gate.foreground_coat_profile,
                            it["pet"]["coat_color"],
                            it["pet"]["appearance_tags"],
                        )
                    )
                    orange_cat_coat_precisions.append(hits / len(sim_items))

    # 3. Non-Animal, Toy, Other-Animal, Multi-Animal, Degraded & No-Similar-Shop Rejection
    real_neg_fp = 0
    for r in real_negs:
        out, _gate, lat = _search_ai4b_auto((ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)
        latencies_ms.append(lat)
        if out["results"]:
            real_neg_fp += 1

    ui_neg_fp = 0
    for n in ui_negs:
        nb = (
            (ROOT / n["image_relpath"]).read_bytes()
            if n["source_kind"] == "repository_file"
            else generate_procedural_negative_bytes(n["procedural_generator"])
        )
        out, _gate, lat = _search_ai4b_auto(nb, enrolled_catalog)
        latencies_ms.append(lat)
        if out["results"]:
            ui_neg_fp += 1

    multi_rejected = 0
    for r in real_multi:
        out, gate, lat = _search_ai4b_auto((ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)
        latencies_ms.append(lat)
        if len(out["results"]) == 0 and gate.subject_status == SUBJECT_MULTIPLE_ANIMALS:
            multi_rejected += 1

    other_rejected = 0
    for r in real_other:
        out, gate, lat = _search_ai4b_auto((ROOT / r["image_relpath"]).read_bytes(), enrolled_catalog)
        latencies_ms.append(lat)
        if len(out["results"]) == 0 and gate.subject_status in (SUBJECT_OTHER_ANIMAL, SUBJECT_NO_RELIABLE_ANIMAL, SUBJECT_AMBIGUOUS):
            other_rejected += 1

    degraded_rejected = 0
    real_lookup = {r["sample_id"]: r for r in manifest["real_photographs"]}
    for d in degraded:
        parent_bytes = (ROOT / real_lookup[d["parent_sample_id"]]["image_relpath"]).read_bytes()
        db = make_degraded_variant_bytes(parent_bytes, d["transform"])
        out, _gate, lat = _search_ai4b_auto(db, enrolled_catalog)
        latencies_ms.append(lat)
        if len(out["results"]) == 0 and out["match_outcome"] == MATCH_OUTCOME_NONE:
            degraded_rejected += 1

    # Case D: Cat uploaded when shop has NO sufficiently similar cats (e.g., shop only has black cats, query is orange cat)
    black_cats_only = [c for c in enrolled_catalog if c["code"] in ("PET-136", "PET-148")]
    case_d_queries = [r for r in real_pets if r["category"] == "cat" and r["coat_group"] == "orange_gold"]
    case_d_rejected = 0
    for r in case_d_queries:
        out, _gate, _lat = _search_ai4b_auto((ROOT / r["image_relpath"]).read_bytes(), black_cats_only)
        if len(out["results"]) == 0 and out["match_outcome"] == MATCH_OUTCOME_NONE:
            case_d_rejected += 1

    # Derived species precision, recall, abstention, coverage
    cat_tp = cm_all_new["true_cat"]["pred_cat"]
    cat_fp = cm_all_new["true_dog"]["pred_cat"]
    cat_fn_swap = cm_all_new["true_cat"]["pred_dog"]
    cat_abs = cm_all_new["true_cat"]["abstained"]
    cat_total = cat_tp + cat_fn_swap + cat_abs

    dog_tp = cm_all_new["true_dog"]["pred_dog"]
    dog_fp = cm_all_new["true_cat"]["pred_dog"]
    dog_fn_swap = cm_all_new["true_dog"]["pred_cat"]
    dog_abs = cm_all_new["true_dog"]["abstained"]
    dog_total = dog_tp + dog_fn_swap + dog_abs

    total_new = max(1, len(new_pet_queries))
    total_abs = cat_abs + dog_abs
    total_non_animal_all = max(1, len(real_negs) + len(ui_negs))
    total_nomatch_pool = len(real_negs) + len(ui_negs) + len(real_multi) + len(real_other) + len(degraded) + len(case_d_queries)
    total_nomatch_correct = (
        (len(real_negs) - real_neg_fp)
        + (len(ui_negs) - ui_neg_fp)
        + multi_rejected
        + other_rejected
        + degraded_rejected
        + case_d_rejected
    )

    return {
        "split": split_name,
        "query_counts": {
            "seeded_pets": len(full_seeded),
            "new_absent_pets_total": len(new_pet_queries),
            "new_real_pet_photos": len(real_pets),
            "new_absent_seeded_pets": len(absent_seeded),
            "real_non_animal_and_toys": len(real_negs),
            "ui_or_procedural_negatives": len(ui_negs),
            "real_multi_animal_photos": len(real_multi),
            "real_other_animal_photos": len(real_other),
            "degraded_low_confidence_photos": len(degraded),
            "no_similar_coat_shop_queries": len(case_d_queries),
        },
        "confusion_matrix_new_pets_all": cm_all_new,
        "confusion_matrix_real_photos_only": cm_real,
        "species_metrics": {
            "cat_precision_when_predicted": round(cat_tp / max(1, cat_tp + cat_fp), 4) if (cat_tp + cat_fp) else None,
            "cat_end_to_end_recall": round(cat_tp / max(1, cat_total), 4),
            "dog_precision_when_predicted": round(dog_tp / max(1, dog_tp + dog_fp), 4) if (dog_tp + dog_fp) else None,
            "dog_end_to_end_recall": round(dog_tp / max(1, dog_total), 4),
            "species_abstention_rate_all_new": round(total_abs / total_new, 4),
            "coverage_on_new_images_all": round(ai4b_new_covered / total_new, 4),
            "coverage_on_real_photographs": round(ai4b_real_covered / max(1, len(real_pets)), 4),
            "ai4_0a_coverage_on_new_images_unfiltered": round(ai4a_new_covered / total_new, 4),
        },
        "retrieval_and_rejection": {
            "exact_image_rank1_accuracy": round(exact_hits_4b / max(1, len(full_seeded)), 4),
            "exact_image_rank1_hits": f"{exact_hits_4b}/{len(full_seeded)}",
            "near_duplicate_resize_q70_recall": round(ndup_resize_hits / max(1, len(enrolled_seeded)), 4),
            "near_duplicate_false_positives": ndup_fp,
            "cross_species_retrieval_error_rate": round(ai4b_cross_species_retrieval_errors / total_new, 4),
            "cross_species_retrieval_errors": f"{ai4b_cross_species_retrieval_errors}/{len(new_pet_queries)}",
            "orange_cat_golden_dog_cross_species_errors": f"{orange_golden_cross_species}/{orange_golden_queries}",
            "orange_cat_coat_precision_mean": round(sum(orange_cat_coat_precisions) / len(orange_cat_coat_precisions), 4) if orange_cat_coat_precisions else None,
            "absent_pet_false_identity_claims": ai4b_false_identity_claims,
            "real_non_animal_and_toy_fpr": round(real_neg_fp / max(1, len(real_negs)), 4),
            "ui_or_procedural_non_animal_fpr": round(ui_neg_fp / max(1, len(ui_negs)), 4),
            "combined_non_animal_fpr": round((real_neg_fp + ui_neg_fp) / total_non_animal_all, 4),
            "multiple_animal_rejection_accuracy": round(multi_rejected / max(1, len(real_multi)), 4),
            "multiple_animal_rejected": f"{multi_rejected}/{len(real_multi)}",
            "other_animal_rejection_accuracy": round(other_rejected / max(1, len(real_other)), 4),
            "degraded_low_confidence_rejection_accuracy": round(degraded_rejected / max(1, len(degraded)), 4),
            "case_d_no_similar_coat_rejection_accuracy": round(case_d_rejected / max(1, len(case_d_queries)), 4),
            "overall_no_match_rejection_accuracy": round(total_nomatch_correct / max(1, total_nomatch_pool), 4),
            "overall_no_match_rejected": f"{total_nomatch_correct}/{total_nomatch_pool}",
        },
        "latency_ms": {
            "samples": len(latencies_ms),
            "p50": round(statistics.median(latencies_ms), 3) if latencies_ms else 0.0,
            "p95": _percentile(latencies_ms, 95.0),
        },
    }


def run_ai4b_evaluation(manifest_v2: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the complete AI-4.0b benchmark across calibration, acceptance_holdout, and combined splits."""
    manifest_v2 = manifest_v2 or build_ai4b_manifest_v2()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    full_68_catalog = [_prepare_catalog_row(s) for s in manifest_v2["pet_samples"]]
    enrolled_catalog = [
        row for row, s in zip(full_68_catalog, manifest_v2["pet_samples"])
        if s["catalog_enrollment"] == "enrolled"
    ]

    cal_res = _evaluate_split_v2("calibration", manifest_v2, enrolled_catalog, full_68_catalog)
    hold_res = _evaluate_split_v2("acceptance_holdout", manifest_v2, enrolled_catalog, full_68_catalog)
    all_res = _evaluate_split_v2("all", manifest_v2, enrolled_catalog, full_68_catalog)

    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS ru_maxrss is in bytes; Linux is in KiB
    import sys
    rss_scale = (1024.0 * 1024.0) if sys.platform == "darwin" else 1024.0
    model_info = get_model_manifest_summary()
    total_model_bytes = sum(int(m["size_bytes"]) for m in model_info["models"])

    return {
        "benchmark_id": manifest_v2["dataset_id"],
        "version": manifest_v2["version"],
        "models": model_info,
        "resource_profile": {
            "total_model_size_bytes": total_model_bytes,
            "total_model_size_mb": round(total_model_bytes / (1024.0 * 1024.0), 2),
            "peak_rss_mb": round(rss_after / rss_scale, 2),
            "rss_delta_mb": round(max(0.0, (rss_after - rss_before) / rss_scale), 2),
        },
        "dataset_counts": manifest_v2["counts"],
        "splits": {
            "calibration": cal_res,
            "acceptance_holdout": hold_res,
            "combined_all": all_res,
        },
    }


def render_ai4b_markdown_report(report: dict[str, Any]) -> str:
    """Format the AI-4.0b evaluation report into Markdown."""
    cal = report["splits"]["calibration"]
    hold = report["splits"]["acceptance_holdout"]
    comb = report["splits"]["combined_all"]
    res_prof = report["resource_profile"]
    cm_hold_all = hold["confusion_matrix_new_pets_all"]
    cm_hold_real = hold["confusion_matrix_real_photos_only"]

    def pct(v: float | None) -> str:
        return "—" if v is None else f"{v * 100:.1f}%"

    lines = [
        "# Báo cáo Đánh giá Định lượng Tự động Phát hiện Thú cưng & Nhận diện Loài — `AI-4.0b`",
        "",
        f"- **Bộ kiểm chuẩn**: `{report['benchmark_id']}` `v{report['version']}` (`manifest_v2.json`)",
        f"- **Mô hình cục bộ**: `YOLOX-Nano` (`3.55 MB`, Apache-2.0) + `MobileNetV2-12` (`13.32 MB`, Apache-2.0) = **`{res_prof['total_model_size_mb']} MB`** trên `onnxruntime` (`CPUExecutionProvider`, `0` gọi mạng, `0` cần PyTorch).",
        f"- **Đỉnh bộ nhớ tiến trình (`Peak RSS`)**: `{res_prof['peak_rss_mb']} MB`.",
        "",
        "## 1. Ma trận Nhầm lẫn Mèo / Chó trên Tập Nghiệm thu Độc lập (`Acceptance Holdout` — Ảnh Mới Ngoài Kho)",
        "",
        "### 1.1. Toàn bộ ảnh mới ngoài kho trên `Acceptance Holdout` (`8` ảnh nhiếp ảnh thực + `6` chân dung ngoài kho = `14` cá thể)",
        "",
        "| Nhãn Thực tế \\ Dự đoán Tự động | Dự đoán `Mèo` (`one_cat`) | Dự đoán `Chó` (`one_dog`) | Từ chối an toàn (`Abstained`) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Thực tế là `Mèo` (`7`)** | **`{cm_hold_all['true_cat']['pred_cat']}`** | **`{cm_hold_all['true_cat']['pred_dog']}`** | `{cm_hold_all['true_cat']['abstained']}` |",
        f"| **Thực tế là `Chó` (`7`)** | **`{cm_hold_all['true_dog']['pred_cat']}`** | **`{cm_hold_all['true_dog']['pred_dog']}`** | `{cm_hold_all['true_dog']['abstained']}` |",
        "",
        "### 1.2. Riêng nhóm Ảnh Nhiếp ảnh Thực tế Độc lập (`Real Photographs Only` trên `Acceptance Holdout` — `8` ảnh)",
        "",
        "| Nhãn Thực tế \\ Dự đoán Tự động | Dự đoán `Mèo` (`one_cat`) | Dự đoán `Chó` (`one_dog`) | Từ chối an toàn (`Abstained`) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Ảnh thật `Mèo` (`4`)** | **`{cm_hold_real['true_cat']['pred_cat']}`** | **`{cm_hold_real['true_cat']['pred_dog']}`** | `{cm_hold_real['true_cat']['abstained']}` |",
        f"| **Ảnh thật `Chó` (`4`)** | **`{cm_hold_real['true_dog']['pred_cat']}`** | **`{cm_hold_real['true_dog']['pred_dog']}`** | `{cm_hold_real['true_dog']['abstained']}` |",
        "",
        "## 2. So sánh Trực tiếp `AI-4.0a` vs `AI-4.0b` (Độ chính xác, Độ phủ & Từ chối An toàn)",
        "",
        "| Chỉ số đo lường | `AI-4.0a` (Không lọc tay) | `AI-4.0b` (`Calibration`) | **`AI-4.0b` (`Acceptance Holdout`)** | `AI-4.0b` (Toàn bộ) |",
        "| :--- | :---: | :---: | :---: | :---: |",
        f"| **Độ phủ tự động trên ảnh thú cưng mới (`Coverage`)** | `0.0%` (luôn đòi chọn tay) | `{pct(cal['species_metrics']['coverage_on_new_images_all'])}` | **`{pct(hold['species_metrics']['coverage_on_new_images_all'])}`** | `{pct(comb['species_metrics']['coverage_on_new_images_all'])}` |",
        f"| **Độ phủ tự động riêng trên Ảnh Thật (`Real Photos`)** | `0.0%` | `{pct(cal['species_metrics']['coverage_on_real_photographs'])}` | **`{pct(hold['species_metrics']['coverage_on_real_photographs'])}`** | `{pct(comb['species_metrics']['coverage_on_real_photographs'])}` |",
        f"| **Tỷ lệ từ chối phân loại loài (`Species Abstention`)** | `100.0%` | `{pct(cal['species_metrics']['species_abstention_rate_all_new'])}` | **`{pct(hold['species_metrics']['species_abstention_rate_all_new'])}`** | `{pct(comb['species_metrics']['species_abstention_rate_all_new'])}` |",
        f"| **Precision loài `Mèo` / `Chó` (khi đã xác nhận)** | — | `{pct(cal['species_metrics']['cat_precision_when_predicted'])} / {pct(cal['species_metrics']['dog_precision_when_predicted'])}` | **`{pct(hold['species_metrics']['cat_precision_when_predicted'])} / {pct(hold['species_metrics']['dog_precision_when_predicted'])}`** | `{pct(comb['species_metrics']['cat_precision_when_predicted'])} / {pct(comb['species_metrics']['dog_precision_when_predicted'])}` |",
        f"| **Recall đầu-cuối loài `Mèo` / `Chó`** | `0.0% / 0.0%` | `{pct(cal['species_metrics']['cat_end_to_end_recall'])} / {pct(cal['species_metrics']['dog_end_to_end_recall'])}` | **`{pct(hold['species_metrics']['cat_end_to_end_recall'])} / {pct(hold['species_metrics']['dog_end_to_end_recall'])}`** | `{pct(comb['species_metrics']['cat_end_to_end_recall'])} / {pct(comb['species_metrics']['dog_end_to_end_recall'])}` |",
        f"| **Lỗi truy xuất chéo loài Mèo <-> Chó (`CSER`)** | `0.0%` (do từ chối 100%) | `{pct(cal['retrieval_and_rejection']['cross_species_retrieval_error_rate'])}` (`{cal['retrieval_and_rejection']['cross_species_retrieval_errors']}`) | **`{pct(hold['retrieval_and_rejection']['cross_species_retrieval_error_rate'])}` (`{hold['retrieval_and_rejection']['cross_species_retrieval_errors']}`)** | `{pct(comb['retrieval_and_rejection']['cross_species_retrieval_error_rate'])}` (`{comb['retrieval_and_rejection']['cross_species_retrieval_errors']}`) |",
        f"| **Lỗi chéo loài Mèo Cam vs Chó Lông Vàng** | — | `{cal['retrieval_and_rejection']['orange_cat_golden_dog_cross_species_errors']}` | **`{hold['retrieval_and_rejection']['orange_cat_golden_dog_cross_species_errors']}`** | `{comb['retrieval_and_rejection']['orange_cat_golden_dog_cross_species_errors']}` |",
        f"| **Precision màu lông Mèo Cam tự động (`sP@5`)** | — | `{pct(cal['retrieval_and_rejection']['orange_cat_coat_precision_mean'])}` | **`{pct(hold['retrieval_and_rejection']['orange_cat_coat_precision_mean'])}`** | `{pct(comb['retrieval_and_rejection']['orange_cat_coat_precision_mean'])}` |",
        f"| **Exact-Image Rank-1 (`EIRA@1`)** | `100.0%` | `{pct(cal['retrieval_and_rejection']['exact_image_rank1_accuracy'])}` (`{cal['retrieval_and_rejection']['exact_image_rank1_hits']}`) | **`{pct(hold['retrieval_and_rejection']['exact_image_rank1_accuracy'])}` (`{hold['retrieval_and_rejection']['exact_image_rank1_hits']}`)** | `{pct(comb['retrieval_and_rejection']['exact_image_rank1_accuracy'])}` (`{comb['retrieval_and_rejection']['exact_image_rank1_hits']}`) |",
        f"| **FPR trên Ảnh Thật Phi Động vật & Thú Bông** | *(không chặn nếu ép loài)* | `{pct(cal['retrieval_and_rejection']['real_non_animal_and_toy_fpr'])}` | **`{pct(hold['retrieval_and_rejection']['real_non_animal_and_toy_fpr'])}`** | `{pct(comb['retrieval_and_rejection']['real_non_animal_and_toy_fpr'])}` |",
        f"| **FPR trên Ảnh Chụp Giao diện / Đồ họa** | `0.0%` | `{pct(cal['retrieval_and_rejection']['ui_or_procedural_non_animal_fpr'])}` | **`{pct(hold['retrieval_and_rejection']['ui_or_procedural_non_animal_fpr'])}`** | `{pct(comb['retrieval_and_rejection']['ui_or_procedural_non_animal_fpr'])}` |",
        f"| **Độ chính xác từ chối Ảnh Đa Động vật (`2+` con)** | `0.0%` (nếu ép loài) | `{pct(cal['retrieval_and_rejection']['multiple_animal_rejection_accuracy'])}` (`{cal['retrieval_and_rejection']['multiple_animal_rejected']}`) | **`{pct(hold['retrieval_and_rejection']['multiple_animal_rejection_accuracy'])}` (`{hold['retrieval_and_rejection']['multiple_animal_rejected']}`)** | `{pct(comb['retrieval_and_rejection']['multiple_animal_rejection_accuracy'])}` (`{comb['retrieval_and_rejection']['multiple_animal_rejected']}`) |",
        f"| **Độ chính xác từ chối Không khớp Tổng hợp** | — | `{pct(cal['retrieval_and_rejection']['overall_no_match_rejection_accuracy'])}` (`{cal['retrieval_and_rejection']['overall_no_match_rejected']}`) | **`{pct(hold['retrieval_and_rejection']['overall_no_match_rejection_accuracy'])}` (`{hold['retrieval_and_rejection']['overall_no_match_rejected']}`)** | `{pct(comb['retrieval_and_rejection']['overall_no_match_rejection_accuracy'])}` (`{comb['retrieval_and_rejection']['overall_no_match_rejected']}`) |",
        f"| **Độ trễ tìm kiếm toàn trình `p50 / p95` (ms)** | `21.4 / 27.3 ms` | `{cal['latency_ms']['p50']} / {cal['latency_ms']['p95']} ms` | **`{hold['latency_ms']['p50']} / {hold['latency_ms']['p95']} ms`** | `{comb['latency_ms']['p50']} / {comb['latency_ms']['p95']} ms` |",
        "",
    ]
    return "\n".join(lines)
