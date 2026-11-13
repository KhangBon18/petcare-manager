"""CLI runner for the Independent Out-of-Distribution (OOD) PetCare AI Evaluation (Part B)."""

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
from petcare.ai.independent_evaluation import run_independent_ood_evaluation  # noqa: E402
from petcare.config import Config  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent OOD PetCare AI benchmark on an isolated _test DB.")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON report path.")
    parser.add_argument("--skip-init", action="store_true", help="Skip schema init/seed if QA _test DB is already seeded.")
    args = parser.parse_args()

    test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
    if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
        raise SystemExit(
            "Refusing to run evaluation outside an isolated _test database (set DB_NAME=PETCARE_TEST_DB_NAME=*_test)."
        )

    if not args.skip_init:
        initialize_database()
        seed_database()

    app = create_app({"TESTING": True, "AI_PROVIDER_APPROVED": False})
    with app.app_context():
        report = run_independent_ood_evaluation()

    print(json.dumps(report["metrics"], indent=2, ensure_ascii=False))
    print(f"\nFailed cases ({len(report['failures'])}/{report['metrics']['total_cases']}):")
    for fail in report["failures"]:
        reasons = "; ".join(
            f"T{t['turn']}: {', '.join(t['failure_reasons'])}" for t in fail["turns"]
        )
        print(f"  - [{fail['case_id']}] ({fail['category']}): {reasons}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
