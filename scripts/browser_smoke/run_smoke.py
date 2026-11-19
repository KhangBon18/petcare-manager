"""Run the optional Playwright browser smoke suite and write a JSON result."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    artifact_dir = Path(
        os.environ.get(
            "PLAYWRIGHT_ARTIFACT_DIR",
            str(Path(tempfile.gettempdir()) / "petcare-phase35-browser-artifacts"),
        )
    )
    artifact_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(SCRIPT_DIR), pattern="test_*.py", top_level_dir=str(SCRIPT_DIR)
    )
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    status = "PASS" if result.wasSuccessful() else "FAIL"
    report = {
        "status": status,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "tests_run": result.testsRun,
        "failures": [
            {"test": test.id(), "detail": detail}
            for test, detail in result.failures
        ],
        "errors": [
            {"test": test.id(), "detail": detail}
            for test, detail in result.errors
        ],
        "skipped": [
            {"test": test.id(), "reason": reason}
            for test, reason in result.skipped
        ],
        "artifacts_directory": str(artifact_dir),
    }
    result_path = artifact_dir / "results.json"
    result_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result_path.chmod(0o600)
    print(f"Browser smoke result: {status} ({result.testsRun} tests); {result_path}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
