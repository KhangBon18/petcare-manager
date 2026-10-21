"""Lightweight, local visual descriptors for ranking similar pet photos.

This is an image-similarity aid rather than a trained species classifier. It
uses a color histogram and a small grayscale grid, so it works without a cloud
service and does not claim to identify an animal by itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from petcare.services.exceptions import ValidationError


MAX_PIXELS = 20_000_000
HISTOGRAM_SIZE = 32
GRID_SIZE = 16
VISUAL_HASH_VERSION = 1
VISUAL_HASH_BITS = 64
_HISTOGRAM_WEIGHT = 0.39
_GRID_WEIGHT = 0.22
_UINT64_MASK = (1 << 64) - 1


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
    if red > 85 and red > green * 1.22 and red > blue * 1.18:
        return "nâu"
    if green > red * 1.18 and green > blue * 1.08:
        return "xanh lá"
    if blue > red * 1.15 and blue > green * 1.08:
        return "xanh dương"
    if red > 140 and blue > 110 and abs(red - blue) < 75:
        return "hồng"
    return "nâu"


def describe_image(image_bytes: bytes) -> ImageDescriptor:
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
    return ImageDescriptor(
        width, height, normalized_histogram, grid, dominant, center_histogram, visual_hash
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
        return ImageDescriptor(
            int(data["width"]),
            int(data["height"]),
            tuple(float(item) for item in data["color_histogram"]),
            tuple(int(item) for item in data["grayscale_grid"]),
            tuple(str(item) for item in data.get("dominant_colors", ())),
            tuple(float(item) for item in data.get("center_color_histogram", ())),
            str(data.get("visual_hash", "")),
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
