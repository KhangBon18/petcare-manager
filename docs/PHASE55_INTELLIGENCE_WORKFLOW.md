# Phase 5.5 — Intelligence workflow contract

Ngày: 2026-11-11. Luồng: **admin hỏi tổng quan cần chú ý trong cửa hàng**.

## Người dùng và giá trị

Quản trị viên active của tenant hiện tại cần biết nhanh sản phẩm đang đạt ngưỡng cảnh báo, đơn nhập còn mở và bối cảnh sản phẩm bán chạy gần đây. Thay vì mở từng module hoặc gửi ba câu hỏi riêng, admin chọn một prompt gợi ý và nhận ba nhóm dữ kiện có liên kết tới trang hiện hành.

## Intent được hỗ trợ

Nhận diện phrase xác định, gồm:

- Tiếng Anh: `overview`, `operations overview`, `business overview`, `store overview`, `what needs attention`, `Give me an overview of what needs attention in my store`.
- Tiếng Việt: `tổng quan vận hành`, `tổng quan cửa hàng`, `tổng quan cần chú ý`, `cửa hàng cần chú ý`, `việc cần chú ý`.

Câu có period khác phần sales cố định bảy ngày (ví dụ last 30 days, this month, date range) nhận clarification. Câu hỏi overview là deterministic local capability và không đi vào nhánh LLM.

## Dòng gọi service

```text
POST /assistant/chat
  -> assistant_service.answer
  -> intent registry: operations_overview
  -> assistant_operations_service.answer
       1) purchase_service.list_purchase_orders(ordered)
       2) purchase_service.list_purchase_orders(partially_received)
       3) restock_service.recommendations
       4) report_service.top_products_for_period("7d")
  -> assistant_routes tạo URL, locale date/money labels
  -> assistant.js render section/card bằng textContent
```

Request format, auth session, CSRF, rate limit và response envelope `reply`/`mode` của `/assistant/chat` giữ nguyên.

## Authorization boundary

- Overview chỉ dành cho `admin` trong tenant hiện hành. `purchase_service` là cổng role đầu tiên vì purchasing vốn admin-only; staff nhận `status: "forbidden"` và không có `insight`.
- Mỗi service tiếp tục gọi kiểm tra actor/tenant hiện có. Tenant chỉ lấy từ session; request JSON có gửi `tenant_id` cũng không thay đổi query scope.
- Nếu quyền bị thu hồi trong lúc đang tổng hợp, `ForbiddenError` làm hủy toàn bộ insight, không trả phần đã đọc trước đó.
- Không có prompt-to-SQL, table/column name từ text, service write call hoặc provider request.

## Số liệu được trả

### `inventory`

Nguồn: `restock_service.recommendations(actor_id, tenant_id=...)`. `total` đếm chính xác các dòng có `warning`; số liệu `suggested_qty`, `days_left`, `reorder_level` giữ nguyên service rule. Tối đa 5 item. Count exact đòi hỏi service hiện tại duyệt toàn bộ sản phẩm active; không tạo count heuristic mới.

### `purchasing`

Nguồn: `purchase_service.list_purchase_orders` cho đúng hai enum `ordered` và `partially_received`. `open_total` là tổng hai count service trả về; không cộng `received`/`cancelled`. Service page hiện tại lấy tối đa 25 record mỗi status; khi gộp và xếp ngày mới nhất, chỉ đưa tối đa 5 record ra UI. Không trả email/note/supplier contact.

### `sales`

Nguồn: `report_service.top_products_for_period(actor_id, "7d", tenant_id=...)`; ngày được tính theo timezone tenant. Chỉ trả sản phẩm có net quantity dương, tối đa 5 item, quantity và revenue của từng sản phẩm. Không cộng những dòng này thành tổng doanh thu toàn cửa hàng.

## Contract response mới

```json
{
  "reply": "...",
  "mode": "local",
  "status": "ok",
  "insight": {
    "kind": "operations_overview",
    "purchasing": {
      "status": "available",
      "open_total": 0,
      "status_counts": {"ordered": 0, "partially_received": 0},
      "items": [],
      "url": "/purchasing/"
    },
    "inventory": {
      "status": "available",
      "total": 0,
      "target_days": 14,
      "warning_days": 7,
      "items": []
    },
    "sales": {
      "status": "available",
      "period": "7d",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "currency_code": "...",
      "items": [],
      "url": "/reports/?start=YYYY-MM-DD&end=YYYY-MM-DD"
    }
  }
}
```

`inventory` hoặc `sales` có thể là `{"status":"unavailable"}` khi riêng source đó lỗi; top-level `status` trở thành `partial`. Purchasing/auth gate failure trả `status: "unavailable"` hoặc `forbidden`, không có `insight`. Dữ liệu exception/credential không được đưa vào response.

## Next-step recommendations

- Khi có sản phẩm warning, mở product detail để admin kiểm tồn và quy tắc nhập lại.
- Khi có ordered/partially received PO, mở đơn hoặc purchasing list để admin xem trạng thái.
- Mở report filter đúng khoảng ngày để kiểm tra sản phẩm bán chạy.

Các link do Flask `url_for` sinh từ ID/period đã được service trả về. Assistant không thực hiện các hành động ghi này.

## Acceptance đã kiểm

1. Admin nhận ba source groups qua một câu VI/EN.
2. Staff không nhận purchasing count hoặc inventory/sales payload qua overview.
3. Tenant override trong payload bị bỏ qua; route dùng tenant từ phiên hiện hành.
4. Prompt injection không đổi intent boundary, quyền hoặc provider path.
5. Counts, period, product/PO IDs và links đối chiếu với service thật trên MySQL QA.
6. Empty state, per-source unavailable, unsupported range, cap 5 và safe text/link được test.
7. Stock quantity và PO state trước/sau route bằng nhau; không có mutation.

Evidence: [MySQL integration test](../tests/integration/test_mysql_purchasing.py), [unit tests](../tests/unit/test_assistant_operations_overview.py), [API contract](API_CONTRACT.md).
