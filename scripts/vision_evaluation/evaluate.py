#!/usr/bin/env python3
"""Score a Vision prediction JSON file without making provider requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from petcare.vision.evaluation import EvaluationInputError, evaluate_files, render_markdown  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate_files(args.manifest, args.predictions)
    except EvaluationInputError as exc:
        parser.error(str(exc))
    machine = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    human = render_markdown(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(machine, encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(human, encoding="utf-8")
    print(human, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
