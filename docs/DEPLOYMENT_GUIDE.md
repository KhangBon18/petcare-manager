# Deployment Guide (`DEPLOYMENT_GUIDE.md`)

Operational deployment specification for staging and controlled production environments (also see [STAGING_DEPLOYMENT_PLAN.md](STAGING_DEPLOYMENT_PLAN.md), [operations.md](operations.md), and [launch_readiness.md](launch_readiness.md)).

---

## 1. Mandatory Production Safeguards (`APP_ENV=production`)

`petcare/app_configuration.py` enforces fail-closed validation in `production` mode:
- **Strong Stable `SECRET_KEY`**: Random secret shared across Gunicorn workers via environment/secret manager.
- **HTTPS & Cookies**: `COOKIE_SECURE=1`, TLS terminated at trusted reverse proxy (`PUBLIC_BASE_URL=https://<domain>`), and `TRUST_PROXY=1` only when behind a single trusted reverse proxy overwriting forwarded headers.
- **Non-Demo Database Name**: Must **not** end with `_dev` or `_test`. Never enable `PETCARE_DEMO_MODE=1` in production.
- **MySQL TLS**: Provide `DB_SSL_CA` pointing to the read-only mounted MySQL CA bundle for certificate & hostname verification.
- **Dedicated Migration Account**: Run migrations via one-off job using `MIGRATION_DB_USER` / `MIGRATION_DB_PASSWORD`; keep runtime `DB_USER` strictly at DML (`SELECT, INSERT, UPDATE, DELETE`).
- **Encryption Keys**: Generate and stably retain `TENANT_EXPORT_JOB_KEY` and `MAIL_OUTBOX_KEY` (Fernet keys) across `web`, `email-worker`, and `export-worker`.
- **Disable LAN HTTP QR**: Keep `LAN_ACCESS_ENABLED=0` in production.

---

## 2. Container Stack (`Dockerfile` & `docker-compose.yml`)

Services defined in `docker-compose.yml`:
- `mysql`: MySQL 8.4 (`InnoDB`, `utf8mb4_unicode_ci`) with persistent named volume `petcare_manager_mysql_data`.
- `web`: `python:3.12-slim` non-root `petcare` user running Gunicorn (`wsgi:app`, `2` workers × `4` threads, access logs stripped of query strings to protect tokens/search terms).
- `email-worker`: `python -m petcare.services.mail_worker` (encrypted SMTP STARTTLS outbox dispatch + stale heartbeat cleanup).
- `export-worker`: `python -m petcare.services.tenant_export_worker_cli` (AES-256-GCM `.pcarexport` generation + retention pruning).

---

## 3. Controlled Upgrade Sequence

```sh
# 1. Back up database & private media
python scripts/petcare_backup.py create --media-source compose

# 2. Build/pull verified image and run one-off schema initializer
docker compose build
docker compose run --rm \
  -e MIGRATION_DB_HOST=... -e MIGRATION_DB_USER=... -e MIGRATION_DB_PASSWORD=... \
  web python -m petcare.database.initialize

# 3. Restart web & workers
docker compose up -d web email-worker export-worker
```

---

## 4. Health & Readiness Endpoints

- `GET /healthz`: Process liveness (`200 {"status": "ok"}`).
- `GET /readyz`: Verifies live MySQL connection and `readiness.py` schema/FK contract (`200 {"status": "ready"}`, `503` on missing migrations).
- `GET /workersz`: Verifies both `email-worker` and `export-worker` reported a healthy heartbeat within the last 90 seconds.
- `GET /metrics`: Disabled unless `OPS_METRICS_TOKEN` is set; restrict to private monitoring with Bearer auth.
