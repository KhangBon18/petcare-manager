# Contributing to PetCare Manager

Thank you for contributing to **PetCare Manager**.

## Development Standards

1. **Architecture & Boundaries**:
   - **Routes (`petcare/routes/`)**: Parse input, enforce `@login_required` / role checks / CSRF, delegate to services, and redirect after successful `POST`.
   - **Services (`petcare/services/`)**: Enforce business invariants, tenancy actor context (`require_actor`), input validation, and MySQL transactions (`transaction()` / `commit`).
   - **Repositories (`petcare/repositories/`)**: Hold parameterized MySQL SQL queries only; do not manage transaction commits.
2. **Code Quality & Security**:
   - Never construct SQL with unvalidated string interpolation (`%s` bound parameters only; review Bandit `# nosec` annotations carefully).
   - Never store secrets, `.env` values, tokens, or real customer PII in commits, fixtures, or screenshots.
   - Maintain multi-tenant scoping (`tenant_id`) on every read/write query and storage path.
3. **Frontend Discipline**:
   - Vanilla HTML (Jinja2), CSS (`tokens.css`, `app.css`, `ui.css`, `storefront.css`), and vanilla externalized JS (no inline `<script>` / CSP violations, no CDN dependencies).
   - Verify responsiveness across `1440px`, `834px`, `390px`, and `320px`.
4. **Testing & PR Checklist**:
   - Create isolated feature branches from `solo/khang-petcare`; open Pull Requests instead of pushing directly to `solo/khang-petcare` or `main`.
   - Run verification locally before pushing (see [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)):
     - `python -m unittest discover -s tests -q` (against an isolated `*_test` MySQL schema)
     - `node --test tests/js/*.test.cjs`
     - `bandit -q -r petcare scripts main.py run.py wsgi.py -x petcare/templates,petcare/static -b .security/bandit-baseline.json`
     - `python scripts/browser_smoke/run_smoke.py` (when UI/JS/E2E paths change)
