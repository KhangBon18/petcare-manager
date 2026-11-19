# Troubleshooting Guide (`TROUBLESHOOTING.md`)

Verified fixes for common setup, database, media, and browser runtime issues.

---

| Symptom | Root Cause | Resolution |
|---|---|---|
| `/readyz` returns `503 Service Unavailable` | Schema missing newer migrations (`pet_reference_photos_v1`, `storefront_orders_v1`, `storefront_orders_v1_1`) | Back up DB and run `python -m petcare.database.initialize`. Verify `DB_NAME` matches your intended target schema. |
| `demo_staging_setup.py` raises `Demo setup requires PETCARE_DEMO_MODE=1` | Demo safety guard enabled | Run against a disposable `*_test` database with `PETCARE_DEMO_MODE=1 APP_ENV=test` and 3 distinct `16+` char passwords (`PETCARE_DEMO_ADMIN_PASSWORD`, `PETCARE_DEMO_STAFF_PASSWORD`, `PETCARE_DEMO_CUSTOMER_PASSWORD`). |
| `403 Forbidden` / CSRF failure on HTTP `127.0.0.1` | `COOKIE_SECURE=1` or `APP_ENV=production` without HTTPS | Set `APP_ENV=development` (or `test`) and `COOKIE_SECURE=0` for HTTP loopback testing. |
| Port `5000` conflict on macOS | macOS AirPlay Receiver listens on port 5000 | Use the default `APP_PORT=5055` configured in `.env.example` and `run.py`. |
| `Unknown database` on first startup | MySQL schema has not been created yet | Create the schema in UTF8MB4 first (`CREATE DATABASE ... CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`), then run `initialize`. |
| Integration test fails with `MySQLInterfaceError` on port `3306` vs custom Docker port | `.env` overrides or omitted `APP_ENV=test` / `DB_PORT` | Explicitly pass `APP_ENV=test DB_HOST=127.0.0.1 DB_PORT=<port> DB_NAME=<db>_test PETCARE_TEST_DB_NAME=<db>_test`. |
| Pet/Product photo permissions or missing file error | Custom `PET_IMAGE_DIR` / `PRODUCT_IMAGE_DIR` lacks `rwx` for Flask user, or old files lack `0600` permissions | Ensure OS user owns image dirs (`petcare:petcare` in Docker) and run `python -m petcare.vision.secure_photo_permissions`. |
| Visual Search model missing or corrupted | Incomplete clone or modified ONNX binary | Re-verify `shasum -a 256 petcare/vision/models/*.onnx` against [`petcare/vision/models/MODEL_MANIFEST.json`](../petcare/vision/models/MODEL_MANIFEST.json). |
| Webcam capture blocked in LAN demo on phone | Browser restricts `getUserMedia` to HTTPS or `localhost` | On HTTP LAN mobile (`LAN_ACCESS_ENABLED=1`), use the native file picker camera button on `/pets/find-similar`. |
