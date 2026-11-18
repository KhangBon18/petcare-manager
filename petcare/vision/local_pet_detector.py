"""Offline 2-stage ONNX pet detector and temperature-calibrated species gate (AI-4.0b).

Stage 1: Official YOLOX-Nano (Apache-2.0, 416x416 COCO 80-class detector) detects actual
         animal bounding boxes, counts animals, and identifies plush toys / non-animals.
Stage 2: Official MobileNetV2-12 (Apache-2.0, 224x224 ImageNet-1K breed logits) classifies
         the cropped animal bounding box with Temperature Scaling (calibrated on the
         identity-disjoint AI-4.0b calibration split) and enforces strict stage agreement.

Zero external network access and zero PyTorch runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
import json
from pathlib import Path
import threading
import time
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from petcare.vision.coat_color_lab import (
    EMBEDDING_VERSION,
    FG_LAB_VERSION,
    compute_foreground_lab_coat,
    encode_embedding_f16_b64,
    l2_normalize_embedding,
)
from petcare.vision.image_features import (
    ImageDescriptor,
    compute_subject_coat_profile,
    describe_image,
    sha256_hex,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"
MANIFEST_PATH = MODELS_DIR / "MODEL_MANIFEST.json"
CALIBRATION_PATH = MODELS_DIR / "species_gate_calibration_v1.json"

SUBJECT_ONE_CAT = "one_cat"
SUBJECT_ONE_DOG = "one_dog"
SUBJECT_OTHER_ANIMAL = "other_animal"
SUBJECT_NO_RELIABLE_ANIMAL = "no_reliable_animal"
SUBJECT_MULTIPLE_ANIMALS = "multiple_animals"
SUBJECT_AMBIGUOUS = "ambiguous_subject"
SUBJECT_GATE_UNAVAILABLE = "gate_unavailable"

COCO_ANIMAL_CLASSES: dict[int, str] = {
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
}
COCO_TEDDY_BEAR_CLASS = 77

_IMAGENET_CAT_SLICE = slice(281, 286)  # tabby, tiger cat, Persian, Siamese, Egyptian cat
_IMAGENET_DOG_SLICE = slice(151, 269)  # 118 domestic dog breeds (incl. Pembroke/Cardigan Corgi)
_IMAGENET_TEDDY_INDEX = 850
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_YOLOX_STRIDES = (8, 16, 32)
_YOLOX_INPUT_SIZE = 416


def _build_yolox_grids() -> tuple[np.ndarray, np.ndarray]:
    grids = []
    strides = []
    for st in _YOLOX_STRIDES:
        hs, ws = _YOLOX_INPUT_SIZE // st, _YOLOX_INPUT_SIZE // st
        xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
        grid = np.stack((xv, yv), axis=2).reshape(1, -1, 2).astype(np.float32)
        grids.append(grid)
        strides.append(np.full((1, grid.shape[1], 1), st, dtype=np.float32))
    return np.concatenate(grids, axis=1), np.concatenate(strides, axis=1)


_YOLOX_GRIDS, _YOLOX_STRIDE_TENSOR = _build_yolox_grids()


@dataclass(frozen=True, slots=True)
class DetectedBox:
    """One NMS-filtered object detection box in original image coordinates."""

    class_id: int
    label: str
    raw_score: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class SpeciesGateDecision:
    """Structured output of the local 2-stage pet detection and species verification gate."""

    subject_status: str
    verified_species: str | None
    detail_reason: str
    animal_count: int
    primary_bbox: tuple[float, float, float, float] | None
    detector_label: str | None
    detector_raw_score: float | None
    calibrated_cat_prob: float | None
    calibrated_dog_prob: float | None
    candidate_species_support: frozenset[str]
    foreground_coat_profile: tuple[float, ...]
    foreground_descriptor: ImageDescriptor | None
    inference_ms: float
    foreground_embedding_b64: str = ""
    foreground_lab_histogram: tuple[float, ...] = ()
    foreground_lab_coat_profile: tuple[float, ...] = ()


class _LocalVisionRuntime:
    """Thread-safe lazy holder for SHA-256-verified local ONNX sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._det_session: ort.InferenceSession | None = None
        self._cls_session: ort.InferenceSession | None = None
        self._calibration: dict[str, Any] | None = None

    def load(self) -> tuple[ort.InferenceSession, ort.InferenceSession, dict[str, Any]]:
        if (
            self._det_session is not None
            and self._cls_session is not None
            and self._calibration is not None
        ):
            return self._det_session, self._cls_session, self._calibration

        with self._lock:
            if (
                self._det_session is not None
                and self._cls_session is not None
                and self._calibration is not None
            ):
                return self._det_session, self._cls_session, self._calibration

            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            by_role = {m["role"]: m for m in manifest["models"]}

            det_meta = by_role["stage1_object_detector"]
            cls_meta = by_role["stage2_crop_species_verifier"]
            det_path = MODELS_DIR / det_meta["filename"]
            cls_path = MODELS_DIR / cls_meta["filename"]

            if not det_path.is_file() or not cls_path.is_file():
                raise FileNotFoundError("Bundled ONNX vision models are missing.")

            det_bytes = det_path.read_bytes()
            cls_bytes = cls_path.read_bytes()
            if sha256_hex(det_bytes) != det_meta["sha256"]:
                raise RuntimeError("SHA-256 mismatch for stage1_object_detector ONNX artifact.")
            if sha256_hex(cls_bytes) != cls_meta["sha256"]:
                raise RuntimeError("SHA-256 mismatch for stage2_crop_species_verifier ONNX artifact.")

            variants = manifest.get("derived_variants") or []
            var_by_role = {v["role"]: v for v in variants}
            feat_meta = var_by_role.get("stage2_crop_species_and_embedding_extractor")
            active_cls_bytes = cls_bytes
            if feat_meta is not None:
                feat_path = MODELS_DIR / feat_meta["filename"]
                if not feat_path.is_file():
                    raise FileNotFoundError("Bundled MobileNetV2 feature-extractor ONNX variant is missing.")
                feat_bytes = feat_path.read_bytes()
                if sha256_hex(feat_bytes) != feat_meta["sha256"]:
                    raise RuntimeError("SHA-256 mismatch for MobileNetV2 feature-extractor ONNX artifact.")
                active_cls_bytes = feat_bytes

            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1

            self._det_session = ort.InferenceSession(
                det_bytes, sess_options=opts, providers=["CPUExecutionProvider"]
            )
            self._cls_session = ort.InferenceSession(
                active_cls_bytes, sess_options=opts, providers=["CPUExecutionProvider"]
            )
            self._calibration = calibration["parameters"]
            return self._det_session, self._cls_session, self._calibration


_RUNTIME = _LocalVisionRuntime()


def _nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / np.maximum(1e-6, area_i + area_r - inter)
        order = rest[iou <= iou_thr]
    return keep


def _collapse_concentric_animal_boxes(
    boxes: list[DetectedBox],
    containment_thr: float,
    center_shift_max: float,
) -> list[DetectedBox]:
    """Collapse only concentric head-inside-body boxes of the same animal while preserving multi-pet pairs."""
    kept: list[DetectedBox] = []
    for cand in boxes:
        cx1, cy1, cx2, cy2 = cand.bbox
        c_area = max(1.0, (cx2 - cx1) * (cy2 - cy1))
        ccx, ccy = 0.5 * (cx1 + cx2), 0.5 * (cy1 + cy2)
        is_duplicate_part = False
        for prev in kept:
            px1, py1, px2, py2 = prev.bbox
            p_area = max(1.0, (px2 - px1) * (py2 - py1))
            ix1, iy1 = max(cx1, px1), max(cy1, py1)
            ix2, iy2 = min(cx2, px2), min(cy2, py2)
            inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            containment = inter / min(c_area, p_area)
            pcx, pcy = 0.5 * (px1 + px2), 0.5 * (py1 + py2)
            ref_span = max(1.0, max(cx2 - cx1, cy2 - cy1, px2 - px1, py2 - py1))
            center_dist = ((ccx - pcx) ** 2 + (ccy - pcy) ** 2) ** 0.5 / ref_span
            if containment >= containment_thr and center_dist <= center_shift_max:
                is_duplicate_part = True
                break
        if not is_duplicate_part:
            kept.append(cand)
    return kept


def _run_yolox_detector(
    det_sess: ort.InferenceSession,
    pil_rgb: Image.Image,
    min_score: float,
    nms_iou: float,
) -> list[DetectedBox]:
    w, h = pil_rgb.size
    ratio = min(_YOLOX_INPUT_SIZE / h, _YOLOX_INPUT_SIZE / w)
    nw, nh = max(1, int(w * ratio)), max(1, int(h * ratio))
    padded = Image.new("RGB", (_YOLOX_INPUT_SIZE, _YOLOX_INPUT_SIZE), (114, 114, 114))
    padded.paste(pil_rgb.resize((nw, nh), Image.Resampling.BILINEAR), (0, 0))

    bgr = np.asarray(padded, dtype=np.float32)[:, :, ::-1]
    blob = np.ascontiguousarray(np.transpose(bgr, (2, 0, 1))[None, ...], dtype=np.float32)
    raw = det_sess.run(None, {det_sess.get_inputs()[0].name: blob})[0].copy()

    raw[..., :2] = (raw[..., :2] + _YOLOX_GRIDS) * _YOLOX_STRIDE_TENSOR
    raw[..., 2:4] = np.exp(raw[..., 2:4]) * _YOLOX_STRIDE_TENSOR
    preds = raw[0]

    boxes = np.empty_like(preds[:, :4])
    boxes[:, 0] = np.clip((preds[:, 0] - preds[:, 2] * 0.5) / ratio, 0.0, float(w))
    boxes[:, 1] = np.clip((preds[:, 1] - preds[:, 3] * 0.5) / ratio, 0.0, float(h))
    boxes[:, 2] = np.clip((preds[:, 0] + preds[:, 2] * 0.5) / ratio, 0.0, float(w))
    boxes[:, 3] = np.clip((preds[:, 1] + preds[:, 3] * 0.5) / ratio, 0.0, float(h))

    scores_mat = preds[:, 4:5] * preds[:, 5:]
    cls_ids = scores_mat.argmax(axis=1)
    confs = scores_mat[np.arange(len(preds)), cls_ids]
    mask = confs >= min_score
    if not np.any(mask):
        return []

    kept_boxes = boxes[mask]
    kept_confs = confs[mask]
    kept_cls = cls_ids[mask]
    keep_indices = _nms_xyxy(kept_boxes, kept_confs, nms_iou)

    detections: list[DetectedBox] = []
    for idx in keep_indices:
        cid = int(kept_cls[idx])
        label = COCO_ANIMAL_CLASSES.get(cid, "teddy bear" if cid == COCO_TEDDY_BEAR_CLASS else f"coco_{cid}")
        bx = kept_boxes[idx]
        detections.append(
            DetectedBox(
                class_id=cid,
                label=label,
                raw_score=round(float(kept_confs[idx]), 4),
                bbox=(round(float(bx[0]), 2), round(float(bx[1]), 2), round(float(bx[2]), 2), round(float(bx[3]), 2)),
            )
        )
    return detections


def _extract_crop_embedding_b64(cls_sess: ort.InferenceSession, crop_rgb: Image.Image) -> str:
    resized = crop_rgb.resize((224, 224), Image.Resampling.BILINEAR)
    arr = (np.asarray(resized, dtype=np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
    blob = np.ascontiguousarray(np.transpose(arr, (2, 0, 1))[None, ...], dtype=np.float32)
    outputs = cls_sess.run(None, {cls_sess.get_inputs()[0].name: blob})
    if len(outputs) < 2:
        return ""
    unit_vec = l2_normalize_embedding(outputs[1][0])
    return encode_embedding_f16_b64(unit_vec)


def _classify_animal_crop(
    cls_sess: ort.InferenceSession,
    pil_rgb: Image.Image,
    bbox: tuple[float, float, float, float],
    margin_ratio: float,
    temperature: float,
) -> tuple[float, float, float, Image.Image, Image.Image, str]:
    w, h = pil_rgb.size
    x1, y1, x2, y2 = bbox
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    tx1, ty1 = max(0, round(x1)), max(0, round(y1))
    tx2, ty2 = min(w, round(x2)), min(h, round(y2))
    tight_crop = pil_rgb.crop((tx1, ty1, tx2, ty2)) if tx2 > tx1 and ty2 > ty1 else pil_rgb

    cx1 = max(0, round(x1 - margin_ratio * bw))
    cy1 = max(0, round(y1 - margin_ratio * bh))
    cx2 = min(w, round(x2 + margin_ratio * bw))
    cy2 = min(h, round(y2 + margin_ratio * bh))
    context_crop = pil_rgb.crop((cx1, cy1, cx2, cy2)) if cx2 > cx1 and cy2 > cy1 else pil_rgb

    resized = context_crop.resize((224, 224), Image.Resampling.BILINEAR)
    arr = (np.asarray(resized, dtype=np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
    blob = np.ascontiguousarray(np.transpose(arr, (2, 0, 1))[None, ...], dtype=np.float32)
    outputs = cls_sess.run(None, {cls_sess.get_inputs()[0].name: blob})
    logits = outputs[0][0]
    emb_b64 = ""
    if len(outputs) >= 2:
        emb_b64 = encode_embedding_f16_b64(l2_normalize_embedding(outputs[1][0]))

    scaled = logits / max(0.05, float(temperature))
    scaled = scaled - scaled.max()
    probs = np.exp(scaled) / np.exp(scaled).sum()
    p_cat = float(probs[_IMAGENET_CAT_SLICE].sum())
    p_dog = float(probs[_IMAGENET_DOG_SLICE].sum())
    p_teddy = float(probs[_IMAGENET_TEDDY_INDEX])
    return p_cat, p_dog, p_teddy, tight_crop, context_crop, emb_b64


from petcare.vision.species_taxonomy import COAT_PROFILE_BUCKETS


def _extract_foreground_features(tight_crop: Image.Image) -> tuple[tuple[float, ...], ImageDescriptor | None]:
    w, h = tight_crop.size
    cw, ch = max(1, round(w * 0.72)), max(1, round(h * 0.72))
    lx, ty = (w - cw) // 2, (h - ch) // 2
    inner = tight_crop.crop((lx, ty, lx + cw, ty + ch)).resize((64, 64), Image.Resampling.BILINEAR)
    px = list(inner.get_flattened_data() if hasattr(inner, "get_flattened_data") else inner.getdata())
    counts = {k: 0 for k in COAT_PROFILE_BUCKETS}
    for r, g, b in px:
        hi, lo = max(r, g, b), min(r, g, b)
        chroma = hi - lo
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum < 52 and chroma < 42:
            counts["black_dark"] += 1
        elif lum > 202 and chroma < 30:
            counts["white_light"] += 1
        elif chroma < 20:
            counts["gray_silver"] += 1
        elif r >= b + 18 and r >= g - 4 and g >= b - 10:
            if lum > 158 and chroma < 68:
                counts["cream_tan"] += 1
            elif (r >= 95 and r > b * 1.42 and (g - b) >= 8) or (r > 132 and (g - b) >= 10):
                counts["orange_gold"] += 1
            else:
                counts["brown"] += 1
        else:
            counts["other"] += 1
    denom = max(1, len(px))
    fg_coat = tuple(round(counts[k] / denom, 5) for k in COAT_PROFILE_BUCKETS)
    if min(tight_crop.size) < 16:
        return fg_coat, None
    buf = BytesIO()
    tight_crop.save(buf, format="JPEG", quality=88)
    fg_desc = describe_image(buf.getvalue())
    return fg_coat, fg_desc


def analyze_pet_image(
    normalized_image_bytes: bytes,
    *,
    flat_pixel_ratio: float = 0.0,
) -> SpeciesGateDecision:
    """Run local object detection and calibrated species identification on normalized RGB/JPEG bytes."""
    t0 = time.perf_counter()
    try:
        det_sess, cls_sess, cal = _RUNTIME.load()
    except Exception:
        return SpeciesGateDecision(
            subject_status=SUBJECT_GATE_UNAVAILABLE,
            verified_species=None,
            detail_reason="local_model_unavailable",
            animal_count=0,
            primary_bbox=None,
            detector_label=None,
            detector_raw_score=None,
            calibrated_cat_prob=None,
            calibrated_dog_prob=None,
            candidate_species_support=frozenset(),
            foreground_coat_profile=(),
            foreground_descriptor=None,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    with Image.open(BytesIO(normalized_image_bytes)) as src:
        pil_rgb = ImageOps.exif_transpose(src).convert("RGB")

    if flat_pixel_ratio > float(cal["max_flat_pixel_ratio"]):
        return SpeciesGateDecision(
            subject_status=SUBJECT_NO_RELIABLE_ANIMAL,
            verified_species=None,
            detail_reason="non_photographic_or_low_texture",
            animal_count=0,
            primary_bbox=None,
            detector_label=None,
            detector_raw_score=None,
            calibrated_cat_prob=None,
            calibrated_dog_prob=None,
            candidate_species_support=frozenset(),
            foreground_coat_profile=(),
            foreground_descriptor=None,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    min_anim_score = float(cal["detector_animal_min_score"])
    min_toy_score = float(cal["detector_toy_min_score"])
    detections = _run_yolox_detector(
        det_sess,
        pil_rgb,
        min_score=min(min_anim_score, min_toy_score),
        nms_iou=float(cal["nms_iou_threshold"]),
    )

    raw_animals = [
        d for d in detections
        if d.class_id in COCO_ANIMAL_CLASSES and d.raw_score >= min_anim_score
    ]
    animals = _collapse_concentric_animal_boxes(
        raw_animals,
        containment_thr=float(cal["nested_box_containment_threshold"]),
        center_shift_max=float(cal["nested_box_center_shift_max"]),
    )
    toys = [
        d for d in detections
        if d.class_id == COCO_TEDDY_BEAR_CLASS and d.raw_score >= min_toy_score
    ]

    if len(animals) == 0:
        reason = "stuffed_toy_or_figurine" if toys else "no_animal_detected"
        top_toy = toys[0] if toys else None
        return SpeciesGateDecision(
            subject_status=SUBJECT_NO_RELIABLE_ANIMAL,
            verified_species=None,
            detail_reason=reason,
            animal_count=0,
            primary_bbox=top_toy.bbox if top_toy else None,
            detector_label=top_toy.label if top_toy else None,
            detector_raw_score=top_toy.raw_score if top_toy else None,
            calibrated_cat_prob=None,
            calibrated_dog_prob=None,
            candidate_species_support=frozenset(),
            foreground_coat_profile=(),
            foreground_descriptor=None,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    if len(animals) >= 2:
        return SpeciesGateDecision(
            subject_status=SUBJECT_MULTIPLE_ANIMALS,
            verified_species=None,
            detail_reason="multiple_animals_detected",
            animal_count=len(animals),
            primary_bbox=animals[0].bbox,
            detector_label=animals[0].label,
            detector_raw_score=animals[0].raw_score,
            calibrated_cat_prob=None,
            calibrated_dog_prob=None,
            candidate_species_support=frozenset(),
            foreground_coat_profile=(),
            foreground_descriptor=None,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    primary = animals[0]
    p_cat, p_dog, p_teddy, tight_crop, _ctx_crop, emb_b64 = _classify_animal_crop(
        cls_sess,
        pil_rgb,
        primary.bbox,
        margin_ratio=float(cal["crop_context_margin_ratio"]),
        temperature=float(cal["temperature"]),
    )

    if p_teddy >= 0.45 and p_teddy > max(p_cat, p_dog):
        return SpeciesGateDecision(
            subject_status=SUBJECT_NO_RELIABLE_ANIMAL,
            verified_species=None,
            detail_reason="stuffed_toy_or_figurine",
            animal_count=0,
            primary_bbox=primary.bbox,
            detector_label="teddy bear",
            detector_raw_score=primary.raw_score,
            calibrated_cat_prob=round(p_cat, 4),
            calibrated_dog_prob=round(p_dog, 4),
            candidate_species_support=frozenset(),
            foreground_coat_profile=(),
            foreground_descriptor=None,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )

    fg_coat, fg_desc = _extract_foreground_features(tight_crop)
    fg_lab_hist, fg_lab_coat7 = compute_foreground_lab_coat(pil_rgb, primary.bbox)
    min_prob = float(cal["min_calibrated_species_prob"])
    min_margin = float(cal["min_species_margin"])

    if primary.class_id not in (15, 16):
        if max(p_cat, p_dog) < min_prob:
            return SpeciesGateDecision(
                subject_status=SUBJECT_OTHER_ANIMAL,
                verified_species=None,
                detail_reason="unsupported_other_animal",
                animal_count=1,
                primary_bbox=primary.bbox,
                detector_label=primary.label,
                detector_raw_score=primary.raw_score,
                calibrated_cat_prob=round(p_cat, 4),
                calibrated_dog_prob=round(p_dog, 4),
                candidate_species_support=frozenset(),
                foreground_coat_profile=fg_coat,
                foreground_descriptor=fg_desc,
                inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                foreground_embedding_b64=emb_b64,
                foreground_lab_histogram=fg_lab_hist,
                foreground_lab_coat_profile=fg_lab_coat7,
            )
        support = set()
        if p_cat >= 0.25:
            support.add("cat")
        if p_dog >= 0.25:
            support.add("dog")
        return SpeciesGateDecision(
            subject_status=SUBJECT_AMBIGUOUS,
            verified_species=None,
            detail_reason="stage_disagreement",
            animal_count=1,
            primary_bbox=primary.bbox,
            detector_label=primary.label,
            detector_raw_score=primary.raw_score,
            calibrated_cat_prob=round(p_cat, 4),
            calibrated_dog_prob=round(p_dog, 4),
            candidate_species_support=frozenset(support),
            foreground_coat_profile=fg_coat,
            foreground_descriptor=fg_desc,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            foreground_embedding_b64=emb_b64,
            foreground_lab_histogram=fg_lab_hist,
            foreground_lab_coat_profile=fg_lab_coat7,
        )

    det_species = "cat" if primary.class_id == 15 else "dog"
    crop_species = "cat" if p_cat >= p_dog else "dog"
    top_prob = max(p_cat, p_dog)
    margin = abs(p_cat - p_dog)

    support_set = {det_species}
    if p_cat >= 0.25:
        support_set.add("cat")
    if p_dog >= 0.25:
        support_set.add("dog")

    if det_species != crop_species:
        return SpeciesGateDecision(
            subject_status=SUBJECT_AMBIGUOUS,
            verified_species=None,
            detail_reason="stage_disagreement",
            animal_count=1,
            primary_bbox=primary.bbox,
            detector_label=primary.label,
            detector_raw_score=primary.raw_score,
            calibrated_cat_prob=round(p_cat, 4),
            calibrated_dog_prob=round(p_dog, 4),
            candidate_species_support=frozenset(support_set),
            foreground_coat_profile=fg_coat,
            foreground_descriptor=fg_desc,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            foreground_embedding_b64=emb_b64,
            foreground_lab_histogram=fg_lab_hist,
            foreground_lab_coat_profile=fg_lab_coat7,
        )

    if top_prob < min_prob or margin < min_margin:
        return SpeciesGateDecision(
            subject_status=SUBJECT_AMBIGUOUS,
            verified_species=None,
            detail_reason="low_species_confidence",
            animal_count=1,
            primary_bbox=primary.bbox,
            detector_label=primary.label,
            detector_raw_score=primary.raw_score,
            calibrated_cat_prob=round(p_cat, 4),
            calibrated_dog_prob=round(p_dog, 4),
            candidate_species_support=frozenset(support_set),
            foreground_coat_profile=fg_coat,
            foreground_descriptor=fg_desc,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            foreground_embedding_b64=emb_b64,
            foreground_lab_histogram=fg_lab_hist,
            foreground_lab_coat_profile=fg_lab_coat7,
        )

    if det_species == "cat":
        return SpeciesGateDecision(
            subject_status=SUBJECT_ONE_CAT,
            verified_species="cat",
            detail_reason="verified_single_cat",
            animal_count=1,
            primary_bbox=primary.bbox,
            detector_label="cat",
            detector_raw_score=primary.raw_score,
            calibrated_cat_prob=round(p_cat, 4),
            calibrated_dog_prob=round(p_dog, 4),
            candidate_species_support=frozenset({"cat"}),
            foreground_coat_profile=fg_coat,
            foreground_descriptor=fg_desc,
            inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            foreground_embedding_b64=emb_b64,
            foreground_lab_histogram=fg_lab_hist,
            foreground_lab_coat_profile=fg_lab_coat7,
        )

    return SpeciesGateDecision(
        subject_status=SUBJECT_ONE_DOG,
        verified_species="dog",
        detail_reason="verified_single_dog",
        animal_count=1,
        primary_bbox=primary.bbox,
        detector_label="dog",
        detector_raw_score=primary.raw_score,
        calibrated_cat_prob=round(p_cat, 4),
        calibrated_dog_prob=round(p_dog, 4),
        candidate_species_support=frozenset({"dog"}),
        foreground_coat_profile=fg_coat,
        foreground_descriptor=fg_desc,
        inference_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        foreground_embedding_b64=emb_b64,
        foreground_lab_histogram=fg_lab_hist,
        foreground_lab_coat_profile=fg_lab_coat7,
    )


def enrich_descriptor_with_local_vision(
    normalized_image_bytes: bytes,
    descriptor: ImageDescriptor,
) -> ImageDescriptor:
    """Attach versioned 1280-D foreground embedding and white-balanced CIE-Lab coat profile."""
    if descriptor.flat_pixel_ratio > 0.68:
        return replace(
            descriptor,
            embedding_version=EMBEDDING_VERSION,
            embedding_b64="",
            fg_lab_version=FG_LAB_VERSION,
            fg_lab_histogram=(),
            fg_coat_profile=(),
            fg_bbox=None,
        )

    gate = analyze_pet_image(normalized_image_bytes, flat_pixel_ratio=descriptor.flat_pixel_ratio)
    if gate.subject_status == SUBJECT_GATE_UNAVAILABLE:
        return descriptor

    if gate.foreground_embedding_b64 and gate.foreground_lab_histogram:
        return replace(
            descriptor,
            embedding_version=EMBEDDING_VERSION,
            embedding_b64=gate.foreground_embedding_b64,
            fg_lab_version=FG_LAB_VERSION,
            fg_lab_histogram=gate.foreground_lab_histogram,
            fg_coat_profile=gate.foreground_lab_coat_profile,
            fg_bbox=gate.primary_bbox,
        )

    # Catalog fallback when an enrolled single-pet close-up has no detector box and is not multi-pet/toy
    if gate.animal_count == 0 and gate.detail_reason == "no_animal_detected":
        try:
            _det_sess, cls_sess, _cal = _RUNTIME.load()
            with Image.open(BytesIO(normalized_image_bytes)) as src:
                pil_rgb = ImageOps.exif_transpose(src).convert("RGB")
            w, h = pil_rgb.size
            inset_box = (round(w * 0.08, 2), round(h * 0.08, 2), round(w * 0.92, 2), round(h * 0.92, 2))
            crop = pil_rgb.crop((round(w * 0.08), round(h * 0.08), round(w * 0.92), round(h * 0.92)))
            emb_b64 = _extract_crop_embedding_b64(cls_sess, crop)
            lab_hist, lab_coat7 = compute_foreground_lab_coat(pil_rgb, inset_box)
            return replace(
                descriptor,
                embedding_version=EMBEDDING_VERSION,
                embedding_b64=emb_b64,
                fg_lab_version=FG_LAB_VERSION,
                fg_lab_histogram=lab_hist,
                fg_coat_profile=lab_coat7,
                fg_bbox=inset_box,
            )
        except Exception:
            return descriptor

    return replace(
        descriptor,
        embedding_version=EMBEDDING_VERSION,
        embedding_b64="",
        fg_lab_version=FG_LAB_VERSION,
        fg_lab_histogram=(),
        fg_coat_profile=(),
        fg_bbox=gate.primary_bbox,
    )


def get_model_manifest_summary() -> dict[str, Any]:
    """Return auditable metadata for the bundled local ONNX vision models."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
