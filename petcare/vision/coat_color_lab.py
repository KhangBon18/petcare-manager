"""Foreground-aware white-balanced CIE-Lab coat descriptors and 1280-D embedding utilities (AI-4.0c).

Implements:
1. Versioned compact L2-normalized 1280-D penultimate visual embedding codec (float16 base64)
   with strict dimension, finiteness, and unit-norm integrity checks.
2. Standard IEC 61966-2-1 sRGB -> Linear RGB -> CIE XYZ (D65) -> CIE-Lab (L*, a*, b*) conversion.
3. Bounded Achromatic-Quantile Shades-of-Gray white balance that corrects warm indoor tungsten
   and cool shade color casts while protecting natural orange, golden, cream, white, and black coats
   against Gray-World overcorrection.
4. Bounding-box-guided foreground spatial weighting + peripheral background ΔE suppression +
   non-mammalian foliage/cyan hue suppression, producing a 16-bin perceptual CIE-Lab histogram
   and a 7-bucket canonical coat profile.
"""

from __future__ import annotations

import base64
import binascii
from typing import Literal

import numpy as np
from PIL import Image

from petcare.vision.species_taxonomy import COAT_PROFILE_BUCKETS, extract_db_coat_groups

EMBEDDING_VERSION = "mnv2_op12_fg1280_f16_v1"
EMBEDDING_DIM = 1280
_EMBEDDING_F16_BYTES = EMBEDDING_DIM * 2  # 2,560 bytes
_EMBEDDING_B64_LEN = 3416  # ceil(2560 / 3) * 4

FG_LAB_VERSION = "cielab_wb_sog_fg16_v1"
FG_LAB_BINS = 16

WBMode = Literal["achromatic_shades_of_gray", "shades_of_gray_p6", "gray_world", "none"]

# Canonical CIE-Lab (L*, a*, b*) prototypes for the 16 foreground coat bins
_LAB_BIN_PROTOTYPES = np.array(
    [
        [14.0, 0.0, 1.0],    # 00: jet_black
        [27.0, 0.0, 2.0],    # 01: charcoal_dark
        [41.0, 0.0, 1.0],    # 02: dark_slate_gray
        [55.0, 0.0, 2.0],    # 03: medium_silver_gray
        [68.0, 0.0, 3.0],    # 04: light_ash_gray
        [79.0, 1.0, 5.0],    # 05: soft_ivory_white
        [90.0, 0.0, 3.0],    # 06: bright_pure_white
        [74.0, 3.0, 14.0],   # 07: light_cream_pastel
        [57.0, 6.0, 16.0],   # 08: warm_tan_fawn
        [38.0, 6.0, 15.0],   # 09: muted_taupe_brown
        [70.0, 11.0, 30.0],  # 10: bright_ginger_gold
        [53.0, 15.0, 31.0],  # 11: vivid_orange_amber
        [36.0, 13.0, 22.0],  # 12: deep_rufous_ginger
        [46.0, 18.0, 20.0],  # 13: rich_chestnut_brown
        [26.0, 9.0, 14.0],   # 14: dark_chocolate_brown
        [55.0, -5.0, -5.0],  # 15: residual_other
    ],
    dtype=np.float32,
)

_PROTO_DIFF = _LAB_BIN_PROTOTYPES[:, None, :] - _LAB_BIN_PROTOTYPES[None, :, :]
_LAB_SIM_KERNEL = np.exp(-np.sum(_PROTO_DIFF * _PROTO_DIFF, axis=-1) / (2.0 * (16.0**2))).astype(
    np.float32
)

_YY64, _XX64 = np.mgrid[0:64, 0:64]
_R2_64 = (((_XX64 - 31.5) / 31.5) ** 2 + ((_YY64 - 31.5) / 31.5) ** 2).astype(np.float32)
_SPATIAL_PRIOR_64 = np.exp(-1.35 * _R2_64).astype(np.float32)


def l2_normalize_embedding(raw_vec: np.ndarray | list[float] | tuple[float, ...]) -> np.ndarray | None:
    """Validate a 1280-D feature vector and normalize it to unit L2 length."""
    arr = np.asarray(raw_vec, dtype=np.float32).reshape(-1)
    if arr.shape != (EMBEDDING_DIM,) or not np.all(np.isfinite(arr)):
        return None
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-8:
        return None
    return (arr / norm).astype(np.float32)


def encode_embedding_f16_b64(unit_vec: np.ndarray | None) -> str:
    """Serialize a validated unit-norm 1280-D vector as compact little-endian float16 base64."""
    if unit_vec is None:
        return ""
    clean = l2_normalize_embedding(unit_vec)
    if clean is None:
        return ""
    f16_bytes = clean.astype("<f2").tobytes()
    return base64.b64encode(f16_bytes).decode("ascii")


def decode_embedding_f16_b64(
    b64_value: str | None,
    *,
    actual_version: str = EMBEDDING_VERSION,
    expected_version: str = EMBEDDING_VERSION,
) -> np.ndarray | None:
    """Decode and validate a stored 1280-D float16 embedding; returns None if missing or outdated."""
    if (
        not b64_value
        or not isinstance(b64_value, str)
        or actual_version != expected_version
        or len(b64_value) != _EMBEDDING_B64_LEN
    ):
        return None
    try:
        raw = base64.b64decode(b64_value.encode("ascii"), validate=True)
    except (ValueError, binascii.Error):
        return None
    if len(raw) != _EMBEDDING_F16_BYTES:
        return None
    vec = np.frombuffer(raw, dtype="<f2").astype(np.float32)
    if vec.shape != (EMBEDDING_DIM,) or not np.all(np.isfinite(vec)):
        return None
    norm = float(np.linalg.norm(vec))
    if not (0.97 <= norm <= 1.03):
        return None
    return (vec / norm).astype(np.float32)


def embedding_cosine_similarity(left: np.ndarray | None, right: np.ndarray | None) -> float | None:
    """Compute exact L2-normalized cosine similarity in [0.0, 1.0] for valid 1280-D embeddings."""
    if left is None or right is None:
        return None
    if left.shape != (EMBEDDING_DIM,) or right.shape != (EMBEDDING_DIM,):
        return None
    dot = float(np.dot(left, right))
    if not np.isfinite(dot):
        return None
    return max(0.0, min(1.0, dot))


def srgb_to_linear(rgb01: np.ndarray) -> np.ndarray:
    """Convert sRGB [0, 1] array to linear-light RGB."""
    clipped = np.clip(rgb01, 0.0, 1.0)
    return np.where(
        clipped <= 0.04045,
        clipped / 12.92,
        np.power((clipped + 0.055) / 1.055, 2.4),
    ).astype(np.float32)


def linear_to_cie_lab(lin_rgb: np.ndarray) -> np.ndarray:
    """Convert linear RGB [0, 1+] array to CIE 1976 L*a*b* under D65 reference white."""
    c = np.maximum(lin_rgb, 0.0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.00000
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    eps = (6.0 / 29.0) ** 3
    kappa = (1.0 / 3.0) * ((29.0 / 6.0) ** 2)
    fx = np.where(x > eps, np.cbrt(np.maximum(x, 1e-12)), kappa * x + (4.0 / 29.0))
    fy = np.where(y > eps, np.cbrt(np.maximum(y, 1e-12)), kappa * y + (4.0 / 29.0))
    fz = np.where(z > eps, np.cbrt(np.maximum(z, 1e-12)), kappa * z + (4.0 / 29.0))

    l_star = 116.0 * fy - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return np.stack([l_star, a_star, b_star], axis=-1).astype(np.float32)


def estimate_white_balance_gains(
    rgb_full_01: np.ndarray,
    *,
    mode: WBMode = "achromatic_shades_of_gray",
) -> np.ndarray:
    """Estimate luminance-preserving von Kries RGB gains without washing out natural fur colors."""
    if mode == "none":
        return np.ones(3, dtype=np.float32)

    lin = srgb_to_linear(rgb_full_01)
    flat = lin.reshape(-1, 3)
    mx = flat.max(axis=1)
    s = flat.sum(axis=1)
    mask = (mx >= 0.035) & (mx <= 0.97) & (s >= 0.07)
    valid = flat[mask]
    if len(valid) < 64:
        return np.ones(3, dtype=np.float32)

    if mode == "gray_world":
        est = valid.mean(axis=0)
        lum = 0.2126 * est[0] + 0.7152 * est[1] + 0.0722 * est[2]
        return np.clip(lum / np.maximum(est, 1e-4), 0.55, 1.80).astype(np.float32)

    if mode == "shades_of_gray_p6":
        est = np.power(np.mean(np.power(valid, 6.0), axis=0), 1.0 / 6.0)
        lum = 0.2126 * est[0] + 0.7152 * est[1] + 0.0722 * est[2]
        raw_gains = lum / np.maximum(est, 1e-4)
        return np.clip(1.0 + 0.75 * (raw_gains - 1.0), 0.80, 1.28).astype(np.float32)

    # Default: Achromatic-Quantile Shades-of-Gray (22% least-chromatic scene pixels, sqrt-Y weighted)
    chrom = valid / s[mask, None]
    dev = np.abs(chrom - (1.0 / 3.0)).sum(axis=1)
    k = max(32, int(0.22 * len(valid)))
    idx = np.argpartition(dev, k - 1)[:k]
    pool = valid[idx]
    pool_chrom = chrom[idx]
    lum_w = np.sqrt(0.2126 * pool[:, 0] + 0.7152 * pool[:, 1] + 0.0722 * pool[:, 2])[:, None]
    est_chrom = (pool_chrom * lum_w).sum(axis=0) / max(float(lum_w.sum()), 1e-6)
    ref_lum = 0.2126 * est_chrom[0] + 0.7152 * est_chrom[1] + 0.0722 * est_chrom[2]
    raw_gains = ref_lum / np.maximum(est_chrom, 1e-4)
    # Damp green-magenta channel so green grass never induces magenta tint
    raw_gains[1] = 1.0 + 0.25 * (raw_gains[1] - 1.0)
    delta = raw_gains - 1.0
    delta = np.sign(delta) * np.maximum(0.0, np.abs(delta) - 0.05)
    return np.clip(1.0 + 0.85 * delta, 0.80, 1.28).astype(np.float32)


def compute_foreground_lab_coat(
    pil_rgb: Image.Image,
    bbox: tuple[float, float, float, float] | None = None,
    *,
    wb_mode: WBMode = "achromatic_shades_of_gray",
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Compute (fg_lab_histogram_16, fg_coat_profile_7) inside the detected animal bounding box."""
    w, h = pil_rgb.size
    if bbox is None:
        eff_bbox = (w * 0.12, h * 0.12, w * 0.88, h * 0.88)
    else:
        eff_bbox = bbox

    small_full = (
        np.asarray(pil_rgb.resize((96, 96), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    )
    gains = estimate_white_balance_gains(small_full, mode=wb_mode)
    full_lab = linear_to_cie_lab(
        np.clip(srgb_to_linear(small_full) * gains[None, None, :], 0.0, 1.18)
    )

    bx1 = max(0, min(96, int(round(eff_bbox[0] / max(1, w) * 96))))
    by1 = max(0, min(96, int(round(eff_bbox[1] / max(1, h) * 96))))
    bx2 = max(0, min(96, int(round(eff_bbox[2] / max(1, w) * 96))))
    by2 = max(0, min(96, int(round(eff_bbox[3] / max(1, h) * 96))))

    bg_mask = np.ones((96, 96), dtype=bool)
    if (bx2 - bx1) * (by2 - by1) < int(0.82 * 96 * 96):
        bg_mask[by1:by2, bx1:bx2] = False
    else:
        bg_mask[6:90, 6:90] = False

    bg_px = full_lab[bg_mask]
    if len(bg_px) >= 16:
        med_l = float(np.median(bg_px[:, 0]))
        lo_px = bg_px[bg_px[:, 0] <= med_l]
        hi_px = bg_px[bg_px[:, 0] >= med_l]
        bg_lo = np.median(lo_px, axis=0) if len(lo_px) else np.median(bg_px, axis=0)
        bg_hi = np.median(hi_px, axis=0) if len(hi_px) else np.median(bg_px, axis=0)
    else:
        bg_lo = bg_hi = np.array([-999.0, 0.0, 0.0], dtype=np.float32)

    tx1, ty1 = max(0, round(eff_bbox[0])), max(0, round(eff_bbox[1]))
    tx2, ty2 = min(w, round(eff_bbox[2])), min(h, round(eff_bbox[3]))
    crop = pil_rgb.crop((tx1, ty1, tx2, ty2)) if tx2 > tx1 and ty2 > ty1 else pil_rgb
    crop_srgb = np.asarray(crop.resize((64, 64), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    lab = linear_to_cie_lab(np.clip(srgb_to_linear(crop_srgb) * gains[None, None, :], 0.0, 1.18))

    wt = _SPATIAL_PRIOR_64.copy()
    core_med = np.median(lab[_R2_64 <= 0.22], axis=0)
    core_de = min(
        float(np.linalg.norm(core_med - bg_lo)),
        float(np.linalg.norm(core_med - bg_hi)),
    )

    de_bg = np.minimum(
        np.linalg.norm(lab - bg_lo[None, None, :], axis=-1),
        np.linalg.norm(lab - bg_hi[None, None, :], axis=-1),
    )

    l_ch = lab[..., 0]
    a_ch = lab[..., 1]
    b_ch = lab[..., 2]
    chroma = np.hypot(a_ch, b_ch)

    # Suppress foliage green and deep cyan/blue background pixels that never occur on cat/dog fur
    non_fur_hue = (a_ch < -8.5) | ((b_ch < -11.5) & (l_ch < 74.0))
    wt = np.where(non_fur_hue, wt * 0.02, wt)

    # Suppress peripheral bbox background spill while protecting dark-on-dark and golden-on-golden cores
    if core_de > 18.0:
        wt = np.where((_R2_64 > 0.24) & (de_bg < 14.0), wt * 0.05, wt)

    bins = np.full((64, 64), 15, dtype=np.int32)
    achrom = (
        (chroma < 13.0)
        | ((l_ch < 24.0) & (chroma < 18.0))
        | ((l_ch >= 72.0) & (chroma < 15.5))
    )

    bins = np.where(achrom & (l_ch < 20.0), 0, bins)
    bins = np.where(achrom & (l_ch >= 20.0) & (l_ch < 33.0), 1, bins)
    bins = np.where(achrom & (l_ch >= 33.0) & (l_ch < 48.0), 2, bins)
    bins = np.where(achrom & (l_ch >= 48.0) & (l_ch < 63.0), 3, bins)
    bins = np.where(achrom & (l_ch >= 63.0) & (l_ch < 72.0), 4, bins)
    bins = np.where(achrom & (l_ch >= 72.0) & (l_ch < 83.0), 5, bins)
    bins = np.where(achrom & (l_ch >= 83.0), 6, bins)

    warm_mid = (~achrom) & (chroma < 22.0) & (b_ch >= 8.0) & (a_ch >= -3.5)
    bins = np.where(warm_mid & (l_ch >= 65.0), 7, bins)
    bins = np.where(warm_mid & (l_ch >= 44.0) & (l_ch < 65.0), 8, bins)
    bins = np.where(warm_mid & (l_ch < 44.0), 9, bins)

    warm_hi = (~achrom) & (chroma >= 21.5) & (b_ch >= 9.0) & (a_ch >= -2.5)
    bins = np.where(warm_hi & (l_ch >= 60.0) & (b_ch >= 20.0), 10, bins)
    bins = np.where(
        warm_hi & (l_ch >= 44.0) & (l_ch < 60.0) & (b_ch >= 18.5) & (b_ch >= 1.05 * a_ch),
        11,
        bins,
    )
    bins = np.where(
        warm_hi & (l_ch >= 25.0) & (l_ch < 44.0) & (b_ch >= 15.0) & (b_ch >= 1.12 * a_ch) & (a_ch >= 4.5),
        12,
        bins,
    )
    bins = np.where(warm_hi & (l_ch >= 30.0) & (bins == 15), 13, bins)
    bins = np.where(warm_hi & (l_ch < 30.0) & (bins == 15), 14, bins)

    hist = np.bincount(bins.ravel(), weights=wt.ravel(), minlength=FG_LAB_BINS).astype(np.float32)
    hist /= max(float(hist.sum()), 1e-8)

    hist_tuple = tuple(round(float(v), 5) for v in hist)
    coat7_tuple = (
        round(float(hist[10] + hist[11] + hist[12]), 5),  # orange_gold
        round(float(hist[7] + hist[8]), 5),               # cream_tan
        round(float(hist[9] + hist[13] + hist[14]), 5),   # brown
        round(float(hist[0] + hist[1]), 5),               # black_dark
        round(float(hist[2] + hist[3] + hist[4]), 5),     # gray_silver
        round(float(hist[5] + hist[6]), 5),               # white_light
        round(float(hist[15]), 5),                        # other
    )
    return hist_tuple, coat7_tuple


def validate_lab_histogram(values: tuple[float, ...] | list[float] | None) -> tuple[float, ...] | None:
    """Validate a stored 16-bin foreground CIE-Lab histogram."""
    if not values or not isinstance(values, (list, tuple)) or len(values) != FG_LAB_BINS:
        return None
    try:
        arr = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(arr)) or np.any(arr < -1e-4):
        return None
    total = float(arr.sum())
    if not (0.95 <= total <= 1.05):
        return None
    arr = np.maximum(arr, 0.0) / total
    return tuple(round(float(x), 5) for x in arr)


def compare_lab_histograms(
    left: tuple[float, ...] | list[float] | None,
    right: tuple[float, ...] | list[float] | None,
) -> float | None:
    """Perceptual similarity in [0.0, 1.0] combining exact bin intersection and ΔE kernel similarity."""
    if not left or not right or len(left) != FG_LAB_BINS or len(right) != FG_LAB_BINS:
        return None
    h1 = np.asarray(left, dtype=np.float32)
    h2 = np.asarray(right, dtype=np.float32)
    if not (np.all(np.isfinite(h1)) and np.all(np.isfinite(h2))):
        return None
    inter = float(np.minimum(h1, h2).sum())
    q12 = float(h1 @ _LAB_SIM_KERNEL @ h2)
    q11 = float(h1 @ _LAB_SIM_KERNEL @ h1)
    q22 = float(h2 @ _LAB_SIM_KERNEL @ h2)
    quad = q12 / max(1e-8, (q11 * q22) ** 0.5)
    return max(0.0, min(1.0, 0.50 * inter + 0.50 * quad))


def extract_lab_coat_groups(coat7: tuple[float, ...] | list[float] | None) -> frozenset[str]:
    """Extract canonical coat-color families from a 7-bucket CIE-Lab foreground coat profile."""
    if not coat7 or len(coat7) != len(COAT_PROFILE_BUCKETS):
        return frozenset()
    by_b = dict(zip(COAT_PROFILE_BUCKETS, (float(x) for x in coat7)))
    groups: set[str] = set()

    warm_sum = by_b["orange_gold"] + by_b["cream_tan"]
    if by_b["orange_gold"] >= 0.15:
        groups.update({"orange_gold", "cream_tan"})
    elif by_b["cream_tan"] >= 0.24:
        if (by_b["brown"] + by_b["black_dark"]) >= 0.18:
            groups.update({"cream_tan", "brown"})
        else:
            groups.update({"orange_gold", "cream_tan"})
    elif warm_sum >= 0.28:
        groups.update({"orange_gold", "cream_tan"})

    # Only add standalone brown if the coat is genuinely brown rather than shaded ginger stripes
    if by_b["brown"] >= 0.22 and by_b["orange_gold"] < 0.20:
        groups.add("brown")

    chromatic_warm_or_brown = warm_sum + by_b["brown"]
    if by_b["gray_silver"] >= 0.28 and not (chromatic_warm_or_brown >= 0.36 and by_b["gray_silver"] < 0.40):
        groups.add("gray_silver")

    if (
        by_b["black_dark"] >= 0.28
        and not (by_b["gray_silver"] >= 0.50 and by_b["black_dark"] < 0.46)
        and not (by_b["brown"] >= 0.28 and by_b["black_dark"] < 0.48)
    ):
        groups.add("black_dark")

    if not groups and by_b["white_light"] >= 0.25:
        groups.add("white_light")
    elif by_b["white_light"] >= 0.58 and warm_sum < 0.20 and by_b["black_dark"] < 0.16:
        groups.add("white_light")

    # Fallback to single argmax non-other bucket so no valid coat ever becomes a wildcard
    if not groups:
        best_key = max(COAT_PROFILE_BUCKETS[:-1], key=lambda k: by_b[k])
        if by_b[best_key] >= 0.12:
            groups.add(best_key)
    return frozenset(groups)


def lab_coat_groups_compatible(
    query_lab_coat7: tuple[float, ...] | list[float] | None,
    pet_coat_color: str | None,
    pet_appearance_tags: str | None = "",
    candidate_lab_coat7: tuple[float, ...] | list[float] | None = None,
) -> bool:
    """Precision-first foreground CIE-Lab coat compatibility check."""
    q_groups = extract_lab_coat_groups(query_lab_coat7)
    c_groups = extract_db_coat_groups(pet_coat_color, pet_appearance_tags)
    if not c_groups and candidate_lab_coat7:
        c_groups = extract_lab_coat_groups(candidate_lab_coat7)
    if not q_groups or not c_groups:
        return True

    # Guardrail for solid pure-white queries (e.g. Samoyed / white Angora):
    # prevent matching spotted/calico/tuxedo pets purely via the word "trắng" in "trắng cam đen" / "trắng đốm đen".
    if query_lab_coat7 and len(query_lab_coat7) == len(COAT_PROFILE_BUCKETS):
        by_q = dict(zip(COAT_PROFILE_BUCKETS, (float(x) for x in query_lab_coat7)))
        is_solid_white_query = (
            by_q["white_light"] >= 0.68
            and (by_q["black_dark"] + by_q["orange_gold"] + by_q["brown"]) < 0.12
        )
        if is_solid_white_query and (c_groups & {"black_dark", "orange_gold", "brown"}):
            return False

    return bool(q_groups & c_groups)
