"""MySQL integration tests for the Google Gemini Free Tier 1-3 Request QA Smoke Harness."""

from __future__ import annotations

import os
import re
import unittest

import scripts.demo.test_accounts  # noqa: F401
from petcare import create_app
from petcare.ai.pilot_runner import (
    GeminiFreeTierSmokeConfig,
    PilotIsolationError,
    run_gemini_free_tier_smoke,
)
from petcare.config import Config
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database

TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class GeminiFreeTierSmokeMySQLTests(unittest.TestCase):
    """Verify dry-run, mock 1-3 call execution, thought_signature preservation, and live-gate blocking on QA MySQL."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        cls.app = create_app(
            {
                "TESTING": True,
                "APP_ENV": "test",
                "DB_NAME": TEST_DB,
                "AI_PROVIDER": "gemini",
                "AI_MODEL": "gemini-3.5-flash-lite",
                "AI_PROVIDER_APPROVED": False,
                "AI_TOOL_CALLING_ENABLED": False,
                "AI_VISION_ENABLED": False,
            }
        )

    @classmethod
    def tearDownClass(cls) -> None:
        Config.DB_NAME = cls.previous_db_name

    def test_gemini_smoke_dry_run_and_mock_presets_pass_with_zero_live_calls(self) -> None:
        with self.app.app_context():
            dry = run_gemini_free_tier_smoke(GeminiFreeTierSmokeConfig(mode="dry_run"))
            self.assertEqual(dry["execution_mode"], "dry_run")
            self.assertEqual(dry["live_network_calls_made"], 0)
            self.assertTrue(dry["is_isolated_test_db"])
            self.assertFalse(dry["free_tier_policy"]["paid_model_fallback_allowed"])

            mock_2 = run_gemini_free_tier_smoke(
                GeminiFreeTierSmokeConfig(mode="mock", preset="quick-2calls", max_api_calls=2)
            )
            self.assertTrue(mock_2["passed"])
            self.assertEqual(mock_2["live_network_calls_made"], 0)
            self.assertEqual(mock_2["simulated_or_live_api_steps"], 2)
            self.assertTrue(mock_2["checks"]["retained_apartment_context"])
            self.assertTrue(mock_2["checks"]["retained_chicken_allergy_slot"])
            self.assertTrue(mock_2["checks"]["excluded_chicken_allergen"])
            self.assertTrue(mock_2["checks"]["llm_usage_recorded"])
            self.assertEqual(mock_2["outbound_privacy_audit"]["audited_adapter_requests"], 2)
            self.assertTrue(mock_2["outbound_privacy_audit"]["passed"])

            mock_1 = run_gemini_free_tier_smoke(
                GeminiFreeTierSmokeConfig(mode="mock", preset="single-1call", max_api_calls=1)
            )
            self.assertTrue(mock_1["passed"])
            self.assertEqual(mock_1["live_network_calls_made"], 0)
            self.assertEqual(mock_1["simulated_or_live_api_steps"], 1)
            self.assertTrue(mock_1["checks"]["retained_chicken_allergy_slot"])
            self.assertTrue(mock_1["checks"]["llm_usage_recorded"])
            self.assertEqual(mock_1["outbound_privacy_audit"]["audited_adapter_requests"], 1)

            # Preset `quick-2calls` with `max_api_calls=1` is rejected preflight because tool calling requires 2 steps
            with self.assertRaisesRegex(PilotIsolationError, "requires --max-api-calls >= 2"):
                run_gemini_free_tier_smoke(
                    GeminiFreeTierSmokeConfig(mode="mock", preset="quick-2calls", max_api_calls=1)
                )

            # Live mode without explicit user confirmation is strictly blocked
            with self.assertRaises(PilotIsolationError):
                run_gemini_free_tier_smoke(
                    GeminiFreeTierSmokeConfig(mode="live", confirm_live_gemini=False)
                )


if __name__ == "__main__":
    unittest.main()
