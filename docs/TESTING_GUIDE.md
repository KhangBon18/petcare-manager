# Testing Guide (`TESTING_GUIDE.md`)

All verification suites run without touching development or production schemas. Any test touching MySQL **must** target an isolated database ending in `_test` (`PETCARE_TEST_DB_NAME=<name>_test`).

---

## 1. Prerequisites

```sh
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt -c requirements.lock
python -m pip install -r requirements-browser.lock
python -m playwright install chromium
npm ci --prefix tests/a11y
```

---

## 2. Test Suites & Exact Commands

### 2.1 Syntax & Python Unit / Web Suites (No MySQL required for mock-only run)
```sh
python -m compileall -q run.py main.py petcare tests
pytest tests/unit tests/web -q
```

### 2.2 Full Python + MySQL Integration Suite (`unittest discover`)
Requires a clean empty MySQL 8.4 `_test` schema and isolated temp media folders:
```sh
D_TMP=$(python -c "import tempfile; print(tempfile.gettempdir())")
mkdir -p "$D_TMP/pc-test/pets" "$D_TMP/pc-test/products" "$D_TMP/pc-test/exports"

APP_ENV=test \
SECRET_KEY="local-test-secret-key-not-for-deployment-0123456789" \
COOKIE_SECURE=0 \
DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=petcare_app DB_PASSWORD="<pw>" \
DB_NAME=petcare_ci_test PETCARE_TEST_DB_NAME=petcare_ci_test \
PET_IMAGE_DIR="$D_TMP/pc-test/pets" \
PRODUCT_IMAGE_DIR="$D_TMP/pc-test/products" \
TENANT_EXPORT_DIR="$D_TMP/pc-test/exports" \
python -m unittest discover -s tests -q
```

### 2.3 JavaScript Regression Tests (Vanilla JS Modules)
```sh
node --test tests/js/*.test.cjs
```

### 2.4 Playwright Chromium E2E + Axe Accessibility (`run_smoke.py`)
Exercises 35 full end-to-end journeys across `1440px`, `834px`, `390px`, `320px` (AI Vision 4.0 ONNX matching, Internal & Customer AI safety guardrails, Customer Storefront checkout & staff COD payment lifecycle, PO partial receiving, refunds, RBAC, multi-tenant isolation, and WCAG 2.0/2.1 AA axe checks):
```sh
PLAYWRIGHT_ARTIFACT_DIR="$D_TMP/pc-e2e" \
PET_IMAGE_DIR="$D_TMP/pc-e2e/pets" \
PRODUCT_IMAGE_DIR="$D_TMP/pc-e2e/products" \
TENANT_EXPORT_DIR="$D_TMP/pc-e2e/exports" \
AXE_CORE_PATH="$PWD/tests/a11y/node_modules/axe-core/axe.min.js" \
APP_ENV=test APP_PORT=5080 PUBLIC_BASE_URL=http://127.0.0.1:5080 \
COOKIE_SECURE=0 LAN_ACCESS_ENABLED=0 \
DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=petcare_app DB_PASSWORD="<pw>" \
DB_NAME=petcare_e2e_test PETCARE_TEST_DB_NAME=petcare_e2e_test \
SECRET_KEY="ci-browser-smoke-secret-not-for-deployment-0123456789" \
python scripts/browser_smoke/run_smoke.py
```

### 2.5 Security & Dependency Audits
```sh
bandit -q -r petcare scripts main.py run.py wsgi.py -x petcare/templates,petcare/static -b .security/bandit-baseline.json
pip-audit -r requirements.lock
pip-audit -r requirements-browser.lock
npm audit --prefix tests/a11y
docker compose config --quiet
```

---

## 3. Clean-State Rule
Drop temporary `*_test` schemas and clean `$D_TMP/pc-*` folders when finished so `instance/` inside the workspace remains unpolluted.
