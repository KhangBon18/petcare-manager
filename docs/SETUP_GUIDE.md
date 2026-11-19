# Hướng dẫn Cài đặt & Khởi chạy Reproducible (`SETUP_GUIDE.md`)

Tài liệu này mô tả đầy đủ quy trình cài đặt lại từ đầu trên máy mới cho phiên bản tích hợp hoàn chỉnh **PetCare Manager** (Admin/Staff Workspace Option A + AI Vision 4.0 ONNX + Customer Storefront `/shop`). Mọi lệnh bên dưới đều đã được kiểm chứng thực tế trên codebase tại nhánh `solo/khang-petcare` / `feature/demo-staging-readiness`.

> **Nguyên tắc an toàn**: Không dùng tài khoản MySQL `root` cho ứng dụng runtime, không nạp dữ liệu demo vào database sản xuất hoặc database làm việc thật, và **không bao giờ commit `.env` hay mật khẩu lên Git**.

---

## 1. Yêu cầu hệ thống & thành phần bắt buộc

| Thành phần | Phiên bản / Yêu cầu tối thiểu | Mục đích |
| :--- | :--- | :--- |
| **Python** | `3.11+` (đã CI verify trên `3.11`, `3.12`, `3.13`) | Backend Flask, ONNX Vision, MySQL connector |
| **MySQL Server** | `8.0.16+` (`InnoDB`, `utf8mb4_unicode_ci`) | Lưu trữ dữ liệu multi-tenant & CHECK/FK constraints |
| **ONNX Vision Models** | `yolox_nano.onnx`, `mobilenetv2-12-features.onnx`, `mobilenetv2-12.onnx` | Nằm sẵn tại `petcare/vision/models/` (chạy CPU offline) |
| **Node.js (tùy chọn QA)** | `18+` | Chỉ phục vụ `node --test tests/js/*.test.cjs` & `tests/a11y` (app không cần bước build JS) |
| **Docker Engine / Compose** | Tùy chọn | Chạy MySQL hoặc stack container (`Dockerfile`, `docker-compose.yml`) |

Kiểm tra nhanh model ONNX cục bộ không bị thiếu sau khi clone:

```sh
ls -lh petcare/vision/models/mobilenetv2-12-features.onnx \
       petcare/vision/models/mobilenetv2-12.onnx \
       petcare/vision/models/yolox_nano.onnx
```

---

## 2. Cài đặt từ đầu (Bare-Metal Local Setup)

### Bước 1: Clone & cài Python dependencies

```sh
git clone https://github.com/KhangBon18/petcare-manager.git
cd petcare-manager
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c requirements.lock
```

*(Tùy chọn cho Playwright E2E / Visual QA)*:
```sh
python -m pip install -r requirements-browser.lock
python -m playwright install chromium
npm ci --prefix tests/a11y
```

### Bước 2: Cấu hình biến môi trường (`.env`)

Sao chép mẫu cấu hình an toàn:

```sh
cp .env.example .env
```

Tạo `SECRET_KEY`, `TENANT_EXPORT_JOB_KEY` và `MAIL_OUTBOX_KEY` ngẫu nhiên (chỉ ghi vào `.env`, **không đưa vào repo**):

```sh
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Các biến quan trọng khi chạy demo cục bộ trên schema `_test` cô lập:
- `APP_ENV=test` (khi chạy `demo_staging_setup.py` với DB hậu tố `_test`; hoặc `development` khi chạy cùng `*_dev`)
- `COOKIE_SECURE=0` (bắt buộc `0` nếu truy cập qua `http://127.0.0.1:5055` không HTTPS)
- `DB_HOST=127.0.0.1`, `DB_PORT=3306` (hoặc port Docker MySQL riêng, ví dụ `33339`), `DB_NAME=petcare_demo_stage_test`
- `PET_IMAGE_DIR`, `PRODUCT_IMAGE_DIR`, `TENANT_EXPORT_DIR`: trỏ tới thư mục tạm cô lập có quyền ghi (ví dụ `$TMPDIR/petcare-demo/pets`, hoặc `instance/pet-images` khi chạy mặc định).

### Bước 3: Khởi động MySQL 8 & tạo Database + User quyền tối thiểu

Nếu dùng Docker cho MySQL 8 cục bộ cô lập:

```sh
docker run -d --name petcare-mysql8-local \
  -e MYSQL_ROOT_PASSWORD='<local-root-password>' \
  -p 127.0.0.1:3306:3306 \
  mysql:8.4
```

Tạo schema và user riêng (UTF8MB4):

```sql
CREATE DATABASE petcare_demo_stage_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'petcare_app'@'127.0.0.1' IDENTIFIED BY '<local-app-password>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP ON petcare_demo_stage_test.* TO 'petcare_app'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### Bước 4: Khởi tạo Schema (31 bảng, 7 migrations) & Nạp Dữ liệu Demo Cô lập

Chạy initializer idempotent:

```sh
python -m petcare.database.initialize
```

Nạp đầy đủ dữ liệu demo cho cả 3 vai trò (**Admin**, **Staff**, **Customer Storefront**), 22 sản phẩm, 74 thú cưng, 8 hóa đơn paid, 2 đơn online (`pending` COD + `ready_completed` COD) và 37 `stock_movements`:

```sh
D_TMP=$(python -c "import tempfile; print(tempfile.gettempdir())")
PETCARE_DEMO_MODE=1 APP_ENV=test \
DB_NAME=petcare_demo_stage_test \
PET_IMAGE_DIR="$D_TMP/petcare-demo-pets" \
PRODUCT_IMAGE_DIR="$D_TMP/petcare-demo-prods" \
TENANT_EXPORT_DIR="$D_TMP/petcare-demo-exports" \
PETCARE_DEMO_ADMIN_PASSWORD='<mật-khẩu-admin-16+-ký-tự>' \
PETCARE_DEMO_STAFF_PASSWORD='<mật-khẩu-staff-16+-ký-tự-khác>' \
PETCARE_DEMO_CUSTOMER_PASSWORD='<mật-khẩu-customer-16+-ký-tự-khác>' \
python scripts/demo_staging_setup.py --reset-disposable --json
```

> **Quy trình Reset Demo An toàn**: Lệnh `--reset-disposable` **chỉ** cho phép reset DB có tên kết thúc bằng `*_test` (sẽ fail-closed nếu trỏ vào `_dev` hoặc `production`). Để chạy lại nhiều lần không xóa dữ liệu đang thử, bỏ cờ `--reset-disposable`.

### Bước 5: Khởi chạy Ứng dụng Flask & Truy cập

```sh
PETCARE_DEMO_MODE=1 APP_ENV=test COOKIE_SECURE=0 \
DB_NAME=petcare_demo_stage_test \
PET_IMAGE_DIR="$D_TMP/petcare-demo-pets" \
PRODUCT_IMAGE_DIR="$D_TMP/petcare-demo-prods" \
TENANT_EXPORT_DIR="$D_TMP/petcare-demo-exports" \
python run.py
```

Các URL kiểm tra & truy cập:
- **Health check web process**: `http://127.0.0.1:5055/healthz` → `200 {"status": "ok"}`
- **Readiness check MySQL + schema contract**: `http://127.0.0.1:5055/readyz` → `200 {"status": "ready"}`
- **Internal Admin/Staff Workspace**: `http://127.0.0.1:5055/login` (tài khoản `admin` hoặc `staff1`)
- **Customer Storefront (`/shop`)**: `http://127.0.0.1:5055/shop` (tài khoản khách `demo.customer@example.invalid`)
- **AI Vision cục bộ**: `http://127.0.0.1:5055/pets/find-similar` (nội bộ) hoặc `http://127.0.0.1:5055/shop/image-search` (công khai)

---

## 3. Khởi chạy bằng Docker Compose (Tùy chọn)

```sh
docker compose config --quiet
docker compose build
docker compose up -d mysql
# Chờ mysql healthy rồi chạy migration một lần:
docker compose run --rm web python -m petcare.database.initialize
docker compose up -d web email-worker export-worker
```

Kiểm tra trạng thái các container và `/readyz`:
- `http://127.0.0.1:5055/healthz`
- `http://127.0.0.1:5055/readyz`
- `http://127.0.0.1:5055/workersz` (chỉ `ready` khi cả `email-worker` và `export-worker` hoạt động trong vòng 90 giây).

---

## 4. Quyền thư mục Media & Upload

- Thư mục mặc định: `instance/pet-images`, `instance/product-images`, `instance/tenant-exports`. Trong Dockerfile, thư mục `/app/instance` thuộc sở hữu user không đặc quyền `petcare:petcare`.
- Khi dùng thư mục tùy chỉnh qua `PET_IMAGE_DIR` / `PRODUCT_IMAGE_DIR` / `TENANT_EXPORT_DIR`, tài khoản OS chạy Flask phải có quyền `rwx` trên thư mục đó. Ảnh được phục vụ qua route Python có kiểm tra session/tenant (`pets.photo`, `storefront.public_pet_photo`), **không** expose trực tiếp ra static folder công khai.

---

## 5. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `/readyz` trả HTTP `503` | Thiếu bảng hoặc migration mới (`pet_reference_photos_v1`, `storefront_orders_v1_1`) | Chạy lại `python -m petcare.database.initialize` |
| Lỗi `DEMO_MODE` hoặc `16-1024 characters` khi seed | Thiếu `PETCARE_DEMO_MODE=1` hoặc 3 mật khẩu Demo chưa đủ 16 ký tự / trùng nhau | Truyền 3 biến `PETCARE_DEMO_*_PASSWORD` riêng biệt dài 16+ ký tự |
| `403` / CSRF lỗi trên HTTP `127.0.0.1` | Để `APP_ENV=production` hoặc `COOKIE_SECURE=1` khi chạy HTTP thường | Đặt `APP_ENV=test` (hoặc `development`) và `COOKIE_SECURE=0` trên loopback |
| Port `5000` bị macOS AirPlay chiếm | AirPlay Receiver trên macOS | Giữ nguyên cổng mặc định `APP_PORT=5055` |

