# Phase 5.5 — Intelligent Operations & Product Experience

Ngày: 2026-11-11. Trạng thái: **IMPLEMENTED / VERIFIED trên QA cô lập**.

## Tóm tắt

Đã thêm một luồng assistant deterministic, chỉ đọc dành cho admin: **“Tổng quan cần chú ý ở cửa hàng”**. Một request kết hợp dữ liệu tồn kho, đơn nhập đang mở và ngữ cảnh top products bảy ngày. Luồng dùng service nghiệp vụ hiện có, không viết SQL mới, không gọi AI provider và không thay đổi dữ liệu.

## Hành vi đã triển khai

- Nhận diện các cụm từ overview tiếng Việt/Anh bằng intent registry hiện có. Câu hỏi ngày tùy chỉnh ngoài phạm vi nhận clarification; “last 7 days” được hỗ trợ cho phần sales.
- Admin được xác thực đầu tiên qua `purchase_service`; nếu bị từ chối hoặc không thể kiểm tra quyền thì không đọc inventory/report và không trả insight.
- `restock_service.recommendations` cho exact warning count và các sản phẩm ưu tiên theo công thức hiện hành; response giới hạn 5.
- `purchase_service.list_purchase_orders` lấy count của `ordered` và `partially_received`, rồi xếp 5 đơn mới nhất. `received` và `cancelled` không được coi là đang chờ xử lý.
- `report_service.top_products_for_period(..., "7d")` cung cấp tối đa 5 sản phẩm có net quantity dương, ngày bắt đầu/kết thúc theo timezone tenant và revenue đã được report service tính.
- UI gom ba nhóm thành insight cards có source label, trạng thái rỗng/lỗi từng nguồn và liên kết tới product, purchase order/list, hoặc report đúng ngày.
- Mọi insight trả `mode: "local"`. Không tạo PO, nhận/hủy PO, điều chỉnh tồn hoặc sửa hồ sơ; provider `complete()` không được gọi.

## Quyền, an toàn và dữ liệu

- Actor và tenant đều lấy từ session/context server. `tenant_id` trong JSON không được dùng làm quyền.
- Service nghiệp vụ hiện có tiếp tục kiểm tenant/role; route chỉ tạo URL same-origin bằng `url_for`.
- Business text được render bằng `textContent`; frontend chỉ chấp nhận link pattern nội bộ cho product/PO/report.
- Response không chứa supplier email, note PO, ảnh hay thông tin khách hàng.
- Nếu inventory hoặc report service lỗi sau khi admin đã được xác nhận, response giữ những nhóm còn đọc được và đánh dấu `partial`. Lỗi ở purchase/auth gate trả thông báo chung, không có insight.
- Các service dùng connection/read snapshot riêng; overview không phải snapshot transaction atomic giữa module.

## Thay đổi mã

- Thêm [assistant_operations_service.py](../petcare/services/assistant_operations_service.py) làm lớp tổng hợp nhỏ, chỉ gọi service hiện hành.
- Mở rộng registry/dispatcher tại [assistant_capabilities.py](../petcare/services/assistant_capabilities.py) và URL/format labels tại [assistant_routes.py](../petcare/routes/assistant_routes.py).
- Thêm nhóm card an toàn, nguồn và empty/error states trong [assistant.js](../petcare/static/js/assistant.js); thêm suggestion admin, copy capability rõ ràng, bản dịch và style responsive.
- Thêm unit, MySQL integration, JavaScript và Playwright coverage.
- Cập nhật API/QA/roadmap/handoff documents và lưu ảnh ở [assets/phase55](assets/phase55/).

Không thêm migration/schema change, dependency runtime/browser hoặc framework. Không thay API request, CSRF, throttling, provider boundary hay các capability Phase 5.4.

## Đo giá trị sản phẩm

Trong browser task có dữ liệu MySQL QA thật, cách cũ cần ba câu hỏi được gửi riêng (3 POST; mở assistant, chọn restock, rồi hai lần nhập/gửi = 6 interaction events trong test). Overview cần mở assistant và chọn một câu gợi ý (1 POST; 2 interaction events). Đây là phép đếm trong một script tái lập, không phải nghiên cứu người dùng hoặc đo thời gian thực.

## Verification

- Python: **421/421 PASS, 0 skipped**, MySQL 8.4 disposable schema `_test` trên tmpfs.
- JavaScript: **40/40 PASS**.
- Full Chromium/Playwright: **18/18 PASS, 0 skipped**; targeted overview rerun sau khi thêm kiểm tra giới hạn panel theo chiều dọc: **1/1 PASS**.
- `/healthz=200`, `/readyz=200` trên QA; browser scenario mở product, PO detail và report link thật.
- Bandit với exact CI arguments/baseline exit 0; hai `pip-audit` không có known vulnerabilities; `npm audit` 0 vulnerabilities; `pip check`, compileall, Compose QA config, Docker build và `git diff --check` pass.
- Axe hai overview states: 0 violations, mỗi state có 3 incomplete items. Hosted Actions không được chạy lại vì không push.
- Real AI/Vision provider, SMTP và S3 không được gọi; Vision browser suite hiện có chạy offline/mock.

## Giới hạn còn lại

- Intent vẫn là phrase rules, không phải hiểu hội thoại tự do.
- Sales section là top-selling context trong bảy ngày; không khẳng định tổng doanh thu, số hóa đơn hoặc so sánh với kỳ trước.
- Inventory exact count yêu cầu service hiện có duyệt catalog active; chưa đo latency theo catalog lớn.
- Các nguồn đọc riêng, nên số liệu có thể thay đổi giữa các lần đọc.
- Screen reader, true 200% zoom, Safari/Firefox và usability session với người dùng chưa thực hiện.
- Real provider quality, cost, latency, privacy/retention và external services vẫn chưa được đánh giá.

Chi tiết: [workflow](PHASE55_INTELLIGENCE_WORKFLOW.md), [evaluation](PHASE55_AI_EVALUATION.md), [UX verification](PHASE55_UX_VERIFICATION.md), [Phase 6 handoff](PHASE6_HANDOFF.md).
