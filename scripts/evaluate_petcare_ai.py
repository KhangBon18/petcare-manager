#!/usr/bin/env python3
"""Run the 84-case PetCare AI evaluation benchmark on the isolated QA database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare import create_app  # noqa: E402
from petcare.ai.evaluation import run_benchmark_evaluation  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate PetCare AI benchmark suite.")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--skip-init", action="store_true", help="Skip schema init/seed when already seeded.")
    args = parser.parse_args()

    if not args.skip_init:
        initialize_database()
        seed_database()

    app = create_app({"TESTING": True})
    with app.app_context():
        report = run_benchmark_evaluation()

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    metrics = report["metrics"]
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    failed = [c for c in report["cases"] if not c["passed"]]
    if failed:
        print(f"\nFAILED CASES ({len(failed)}):", file=sys.stderr)
        for item in failed:
            print(f"  - {item['case_id']} ({item['category']}): {item['turns']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
