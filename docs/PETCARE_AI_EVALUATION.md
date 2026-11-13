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

## 4. Independent OOD, Regression & Untouched Generalization Evaluations (`AI-2.1` → `AI-2.2`)

To prevent overfitting to internal unit/regression phrasing, PetCare AI separates development regression suites from untouched hold-out evaluation:

1. **Immutable 44-Case Independent OOD Benchmark** (`petcare/ai/independent_evaluation.py`, SHA-256 `0b3164c3080dd785b7e002616f7368fd789b5c12b170c5b8d94f72d417d541b3` — untouched labels & prompts):
   - **Before `AI-2.1`**: `16 / 44` cases (`36.36%`), `unsafe_vet_advice = 0 / 4`, `complex_multi_intent = 0 / 4`.
   - **After `AI-2.1` & `AI-2.2`**: **`44 / 44` cases (`100.00%`)**, `49 / 49` turns (`100.00%`), `0.00%` hallucination, `0.00%` unauthorized exposure.
2. **Historical 34-Case AI-2.1 Regression Suite** (`petcare/ai/heldout_safety_evaluation.py`, SHA-256 `bf96282d651f63c2d11fb0c5cf2e4874389bc7c31d233101f811af6055a2a4ef` — preserved unchanged; treated as a regression benchmark in `AI-2.2` after its 6 `AI-2.1` misses informed engineering fixes):
   - **`AI-2.1` Baseline**: `28 / 34` (`82.35%`), vet recall `9 / 11` (`81.82%`), vet precision `9 / 9` (`100.00%`).
   - **`AI-2.2` Regression Verification**: **`34 / 34` (`100.00%`)**, vet recall **`11 / 11` (`100.00%`)**, vet precision **`11 / 11` (`100.00%`, `0` FP)**, tool authorization **`7 / 7` (`100.00%`)**, grounded consistency **`36 / 36` (`100.00%`)**.
3. **Untouched 40-Case AI-2.2 Final Safety & Generalization Hold-Out** (`petcare/ai/final_safety_generalization_eval.py`, `42` turns — executed strictly after code freeze with zero post-inspection tuning):
   - **Overall Task Success**: **`34 / 40` (`85.00%`, Wilson 95% CI `[70.93%, 92.94%]`)** | **Turn Success**: `36 / 42` (`85.71%`).
   - **Veterinary Escalation Precision**: **`11 / 11` (`100.00%`, Wilson 95% CI `[74.12%, 100.00%]`, `0 / 9` false positives across controls, negations, and resolved history)**.
   - **Veterinary Escalation Recall**: **`11 / 15` (`73.33%`, Wilson 95% CI `[48.05%, 89.10%]`, `4` documented false negatives: `FG-VET-POS-01`, `FG-VET-POS-02`, `FG-VET-POS-11`, `FG-VET-POS-12`)**.
   - **Grounding Correctness**: **`42 / 42` (`100.00%`)** | **Authorization Enforcement**: **`7 / 7` (`100.00%`)** | **Constraint Satisfaction**: **`63 / 63` (`100.00%`)**.

Full analysis, statistical intervals, and remaining non-clinical boundaries are documented in `docs/PETCARE_AI_2_2_RELEASE.md`.

---

## 5. Visual & Browser Verification Artifacts

Real headless Chromium E2E tests (`scripts/browser_smoke/test_petcare_ai_e2e.py`, `6/6` PASS inside `25/25` `run_smoke.py`) verify multi-turn pet discovery, multi-turn slot-removal and simultaneous budget replacement corrections, bounded multi-intent replies, descriptive English veterinary triage (including head-pressing + scleral icterus), undocumented nutrient/taurine disclosures, product checkbox comparison, `Shopper Preview (QA)` scope locking, `staff` vs `admin` operational permission boundaries, keyboard (`Enter`/`Escape`) interaction, floating widget parity, `0px` horizontal overflow across `320px–1440px`, and `0` serious/critical `axe-core` WCAG 2.1 A/AA violations:
- Desktop Vietnamese Multi-Turn Pet Discovery: `docs/assets/petcare-ai/petcare-ai-workspace-desktop.png`
- Desktop English Side-by-Side Product Comparison: `docs/assets/petcare-ai/petcare-ai-comparison-desktop.png`
- Mobile `390x844` Responsive Workspace: `docs/assets/petcare-ai/petcare-ai-mobile-390.png`
- Desktop Descriptive English Veterinary Triage (`AI-2.1`): `docs/assets/petcare-ai/petcare-ai-2-1-vet-triage-desktop.png`
- Mobile `390x844` Veterinary Triage (`AI-2.1`): `docs/assets/petcare-ai/petcare-ai-2-1-vet-triage-mobile-390.png`
- Desktop Vietnamese Multi-Intent Citations + Recommendations (`AI-2.1`): `docs/assets/petcare-ai/petcare-ai-2-1-multi-intent-desktop.png`
- Desktop Head-Pressing Triage & Missing-Nutrient Disclosure (`AI-2.2`): `docs/assets/petcare-ai/petcare-ai-2-2-safety-and-missing-data-desktop.png`
