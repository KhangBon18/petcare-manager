# PetCare AI-3 — Controlled Real-LLM Pilot Readiness

## 1. Milestone Scope & Operational Invariants

`AI-3` prepares **PetCare AI — Intelligent Pet Shopping & Care Assistant** on branch `solo/khang-petcare` (base commit `60336283750f6818f76d5d00cd3f7cc02140b929`) to transition safely from deterministic offline NLU to a **genuine, controlled LLM-powered natural-language understanding and tool-calling pilot**, while preserving Python business logic, strict server-side RBAC/tenant isolation, deterministic offline fallback, and independent veterinary safety triage.

- **Live External LLM Calls Executed in AI-3**: **`0`** (`AI_PROVIDER_APPROVED=0` and `AI_TOOL_CALLING_ENABLED=0` remain disabled by default in `petcare/config.py`).
- **Database Safety**: Zero modifications to development (`petcare_shop_dev` on `127.0.0.1:3306`) or production data; all verification executed against a disposable `mysql:8.4` QA instance (`petcare_ai3_qa_test`).
- **Benchmark Integrity**: Zero existing benchmark cases were relabeled or edited (`evaluation.py`, `independent_evaluation.py`, `heldout_safety_evaluation.py`, and `final_safety_generalization_eval.py` retain identical SHA-256 checksums). Because `AI-3` closes the 4 safety gap classes previously surfaced by `final_safety_generalization_eval.py`, that 40-case suite is now classified as an **immutable regression suite** rather than an unseen hold-out.

---

## 2. Server-Side Veterinary Safety Hardening (4-Tier Separation)

`petcare/ai/safety_triage.py` and `petcare/ai/knowledge_base.py` execute deterministically **before** shopping intent routing, catalog search, or LLM invocation, separating four explicit clinical/care tiers:

| Tier (`SafetyTriageDecision.outcome`) | Clinical / Policy Scope | Server Action | Shopping Cards Returned |
| :--- | :--- | :--- | :--- |
| `1. "none"` | General dog/cat care knowledge (`KB-*`), negative ingredient filters (`xylitol-free`), dietary allergies, resolved historical illnesses, negated symptoms, routine healthy shopping | Normal KB / catalog / LLM tool routing with `disclaimer` notice on care guidance | Allowed when shopping |
| `2. "vet_nonurgent_referral"` | Active subacute or unrecognized clinical concerns paired with shopping (multi-day anorexia with lethargy/fever, purulent swelling/abscess/discharge, acute painful non-weight-bearing lameness, persistent repeated vomiting/watery diarrhea) | Prefers safe veterinary referral & clinical clarification (`severity="vet_referral"`, cites `KB-VET-009`) over retail product recommendations | **`0` cards** |
| `3. "vet_emergency"` | Potentially life-threatening acute symptoms & incidents (urinary straining without urine, open-mouth/orthopnea breathing, acute toxin ingestion, double-dosed insulin / medication overdose, post-op suture dehiscence with exposed tissue, head-pressing/icterus, pale gums/shock, GDV, hemorrhage, seizures, trauma) | Immediate emergency veterinary escalation (`severity="emergency"`, cites `KB-VET-009` + `KB-SAFE-002`) | **`0` cards** |
| `4. "vet_medical_boundary"` | Unsafe medical instruction requests: human OTC medications (`Panadol`, `Efferalgan`, `ibuprofen`, `Berberin`, `loperamide`), unsafe home emetics (`hydrogen peroxide`), `mg/kg` drug dosing, antibiotic prescriptions, or disease diagnosis | Explicit refusal & veterinary referral (`severity="medical_boundary"`) | **`0` cards** |

### Closure of Known Safety Gaps via Reusable Compositional Detection
1. **Urinary Straining + Absent/Scant Output (`FG-VET-POS-01` class)**: Clause-scoped, negation-aware composition combining repeated/agitated litter-box visits or straining posture (`nhảy ra nhảy vô chậu cát`, `ngồi rặn`, `in and out of the litter box`) with absent/scant urine or vocal pain (`không rỉ được giọt nước tiểu nào`, `dry litter`, `yowling`).
2. **Word-Order-Independent Respiratory Effort + Open-Mouth / Orthopnea (`FG-VET-POS-02` class)**: Co-occurrence of active non-negated respiratory verbs (`breathing`, `panting`, `wheezing`, `thở`) with open-mouth modifiers (`mouth wide/fully/hanging open`, `há rộng miệng`) or orthopnea posture (`neck extended`, `sitting hunched`, `abdomen heaving`), excluding benign dental-brushing or post-play fetch contexts.
3. **Therapeutic Medication Overdose / Double-Dosing Incidents (`FG-VET-POS-11` class)**: Compositional incident detector pairing accidental double/overdose administration (`injected ... twice`, `double dose`, `tiêm nhầm hai mũi`, `quá liều`) with therapeutic agents (`insulin`, `medication`, `thuốc tiểu đường`, `phenobarbital`), plus insulin + acute neuroglycopenic signs (`wobbling`, `staring blankly`, `loạng choạng`).
4. **Post-Operative Wound Dehiscence & Exposed Tissue (`FG-VET-POS-12` class)**: Compositional detector pairing surgical/suture sites (`spay`, `stitches`, `incision`, `vết mổ`, `chỉ khâu`, `triệt sản`) with dehiscence/evisceration (`chewed open`, `bung chỉ`, `pink tissue is poking out`, `lòi thịt hồng`), while leaving benign post-surgery recovery collar shopping untouched when no dehiscence is present.

### Remaining Safety Limitations (Explicitly Disclosed)
- Triage rules reference public owner-education guidance from AVMA, ASPCA Animal Poison Control, AAHA Diabetes Management Guidelines, and the Cornell Feline Health Center, **not** clinical sign-off by a licensed Doctor of Veterinary Medicine (`DVM`).
- Compositional lexical/clause rules still cannot anticipate every rare, metaphorical, or multi-sentence indirect clinical description without lexical overlap; therefore, the LLM system prompt (`_build_system_prompt`), mid-loop tool-argument Gate 2, and post-generation consistency verifier (`_SAFETY_OVERRIDE_DISMISSAL_RE`) remain active as defense-in-depth layers.

---

## 3. Real-LLM Execution Path & Hardened Security Boundaries

Verified end-to-end execution pipeline:

```text
User Question
  -> Gate 1: Server-Side Veterinary & Policy Triage (safety_triage.py / nlu.py)
  -> Gate 2: Provider Approval, Kill-Switch & Input-Token Guard (provider.py / llm_tool_agent.py)
  -> LLM Natural-Language Interpretation (OpenAICompatibleToolCallingAdapter)
  -> Gate 3: Strict JSON Schema, Forbidden-Arg (`tenant_id`, `role`, `sql`) & RBAC Check (tool_schemas.py / tools.py)
  -> Read-Only Python Business Execution on Tenant-Scoped MySQL (`recommend_pets`, `recommend_products`, `compare_products`, BM25 KB, Ops)
  -> Server-Owned TurnGroundingLedger (verified IDs, codes, VND prices, stock counts, KB doc IDs & URLs)
  -> LLM Grounded Answer Composition
  -> Gate 4: Server-Side Consistency Verifier (`verify_llm_answer_consistency`: blocks hallucinated SKUs/prices/URLs, false stock claims, drug dosages & vet-dismissal overrides)
  -> Deterministic Python Fallback on Timeout / Error / Consistency Failure
  -> `/assistant/chat` UI with Honest Mode & Provenance Diagnostics
```

### Key Hardening Fixes Implemented in AI-3
- **Closed Legacy Unapproved Provider Egress (`petcare/services/assistant_service.py`)**: Legacy workspace store queries now require `AI_PROVIDER_APPROVED=True` and `AI_PILOT_KILL_SWITCH=False` before calling `ai_client.complete()`.
- **Eliminated Misleading UI Connection Badge (`petcare/templates/base.html` & `chat.html`)**: `"AI tạo sinh đang bật"` and external data-transmission disclosures now render **only** when `AI_PROVIDER_APPROVED=True` and `AI_PILOT_KILL_SWITCH=False`. Workspace header `#ai-engine-badge` exposes `data-engine-state` (`offline_disabled`, `offline_kill_switch`, `approved_llm_prose`, `approved_llm_tool_calling`), and turn footers distinguish `Approved Real LLM` vs `Offline Python Fallback` vs `Offline Python Engine`.
- **SSRF & Preflight Provider Validation (`petcare/ai/client.py` & `petcare/ai/provider.py`)**: `validate_endpoint_url()` and `validate_provider_configuration()` block cloud metadata (`169.254.169.254`), link-local, multicast, and unauthorized RFC1918/loopback targets before socket creation, validate model names and token/round/timeout bounds, and never echo API keys or headers.
- **Token & Latency Instrumentation (`petcare/ai/llm_tool_agent.py`)**: `ModelTurnOutput` and `run_tool_calling_turn()` record `prompt_tokens`, `completion_tokens`, `total_tokens`, `rounds_completed`, and `provider_latency_ms` under `response["llm_usage"]`.

---

## 4. Privacy & External Data Exposure Contract

When a live provider is explicitly approved in a future pilot, **only** the following minimized fields can leave the application boundary:

1. **System Prompt**: Read-only behavioral instructions + sanitized `PreferenceSlots.to_public_dict()` (`species`, `budget_min`, `budget_max`, `living_space`, `temperament`, `size_preference`, `life_stage`, `allergies`, `product_category`).
2. **Recent Conversation Context**: Up to `6` prior turns from the same `(tenant_id, user_id, scope, conversation_id)` session, each passed through `redact_sensitive_text(..., max_chars=400)`.
3. **Current User Question**: Passed through `redact_sensitive_text(..., max_chars=800)`.
4. **Allowlisted OpenAI Function Schemas**: Filtered strictly by `ActorContext` (`shopper_preview` receives `8` public catalog/KB tools only; `staff` receives `11`; `admin` receives `13` read-only tools).
5. **Minimized Tool Observations (`<= 4,000` chars)**: Public pet/product attributes (`id`, `code`, `name`, `price`, `stock_qty`, `unit_price_display`, `reasons`, `warnings`), reviewed KB text/citations, or aggregated product-level sales/forecast counts in `workspace`.

### Strictly Excluded Data (Verified by Automated Outbound Privacy Audit)
- Customer full names, phone numbers, email addresses, street addresses, or private notes
- Passwords, password hashes, `SECRET_KEY`, `AI_API_KEY`, `DB_PASSWORD`, or `OPS_METRICS_TOKEN`
- Flask session cookies or `X-CSRFToken` headers
- Private invoice customer headers or line-level customer purchase histories
- Cross-tenant catalog, inventory, or operational records
- Complete unfiltered MySQL rows

---

## 5. Controlled Pilot Harness & Mock Demonstration Evidence

 CLI entrypoint: `scripts/run_petcare_ai_pilot.py` (backed by `petcare/ai/pilot_runner.py`).
- **Default Mode**: `--mode dry-run` (`0` DB writes, `0` network calls).
- **Safety & Spend Guards**:
  - Refuses to execute `mock` or `live` modes unless `DB_NAME` ends with `_test` (`PilotIsolationError`).
  - Refuses `--mode live` unless `AI_PROVIDER_APPROVED=1`, `AI_TOOL_CALLING_ENABLED=1`, `validate_provider_configuration()` passes, **and** `--confirm-live-pilot` is supplied on the CLI.
  - Enforces `PilotBudgetAndSafetyGuard` **before** every turn and **before** every tool-calling round (`step_guard`): checks `max_requests`, `max_input_tokens`, `max_output_tokens`, `max_total_tokens`, `max_concurrency` (`1..2`), and cumulative + worst-case next-step USD cost against `max_cost_usd` (never relying solely on upstream provider billing dashboards).
  - Immediate kill switch via `AI_PILOT_KILL_SWITCH=1` or `--kill-switch-file <path>`.

### Mock Pilot Demonstration Results (`MOCK_ADAPTER_SIMULATION_ONLY` — Zero Live LLM Calls)
Executed on isolated QA MySQL (`petcare_ai3_qa_test`, `16` scenarios / `18` requests across all `14` required categories):

- **Deterministic Safety & Fallback Track (`PL-10`..`PL-16`)**:
  - Turns passed: **`7 / 7` (`100.0%`)**
  - Veterinary false negatives: **`0`** (`3 / 3` positive clinical/incident cases intercepted pre-LLM with `0` shopping cards)
  - Tenant / RBAC violations: **`0`** (`tenant_id=9999` rejected by schema validator; `shopper_preview` sales & `staff` 8-week forecast denied)
  - Upstream HTTP `504` timeout fallback (`PL-16`): **`fallback_used=True`**, automatic grounded Python tofu-litter fallback (`<= 250,000 VND`)
- **Simulated LLM Tool-Orchestration Track (`PL-01`..`PL-09`, Mock Adapter)**:
  - Turns evaluated: **`11`** (`26` mock model steps) — **Note**: measures orchestration plumbing under deterministic mock steps, **not** live neural NLU accuracy
  - Task success rate: **`11 / 11` (`100.0%`)**
  - Tool selection accuracy: **`100.0%`** | Tool argument validity: **`100.0%`**
  - Grounded factual correctness: **`100.0%`** | Hallucinated prices or SKUs: **`0`**
  - Simulated token accounting: `34,647` prompt tokens + `1,080` completion tokens (`35,727` total)
  - Outbound privacy audit: `27` adapter requests (`91` messages) inspected -> **`0` violations**

### Estimated Live Pilot Cost & Model Lifecycle Update (`AI-3.1`)
> **Model Update (`AI-3.1`)**: OpenAI issued formal deprecation notices (`2026-10-14`, shutdown `2027-01-14`) for `gpt-4o-mini` and `gpt-4.1-mini`. **`gpt-6-luna`** (`$0.10` input / `$0.50` output per 1M tokens, `$0.01` cached input, with `AI_REASONING_EFFORT="none"` and `max_completion_tokens` on `/v1/chat/completions`) is now the primary supported pilot candidate. See `docs/PETCARE_AI_3_1_RELEASE_AND_PILOT_PLAN.md` for full compatibility details.

Assumptions based on measured multi-round tool-calling payload sizes (`~3,150` prompt tokens + `~100–220` completion tokens per multi-step LLM turn, `1–2` rounds/turn, `max_completion_tokens=700`):

| Candidate Model | Lifecycle Status | Input / 1M (USD) | Output / 1M (USD) | Est. 19-Turn Pilot | Est. 100 Turns |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`gpt-6-luna` (`reasoning_effort="none"`)** | **Active (Recommended)** | **`$0.10`** (`$0.01` cached) | **`$0.50`** | **`~$0.005`** | **`~$0.038`** |
| `gpt-4o-mini` | Deprecated (`2027-01-14`) | `$0.15` | `$0.60` | `~$0.007` | `~$0.056` |
| `gpt-4.1-mini` | Deprecated (`2027-01-14`) | `$0.80` | `$3.20` | `~$0.036` | `~$0.298` |

Recommended initial pilot cap: `--max-requests 20 --max-cost-usd 0.10` on `gpt-6-luna` (always paired with a hard provider-side OpenAI project/key budget cap).

---

## 6. Live Pilot Approval Checklist & Exact Execution Runbook

Before running `--mode live`, obtain explicit owner sign-off on:
1. **Provider & Model**: Approved HTTPS OpenAI endpoint (`https://api.openai.com/v1`) + `gpt-6-luna` (`AI_REASONING_EFFORT="none"`) with API zero-training / data-sharing disabled.
2. **Outbound Payload Scope**: Confirmation of the minimized synthetic QA catalog/KB/slot payload in Section 4 above.
3. **Hard Budget Cap**: Dedicated non-production API key with hard OpenAI project budget cap + application spend cap (`--max-cost-usd 0.10`, `--max-requests 20`).

For the updated `gpt-6-luna` step-by-step CLI commands and 16-scenario (`19`-turn) acceptance rubric, see **`docs/PETCARE_AI_3_1_RELEASE_AND_PILOT_PLAN.md` Sections 4–5**.

