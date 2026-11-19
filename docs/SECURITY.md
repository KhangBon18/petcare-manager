# Security Documentation (`docs/SECURITY.md`)

Detailed technical inventory of security controls in **PetCare Manager**. See also root [`SECURITY.md`](../SECURITY.md).

---

## 1. Authentication, Passwords & Session Controls
- Passwords hashed with **PBKDF2-HMAC-SHA256**; plaintext credentials never persisted or logged.
- Signed session cookie carries only session identity (`user_id`, `tenant_id`, `session_version`); user active state, membership, and role reload from MySQL per request (`petcare/auth.py`). Changing password, revoking access, or altering membership increments `session_version` to invalidate old sessions immediately.
- Login throttling (`login_throttle`) and public/API request throttling (`request_throttle`) use HMAC-hashed client IP keys in MySQL shared cleanly across Gunicorn workers without storing raw IPs.

## 2. CSRF, Headers, CSP & Media Privacy
- All mutating forms and JSON endpoints validate **Flask-WTF CSRF tokens**.
- Strict Content Security Policy disallows inline `<script>` tags; progressive enhancement runs strictly via external static JS (`petcare/static/js/`).
- Authenticated HTML responses send `Cache-Control: private, no-store` to prevent cross-account cache leakage.
- Gunicorn access logs omit query strings (`%(m)s %(U)s %(s)s`) so search queries and invite tokens are never logged.
- Uploaded photos (`<= 5 MB`) undergo Pillow decoding/re-encoding to strip EXIF metadata, randomized filenames, POSIX private permissions, and mandatory authenticated route ownership checks (`pets.photo`, `products.photo`, `storefront.public_pet_photo`).

## 3. Multi-Tenant & Role Boundaries
- Every query passes explicit `tenant_id` scoping reinforced by **composite foreign keys** in InnoDB (`readiness.py`).
- Staff cannot escalate to Store Settings, User Admin, Purchasing, Refunds, Financial Exports, or `/activity/`.
- Public `/shop` routes only expose `available` pets, `active` products, order-lookup verification (`order_code + phone`), and customer-owned orders.

## 4. Cryptography for Exports, Backups & Mail Outbox
- Tenant exports (`.pcarexport`) and full system backups (`.pcarebackup`) use **AES-256-GCM** with random salt/nonce and **PBKDF2-HMAC-SHA256** key derivation (`0600` file permissions, CSV formula-injection neutralization).
- Pending passphrases (`tenant_export_jobs`) and mail payloads (`email_outbox`) are **Fernet-encrypted** in MySQL via `TENANT_EXPORT_JOB_KEY` (with rotation support via `TENANT_EXPORT_JOB_FALLBACK_KEYS`) and `MAIL_OUTBOX_KEY`.

## 5. Automated Security Verification
- GitHub Actions runs **Bandit** (baseline diff), **Trivy** filesystem secret scan & production Docker image CVE scan, **pip-audit** on locked runtime and browser dependency graphs, and **`npm audit`** on `tests/a11y`.
