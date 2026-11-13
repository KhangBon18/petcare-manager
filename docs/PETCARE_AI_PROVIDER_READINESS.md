# PetCare AI — External LLM Provider Readiness (`Mode A` vs `Mode B`)

## 1. Dual-Mode Engine Architecture (`petcare/ai/provider.py`)

PetCare AI separates **business logic, retrieval, ranking, and authorization** from **natural-language phrasing**:

| Engine Mode | Enum Value | Default State | Network Egress | How It Works |
|---|---|---|---|---|
| **Mode A — Offline Deterministic Python Engine** | `offline` | **ACTIVE DEFAULT** | **Zero external calls** | Python NLU, `PreferenceSlots`, two-stage pet matching, `Decimal` unit-price product ranking, Okapi BM25 retrieval, and bilingual templates generate 100% of responses locally in ~`10ms`. |
| **Mode B — Approved Real LLM Synthesis** | `real_llm` | **DISABLED BY DEFAULT** | HTTPS to configured OpenAI-compatible `/chat/completions` | Python still executes **all** NLU, RBAC, MySQL tool calls, scoring, and citations first, then passes a strictly bounded `VERIFIED_GROUNDED_FACTS_JSON` payload to the LLM solely to polish prose phrasing. |

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

## 4. Pre-Activation Pilot Checklist

Before setting `AI_PROVIDER_APPROVED=1` in any shared environment:
1. Confirm vendor data-processing terms (zero training retention on store data) and configure hard monthly spend caps on the API key.
2. Verify `ASSISTANT_RATE_LIMIT_PER_MINUTE` and `ASSISTANT_IP_RATE_LIMIT_PER_MINUTE` are active in production config.
3. Re-run `scripts/evaluate_petcare_ai.py` with `AI_PROVIDER_APPROVED=1` on an isolated `_test` database and confirm `hallucinated_item_or_price_rate == 0.0` and `p95` latency remains within SLA (`< 3000 ms`).
