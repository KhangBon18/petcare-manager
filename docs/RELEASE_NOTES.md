# Release Notes — PetCare Manager `v2.0.0` (Proposed)

- **Proposed Semantic Version**: `v2.0.0` (Major generation upgrade over historical `v1.0.0` & `v1.0-demo-ready`)
- **Integration Branch**: `main` (synchronized with `solo/khang-petcare`)
- **Preserved Historical Tags**: `v1.0.0`, `v1.0-demo-ready`

---

## What Changed Since `v1.0.0` / `v1.0-demo-ready`

### 1. Local AI Vision 4.0 (PR #3)
- Integrated offline ONNX object detection (`yolox_nano.onnx`), crop species verification (`mobilenetv2-12.onnx`), and `1280`-D foreground embedding extraction (`mobilenetv2-12-features.onnx`) + white-balanced CIE-Lab reranking.
- Added multi-photo pet reference galleries (`pet_reference_photos`, up to 5 verified images/pet), LSH index maintenance (`pet_photo_lsh`), and honest identity-safe visual similarity UX.

### 2. Precision SaaS Light Option A UI/UX Redesign & Complete Media (PR #4)
- Unified administrative/staff workspace under Option A design tokens (`ui.css`, `tokens.css`), integrated account menu + locale selector, compact POS cards, and complete synthetic demo catalog imagery (`22` product thumbnails, `68` demo pet portraits, `10` SVG fallbacks).

### 3. Customer Storefront `/shop` & Order Queue (PR #5)
- Added full public Storefront (`storefront` blueprint, 4 MySQL tables in `storefront.sql`): catalog browsing, pet/product detail pages, session cart, pickup vs COD checkout, order lookup & account history, public Shopping AI Assistant (`/shop/ai-assistant`), and public Visual Pet Search (`/shop/image-search`).
- Added internal Online Orders queue (`orders` blueprint) with inventory/pet locking (`customer_order_pet_locks`) on confirmation and explicit cash/payment settlement before deducting stock or posting paid invoices.

### 4. Demo/Staging Readiness & UI/Module Acceptance Polish (PR #6)
- Added `scripts/demo_staging_setup.py` for fail-closed isolated `_test` demo provisioning across all 3 roles (Admin, Staff, Customer).
- Fixed mobile `/shop/account` card layout (`clippedRight: false` at `320px`/`390px`), docked `#assistant-launcher` into `.topbar` (eliminating all button overlaps), deduplicated internal AI safety banner text, expanded horizontal customer AI cards, compacted mobile Storefront hero, added conditional checkout delivery address toggling, and rendered uploaded query previews with `/100` heuristic score labels.
- Completed 60-check multi-viewport module acceptance (including `/activity/`) documented in [FINAL_UI_MODULE_ACCEPTANCE.md](FINAL_UI_MODULE_ACCEPTANCE.md).

### 5. Repository Reconciliation, Attribution & Licensing (PR #7 – PR #10 & Licensing)
- Completed repository audit, clean-clone verification (`SETUP_GUIDE.md`, `REPOSITORY_CLEANUP_AUDIT.md`), and safe Git history reconciliation with `origin/main` without reintroducing legacy desktop SQL fixtures (`docs/archive/README.md`).
- Added comprehensive third-party attribution ([THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)) covering GSAP Standard License, Apache-2.0 ONNX models, `mysql-connector-python` (GPLv2 + FOSS License Exception), and Wikimedia Commons `CC BY` evaluation fixtures, alongside the canonical first-party [MIT License](../LICENSE).

---

## Known Limitations
- **Visual Search != Biometric Identity**: Local ONNX similarity assists visual browsing and does not confirm two distinct photographs show the same physical animal (`same_pet_multi_view_reidentification = NOT EVALUATED`).
- **Offline COD / Counter Payment Only**: No online card/wallet payment gateway; orders stay `unpaid` until staff confirm collection.
- **Public Signup Disabled by Default**: `PUBLIC_SIGNUP_ENABLED=0` remains off pending commercial billing/quota controls.
- **External AI Providers Opt-In**: External LLM chat (`AI_PROVIDER_APPROVED=0`) and external image analysis (`AI_VISION_ENABLED=0`) are disabled by default; when enabled, short chat history is sent outbound per user consent notices.
