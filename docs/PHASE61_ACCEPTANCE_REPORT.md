# Phase 6.1 — nghiệm thu ứng dụng

Ngày: 2026-11-11

Repo: `solo/khang-petcare`, HEAD `e1dc2114f078162f0d78cb3bcafdeeaee061fb92`

Môi trường thực thi: cài Python sạch, MySQL 8.4 QA trên tmpfs, storage/artifacts riêng trong `/tmp`.

## Kết luận

- **Academic demo: GO có điều kiện.** Có thể trình diễn trên database QA mới, dữ liệu seed tổng hợp, Flask chạy local, worker export local và Vision mock. Không dùng `petcare_shop_dev`, production, SMTP thật, AI provider, S3 hay payment provider. Xem [hướng dẫn bàn giao demo](PHASE62_DEMO_HANDOFF.md).
- **Production: NO-GO.** Schema phát triển có lịch sử readiness 503 chưa được kiểm tra lại theo chỉ thị không chạm DB; SMTP/AI/Vision/S3/payment thật, full screen-reader/zoom, hosted CI mới và vận hành production chưa được nghiệm thu độc lập.
- Không có lỗi P0/P1 hoặc blocker demo cốt lõi tái hiện được trong QA. Không sửa logic ứng dụng; chỉ cập nhật tài liệu nghiệm thu/roadmap và loại mật khẩu seed khỏi các tài liệu đang dùng.

## Baseline và cách ly

- Nhánh, HEAD và upstream giữ nguyên; không commit/push. Trước khi làm, tracked tree sạch; các untracked cũ `.agents/`, `docs/skills.md`, `skills-lock.json` được giữ nguyên.
- Compose project riêng `pc61-f88df46e58`; schema `petcare_a7639e123a_test`, MySQL 8.4 trên tmpfs, web bind loopback, ảnh/export/browser artifacts ở `/tmp/petcare-phase61-acceptance-potb7m9o`. Không kết nối hoặc thay đổi schema dev/production.
- `.env`, `.venv`, thư mục media/instance hiện có không bị sửa. AI endpoint/model/key, Vision thật, SMTP và S3 tắt; payment/refund là ledger mô phỏng, không có cổng thanh toán.

## Cài đặt sạch và chạy thật

- Tạo Python venv mới bằng Python 3.13.3; `pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock` hoàn tất. `pip check`: không có dependency hỏng.
- Accessibility test package được cài riêng từ `tests/a11y/package.json`/lock bằng `npm ci`; npm audit sạch. Frontend Jinja/CSS/JS không cần bước bundling để chạy.
- Chromium/Firefox/WebKit được cài trong thư mục tạm; bộ browser automation chính chạy Chromium. Máy chỉ có Python 3.13.3 cục bộ; Python 3.11/3.12 không chạy lại tại chỗ. Baseline GitHub Actions 6/6 trên ba phiên bản là lịch sử Phase 6.0, không phải run mới trong Phase 6.1.
- Setup test khởi tạo schema QA mới trên MySQL 8.4: 26 bảng và 4 migration markers; `/healthz=200`, `/readyz=200`.
- Flask khởi động và được điều khiển bằng Chromium. Worker email và tenant-export chạy với cấu hình không SMTP và local storage.
- `python run.py prepare-demo --json` chạy trên cùng server/config/schema QA và trả exit 0, `ok=true`, 68 ảnh local được kiểm, 7 hóa đơn seed được cập nhật ngày demo, AI=`local`. Chỉ fixture tổng hợp trên QA thay đổi.
- README setup dev dựa trên `.env` hiện có và `petcare_shop_dev`; không dùng lệnh đó trong lượt này vì DB dev không được phép chạm. Hướng dẫn QA cô lập nằm trong handoff mới.

## Hành trình và module đã vận hành

- **Auth/role:** login admin; staff chỉ xem route được phép và bị chặn khỏi khu admin. Browser 403 `/users/` là kết quả mong đợi.
- **Khách hàng/thú cưng:** tạo/sửa hồ sơ, liên kết thú cưng/người mua qua luồng hỗ trợ, kiểm form sai, quan hệ và persistence trên MySQL.
- **Sản phẩm/kho/POS:** tạo product, tìm catalog, kiểm số lượng âm, điều chỉnh kho có lý do, sổ kho, cart/estimate, hóa đơn và thu tiền mô phỏng.
- **Nhập hàng:** tạo PO qua UI, nhận 4/10 rồi 6/10, xác nhận trạng thái và tồn kho; MySQL tests kiểm hủy, invalid transition, nhận lặp/idempotency và rollback.
- **Hoàn tiền:** xác nhận/dismiss, số lượng 0/quá mức, partial/full, retry cùng request key, stock/movement và transaction rollback trên QA.
- **Báo cáo/export:** period filter, top products, XLSX, tenant export worker, status/download artifact local.
- **Assistant:** top-selling products, restock, PO status và operations overview đọc từ business service; kiểm role/tenant/link bản ghi và không gọi provider.
- **Vision: MOCKED:** ảnh synthetic, mock loopback; valid/invalid upload, structured suggestion, chỉ áp dụng field trống, giữ giá trị người dùng, không tự lưu, timeout/malformed/retry và staff denial.
- **Hành trình ghép cùng bản ghi:** sản phẩm QA từ 0 → PO #17 nhận 4+6, tồn 10 → hóa đơn #26 bán 2 và thu tiền, tồn 8 → hoàn 1 sản phẩm 10.000 VND, tồn 9 → báo cáo hiển thị SKU bán ròng 1. UI doanh thu kỳ `638.000 VND` khớp `report_service`; tổng kỳ còn có hóa đơn seed. Xem [cross-module verification](PHASE61_CROSS_MODULE_VERIFICATION.md).

## Kiểm thử và cổng chất lượng

| Hạng mục | Kết quả thực thi Phase 6.1 |
|---|---|
| Python unittest + MySQL 8.4 | **421/421 PASS**, 0 failure/error/skip; lệnh `python -m unittest discover -s tests -v`. |
| JavaScript | **40/40 PASS**, 0 skipped; `node --test tests/js/*.test.cjs`. |
| Playwright | **18/18 PASS**, 0 skip; `scripts/browser_smoke/run_smoke.py`, Flask/MySQL QA thật, Vision mock. |
| Chromium diagnostics | 13 diagnostic entries: 0 page errors, 0 failed requests; 1 console/HTTP 403 tại route admin do test staff, được mong đợi. |
| axe-core 4.14.0 | 31 page/state scans + 5 Vision states: 0 violations. 36 incomplete occurrences ở suite chính và 5 incomplete icon/contrast Vision; xem phần accessibility. |
| Bandit | Lệnh source-security đúng `.github/workflows/ci.yml`, baseline được áp dụng, exit 0. Bandit in thông báo `nosec encountered (B608)` tại các statement suppression hẹp; gate không thất bại. |
| pip-audit | Runtime lock và browser lock: “No known vulnerabilities found”. |
| npm audit | 0 vulnerabilities. |
| `pip check`, compileall, Compose config | PASS; không có dependency conflict, lỗi cú pháp hoặc lỗi parse Compose. |
| Docker image | `docker build --tag petcare-manager-web:phase61-acceptance .` PASS. Image không được triển khai vào production. |
| App health/readiness | QA bình thường: `/healthz=200`, `/readyz=200`. DB QA trỏ tới cổng loopback chưa lắng nghe: app vẫn chạy, `/healthz=200`, `/readyz=503`. |
| Worker recovery | Xóa marker chỉ trong QA: `/workersz=503`; bật cả hai worker với SMTP trống/local storage: `/workersz=200`. |
| Demo preflight | `python run.py prepare-demo --json`: exit 0, `ok=true`, duration 0.666s trên QA. |
| Hosted CI / Trivy | Không chạy lại trong lượt này; commit không đổi và không push. Actions 6/6 là baseline lịch sử Phase 6.0. |

## UI, accessibility và giới hạn

- Chromium scenarios dùng widths 320/390/768/820/1024/1440px trên các trang customer/pet, product/inventory, POS, purchasing, reports và Vision theo từng browser test; các assertions không phát hiện tràn ngang tại breakpoint đã chạy. Không phải mọi route đều được test ở mọi width.
- Firefox và WebKit đăng nhập rồi mở sáu route chính ở 390px; tất cả trả 200 và không tràn ngang. WebKit có 19 cảnh báo CSP khi hiệu ứng GSAP thử ghi inline transform/style; stylesheet ngoài vẫn tải và trang hoạt động. Đây là suy luận về hiệu ứng tùy chọn từ source + console, không phải lỗi nghiệp vụ.
- axe không phát hiện violation. Incomplete còn lại gồm contrast của SVG/chart, phần tử ảnh/chồng lấp, icon Unicode trang trí và `aria-label` trên `.assistant-catalog` không có role. Không có thiết bị đo contrast hoặc screen reader để chốt các trường hợp này.
- Browser suite mô phỏng 200% zoom bằng layout viewport 720px ở một số trang; **zoom trình duyệt thật 200% NOT TESTED**. Screen reader **NOT TESTED**. Không tuyên bố WCAG conformance.
- SMTP/email delivery, live AI/AI Vision, S3, payment provider, production load/performance, production secrets/config và production DB **NOT TESTED**.

## Thay đổi và hướng xử lý

- Thêm sáu deliverable Phase 6.1/6.2, cập nhật roadmap/test/module matrix và gỡ giá trị mật khẩu demo khỏi README/user docs hiện hành. Không thay framework, API contract, business logic hoặc schema.
- Chi tiết issue và ưu tiên: [defects and risks](PHASE61_DEFECTS_AND_RISKS.md). Trình tự tiếp theo: [roadmap Phase 6.2](MASTER_UPGRADE_ROADMAP.md#phase-62-demo-hardening-và-accessibility).
