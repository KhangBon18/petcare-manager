"""CLI runner for the Untouched AI-2.2 Final Safety & Generalization Evaluation (Step 3)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.demo import test_accounts as _test_accounts  # noqa: E402,F401

from petcare import create_app  # noqa: E402
from petcare.ai.final_safety_generalization_eval import (  # noqa: E402
    run_final_safety_generalization_evaluation,
)
from petcare.config import Config  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run untouched AI-2.2 final safety & generalization evaluation on an isolated _test DB."
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON report output path.")
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip schema init/seed when disposable QA _test DB is already seeded.",
    )
    args = parser.parse_args()

    test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
    if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
        raise SystemExit(
            "Refusing to run final evaluation outside an isolated _test database (set DB_NAME=PETCARE_TEST_DB_NAME=*_test)."
        )

    if not args.skip_init:
        initialize_database()
        seed_database()

    app = create_app({"TESTING": True, "AI_PROVIDER_APPROVED": False, "AI_TOOL_CALLING_ENABLED": False})
    with app.app_context():
        report = run_final_safety_generalization_evaluation()

    print(json.dumps(report["metrics"], indent=2, ensure_ascii=False))
    failed = [c for c in report["cases"] if not c["passed"]]
    print(f"\nFinal untouched hold-out non-passing cases ({len(failed)}/{report['metrics']['sample_sizes']['total_cases']}):")
    for item in failed:
        reasons = "; ".join(
            f"T{t['turn']}: {', '.join(t['failure_reasons'])}"
            for t in item["turns"]
            if not t["passed"]
        )
        print(f"  - [{item['case_id']}] ({item['category']}): {reasons}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

