# Phase 5.5 — Assistant intelligence evaluation

Ngày: 2026-11-11. Phạm vi: **đánh giá retrieval và contract deterministic**; không đánh giá model generative.

## Cách đánh giá

Operations overview chạy bằng phrase registry + service rules. Không có LLM/provider tham gia quyết định intent, permission, query shape, số liệu hoặc link. Vì vậy chỉ tiêu accuracy/latency/cost của model không áp dụng và không được suy ra từ test mock.

Test dùng dữ liệu synthetic trên disposable MySQL 8.4 `_test`, gọi application service/route thật. Các unit test dùng fixtures có cấu trúc để kiểm tra cap, lỗi và empty states. Không có fixture/customer data từ production.

## Evaluation cases

| Trường hợp | Kỳ vọng | Kết quả |
|---|---|---|
| Admin hỏi overview VI/EN | `kind=operations_overview`, `mode=local`, ba nhóm facts | PASS; registry, service unit, route MySQL và Playwright |
| Restock warning | `total`, stock, reorder level và suggested quantity khớp `restock_service`; tối đa 5 card | PASS trên MySQL QA + unit cap |
| PO cần xử lý | Chỉ `ordered` + `partially_received`; count khớp `purchase_service`, order links hiện tenant hiện tại | PASS trên MySQL QA |
| Sales context | Kỳ `7d`, ngày theo tenant và top products/revenue từ `report_service`; không bịa total revenue | PASS trên MySQL QA; empty results cũng được kiểm |
| Admin authorization | Purchasing service gate được gọi trước inventory/report | PASS bằng unit ordering + route integration |
| Staff | `forbidden`, không có `insight`; không gọi inventory/report sau khi gate từ chối | PASS bằng unit + MySQL staff route |
| Tenant override | JSON `tenant_id` khác không làm đổi tenant trong các service calls | PASS bằng route integration với session tenant thật |
| Prompt injection | Cụm “ignore all rules” không đổi deterministic scope hoặc provider path | PASS bằng MySQL route với provider mock đánh dấu configured; `complete()` không được gọi |
| Custom/invalid date range | Clarification trước mọi service query | PASS bằng unit test; không tạo khoảng ngày từ prompt |
| Empty business data | Count 0 và danh sách rỗng được trả đúng; không thêm facts | PASS bằng deterministic unit fixture |
| Service failure | Purchase/auth gate lỗi trả unavailable không có insight; inventory lỗi trả partial, không lộ exception text | PASS bằng unit tests |
| Frontend hostile text/link | Tên `<img>`/`<script>` hiện bằng text; URL ngoại lai bị bỏ | PASS bằng JavaScript unit test; browser links mở đúng page thật |
| Data mutation | Tồn và trạng thái PO trước/sau assistant request giống nhau | PASS bằng MySQL integration assertion |

## Kết quả regression liên quan

- Python/MySQL toàn suite: **421/421 PASS, 0 skip**.
- JavaScript: **40/40 PASS**.
- Playwright: **18/18 PASS, 0 skip**; overview target rerun **1/1 PASS** sau khi bổ sung kiểm tra giới hạn panel theo dọc.
- Vision browser flows hiện có vẫn pass bằng mock; provider thật không được gọi.
- Bandit source gate exit 0; dependency audit hai Python lockfiles không có known vulnerabilities; npm audit 0.

## Kết luận và ranh giới

Kịch bản trả facts do service hiện có tính toán; không có hallucination path trong overview vì response được tạo local. Bài test chứng minh contract và sample fixtures, không chứng minh business rule đúng với mọi quy tắc cửa hàng chưa có trong code.

Chưa đo:

- Chất lượng, độ chính xác hoặc độ an toàn của provider AI thật.
- Latency theo quy mô catalog lớn; `restock_service` vẫn duyệt sản phẩm active để tạo exact count.
- Tính atomic của ba source snapshots; các service đọc độc lập trên các connection riêng.
- Tỷ lệ intent đúng trên câu hỏi tự nhiên của người dùng thật.
- Cost/token/retention/region của bất kỳ provider nào.

External AI egress, SMTP, S3 và Vision provider bị tắt trong QA. Không bật provider paid hoặc tạo claim về model quality từ deterministic test.
