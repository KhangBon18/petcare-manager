#!/usr/bin/env python3
"""CLI entrypoint for the Google Gemini Free Tier 1-3 Request Synthetic QA Smoke Test.

Defaults safely to `--mode dry-run` (zero database writes and zero external API calls).
Never prints or logs `GEMINI_API_KEY`, never upgrades billing, and never switches to a paid model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare import create_app  # noqa: E402
from petcare.ai.pilot_runner import (  # noqa: E402
    GeminiFreeTierSmokeConfig,
    PilotSafetyAbortError,
    run_gemini_free_tier_smoke,
)
from petcare.config import Config  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or run a 1-3 request Google Gemini Free Tier smoke test on synthetic QA data."
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "mock", "live"),
        default="dry-run",
        help="dry-run (default, 0 calls), mock (offline QA MySQL + thought_signature check), or live (requires --confirm-live-gemini).",
    )
    parser.add_argument(
        "--preset",
        choices=("quick-2calls", "single-1call"),
        default="quick-2calls",
        help="quick-2calls (recommended: 2 Gemini API calls for tool selection + grounded Vietnamese reply) or single-1call (prose-only Mode B, no tool selection).",
    )
    parser.add_argument(
        "--model",
        default=Config.DEFAULT_GEMINI_MODEL,
        help="Google Gemini model name (default: gemini-3.5-flash-lite).",
    )
    parser.add_argument(
        "--max-api-calls",
        type=int,
        default=3,
        help="Hard ceiling on outbound Gemini HTTP requests (2..3 for quick-2calls, default: 3).",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1536,
        help="Per-step max_tokens cap for Gemini including thinking tokens (default: 1536).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=50.0,
        help="Per-HTTP-request timeout in seconds for Gemini QA smoke (5..60, default: 50.0).",
    )
    parser.add_argument(
        "--kill-switch-file",
        type=Path,
        default=None,
        help="Optional kill-switch sentinel file path.",
    )
    parser.add_argument(
        "--confirm-live-gemini",
        action="store_true",
        help="Explicit human approval flag required alongside AI_PROVIDER_APPROVED=1 for --mode live.",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip QA schema initialization and synthetic seeding when already initialized.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to save secret-redacted JSON report.",
    )
    args = parser.parse_args()

    mode_normalized = "dry_run" if args.mode == "dry-run" else args.mode
    if Config.APP_ENV == "production":
        print(
            json.dumps(
                {
                    "aborted": True,
                    "error_type": "PilotIsolationError",
                    "message": "Refusing to run Gemini smoke script when APP_ENV='production'.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    if mode_normalized in {"mock", "live"} and not args.skip_init:
        initialize_database()
        seed_database()

    app_overrides: dict[str, object] = {
        "TESTING": mode_normalized != "live",
        "AI_PROVIDER": Config.AI_PROVIDER or "gemini",
        "AI_MODEL": args.model,
        "AI_VISION_ENABLED": False,
    }
    if mode_normalized == "live":
        # Allow approved HTTPS egress while `run_gemini_free_tier_smoke` strictly enforces `*_test` DB isolation
        app_overrides["APP_ENV"] = "development"

    app = create_app(app_overrides)
    smoke_cfg = GeminiFreeTierSmokeConfig(
        mode=mode_normalized,
        preset=args.preset,
        model_name=args.model,
        confirm_live_gemini=bool(args.confirm_live_gemini),
        max_api_calls=max(1, min(int(args.max_api_calls), 3)),
        max_output_tokens=max(256, min(int(args.max_output_tokens), 2048)),
        timeout_seconds=max(5.0, min(float(args.timeout_seconds), 60.0)),
        kill_switch_file=args.kill_switch_file,
    )

    try:
        with app.app_context():
            report = run_gemini_free_tier_smoke(smoke_cfg)
    except PilotSafetyAbortError as exc:
        print(
            json.dumps(
                {"aborted": True, "error_type": type(exc).__name__, "message": str(exc)},
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if mode_normalized in {"mock", "live"} and not report.get("passed", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
