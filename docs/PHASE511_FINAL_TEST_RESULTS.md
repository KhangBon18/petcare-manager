# Phase 5.1.1 — Kết quả kiểm thử cuối

Ngày: 2026-11-10. Trạng thái được đo trên checkout hiện có, trong test-only MySQL 8.4 Compose service và storage tạm. Không phải kết quả GitHub-hosted CI.

## Môi trường

- `compose.qa-test.yml`, MySQL `8.4`, schema `petcare_phase511_test`, user bị giới hạn trong schema đó.
- DB dùng tmpfs, không dùng volume của MySQL dev/test tồn lưu. App test dùng `DB_NAME == PETCARE_TEST_DB_NAME`.
- Flask, media và export local; provider AI/Vision, SMTP và S3 tắt.
- Browser server chờ `/readyz=200`; Chromium chạy trên loopback. Ảnh/trace/log ở `/tmp/petcare-phase511-regression-1w_1y7zt/artifacts/`.

## Kết quả

| Suite/gate | Kết quả | Bằng chứng/lệnh |
|---|---|---|
| Python full regression | **380/380 PASS**, 0 failure/error/skip, chạy 2 lần | `.venv/bin/python -m unittest discover -s tests -v`; `python-regression-final-1.log` (43.662s), `python-regression-final-2.log` (39.691s). |
| Unit | **228/228 PASS** | `.venv/bin/python -m unittest discover -s tests/unit -v`. |
| Web/route | **86/86 PASS** | `.venv/bin/python -m unittest discover -s tests/web -v`. |
| MySQL integration | **66/66 PASS** | `.venv/bin/python -m unittest discover -s tests/integration -v` trên Compose schema tạm. |
| AI assistant slice | **8 passed, 13 subtests passed** | Pytest của `test_assistant_sales_insight.py` và MySQL `test_assistant_top_products_uses_current_tenant_sales_report`. |
| JavaScript | **31/31 PASS**, 0 skip | `node --test tests/js/*.test.cjs`. |
| Playwright full suite | **11/11 PASS, 0 skip**, hai lần | `scripts/browser_smoke/run_smoke.py`; logs `playwright-regression-final-1.log`, `playwright-regression-final-2.log`. |
| Playwright diagnostics | Không page exception, failed request hay HTTP error bất ngờ | Mỗi lần có 11 diagnostics. Một console entry là 403 dự kiến khi staff bị chặn `/users/`; `favicon.ico` 404 nếu xuất hiện nằm trong allowlist. `/readyz=200`. |
| Bandit CI gate | **PASS**, exit 0 | Lệnh chính xác từ `.github/workflows/ci.yml`; còn B608 `nosec encountered` warnings hiện có trong baseline, không finding làm gate fail. |
| Dependency audits | **PASS** | `pip-audit -r requirements.lock`, `pip-audit -r requirements-browser.lock`: không có known vulnerabilities; `pip check`: không có broken requirements. |
| Compile/package/container | **PASS** | `compileall`, `docker compose config --quiet`, `docker build --tag petcare-manager-web:phase511-regression .`. |
| Diff/style | **PASS** | `git diff --check`; docs/compose newline và trailing whitespace được kiểm tra thêm trước handoff. |

AI Playwright screenshot/trace và các log đầy đủ không được đưa vào docs/repository; chúng ở thư mục `/tmp/petcare-phase511-regression-1w_1y7zt/artifacts/`, quyền thư mục giới hạn cho user hiện tại. Sau khi kiểm tra artifacts, test Compose được dừng; không giữ test credential trong repository.

## Fixture cleanup hậu kiểm

Trên schema test-only sau Python/browser runs, count bằng 0 cho:

- Audit events orphan của customer, product, pet, invoice và refund.
- Sales products/customers/invoices/pets được test tạo.
- Browser product `PW-%`, customer `Browser refund QA %` và invoice note `Playwright refund fixture %`.

Hai audit event orphan (một product.created, một pet.created) đã được quan sát ở lượt chạy chẩn đoán trước khi hoàn thiện teardown. Cleanup tương ứng được bổ sung; lượt final cho toàn bộ các count trên bằng 0.

## So sánh với kết quả Phase 5.1 ban đầu

Trước recovery, run trên QA schema có sẵn là 380 tests với 2 failures/15 errors; browser 11 tests có 6 failures/1 error trước khi chạy selector đã sửa. Khi dùng DB/storage mới, full Python pass lặp lại, và Playwright pass lặp lại. Các test context thiếu tenant, assertion count cứng, seed lookup không tenant-scope và teardown audit thiếu đã được sửa. Không có business-logic regression nào được tái hiện.

## Phạm vi chưa kiểm thử

- GitHub-hosted Actions và Trivy chưa chạy.
- `petcare_shop_dev` readiness vẫn chưa đạt; DB này không được kết nối/sửa trong lượt này.
- Provider AI thật, Vision, SMTP, S3, chi phí/latency provider không được kiểm tra.
- Không chạy production acceptance hoặc load/concurrency benchmark ngoài các integration test sẵn có.
