# PetCare AI — Agent Milestone Handoff (`AI-3` Controlled Real-LLM Pilot Readiness)

## Current Git & Environment State
- **Branch**: `solo/khang-petcare`
- **Verified Base HEAD / Upstream**: `60336283750f6818f76d5d00cd3f7cc02140b929` (`origin/solo/khang-petcare`, `0` ahead / `0` behind).
- **Working Tree Policy (`AI-3`)**: Per milestone instructions, **no automatic `git commit` or `git push`** was performed; all `AI-3` code, tests, and documentation remain cleanly in the working tree for human review.
- **Preserved Untracked Local Tooling**: `.agents/`, `docs/skills.md`, `skills-lock.json` (intentionally excluded from Git).
- **Disposable QA Cleanup**: `petcare-ai3-qa-mysql-1` (`127.0.0.1:33339`) and temporary QA artifact directories removed; development MySQL `petcare-manager-mysql-1` (`127.0.0.1:3306`) untouched.

## Mandatory Safety & Evaluation Invariants
1. **External LLM Disabled by Default**:
   - `AI_PROVIDER_APPROVED = False` (`"0"`) and `AI_TOOL_CALLING_ENABLED = False` (`"0"`) in `petcare/config.py`.
   - `AI_PILOT_KILL_SWITCH = False` (`"0"` default; setting `"1"` or `--kill-switch-file` immediately halts pilot execution and forces `EngineMode.OFFLINE`).
   - Legacy `petcare/services/assistant_service.py` fallback and `petcare/templates/base.html` header now also require `AI_PROVIDER_APPROVED=True` before invoking `ai_client.complete()` or showing `"AI tạo sinh đang bật"`.
2. **Immutable Benchmark Regression Checksums (Unrelabeled)**:
   - `petcare/ai/evaluation.py` (`84` cases): `beb3a4bbed06e2c34385281eb7b685ca54dd5ec1a494cc965ad84b45718a774f`
   - `petcare/ai/independent_evaluation.py` (`44` cases): `0b3164c3080dd785b7e002616f7368fd789b5c12b170c5b8d94f72d417d541b3`
   - `petcare/ai/heldout_safety_evaluation.py` (`34` cases): `bf96282d651f63c2d11fb0c5cf2e4874389bc7c31d233101f811af6055a2a4ef`
   - `petcare/ai/final_safety_generalization_eval.py` (`40` cases, now classified as `AI-2.2` Regression Suite): `ba182d224530be82031dbc4e2db237d7ee881fe8a15d1023170fc8e24fd3362c`
3. **Methodological Separation**: Always report deterministic Python / mock-adapter simulation metrics separately from genuine live-provider pilot metrics. Never claim clinical veterinary validation without licensed DVM review.

## Verified Quality Gates (`AI-3` on Isolated QA MySQL)
- **Python / MySQL**: **`496 / 496` PASS** (`45.91s`, `0` skipped)
- **JavaScript**: **`47 / 47` PASS** (`128.4ms`)
- **Playwright Browser Smoke & E2E**: **`26 / 26` PASS** (`75.46s`, desktop + `390x844` mobile + axe-core)
- **Offline Regression Evaluations**:
  - Core Benchmark: **`84 / 84` (`100.0%`)**
  - Original Independent OOD: **`44 / 44` (`100.0%`)**
  - AI-2.1 Held-Out Regression: **`34 / 34` (`100.0%`, `11 / 11` vet recall, `0` FP)**
  - AI-2.2 Regression (`final_safety_generalization_eval.py`, untouched): **`39 / 40` (`97.5%`)**, **veterinary recall `15 / 15` (`100.0%`, `0` FN, `0` FP)**; the sole `1 / 40` diff is `FG-MUL-01`'s untouched citation-ID typo (`KB-NUT-001` vs real `KB-NUTR-001`).
- **Controlled Pilot Harness (`scripts/run_petcare_ai_pilot.py`)**:
  - `--mode dry-run`: PASS (`0` network calls, config/SSRF/privacy/cost projection verified)
  - `--mode mock`: **`16 / 16` scenarios PASS (`18` requests, `0` live network calls, `0` privacy violations, `0` vet FNs, `0` tenant/RBAC violations)**
- **Security & Build Gates**: Bandit `1.9.4` (baseline clean), `pip-audit` (`requirements.lock` + `requirements-browser.lock`: `0` CVEs), `npm audit --prefix tests/a11y` (`0` CVEs), `pip check`, `compileall`, `docker build`, `docker compose config --quiet`, and `git diff --check`.

## Next Milestone Action (`AI-3.1` First Approved Live LLM Pilot)
Follow the exact approval checklist and CLI runbook in `docs/PETCARE_AI_3_PILOT_READINESS.md` Section 6 (`--mode live --confirm-live-pilot --max-requests 20 --max-cost-usd 0.10 --kill-switch-file /tmp/PETCARE_STOP_PILOT` against an isolated `*_test` QA database only).
