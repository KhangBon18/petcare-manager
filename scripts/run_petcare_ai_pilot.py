#!/usr/bin/env python3
"""CLI entrypoint for the PetCare AI-3 Controlled Real-LLM Pilot Harness.

Defaults safely to `--mode dry-run` (zero database writes and zero external API calls).
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare import create_app  # noqa: E402
from petcare.ai.pilot_runner import (  # noqa: E402
    PilotRunConfig,
    PilotSafetyAbortError,
    run_controlled_pilot,
)
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PetCare AI-3 Controlled Pilot Harness (defaults to safe dry-run mode)."
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "mock", "live"),
        default="dry-run",
        help="Execution mode: dry-run (default, 0 calls), mock (offline QA MySQL), or live (requires explicit approval).",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="Model identifier for budgeting or live execution.")
    parser.add_argument("--max-requests", type=int, default=20, help="Hard request count ceiling (max 25).")
    parser.add_argument("--max-input-tokens", type=int, default=6000, help="Per-step input token ceiling.")
    parser.add_argument("--max-output-tokens", type=int, default=700, help="Per-step completion token ceiling.")
    parser.add_argument("--max-total-tokens", type=int, default=40000, help="Cumulative pilot token ceiling.")
    parser.add_argument("--max-cost-usd", type=Decimal, default=Decimal("0.25"), help="Application-side USD spend cap.")
    parser.add_argument("--max-concurrency", type=int, default=1, help="Bounded worker concurrency (1..2).")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="Per-turn timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=1, help="Transient retry limit (0..1).")
    parser.add_argument("--kill-switch-file", type=Path, default=None, help="Optional kill-switch sentinel file path.")
    parser.add_argument(
        "--confirm-live-pilot",
        action="store_true",
        help="Explicit human confirmation required alongside AI_PROVIDER_APPROVED=1 for --mode live.",
    )
    parser.add_argument("--skip-init", action="store_true", help="Skip QA schema init/seed when already seeded.")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write secret-redacted JSON report.")
    args = parser.parse_args()

    mode_normalized = "dry_run" if args.mode == "dry-run" else args.mode
    if mode_normalized in {"mock", "live"} and not args.skip_init:
        initialize_database()
        seed_database()

    app_overrides: dict[str, object] = {"TESTING": mode_normalized != "live"}
    if mode_normalized == "live":
        app_overrides["AI_MODEL"] = args.model

    app = create_app(app_overrides)
    pilot_cfg = PilotRunConfig(
        mode=mode_normalized,
        model_name=args.model,
        confirm_live_pilot=bool(args.confirm_live_pilot),
        max_requests=max(1, min(int(args.max_requests), 25)),
        max_input_tokens=max(512, min(int(args.max_input_tokens), 32000)),
        max_output_tokens=max(128, min(int(args.max_output_tokens), 2048)),
        max_total_tokens=max(1000, min(int(args.max_total_tokens), 200000)),
        max_cost_usd=Decimal(str(args.max_cost_usd)),
        max_concurrency=max(1, min(int(args.max_concurrency), 2)),
        timeout_seconds=max(0.5, min(float(args.timeout_seconds), 15.0)),
        max_retries=max(0, min(int(args.max_retries), 1)),
        kill_switch_file=args.kill_switch_file,
    )

    try:
        with app.app_context():
            report = run_controlled_pilot(pilot_cfg)
    except PilotSafetyAbortError as exc:
        print(json.dumps({"aborted": True, "error_type": type(exc).__name__, "message": str(exc)}, indent=2), file=sys.stderr)
        return 2

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary_view = {
        k: v for k, v in report.items() if k != "cases"
    }
    print(json.dumps(summary_view, indent=2, ensure_ascii=False))

    if mode_normalized in {"mock", "live"}:
        failed = [c for c in report.get("cases", []) if not c.get("passed")]
        if failed or not report.get("outbound_privacy_audit", {}).get("passed", True):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

