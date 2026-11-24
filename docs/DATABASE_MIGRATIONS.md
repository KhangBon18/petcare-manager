# Database Schema & Migrations Guide (`DATABASE_MIGRATIONS.md`)

PetCare Manager runs exclusively on **MySQL 8.0.16+** (`InnoDB`, `utf8mb4_unicode_ci`) using explicit SQL DDL and idempotent forward migrations — no ORM (`SQLAlchemy`) or SQLite runtime support.

---

## 1. Schema Structure (32 Tables across 4 SQL Modules)

| SQL Module | Tables Created | Purpose |
|---|---|---|
| [`petcare/database/schema.sql`](../petcare/database/schema.sql) (21) | `tenants`, `schema_migrations`, `users`, `account_tokens`, `email_outbox`, `tenant_users`, `tenant_invitations`, `tenant_owner_transfers`, `tenant_export_jobs`, `login_throttle`, `request_throttle`, `worker_heartbeats`, `audit_events`, `customers`, `products`, `pets`, `pet_photo_lsh`, `pet_reference_photos`, `invoices`, `invoice_items`, `stock_movements` | Core multi-tenant identity, auth/session versioning, encrypted workers, throttling, audit, retail catalog, LSH vision descriptors, and POS billing/stock ledger |
| [`petcare/database/purchasing.sql`](../petcare/database/purchasing.sql) (4) | `suppliers`, `purchase_orders`, `purchase_order_items`, `purchase_order_receipt_requests` | Suppliers, snapshotted purchase orders, partial receipts & receipt idempotency keys |
| [`petcare/database/refunds.sql`](../petcare/database/refunds.sql) (2) | `invoice_refunds`, `invoice_refund_items` | Separate immutable-invoice refund ledger & restock disposition |
| [`petcare/database/storefront.sql`](../petcare/database/storefront.sql) (5) | `customer_accounts`, `customer_orders`, `customer_order_items`, `customer_order_pet_locks`, `tenant_public_policies` | Customer portal auth, pickup/COD orders, item snapshots, exclusive pet reservation locks, and Admin-configured public store policies/contacts ([contract](STORE_SETTINGS_POLICIES.md)) |

---

## 2. Recorded Schema Migrations (`schema_migrations`)

`python -m petcare.database.initialize` executes idempotently using `MIGRATION_DB_*` credentials (falling back to `DB_*` in non-production):
1. `datetime_storage_utc_v1` — Converts legacy local-offset timestamps to UTC-naive storage with tenant IANA timezone rendering.
2. `purchasing_orders_v1` — Applies `purchasing.sql`.
3. `invoice_refunds_v1` — Applies `refunds.sql`.
4. `purchase_receipt_idempotency_v1` — Adds request-fingerprint idempotency table for multi-batch receiving.
5. `pet_reference_photos_v1` — Adds multi-photo reference gallery (`<= 5`/pet) & backfills existing primary pet photos.
6. `storefront_orders_v1` — Applies `storefront.sql`.
7. `storefront_orders_v1_1` — Adds `fulfilled` status and `fulfilled_at` column cleanly for upgrades from Storefront MVP 1.0.
8. `storefront_public_policies_v1` — Ensures `tenant_public_policies` exists (`storefront.sql`) for Admin-editable public Storefront policies & contacts.

---

## 3. Readiness Contract & Privilege Separation

- **`petcare/database/readiness.py`**: Powers `/readyz` (`schema_contract_is_ready()`), verifying required columns, composite tenant foreign keys (`REQUIRED_TENANT_FOREIGN_KEYS`, `REQUIRED_GLOBAL_FOREIGN_KEYS`), and applied migrations read-only.
- **Runtime vs Migration Users (Production)**:
  - Web & worker runtime (`DB_USER`): Grant **DML only** (`SELECT, INSERT, UPDATE, DELETE`) on the application schema.
  - One-off migration job (`MIGRATION_DB_USER`): Grant DDL (`CREATE, ALTER, INDEX, REFERENCES, DROP`) only during controlled upgrade runs. Never give MySQL `root` credentials to the web container.

---

## 4. Safe Fresh Install vs Upgrade Procedure

1. **Back up first** (on existing DBs): `python scripts/petcare_backup.py create --media-source host` (or `--media-source compose`).
2. **Run initializer**: `python -m petcare.database.initialize` (tested idempotent on fresh install and on upgrades from historical AI-3.4 commit `7514b47` -> `31` tables).
3. **Verify `/readyz`**: Confirm HTTP `200 {"status": "ready"}`.
4. **Demo data**: Run `scripts/demo_staging_setup.py --reset-disposable` **only** against isolated `*_test` schemas with `PETCARE_DEMO_MODE=1`.
