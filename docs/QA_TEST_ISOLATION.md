# QA test isolation

## Nguyên tắc

- Mặc định `DB_NAME` có thể trỏ `petcare_shop_dev`; không chạy integration/browser tests khi chưa đặt rõ `DB_NAME` và `PETCARE_TEST_DB_NAME` về cùng một schema kết thúc bằng `_test`.
- Không chạy fixture trên development, production, `petcare_shop_test` dùng chung hoặc bất kỳ schema test tồn lưu nào.
- Dùng MySQL 8.4 mới với schema riêng. `compose.qa-test.yml` không mount database volume; dữ liệu DB nằm trong tmpfs và biến mất khi container dừng.
- Ảnh, export và browser artifacts đặt trong thư mục tạm riêng. Tắt AI provider, Vision, SMTP và S3 trong test.
- Test runner phải có quyền DDL trên đúng schema test vì `initialize_database()` chạy migrations. Không cần cấp `CREATE DATABASE` cho app/test user nếu schema đã được MySQL container tạo lúc khởi động.

## Môi trường đã xác minh trong Phase 5.1.1

- Docker Desktop + image `mysql:8.4`.
- Schema `petcare_phase511_test`, app user chỉ có grant trên schema này.
- MySQL chỉ publish loopback host port; database files ở tmpfs; Flask và Chromium chạy trên máy local.
- Playwright dùng storage `local` và thư mục artifacts owner-only trong `/tmp`.
- Không có thông tin credential thật trong docs hoặc repository. Password test được sinh trong shell, không ghi vào `.env` của ứng dụng hoặc command log.

## Cách dựng môi trường local

Chạy từ root repo trong một shell riêng. Dùng project name riêng để lệnh cleanup chỉ nhắm service test do phiên này tạo:

```sh
export PETCARE_QA_PROJECT="petcare-qa-$(id -u)-$$"
export PETCARE_QA_DATABASE="petcare_qa_test"
export PETCARE_QA_USER="petcare_qa"
export PETCARE_QA_MYSQL_PORT="33307"
export PETCARE_QA_MYSQL_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PETCARE_QA_MYSQL_ROOT_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose -p "$PETCARE_QA_PROJECT" -f compose.qa-test.yml up -d --wait mysql

export APP_ENV=test
export DB_HOST=127.0.0.1
export DB_PORT="$PETCARE_QA_MYSQL_PORT"
export DB_NAME="$PETCARE_QA_DATABASE"
export DB_USER="$PETCARE_QA_USER"
export DB_PASSWORD="$PETCARE_QA_MYSQL_PASSWORD"
export PETCARE_TEST_DB_NAME="$PETCARE_QA_DATABASE"
export APP_PORT=5061
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export COOKIE_SECURE=0
export LAN_ACCESS_ENABLED=0
export AI_API_BASE_URL=
export AI_API_KEY=
export AI_MODEL=
export AI_VISION_ENABLED=0
export MAIL_HOST=
export MAIL_USERNAME=
export MAIL_PASSWORD=
export MAIL_FROM=
export MEDIA_STORAGE_BACKEND=local
export TENANT_EXPORT_STORAGE_BACKEND=local

export QA_RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/petcare-qa.XXXXXX")"
chmod 700 "$QA_RUN_DIR"
mkdir -p "$QA_RUN_DIR/pets" "$QA_RUN_DIR/products" "$QA_RUN_DIR/exports" "$QA_RUN_DIR/browser"
export PET_IMAGE_DIR="$QA_RUN_DIR/pets"
export PRODUCT_IMAGE_DIR="$QA_RUN_DIR/products"
export TENANT_EXPORT_DIR="$QA_RUN_DIR/exports"
export PLAYWRIGHT_ARTIFACT_DIR="$QA_RUN_DIR/browser"
```

`33307` hoặc `5061` có thể đang được dùng. Nếu vậy, chọn port loopback còn trống và dùng cùng giá trị trong suốt phiên. Nếu Compose báo port collision thì dừng; không đổi sang kết nối DB app đang dùng.

## Lệnh kiểm tra

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests/unit -v
.venv/bin/python -m unittest discover -s tests/web -v
.venv/bin/python -m unittest discover -s tests/integration -v
.venv/bin/python -m pytest -q \
  tests/unit/test_assistant_sales_insight.py \
  tests/integration/test_mysql_web.py::MySQLWebIntegrationTests::test_assistant_top_products_uses_current_tenant_sales_report
node --test tests/js/*.test.cjs
.venv/bin/python scripts/browser_smoke/run_smoke.py
```

Quality gates của repo:

```sh
bandit -q -r petcare scripts main.py run.py wsgi.py \
  -x petcare/templates,petcare/static -b .security/bandit-baseline.json
pip-audit -r requirements.lock
pip-audit -r requirements-browser.lock
pip check
python -m compileall -q petcare scripts tests
docker compose config --quiet
git diff --check
```

Để giữ test artifacts, sao chép đường dẫn `QA_RUN_DIR` ra terminal riêng trước khi cleanup. Mỗi browser test ghi screenshot/trace; runner ghi `results.json`, `browser-diagnostics.json` và `runtime.log` trong thư mục artifact.

## Cleanup an toàn

Sau khi review log và artifacts:

```sh
docker compose -p "$PETCARE_QA_PROJECT" -f compose.qa-test.yml down
```

Compose QA không có named volume hoặc bind mount cho database; `down` chỉ dừng/xóa service thuộc project name riêng và network của nó. Giữ hoặc xóa riêng `QA_RUN_DIR` sau khi xác nhận đó đúng là thư mục vừa tạo bởi `mktemp`; không dùng wildcard hoặc lệnh cleanup lên `instance/`, thư mục user hoặc Docker project khác.

Test fixtures dùng UUID/prefix riêng, giới hạn query theo tenant và cleanup đúng row sở hữu. Full run Phase 5.1.1 kiểm tra lại orphan audit events và prefix browser/sales; tất cả count hậu kiểm bằng 0.

## Khi dùng MySQL do admin provision

Nếu không dùng Docker và tài khoản hiện tại không được phép tạo schema, **không** tăng quyền tài khoản app hiện hữu. Gửi DBA yêu cầu provision riêng; không chạy lệnh dưới đây bằng app account. DBA chọn host pattern đúng với máy test và đặt password ngẫu nhiên ở secret store:

```sql
CREATE DATABASE `petcare_qa_test`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'petcare_qa'@'127.0.0.1' IDENTIFIED BY '<random-secret-from-secret-store>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `petcare_qa_test`.* TO 'petcare_qa'@'127.0.0.1';
```

Runtime test user chỉ được grant trên schema QA vừa tạo; không grant global `CREATE`, `CREATE USER`, `DROP DATABASE`, `FILE`, `PROCESS`, `SUPER` hoặc `GRANT OPTION`. MySQL yêu cầu `CREATE`/`INSERT` đi cùng thao tác `ALTER TABLE`, và `REFERENCES` trên bảng cha khi tạo foreign key; xem [MySQL 8.4 privileges](https://dev.mysql.com/doc/refman/8.4/en/privileges-provided.html). Admin provisioning cần quyền account/schema tương ứng; việc tạo user là quyền quản trị riêng, không thuộc quyền test runner.

Sau provision, đặt `DB_NAME=PETCARE_TEST_DB_NAME=petcare_qa_test`, cấu hình endpoint/user/password từ secret store, xác nhận `SELECT DATABASE()` là schema test, rồi mới chạy test. Không tự chạy `CREATE DATABASE` bằng app credentials khi bị từ chối.
