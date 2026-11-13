"""Evaluate local image similarity on bundled synthetic demo pet images.

Example: ``.venv/bin/python scripts/evaluate_demo_pet_image_retrieval.py \
  --output docs/assets/python-first-v2/image-retrieval-evaluation.json``

Labels are source-file identities known by construction. The result measures
near-duplicate retrieval under mild synthetic image transforms; it is not a
pet-identity, species, breed, or production-recall benchmark.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from petcare.vision.image_features import compare_images, describe_image
from petcare.vision.retrieval_evaluation import evaluate_rankings


IMAGE_ROOT = ROOT / "assets" / "demo" / "pets"
QUERY_VARIANTS = ("jpeg_resize", "mild_brightness", "center_crop")


def _jpeg_bytes(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    output = BytesIO()
    rgb.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def _variants(path: Path):
    with Image.open(path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
    small = original.copy()
    small.thumbnail((512, 512), Image.Resampling.LANCZOS)
    yield "jpeg_resize", _jpeg_bytes(small)
    yield "mild_brightness", _jpeg_bytes(ImageEnhance.Brightness(original).enhance(1.06))
    width, height = original.size
    inset_x, inset_y = max(1, round(width * 0.04)), max(1, round(height * 0.04))
    crop = original.crop((inset_x, inset_y, width - inset_x, height - inset_y))
    yield "center_crop", _jpeg_bytes(crop.resize((width, height), Image.Resampling.LANCZOS))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile / 100) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def evaluate() -> dict:
    sources = sorted(
        path for path in IMAGE_ROOT.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    if not sources:
        raise RuntimeError("No synthetic pet demo images were found.")
    descriptors = {path.name: describe_image(path.read_bytes()) for path in sources}
    rankings: dict[str, list[str]] = {}
    labels: dict[str, set[str]] = {}
    latencies_ms: list[float] = []
    preprocessing_ms: list[float] = []
    errors: list[dict[str, str]] = []

    for path in sources:
        for variant_name, image_bytes in _variants(path):
            query_id = f"{path.name}:{variant_name}"
            try:
                started = time.perf_counter()
                query = describe_image(image_bytes)
                preprocessing_ms.append((time.perf_counter() - started) * 1000)
                started = time.perf_counter()
                ranked = sorted(
                    (
                        (compare_images(query, descriptor), candidate_id)
                        for candidate_id, descriptor in descriptors.items()
                    ),
                    key=lambda pair: (-pair[0], pair[1]),
                )
                latencies_ms.append((time.perf_counter() - started) * 1000)
                rankings[query_id] = [candidate_id for _score, candidate_id in ranked]
                labels[query_id] = {path.name}
            except (OSError, ValueError) as exc:
                errors.append({"query_id": query_id, "error_type": type(exc).__name__})

    metrics = evaluate_rankings(rankings, labels, k=5) if rankings else None
    top_one = evaluate_rankings(rankings, labels, k=1) if rankings else None
    return {
        "evaluation_kind": "synthetic_demo_near_duplicate_retrieval",
        "dataset": {
            "source": "assets/demo/pets/README.md",
            "images": len(sources),
            "cats": sum(path.name.startswith("demo-cat-") for path in sources),
            "dogs": sum(path.name.startswith("demo-dog-") for path in sources),
            "query_variants_per_image": list(QUERY_VARIANTS),
            "queries_scored": len(rankings),
            "relevance_rule": "Exact source image file is relevant by construction.",
        },
        "metrics": None if metrics is None else {
            "precision_at_1": round(top_one.precision_at_k, 6),
            "precision_at_5": round(metrics.precision_at_k, 6),
            "recall_at_5": round(metrics.recall_at_k, 6),
            "mrr": round(metrics.mean_reciprocal_rank, 6),
        },
        "latency_ms": {
            "candidate_count": len(sources),
            "ranking_p50": round(statistics.median(latencies_ms), 3) if latencies_ms else None,
            "ranking_p95": round(_percentile(latencies_ms, 95), 3),
            "query_preprocess_p50": round(statistics.median(preprocessing_ms), 3) if preprocessing_ms else None,
            "error_rate": round(len(errors) / (len(rankings) + len(errors)), 6)
            if rankings or errors else 0.0,
        },
        "errors": errors,
        "limitations": [
            "Synthetic, repository-provided images only; no real customer photos were used.",
            "Near-duplicate source retrieval only; not pet identity, breed, species, or recognition accuracy.",
            "Ranking latency measures in-process descriptor comparison across this fixed local catalog; it excludes HTTP, database, storage, and concurrency costs.",
            "This script evaluates exhaustive descriptor ranking and does not measure approximate LSH candidate recall.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report.")
    args = parser.parse_args()
    report = evaluate()
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        destination = args.output if args.output.is_absolute() else ROOT / args.output
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
