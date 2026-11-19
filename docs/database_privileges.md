# MySQL database accounts

Production uses separate credentials for the application and schema changes. Create the database and accounts with the managed database administrator or the provider's control plane. Replace the example database name, account hosts and generated secrets; keep secrets out of shell history and Git.

```sql
CREATE DATABASE `petcare_prod`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'petcare_runtime'@'APP_HOST'
  IDENTIFIED BY 'GENERATE_A_UNIQUE_RUNTIME_SECRET';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON `petcare_prod`.* TO 'petcare_runtime'@'APP_HOST';

CREATE USER 'petcare_migrator'@'MIGRATION_HOST'
  IDENTIFIED BY 'GENERATE_A_UNIQUE_MIGRATION_SECRET';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `petcare_prod`.* TO 'petcare_migrator'@'MIGRATION_HOST';
```

`APP_HOST` should match only the application network identity; `MIGRATION_HOST` should match only the one-off release runner. Neither account needs a global grant or `GRANT OPTION`. The runtime account has no DDL privileges. The migration account can create/update schema and backfill tenant data; it is not used by HTTP requests.

Configure the web service with `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER=petcare_runtime`, and `DB_PASSWORD`. Inject `MIGRATION_DB_USER=petcare_migrator` and `MIGRATION_DB_PASSWORD` only into a trusted one-off schema job, with `MIGRATION_DB_HOST`, `MIGRATION_DB_PORT`, and `MIGRATION_DB_NAME` when they differ from the runtime connection. The initializer rejects a shared account and a different target database. Keep migration credentials in the deployment secret store and out of the long-running web container.

Production also requires `DB_SSL_CA`, the path to the managed MySQL provider's CA bundle as mounted inside the web, worker, and one-off migration containers. Connector/Python is configured to verify the server certificate and hostname; a missing CA file makes production startup or connection configuration fail. Mount the CA read-only and rotate it through a deployment rollout. Development/test connections omit TLS options unless a CA is explicitly configured.

The app uses a thread-safe Connector/Python pool per process. `DB_POOL_SIZE` defaults to 5 and is limited to 1–32 connections. Capacity is multiplied by the number of web workers and other processes using the same setting; set it below the database's connection budget with headroom for migrations, operators and monitoring. Returned sessions are reset and the app reapplies UTC plus a null tenant context before each checkout.

Before a production migration, take and verify a backup. Then run `python -m petcare.database.initialize` in the one-off job. It uses the migration connection; ordinary service transactions, user/store provisioning, demo seeding and web requests continue to use the runtime account. Production initialization fails if migration credentials are missing. Local development and test environments may omit them and fall back to `DB_USER` so the existing Compose and isolated-test workflows remain simple.

The initializer performs additive MySQL DDL, which may auto-commit. Run it as a controlled release step, inspect `/readyz`, verify the tenant backfill and constraints, and only then route traffic. Do not run demo seed against production data.

## Local privilege verification

On 2026-10-18, the documented split was exercised against a disposable MySQL 8.4 container and isolated database. The migration account initialized the schema; the app then connected with production-mode settings and the DML-only runtime account, returned `200` from `/readyz`, and completed a read. MySQL denied `CREATE TABLE` to that runtime account. The container was removed afterward. This confirms the application wiring and grant boundary locally; each production provider still needs its own accounts and secrets provisioned and verified.
