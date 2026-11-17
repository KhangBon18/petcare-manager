"""Unit tests for AI-3 Safety Hardening, Provider Config Validation & Controlled Pilot Guards."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from petcare import create_app
from petcare.ai import client as ai_client
from petcare.ai.contracts import AssistantScope, EngineMode, PreferenceSlots, ResponseType
from petcare.ai.llm_tool_agent import (
    MockToolCallingAdapter,
    ModelTurnOutput,
    ProposedToolCall,
    TurnGroundingLedger,
    run_tool_calling_turn,
    verify_llm_answer_consistency,
)
from petcare.ai.pilot_runner import (
    PilotBudgetAndSafetyGuard,
    PilotBudgetExceededError,
    PilotIsolationError,
    PilotKillSwitchError,
    PilotRunConfig,
    run_controlled_pilot,
    scrub_pilot_report_secrets,
)
from petcare.ai.provider import get_provider_status, validate_provider_configuration
from petcare.ai.safety_triage import evaluate_veterinary_safety
from petcare.ai.tools import ActorContext


class AI3SafetyTriageTests(unittest.TestCase):
    """Verify compositional symptom/incident detection, 4-tier separation, and negation/false-positive guards."""

    def test_closes_all_four_known_safety_gap_classes_and_unseen_paraphrases(self) -> None:
        # 1. Prolonged colloquial Vietnamese urinary straining without urine
        u1 = evaluate_veterinary_safety(
            "Từ khuya qua tới sáng bé mèo đực cứ nhảy ra nhảy vô chậu cát gào khóc rặn mãi mà không rỉ được giọt nước tiểu nào."
        )
        self.assertEqual(u1.outcome, "vet_emergency")
        self.assertEqual(u1.category, "urinary_obstruction")

        u2 = evaluate_veterinary_safety(
            "Mèo anh lông ngắn cứ chui ra chui vào nhà vệ sinh ngồi rặn nãy giờ mà không nhỏ được tí nước đái nào."
        )
        self.assertEqual(u2.outcome, "vet_emergency")
        self.assertEqual(u2.category, "urinary_obstruction")

        # 2. Inverted / unusual English & Vietnamese open-mouth / orthopnea breathing
        r1 = evaluate_veterinary_safety(
            "Our indoor cat is sitting hunched with her neck extended and breathing with her mouth wide open."
        )
        self.assertEqual(r1.outcome, "vet_emergency")
        self.assertEqual(r1.category, "respiratory_distress")

        r2 = evaluate_veterinary_safety(
            "With his mouth hanging open, our kitten keeps panting rapidly on the bedroom floor."
        )
        self.assertEqual(r2.outcome, "vet_emergency")
        self.assertEqual(r2.category, "respiratory_distress")

        # 3. Accidental double insulin / therapeutic medication overdose
        m1 = evaluate_veterinary_safety(
            "We accidentally injected our diabetic cat's morning insulin twice and now he is staring blankly and wobbling — what treats should we buy?"
        )
        self.assertEqual(m1.outcome, "vet_emergency")
        self.assertEqual(m1.category, "medication_overdose_or_adverse_event")

        m2 = evaluate_veterinary_safety(
            "Nhà mình lỡ tiêm nhầm hai mũi thuốc tiểu đường insulin cho cún giờ bé đi loạng choạng mệt lả."
        )
        self.assertEqual(m2.outcome, "vet_emergency")
        self.assertEqual(m2.category, "medication_overdose_or_adverse_event")

        # 4. Post-operative surgical incision dehiscence / exposed tissue
        w1 = evaluate_veterinary_safety(
            "My female cat chewed open her spay stitches tonight and pink tissue is poking out of the belly incision — do you sell recovery cones?"
        )
        self.assertEqual(w1.outcome, "vet_emergency")
        self.assertEqual(w1.category, "post_operative_or_wound_emergency")

        w2 = evaluate_veterinary_safety(
            "Mèo cái mới triệt sản tự cắn bung chỉ vết mổ ở bụng làm lòi thịt hồng ra ngoài, shop có bán áo chống liếm không?"
        )
        self.assertEqual(w2.outcome, "vet_emergency")
        self.assertEqual(w2.category, "post_operative_or_wound_emergency")

    def test_separates_nonurgent_clinical_referral_from_routine_shopping_and_negations(self) -> None:
        # Nonurgent / unrecognized clinical illness -> safe veterinary referral over shopping
        n1 = evaluate_veterinary_safety(
            "Mèo nhà mình bỏ ăn 3 ngày nay nằm ủ rũ sốt nhẹ, bên shop có pate nào kích thích ăn không?"
        )
        self.assertEqual(n1.outcome, "vet_nonurgent_referral")

        n2 = evaluate_veterinary_safety(
            "My dog has a rapidly growing lump oozing yellow pus on his shoulder — which shampoo should I buy?"
        )
        self.assertEqual(n2.outcome, "vet_nonurgent_referral")

        n3 = evaluate_veterinary_safety(
            "Cún nhà em tự nhiên đi khập khiễng co chân không chạm đất kêu đau khi chạm vào, mua canxi uống được không?"
        )
        self.assertEqual(n3.outcome, "vet_nonurgent_referral")

        # False-positive & negation controls -> must remain "none"
        benign_cases = [
            "Do you sell soft recovery collars for cats after spay surgery?",
            "How do I get my dog to keep his mouth open when brushing teeth with enzymatic toothpaste?",
            "My dog pants after playing fetch at the park; recommend a travel water bowl under 200k.",
            "Mèo trưởng thành khỏe mạnh, không nôn, không khó thở, đi tiểu bình thường — gợi ý hạt dưới 300k.",
            "Cách chuyển đổi thức ăn hạt trong 7-10 ngày để mèo không bị tiêu chảy?",
            "Năm ngoái cún mổ triệt sản đã lành hẳn, hiện tại khỏe mạnh — gợi ý bánh thưởng dưới 150k.",
        ]
        for query in benign_cases:
            with self.subTest(query=query):
                res = evaluate_veterinary_safety(query)
                self.assertEqual(res.outcome, "none")

    def test_llm_cannot_override_safety_decisions_pre_or_post_generation(self) -> None:
        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="en",
        )
        # Malicious adapter tries to shop during double-insulin emergency -> Gate 1 blocks with 0 LLM calls
        malicious_adapter = MockToolCallingAdapter([
            ModelTurnOutput(
                tool_calls=(ProposedToolCall("c1", "recommend_products", {"species": "cat", "category": "food"}),)
            ),
            ModelTurnOutput(assistant_text="Buy treats right away, no need to see a vet!"),
        ])
        out = run_tool_calling_turn(
            adapter=malicious_adapter,
            actor=actor,
            question="We accidentally injected our cat's insulin twice and he is wobbling.",
            session_state=None,
            initial_slots=PreferenceSlots(),
            conversation_id="conv_safety_1",
            offline_fallback_fn=lambda: {"reply": "fallback"},
        )
        self.assertEqual(malicious_adapter.call_count, 0)
        self.assertEqual(out["safety_notice"]["severity"], "emergency")
        self.assertEqual(out.get("cards", []), [])

        # Post-generation consistency verifier blocks veterinary-care dismissal phrases
        ledger = TurnGroundingLedger()
        ok, reason = verify_llm_answer_consistency(
            "These kibble options are great, so there is no need to see a veterinarian.",
            ledger,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "unsafe_medical_content")


class AI3ProviderValidationAndGuardTests(unittest.TestCase):
    """Verify SSRF guards, config validation, secret scrubbing, spend caps, and kill switches."""

    def _app(self, **overrides):
        app = Flask("ai3-provider-validation-test")
        cfg = {
            "TESTING": True,
            "APP_ENV": "production",
            "SECRET_KEY": "unit-test-secret-key-not-logged-32-chars",
            "AI_PROVIDER_APPROVED": False,
            "AI_TOOL_CALLING_ENABLED": False,
            "AI_PILOT_KILL_SWITCH": False,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
        }
        cfg.update(overrides)
        app.config.update(cfg)
        return app

    def test_default_provider_status_is_offline_disabled_and_kill_switch_overrides_approval(self) -> None:
        synthetic_probe_key = "".join(("sk", "-", "unit-test-redaction-probe-0001"))
        app = self._app(
            AI_PROVIDER_APPROVED=False,
            AI_API_BASE_URL="https://api.openai.com/v1",
            AI_API_KEY=synthetic_probe_key,
            AI_MODEL="gpt-4o-mini",
        )
        with app.app_context():
            status = get_provider_status()
            self.assertEqual(status.active_mode, EngineMode.OFFLINE)
            self.assertEqual(status.diagnostic_state, "offline_disabled")

        app_killed = self._app(
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_PILOT_KILL_SWITCH=True,
            AI_API_BASE_URL="https://api.openai.com/v1",
            AI_API_KEY=synthetic_probe_key,
            AI_MODEL="gpt-4o-mini",
        )
        with app_killed.app_context():
            status_killed = get_provider_status()
            self.assertEqual(status_killed.active_mode, EngineMode.OFFLINE)
            self.assertEqual(status_killed.diagnostic_state, "offline_kill_switch")
            with self.assertRaisesRegex(ai_client.AIProviderError, "AI_PILOT_KILL_SWITCH"):
                ai_client.complete_chat_with_tools([{"role": "user", "content": "hi"}], [])

    def test_provider_validation_blocks_ssrf_missing_key_and_never_echoes_secrets(self) -> None:
        secret = "".join(("sk", "-", "unit-test-secret-probe-9876543210"))
        app_ssrf = self._app(
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="https://169.254.169.254/latest/meta-data",
            AI_API_KEY=secret,
            AI_MODEL="gpt-4o-mini",
        )
        with app_ssrf.app_context():
            rep = validate_provider_configuration(require_approval=True, require_tool_calling=True)
            self.assertFalse(rep.ok)
            self.assertTrue(any("SSRF" in e for e in rep.errors))
            serialized = json.dumps(rep.to_dict())
            self.assertNotIn(secret, serialized)

        app_priv = self._app(
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="https://10.12.0.5/v1",
            AI_API_KEY="",
            AI_MODEL="gpt-4o-mini",
        )
        with app_priv.app_context():
            rep_priv = validate_provider_configuration(require_approval=True, require_tool_calling=True)
            self.assertFalse(rep_priv.ok)
            self.assertGreaterEqual(len(rep_priv.errors), 2)

        scrubbed = scrub_pilot_report_secrets({
            "api_key": secret,
            "api_key_present": True,
            "nested": {"note": f"Authorization: Bearer {secret}"},
        })
        self.assertEqual(scrubbed["api_key"], "[REDACTED]")
        self.assertIs(scrubbed["api_key_present"], True)
        self.assertNotIn(secret, json.dumps(scrubbed))

    def test_pilot_guards_enforce_dry_run_budget_kill_switch_and_db_isolation(self) -> None:
        app_dev_db = self._app(APP_ENV="test", DB_NAME="petcare_shop_dev")
        with app_dev_db.app_context():
            # Dry-run succeeds with 0 network calls and reports `is_isolated_test_db=False`
            dry = run_controlled_pilot(PilotRunConfig(mode="dry_run", model_name="gpt-4o-mini"))
            self.assertEqual(dry["execution_mode"], "dry_run")
            self.assertEqual(dry["live_network_calls_made"], 0)
            self.assertFalse(dry["is_isolated_test_db"])

            # Mock or live mode against non-`_test` DB is strictly blocked
            with self.assertRaises(PilotIsolationError):
                run_controlled_pilot(PilotRunConfig(mode="mock"))

        app_test_db = self._app(APP_ENV="test", DB_NAME="petcare_shop_test")
        with app_test_db.app_context():
            # Live mode without explicit confirmation is strictly blocked
            with self.assertRaises(PilotIsolationError):
                run_controlled_pilot(PilotRunConfig(mode="live", confirm_live_pilot=False))

        # Spending circuit breaker halts BEFORE step when projected step exceeds max_cost_usd
        guard = PilotBudgetAndSafetyGuard(
            PilotRunConfig(
                mode="mock",
                model_name="gpt-4o",
                max_cost_usd=Decimal("0.001"),
                max_output_tokens=700,
            )
        )
        with self.assertRaises(PilotBudgetExceededError):
            guard.check_before_model_step(0, 2000, {})

        # Kill-switch file halts immediately
        with tempfile.TemporaryDirectory() as tmp:
            ks_path = Path(tmp) / "STOP_PILOT"
            ks_guard = PilotBudgetAndSafetyGuard(PilotRunConfig(kill_switch_file=ks_path))
            ks_guard.check_kill_switch()
            ks_path.write_text("1", encoding="utf-8")
            with self.assertRaises(PilotKillSwitchError):
                ks_guard.check_kill_switch()

        # Env kill switch halts immediately
        with patch.dict("os.environ", {"AI_PILOT_KILL_SWITCH": "1"}):
            with self.assertRaises(PilotKillSwitchError):
                PilotBudgetAndSafetyGuard(PilotRunConfig()).check_kill_switch()


if __name__ == "__main__":
    unittest.main()
