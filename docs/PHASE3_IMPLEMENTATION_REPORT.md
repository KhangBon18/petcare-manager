# Báo cáo triển khai Phase 3

Ngày: 2026-11-09
Trạng thái: **đã hoàn tất phần cải tiến an toàn trong phạm vi Phase 3; chưa triển khai migration lên DB dev và chưa production-ready**

## Tóm tắt điều hành

Phase 3 cải thiện độ tin cậy của migration tiền, kiểm thử thật refund trên MySQL, hoàn thiện UX cho tablet navigation/mobile POS và làm rõ trạng thái tenant export. Bộ Python tăng từ 366 lên **369/369 PASS**; JavaScript từ 27 lên **28/28 PASS**. Browser thật xác minh account profile, role access, export job, và responsive tại ba kích thước lấy mẫu.

Migration readiness đã được rehearsal trên clone tách biệt: schema trước 20 bảng/729 dòng/1 marker, sau 26 bảng/4 marker và `/readyz` 200. Một drift check constraint legacy được sửa trong migration code và kiểm bằng MySQL. `petcare_shop_dev` không bị ghi: vẫn 20 bảng, readiness 503. Việc áp dụng migration lên DB dev dừng tại ranh giới phê duyệt.

Không xác nhận P0. Không có chuyển tiền, gửi email, gọi dịch vụ AI trả phí hoặc ghi vào database dev/production. Refund browser submit, accessibility đầy đủ, network request audit, SMTP, AI/Vision thật và S3 vẫn chưa được kiểm.

## An toàn và cô lập thay đổi

- Working tree đã có nhiều thay đổi và file untracked trước các chỉnh sửa Phase 3. Không xóa hay khôi phục chúng, không commit.
- Tạo checkpoint bền vững trước khi sửa tại `/Users/heisenbon/Documents/Codex/petcare-phase3-checkpoint-20261109` gồm HEAD, status, tracked/index patch, gói file untracked và SHA-256 manifest.
- Python/MySQL test dùng schema `petcare_phase3_automated_test`; browser dùng `petcare_phase3_browser_test`; migration rehearsal dùng `petcare_phase3_dev_clone`. Media/export QA đặt dưới `/tmp/petcare-phase3`.
- Không chạy initializer/seed/DDL/DML trên `petcare_shop_dev`. Không sao chép credentials vào tài liệu.

## Cải tiến và lỗi đã xử lý

| ID | Mức độ | Kết quả | Thay đổi và bằng chứng |
|---|---|---|---|
| DB-03 | P1 trong đường migration; đã sửa trên code/clone | FIXED, cần duyệt trước khi áp dụng dev | Constraint `chk_products_price`, `chk_pets_price`, `chk_invoice_item_total` có thể còn biểu thức `_vnd` vì `CREATE TABLE IF NOT EXISTS` không sửa constraint hiện có. `initialize.py` nay đọc biểu thức từ `information_schema`, kiểm toàn bộ hàng hiện có trước ALTER, thay đúng ba named checks bằng invariant trên cột Decimal, và no-op khi đã canonical. Clone có 0 hàng vi phạm; initializer lặp lại an toàn; MySQL từ chối các update vi phạm với errno 3819. |
| QA-REFUND | P1/P2 coverage gap; regression đã thêm | VERIFIED qua route + MySQL | Route integration kiểm partial/full, replay key, từ chối over-refund, kiểm tồn/ledger và rollback khi audit event phát sinh lỗi. Không kết nối payment gateway. Browser submit vẫn `NOT TESTED`. |
| UX-04 | P3 | FIXED | Tablet nav có scrollbar styling và fade ở mép phải trong 681–980 px. Browser 820×1180 cho thấy fade, Reports mở được; document không tràn ngang. |
| UX-05 | P3 | FIXED | POS mobile có cart preview với số món/tổng và link tới `#pos-order`. Browser 390×844 xác nhận 1 món/55.000 VND và không tràn ngang; không submit invoice. |
| UX-06 | P2 | FIXED | Export job heading thay theo pending/processing/ready/failed/expired. Regression test kiểm năm trạng thái và English `Export ready`; browser job thật hiển thị ready/download. |

Thay đổi code tập trung ở `petcare/database/initialize.py`, POS template/JS/CSS, export template/i18n và regression tests tương ứng. Không đổi framework hoặc API contract. Các thay đổi khác đang có trong working tree được giữ nguyên; chúng không được xem là Phase 3 implementation nếu không được nêu ở đây.

## File thay đổi trong phạm vi Phase 3

- Code/UI: `petcare/database/initialize.py`, `petcare/templates/invoices/form.html`, `petcare/static/js/pos.js`, `petcare/static/css/app.css`, `petcare/templates/users/export_job.html`, `petcare/i18n.py`.
- Tests: `tests/integration/test_mysql_sales.py`, `tests/integration/test_mysql_web.py`, `tests/web/test_phase3_modules.py`, `tests/unit/test_database_config.py`, `tests/js/pos.test.cjs`; test CSS đã dùng lại `tests/web/test_design_tokens.py`.
- Tài liệu cập nhật: `docs/MASTER_UPGRADE_ROADMAP.md`, `docs/MODULE_COMPLETENESS_MATRIX.md`, `docs/TEST_MATRIX.md`, `docs/DB_READINESS_REMEDIATION.md`, `docs/BROWSER_TEST_RESULTS.md`, `docs/TEST_COVERAGE_GAPS.md`, `docs/UX_ISSUES.md`.
- Tài liệu mới: `docs/PHASE3_IMPLEMENTATION_REPORT.md` và `docs/PHASE3_REMAINING_WORK.md`.

Danh sách trên mô tả phạm vi Phase 3 so với checkpoint, không phải toàn bộ `git status`: working tree đã có thay đổi/untracked từ trước và được giữ nguyên.

## Browser và chức năng

- **Account/RBAC:** staff đổi display name, nhận success feedback, rồi khôi phục tên ban đầu. Staff dashboard được phép; `/users/` trả access denied. Không submit đổi mật khẩu, recovery hoặc email.
- **Tenant export:** passphrase mismatch bị từ chối; request hợp lệ tạo job; worker one-shot với cấu hình đúng hoàn tất; UI hiển thị `Export ready`. Bundle đã tải có magic `PCEXP001`, kích thước 2,283,927 bytes và được giữ ngoài repo với file mode 0600. Chỉ kiểm header/kích thước, không giải mã hoặc xem dữ liệu.
- **Refund:** route MySQL test đi qua create/pay/refund thật trong schema test; browser form/confirm chưa được submit do CUA không giữ native confirm dialog.
- **Responsive:** 390×844 mobile POS, 820×1180 tablet navigation, 1440×900 desktop. Không có document overflow tại ba viewport. Điều này không thay thế accessibility hoặc kiểm mọi trang.
- **Console:** error/warning rỗng trong tab đã kiểm; `/favicon.ico` vẫn 404, còn `/static/favicon.svg` 200. Network request panel không được thu thập.

## Migration và database readiness

Clone tạo từ dump read-only của `petcare_shop_dev`; clone trước migration: 20 bảng, 729 dòng tổng cộng, marker UTC. `initialize_database()` đưa clone lên 26 bảng và bốn marker readiness. Sáu bảng nghiệp vụ mới rỗng; row counts nghiệp vụ cũ giữ nguyên. Schema check/cột/FK đã đối chiếu; initializer chạy lần nữa thành công. Hai tên index hỗ trợ FK tự sinh vẫn khác nhưng cột key tương đương, được ghi trong [DB_READINESS_REMEDIATION.md](DB_READINESS_REMEDIATION.md).

`petcare_shop_dev`: **20 bảng, một marker, `/readyz` 503**, không đổi trong Phase 3. Cần phê duyệt tường minh trước bất cứ DDL nào trên DB dev, cùng backup và restore rehearsal được xác minh. Xem [DB_READINESS_REMEDIATION.md](DB_READINESS_REMEDIATION.md) để có commands và điều kiện recovery.

## Quality gates

| Gate | Trạng thái | Kết quả |
|---|---|---|
| Python | PASS | 369/369, 0 skipped |
| JavaScript | PASS | 28/28, 0 skipped |
| Bandit CI command | PASS | Exit 0 theo config/baseline CI; cảnh báo hiện hữu về `nosec` B608 được giới hạn ở câu lệnh đã review |
| pip-audit | PASS | Không có advisory đã biết trong `requirements.lock` tại lần quét |
| compileall / pip check | PASS | Không có syntax hoặc dependency conflict |
| Docker Compose config / image build | PASS | Cấu hình hợp lệ; image `petcare-manager-web:phase3` build thành công |
| Health/readiness | PASS có giới hạn | Browser QA và clone 200; `/workersz` 503 vì không chạy worker nền; dev `/readyz` 503 |
| Trivy / GitHub Actions | NOT TESTED | Trivy CLI chưa cài; hosted workflow không được chạy |
| `git diff --check` | PASS | Không có whitespace error sau cập nhật tài liệu |

## Hạn chế và bước tiếp theo

Không tuyên bố production-ready. Bước tiếp theo: duyệt/remediate DB dev theo runbook; thêm browser regression runner có confirm dialog cho refund trong QA; thử recovery/email/account workflows bằng mail stub; hoàn thành accessibility và request-level network audit; chạy Trivy/CI hosted. Provider thật, SMTP và S3 chỉ đánh giá với cấu hình staging/data tổng hợp sau khi được cho phép.

Ma trận chi tiết: [TEST_MATRIX.md](TEST_MATRIX.md), [TEST_COVERAGE_GAPS.md](TEST_COVERAGE_GAPS.md), [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md), [MASTER_UPGRADE_ROADMAP.md](MASTER_UPGRADE_ROADMAP.md).
