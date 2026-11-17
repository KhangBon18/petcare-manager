"""Unit tests for Google Gemini Free Tier provider integration, thought signatures, schema sanitization & rate limits."""

from __future__ import annotations

import io
import json
import socket
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from flask import Flask

from petcare.ai import client as ai_client
from petcare.ai.contracts import AssistantScope, EngineMode, PreferenceSlots
from petcare.ai.llm_tool_agent import (
    MockToolCallingAdapter,
    ModelTurnOutput,
    OpenAICompatibleToolCallingAdapter,
    ProposedToolCall,
    run_tool_calling_turn,
)
from petcare.ai.memory import MEMORY_STORE, redact_sensitive_text
from petcare.ai.nlu import extract_preference_slots
from petcare.ai.pilot_runner import scrub_pilot_report_secrets
from petcare.ai.provider import (
    get_provider_status,
    synthesize_approved_llm_reply_detailed,
    validate_provider_configuration,
)
from petcare.ai.tool_schemas import list_openai_tools_for_actor
from petcare.ai.tools import ActorContext


class GeminiProviderConfigAndWireTests(unittest.TestCase):
    """Verify Gemini configuration, secret isolation, URL normalization, parameters, and schemas."""

    def setUp(self) -> None:
        ai_client.GLOBAL_PROVIDER_RATE_LIMITER.reset()

    def tearDown(self) -> None:
        ai_client.GLOBAL_PROVIDER_RATE_LIMITER.reset()

    def _app(self, **overrides) -> Flask:
        app = Flask("gemini-unit-test")
        cfg = {
            "TESTING": True,
            "APP_ENV": "development",
            "SECRET_KEY": "unit-test-secret-key-not-logged-32-chars",
            "AI_PROVIDER": "",
            "AI_PROVIDER_APPROVED": False,
            "AI_TOOL_CALLING_ENABLED": False,
            "AI_PILOT_KILL_SWITCH": False,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "GEMINI_API_KEY": "",
            "AI_MODEL": "",
            "AI_REASONING_EFFORT": "",
            "AI_RATE_LIMIT_RPM": 10,
            "AI_RATE_LIMIT_TPM": 180000,
            "AI_RATE_LIMIT_RPD": 450,
            "AI_MIN_REQUEST_INTERVAL_MS": 1200,
        }
        cfg.update(overrides)
        app.config.update(cfg)
        return app

    def test_gemini_disabled_by_default_even_when_gemini_api_key_present(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiProbeKey00000001"))
        app = self._app(
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=False,
            AI_TOOL_CALLING_ENABLED=False,
            GEMINI_API_KEY=probe_key,
        )
        with app.app_context():
            status = get_provider_status()
            self.assertEqual(status.active_mode, EngineMode.OFFLINE)
            self.assertEqual(status.diagnostic_state, "offline_disabled")
            self.assertEqual(status.provider_family, "offline")
            self.assertNotIn(probe_key, json.dumps(status.to_dict()))

    def test_gemini_provider_resolves_endpoint_model_and_never_exposes_api_key(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiProbeKey00000002"))
        app = self._app(
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            GEMINI_API_KEY=probe_key,
        )
        with app.app_context():
            status = get_provider_status()
            self.assertEqual(status.active_mode, EngineMode.REAL_LLM)
            self.assertEqual(status.provider_family, "gemini")
            self.assertEqual(status.model_name, "gemini-3.5-flash-lite")
            self.assertEqual(status.api_key_source, "GEMINI_API_KEY")
            self.assertEqual(status.diagnostic_state, "configured_llm_tool_calling_standby")

            rep = validate_provider_configuration(require_approval=True, require_tool_calling=True)
            self.assertTrue(rep.ok)
            self.assertEqual(rep.provider_family, "gemini")
            self.assertEqual(rep.endpoint_host, "generativelanguage.googleapis.com")
            self.assertEqual(rep.endpoint_scheme, "https")
            self.assertIsNone(rep.reasoning_effort_effective)
            self.assertEqual(rep.rate_limit_guard["rpm"], 10)
            serialized = json.dumps(rep.to_dict())
            self.assertNotIn(probe_key, serialized)

            # Verify URL normalization produces /v1beta/openai/chat/completions (never /v1beta/openai/v1/...)
            normalized = ai_client.validate_endpoint_url(
                "https://generativelanguage.googleapis.com/v1beta/openai/",
                app_env="development",
            )
            self.assertEqual(
                normalized,
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            )

        # Memory & report redaction scrub bare AIza... keys and GEMINI_API_KEY=... assignments
        redacted = redact_sensitive_text(f"My key is {probe_key} and GEMINI_API_KEY=secret123", max_chars=200)
        self.assertNotIn(probe_key, redacted)
        self.assertNotIn("secret123", redacted)
        scrubbed = scrub_pilot_report_secrets({"GEMINI_API_KEY": probe_key, "note": f"token {probe_key}"})
        self.assertEqual(scrubbed["GEMINI_API_KEY"], "[REDACTED]")
        self.assertNotIn(probe_key, json.dumps(scrubbed))

    def test_gemini_parameter_validation_blocks_gpt6_none_reasoning_and_warns_on_high_rpm(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiProbeKey00000003"))
        # 1. Default Gemini params omit GPT-6's `reasoning_effort='none'` and send standard `max_tokens`
        default_params = ai_client.resolve_chat_completions_params(
            "gemini-3.5-flash-lite",
            "",
            has_tools=True,
            max_output_tokens=800,
            default_temperature=0.1,
            provider_family="gemini",
        )
        self.assertEqual(default_params, {"temperature": 0.1, "max_tokens": 800})
        self.assertNotIn("reasoning_effort", default_params)
        self.assertNotIn("max_completion_tokens", default_params)

        # 2. Explicit 'minimal' / 'low' reasoning_effort is accepted for Gemini 3.5
        low_params = ai_client.resolve_chat_completions_params(
            "gemini-3.5-flash-lite",
            "minimal",
            has_tools=True,
            max_output_tokens=800,
            default_temperature=0.1,
            provider_family="gemini",
        )
        self.assertEqual(low_params["reasoning_effort"], "minimal")

        # 3. GPT-6's `reasoning_effort='none'` is rejected on Gemini 3.5 preflight
        app_bad_effort = self._app(
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
            AI_REASONING_EFFORT="none",
        )
        with app_bad_effort.app_context():
            rep_bad = validate_provider_configuration(require_approval=True, require_tool_calling=True)
            self.assertFalse(rep_bad.ok)
            self.assertTrue(any("none" in e for e in rep_bad.errors))

        # 4. Setting RPM above 15 emits a Free Tier warning
        app_high_rpm = self._app(
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            GEMINI_API_KEY=probe_key,
            AI_RATE_LIMIT_RPM=25,
        )
        with app_high_rpm.app_context():
            rep_warn = validate_provider_configuration(require_approval=True, require_tool_calling=True)
            self.assertTrue(rep_warn.ok)
            self.assertTrue(any("15 RPM" in w for w in rep_warn.warnings))

    def test_gemini_tool_schema_sanitization_strips_unsupported_keywords_and_empty_properties(self) -> None:
        admin_actor = ActorContext(
            user_id=1,
            tenant_id=1,
            role="admin",
            scope=AssistantScope.WORKSPACE,
            locale="vi",
        )
        gemini_tools = list_openai_tools_for_actor(admin_actor, provider_family="gemini")
        openai_tools = list_openai_tools_for_actor(admin_actor, provider_family="openai")
        self.assertEqual(len(gemini_tools), 13)
        self.assertEqual(len(openai_tools), 13)

        gemini_json = json.dumps(gemini_tools)
        self.assertNotIn('"additionalProperties"', gemini_json)
        self.assertNotIn('"minLength"', gemini_json)
        self.assertNotIn('"maxLength"', gemini_json)
        self.assertNotIn('"pattern"', gemini_json)

        # Zero-arg `get_operations_overview` omits `parameters` for Gemini while OpenAI keeps `properties: {}`
        gem_ops = next(t for t in gemini_tools if t["function"]["name"] == "get_operations_overview")
        self.assertNotIn("parameters", gem_ops["function"])
        oai_ops = next(t for t in openai_tools if t["function"]["name"] == "get_operations_overview")
        self.assertIn("parameters", oai_ops["function"])

    def test_gemini_wire_roundtrip_preserves_thought_signatures_and_empty_call_ids(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiProbeKey00000004"))
        captured_http_bodies: list[dict] = []

        responses = [
            # Step 1: Gemini returns parallel/single tool call with `extra_content.google.thought_signature` and `id: ""`
            {
                "id": "gemini-cmpl-1",
                "model": "gemini-3.5-flash-lite",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {
                                        "name": "search_pet_care_knowledge",
                                        "arguments": json.dumps({"query": "chuyển đổi thức ăn hạt 7-10 ngày"}),
                                    },
                                    "extra_content": {
                                        "google": {
                                            "thought_signature": "CvcQAdH_Gemini35_SigToken_XYZ=="
                                        }
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 640,
                    "completion_tokens": 55,
                    "total_tokens": 695,
                    "thoughts_token_count": 21,
                },
            },
            # Step 2: Gemini verifies thought_signature on incoming history and returns grounded answer
            {
                "id": "gemini-cmpl-2",
                "model": "gemini-3.5-flash-lite",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Bạn nên chuyển đổi thức ăn mới từ từ trong 7-10 ngày theo tài liệu KB-NUTR-001.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 910,
                    "completion_tokens": 42,
                    "total_tokens": 952,
                    "thoughts_token_count": 14,
                },
            },
        ]

        class _SeqResp:
            def __init__(self, payload: dict):
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _limit: int) -> bytes:
                return self._raw

        class _SeqOpener:
            def __init__(self):
                self.idx = 0

            def open(self, req, timeout=15):
                captured_http_bodies.append(
                    {
                        "url": req.full_url,
                        "auth": req.get_header("Authorization"),
                        "body": json.loads(req.data.decode("utf-8")),
                    }
                )
                payload = responses[self.idx]
                self.idx += 1
                return _SeqResp(payload)

        app = self._app(
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19998/v1beta/openai/",
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
        )
        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )
        with app.app_context(), patch("petcare.ai.client.build_opener", return_value=_SeqOpener()):
            adapter = OpenAICompatibleToolCallingAdapter("gemini-3.5-flash-lite", provider_family="gemini")
            res = run_tool_calling_turn(
                adapter=adapter,
                actor=actor,
                question="Cách chuyển đổi thức ăn hạt mới cho mèo trong 7-10 ngày?",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_gem_sig_1",
                offline_fallback_fn=lambda: {"reply": "fallback", "engine_mode": "offline"},
            )

        self.assertEqual(len(captured_http_bodies), 2)
        self.assertEqual(
            captured_http_bodies[0]["url"],
            "http://127.0.0.1:19998/v1beta/openai/chat/completions",
        )
        self.assertEqual(captured_http_bodies[0]["auth"], f"Bearer {probe_key}")
        step1_body = captured_http_bodies[0]["body"]
        self.assertNotIn("reasoning_effort", step1_body)
        self.assertIn("max_tokens", step1_body)
        self.assertNotIn('"additionalProperties"', json.dumps(step1_body["tools"]))

        # Verify Step 2 echoed back exact `id: ""`, `extra_content.google.thought_signature`, and `role: "tool"` with `name`
        step2_msgs = captured_http_bodies[1]["body"]["messages"]
        asst_msg = next(m for m in step2_msgs if m["role"] == "assistant" and m.get("tool_calls"))
        self.assertIsNone(asst_msg["content"])
        self.assertEqual(asst_msg["tool_calls"][0]["id"], "")
        self.assertEqual(
            asst_msg["tool_calls"][0]["extra_content"]["google"]["thought_signature"],
            "CvcQAdH_Gemini35_SigToken_XYZ==",
        )
        tool_msg = next(m for m in step2_msgs if m["role"] == "tool")
        self.assertEqual(tool_msg["tool_call_id"], "")
        self.assertEqual(tool_msg["name"], "search_pet_care_knowledge")

        self.assertEqual(res["engine_mode"], "real_llm")
        self.assertFalse(res["fallback_used"])
        self.assertEqual(res["llm_usage"]["rounds_completed"], 2)
        self.assertEqual(res["llm_usage"]["reasoning_tokens"], 35)


class GeminiSafetyAndRateLimitTests(unittest.TestCase):
    """Verify Free Tier rate limiting, HTTP 429 fallback, timeout fallback, RBAC, and grounding."""

    def setUp(self) -> None:
        ai_client.GLOBAL_PROVIDER_RATE_LIMITER.reset()
        MEMORY_STORE.clear_all()

    def tearDown(self) -> None:
        ai_client.GLOBAL_PROVIDER_RATE_LIMITER.reset()
        MEMORY_STORE.clear_all()

    def test_free_tier_rate_limiter_paces_multi_request_turns_and_blocks_quota_exhaustion(self) -> None:
        fake_now = [100.0]
        slept: list[float] = []

        def _clock() -> float:
            return fake_now[0]

        def _sleep(sec: float) -> None:
            slept.append(round(sec, 3))
            fake_now[0] += sec

        limiter = ai_client.FreeTierRateLimiter(clock=_clock, sleeper=_sleep)

        # Turn 1 Step 1 (immediate) + Turn 1 Step 2 (paced by 1.2s min_interval_seconds)
        w1 = limiter.acquire(
            "gemini",
            estimated_input_tokens=1000,
            rpm_limit=3,
            tpm_limit=10000,
            rpd_limit=10,
            min_interval_seconds=1.2,
            max_wait_seconds=2.5,
        )
        self.assertEqual(w1, 0.0)
        fake_now[0] += 0.2
        w2 = limiter.acquire(
            "gemini",
            estimated_input_tokens=1200,
            rpm_limit=3,
            tpm_limit=10000,
            rpd_limit=10,
            min_interval_seconds=1.2,
            max_wait_seconds=2.5,
        )
        self.assertAlmostEqual(w2, 1.0, places=2)
        self.assertEqual(slept, [1.0])

        # 3rd request fits inside RPM=3 after spacing
        fake_now[0] += 1.5
        limiter.acquire(
            "gemini",
            estimated_input_tokens=1000,
            rpm_limit=3,
            tpm_limit=10000,
            rpd_limit=10,
            min_interval_seconds=1.2,
            max_wait_seconds=2.5,
        )

        # 4th request within the same 60s window hits RPM=3 and immediately raises AIRateLimitError
        fake_now[0] += 1.5
        with self.assertRaises(ai_client.AIRateLimitError) as ctx:
            limiter.acquire(
                "gemini",
                estimated_input_tokens=1000,
                rpm_limit=3,
                tpm_limit=10000,
                rpd_limit=10,
                min_interval_seconds=1.2,
                max_wait_seconds=2.5,
            )
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertFalse(ctx.exception.retryable)

    def test_http_429_and_timeout_degrade_gracefully_to_offline_python_never_paid_model(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiProbeKey00000005"))
        app = Flask("gemini-429-test")
        app.config.update(
            TESTING=True,
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_ENFORCE_TEST_RATE_LIMIT=True,
            AI_MIN_REQUEST_INTERVAL_MS=0,
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19997/v1beta/openai/",
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
        )

        class _RateLimitedOpener:
            def __init__(self):
                self.calls = 0

            def open(self, req, timeout=15):
                self.calls += 1
                raise HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "8"}, None)

        opener_429 = _RateLimitedOpener()
        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )
        with app.app_context(), patch("petcare.ai.client.build_opener", return_value=opener_429):
            adapter = OpenAICompatibleToolCallingAdapter("gemini-3.5-flash-lite", provider_family="gemini")
            out_429 = run_tool_calling_turn(
                adapter=adapter,
                actor=actor,
                question="Gợi ý hạt cho mèo trưởng thành dưới 400k",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_429",
                offline_fallback_fn=lambda: {
                    "reply": "Kết quả Python nội bộ xác thực.",
                    "engine_mode": "offline",
                    "mode": "local",
                },
            )
            snap = ai_client.GLOBAL_PROVIDER_RATE_LIMITER.snapshot("gemini")

        # HTTP 429 is NOT retried blindly, sets cooldown, and degrades to Offline Python (zero paid fallback)
        self.assertEqual(opener_429.calls, 1)
        self.assertTrue(out_429["fallback_used"])
        self.assertEqual(out_429["fallback_reason"], "provider_rate_limited")
        self.assertEqual(out_429["engine_mode"], "offline")
        self.assertGreater(snap["cooldown_remaining_seconds"], 0.0)

        # Provider timeout also falls back cleanly to Offline Python
        timeout_adapter = MockToolCallingAdapter(
            [TimeoutError("Gemini endpoint timed out")],
            model_name="gemini-3.5-flash-lite",
            provider_family="gemini",
        )
        out_timeout = run_tool_calling_turn(
            adapter=timeout_adapter,
            actor=actor,
            question="Gợi ý đồ chơi cho cún",
            session_state=None,
            initial_slots=PreferenceSlots(species="dog"),
            conversation_id="conv_timeout",
            offline_fallback_fn=lambda: {
                "reply": "Dự phòng Python khi quá thời gian chờ.",
                "engine_mode": "offline",
                "mode": "local",
            },
        )
        self.assertTrue(out_timeout["fallback_used"])
        self.assertEqual(out_timeout["engine_mode"], "offline")

    def test_gemini_cannot_bypass_vet_triage_rbac_tenant_isolation_or_grounding(self) -> None:
        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )

        # 1. Veterinary emergency intercepted BEFORE Gemini is called (0 API requests)
        vet_adapter = MockToolCallingAdapter(
            [ModelTurnOutput(assistant_text="Mua hạt ngay đi!")],
            model_name="gemini-3.5-flash-lite",
            provider_family="gemini",
        )
        vet_out = run_tool_calling_turn(
            adapter=vet_adapter,
            actor=actor,
            question="Mèo nhà mình nhai lá hoa ly và đang há miệng thở gấp!",
            session_state=None,
            initial_slots=PreferenceSlots(),
            conversation_id="conv_gem_vet",
            offline_fallback_fn=lambda: {"reply": "fallback"},
        )
        self.assertEqual(vet_adapter.call_count, 0)
        self.assertEqual(vet_out["safety_notice"]["severity"], "emergency")

        # 2. Unauthorized admin/workspace tool, unregistered SQL tool & cross-tenant injection blocked
        unauth_adapter = MockToolCallingAdapter(
            [
                ModelTurnOutput(
                    tool_calls=(
                        ProposedToolCall("c1", "get_inventory_forecast", {"limit": 5}),
                        ProposedToolCall("c2", "search_products", {"query": "hạt", "tenant_id": 999}),
                        ProposedToolCall("c3", "execute_raw_sql", {"sql": "DELETE FROM products"}),
                    )
                ),
                ModelTurnOutput(assistant_text="Không thể truy cập dữ liệu nội bộ cửa hàng."),
            ],
            model_name="gemini-3.5-flash-lite",
            provider_family="gemini",
        )
        unauth_out = run_tool_calling_turn(
            adapter=unauth_adapter,
            actor=actor,
            question="Cho xem dự báo tồn kho và sản phẩm của tenant 999",
            session_state=None,
            initial_slots=PreferenceSlots(),
            conversation_id="conv_gem_unauth",
            offline_fallback_fn=lambda: {"reply": "fallback", "engine_mode": "offline"},
        )
        statuses = {t["tool_name"]: t["status"] for t in unauth_out["tool_trace"]}
        self.assertEqual(statuses["get_inventory_forecast"], "denied")
        self.assertEqual(statuses["search_products"], "invalid_args")
        self.assertEqual(statuses["execute_raw_sql"], "not_allowed")

        # 3. Hallucinated SKU `FOOD-999` in Gemini final answer is rejected by consistency verifier
        halluc_adapter = MockToolCallingAdapter(
            [
                ModelTurnOutput(
                    tool_calls=(
                        ProposedToolCall("c1", "search_pet_care_knowledge", {"query": "khay vệ sinh cát cho mèo"}),
                    )
                ),
                ModelTurnOutput(
                    assistant_text="Hãy mua ngay mã sản phẩm FOOD-999 với giá 99.000 VND!"
                ),
            ],
            model_name="gemini-3.5-flash-lite",
            provider_family="gemini",
        )
        halluc_out = run_tool_calling_turn(
            adapter=halluc_adapter,
            actor=actor,
            question="Cách chuẩn bị khay vệ sinh cát cho mèo?",
            session_state=None,
            initial_slots=PreferenceSlots(species="cat"),
            conversation_id="conv_gem_halluc",
            offline_fallback_fn=lambda: {"reply": "fallback", "engine_mode": "offline"},
        )
        self.assertTrue(halluc_out["fallback_used"])
        self.assertEqual(halluc_out["engine_mode"], "offline")
        self.assertNotIn("FOOD-999", halluc_out["reply"])

    def test_reproduces_and_fixes_first_live_smoke_bugs_diagnostics_role_merge_and_allergy_nlu(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiDiagProbe000099"))

        # 1. Offline NLU extracts chicken allergy from natural Vietnamese 'không chứa thịt gà' / 'né vị gà' / EN 'without chicken'
        for phrase in (
            "Gợi ý giúp mình thức ăn hạt không chứa thịt gà dưới 400k đang còn hàng cho bé nhé.",
            "Tìm hạt mèo trưởng thành né vị gà tầm 350k",
            "Recommend adult cat food without chicken under 400k",
        ):
            slots, _, _ = extract_preference_slots(phrase)
            self.assertIn("chicken", slots.allergies, f"Missed chicken exclusion in: {phrase}")

        # 2. Gemini consecutive `role == 'user'` messages are merged into 1 user turn (preventing HTTP 400 INVALID_ARGUMENT)
        merged_msgs = ai_client.normalize_messages_for_provider(
            [
                {"role": "system", "content": "Rules"},
                {"role": "user", "content": "VERIFIED_GROUNDED_FACTS_JSON: {}"},
                {"role": "user", "content": "Gợi ý hạt mèo"},
            ],
            "gemini",
        )
        self.assertEqual([m["role"] for m in merged_msgs], ["system", "user"])
        self.assertIn("VERIFIED_GROUNDED_FACTS_JSON", merged_msgs[1]["content"])
        self.assertIn("Gợi ý hạt mèo", merged_msgs[1]["content"])

        # 3. Upstream Gemini HTTP 400 JSON-array error preserves exact status/category, scrubs secrets,
        #    sets non-null fallback_reason & llm_usage, and records outbound messages for privacy auditing!
        app = Flask("gemini-diag-test")
        app.config.update(
            TESTING=True,
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19996/v1beta/openai/",
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
        )

        err_body_bytes = json.dumps([
            {
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": f"Invalid argument near key={probe_key} at https://generativelanguage.googleapis.com/v1beta/openai",
                }
            }
        ]).encode("utf-8")

        class _Http400Opener:
            def open(self, req, timeout=15):
                raise HTTPError(
                    req.full_url,
                    400,
                    "Bad Request",
                    {"Content-Type": "application/json"},
                    io.BytesIO(err_body_bytes),
                )

        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )
        with app.app_context(), patch("petcare.ai.client.build_opener", return_value=_Http400Opener()):
            # Check synthesize_approved_llm_reply_detailed (single-1call path)
            detailed = synthesize_approved_llm_reply_detailed(
                question="Gợi ý hạt mèo dưới 400k",
                locale="vi",
                grounded_facts={"cards": [{"code": "FOOD-001"}]},
                fallback_reply="Kết quả nội bộ.",
            )
            self.assertTrue(detailed["fallback_used"])
            self.assertEqual(detailed["fallback_reason"], "provider_http_400:http_400_bad_request")
            self.assertIsNotNone(detailed["llm_usage"])
            self.assertEqual(detailed["provider_diagnostic"]["http_status"], 400)
            self.assertEqual(detailed["provider_diagnostic"]["upstream_error_code"], "INVALID_ARGUMENT")
            self.assertNotIn(probe_key, json.dumps(detailed["provider_diagnostic"]))
            self.assertEqual(len(detailed["outbound_messages"]), 2)
            self.assertEqual([m["role"] for m in detailed["outbound_messages"]], ["system", "user"])

            # Check OpenAICompatibleToolCallingAdapter (quick-2calls path)
            adapter_400 = OpenAICompatibleToolCallingAdapter("gemini-3.5-flash-lite", provider_family="gemini")
            turn_400 = run_tool_calling_turn(
                adapter=adapter_400,
                actor=actor,
                question="Gợi ý hạt mèo dưới 400k",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_400_diag",
                offline_fallback_fn=lambda: {"reply": "fallback", "engine_mode": "offline", "mode": "local"},
            )
            self.assertTrue(turn_400["fallback_used"])
            self.assertEqual(turn_400["fallback_reason"], "provider_http_400:http_400_bad_request")
            self.assertEqual(turn_400["llm_usage"]["last_error"]["http_status"], 400)
            self.assertEqual(turn_400["llm_usage"]["last_error"]["upstream_error_code"], "INVALID_ARGUMENT")
            self.assertNotIn(probe_key, json.dumps(turn_400))
            # Outbound request WAS recorded on the live adapter even when HTTP 400 occurred!
            self.assertEqual(len(adapter_400.recorded_requests), 1)
            self.assertEqual(len(adapter_400.provider_diagnostics), 1)

        # 4. Thinking-token `finish_reason == 'length'` truncation is diagnosed distinctly
        class _TruncatedResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _limit: int) -> bytes:
                return json.dumps({
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": None}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 500, "completion_tokens": 700, "total_tokens": 1200, "thoughts_token_count": 700},
                }).encode("utf-8")

        class _TruncatedOpener:
            def open(self, req, timeout=15):
                return _TruncatedResp()

        with app.app_context(), patch("petcare.ai.client.build_opener", return_value=_TruncatedOpener()):
            adapter_len = OpenAICompatibleToolCallingAdapter("gemini-3.5-flash-lite", provider_family="gemini")
            turn_len = run_tool_calling_turn(
                adapter=adapter_len,
                actor=actor,
                question="Gợi ý hạt mèo dưới 400k",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_len_diag",
                offline_fallback_fn=lambda: {"reply": "fallback", "engine_mode": "offline", "mode": "local"},
            )
            self.assertTrue(turn_len["fallback_used"])
            self.assertEqual(
                turn_len["fallback_reason"],
                "provider_error:MalformedModelOutputError:response_truncated_length",
            )
            self.assertEqual(adapter_len.provider_diagnostics[0]["error_category"], "response_truncated_length")

    def test_gemini_smoke_45_to_60s_step_timeout_final_tool_choice_none_and_ssl_verify(self) -> None:
        probe_key = "".join(("AIza", "SyUnitTestGeminiTimeout50s0001"))

        # 1. Strict SSL certificate + hostname verification remains enabled
        ssl_ctx = ai_client._build_verified_ssl_context()
        self.assertTrue(ssl_ctx.check_hostname)
        self.assertEqual(ssl_ctx.verify_mode, ssl.CERT_REQUIRED)

        # 2. Other providers (e.g., OpenAI default config) retain existing 6.0s step / 15.0s HTTP timeout cap
        app_openai = Flask("openai-default-timeout-check")
        app_openai.config.update(
            TESTING=True,
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_PROVIDER="openai",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19995/v1",
            AI_API_KEY="".join(("sk", "-", "unit-test-openai-timeout-001")),
            AI_MODEL="gpt-6-luna",
        )
        openai_timeouts: list[float] = []

        class _SimpleOkResp:
            def __init__(self, payload: dict):
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _limit: int) -> bytes:
                return self._raw

        class _OpenAITimeoutSpy:
            def open(self, req, timeout=15):
                openai_timeouts.append(float(timeout))
                return _SimpleOkResp({
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                })

        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )
        with app_openai.app_context(), patch("petcare.ai.client.build_opener", return_value=_OpenAITimeoutSpy()):
            oai_adapter = OpenAICompatibleToolCallingAdapter("gpt-6-luna", provider_family="openai")
            run_tool_calling_turn(
                adapter=oai_adapter,
                actor=actor,
                question="Xin chào",
                session_state=None,
                initial_slots=PreferenceSlots(),
                conversation_id="conv_oai_to",
                offline_fallback_fn=lambda: {"reply": "fb", "engine_mode": "offline"},
            )
        self.assertEqual(openai_timeouts, [6.0])

        # 3. Gemini QA smoke config gives BOTH Request 1 and Request 2 a full 50s socket timeout
        #    and sets `tool_choice="none"` on Request 2 (final synthesis round) to prevent redundant tool calls
        app_gem_smoke = Flask("gemini-50s-smoke-test")
        app_gem_smoke.config.update(
            TESTING=True,
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19994/v1beta/openai/",
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
            AI_HTTP_STEP_TIMEOUT_SECONDS=50.0,
            AI_MAX_HTTP_TIMEOUT_SECONDS=50.0,
            AI_MAX_TURN_TIMEOUT_SECONDS=120,
            AI_TIMEOUT_SECONDS=110.0,
            AI_MAX_TOOL_ROUNDS=2,
        )
        captured_calls: list[dict] = []
        step_payloads = [
            {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_gem_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_pet_care_knowledge",
                                        "arguments": json.dumps({"query": "chuyển đổi thức ăn hạt 7-10 ngày"}),
                                    },
                                    "extra_content": {"google": {"thought_signature": "Sig50sRoundTrip=="}},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 2117, "completion_tokens": 64, "total_tokens": 2181},
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Bạn nên chuyển đổi hạt từ từ trong 7-10 ngày (KB-NUTR-001).",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 2580, "completion_tokens": 52, "total_tokens": 2632},
            },
        ]

        class _TwoStepSuccessOpener:
            def open(self, req, timeout=15):
                idx = len(captured_calls)
                captured_calls.append({
                    "timeout": float(timeout),
                    "body": json.loads(req.data.decode("utf-8")),
                })
                return _SimpleOkResp(step_payloads[idx])

        with app_gem_smoke.app_context(), patch("petcare.ai.client.build_opener", return_value=_TwoStepSuccessOpener()):
            gem_adapter = OpenAICompatibleToolCallingAdapter(
                "gemini-3.5-flash-lite",
                max_output_tokens=1536,
                provider_family="gemini",
                max_retries=0,
            )
            ok_res = run_tool_calling_turn(
                adapter=gem_adapter,
                actor=actor,
                question="Cách chuyển đổi thức ăn hạt trong 7-10 ngày?",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_gem_50s_ok",
                offline_fallback_fn=lambda: {"reply": "fb", "engine_mode": "offline"},
            )

        self.assertEqual(len(captured_calls), 2)
        self.assertAlmostEqual(captured_calls[0]["timeout"], 50.0, places=1)
        self.assertAlmostEqual(captured_calls[1]["timeout"], 50.0, places=1)
        self.assertEqual(captured_calls[0]["body"]["tool_choice"], "auto")
        # Final synthesis step on Gemini strips `tools` and formats VERIFIED_PYTHON_TOOL_RESULTS_JSON
        self.assertNotIn("tools", captured_calls[1]["body"])
        self.assertNotIn("tool_choice", captured_calls[1]["body"])
        self.assertIn("VERIFIED_PYTHON_TOOL_RESULTS_JSON", captured_calls[1]["body"]["messages"][-1]["content"])
        self.assertEqual(ok_res["engine_mode"], "real_llm")
        self.assertFalse(ok_res["fallback_used"])
        self.assertEqual(ok_res["llm_usage"]["rounds_completed"], 2)

        # 4. If Request 2 still times out, diagnostics record step 1 timeout and safely compose grounded ledger fallback
        class _SecondStepTimeoutOpener:
            def __init__(self):
                self.calls = 0

            def open(self, req, timeout=15):
                self.calls += 1
                if self.calls == 1:
                    return _SimpleOkResp(step_payloads[0])
                raise socket.timeout("timed out")

        with app_gem_smoke.app_context(), patch("petcare.ai.client.build_opener", return_value=_SecondStepTimeoutOpener()):
            gem_to_adapter = OpenAICompatibleToolCallingAdapter(
                "gemini-3.5-flash-lite",
                max_output_tokens=1536,
                provider_family="gemini",
                max_retries=0,
            )
            to_res = run_tool_calling_turn(
                adapter=gem_to_adapter,
                actor=actor,
                question="Cách chuyển đổi thức ăn hạt trong 7-10 ngày?",
                session_state=None,
                initial_slots=PreferenceSlots(species="cat"),
                conversation_id="conv_gem_50s_to",
                offline_fallback_fn=lambda: {"reply": "fb", "engine_mode": "offline"},
            )

        self.assertTrue(to_res["fallback_used"])
        self.assertEqual(to_res["fallback_reason"], "provider_error:timeout")
        self.assertEqual(to_res["engine_mode"], "offline")
        self.assertGreaterEqual(len(to_res["citations"]), 1)
        self.assertEqual(gem_to_adapter.provider_diagnostics[0]["http_status"], 200)
        self.assertEqual(gem_to_adapter.provider_diagnostics[1]["error_category"], "timeout")

    def test_reproduces_request2_unexpected_tool_call_and_verifies_tool_free_gemini_final_synthesis(self) -> None:
        from decimal import Decimal
        import os
        from petcare.ai.contracts import RecommendationCard
        from petcare.ai.memory import SessionState
        from petcare.ai.pilot_runner import _audit_outbound_messages_privacy
        from petcare.ai.recommender_products import ProductRecommendationResult
        from petcare.ai.tools import TOOL_REGISTRY, ToolSpec
        from scripts.run_gemini_qa_web import build_gemini_qa_web_app

        probe_key = "".join(("AIza", "SyUnitTestGeminiFinalSynth0099"))
        app = Flask("gemini-final-synthesis-test")
        app.config.update(
            TESTING=True,
            APP_ENV="test",
            AI_TEST_ALLOW_LOOPBACK_PROVIDER=True,
            AI_PROVIDER="gemini",
            AI_PROVIDER_APPROVED=True,
            AI_TOOL_CALLING_ENABLED=True,
            AI_API_BASE_URL="http://127.0.0.1:19993/v1beta/openai/",
            GEMINI_API_KEY=probe_key,
            AI_MODEL="gemini-3.5-flash-lite",
            AI_HTTP_STEP_TIMEOUT_SECONDS=50.0,
            AI_MAX_HTTP_TIMEOUT_SECONDS=50.0,
            AI_MAX_TURN_TIMEOUT_SECONDS=120,
            AI_TIMEOUT_SECONDS=110.0,
            AI_MAX_TOOL_ROUNDS=2,
        )
        actor = ActorContext(
            user_id=2,
            tenant_id=1,
            role="staff",
            scope=AssistantScope.SHOPPER_PREVIEW,
            locale="vi",
        )

        fake_prod_result = ProductRecommendationResult(
            cards=[
                RecommendationCard(
                    kind="product",
                    entity_id=101,
                    code="FOOD-001",
                    name="Thức ăn cho mèo 1kg",
                    subtitle="Thức ăn",
                    price=Decimal("100000"),
                    currency_code="VND",
                    availability_status="active",
                    score=95,
                    stock_qty=12,
                    unit_price_display="100.000 VND/kg",
                    reasons=["Phù hợp mèo trưởng thành căn hộ, không chứa thịt gà"],
                ),
                RecommendationCard(
                    kind="product",
                    entity_id=104,
                    code="FOOD-004",
                    name="Hạt mèo trong nhà 1.5kg",
                    subtitle="Thức ăn",
                    price=Decimal("210000"),
                    currency_code="VND",
                    availability_status="active",
                    score=92,
                    stock_qty=8,
                    unit_price_display="140.000 VND/kg",
                    reasons=["Dành cho mèo nuôi trong nhà, giá dưới 400.000 VND"],
                ),
            ],
            no_primary_match=False,
            out_of_stock_names=[],
            missing_data_notes=[],
            reasoning_summary="Lọc theo mèo trưởng thành căn hộ, tránh thịt gà, <= 400.000 VND",
            follow_up_questions=[],
        )
        fake_recommend_spec = ToolSpec(
            name="recommend_products",
            description="mock recommend_products",
            allowed_scopes=TOOL_REGISTRY["recommend_products"].allowed_scopes,
            required_role="any",
            max_items=5,
            handler=lambda _actor, **_kw: (fake_prod_result, 2),
        )

        class _SimpleResp:
            def __init__(self, payload: dict):
                self._raw = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _limit: int) -> bytes:
                return self._raw

        step1_tool_call = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "fc-gem-prod-1",
                                "type": "function",
                                "function": {
                                    "name": "recommend_products",
                                    "arguments": json.dumps({
                                        "species": "cat",
                                        "life_stage": "adult",
                                        "product_category": "food",
                                        "allergies": ["chicken"],
                                        "budget_max": 400000,
                                    }),
                                },
                                "extra_content": {"google": {"thought_signature": "GemSig_Step1=="}},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 2117, "completion_tokens": 58, "total_tokens": 2175},
        }

        # (A) Reproduce rogue upstream returning `get_product_detail` on Request 2 despite final-synthesis mode:
        #     Never executes the unexpected tool, records `unexpected_tool_call_on_final_synthesis`, and degrades safely!
        rogue_step2_tool_call = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "fc-rogue-2",
                                "type": "function",
                                "function": {
                                    "name": "get_product_detail",
                                    "arguments": json.dumps({"product_id": 101}),
                                },
                                "extra_content": {"google": {"thought_signature": "GemSig_Step2Rogue=="}},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1350, "completion_tokens": 28, "total_tokens": 1378},
        }

        class _RogueStep2Opener:
            def __init__(self):
                self.idx = 0

            def open(self, req, timeout=15):
                out = step1_tool_call if self.idx == 0 else rogue_step2_tool_call
                self.idx += 1
                return _SimpleResp(out)

        with (
            app.app_context(),
            patch.dict(TOOL_REGISTRY, {"recommend_products": fake_recommend_spec}),
            patch("petcare.ai.client.build_opener", return_value=_RogueStep2Opener()),
        ):
            rogue_adapter = OpenAICompatibleToolCallingAdapter(
                "gemini-3.5-flash-lite",
                max_output_tokens=1536,
                provider_family="gemini",
                max_retries=0,
            )
            rogue_res = run_tool_calling_turn(
                adapter=rogue_adapter,
                actor=actor,
                question="Gợi ý giúp mình thức ăn hạt không chứa thịt gà dưới 400k đang còn hàng cho bé nhé.",
                session_state=None,
                initial_slots=PreferenceSlots(
                    species="cat",
                    living_space="apartment",
                    life_stage="adult",
                    allergies=("chicken",),
                    active_domain="product",
                ),
                conversation_id="conv_rogue_r2",
                offline_fallback_fn=lambda: {"reply": "fb", "engine_mode": "offline"},
            )

        self.assertTrue(rogue_res["fallback_used"])
        self.assertEqual(
            rogue_res["fallback_reason"],
            "provider_error:MalformedModelOutputError:unexpected_tool_call_on_final_synthesis",
        )
        self.assertEqual(len(rogue_res["tool_trace"]), 1)
        self.assertEqual(rogue_res["tool_trace"][0]["tool_name"], "recommend_products")
        self.assertEqual(rogue_adapter.provider_diagnostics[1]["error_category"], "unexpected_tool_call_on_final_synthesis")
        self.assertEqual(rogue_adapter.provider_diagnostics[1]["unexpected_tool_names"], ["get_product_detail"])
        self.assertEqual([c["code"] for c in rogue_res["cards"]], ["FOOD-001", "FOOD-004"])

        # (B) Verify corrected tool-free Gemini Request 2 wire payload with multi-turn session history
        session = SessionState(
            tenant_id=1,
            user_id=2,
            scope=AssistantScope.SHOPPER_PREVIEW,
            conversation_id="conv_gem_synth_ok",
        )
        session.slots = PreferenceSlots(
            species="cat",
            living_space="apartment",
            life_stage="adult",
            allergies=("chicken",),
            active_domain="product",
        )
        session.record_turn("user", "Mình đang nuôi một bé mèo trưởng thành bị dị ứng thịt gà ở căn hộ chung cư nhỏ.")
        session.record_turn("assistant", "Mình đã ghi nhận bé mèo trưởng thành ở căn hộ cần tránh thịt gà.")

        captured_wire: list[dict] = []
        valid_step2_text = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "Dựa trên nhu cầu của bé mèo trưởng thành ở căn hộ, tránh thịt gà và ngân sách dưới 400.000 VND, "
                            "bạn có thể chọn:\n"
                            "1. **Thức ăn cho mèo 1kg (FOOD-001)** — 100.000 VND (còn hàng).\n"
                            "2. **Hạt mèo trong nhà 1.5kg (FOOD-004)** — 210.000 VND (còn hàng)."
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1180, "completion_tokens": 74, "total_tokens": 1254, "thoughts_token_count": 19},
        }

        class _ValidTwoStepOpener:
            def open(self, req, timeout=15):
                idx = len(captured_wire)
                captured_wire.append(json.loads(req.data.decode("utf-8")))
                return _SimpleResp(step1_tool_call if idx == 0 else valid_step2_text)

        with (
            app.app_context(),
            patch.dict(TOOL_REGISTRY, {"recommend_products": fake_recommend_spec}),
            patch("petcare.ai.client.build_opener", return_value=_ValidTwoStepOpener()),
        ):
            clean_adapter = OpenAICompatibleToolCallingAdapter(
                "gemini-3.5-flash-lite",
                max_output_tokens=1536,
                provider_family="gemini",
                max_retries=0,
            )
            clean_res = run_tool_calling_turn(
                adapter=clean_adapter,
                actor=actor,
                question="Gợi ý giúp mình thức ăn hạt không chứa thịt gà dưới 400k đang còn hàng cho bé nhé.",
                session_state=session,
                initial_slots=session.slots,
                conversation_id=session.conversation_id,
                offline_fallback_fn=lambda: {"reply": "fb", "engine_mode": "offline"},
            )

        self.assertEqual(len(captured_wire), 2)
        # Step 1 includes sanitized tools; Step 2 completely omits `tools` and `tool_choice`
        self.assertIn("tools", captured_wire[0])
        self.assertEqual(captured_wire[0]["tool_choice"], "auto")
        self.assertNotIn("tools", captured_wire[1])
        self.assertNotIn("tool_choice", captured_wire[1])

        # Step 2 maintains strict Gemini role alternation: system -> user -> assistant -> user (no orphaned role=='tool')
        step2_roles = [m["role"] for m in captured_wire[1]["messages"]]
        self.assertEqual(step2_roles, ["system", "user", "assistant", "user"])
        final_user_msg = captured_wire[1]["messages"][-1]["content"]
        self.assertIn("VERIFIED_PYTHON_TOOL_RESULTS_JSON", final_user_msg)
        self.assertIn('"applied_filters"', final_user_msg)
        self.assertIn('"chicken"', final_user_msg)
        self.assertIn("FOOD-001", final_user_msg)

        privacy = _audit_outbound_messages_privacy(clean_adapter.recorded_requests)
        self.assertTrue(privacy["passed"])
        self.assertEqual(clean_res["engine_mode"], "real_llm")
        self.assertFalse(clean_res["fallback_used"])
        self.assertIn("FOOD-001", clean_res["reply"])
        self.assertIn("FOOD-004", clean_res["reply"])

        # (C) QA-only Gemini web launcher refuses dev/prod DBs and accepts isolated *_test DBs
        with patch.dict(os.environ, {"APP_ENV": "development", "DB_NAME": "petcare_shop_dev"}, clear=False):
            with self.assertRaises(RuntimeError):
                build_gemini_qa_web_app()
        with patch.dict(os.environ, {"APP_ENV": "production", "DB_NAME": "petcare_gemini_qa_test"}, clear=False):
            with self.assertRaises(RuntimeError):
                build_gemini_qa_web_app()
        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "DB_NAME": "petcare_gemini_qa_test", "GEMINI_API_KEY": probe_key},
            clear=False,
        ):
            qa_web_app = build_gemini_qa_web_app()
            self.assertEqual(qa_web_app.config["AI_PROVIDER"], "gemini")
            self.assertEqual(qa_web_app.config["AI_MAX_TOOL_ROUNDS"], 2)
            self.assertEqual(qa_web_app.config["AI_HTTP_STEP_TIMEOUT_SECONDS"], 50.0)


if __name__ == "__main__":
    unittest.main()
