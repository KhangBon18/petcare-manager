#!/usr/bin/env python3
"""CLI for AI-4.0e real identity dataset intake validation and final release readiness QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare.vision.ai4e_validation import (  # noqa: E402
    DEFAULT_MANIFEST_V4_PATH,
    build_real_identity_manifest_v4,
    render_ai4e_final_qa_markdown,
    run_ai4e_final_evaluation,
    validate_real_identity_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_V4_PATH,
        help="Path to manifest_v4_identities.json (created from verified repo inventory if absent).",
    )
    parser.add_argument(
        "--rebuild-default-manifest",
        action="store_true",
        help="Rebuild the baseline manifest_v4_identities.json from verified repository files.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate manifest integrity, anti-crop independence, and split disjointness only.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs" / "assets" / "vision-ai4" / "ai4_0e_final_evaluation.json",
        help="Path to write machine-readable AI-4.0e evaluation JSON.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs" / "AI4_0E_FINAL_VISION_QA.md",
        help="Path to write human-readable AI-4.0e Final Vision QA report.",
    )
    args = parser.parse_args(argv)

    if args.rebuild_default_manifest or not args.manifest.is_file():
        manifest_v4 = build_real_identity_manifest_v4()
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest_v4, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        manifest_v4 = json.loads(args.manifest.read_text(encoding="utf-8"))

    intake = validate_real_identity_manifest(manifest_v4)
    if args.validate_only:
        print(json.dumps(intake, ensure_ascii=False, indent=2))
        return 0 if intake["valid"] else 1

    if not intake["valid"]:
        print(json.dumps(intake, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    report = run_ai4e_final_evaluation(manifest_v4)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = render_ai4e_final_qa_markdown(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(md, encoding="utf-8")

    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
