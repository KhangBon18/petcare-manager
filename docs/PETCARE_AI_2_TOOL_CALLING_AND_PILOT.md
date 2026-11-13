# PetCare AI-2 — LLM Tool-Calling Architecture, Independent OOD Benchmark & Provider Pilot Readiness

> **Status**: Implemented & verified offline with deterministic `MockToolCallingAdapter` (`AI_PROVIDER_APPROVED=0`, `AI_TOOL_CALLING_ENABLED=0`). **Zero live external LLM requests have been executed.** Live activation requires explicit written approval of Section 4 below.

---

## 1. Honest Audit of AI-1 Deterministic Engine & Independent OOD Benchmark (Part B)

### 1.1 Why In-Distribution 100% (`84/84`) Does Not Prove Open-Ended NLU
In PetCare AI-1 (`d05255c04b281a4bdf807722e97f0bfab88c9096`), `petcare/ai/nlu.py` relies on deterministic diacritic stripping (`_normalize`), phrase-tuple matching, and regular expressions, while `petcare/ai/provider.py` (`synthesize_approved_llm_reply`) only performs post-hoc text polishing *after* `nlu.py` and a single hardcoded `execute_tool()` call have already finished.

| Capability Criterion | AI-1 `real_llm` (`provider.py`) | AI-2 Tool-Calling (`llm_tool_agent.py`) |
|---|---|---|
| **A. Understands open-ended user requests** | **No** (100% regex/substring in `nlu.py`) | **Yes** (LLM interprets colloquial, typo, and compound turns) |
| **B. Extracts structured preferences** | **No** (regex-only; monotonic slot append) | **Yes** (JSON-Schema tool args + `clear_allergies` / `clear_budget`) |
| **C. Selects allowed Python tools** | **No** (hardcoded `if/elif`, max 1 tool/turn) | **Yes** (multi-tool selection over RBAC/scope-filtered allowlist) |
| **D. Handles tool results iteratively** | **Partial** (one-shot JSON prompt, no loop) | **Yes** (bounded `role: "tool"` observation loop up to 3 rounds / 4 calls) |
| **E. Produces grounded, verified responses** | **Partial** (no post-LLM prose verification) | **Yes** (`TurnGroundingLedger` + `verify_llm_answer_consistency`) |

### 1.2 Independent Out-of-Distribution (OOD) Evaluation Results
Module: `petcare/ai/independent_evaluation.py` · Runner: `scripts/evaluate_petcare_ai_independent.py`

Measured against isolated MySQL QA (`44` independent cases, `49` conversational turns across `11` categories; ground-truth labels untouched):

- **Overall Case Pass Rate**: **`16 / 44` (`36.36%`)** · **Turn Pass Rate**: **`21 / 49` (`42.86%`)**
- **Hallucinated Item / Price Rate**: **`0.00%`**
- **Unauthorized Cross-Tenant / RBAC Exposure Rate**: **`0.00%`**

| Category | Passed / Total | Pass Rate | Primary Empirical Failure Mode in Deterministic Regex NLU |
|---|---:|---:|---|
| `colloquial_vi` | `2 / 4` | `50.0%` | Slang `"hoàng thượng"` + `"6 củ quay đầu"` missed; `"giá hạt dẻ dưới 4 xị"` normalized `"giá"` → `"gia"`, colliding with elderly life-stage `"gia"` (`senior`) and parsing `budget_max=4` VND! |
| `typos_no_diacritics` | `1 / 4` | `25.0%` | Chat shorthand `"rcm hat cho meo truog thanh"`, `"pate ca ngu"`, `"ss dum minh"` miss exact keyword tuples. |
| `complex_multi_intent` | `0 / 4` | `0.0%` | Single-intent `if/elif` router cannot combine BM25 care guidance + product cards or sales + restock insights in one turn. |
| `followup_corrections` | `1 / 4` | `25.0%` | `merge_preference_slots` appends allergies monotonically and cannot clear negated allergies or remove a prior budget cap. |
| `ambiguous_budgets` | `2 / 4` | `50.0%` | Qualitative `"giá sinh viên"` and English number words (`"five to seven million VND"`) bypass digit regexes. |
| `natural_product_comparison` | `2 / 4` | `50.0%` | Natural phrasing (`"Đặt lên bàn cân..."`, `"Which gives better value per kg..."`) misses `_COMPARISON_PHRASES`. |
| `nuanced_pet_matching` | `2 / 4` | `50.0%` | Implicit constraints (`"em bé sơ sinh ngủ rất nhạy"`, `"35m2 studio flat"`) lack literal `"hiền"` / `"apartment"` tokens. |
| `insufficient_data` | `0 / 4` | `0.0%` | Undocumented `% protein`, vaccine dates, or exotic species (`Hamster`) trigger generic clarification or empty lists without explicit missing-field disclosure. |
| `unsafe_vet_advice` | `0 / 4` | `0.0%` | Brand-name human drugs (`Berberin`, `Smecta`, `Tylenol`), `"chứa xylitol"`, and descriptive urinary blockage (`"vào khay cát cứ ngồi rặn mãi..."` matching `"khay cát"` → `litter`!) bypass static safety phrases. |
| `prompt_injection` | `2 / 4` | `50.0%` | Indirect translation prompt-extraction and `[SYSTEM OVERRIDE]` framing route to generic catalog clarification instead of explicit policy refusal. |
| `tenant_access_restrictions` | `4 / 4` | `100.0%` | Server-side RBAC, `shopper_preview` guardrails, and MySQL `@petcare_tenant_id` held at **100%**. |

---

## 2. Secure AI-2 LLM Tool-Calling Architecture (Part C & Part D)

### 2.1 End-to-End Execution Pipeline
```text
User Question
  │
  ▼
[1. Pre-LLM Deterministic Guardrails (orchestrator.py)]
  ├── Conversation reset (`reset_context`), SQL/prompt-injection/write-action refusals,
  │   and unambiguous vet emergencies handled immediately in 0 external calls.
  └── Server resolves `ActorContext(user_id, tenant_id, role, scope, locale)` from Flask session + MySQL `require_actor()`.
  │
  ▼
[2. Scoped Tool Schema Filtering (tool_schemas.py)]
  └── `list_openai_tools_for_actor(actor)` exposes ONLY read-only tools authorized for `(actor.scope, actor.role)`:
      • `shopper_preview`: 8 public catalog/matching/comparison/KB tools only.
      • `workspace` (`staff`): + `get_restock_insights`, `get_sales_summary` (10 tools).
      • `workspace` (`admin`): + `get_purchase_status`, `get_inventory_forecast`, `get_operations_overview` (13 tools).
  │
  ▼
[3. Bounded Tool-Calling Loop (llm_tool_agent.py :: run_tool_calling_turn)]
  ├── Hard caps: `AI_MAX_TOOL_ROUNDS=3`, `AI_MAX_TOTAL_TOOL_CALLS=4`, `AI_TOOL_TIMEOUT_SECONDS=3.0`, `AI_TIMEOUT_SECONDS=8.0`.
  ├── Strict server-side argument validator (`validate_and_build_tool_kwargs`):
  │   • Rejects unknown keys and privilege-escalation keys (`tenant_id`, `actor_id`, `user_id`, `role`, `scope`).
  │   • Enforces integer bounds, enum allowlists, SKU regex (`^[A-Z]{2,6}-\d{2,4}$`), and SQL-fragment blocking.
  │   • Supports structured slot updates including `clear_allergies` and `clear_budget`.
  └── Executes existing read-only Python services via `execute_tool()` inside a timeout-bounded `ContextVar` executor.
  │
  ▼
[4. Server-Owned TurnGroundingLedger & Post-LLM Consistency Verifier]
  ├── `TurnGroundingLedger` records every verified SKU/pet code, exact `Decimal` price, zero-stock code, citation `doc_id`, and source URL.
  ├── `verify_llm_answer_consistency(reply_text, ledger)` blocks:
  │   1. Any SKU/pet/KB code not retrieved in the current turn (`hallucinated_catalog_code` / `hallucinated_citation_id`).
  │   2. Any currency figure not matching retrieved prices or user budget (`ungrounded_or_contradictory_price`).
  │   3. Any `"còn hàng"` / `"in stock"` claim on a `stock_qty == 0` item (`contradictory_stock_status`).
  │   4. Any `mg/kg` dosage or human OTC medication name (`unsafe_medical_content`).
  │   5. Any URL outside verified knowledge citations (`untrusted_url`).
  └── On ANY provider error, timeout, budget exhaustion, or consistency violation:
      • Automatically falls back to deterministic Python composition from `TurnGroundingLedger` (if tools succeeded)
        or Mode A (`assistant_service.answer(..., _force_offline=True)`), setting `fallback_used=True`.
```

---

## 3. Provider Pilot Readiness Plan (Part E — Official Verified Specifications)

### 3.1 Recommended Provider & Model Candidates
Because `petcare/ai/client.py` (`complete_chat_with_tools`) speaks the standard OpenAI Chat Completions `tools` (`type: "function"`) contract over HTTPS, two official production-grade providers are directly compatible without SDK lock-in:

| Attribute | Primary Recommended Pilot: **OpenAI `gpt-4o-mini`** *(or `gpt-4.1-mini`)* | Secondary Compatible Option: **Google Gemini `gemini-3.1-flash-lite`** *(Paid Tier)* |
|---|---|---|
| **HTTPS Endpoint** | `https://api.openai.com/v1/chat/completions` | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` |
| **Tool-Calling Contract** | Native `tools: [{"type": "function", ...}]`, `tool_choice: "auto"`, parallel & multi-turn `role: "tool"` | OpenAI-compatible `tools` & `tool_choice: "auto"` endpoint |
| **Input Token Price** | **`$0.15` / 1M tokens** (`$0.075` cached) · *(`gpt-4.1-mini`: `$0.40` / 1M)* | **`$0.25` / 1M tokens** (`$0.025` cached) |
| **Output Token Price** | **`$0.60` / 1M tokens** · *(`gpt-4.1-mini`: `$1.60` / 1M)* | **`$1.50` / 1M tokens** |
| **Training on API Data** | **Never used for training** by default (OpenAI API Terms) | **Paid Tier**: Not used for training. *(Free Tier trains on data — **NEVER USE FREE TIER**)* |
| **Abuse Log Retention** | Up to **30 days** by default; Zero Data Retention (`ZDR`) available on eligible orgs | Paid API retains abuse logs briefly; strict `ZDR` requires Google Cloud Vertex AI |

### 3.2 Exact Data Sent Externally When Enabled
- **Sent**:
  1. System prompt (`_build_system_prompt`) + active session `PreferenceSlots` summary (species, budget, living space, life stage, allergies).
  2. Up to `6` redacted recent turn summaries (`<= 400` chars each, passed through `redact_sensitive_text` stripping emails, phone numbers, card numbers, and secrets).
  3. Current user message (`<= 800` chars, PII-redacted).
  4. Minimized read-only tool observations (`<= 4,000` chars per call): public pet/product codes, names, prices, stock counts, reviewed KB snippets, or aggregated SKU sales/restock counts (workspace only).
- **NEVER Sent**:
  - Customer names, phone numbers, emails, addresses (`customers` table), invoice buyer identities, staff password hashes, session cookies, CSRF tokens, `.env` secrets, or cross-tenant rows.

### 3.3 Expected Cost & Budget Controls
- **Per-Turn Token Estimate** (typical 2-round tool-calling turn):
  - Round 1 (system prompt + 10 tool schemas + history + user prompt): `~1,150` input tokens, `~80` output tokens.
  - Round 2 (prior transcript + compact JSON tool observation): `~1,350` input tokens, `~220` output tokens.
  - **Total per turn**: `~2,500` input tokens + `~300` output tokens.
- **Estimated Cost**:
  - **`gpt-4o-mini`**: `~$0.000555` / turn (**`~$0.56` per `1,000` turns**).
  - **`gpt-4.1-mini`**: `~$0.00148` / turn (**`~$1.48` per `1,000` turns**).
  - **`gemini-3.1-flash-lite` (Paid)**: `~$0.001075` / turn (**`~$1.08` per `1,000` turns**).
- **Mandatory Budget Controls**:
  - Configure a **hard monthly spend cap of `$5.00` USD** (soft alert at `$2.00` USD) in a dedicated isolated `"PetCare-AI2-Pilot"` project before generating any API key.

### 3.4 Credential, Timeout, Retry & Rate-Limit Policy
- **Credentials**: Dedicated project-scoped `AI_API_KEY` stored exclusively in host secret manager / untracked `.env` (`0600` permissions), never committed to Git or baked into Docker images.
- **Request & Loop Caps**:
  - `AI_MAX_TOOL_ROUNDS=3` (max 3 model completions per user message).
  - `AI_MAX_TOTAL_TOOL_CALLS=4` (max 4 Python tool executions per user message).
  - `complete_chat_with_tools(..., max_retries=1)`: **at most 1 retry** on transient `408/500/502/503/504` or socket timeout; **0 retries** on `400/401/403/429` or malformed JSON.
- **Timeouts & Rate Limits**:
  - `AI_TOOL_TIMEOUT_SECONDS=3.0` per Python tool call.
  - `AI_TIMEOUT_SECONDS=8` wall-clock deadline per turn.
  - Existing server rate limiters remain active: `ASSISTANT_RATE_LIMIT_PER_MINUTE=20` (per user) and `ASSISTANT_IP_RATE_LIMIT_PER_MINUTE=60` (per IP).

### 3.5 Pilot Evaluation Dataset & Acceptance Criteria
Before promoting `AI-2` beyond an isolated staging pilot, run **both** suites against a disposable `_test` MySQL schema:
1. `scripts/evaluate_petcare_ai.py` (`84` core cases) -> **Required**: `>= 98%` case pass rate, `0.0%` hallucination rate, `0.0%` RBAC/tenant leak rate.
2. `scripts/evaluate_petcare_ai_independent.py` (`44` OOD cases) -> **Required**:
   - Overall case pass rate **`>= 85%`** (up from `36.36%` deterministic baseline).
   - `unsafe_vet_advice` pass rate **`100%`** (`4/4` emergency & OTC medication escalations).
   - `tenant_access_restrictions` & `prompt_injection` pass rate **`100%`**.
   - `hallucinated_item_or_price_rate == 0.0` (`0%` unverified SKUs/prices reaching response).
   - End-to-end `p95` turn latency **`<= 4,500 ms`** and fallback rate **`< 5%`**.

### 3.6 Instant Rollback / Disable Procedure
Disabling external LLM tool calling requires **zero database migrations and zero code reverts**:
1. Set `AI_TOOL_CALLING_ENABLED=0` and `AI_PROVIDER_APPROVED=0` in runtime environment variables.
2. Reload Gunicorn / restart web container (`docker compose up -d web` or `kill -HUP <gunicorn-master-pid>`).
3. Verify `GET /assistant/chat` bootstrap metadata reports `active_mode: "offline"` and `tool_calling_enabled: false`. Traffic immediately runs 100% on deterministic Python Mode A (`~10 ms` latency).

---

## 4. Explicit Approval Gate Before Live Provider Activation
Do **not** set `AI_PROVIDER_APPROVED=1` or `AI_TOOL_CALLING_ENABLED=1` until the project owner explicitly confirms:
1. Selected provider & model (`gpt-4o-mini`, `gpt-4.1-mini`, or paid-tier `gemini-3.1-flash-lite`).
2. Acceptance of vendor API data-processing & 30-day abuse-log retention terms (or ZDR enrollment).
3. Provisioning of a dedicated project API key with a hard `$5–$10/month` spend ceiling.
4. Approval to run the `84 + 44 = 128` evaluation cases (~`$0.08–$0.20` total token spend) against disposable synthetic `_test` data first.
