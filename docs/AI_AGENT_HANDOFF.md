# PetCare AI — Agent Milestone Handoff (`AI-3.0` Release & `AI-3.1` `gpt-6-luna` Live Pilot Readiness)

## Current Git & Environment State
- **Branch**: `solo/khang-petcare`
- **Previous Remote Baseline**: `60336283750f6818f76d5d00cd3f7cc02140b929`
- **Released Commits (`solo/khang-petcare`)**:
  1. `AI-3.0` Foundation Commit (`f6c506ff0731640d6329e36e66e8e46ca0687a98`): 4-tier veterinary safety hardening, SSRF/config preflight validation, legacy egress gate, and controlled pilot harness.
  2. `AI-3.1` Compatibility & Pilot Plan Commit (`HEAD` / `origin/solo/khang-petcare`): `gpt-6-luna` `/v1/chat/completions` function-calling compatibility (`reasoning_effort="none"`, `max_completion_tokens`, provider-reported usage & cached-token accounting), legacy 4-series deprecation warnings (`2027-01-14`), honest standby vs confirmed-live header badges, structural `dry_run`/`mock` socket blocks, and the `16`-scenario (`19`-turn) live pilot runbook in `docs/PETCARE_AI_3_1_RELEASE_AND_PILOT_PLAN.md`.
- **Preserved Untracked Local Tooling**: `.agents/`, `docs/skills.md`, `skills-lock.json` (intentionally excluded from Git).
- **Disposable QA Cleanup**: `petcare-ai31-qa-mysql-1` (`127.0.0.1:33339`), temporary Docker image, and QA artifact directories removed; development MySQL `petcare-manager-mysql-1` (`127.0.0.1:3306`) untouched.

## Mandatory Safety & Evaluation Invariants
1. **External LLM Disabled by Default (`0` Live API Calls Executed)**:
   - `AI_PROVIDER_APPROVED = False` (`"0"`), `AI_TOOL_CALLING_ENABLED = False` (`"0"`), `AI_PILOT_KILL_SWITCH = False` (`"0"`), and `AI_VISION_ENABLED = False` (`"0"`) in `petcare/config.py`.
   - `/assistant/chat` header badge `#ai-engine-badge` never claims `"Real LLM Connected"` on standby; it transitions to `data-engine-state="real_llm_confirmed"` **only** after an actual turn response returns `engine_mode == "real_llm"` without fallback.
   - `PilotBudgetAndSafetyGuard` enforces application-side request/token/USD circuit breakers, accompanied by `BILLING_GUARD_DISCLAIMER` requiring a paired upstream OpenAI project/key budget cap.
2. **Selected Live-Pilot Model Candidate (`gpt-6-luna`)**:
   - `gpt-4o-mini` and `gpt-4.1-mini` received OpenAI deprecation notices (`2026-10-14`, shutdown `2027-01-14`).
   - `gpt-6-luna` (`$0.10` input / `$0.50` output per 1M tokens, `$0.01` cached input) is enforced with `reasoning_effort="none"` and `max_completion_tokens` when `tools` are sent to `POST /v1/chat/completions` (`petcare/ai/client.py`). Active reasoning (`low`..`max`) alongside tools requires migrating to `POST /v1/responses` (documented in `docs/PETCARE_AI_3_1_RELEASE_AND_PILOT_PLAN.md` Section 2.4).
3. **Immutable Benchmark Regression Checksums (Unrelabeled)**:
   - `petcare/ai/evaluation.py` (`84` cases): `beb3a4bbed06e2c34385281eb7b685ca54dd5ec1a494cc965ad84b45718a774f`
   - `petcare/ai/independent_evaluation.py` (`44` cases): `0b3164c3080dd785b7e002616f7368fd789b5c12b170c5b8d94f72d417d541b3`
   - `petcare/ai/heldout_safety_evaluation.py` (`34` cases): `bf96282d651f63c2d11fb0c5cf2e4874389bc7c31d233101f811af6055a2a4ef`
   - `petcare/ai/final_safety_generalization_eval.py` (`40` cases, `AI-2.2` Regression Suite): `ba182d224530be82031dbc4e2db237d7ee881fe8a15d1023170fc8e24fd3362c`

## Verified Quality Gates (`AI-3.0 + AI-3.1` on Isolated QA MySQL)
- **Python / MySQL**: **`497 / 497` PASS** (`52.98s`, `0` skipped)
- **JavaScript**: **`47 / 47` PASS** (`155.4ms`)
- **Playwright Browser Smoke & E2E**: **`26 / 26` PASS** (`86.66s`, desktop + `390x844` mobile + axe-core WCAG 2.1 AA)
- **Offline Regression Evaluations**:
  - Core Benchmark: **`84 / 84` (`100.0%`)**
  - Original Independent OOD: **`44 / 44` (`100.0%`)**
  - AI-2.1 Held-Out Regression: **`34 / 34` (`100.0%`, `11 / 11` vet recall, `0` FP)**
  - AI-2.2 Regression (`final_safety_generalization_eval.py`, untouched): **`39 / 40` (`97.5%`)**, **veterinary recall `15 / 15` (`100.0%`, `0` FN, `0` FP)** (`FG-MUL-01` untouched label typo `KB-NUT-001` vs `KB-NUTR-001`).
- **Controlled Pilot Harness (`scripts/run_petcare_ai_pilot.py` with `gpt-6-luna`)**:
  - `--mode dry-run`: PASS (`0` network calls, `gpt-6-luna` preflight & cost projection verified)
  - `--mode mock`: **`16 / 16` scenarios PASS (`19` turns, `28` mock model rounds, `failed_cases_detail = []`, `0` live network calls, `0` privacy violations, `0` vet FNs, `0` tenant/RBAC violations)**
- **Security & Build Gates**: Bandit `1.9.4` (clean), `pip-audit` (`requirements.lock` + `requirements-browser.lock`: `0` CVEs), `npm audit --prefix tests/a11y` (`0` CVEs), `pip check`, `compileall`, `docker build`, `docker compose config --quiet`, and `git diff --check`.

## Next Milestone Action (First Approved Live LLM Pilot on `gpt-6-luna`)
After explicit owner sign-off on provider/model, outbound payload scope, and hard OpenAI project budget cap, run the exact commands in **`docs/PETCARE_AI_3_1_RELEASE_AND_PILOT_PLAN.md` Section 5** (`--mode live --confirm-live-pilot --model gpt-6-luna --max-requests 20 --max-cost-usd 0.10 --kill-switch-file /tmp/PETCARE_STOP_PILOT` against an isolated `*_test` QA database only).
