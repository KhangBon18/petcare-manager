# Danh mục module và tính năng

Ngày kiểm kê: 2026-11-09. Đường dẫn tính từ thư mục gốc repository.

## Stack và entry point

- Runtime: Python 3.11+; audit host Python 3.13.3; Dockerfile Python 3.12.
- Web: Flask + Flask-WTF/CSRF + Jinja2; frontend HTML/CSS/vanilla JavaScript, không có bundler.
- Persistence: MySQL 8/InnoDB/utf8mb4 qua mysql-connector-python; không có ORM.
- Worker: tiến trình riêng cho email outbox và tenant export.
- Tích hợp tùy chọn: endpoint chat-completions/AI Vision, S3-compatible object storage, SMTP, Prometheus.
- Lệnh chạy: `python run.py`; WSGI: `wsgi:app`; compatibility entry points: `main.py` và `petcare/app.py`.
- Cài đặt: `python -m pip install -r requirements.txt -c requirements.lock`. `requirements.txt` giữ dải tương thích; `requirements.lock` khóa phiên bản runtime đã resolve để CI và Docker cài bộ giống nhau.

## Package Python

Repository có 112 file Python trong package `petcare`. Các module theo package:

### Core — 14 module tại `petcare/`

`__init__.py`, `app.py`, `app_configuration.py`, `app_factory.py`, `app_hooks.py`, `auth.py`, `config.py`, `email_address.py`, `i18n.py`, `money.py`, `prepare_demo.py`, `secure_bundle.py`, `security.py`, `timezones.py`.

Trách nhiệm: app composition, cấu hình và kiểm tra môi trường, hooks/error handling, xác thực/phiên, định dạng locale/tiền/thời gian, preflight demo, bundle mã hóa và chính sách bảo mật.

### AI — 2 module tại `petcare/ai/`

`__init__.py`, `client.py`. Client HTTP cho provider tương thích chat-completions; endpoint/khóa/model được cấu hình bằng biến môi trường.

### Database — 9 module tại `petcare/database/`

`__init__.py`, `connection.py`, `create_admin.py`, `create_store.py`, `export_tenant.py`, `initialize.py`, `readiness.py`, `seed.py`, `tenancy.py`.

SQL schema: `schema.sql`, `purchasing.sql`, `refunds.sql`. Các script migration thêm bảng/cột/index và backfill; không dùng ORM. `connection.py` quản lý pool MySQL runtime và migration connection riêng, thiết lập UTC, reset tenant context và transaction commit/rollback.

### Routes — 16 module tại `petcare/routes/`

`__init__.py`, `account_routes.py`, `assistant_routes.py`, `audit_routes.py`, `auth_routes.py`, `customer_routes.py`, `health_routes.py`, `invoice_routes.py`, `main_routes.py`, `metrics_routes.py`, `pet_routes.py`, `product_routes.py`, `purchasing_routes.py`, `report_routes.py`, `store_routes.py`, `user_routes.py`.

Các blueprint đăng ký trong `petcare/app_factory.py`. 79 route ứng dụng được đăng ký (không tính endpoint static của Flask). Route xử lý HTTP/CSRF/render/redirect; business logic nằm ở service.

### Repositories — 25 module tại `petcare/repositories/`

`__init__.py`, `account_token_repo.py`, `assistant_repo.py`, `audit_repo.py`, `base.py`, `catalog_repo.py`, `customer_repo.py`, `invitation_repo.py`, `invoice_repo.py`, `login_throttle_repo.py`, `mail_outbox_repo.py`, `ops_metrics_repo.py`, `pet_repo.py`, `product_repo.py`, `purchase_repo.py`, `refund_repo.py`, `report_repo.py`, `request_throttle_repo.py`, `restock_repo.py`, `tenant_cleanup_repo.py`, `tenant_export_repo.py`, `tenant_owner_transfer_repo.py`, `tenant_repo.py`, `user_repo.py`, `worker_heartbeat_repo.py`.

Trách nhiệm: SQL có tham số cho auth/tokens, membership, khách hàng, catalog, hóa đơn/kho, nhập hàng/hoàn tiền, báo cáo, audit, throttling, mail/export jobs và worker heartbeat. Repository không sở hữu commit.

### Services — 39 module tại `petcare/services/`

`__init__.py`, `account_security_service.py`, `actors.py`, `assistant_local.py`, `assistant_query.py`, `assistant_service.py`, `audit_service.py`, `auth_service.py`, `catalog_intent.py`, `catalog_service.py`, `common.py`, `customer_service.py`, `exceptions.py`, `invoice_service.py`, `mail_outbox_worker.py`, `mail_service.py`, `mail_templates.py`, `mail_worker.py`, `ops_metrics_service.py`, `pet_image_service.py`, `pet_service.py`, `product_service.py`, `purchase_service.py`, `refund_service.py`, `report_export_service.py`, `report_service.py`, `request_throttle_service.py`, `restock_service.py`, `tenant_export_service.py`, `tenant_export_storage.py`, `tenant_export_worker.py`, `tenant_export_worker_cli.py`, `tenant_invite_service.py`, `tenant_owner_transfer_service.py`, `tenant_settings_service.py`, `tenant_signup_cleanup.py`, `ui_text.py`, `user_service.py`, `worker_heartbeat.py`.

Trách nhiệm: xác thực actor/quyền, validation, giao dịch nghiệp vụ, locale cho thông báo, trợ lý local/provider, báo cáo, mail/export workers, invite/ownership, media metadata và heartbeat.

### Vision/media — 7 module tại `petcare/vision/`

`__init__.py`, `image_features.py`, `media_storage.py`, `migrate_media.py`, `photo_storage.py`, `reindex_pet_descriptors.py`, `secure_photo_permissions.py`.

Trách nhiệm: giải mã/chuẩn hóa/descriptor ảnh, tìm ảnh gần đúng, backend local/S3, migration và reindex ảnh, phân quyền đọc ảnh.

## Màn hình và template

50 file HTML/Jinja trong `petcare/templates`:

- Khung dùng chung: `base.html`, `dashboard.html`, `pagination.html`.
- Auth: `auth/login.html`, `auth/signup.html`, `auth/signup_complete.html`.
- Account: `account/settings.html`, `account/verify_email.html`, `account/forgot_password.html`, `account/reset_password.html`.
- Khách hàng: `customers/index.html`, `customers/form.html`, `customers/detail.html`.
- Thú cưng bán lẻ: `pets/index.html`, `pets/form.html`, `pets/detail.html`, `pets/search_image.html`.
- Sản phẩm: `products/index.html`, `products/form.html`, `products/detail.html`.
- POS/hóa đơn: `invoices/index.html`, `invoices/form.html`, `invoices/detail.html`.
- Nhập hàng: `purchasing/index.html`, `purchasing/order_form.html`, `purchasing/detail.html`, `purchasing/suppliers.html`, `purchasing/supplier_form.html`.
- Báo cáo: `reports/index.html`, `reports/error.html`.
- Audit: `audit/index.html`.
- Cửa hàng: `store/settings.html`.
- Thành viên/tenant: `users/index.html`, `users/form.html`, `users/accept_invitation.html`, `users/ownership.html`, `users/export.html`, `users/export_job.html`.
- Lỗi: `errors/403.html`, `errors/404.html`, `errors/413.html`, `errors/500.html`, `errors/database.html`.
- Partials: `partials/business_chart.html`, `partials/form_errors.html`, `partials/icons.html`, `partials/invoice_line.html`, `partials/language_picker.html`, `partials/pos_card.html`, `partials/restock.html`.

## Frontend assets

- CSS: `static/css/tokens.css`, `static/css/app.css`, `static/css/motion.css`.
- JavaScript: `static/js/app.js`, `assistant.js`, `camera_scan.js`, `export-job.js`, `invoice.js`, `motion.js`, `pet_attributes.js`, `photo_preview.js`, `pos.js`, `purchasing.js`, `reports.js`.
- Vendor: `static/vendor/gsap/gsap.min.js`; test kiểm tra bản phân phối local và license. Không phụ thuộc CDN theo template/tests.
- Icon/fav: `static/favicon.svg` và `templates/partials/icons.html`.

## Dữ liệu MySQL

26 bảng khi khởi tạo schema hiện hành: `tenants`, `schema_migrations`, `users`, `account_tokens`, `email_outbox`, `tenant_users`, `tenant_invitations`, `tenant_owner_transfers`, `tenant_export_jobs`, `login_throttle`, `request_throttle`, `worker_heartbeats`, `audit_events`, `customers`, `products`, `pets`, `pet_photo_lsh`, `invoices`, `invoice_items`, `stock_movements`, `suppliers`, `purchase_orders`, `purchase_order_items`, `purchase_order_receipt_requests`, `invoice_refunds`, `invoice_refund_items`.

Không có model ORM; schema/migration SQL và repository queries là nguồn hợp đồng dữ liệu.

## Scripts, tài liệu và kiểm thử

- Lệnh quản trị/benchmark: `scripts/petcare_backup.py`, `scripts/benchmark_catalog_search.py`, `scripts/benchmark_pet_image_search.py`; database CLIs nằm trong `petcare/database/` và `petcare/vision/`.
- Tài liệu hiện hành: README, REPO_GUIDE, `docs/scope.md`, `docs/architecture.md`, `docs/erd.md`, `docs/data_dictionary.md`, `docs/billing_rules.md`, `docs/operations.md`, `docs/media_storage.md`, `docs/phase3_ai_automation.md`, `docs/launch_readiness.md` và tài liệu QA.
- Tests: 51 file Python trong `tests/unit`, `tests/web`, `tests/integration` và 4 file JavaScript trong `tests/js`; tổng 364 Python test methods/cases trong lần chạy Phase 1.5, không skip khi MySQL test database riêng được cung cấp. 63 là integration tests MySQL trong lần chạy này.
- Tài liệu source desktop cũ ở `docs/archive/desktop_source` và `docs/archive/desktop_tests` không được import/đăng ký như ứng dụng web hiện hành. Khám bệnh, lịch hẹn và tiêm phòng là ngoài phạm vi retail web theo README/REPO_GUIDE.

## Tính năng theo domain

| Domain | Màn hình/route | Service chính |
|---|---|---|
| Auth và account | login/signup/logout, đổi locale, verify email, password reset, profile | auth, account security, mail |
| Multi-tenant | switch store, store settings, member/invite, owner transfer | actors, tenant settings/invite/transfer |
| Khách hàng | search/list/profile/create/update/active | customer |
| Catalog | sản phẩm, thú cưng, ảnh, điều chỉnh kho, suggest attributes, tìm ảnh | product, pet, pet image, media |
| POS | tạo draft invoice, quick customer, item/customer lookups, pay/cancel/refund | invoice, refund |
| Nhập hàng | suppliers, purchase orders, partial receive/cancel, restock | purchase, restock |
| Báo cáo | date range, charts/tables, XLSX snapshot export | report, report export |
| Trợ lý | local Q&A, catalog cards, optional provider | assistant local/query/service |
| Audit/ops | activity, health/readiness/worker probes, metrics | audit, heartbeat, metrics |
| Dữ liệu | tenant export queue/status/download, operator backup/verify | tenant export, secure bundle, backup script |

## Quan sát về code chưa hoàn tất

Không tìm thấy TODO/FIXME/NotImplemented trong Python/JS đang chạy. Các `pass` nhìn thấy là lớp exception rỗng hoặc nhánh bỏ qua lỗi cleanup, không phải implementation stub. Không xác nhận dead code ngoài source desktop đã lưu archive. `petcare/app.py`, package `__init__.py` và facade trong assistant được mô tả trong docs như compatibility exports, không nên xóa chỉ vì ít caller.
