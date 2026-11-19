#!/usr/bin/env python3
"""Repeatable CLI for building Manifest v2 and measuring AI-4.0b local pet detection & species recognition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.vision.ai4b_benchmark import (  # noqa: E402
    DEFAULT_MANIFEST_V2_PATH,
    build_ai4b_manifest_v2,
    render_ai4b_markdown_report,
    run_ai4b_evaluation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_V2_PATH,
        help="Path to write Manifest v2 JSON.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs" / "assets" / "vision-ai4" / "ai4_0b_evaluation.json",
        help="Path to write machine-readable AI-4.0b evaluation JSON.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs" / "AI4_0B_EVALUATION_REPORT.md",
        help="Path to write human-readable AI-4.0b Markdown report.",
    )
    args = parser.parse_args(argv)

    manifest_v2 = build_ai4b_manifest_v2()
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest_v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = run_ai4b_evaluation(manifest_v2)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = render_ai4b_markdown_report(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(md, encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
