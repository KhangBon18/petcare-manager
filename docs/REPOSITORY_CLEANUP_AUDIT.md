# Repository Cleanup & Release Audit (`REPOSITORY_CLEANUP_AUDIT.md`)

- **Audit Branch Baseline**: `solo/khang-petcare` @ `b95ddd8d48056385367b8d03eb5d4aa95a9a353a`
- **Cleanup Working Branch**: `feature/final-repository-release`
- **Verified Predecessor PRs**: PR `#3` (`AI-4.0`), PR `#4` (`Option A UI/UX`), PR `#5` (`Customer Storefront`), PR `#6` (`Demo & Staging Readiness`) — all merged into `solo/khang-petcare` with post-merge CI `44489894657` passing **6/6** jobs.
- **Policy**: **No untracked/ignored/local file was deleted automatically during this audit.** All destructive removals or external backups await explicit user approval.

---

## 1. Git Topology, Branches, Stashes, Worktrees & Tags Inventory

| Ref / Artifact | Commit / Location | Status vs `solo/khang-petcare` (`b95ddd8`) | Notes |
|---|---|---|---|
| `solo/khang-petcare` (`origin/solo/khang-petcare`) | `b95ddd8` | Current integrated baseline (`0` ahead) | Contains PR #3, #4, #5, #6 |
| `origin/main` (default public branch) | `5f43633` | **1 commit ahead, 59 behind** (merge-base `8c7c176`) | Commit `5f43633` ("Sửa", Oct 16 2026) adds legacy SQL dump `data/quan_ly_thu_cung.sql` (`+149/-1`). Zero conflict with `b95ddd8` (which archived SQL under `docs/archive/desktop_data/quan_ly_thu_cung.sql`). |
| `local main` & `fix/qc-baseline` | `8c7c176` | `0` ahead (`v1.0.0` baseline ancestor) | Fully merged into `solo/khang-petcare` |
| `feature/full-implementation` | `0fdfd8b` | `0` ahead | Fully merged ancestor |
| `feature/ai-4.0-pet-image-matching` | `b372b22` | `0` ahead | Merged in PR #3 |
| `feature/petcare-ui-ux-redesign` | `148a9a1` | `0` ahead | Merged in PR #4 |
| `feature/customer-storefront-mvp` | `7440a47` | `0` ahead | Merged in PR #5 |
| `feature/demo-staging-readiness` | `60dbb01` | `0` ahead | Merged in PR #6 |
| `origin/copilot/fix-browser-smoke-job` (PR #2 open) | `927b8c3` | CI Playwright apt retry fix | Equivalent retry loop is already integrated in `.github/workflows/ci.yml` |
| `origin/copilot/fix-verifying-github-actions-job` (PR #1 open) | `aaee86d` | Draft/abandoned investigation commit (`Initial plan`) | Obsolete; CI `verify` passes 3/3 (`3.11`, `3.12`, `3.13`) |
| `git stash list` | Empty (`0` stashes) | Clean | — |
| `git worktree list` | Single primary checkout | Clean | — |
| Historical Tags | `v1.0.0` (`8c7c176`), `v1.0-demo-ready` (`7514b47` ancestor chain) | Preserved intact | Do not overwrite or delete |
| Historical Academic ZIPs (parent dir) | `../petcare-manager.zip` (`145,769,315` bytes), `../petcare-manager-final-submission.zip` (`48,253,328` bytes) | Outside repo, preserved intact | Never overwrite |

---

## 2. Complete Classification of Local / Untracked / Ignored Files

Classification codes:
- **A**: Required project source
- **B**: Required configuration/template
- **C**: Useful documentation
- **D**: Required AI model or asset
- **E**: Valid test fixture
- **F**: Temporary / generated artifact
- **G**: Local-only tooling / personal user file
- **H**: Sensitive / private file
- **I**: Unknown (requires review)

| Exact Path | Class | Tracked by Git? | Used by Runtime App? | Recommendation | Intended Destination | Proposed Action (Pending Approval) |
|---|---|---|---|---|---|---|
| `.env` (`399 B`) | **H** | No (`.gitignore`) | Yes (local dev config only) | Keep private on developer host; **never** commit or archive | Local developer machine only | Retain locally; excluded by `.gitignore` & release packaging |
| `data/petcare.db` (`112 KB`) | **F / G** | No (`.gitignore`) | No (runtime uses MySQL 8.4) | Legacy early SQLite file from Oct 16 | Outside repo backup or keep ignored locally | Retain locally or back up outside repo after approval |
| `instance/pet-images/` (`~3,956` `t1-*`/`t5-*` files, `~149 MB`) | **F** | No (`.gitignore`) | No (artifacts from prior unit/smoke runs before `$TMPDIR` isolation) | Clean disposable test uploads after backing up if desired | Delete disposable `t*-*` cache after approval | Remove disposable test files after explicit approval |
| `instance/product-images/` (`1` file, `300 B`) | **F** | No (`.gitignore`) | No (smoke test file from Oct 17) | Disposable test image | Clean after approval | Remove disposable test artifact after approval |
| `instance/tenant-exports/` | **F** | No (`.gitignore`) | No (test export artifacts) | Disposable local test output | Clean after approval | Empty temp export directory after approval |
| `.playwright-cli/` (`908 KB`) | **F** | No (`.gitignore`) | No | Nov 2–3 debug YAML/PNG captures | Remove or keep outside repo | Remove disposable debug captures after approval |
| `.playwright/` (`0 B`, empty dir) | **F** | No | No | Empty stale tool directory | Safe to ignore/remove | Add `.playwright/` to `.gitignore`; remove empty dir after approval |
| `.pytest_cache/` | **F** | No | No | Pytest local cache | Ignore in `.gitignore` | Add `.pytest_cache/` to `.gitignore`; prune safely |
| `.venv/` (`465 MB`) | **G** | No (`.gitignore`) | Local Python venv only | Keep for local dev/tests; excluded from release | Developer host only | Retain `.venv/` locally |
| `tests/a11y/node_modules/` (`3.3 MB`) | **G** | No (`.gitignore`) | Playwright axe QA runner only | Keep for local Playwright QA; excluded from ZIP | Developer host (`npm ci` reproducible) | Retain locally; excluded from release ZIP |
| `.agents/` (`25 MB`) | **G** | No | No (agent skills guidance: `frontend-design`, `web-design-guidelines`, `playwright-cli`, `ui-ux-pro-max`, `book-to-skill`) | Preserve local developer AI skills outside Git tracking | Local dev only (add `.agents/` to `.gitignore`) | Keep on disk; ignore via `.gitignore` |
| `docs/skills.md` (`2.0 KB`) & `skills-lock.json` (`1.4 KB`) | **G** | No | No (documents/hashes local `.agents/skills/`) | Retain locally alongside `.agents/`, or ignore `skills-lock.json` | Local dev tooling | Keep on disk; ignore `skills-lock.json` & `docs/skills.md` (or move with `.agents/` outside repo) |
| `ChatGPT Image Nov 17, 2026, 02_48_51 PM.png` (`1.8 MB`) | **G** | No | **No** (unrelated `"Bếp Xuyên Việt OCOP — Xốt ướp thịt"` mascot graphic created Nov 17) | **Back up outside repo before removing from repo root** | `~/Documents/petcare-local-backup/` (or user choice) | Request explicit approval to move outside repo & add pattern/exclude from repo |
| `design-system/petcare-manager/pages/` (`0 B`, empty dir) | **F** | No | No | Empty leftover dir next to `MASTER.md` | Prune empty dir after approval | Remove empty directory after approval |
| `docs/assets/.DS_Store` | **F** | No (`.gitignore`) | No | macOS Finder metadata | Clean on macOS | Remove `.DS_Store` files after approval |
| `**/__pycache__/` & `*.pyc` (inside repo scripts) | **F** | Partially ignored (`__pycache__/`) | No | Python bytecode caches | Keep ignored; clean before manual inspections | Ignored by `.gitignore` & excluded by `git archive` |
| Tracked docs containing local `/Users/` strings | **C** | **Yes** | No | Replace local `file:///Users/...` URLs with portable relative paths in active docs | Same Markdown files in repo | Cleaned in Phase 4 on `feature/final-repository-release` |

---

## 3. Git Clean Dry-Run Summary (`git clean -nd`)

Running non-destructive `git clean -nd` confirmed only the untracked developer tooling (`.agents/`, `docs/skills.md`, `skills-lock.json`), empty leftover directories (`.playwright/`, `design-system/petcare-manager/pages/`), and personal image (`ChatGPT Image Nov 17, 2026, 02_48_51 PM.png`) sit outside `.gitignore`.

**Pending Explicit User Approval (Phase 13):**
1. Back up `ChatGPT Image Nov 17, 2026, 02_48_51 PM.png` and `data/petcare.db` outside the Git repo before removing them from the working tree.
2. Delete disposable local caches: `instance/pet-images/t*-*`, `instance/product-images/*`, `instance/tenant-exports/*`, `.playwright-cli/`, `.playwright/`, `.pytest_cache/`, `design-system/petcare-manager/pages/`, `.DS_Store`.
3. Retain `.env`, `.venv/`, `tests/a11y/node_modules/`, `.agents/`, `docs/skills.md`, and `skills-lock.json` locally on disk (kept out of Git & release archives).
