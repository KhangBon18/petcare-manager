# PetCare AI — External LLM Provider Readiness (`Mode A` vs `Mode B`)

## 1. Dual-Mode Engine Architecture (`petcare/ai/provider.py`)

PetCare AI separates **business logic, retrieval, ranking, and authorization** from **natural-language phrasing**:

| Engine Mode | Enum Value | Default State | Network Egress | How It Works |
|---|---|---|---|---|
| **Mode A — Offline Deterministic Python Engine** | `offline` | **ACTIVE DEFAULT** | **Zero external calls** | Python NLU, `PreferenceSlots`, two-stage pet matching, `Decimal` unit-price product ranking, Okapi BM25 retrieval, and bilingual templates generate 100% of responses locally in ~`10ms`. |
| **Mode B1 — Approved LLM Prose Synthesis** | `real_llm` (`tool_calling_enabled=false`) | **DISABLED BY DEFAULT** | HTTPS to configured OpenAI-compatible `/chat/completions` | Python executes NLU, RBAC, MySQL tool calls, scoring, and citations first, then passes `VERIFIED_GROUNDED_FACTS_JSON` to polish phrasing. |
| **Mode B2 — Approved LLM Tool-Calling (`AI-2`)** | `real_llm` (`tool_calling_enabled=true`) | **DISABLED BY DEFAULT** | HTTPS with bounded OpenAI `tools` (`<= 3` rounds, `<= 4` calls) | LLM interprets open-ended queries and proposes allowlisted read-only tools; Python validates JSON schemas, enforces RBAC/scope/tenant isolation, records a `TurnGroundingLedger`, and runs `verify_llm_answer_consistency()` before returning. See `docs/PETCARE_AI_2_TOOL_CALLING_AND_PILOT.md`. |

---

## 2. Explicit Approval Gate (`AI_PROVIDER_APPROVED`)

Even if `AI_API_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` are present in the environment, **Mode B will NOT activate unless `AI_PROVIDER_APPROVED=1` is explicitly set**:

```bash
# Default safe posture (zero paid API calls):
AI_PROVIDER_APPROVED=0

# Explicit opt-in for approved pilot / staging validation:
AI_PROVIDER_APPROVED=1
AI_API_BASE_URL=https://api.openai.com/v1
AI_API_KEY=<secret-stored-in-vault-never-committed>
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=8
```

Loopback Vision test mocks (`AI_MODEL=petcare-local-demo-mock` with `AI_TEST_ALLOW_LOOPBACK_PROVIDER=1`) are automatically recognized and excluded from `Mode B` chat calls.

---

## 3. Security, Privacy & Reliability Safeguards for Mode B

1. **Strict Data Minimization**:
   - Customer PII (`customers` table, phone numbers, addresses, invoice buyer info), cross-tenant rows, and unapproved internal tables are **never** serialized into `VERIFIED_GROUNDED_FACTS_JSON`.
   - User prompts are truncated (`<= 800` chars) and session history is redacted by `redact_sensitive_text()`.
2. **Untrusted Data Framing**:
   - Grounded facts are passed in a dedicated reference message with explicit system instructions forbidding invented SKUs, prices, stock counts, breed temperaments, nutrition percentages, or veterinary dosages.
   - Structured UI elements (`cards`, `comparison`, `citations`, `safety_notice`, `url_for()` links) are **always** attached directly from Python's verified tool output—never parsed from free-form LLM text.
3. **SSRF, Timeout & Automatic Fallback**:
   - `petcare/ai/client.py` enforces HTTPS, DNS/IP private-network SSRF blocking, bounded response byte limits, and `AI_TIMEOUT_SECONDS`.
   - If the external provider times out, rate-limits (`429`), or returns `5xx`, `synthesize_approved_llm_reply()` catches `AIProviderError` and seamlessly returns Mode A's verified deterministic reply with an honest fallback notice.

---

## 4. Pre-Activation Blockers & Isolated Pilot Prerequisites (`AI-2.2` Status)

External LLM providers (`AI_PROVIDER_APPROVED=0`, `AI_TOOL_CALLING_ENABLED=0`) have **NOT** been tested against a live API and are **NOT** ready for production or unsupervised shopper traffic.

### Mandatory Blockers Before Any Real-LLM Activation
1. **Explicit Owner Authorization, DPA & Hard Spend Caps**: Zero-training-retention vendor DPA plus hard billing/token caps on a dedicated sandbox API key stored outside Git.
2. **Real-Provider Benchmark Validation**: Zero live API calls have been executed to date; `evaluate_petcare_ai.py` (`84` cases), `evaluate_petcare_ai_independent.py` (`44` cases), `evaluate_petcare_ai_heldout.py` (`34` cases), and `evaluate_petcare_ai_final_holdout.py` (`40` cases) must be run end-to-end against the real model on a disposable `_test` database with `hallucinated_item_or_price_rate == 0.0`, `unauthorized_exposure_rate == 0.0`, and `p95 < 3000 ms`.
3. **Licensed Veterinary Clinical Review & Semantic Safety Classifier**: Deterministic regex triage (`petcare/ai/safety_triage.py`) achieved `100.0%` precision (`0` FP) across all suites and `100.0%` recall on known regression cases (`34/34`), but `73.33%` recall (`11/15`, Wilson 95% CI `[48.05%, 89.10%]`) on the untouched `AI-2.2` generalization hold-out (`4` misses on long-span colloquial urinary straining, inverted open-mouth breathing syntax, accidental double insulin dosing, and post-spay incision dehiscence). Licensed veterinarian review and semantic pre-routing safety classification are required before public shopper deployment.
4. **Distributed Session Memory & Multi-Worker Rate Limiting**: Replace process-local `MEMORY_STORE` with shared Redis/MySQL session backing before multi-worker Gunicorn scaling.

### Pilot Gate Decision (`AI-2.2`)
- **Production / Live Shopper Deployment**: **NO-GO**.
- **Isolated Offline-Seeded QA Pilot (`_test` DB only, internal staff/QA only, budget-capped key)**: **CONDITIONAL GO** once Blockers 1 and 2 are authorized by the project owner (see `docs/PETCARE_AI_2_2_RELEASE.md`).
