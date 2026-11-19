#!/usr/bin/env python3
"""Repeatable CLI for running the AI-4.0d multi-photo gallery & crop-robust evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.vision.ai4d_benchmark import (  # noqa: E402
    render_ai4d_markdown_report,
    run_ai4d_evaluation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs" / "assets" / "vision-ai4" / "ai4_0d_evaluation.json",
        help="Path to write machine-readable AI-4.0d evaluation JSON.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs" / "AI4_0D_EVALUATION_REPORT.md",
        help="Path to write human-readable AI-4.0d Markdown evaluation report.",
    )
    args = parser.parse_args(argv)

    report = run_ai4d_evaluation()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = render_ai4d_markdown_report(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(md, encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
