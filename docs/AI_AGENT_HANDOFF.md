# PetCare AI — Release & Agent Handoff (`AI-3.2` Google Gemini Free Tier Integration)

## 1. Release Scope & Production Safety Defaults
- **Branch**: `solo/khang-petcare`
- **Milestone**: `AI-3.2` — Verified Google Gemini Free Tier (`gemini-3.5-flash-lite`) Live Tool-Calling & Website QA Integration.
- **Production & Default Safety Invariant**:
  - External LLM execution remains **disabled by default** in `petcare/config.py` and `.env.example`:
    - `AI_PROVIDER_APPROVED = False` (`0`)
    - `AI_TOOL_CALLING_ENABLED = False` (`0`)
    - `AI_VISION_ENABLED = False` (`0`)
    - `AI_PILOT_KILL_SWITCH = False` (`0`)
  - Even when `GEMINI_API_KEY` is present in the environment, PetCare AI stays in `EngineMode.OFFLINE` (`diagnostic_state="offline_disabled"`) unless explicitly approved for a controlled QA session.
  - Existing OpenAI (`gpt-6-luna`) and Offline Python Mode A workflows, all `13` read-only Python tools, server-side RBAC (`workspace` vs `shopper_preview`, `admin` vs `staff`), tenant isolation, pre/post-LLM veterinary safety triage, and MySQL grounding verification remain intact.

---

## 2. Gemini Provider & Wire Architecture
- **Provider Family**: `gemini` (`AI_PROVIDER=gemini`)
- **Verified Free Tier Model**: `gemini-3.5-flash-lite` (`Config.DEFAULT_GEMINI_MODEL`)
- **OpenAI-Compatible Base URL**: `https://generativelanguage.googleapis.com/v1beta/openai/` (normalized to `/v1beta/openai/chat/completions` in `petcare/ai/client.py`).
- **2-Step Function-Calling & Grounded Synthesis Protocol**:
  1. **Step 1 — Authorized Tool Selection (`tool_choice="auto"`)**:
     - Sends Gemini-sanitized OpenAPI 3.0 tool schemas (`sanitize_tool_schema_for_gemini()` strips `additionalProperties`, `pattern`, `minLength`, `maxLength`, `uniqueItems`, and omits empty `parameters` on zero-arg `get_operations_overview` while Python's `validate_and_build_tool_kwargs()` enforces full server-side validation).
     - Omits GPT-6's `reasoning_effort="none"` (unsupported on Gemini 3.5) and allocates thinking-safe `max_tokens` (`>= 1200`, `1536` in QA).
     - Preserves `extra_content.google.thought_signature` and exact `tool_call.id` (including `""`) across multi-round tool calls.
  2. **Python Server-Side Execution & Grounding Ledger**:
     - Validates tool name against `TOOL_REGISTRY`, enforces `ActorContext` scope/role/tenant boundaries, queries MySQL/BM25, and records allowed SKUs, exact prices, stock status, and `applied_filters` inside `TurnGroundingLedger`.
  3. **Step 2 — Tool-Free Final Grounded Synthesis (`build_gemini_final_synthesis_messages()`)**:
     - Because Gemini's `/v1beta/openai/` translation layer can still emit unconstrained `tool_calls` when `tools` remain present alongside `tool_choice="none"`, Step 2 converts verified tool outputs into `VERIFIED_PYTHON_TOOL_RESULTS_JSON` inside a strict `system -> user -> assistant -> user` turn sequence and **omits `"tools"` and `"tool_choice"` completely** from the HTTP payload.
     - Post-generation `verify_llm_answer_consistency()` verifies every SKU code, explicit price, stock claim, URL, and medical safety boundary before returning `engine_mode="real_llm"`.

---

## 3. Verified Live & Offline Quality Gates

### Live Google Gemini Free Tier Verification (`petcare_gemini_qa_test`, `0` Paid Calls)
1. **CLI 2-Call Live Smoke (`scripts/run_gemini_free_tier_smoke.py --mode live --preset quick-2calls`) — PASS (`17/17` criteria)**:
   - `passed=True`, `live_engine_confirmed=True`, `engine_mode="real_llm"`, `fallback_used=False`, `fallback_reason=None`.
   - `live_network_calls_made=2` (Step 0: `HTTP 200`, `finish_reason="tool_calls"`, `has_thought_signature=True` -> Python `recommend_products` returned `5` verified items in `25.24 ms`; Step 1: `HTTP 200`, `finish_reason="stop"`, `tool_calls_count=0` -> grounded Vietnamese answer).
   - Retained `species="cat"`, `living_space="apartment"`, `life_stage="adult"`, `allergies=["chicken"]`, `budget_max="400000"`; excluded chicken products (`FOOD-002`, `FOOD-005`); `outbound_privacy_audit.passed=True`; `total_tokens=4494` (`15.91s`).
2. **Website Chat UI Live E2E (`scripts/run_gemini_qa_web.py` + Headless Chromium `/assistant/chat`) — PASS**:
   - Logged into `main` store (`staff1`), opened `/assistant/chat?scope=shopper_preview`, verified `data-request-timeout-ms="110000"`, submitted live Vietnamese query.
   - `POST /assistant/chat` returned `HTTP 200` (`4.22s` provider latency, `2` rounds, `total_tokens=4189`), `engine_mode="real_llm"`, `mode="ai"`, `fallback_used=False`.
   - Header badge transitioned to `data-engine-state="real_llm_confirmed"`, provenance footer rendered `data-engine-mode="real_llm"`, `5` `.ai-rec-card` cards rendered in DOM, `0` console errors.

### Offline Automated Regression Suites (`0` External API Calls)
- **Python / MySQL Suite**: **`509 / 509` PASS** (`0` skipped)
- **AI & Gemini Unit Suite**: **`57 / 57` PASS**
- **JavaScript Suite**: **`47 / 47` PASS**
- **Playwright Browser Smoke & E2E**: **`26 / 26` PASS** (desktop + `390x844` mobile + `axe-core` WCAG 2.1 AA)
- **Bandit Security & Whitespace Audit**: **PASS** (`0` new findings)

---

## 4. Required Environment Variables & Free Tier Rate Limits

| Variable | Default | Gemini QA Recommended | Purpose |
| :--- | :--- | :--- | :--- |
| `AI_PROVIDER` | `""` | `gemini` | Selects Google Gemini OpenAI-compatible provider family |
| `AI_MODEL` | `""` | `gemini-3.5-flash-lite` | Free-Tier-eligible Gemini model supporting function calling |
| `GEMINI_API_KEY` | `""` | *(local env secret only)* | Sent exclusively via `Authorization: Bearer` header; never committed |
| `AI_PROVIDER_APPROVED` | `0` | `1` *(QA only)* | Explicit approval gate required before any outbound LLM call |
| `AI_TOOL_CALLING_ENABLED` | `0` | `1` *(QA only)* | Enables 2-step authorized Python tool calling |
| `AI_PILOT_KILL_SWITCH` | `0` | `0` (`1` to abort) | Immediate kill switch forcing Offline Mode A |
| `AI_MAX_TOOL_ROUNDS` | `3` | `2` | Caps Gemini QA turns to Step 1 (tool call) + Step 2 (grounded synthesis) |
| `AI_HTTP_STEP_TIMEOUT_SECONDS` | `0` | `50` | Per-HTTP-request socket timeout for Gemini QA (`5..60s`) |
| `AI_MAX_HTTP_TIMEOUT_SECONDS` | `15` | `50` | Upper bound on client HTTP socket timeout (`<= 60s`) |
| `AI_TIMEOUT_SECONDS` | `15` | `110` | Total 2-step turn deadline (`AI_MAX_TURN_TIMEOUT_SECONDS=120`) |
| `AI_MAX_OUTPUT_TOKENS` | `700` | `1536` | Output token budget covering Gemini thinking + Vietnamese prose |
| `AI_RATE_LIMIT_RPM` / `TPM` / `RPD` | `10` / `180000` / `450` | `10` / `180000` / `450` | Conservative sliding-window guard below Google AI Studio Free Tier (`~15 RPM / 250k TPM / 500 RPD`) |
| `AI_MIN_REQUEST_INTERVAL_MS` | `1200` | `1200` | Minimum `1.2s` pacing between Step 1 and Step 2 |

---

## 5. Safe QA Startup Instructions (CLI & Website UI)

> **Important**: `scripts/demo/classroom.sh --target qa` intentionally sets `APP_ENV=test` and `AI_MODEL=petcare-local-demo-mock`, forcing Offline Python mode for zero-quota classroom demos. Use the dedicated isolated QA commands below (against a disposable `*_test` MySQL container, never `_dev` or `production`) when testing live Gemini Free Tier.

### A. 2-Call CLI Smoke Test (Isolated `*_test` MySQL)
```bash
GEMINI_API_KEY="<local_env_key>" \
AI_PROVIDER=gemini \
AI_MODEL=gemini-3.5-flash-lite \
AI_PROVIDER_APPROVED=1 \
AI_TOOL_CALLING_ENABLED=1 \
DB_HOST=127.0.0.1 \
DB_PORT=33339 \
DB_NAME=petcare_gemini_qa_test \
DB_USER=root \
DB_PASSWORD="<disposable_qa_password>" \
.venv/bin/python scripts/run_gemini_free_tier_smoke.py \
  --mode live \
  --confirm-live-gemini \
  --preset quick-2calls \
  --max-api-calls 3 \
  --timeout-seconds 50 \
  --max-output-tokens 1536 \
  --skip-init \
  --json-out /tmp/petcare-gemini-smoke.json
```

### B. Dedicated Gemini-Enabled QA Website Server (`http://127.0.0.1:5095`)
```bash
GEMINI_API_KEY="<local_env_key>" \
DB_HOST=127.0.0.1 \
DB_PORT=33339 \
DB_NAME=petcare_gemini_qa_test \
DB_USER=root \
DB_PASSWORD="<disposable_qa_password>" \
PETCARE_DEMO_ADMIN_PASSWORD="<16+_char_qa_admin_pw>" \
PETCARE_DEMO_STAFF_PASSWORD="<16+_char_qa_staff_pw>" \
.venv/bin/python scripts/run_gemini_qa_web.py \
  --port 5095 \
  --skip-init \
  --sync-demo-passwords
```

---

## 6. Offline Fallback, Security & Known Test Limitations

- **Graceful Offline Fallback (`0` Billing / Paid-Model Escalation)**:
  - Upstream `HTTP 429` (`Retry-After` cooldown), local `FreeTierRateLimiter` saturation, socket timeouts, malformed JSON, unexpected tool calls during final synthesis (`unexpected_tool_call_on_final_synthesis`), or post-generation grounding mismatches (`verify_llm_answer_consistency`) never retry infinitely and never switch to a paid model. When Step 1 already retrieved verified Python tool data, PetCare AI composes a deterministic grounded answer from `TurnGroundingLedger`; otherwise it falls back to Offline Mode A (`fallback_used=True`, explicit `fallback_reason`).
- **Security Controls**:
  - Outbound HTTPS enforces `ssl.CERT_REQUIRED` and `check_hostname=True` (`_build_verified_ssl_context()`, loading `certifi.where()` automatically when macOS Python lacks `/etc/ssl/cert.pem`).
  - SSRF validation blocks private/link-local/cloud-metadata IPs and requires HTTPS for `generativelanguage.googleapis.com`.
  - Secret scrubbing in `client.py`, `memory.py`, and `pilot_runner.py` strips bearer tokens, `AIza...` / `sk-...` patterns, and exact runtime `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `AI_API_KEY` values from error diagnostics, session memory, and JSON reports.
- **Known Test Limitations & Immutable Benchmark Checksums**:
  - **Untouched AI-2.2 Hold-Out Discrepancy (`39 / 40`, `97.5%`)**: In `petcare/ai/final_safety_generalization_eval.py`, case `FG-MUL-01` (`complex_multi_intent`) expects citation typo `'KB-NUT-001'` whereas the canonical reviewed knowledge-base document ID returned by BM25 is `'KB-NUTR-001'` (`citations=['KB-ENV-004', 'KB-NUTR-001']`). All `15 / 15` veterinary safety cases (`100%` recall, `100%` precision, `0` FN, `0` FP), `100%` grounding, and `100%` RBAC assertions pass. Per benchmark integrity rules, no hold-out expectations were modified:
    - `petcare/ai/evaluation.py` (`84/84`): `beb3a4bbed06e2c34385281eb7b685ca54dd5ec1a494cc965ad84b45718a774f`
    - `petcare/ai/independent_evaluation.py` (`44/44`): `0b3164c3080dd785b7e002616f7368fd789b5c12b170c5b8d94f72d417d541b3`
    - `petcare/ai/heldout_safety_evaluation.py` (`34/34`): `bf96282d651f63c2d11fb0c5cf2e4874389bc7c31d233101f811af6055a2a4ef`
    - `petcare/ai/final_safety_generalization_eval.py` (`39/40`): `ba182d224530be82031dbc4e2db237d7ee881fe8a15d1023170fc8e24fd3362c`
  - **CI Execution Policy**: GitHub Actions runs strictly offline (`AI_PROVIDER_APPROVED=0`, `0` external API calls); live Gemini verification is performed only in bounded QA sessions on synthetic `*_test` data.
  - **Free Tier Latency Variance**: Under shared Google AI Studio Free Tier load, 2-step Gemini turns observed `4.2s–15.9s` end-to-end latency (`50s` per-step / `110s` turn-deadline configured in QA).
