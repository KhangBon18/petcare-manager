#!/usr/bin/env python3
"""Safe QA-only Flask web server launcher for testing Google Gemini Free Tier in the chat UI.

Strictly refuses production environments and non-`*_test` databases so real/dev store data
is never touched. Binds exclusively to `127.0.0.1` and never prints `GEMINI_API_KEY`.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from petcare import create_app  # noqa: E402
from petcare.ai.provider import validate_provider_configuration  # noqa: E402
from petcare.config import Config  # noqa: E402
from petcare.database.connection import transaction  # noqa: E402
from petcare.database.initialize import initialize_database  # noqa: E402
from petcare.database.seed import seed_database  # noqa: E402
from petcare.security import hash_password  # noqa: E402

_QA_DB_RE = re.compile(r"^[A-Za-z0-9_]+_test$")


def build_gemini_qa_web_app(
    *,
    model_name: str = Config.DEFAULT_GEMINI_MODEL,
    step_timeout_seconds: float = 50.0,
    max_output_tokens: int = 1536,
    storage_dir: Path | None = None,
):
    """Create an isolated QA-only Flask application wired to Google Gemini Free Tier."""
    raw_env = os.getenv("APP_ENV", "development").strip().lower()
    if raw_env == "production":
        raise RuntimeError("Refusing to start Gemini QA web server when APP_ENV='production'.")

    db_name = os.getenv("DB_NAME", "").strip() or Config.DB_NAME
    if not _QA_DB_RE.fullmatch(db_name) or any(tok in db_name.lower() for tok in ("_dev", "_prod", "production")):
        raise RuntimeError(
            f"Refusing to start Gemini QA web server against '{db_name}'; DB_NAME must match '^[A-Za-z0-9_]+_test$'."
        )

    bounded_step = max(5.0, min(float(step_timeout_seconds), 60.0))
    turn_deadline = int(max(60.0, bounded_step * 2.0 + 10.0))
    base_dir = storage_dir or Path(tempfile.mkdtemp(prefix="petcare-gemini-qa-web-"))
    pets_dir = base_dir / "pets"
    prods_dir = base_dir / "products"
    exports_dir = base_dir / "exports"
    for d in (pets_dir, prods_dir, exports_dir):
        d.mkdir(parents=True, exist_ok=True)

    overrides: dict[str, object] = {
        "APP_ENV": "development",
        "TESTING": False,
        "COOKIE_SECURE": False,
        "LAN_ACCESS_ENABLED": False,
        "SECRET_KEY": os.getenv("SECRET_KEY") or secrets.token_urlsafe(48),
        "DB_NAME": db_name,
        "PET_IMAGE_DIR": str(pets_dir),
        "PRODUCT_IMAGE_DIR": str(prods_dir),
        "TENANT_EXPORT_DIR": str(exports_dir),
        "AI_PROVIDER": "gemini",
        "AI_MODEL": model_name,
        "AI_PROVIDER_APPROVED": True,
        "AI_TOOL_CALLING_ENABLED": True,
        "AI_VISION_ENABLED": False,
        "AI_MAX_TOOL_ROUNDS": 2,
        "AI_HTTP_STEP_TIMEOUT_SECONDS": bounded_step,
        "AI_MAX_HTTP_TIMEOUT_SECONDS": max(15.0, bounded_step),
        "AI_TIMEOUT_SECONDS": turn_deadline,
        "AI_MAX_TURN_TIMEOUT_SECONDS": turn_deadline + 10,
        "AI_MAX_OUTPUT_TOKENS": max(256, min(int(max_output_tokens), 2048)),
    }
    return create_app(overrides)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start a loopback-only QA Flask server with Google Gemini Free Tier enabled on synthetic *_test data."
    )
    parser.add_argument("--port", type=int, default=5095, help="Loopback port on 127.0.0.1 (default: 5095).")
    parser.add_argument("--model", default=Config.DEFAULT_GEMINI_MODEL, help="Gemini model name (default: gemini-3.5-flash-lite).")
    parser.add_argument("--timeout-seconds", type=float, default=50.0, help="Per-HTTP-request timeout in seconds (default: 50.0).")
    parser.add_argument("--max-output-tokens", type=int, default=1536, help="Max output tokens per step (default: 1536).")
    parser.add_argument("--skip-init", action="store_true", help="Skip QA schema initialization and synthetic seeding.")
    parser.add_argument(
        "--sync-demo-passwords",
        action="store_true",
        help="Update isolated *_test 'admin'/'staff1' hashes from PETCARE_DEMO_*_PASSWORD env vars.",
    )
    parser.add_argument("--check-only", action="store_true", help="Validate isolated QA + Gemini config and exit without serving.")
    args = parser.parse_args()

    try:
        app = build_gemini_qa_web_app(
            model_name=args.model,
            step_timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
        )
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    with app.app_context():
        rep = validate_provider_configuration(require_approval=True, require_tool_calling=True)
        summary = {
            "ok": rep.ok,
            "bind_url": f"http://127.0.0.1:{args.port}",
            "target_database": app.config["DB_NAME"],
            "provider_validation": rep.to_dict(),
        }
        if not rep.ok:
            print(json.dumps(summary, indent=2, ensure_ascii=False), file=sys.stderr)
            return 2
        if args.check_only:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0

    if not args.skip_init:
        old_env = os.environ.get("APP_ENV")
        old_demo = os.environ.get("PETCARE_DEMO_MODE")
        os.environ["APP_ENV"] = "test"
        os.environ["PETCARE_DEMO_MODE"] = "1"
        try:
            initialize_database()
            seed_database()
        finally:
            if old_env is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = old_env
            if old_demo is None:
                os.environ.pop("PETCARE_DEMO_MODE", None)
            else:
                os.environ["PETCARE_DEMO_MODE"] = old_demo

    if args.sync_demo_passwords:
        admin_pw = os.environ.get("PETCARE_DEMO_ADMIN_PASSWORD", "")
        staff_pw = os.environ.get("PETCARE_DEMO_STAFF_PASSWORD", "")
        if len(admin_pw) < 16 or len(staff_pw) < 16 or admin_pw == staff_pw:
            print(
                json.dumps({
                    "ok": False,
                    "error": "Provide distinct PETCARE_DEMO_ADMIN_PASSWORD and PETCARE_DEMO_STAFF_PASSWORD (16+ chars).",
                }),
                file=sys.stderr,
            )
            return 2
        with app.app_context(), transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (hash_password(admin_pw),))
                cur.execute("UPDATE users SET password_hash = %s WHERE username = 'staff1'", (hash_password(staff_pw),))
            finally:
                cur.close()

    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    app.run(host="127.0.0.1", port=int(args.port), debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
