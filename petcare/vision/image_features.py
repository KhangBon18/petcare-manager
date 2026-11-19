"""Lightweight, local visual descriptors for ranking similar pet photos.

This is an image-similarity aid rather than a trained species classifier. It
uses a color histogram and a small grayscale grid, so it works without a cloud
service and does not claim to identify an animal by itself.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from petcare.services.exceptions import ValidationError
from petcare.vision.coat_color_lab import (
    EMBEDDING_VERSION,
    FG_LAB_VERSION,
    decode_embedding_f16_b64,
    validate_lab_histogram,
)
from petcare.vision.species_taxonomy import COAT_PROFILE_BUCKETS


MAX_PIXELS = 20_000_000
HISTOGRAM_SIZE = 32
GRID_SIZE = 16
VISUAL_HASH_VERSION = 1
VISUAL_HASH_BITS = 64
_HISTOGRAM_WEIGHT = 0.39
_GRID_WEIGHT = 0.22
_UINT64_MASK = (1 << 64) - 1
_HEX64_RE_LEN = 16
_SHA256_HEX_LEN = 64
_DCT_COS = tuple(
    tuple(math.cos((2 * x + 1) * u * math.pi / 64.0) for u in range(8))
    for x in range(32)
)


def _make_visual_projections():
    """Build versioned projections with a PRNG independent of Python's random module."""
    state = 0x504554434152455F
    projections = []
    for _ in range(VISUAL_HASH_BITS):
        projection = []
        for _ in range(2 * HISTOGRAM_SIZE + GRID_SIZE**2):
            state = (state + 0x9E3779B97F4A7C15) & _UINT64_MASK
            value = state
            value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _UINT64_MASK
            value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _UINT64_MASK
            value ^= value >> 31
            projection.append(1 if value & 1 else -1)
        projections.append(tuple(projection))
    return tuple(projections)


_VISUAL_PROJECTIONS = _make_visual_projections()


def _flatten_pixels(image: Image.Image):
    # Pillow 12 deprecates getdata(); retain a fallback for the declared 10.x range.
    flatten = getattr(image, "get_flattened_data", None)
    return flatten() if flatten else image.getdata()


class InvalidImage(ValidationError):
    """Raised when uploaded bytes are not a safe supported image."""


@dataclass(frozen=True, slots=True)
class ImageDescriptor:
    width: int
    height: int
    color_histogram: tuple[float, ...]
    grayscale_grid: tuple[int, ...]
    dominant_colors: tuple[str, ...]
    # New descriptors retain an extra center crop so backgrounds have less
    # influence. Empty means a legacy descriptor; comparisons then use globals.
    center_color_histogram: tuple[float, ...] = ()
    # Version 1 is a 64-bit SimHash used only to find likely image candidates.
    # The full descriptor remains authoritative for ranking.
    visual_hash: str = ""
    # AI-4.0a cryptographic & perceptual signatures + backdrop-masked coat profile.
    raw_sha256: str = ""
    normalized_sha256: str = ""
    dhash64: str = ""
    phash64: str = ""
    subject_coat_profile: tuple[float, ...] = ()
    flat_pixel_ratio: float = 0.0
    # AI-4.0c versioned 1280-D foreground visual embedding + white-balanced CIE-Lab coat profile.
    embedding_version: str = ""
    embedding_b64: str = ""
    fg_lab_version: str = ""
    fg_lab_histogram: tuple[float, ...] = ()
    fg_coat_profile: tuple[float, ...] = ()
    fg_bbox: tuple[float, float, float, float] | None = None


def sha256_hex(data: bytes) -> str:
    """Return lowercase 64-character SHA-256 hex digest for image byte comparison."""
    return hashlib.sha256(data).hexdigest()


def _compute_dhash64(image: Image.Image) -> str:
    gray = list(_flatten_pixels(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)))
    bits = 0
    for r in range(8):
        row = gray[r * 9 : (r + 1) * 9]
        for c in range(8):
            bits = (bits << 1) | int(row[c] > row[c + 1])
    return f"{bits:016x}"


def _compute_phash64(image: Image.Image) -> str:
    px = list(_flatten_pixels(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)))
    tmp = [[0.0] * 8 for _ in range(32)]
    for y in range(32):
        row = px[y * 32 : (y + 1) * 32]
        for u in range(8):
            tmp[y][u] = sum(row[x] * _DCT_COS[x][u] for x in range(32))
    coeffs: list[float] = []
    for v in range(8):
        for u in range(8):
            if u == 0 and v == 0:
                continue
            coeffs.append(sum(tmp[y][u] * _DCT_COS[y][v] for y in range(32)))
    median = sorted(coeffs)[len(coeffs) // 2]
    bits = 0
    for val in coeffs:
        bits = (bits << 1) | int(val > median)
    return f"{bits:016x}"


def _compute_flat_pixel_ratio(image: Image.Image) -> float:
    px = list(_flatten_pixels(image.convert("L").resize((128, 128), Image.Resampling.BILINEAR)))
    near_zero = 0
    total = 128 * 127
    for y in range(128):
        row = px[y * 128 : (y + 1) * 128]
        for x in range(127):
            if abs(row[x] - row[x + 1]) <= 1:
                near_zero += 1
    return round(near_zero / total, 5)


def _compute_subject_coat_profile(image: Image.Image) -> tuple[float, ...]:
    """Estimate foreground subject coat-color distribution while masking uniform studio backdrops."""
    width, height = image.size
    small = image.resize((48, 48), Image.Resampling.BILINEAR)
    spx = list(_flatten_pixels(small))
    border = [
        spx[y * 48 + x]
        for y in range(48)
        for x in range(48)
        if x < 4 or x >= 44 or y < 4 or y >= 44
    ]
    bg_r = sum(p[0] for p in border) / len(border)
    bg_g = sum(p[1] for p in border) / len(border)
    bg_b = sum(p[2] for p in border) / len(border)

    cw, ch = max(1, round(width * 0.56)), max(1, round(height * 0.56))
    lx, ty = (width - cw) // 2, (height - ch) // 2
    crop = image.crop((lx, ty, lx + cw, ty + ch)).resize((64, 64), Image.Resampling.BILINEAR)
    px = list(_flatten_pixels(crop))

    def _accumulate(mask_backdrop: bool) -> tuple[dict[str, int], int]:
        counts = {k: 0 for k in COAT_PROFILE_BUCKETS}
        kept = 0
        for r, g, b in px:
            if (
                mask_backdrop
                and abs(r - bg_r) < 16
                and abs(g - bg_g) < 16
                and abs(b - bg_b) < 16
            ):
                continue
            kept += 1
            hi, lo = max(r, g, b), min(r, g, b)
            chroma = hi - lo
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum < 52 and chroma < 42:
                counts["black_dark"] += 1
            elif lum > 202 and chroma < 30:
                counts["white_light"] += 1
            elif chroma < 24:
                counts["gray_silver"] += 1
            elif r > b + 32 and r >= g and g >= b - 12:
                if lum > 175 and chroma < 65:
                    counts["cream_tan"] += 1
                elif r > 132 and (g - b) >= 10:
                    counts["orange_gold"] += 1
                else:
                    counts["brown"] += 1
            else:
                counts["other"] += 1
        return counts, kept

    counts, kept = _accumulate(mask_backdrop=True)
    if kept < 200:
        counts, kept = _accumulate(mask_backdrop=False)
    denom = max(1, kept)
    return tuple(round(counts[k] / denom, 5) for k in COAT_PROFILE_BUCKETS)


compute_subject_coat_profile = _compute_subject_coat_profile


def hamming_hex64(left: str | None, right: str | None) -> int | None:
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or len(left) != _HEX64_RE_LEN
        or len(right) != _HEX64_RE_LEN
    ):
        return None
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return None


def compare_coat_profiles(
    left: tuple[float, ...] | list[float],
    right: tuple[float, ...] | list[float],
) -> float | None:
    if len(left) != len(COAT_PROFILE_BUCKETS) or len(right) != len(COAT_PROFILE_BUCKETS):
        return None
    return max(0.0, min(1.0, sum(min(float(a), float(b)) for a, b in zip(left, right))))


def _color_name(red: int, green: int, blue: int) -> str:
    high, low = max(red, green, blue), min(red, green, blue)
    brightness = (red + green + blue) // 3
    if high - low < 28:
        if brightness < 55:
            return "đen"
        if brightness > 218:
            return "trắng"
        return "xám"
    if red > 155 and green > 90 and blue < 105:
        return "vàng"
    if red > 135 and green > 55 and red > green * 1.25 and blue < 125:
        return "cam"
    if red > 175 and green > 150 and blue > 120 and red >= green >= blue and red - blue >= 18:
        return "kem"
    if red > 85 and red > green * 1.22 and red > blue * 1.18:
        return "nâu"
    if green > red * 1.18 and green > blue * 1.08:
        return "xanh lá"
    if blue > red * 1.15 and blue > green * 1.08:
        return "xanh dương"
    if red > 140 and blue > 110 and abs(red - blue) < 75:
        return "hồng"
    return "nâu"


def describe_image(
    image_bytes: bytes,
    *,
    raw_sha256: str = "",
    normalized_sha256: str = "",
) -> ImageDescriptor:
    """Decode, normalize and describe a supported image using Pillow only."""
    if not image_bytes:
        raise InvalidImage("Vui lòng chọn một ảnh hợp lệ.")
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidImage("Chỉ nhận ảnh JPEG, PNG hoặc WebP.")
            if source.width * source.height > MAX_PIXELS:
                raise InvalidImage("Ảnh có kích thước quá lớn; hãy chọn ảnh nhỏ hơn.")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("Không đọc được ảnh. Hãy chọn một tệp ảnh hợp lệ.") from exc

    width, height = image.size
    normalized_histogram, _, _ = _color_histogram(image)
    center_width = max(1, round(width * 0.6))
    center_height = max(1, round(height * 0.6))
    left = (width - center_width) // 2
    top = (height - center_height) // 2
    center_histogram, center_color_counts, center_total = _color_histogram(
        image.crop((left, top, left + center_width, top + center_height))
    )
    grayscale = image.convert("L").resize((GRID_SIZE, GRID_SIZE), Image.Resampling.BILINEAR)
    grid = tuple(_flatten_pixels(grayscale))
    dominant = tuple(
        color for color, count in sorted(
            center_color_counts.items(), key=lambda pair: pair[1], reverse=True
        )[:3]
        if count / center_total >= 0.08
    )
    visual_hash = _visual_hash(normalized_histogram, center_histogram, grid)
    clean_norm_sha = normalized_sha256 if len(normalized_sha256) == _SHA256_HEX_LEN else sha256_hex(image_bytes)
    clean_raw_sha = raw_sha256 if len(raw_sha256) == _SHA256_HEX_LEN else ""
    return ImageDescriptor(
        width,
        height,
        normalized_histogram,
        grid,
        dominant,
        center_histogram,
        visual_hash,
        clean_raw_sha,
        clean_norm_sha,
        _compute_dhash64(image),
        _compute_phash64(image),
        _compute_subject_coat_profile(image),
        _compute_flat_pixel_ratio(image),
    )


def _visual_hash(
    color_histogram: tuple[float, ...],
    center_color_histogram: tuple[float, ...],
    grayscale_grid: tuple[int, ...],
) -> str:
    """Return a deterministic locality-sensitive fingerprint for candidate lookup."""
    center = center_color_histogram or color_histogram
    features = [
        value**0.5 * _HISTOGRAM_WEIGHT**0.5
        for value in (*color_histogram, *center)
    ]
    mean = sum(grayscale_grid) / max(1, len(grayscale_grid))
    centered_grid = [value - mean for value in grayscale_grid]
    grid_norm = sum(value * value for value in centered_grid) ** 0.5
    if grid_norm:
        grid_scale = (_GRID_WEIGHT**0.5) / grid_norm
        features.extend(value * grid_scale for value in centered_grid)
    else:
        features.extend(0.0 for _ in centered_grid)

    fingerprint = 0
    for projection in _VISUAL_PROJECTIONS:
        dot = sum(value * direction for value, direction in zip(features, projection))
        fingerprint = (fingerprint << 1) | int(dot >= 0)
    return f"{fingerprint:016x}"


def visual_hash_bands(value: str | None) -> tuple[int, ...] | None:
    """Split a valid version 1 fingerprint into eight byte-sized LSH bands."""
    if not isinstance(value, str) or len(value) != VISUAL_HASH_BITS // 4:
        return None
    try:
        int(value, 16)
        return tuple(int(value[offset:offset + 2], 16) for offset in range(0, len(value), 2))
    except ValueError:
        return None


def _color_histogram(image: Image.Image):
    """Return normalized HSV bins and dominant-color counts for one image region."""
    sample = image.resize((96, 96), Image.Resampling.BILINEAR)
    histogram = [0] * HISTOGRAM_SIZE
    color_counts: dict[str, int] = {}
    rgb_pixels = _flatten_pixels(sample)
    hsv_pixels = _flatten_pixels(sample.convert("HSV"))
    for (red, green, blue), (hue, saturation, value) in zip(rgb_pixels, hsv_pixels):
        hue_bin = min(7, hue * 8 // 256)
        saturation_bin = int(saturation >= 48)
        value_bin = int(value >= 128)
        histogram[(hue_bin * 2 + saturation_bin) * 2 + value_bin] += 1
        name = _color_name(red, green, blue)
        color_counts[name] = color_counts.get(name, 0) + 1
    total = float(sum(histogram))
    return tuple(value / total for value in histogram), color_counts, total


def normalize_image_bytes(image_bytes: bytes) -> bytes:
    """Re-encode a supported image as a metadata-free, size-limited JPEG."""
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidImage("Chỉ nhận ảnh JPEG, PNG hoặc WebP.")
            if source.width * source.height > MAX_PIXELS:
                raise InvalidImage("Ảnh có kích thước quá lớn; hãy chọn ảnh nhỏ hơn.")
            image = ImageOps.exif_transpose(source)
            # JPEG camera uploads are usually already RGB. Avoid copying the
            # full-resolution pixel buffer just to convert RGB to RGB before
            # the bounded thumbnail. Indexed/grayscale/alpha sources still
            # convert first so thumbnail filtering and transparency behavior
            # remain unchanged.
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("Không đọc được ảnh. Hãy chọn một tệp ảnh hợp lệ.") from exc


def descriptor_to_json(descriptor: ImageDescriptor) -> str:
    return json.dumps(asdict(descriptor), ensure_ascii=False, separators=(",", ":"))


def descriptor_from_json(value: str | bytes | dict | None) -> ImageDescriptor | None:
    if not value:
        return None
    try:
        data = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
        raw_profile = data.get("subject_coat_profile", ())
        coat_profile = (
            tuple(float(item) for item in raw_profile)
            if isinstance(raw_profile, (list, tuple)) and len(raw_profile) == len(COAT_PROFILE_BUCKETS)
            else ()
        )
        emb_ver = str(data.get("embedding_version", "") or "")
        raw_emb_b64 = str(data.get("embedding_b64", "") or "")
        valid_emb = decode_embedding_f16_b64(
            raw_emb_b64, actual_version=emb_ver, expected_version=EMBEDDING_VERSION
        )
        clean_emb_b64 = raw_emb_b64 if valid_emb is not None else ""

        lab_ver = str(data.get("fg_lab_version", "") or "")
        raw_lab_hist = data.get("fg_lab_histogram", ())
        valid_lab_hist = (
            validate_lab_histogram(raw_lab_hist) if lab_ver == FG_LAB_VERSION else None
        )
        raw_fg_coat = data.get("fg_coat_profile", ())
        fg_coat = (
            tuple(float(item) for item in raw_fg_coat)
            if lab_ver == FG_LAB_VERSION
            and isinstance(raw_fg_coat, (list, tuple))
            and len(raw_fg_coat) == len(COAT_PROFILE_BUCKETS)
            else ()
        )
        raw_bbox = data.get("fg_bbox")
        fg_bbox: tuple[float, float, float, float] | None = None
        if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
            bx = tuple(float(v) for v in raw_bbox)
            if all(math.isfinite(v) for v in bx) and bx[2] > bx[0] and bx[3] > bx[1]:
                fg_bbox = bx

        return ImageDescriptor(
            int(data["width"]),
            int(data["height"]),
            tuple(float(item) for item in data["color_histogram"]),
            tuple(int(item) for item in data["grayscale_grid"]),
            tuple(str(item) for item in data.get("dominant_colors", ())),
            tuple(float(item) for item in data.get("center_color_histogram", ())),
            str(data.get("visual_hash", "")),
            str(data.get("raw_sha256", "")),
            str(data.get("normalized_sha256", "")),
            str(data.get("dhash64", "")),
            str(data.get("phash64", "")),
            coat_profile,
            float(data.get("flat_pixel_ratio", 0.0) or 0.0),
            emb_ver if (valid_emb is not None or emb_ver == EMBEDDING_VERSION) else "",
            clean_emb_b64,
            lab_ver if (valid_lab_hist is not None or lab_ver == FG_LAB_VERSION) else "",
            valid_lab_hist or (),
            fg_coat,
            fg_bbox,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def compare_images(left: ImageDescriptor, right: ImageDescriptor) -> float:
    """Return a deterministic 0..1 similarity score from color and structure."""
    if len(left.color_histogram) != len(right.color_histogram):
        return 0.0
    if len(left.grayscale_grid) != len(right.grayscale_grid):
        return 0.0
    global_color_similarity = sum(
        min(a, b) for a, b in zip(left.color_histogram, right.color_histogram)
    )
    if (
        left.center_color_histogram
        and len(left.center_color_histogram) == len(right.center_color_histogram)
    ):
        center_color_similarity = sum(
            min(a, b)
            for a, b in zip(left.center_color_histogram, right.center_color_histogram)
        )
        color_similarity = 0.5 * global_color_similarity + 0.5 * center_color_similarity
    else:
        # Old photo descriptors contain only the global histogram/grid.
        color_similarity = global_color_similarity
    structure_distance = sum(abs(a - b) for a, b in zip(left.grayscale_grid, right.grayscale_grid))
    structure_similarity = max(0.0, 1.0 - structure_distance / (255 * len(left.grayscale_grid)))
    return max(0.0, min(1.0, 0.78 * color_similarity + 0.22 * structure_similarity))


def compare_images_from_json(left: ImageDescriptor, value: str | bytes | dict | None) -> float | None:
    """Compare a stored JSON descriptor without allocating converted tuples.

    MySQL stores descriptors as JSON. Search reads many of them, so converting
    each JSON list into a second tuple before comparing it creates avoidable
    per-candidate work. The direct path keeps the same score and falls back to
    the compatibility decoder for unusual numeric encodings.
    """
    if not value:
        return None
    try:
        data = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        int(data["width"])
        int(data["height"])
        tuple(str(item) for item in data.get("dominant_colors", ()))
        color_histogram = data["color_histogram"]
        grayscale_grid = data["grayscale_grid"]
        center_histogram = data.get("center_color_histogram", ())
        if len(color_histogram) != len(left.color_histogram):
            return 0.0
        if len(grayscale_grid) != len(left.grayscale_grid):
            return 0.0

        global_color_similarity = sum(
            left_value if left_value < right_value else right_value
            for left_value, right_value in zip(left.color_histogram, color_histogram)
        )
        if center_histogram and len(center_histogram) == len(left.center_color_histogram):
            center_color_similarity = sum(
                left_value if left_value < right_value else right_value
                for left_value, right_value in zip(left.center_color_histogram, center_histogram)
            )
            color_similarity = 0.5 * global_color_similarity + 0.5 * center_color_similarity
        else:
            color_similarity = global_color_similarity
        structure_distance = sum(
            abs(left_value - int(right_value))
            for left_value, right_value in zip(left.grayscale_grid, grayscale_grid)
        )
    except (KeyError, TypeError, ValueError):
        candidate = descriptor_from_json(data)
        return compare_images(left, candidate) if candidate else None

    structure_similarity = max(0.0, 1.0 - structure_distance / (255 * len(left.grayscale_grid)))
    return max(0.0, min(1.0, 0.78 * color_similarity + 0.22 * structure_similarity))


def read_upload(upload: BinaryIO, max_bytes: int) -> bytes:
    """Read one uploaded file with a hard byte limit before decoding it."""
    data = upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidImage(f"Ảnh phải nhỏ hơn {max_bytes // (1024 * 1024)} MB.")
    if not data:
        raise InvalidImage("Vui lòng chọn một ảnh hợp lệ.")
    return data


def similarity_components(left, right):
    """Explain only the shortlisted descriptors, without changing ranking."""
    histogram = getattr(left, "color_histogram", ())
    if not right or len(histogram) != len(right.color_histogram) or not histogram:
        return None
    grid = getattr(left, "grayscale_grid", ())
    if not grid or len(grid) != len(right.grayscale_grid):
        return None
    color = sum(min(a, b) for a, b in zip(histogram, right.color_histogram))
    center = getattr(left, "center_color_histogram", ())
    if center and len(center) == len(right.center_color_histogram):
        color = (color + sum(min(a, b) for a, b in zip(center, right.center_color_histogram))) / 2
    structure = max(0, 1 - sum(abs(a - b) for a, b in zip(grid, right.grayscale_grid)) / (255 * len(grid)))
    return {"color": max(0, min(1, color)), "structure": structure}
