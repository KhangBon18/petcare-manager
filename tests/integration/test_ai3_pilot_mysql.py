"""MySQL integration tests for the AI-3 Controlled Pilot Harness in mock mode."""

from __future__ import annotations

from decimal import Decimal
import os
import re
import unittest

from petcare import create_app
from petcare.ai.pilot_runner import (
    PilotBudgetExceededError,
    PilotRunConfig,
    run_controlled_pilot,
)
from petcare.config import Config
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database

TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class AI3PilotHarnessMySQLTests(unittest.TestCase):
    """Execute the 16-scenario (19-request) pilot suite against disposable QA MySQL using mocks."""

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
                "AI_PROVIDER_APPROVED": False,
                "AI_TOOL_CALLING_ENABLED": False,
                "AI_PILOT_KILL_SWITCH": False,
                "AI_VISION_ENABLED": False,
                "AI_API_BASE_URL": "",
                "AI_MODEL": "",
            }
        )

    @classmethod
    def tearDownClass(cls) -> None:
        Config.DB_NAME = cls.previous_db_name

    def test_mock_pilot_suite_passes_all_16_scenarios_with_zero_live_calls_and_clean_privacy_audit(self) -> None:
        with self.app.app_context():
            report = run_controlled_pilot(
                PilotRunConfig(
                    mode="mock",
                    model_name="gpt-6-luna",
                    max_requests=20,
                    max_cost_usd=Decimal("0.10"),
                )
            )

        self.assertEqual(report["execution_mode"], "mock")
        self.assertEqual(report["evidence_classification"], "MOCK_ADAPTER_SIMULATION_ONLY")
        self.assertEqual(report["live_network_calls_made"], 0)
        self.assertEqual(report["overall_summary"]["total_scenarios"], 16)
        self.assertEqual(report["overall_summary"]["passed_scenarios"], 16)
        self.assertEqual(report["overall_summary"]["failed_scenarios"], 0)
        self.assertEqual(report["overall_summary"]["requests_executed"], 19)
        self.assertEqual(report["failed_cases_detail"], [])
        self.assertIn("provider-side key/project budget cap", report["billing_guard_disclaimer"].lower())

        det = report["deterministic_safety_and_fallback_metrics"]
        self.assertEqual(det["turns_passed"], det["turns_evaluated"])
        self.assertEqual(det["veterinary_false_negatives"], 0)
        self.assertEqual(det["prompt_injection_resistance_rate"], 1.0)
        self.assertEqual(det["tenant_or_rbac_violations"], 0)

        llm = report["llm_orchestration_metrics"]
        self.assertEqual(llm["task_success_rate"], 1.0)
        self.assertEqual(llm["tool_selection_accuracy"], 1.0)
        self.assertEqual(llm["tool_argument_validity_rate"], 1.0)
        self.assertEqual(llm["grounded_factual_correctness_rate"], 1.0)
        self.assertEqual(llm["multiturn_context_retention_rate"], 1.0)
        self.assertEqual(llm["hallucinated_prices_or_skus"], 0)
        self.assertGreater(llm["token_usage"]["total_tokens"], 0)

        privacy = report["outbound_privacy_audit"]
        self.assertTrue(privacy["passed"])
        self.assertEqual(privacy["privacy_violations"], [])

    def test_application_spending_guard_aborts_pilot_batch_when_budget_cap_reached(self) -> None:
        with self.app.app_context():
            with self.assertRaises(PilotBudgetExceededError):
                run_controlled_pilot(
                    PilotRunConfig(
                        mode="mock",
                        model_name="gpt-4o",
                        max_requests=20,
                        max_cost_usd=Decimal("0.002"),
                    )
                )


if __name__ == "__main__":
    unittest.main()
