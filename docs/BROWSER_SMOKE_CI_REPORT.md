# Báo cáo Browser Smoke và CI — Phase 3.5

Ngày chạy local: 2026-11-09. Trạng thái áp dụng cho checkout hiện tại và các thay đổi chưa commit; GitHub Actions hosted **chưa được chạy**.

## Kết quả thực thi thật

`python scripts/browser_smoke/run_smoke.py` đã khởi chạy Flask bằng `run.py` trên cổng localhost, chờ `GET /readyz=200`, mở Chromium headless và chạy **3/3 tests PASS trong 7.844 giây** trên MySQL QA `petcare_phase3_browser_test` (MySQL 8.4.11). Database và storage đều tách khỏi `petcare_shop_dev`; app tắt SMTP, AI provider, S3 và metrics token trong test runtime.

Artifact của lần chạy cuối:

- Result: `/var/folders/h8/kq90jvq96b33gb79fnxcqjgh0000gn/T/petcare-phase35-browser-final-i5ka8nbh/results.json`
- Browser diagnostics: `/var/folders/h8/kq90jvq96b33gb79fnxcqjgh0000gn/T/petcare-phase35-browser-final-i5ka8nbh/browser-diagnostics.json`
- Screenshots: `mobile-pos-cart.png`, `refund-after-partial.png`, `refund-after-full.png` và một screenshot cuối mỗi test trong cùng thư mục.
- Trace zip: `test_admin_navigation_modules_responsive_pos_and_accessibility-trace.zip`, `test_browser_refund_confirmation_validation_idempotency_and_persistence-trace.zip`, `test_staff_role_restriction_and_allowed_customer_access-trace.zip`.
- Runtime log: `runtime.log`; artifacts và thư mục cha được tạo với quyền hạn chế ở máy local.

## Phạm vi và bằng chứng

| Test | Thực hiện | Kết quả quan sát |
|---|---|---|
| `test_admin_navigation_modules_responsive_pos_and_accessibility` | Đăng nhập admin; mở dashboard, customers, pets, products, invoices, purchasing, reports; kiểm heading, main landmark, tên button/control, Tab chuyển focus; tablet nav ở 820×1180; POS ở 390×844, thêm một mặt hàng và mở cart anchor. | PASS. Các routes trả 200; cart count/estimate khớp DOM; không có JS exception, failed request hoặc HTTP error ngoài allowlist. Đây là navigation smoke, không phải CRUD E2E mọi module hay WCAG audit. |
| `test_staff_role_restriction_and_allowed_customer_access` | Đăng nhập staff; mở `/customers/`, sau đó thử trực tiếp `/users/`. | PASS. Customers 200; `/users/` 403. Browser console ghi một dòng lỗi do response 403 có chủ đích; test xác nhận đúng request/status trước khi cho phép. |
| `test_browser_refund_confirmation_validation_idempotency_and_persistence` | Tạo customer/product/invoice tổng hợp bằng service trong QA, thanh toán invoice trong schema test, rồi submit refund bằng giao diện. Dismiss và accept native `dialog`; đọc invoice/refund/stock tables sau mỗi bước. | PASS. Dismiss không gửi POST và không đổi DB. Quantity 0 và over-refund bị từ chối, không ghi ledger. Partial refund ghi một lần; replay cùng request key/payload không thêm refund; sau đó hai dòng hóa đơn được hoàn đủ qua các request riêng. Invoice vẫn `paid`; quantity, tiền, stock movements và tồn khớp DB. Không gọi cổng thanh toán. |

Sau test, query chỉ đọc xác nhận không còn invoice có note `Playwright refund fixture %`, customer `Browser refund QA %` hay product code `PW-%` trong browser QA schema. HTTP probe trên Flask process QA thật: `/healthz=200`, `/readyz=200`. `petcare_shop_dev` không được test runner sử dụng.

Suite lưu request method/path/status và request failures, không lưu cookie, headers hay request body. Không có failed request/JS exception; expected staff 403 là trường hợp duy nhất tạo console error. Test harness dùng timeout/assertion Playwright và bounded readiness polling, không có arbitrary browser sleep.

## CI wiring

`.github/workflows/ci.yml` hiện có job `browser-smoke` riêng:

- MySQL 8.4 service dùng schema `petcare_ci_browser_test` và test-only credentials.
- Cài runtime từ `requirements.txt` với `requirements.lock`, cộng `requirements-browser.lock` (Playwright 1.64.1 và dependencies exact pin).
- Audit browser lock bằng `pip-audit`, xác nhận `pip check`, cài Chromium, rồi runner khởi tạo/seed đúng schema `_test` và tự chờ readiness.
- Test bắt buộc `DB_NAME == PETCARE_TEST_DB_NAME` và tên schema khớp `*_test`; thư mục screenshot/trace/log ở runner temp.
- Upload artifact qua `actions/upload-artifact` đã pin SHA, giữ 7 ngày kể cả khi test fail.

> **Local verification:** 3/3 browser tests PASS; workflow YAML parse PASS. **Hosted CI verification:** NOT TESTED trong lượt này; cần push/PR để quan sát Actions result và uploaded artifacts. Không suy luận hosted runner pass từ local run.

Security gate exact CI command cũng chạy lại và PASS sau khi browser harness loại bỏ SQL dynamic placeholder strings, dùng `http.client` cho readiness probe, thay literal `/tmp` bằng `tempfile.gettempdir()`, và giới hạn suppression B404/B603 vào import/call subprocess của fixed `sys.executable` + repository `run.py` (không shell, không input từ request). Suppression không áp dụng tới business code.

Runtime + browser dependency command cũng được cài vào một venv tạm sạch bằng `pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock`; `pip check` sạch và `python -m playwright --version` trả 1.64.1.

## Khoảng trống

- Hosted GitHub Actions, Trivy, full axe/WAVE, screen reader, contrast, zoom 200% và toàn bộ responsive route matrix chưa kiểm chứng.
- Browser smoke chưa chạy CRUD end-to-end cho mỗi customer/pet/catalog/purchase/report flow; backend MySQL suites tiếp tục là bằng chứng cho các transaction đó.
- Không gửi SMTP, AI/AI Vision hoặc S3 request thật; không chạy worker daemon hoặc payment gateway.

Chi tiết test counts và trạng thái DB dev ở [TEST_MATRIX.md](TEST_MATRIX.md), [TEST_COVERAGE_GAPS.md](TEST_COVERAGE_GAPS.md) và [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md).
