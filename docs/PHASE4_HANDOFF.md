# Handoff Phase 4 — Product Modernization

Ngày: 2026-11-09. Phase 3.5 đã xác lập baseline test và browser smoke. Phase 4 nên tập trung vào trải nghiệm sản phẩm/ưu tiên người dùng, không khởi đầu bằng một đợt audit tổng quát hay rewrite framework.

## Product scope và chức năng cần giữ

Petcare Manager hiện là ứng dụng retail web cho cửa hàng thú cưng: khách hàng và hồ sơ lịch sử; catalog thú cưng/sản phẩm; ảnh riêng tư/tìm tương tự local; POS, hóa đơn, thanh toán trạng thái nội bộ, hủy và refund ledger; tồn kho/stock movement; supplier/purchase order/partial receiving; báo cáo/XLSX; local assistant; multi-tenant account/role, invites, ownership transfer, audit và tenant export.

Role owner/admin/staff thuộc membership theo cửa hàng; giữ tenant isolation, CSRF, RBAC, server-side validation, money `Decimal`, invoice currency snapshots, idempotency key cho receiving/refund, stock ledger consistency và transaction rollback. Refund record không gọi payment gateway; cửa hàng tự xử lý hoàn tiền ngoài hệ thống. Clinic, appointment, vaccination và spa không nằm trong retail web scope hiện hành.

## Module inventory và architecture

Stack hiện hành: Python 3.11+, Flask/Flask-WTF, Jinja, MySQL 8/InnoDB, mysql-connector-python, CSS/vanilla JS; không có ORM, frontend bundler hoặc CDN. Entry points: `python run.py`, `wsgi:app`; `requirements.txt` range metadata, `requirements.lock` exact runtime set.

Để giữ inventory đầy đủ và tránh tạo bản kiểm kê lệch nguồn, file-by-file inventory có thẩm quyền là [MODULE_INVENTORY.md](MODULE_INVENTORY.md): 14 core modules; 2 AI; 9 database; 16 route modules; 25 repositories; 39 services; 7 vision/media. Tài liệu đó liệt kê tên từng module. Route + persistence contracts nằm trong [API_CONTRACT.md](API_CONTRACT.md), architecture và transaction boundaries trong [architecture.md](architecture.md).

Module names đầy đủ để bắt đầu điều hướng repository:

| Package | Files/modules |
|---|---|
| `petcare/` core | `__init__.py`, `app.py`, `app_configuration.py`, `app_factory.py`, `app_hooks.py`, `auth.py`, `config.py`, `email_address.py`, `i18n.py`, `money.py`, `prepare_demo.py`, `secure_bundle.py`, `security.py`, `timezones.py` |
| `petcare/ai/` | `__init__.py`, `client.py` |
| `petcare/database/` | `__init__.py`, `connection.py`, `create_admin.py`, `create_store.py`, `export_tenant.py`, `initialize.py`, `readiness.py`, `seed.py`, `tenancy.py` |
| `petcare/routes/` | `__init__.py`, `account_routes.py`, `assistant_routes.py`, `audit_routes.py`, `auth_routes.py`, `customer_routes.py`, `health_routes.py`, `invoice_routes.py`, `main_routes.py`, `metrics_routes.py`, `pet_routes.py`, `product_routes.py`, `purchasing_routes.py`, `report_routes.py`, `store_routes.py`, `user_routes.py` |
| `petcare/repositories/` | `__init__.py`, `account_token_repo.py`, `assistant_repo.py`, `audit_repo.py`, `base.py`, `catalog_repo.py`, `customer_repo.py`, `invitation_repo.py`, `invoice_repo.py`, `login_throttle_repo.py`, `mail_outbox_repo.py`, `ops_metrics_repo.py`, `pet_repo.py`, `product_repo.py`, `purchase_repo.py`, `refund_repo.py`, `report_repo.py`, `request_throttle_repo.py`, `restock_repo.py`, `tenant_cleanup_repo.py`, `tenant_export_repo.py`, `tenant_owner_transfer_repo.py`, `tenant_repo.py`, `user_repo.py`, `worker_heartbeat_repo.py` |
| `petcare/services/` | `__init__.py`, `account_security_service.py`, `actors.py`, `assistant_local.py`, `assistant_query.py`, `assistant_service.py`, `audit_service.py`, `auth_service.py`, `catalog_intent.py`, `catalog_service.py`, `common.py`, `customer_service.py`, `exceptions.py`, `invoice_service.py`, `mail_outbox_worker.py`, `mail_service.py`, `mail_templates.py`, `mail_worker.py`, `ops_metrics_service.py`, `pet_image_service.py`, `pet_service.py`, `product_service.py`, `purchase_service.py`, `refund_service.py`, `report_export_service.py`, `report_service.py`, `request_throttle_service.py`, `restock_service.py`, `tenant_export_service.py`, `tenant_export_storage.py`, `tenant_export_worker.py`, `tenant_export_worker_cli.py`, `tenant_invite_service.py`, `tenant_owner_transfer_service.py`, `tenant_settings_service.py`, `tenant_signup_cleanup.py`, `ui_text.py`, `user_service.py`, `worker_heartbeat.py` |
| `petcare/vision/` | `__init__.py`, `image_features.py`, `media_storage.py`, `migrate_media.py`, `photo_storage.py`, `reindex_pet_descriptors.py`, `secure_photo_permissions.py` |

Frontend hiện có 50 templates tại `petcare/templates/`; CSS `static/css/tokens.css`, `app.css`, `motion.css`; JS `app.js`, `assistant.js`, `camera_scan.js`, `export-job.js`, `invoice.js`, `motion.js`, `pet_attributes.js`, `photo_preview.js`, `pos.js`, `purchasing.js`, `reports.js`; GSAP vendor bundle được phục vụ local. Flask/Jinja render HTML; forms dùng POST + CSRF và thường flash/redirect; một số lookup/status trả JSON.

## Browser routes/features

- Auth/account: `/login`, `/signup` (off mặc định), `/account/settings`, verify/reset email/password.
- Dashboard/home: `/dashboard`.
- Customers: `/customers/`, create/edit/detail/deactivate.
- Pets/catalog: `/pets/`, photo, profile, create/edit, similar-image search, optional attribute suggestion.
- Products/inventory: `/products/`, create/edit/detail/photo/stock adjustment.
- POS/invoices: `/invoices/new`, customer/item lookups, quick customer, detail/pay/cancel/refund.
- Purchasing (admin): `/purchasing/`, products lookup, suppliers, order create/detail/receive/cancel.
- Reports: `/reports/`, XLSX export; assistant `/assistant/chat` (local-first).
- Tenant administration: `/store/settings`, `/users/`, invites, ownership, tenant export/status/download, `/activity/`.
- Probes: `/healthz`, `/readyz`, `/workersz`; `/metrics` only with configured bearer token.

Phase 3.5 browser smoke mở dashboard/customers/pets/products/invoices/purchasing/reports, xác nhận staff customers allowed và `/users/` denied, keyboard Tab trên stock form, tablet nav ở 820×1180, POS cart 390×844, basic landmark/name checks, và refund confirmation/persistence. Chưa có browser CRUD coverage cho mọi màn hình.

## Safe QA setup

1. Dùng MySQL schema disposable kết thúc `_test`; user DB chỉ được quyền trên schema đó. `DB_NAME` phải bằng `PETCARE_TEST_DB_NAME`.
2. Override `.env` dev values trước khi chạy app/tests; đặt `APP_ENV=test`, port loopback riêng, ảnh/export directories trong temp storage và disable SMTP/AI/provider/S3 credentials.
3. Cài runtime và browser toolchain:

   ```sh
   python -m pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock
   python -m playwright install chromium
   python scripts/browser_smoke/run_smoke.py
   ```

   Runner tự initialize/seed test schema, từ chối tên DB không khớp `*_test`, khởi động Flask, chờ `/readyz=200`, dừng process và ghi traces/screenshots/results. Không trỏ runner sang `petcare_shop_dev` hoặc production.

CI hosted job mới được wire, local PASS nhưng chưa chạy GitHub Actions. Database dev hiện 20 bảng và readiness 503; không chạy initializer/seed ở đó. Migration gate xem [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md).

## API contracts không được làm vỡ

- Không đổi method/path, role/CSRF, status codes, JSON field types và HTML POST/redirect semantics mà không cập nhật API contract + tests.
- Session actor/tenant lấy từ server membership; tenant ID, role, tiền và tồn do client gửi không phải nguồn chuẩn.
- JSON lookup giá trả decimal string; report XLSX nhận snapshot token server tạo.
- Purchase receiving phải giữ hidden `receipt_request_key`: retry giữ UUID + payload, một shipment mới dùng key mới.
- Refund form giữ `request_key`; cùng key/payload retry không thêm ledger. Invoice paid vẫn giữ `paid`; refund ledger và stock movement cập nhật trong transaction.
- Ảnh/catalog assets same-origin; media private và tenant-scoped. Signed-in pages dùng `private, no-store`.
- API route matrix/field semantics: [API_CONTRACT.md](API_CONTRACT.md).

## UI/UX constraints và cơ hội

- Không đổi framework chỉ để làm mới giao diện. Tiếp tục dùng tokens, shared Jinja base/partials và local assets; tránh thêm CDN hoặc runtime dependency mới khi chưa có lý do sản phẩm.
- Giữ Vietnamese/English, responsive nav, POS mobile cart preview, form value recovery, reduced-motion behavior, focus semantics, accessible names, monetary totals một dòng và actual server flash/error states.
- Các lỗi UX đã xác nhận ở [UX_ISSUES.md](UX_ISSUES.md): E2E-01/02/03 và UX-04/05/06 đã fixed; NET-01 favicon issue còn mở trong audit history. Phase 3.5 smoke không tìm thấy failed request hoặc JS exception; expected `/users/` 403 phát sinh console log do browser.
- Cơ hội Phase 4: prototype customer/pet profile journey, POS keyboard/mobile efficiency, inventory receiving visibility, reports comparison/filter hierarchy; validate bằng browser trước khi đổi scope. Full accessibility, screen reader, contrast, zoom 200% vẫn cần review.

## Giới hạn kỹ thuật còn lại

- `petcare_shop_dev` readiness 503; migration no-go cho tới khi backup mới được restore-test và có phê duyệt tường minh.
- Hosted CI, Trivy, production container/runtime và production database backup/restore chưa xác minh.
- SMTP thật, remote AI/AI Vision, S3, worker daemon/heartbeat chưa chạy. AI provider có cost/privacy implications; external calls cần staging synthetic data.
- Chưa có full browser CRUD suite, screen reader/axe review, load/branch coverage hoặc performance baseline.

Baseline test và result evidence: [PHASE35_RELEASE_BASELINE.md](PHASE35_RELEASE_BASELINE.md), [BROWSER_SMOKE_CI_REPORT.md](BROWSER_SMOKE_CI_REPORT.md), [TEST_MATRIX.md](TEST_MATRIX.md).
