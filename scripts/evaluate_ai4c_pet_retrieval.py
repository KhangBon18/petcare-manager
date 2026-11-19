#!/usr/bin/env python3
"""Repeatable CLI for building Manifest v3 and running the frozen AI-4.0c 4-way retrieval ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.vision.ai4c_benchmark import (  # noqa: E402
    DEFAULT_MANIFEST_V3_PATH,
    build_ai4c_manifest_v3,
    render_ai4c_markdown_report,
    run_ai4c_evaluation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_V3_PATH,
        help="Path to write Manifest v3 JSON.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs" / "assets" / "vision-ai4" / "ai4_0c_evaluation.json",
        help="Path to write machine-readable AI-4.0c evaluation JSON.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs" / "AI4_0C_EVALUATION_REPORT.md",
        help="Path to write human-readable AI-4.0c Markdown report.",
    )
    args = parser.parse_args(argv)

    manifest_v3 = build_ai4c_manifest_v3()
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest_v3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = run_ai4c_evaluation(manifest_v3)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = render_ai4c_markdown_report(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(md, encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

