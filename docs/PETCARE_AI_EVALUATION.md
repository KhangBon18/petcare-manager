# PetCare AI — Evaluation Benchmark & Quality Report

## 1. Benchmark Methodology

`petcare/ai/evaluation.py` and `scripts/evaluate_petcare_ai.py` implement a deterministic, reproducible evaluation harness against an isolated `_test` MySQL schema seeded with realistic multi-tenant retail data plus targeted edge-case fixtures (undocumented pet attributes, zero-stock SKUs, and a rival tenant `eval-other-tenant` to test cross-tenant exfiltration).

### Reproduction Command (Isolated QA MySQL)

```bash
PETCARE_TEST_DB_NAME=petcare_ai_qa_test \
DB_NAME=petcare_ai_qa_test \
.venv/bin/python scripts/evaluate_petcare_ai.py --json-out /tmp/petcare_ai_eval_report.json
```

---

## 2. Dataset Composition (84 Cases · 95 Conversational Turns)

| Category | Cases | Bilingual (`vi` / `en`) | What Is Evaluated |
|---|---:|---|---|
| Multi-turn Pet Matching & Context Updates | 10 | Both | Guided clarification → slot merge → budget/species refinement → reset (`MT-PET-01`..`10`) |
| Single-turn Pet Matching & Unknown Traits | 8 | Both | Hard constraints (`available`, `<= budget_max`), zero breed stereotyping, unknown weight/age warnings |
| Multi-turn Product Recommendations & Allergies | 8 | Both | Life stage, `5 kg` weight filter, session chicken allergy exclusion, category carry-over |
| Single-turn Product Recommendations & OOS/No-Match | 12 | Both | `Decimal` unit prices (`VND/kg`, `VND/100g`, `VND/tờ`), OOS disclosure, dog-toy honest no-match + alternatives |
| Side-by-Side Product Comparison | 8 | Both | Explicit SKU codes, contextual *"Compare these three products"*, invalid SKU clarification |
| Trusted Knowledge Base & Exotic Species Refusal | 12 | Both | Okapi BM25 hit accuracy (`KB-NUTR-001`..`KB-OWN-008`), citations, iguana/parrot/hamster honest refusal |
| Veterinary Emergency & Medical Dosage Guardrails | 10 | Both | Lily/xylitol/chocolate/respiratory/urinary emergency escalation; antibiotic/`mg/kg` dosage refusal |
| Security, Injection, Write Refusal, RBAC & Cross-Tenant | 16 | Both | SQLi, prompt injection, auto-invoice/refund refusal, `staff` vs `admin` RBAC, `shopper_preview` isolation, rival tenant probe |
| **Total** | **84** | **42 VI / 42 EN** | **95 total turns executed end-to-end against MySQL** |

---

## 3. Measured Benchmark Results (`petcare_ai_qa_test`)

| Metric | Measured Score | Target | Result |
|---|---:|---:|---|
| **Case Pass Rate** (`84 / 84` cases) | **100.00%** (`1.0000`) | $\ge 95\%$ | PASS |
| **Turn Intent & Task Success Rate** (`95 / 95` turns) | **100.00%** (`1.0000`) | $\ge 95\%$ | PASS |
| **Preference Slot Extraction Accuracy** | **100.00%** (`1.0000`) | $\ge 95\%$ | PASS |
| **Multi-Turn Context Retention Rate** | **100.00%** (`1.0000`) | $100\%$ | PASS |
| **Recommendation Precision@K (Verified Catalog)** | **100.00%** (`1.0000`) | $\ge 95\%$ | PASS |
| **Hard Constraint Satisfaction Rate (Species / Status / Budget / Allergy)** | **100.00%** (`1.0000`) | $100\%$ | PASS |
| **Knowledge Base Retrieval Hit Rate (Expected `doc_id` @ Top-2)** | **100.00%** (`1.0000`) | $\ge 90\%$ | PASS |
| **Grounded Factual Correctness Rate (Exact MySQL ID + Price Match)** | **100.00%** (`1.0000`) | $100\%$ | PASS |
| **Hallucinated Item or Price Rate** | **0.00%** (`0.0000`) | $0\%$ | PASS |
| **Unauthorized Cross-Tenant / Role / Scope Exposure Rate** | **0.00%** (`0.0000`) | $0\%$ | PASS |
| **Veterinary Emergency & Medical Boundary Escalation Accuracy** | **100.00%** (`1.0000`) | $100\%$ | PASS |

### End-to-End Turn Latency (Mode A Offline Python + MySQL 8.4)
- **Mean**: `10.56 ms`
- **Median (`p50`)**: `10.61 ms`
- **95th Percentile (`p95`)**: `23.88 ms`
- **Max**: `35.99 ms`

---

## 4. Visual & Browser Verification Artifacts

Real headless Chromium E2E tests (`scripts/browser_smoke/test_petcare_ai_e2e.py`) verify multi-turn pet discovery, English product checkbox comparison, `Shopper Preview (QA)` scope locking, citation/emergency banners, `0px` horizontal overflow across `320px–1440px`, and `0` serious/critical `axe-core` WCAG 2.1 A/AA violations:
- Desktop Vietnamese Multi-Turn Pet Discovery: `docs/assets/petcare-ai/petcare-ai-workspace-desktop.png`
- Desktop English Side-by-Side Product Comparison: `docs/assets/petcare-ai/petcare-ai-comparison-desktop.png`
- Mobile `390x844` Responsive Workspace: `docs/assets/petcare-ai/petcare-ai-mobile-390.png`
