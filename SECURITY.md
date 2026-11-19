# Security Policy

> Detailed technical controls and production deployment safeguards are also documented in [docs/SECURITY.md](docs/SECURITY.md).

## Supported Versions

Only the latest release on `main` and integrated `solo/khang-petcare` baseline receive security updates.

## Reporting a Vulnerability

Please **do not** disclose security vulnerabilities, credentials, or sensitive tenant data in public GitHub issues or Pull Requests.

Report security findings privately to the repository maintainer via GitHub Private Vulnerability Reporting (or direct private contact) with:
- Affected route, module, or configuration surface
- Reproduction steps using synthetic data only
- Assessed impact and suggested remediation if available

## Core Security Guarantees in PetCare Manager

- **Authentication & Sessions**: PBKDF2-HMAC-SHA256 password hashing, per-request user/membership/role verification in MySQL, and `session_version` revocation on password resets or role changes.
- **CSRF & Response Isolation**: Flask-WTF CSRF protection on state-changing requests (`POST` / JSON APIs), strict CSP (no inline `<script>`), `private, no-store` cache headers on authenticated routes.
- **Database & Tenancy**: Parameterized MySQL queries, InnoDB composite `tenant_id` foreign keys, separation of runtime DML account (`SELECT/INSERT/UPDATE/DELETE`) from one-off migration credentials (`MIGRATION_DB_USER`), and mandatory `DB_SSL_CA` verification in production.
- **Encrypted Workers & Exports**: AES-256-GCM encrypted `.pcarexport` tenant bundles (`export_tenant.py`), `.pcarebackup` encrypted backups (`petcare_backup.py`), Fernet-encrypted `email_outbox` and `tenant_export_jobs` passphrases.
