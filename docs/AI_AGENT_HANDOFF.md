# PetCare AI — Agent Milestone Handoff (`AI-2.2` Safety Closure & Offline Release)

## Current Git & Environment State
- **Branch**: `solo/khang-petcare` (synchronized with `origin/solo/khang-petcare`, `0` ahead / `0` behind after final docs push).
- **Release Commit Chain (`AI-2` / `AI-2.1` / `AI-2.2`)**:
  1. `666d500d2219195654494be7b40121520cfca551` — `fix(ai): improve veterinary triage and NLU`
  2. `a38657e31b7bad5441d3c47dc6967ed64bc531b9` — `feat(ai): add safe offline tool-calling foundation`
  3. `22de3bcdc3a72f817f1f5ead02994849faff0f3f` — `test(ai): expand independent evaluation and E2E`
  4. Final `docs(ai): record AI-2 design and evidence` commit at `HEAD`.
- **Durable Pre-`AI-2.2` Checkpoint**: `/Users/heisenbon/Documents/Workspace Code/NNLTPython/petcare-manager-release-checkpoints/petcare-ai-2-pre-2_2-20261113/` (`SHA256SUMS` verified).
- **Preserved Untracked Local Tooling**: `.agents/`, `docs/skills.md`, `skills-lock.json` (intentionally excluded from Git).
- **Disposable QA Cleanup**: `petcare-ai22-qa-mysql-1` (`127.0.0.1:33329`) and `/tmp/petcare-ai22-pw` removed; development MySQL `petcare-manager-mysql-1` (`127.0.0.1:3306`) untouched.

## Mandatory Safety & Evaluation Invariants
1. **External LLM Disabled by Default**: `AI_PROVIDER_APPROVED = False` and `AI_TOOL_CALLING_ENABLED = False` in `petcare/config.py`. Never call paid external AI endpoints without explicit user approval.
2. **Immutable Regression Checksums**:
   - `petcare/ai/independent_evaluation.py` (`44` cases): `0b3164c3080dd785b7e002616f7368fd789b5c12b170c5b8d94f72d417d541b3`
   - `petcare/ai/heldout_safety_evaluation.py` (`34` cases): `bf96282d651f63c2d11fb0c5cf2e4874389bc7c31d233101f811af6055a2a4ef`
3. **Hold-Out Hygiene**: `petcare/ai/final_safety_generalization_eval.py` (`40` cases) was inspected in `AI-2.2` (`34 / 40 = 85.0%`, vet recall `11 / 15 = 73.33%`, vet precision `11 / 11 = 100.0%`). If future commits address its 4 disclosed safety misses (`FG-VET-POS-01`, `02`, `11`, `12`), reclassify `final_safety_generalization_eval.py` as a regression suite and author a fresh untouched `v2` hold-out.

## Verified Quality Gates (`AI-2.2`)
- **Python / MySQL**: **`487 / 487` PASS** (`39.08s`) | **JavaScript**: **`46 / 46` PASS** | **Playwright Smoke**: **`25 / 25` PASS** (`89.32s`).
- **Offline Evaluations**: Core `84 / 84` (`100.0%`), Original OOD `44 / 44` (`100.0%`), Historical AI-2.1 Regression `34 / 34` (`100.0%`, `11 / 11` recall, `0` FP), Untouched AI-2.2 Final Hold-Out `34 / 40` (`85.0%`, `11 / 15` recall, `11 / 11` precision, `100.0%` grounding/auth/constraints).
- **Security & Container Gates**: Bandit `1.9.4`, `pip-audit` (both lockfiles), `npm audit`, `pip check`, `compileall`, `docker build`, `docker compose config`, `git diff --check`, and Hosted GitHub Actions CI (`3.11`, `3.12`, `3.13`, `browser-smoke`, `source-security`, `container`).

## Next Milestone Prerequisites (`AI-2.3` Controlled Sandbox Pilot)
See `docs/PETCARE_AI_2_2_RELEASE.md` Section 7: requires explicit owner approval, budget-capped sandbox API key, closure of the 4 disclosed hold-out safety patterns (`FG-VET-POS-01`, `02`, `11`, `12`) + semantic triage classifier, and full 202-case live-adapter validation on an isolated `_test` database before any real-LLM enablement.
