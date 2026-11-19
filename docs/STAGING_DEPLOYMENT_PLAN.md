# Kế hoạch & Kiểm toán Sẵn sàng Triển khai Staging (`STAGING_DEPLOYMENT_PLAN.md`)

> **Trạng thái**: Đã kiểm toán cấu hình runtime, container và bảo mật trên nhánh `solo/khang-petcare` (`5c34b98`). **Chưa deploy lên staging/production** cho tới khi các điều kiện hạ tầng bên dưới được chuẩn bị đầy đủ.

---

## 1. Phát hiện kiểm toán cấu hình & tách môi trường

Qua rà soát [petcare/config.py](../petcare/config.py), [petcare/app_configuration.py](../petcare/app_configuration.py), [petcare/app_hooks.py](../petcare/app_hooks.py), [Dockerfile](../Dockerfile) và [docker-compose.yml](../docker-compose.yml):

1. **Cách thiết lập `APP_ENV` cho Staging (Quan trọng)**:
   - Hiện tại, các cơ chế fail-closed bảo mật nghiêm ngặt (`SESSION_COOKIE_SECURE=1`, `WTF_CSRF_SSL_STRICT=True`, HSTS header `Strict-Transport-Security`, bắt buộc `SECRET_KEY >= 32` ký tự, cấm `DB_USER=root`, cấm database hậu tố `_dev`/`_test`, bắt buộc `DB_SSL_CA` xác thực cả chứng chỉ và hostname, bắt buộc `PUBLIC_BASE_URL` HTTPS, bắt buộc `MAIL_STARTTLS`, bắt buộc `TENANT_EXPORT_JOB_KEY` chuẩn Fernet, tách biệt `MIGRATION_DB_USER`) **chỉ kích hoạt khi `APP_ENV=production`**.
   - **Khuyến nghị**: Môi trường **Staging** phải chạy với **`APP_ENV=production`**, nhưng trỏ vào **hạ tầng cô lập hoàn toàn với Production** (DB `petcare_shop_staging`, secret store riêng, bucket S3 riêng, tên miền HTTPS staging riêng như `https://staging-petcare.<domain>`). Không đặt `APP_ENV=staging` vì sẽ làm app lọt qua các kiểm tra bảo mật production.

2. **Container & Tải ảnh ONNX đồng thời**:
   - [Dockerfile](../Dockerfile) chạy nền `python:3.12-slim` dưới user không đặc quyền `petcare:petcare`, 2 Gunicorn workers × 4 threads (`--timeout 30`), expose cổng `8000`.
   - `IMAGE_PROCESSING_CONCURRENCY=1` (tính per worker) giới hạn tối đa **2 tiến trình decode/ONNX song song trên mỗi container** bằng `BoundedSemaphore`, trả HTTP `429 Retry-After: 2` (hoặc flash warning) khi quá tải để tránh tràn RAM.

3. **Tài khoản Migration tách biệt khỏi Web Runtime**:
   - `migration_mysql_config()` bắt buộc `MIGRATION_DB_USER` ≠ `DB_USER` khi `APP_ENV=production`. Tài khoản web runtime (`petcare_app`) chỉ cần quyền DML (`SELECT, INSERT, UPDATE, DELETE`), không giữ quyền DDL (`ALTER, DROP`) trong container `web`, `email-worker`, `export-worker`.

4. **Reverse Proxy & Host/Scheme Headers**:
   - Khi đặt sau đúng 1 reverse proxy HTTPS (`Nginx` / `Caddy` / Cloud ALB), bật `TRUST_PROXY=1` để kích hoạt `ProxyFix(x_for=1, x_proto=1)`.
   - Proxy **bắt buộc** phải ghi đè `X-Forwarded-For`, `X-Forwarded-Proto` và lọc `Host` header chuẩn domain staging trước khi chuyển tiếp tới Gunicorn.

5. **Lưu trữ ảnh & Upload bền vững**:
   - **1 instance staging**: có thể dùng Docker persistent volume (`/app/instance`) hoặc disk mount bền vững (`petcare_manager_uploads`), đảm bảo quyền sở hữu cho UID/GID user `petcare`.
   - **Multi-instance staging**: đặt `MEDIA_STORAGE_BACKEND=s3` và `TENANT_EXPORT_STORAGE_BACKEND=s3` với bucket **private, chặn public access, mã hóa SSE-AES256**, endpoint HTTPS; toàn bộ ảnh vẫn đi qua Python route kiểm tra session & tenant, không dùng public ACL hay CDN bypass. Lưu ý `scripts/petcare_backup.py` chỉ sao lưu ảnh local và từ chối chạy khi `MEDIA_STORAGE_BACKEND=s3` (trên S3 phải bật bucket versioning + cross-region/replication backup riêng).

---

## 2. Danh mục kiểm tra Staging Checklist (Theo tầng)

| Hạng mục | Yêu cầu cấu hình bắt buộc | Trạng thái thiết kế |
| :--- | :--- | :--- |
| **Secrets & Keys** | `SECRET_KEY` (32+ bytes random), `DB_PASSWORD`, `TENANT_EXPORT_JOB_KEY` (Fernet), `MAIL_OUTBOX_KEY` (Fernet), `OPS_METRICS_TOKEN` (32+ chars nếu bật) lưu trong secret store; không dùng giá trị mặc định trong `.env.example` | Đã có fail-closed validation trong code |
| **Database & Migration** | MySQL 8.0.16+ (`utf8mb4_unicode_ci`), tên DB `petcare_shop_staging` (không kết thúc `_dev`/`_test`), `DB_SSL_CA` mount read-only, job chạy `python -m petcare.database.initialize` bằng `MIGRATION_DB_*` trước khi roll web mới | Đã kiểm chứng Fresh & Upgrade từ AI-3.4 |
| **HTTPS / Cookie / CSRF** | TLS terminated ở proxy; `PUBLIC_BASE_URL=https://...`; `COOKIE_SECURE=1`; `Session` là `HttpOnly + SameSite=Lax`; CSRF active + `Cache-Control: private, no-store` trên các route đăng nhập/checkout | Đã kiểm chứng trên `app_configuration.py` & `app_hooks.py` |
| **CSP & Security Headers** | `default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; object-src 'none'`; `X-Content-Type-Options: nosniff`; `X-Frame-Options: DENY` | Đã bật mặc định |
| **Rate Limiting & Abuse** | Cấp MySQL `request_throttle` & `login_throttle` cho Login Staff/Customer, AI Assistant (`/assistant/chat`, `/shop/ai-assistant/chat`), Vision (`/pets/find-similar`, `/shop/image-search`), Upload catalog, Checkout, Order lookup, Export & Email reset | Đã triển khai & test |
| **Logging & Error Pages** | Error handlers trả trang lỗi thân thiện 403/404/413/500/503; không trả stack trace hay biến môi trường ra HTTP response | Đã có templates `errors/*.html` |
| **Mail & Export Workers** | 2 process/container riêng (`petcare.services.mail_worker`, `petcare.services.tenant_export_worker_cli`); SMTP dùng `MAIL_STARTTLS=1` | Sẵn sàng trong `docker-compose.yml` |
| **Health & Monitoring** | Load balancer/orchestrator probe `/healthz` (liveness) & `/readyz` (MySQL contract readiness); giám sát `/workersz` bằng alert | Đã kiểm chứng HTTP `200` |

---

## 3. Tài nguyên Hạ tầng Tối thiểu cho Demo / Staging Site

*(Độc lập nhà cung cấp cloud/VPS)*:

- **App + Workers Node**: **2 vCPU · 2 GB RAM** (tối thiểu khuyến nghị **2 vCPU · 4 GB RAM** nếu vừa chạy `web`, `email-worker`, `export-worker` vừa suy luận `yolox_nano.onnx` + `mobilenetv2-12-features.onnx` trên CPU). Dung lượng image & ONNX models < 2 GB; cộng thêm persistent volume tối thiểu 10 GB cho `/app/instance`.
- **MySQL 8 Managed / Server**: **1–2 vCPU · 2 GB RAM**, bật TLS, `max_connections >= 60` (`DB_POOL_SIZE=5` × tổng số web/worker processes), lịch snapshot tự động hàng ngày (retention ≥ 7 ngày) + test restore định kỳ.
- **Reverse Proxy**: TLS 1.2/1.3 (Let's Encrypt hoặc ACM), giới hạn `client_max_body_size >= 8M` (khớp `MAX_CONTENT_LENGTH = 7 MB` của Flask).

---

## 4. Trình tự Triển khai Staging An toàn (Khi được phê duyệt)

1. **Chuẩn bị hạ tầng**: Provision DB `petcare_shop_staging` (user `petcare_app` + `petcare_migrator` tách quyền), CA TLS bundle (`DB_SSL_CA`), persistent volume hoặc private S3 bucket, SMTP sandbox/staging, và nạp secrets vào secret manager.
2. **Kiểm tra cấu hình dry-run**: Tạo app context bằng cấu hình staging (với `APP_ENV=production`) để `validate_app_configuration` thông qua không báo lỗi thiếu biến.
3. **Backup & Migration một lần (One-off Job)**: Snapshot DB (nếu đã có dữ liệu) → chạy container migration với `MIGRATION_DB_*`:
   `python -m petcare.database.initialize`
4. **Khởi động Stack**: Deploy `web`, `email-worker`, `export-worker` và proxy HTTPS → kiểm tra `/healthz` (`200`), `/readyz` (`200`), `/workersz` (`200`).
5. **Smoke Staging trên dữ liệu thử nghiệm riêng**: Chạy kiểm tra đăng nhập admin, `/shop`, AI Vision upload và luồng đặt đơn + thu COD thử nghiệm trên cửa hàng staging (dữ liệu test riêng, tuyệt đối không dùng dữ liệu khách thật), rồi đối chiếu log không có 5xx.
6. **Quy trình Rollback**: Nếu migration hoặc bản build lỗi, giữ nguyên DB snapshot trước nâng cấp, chuyển proxy/image về tag trước đó và khôi phục bản snapshot tương ứng nếu có thay đổi trạng thái giao dịch.

