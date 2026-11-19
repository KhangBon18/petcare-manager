"""Run a reproducible rolling holdout on deterministic synthetic demand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from petcare.analytics.demand_evaluation import (
    evaluate_rolling_holdout,
    synthetic_weekly_scenarios,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    args = parser.parse_args()
    report = {
        "evaluation_kind": "synthetic_inventory_demand",
        "forecast": "8-week recency-weighted average, rounded up to whole units",
        "baseline": "8-week simple mean, rounded up to whole units",
        "dataset": {
            "weeks_per_series": 52,
            "products": 12,
            "patterns": ["stable", "growing", "declining", "intermittent"],
            "label_source": "Verified by construction from this script's deterministic formulas.",
        },
        "results": evaluate_rolling_holdout(synthetic_weekly_scenarios()),
        "limitations": [
            "Synthetic patterns are a mechanics and method comparison, not evidence of real store demand accuracy.",
            "No supplier lead times, seasonality labels, promotions, stockouts, or censored sales are modeled.",
            "MAE is measured in units over a 14-day holdout and is not a confidence interval.",
        ],
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        destination = args.output if args.output.is_absolute() else ROOT / args.output
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
