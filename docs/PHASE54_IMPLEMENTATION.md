# Phase 5.4 — Multi-module assistant implementation

Ngày: 2026-11-10. Trạng thái: **IMPLEMENTED / VERIFIED trên môi trường QA cô lập**.

## Kết quả

Assistant hiện có hai capability dữ liệu mới, xác định và chỉ đọc:

1. **Ưu tiên tồn kho:** gọi `restock_service.recommendations`, giữ nguyên công thức doanh số 14/30 ngày, ngưỡng cảnh báo và lượng đề xuất hiện hành. Trả tổng số cảnh báo và tối đa 8 sản phẩm.
2. **Trạng thái đơn nhập:** gọi `purchase_service.list_purchase_orders` cho bốn trạng thái được hỗ trợ. Trả count theo trạng thái và tối đa 8 đơn gần nhất; chỉ admin được xem.

Hai capability chạy trước nhánh provider tùy chọn, nên luôn trả `mode: local`. Top-products theo báo cáo tiếp tục hoạt động. Không có thao tác tạo/sửa/hủy/nhận đơn từ assistant.

## Thay đổi thực hiện

- Thêm registry, intent rules VI/EN, giới hạn đầu ra, làm rõ khoảng ngày không hỗ trợ, lọc trạng thái an toàn và thông điệp lỗi chung tại `petcare/services/assistant_capabilities.py`.
- Nối capability vào `assistant_service.answer`; route tạo URL cùng-origin, nhãn tiền và thời gian theo locale/timezone.
- Thêm thẻ kết quả đọc được cho tồn kho/đơn nhập; tất cả nội dung dữ liệu hiển thị bằng `textContent`. Bổ sung nguồn dữ liệu, empty/error/permission state và nút retry; suggestion đơn nhập chỉ hiện cho admin.
- Không thêm dependency runtime, migration, SQL tùy chỉnh theo prompt, provider call hoặc Vision request.

## Git và dữ liệu

- Đầu phiên: branch `solo/khang-petcare`, HEAD `8634300f4b5ad4700d6702a048220d6597c4e200`; working tree đã có 112 file tracked modified và 1.040 untracked. Không stage, commit, reset, clean hoặc stash.
- Checkpoint khôi phục trước sửa: `/Users/heisenbon/Documents/Codex/petcare-phase54-checkpoint-20261110`; SHA256 của 10 thành phần đều xác minh OK. Các file assistant/docs vốn đã dirty được chỉnh tiếp; file mới Phase 5.4 được liệt kê cuối báo cáo bàn giao trong chat.
- Test chỉ dùng các schema Compose `*_test` với MySQL tmpfs và thư mục lưu trữ tạm. Container QA đã được dừng sau mỗi run. Không truy cập/sửa `petcare_shop_dev` hoặc production.

## Bằng chứng xác minh

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| Python | **PASS 415/415, 0 skip** | `.venv/bin/python -m unittest discover -s tests -v`, fresh disposable MySQL schema `petcare_phase54_final_test`; two added assistant ambiguity/negation assertions passed. |
| JavaScript | **PASS 38/38** | `node --test tests/js/*.test.cjs`. |
| Chromium / Playwright | **PASS 17/17, 0 skip; targeted assistant rerun 1/1** | Full suite: `scripts/browser_smoke/run_smoke.py`, schema `petcare_phase54_browserfull_test`, storage riêng; `/healthz=200`, `/readyz=200`. Sau hardening intent, assistant responsive/navigable scenario chạy lại 1/1 trên schema `petcare_phase54_ui3_test`, port 5080, axe được bật. |
| MySQL capability route | **PASS** | Bốn trạng thái PO tổng hợp, sản phẩm tồn 0, URL tenant hiện tại, staff denial, payload tenant override và prompt injection; provider mock được đánh dấu configured nhưng `complete` không được gọi. |
| Responsive / accessibility | **PASS theo phạm vi** | Document width 320/390/768/1440 px; panel nằm trong viewport; 3 axe scan trên assistant: 0 violations, 40 incomplete node instances. Screen reader/200% zoom chưa xác minh. |
| Bandit | **PASS** | Đúng lệnh CI với Bandit 1.9.4 và baseline; exit 0. Có cảnh báo `nosec encountered (B608)` tại các statement đã allowlist, không có finding mới. |
| Dependency / package | **PASS** | `pip-audit -r requirements.lock`, `pip-audit -r requirements-browser.lock`: không có known vulnerabilities; `npm audit --prefix tests/a11y`: 0 vulnerabilities; `pip check` sạch. |
| Build / syntax / diff | **PASS** | `compileall`, `docker compose ... config --quiet`, `docker build`, `git diff --check`. |

Lần chạy Playwright đầu tiên có 16/17 pass và dừng accessibility case do checkout chưa cài `axe-core`. Cài đúng lock bằng `npm ci --prefix tests/a11y`; lần chạy đầy đủ tiếp theo đạt 17/17. Sau khi hardening truy vấn mơ hồ, assistant browser case chạy riêng 1/1 pass. Lệnh Bandit đầu tiên không có trong shell `PATH`; gọi cùng lệnh CI với `.venv/bin` trong `PATH` thì pass.

## Ảnh UI

- [Tồn kho — desktop](assets/phase54/assistant-inventory-desktop.png)
- [Trạng thái đơn nhập — desktop](assets/phase54/assistant-purchasing-desktop.png)
- [Trạng thái đơn nhập — mobile 390 px](assets/phase54/assistant-purchasing-mobile-390.png)

Ảnh được tạo bởi browser test với tài khoản/đơn/sản phẩm QA tổng hợp; không chứa credential.

## Giới hạn đã biết

- Intent matching là quy tắc VI/EN được duyệt, không phải hiểu ngôn ngữ tự do. Custom date range nhận clarification; không đưa thời gian từ prompt vào truy vấn.
- Kết quả UI tối đa 8 item. `restock_service` hiện tải danh sách sản phẩm active để tính đúng tổng cảnh báo; đây là đường service hiện có của dashboard/product page, nên latency phụ thuộc quy mô catalog.
- Purchase overview cần 4 lần gọi service (mỗi trạng thái một trang 25 dòng) để có count chính xác; record response vẫn giới hạn 8.
- Test chưa xác minh screen reader, browser zoom thật, Safari/Firefox, production-scale catalog hoặc CI hosted. Provider thật, SMTP, S3 và Vision thật không được gọi; `petcare_shop_dev` không được kiểm tra lại trong phase này.

## Bước tiếp theo

Xem [Phase 5.5 handoff](PHASE55_HANDOFF.md), [evaluation](PHASE54_AI_EVALUATION.md), [security](PHASE54_AI_SECURITY.md) và [UX evidence](PHASE54_AI_UX.md). Không bật provider thật hoặc thêm write capability trong Phase 5.5 nếu chưa có yêu cầu và cổng phê duyệt riêng.
