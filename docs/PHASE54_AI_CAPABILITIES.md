# Phase 5.4 — Assistant capability registry

Assistant hiện đăng ký đúng hai capability dữ liệu mới. Bộ nhận diện dựa trên từ/cụm từ được duyệt, không gửi prompt vào SQL và không cho LLM quyết định quyền.

| Capability | Câu hỏi mẫu VI / EN | Service | Quyền | Kết quả / giới hạn |
|---|---|---|---|---|
| `inventory_restock` | “Gợi ý sản phẩm cần nhập thêm”, “Sản phẩm nào sắp hết?” / “Which products need restocking?” | `restock_service.recommendations(actor_id, tenant_id)` | User đã đăng nhập, có membership active của tenant hiện hành | Chính xác số sản phẩm đang đạt cảnh báo; tối đa 8 sản phẩm ưu tiên. Có tồn, ngưỡng nhập lại, doanh số 14/30 ngày, ngày hàng còn lại và lượng đề xuất. |
| `purchase_status` | “Tình trạng đơn nhập?” / “Show purchase order status” | `purchase_service.list_purchase_orders(actor_id, status, page="1", tenant_id)` | Admin của tenant hiện hành; staff nhận phản hồi `forbidden` và không có `insight` | Count chính xác cho `ordered`, `partially_received`, `received`, `cancelled`; tối đa 8 đơn gần nhất. Status lọc được ánh xạ từ allowlist nội bộ. |

## Contract chung

- Request vẫn là POST `/assistant/chat` với `message` và tùy chọn `history`; auth session, CSRF, throttle và `g.tenant_id` do route hiện tại kiểm soát.
- `tenant_id` trong JSON không được đọc làm quyền. Service nhận tenant từ phiên server.
- Cả hai capability trả `mode: "local"`, `insight.kind` làm discriminant, `reply` cho giải thích bằng VI/EN.
- Dữ liệu hiển thị là số liệu từ service thật. Không gồm thông tin liên hệ supplier/customer, ảnh, prompt history, raw row hoặc note của đơn nhập.
- `url`, `amount_label` và `created_at_label` chỉ được server dựng. Browser chỉ nhận URL allowlist `/products/<id>` hoặc `/purchasing/<id>`.
- Kết quả không thay đổi dữ liệu. Assistant không tạo PO, nhận hàng, đổi tồn, hoàn tiền hoặc sửa hồ sơ.

## Intent, ambiguity và giới hạn

- Từ khóa như `restock`, `reorder`, `low stock`, “tồn kho thấp”, “cần nhập thêm”, “sắp hết” ánh xạ vào `inventory_restock`.
- Cụm “purchase order”, “purchase status”, “đơn nhập”, “đơn mua hàng”, “phiếu nhập” ánh xạ vào `purchase_status`; câu status được nhận theo bộ status cố định.
- Câu có ngày tùy chỉnh/period ngoài phạm vi hiện tại nhận clarification, không query dữ liệu bằng khoảng ngày từ người dùng.
- Câu ghép tồn kho với trạng thái đơn, ghép purchase status với product-sales ranking, yêu cầu nhiều trạng thái PO, hoặc phủ định trạng thái hoàn tất không được ánh xạ chắc chắn sẽ nhận clarification trước khi đọc dữ liệu. “Not received” được ánh xạ thành `ordered`; “partially received” không bị nhầm thành `received`.
- Yêu cầu hiển thị trên 8 item vẫn nhận tối đa 8 và nói rõ cap. Unknown intent đi qua xử lý assistant cũ.
- Inventory đang tái sử dụng `restock_service` hiện có: service đọc mọi sản phẩm active để xếp hạng/cộng tổng cảnh báo. Output của assistant vẫn cap 8; nếu catalog tăng lớn cần profiling trước khi thêm phân trang/aggregation mới.
- Purchasing gọi service một lần cho mỗi status để đếm đủ từng nhóm; mỗi service call chỉ tải một page 25 record, sau đó kết hợp tối đa 8 đơn gần nhất. Không nhận `status`, `LIMIT` hoặc sort expression từ prompt.

## Tiêu chí chấp nhận đã kiểm

1. VI/EN supported intent trả đúng `kind`, local mode, tenant-scoped data và server-generated same-origin link.
2. Unknown/custom-range/ambiguous request không tạo insight không có căn cứ hoặc truy vấn dữ liệu cho các capability ghép.
3. Inventory rỗng có empty state; DB lỗi có thông điệp chung, không trả exception/credential.
4. Staff không thấy PO counts hoặc rows; admin thấy status đầy đủ.
5. Prompt injection và tenant override trong payload không thay đổi scope, query shape hoặc provider path.
6. UI dùng text node, cap card count và không có failed request/page error trên luồng mới.

Bằng chứng triển khai: [implementation](PHASE54_IMPLEMENTATION.md), [API contract](API_CONTRACT.md), [security review](PHASE54_AI_SECURITY.md).
