#!/usr/bin/env python3
"""Repeatable CLI for building the AI-4.0a dataset manifest and measuring image-matching metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.vision.ai4_benchmark import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    build_ai4a_manifest,
    render_ai4a_markdown_report,
    run_ai4a_evaluation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to write/update the reproducible dataset manifest JSON.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs" / "assets" / "vision-ai4" / "ai4_0a_evaluation.json",
        help="Path to write machine-readable evaluation metrics JSON.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs" / "AI4_0A_EVALUATION_REPORT.md",
        help="Path to write human-readable Markdown evaluation report.",
    )
    args = parser.parse_args(argv)

    manifest = build_ai4a_manifest()
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = run_ai4a_evaluation(manifest)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = render_ai4a_markdown_report(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(md, encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

