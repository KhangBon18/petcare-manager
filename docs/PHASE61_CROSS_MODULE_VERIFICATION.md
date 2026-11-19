# Phase 6.1 — kiểm chứng dữ liệu liên mô-đun

## Luồng ghép thực tế

Chạy trên Flask + MySQL 8.4 QA `petcare_a7639e123a_test`, storage tạm. Cùng một SKU tổng hợp được thao tác bằng UI, không dùng dữ liệu dev/production.

| Bước | Thao tác/nguồn | Số liệu kỳ vọng | Kết quả quan sát |
|---|---|---|---|
| 1 | Admin tạo product `E61-F7377808` trên `/products/new` | Tồn đầu 0 | MySQL: product id 376, stock 0 |
| 2 | UI tạo PO #17, 10 units | Tạo order không tăng stock | PO `ordered`; tồn vẫn 0 |
| 3 | UI nhận 4 units | PO partial; tồn tăng đúng lượng | `partially_received`, received 4, stock 4 |
| 4 | UI nhận 6 còn lại | PO hoàn tất | `received`, received 10, stock 10; movements theo từng lần nhận |
| 5 | POS tạo hóa đơn #26, bán 2 units và xác nhận thanh toán | Hóa đơn `paid`; tồn giảm 2 | MySQL: paid, invoice line qty 2, stock 8 |
| 6 | UI ghi nhận partial refund 1 unit, disposition resell | Hoàn 10.000 VND; tồn tăng 1; không gọi cổng tiền | 1 refund, 1 refund item, amount 10.000 VND, stock 9 |
| 7 | UI `/reports/?period=month` và `report_service` | Net quantity SKU 1; doanh thu UI khớp service | Top product quantity 1; UI revenue `638.000 VND` khớp service; kỳ còn có seed sales |

Hệ thống chỉ ghi sổ hoàn tiền; tiền mặt/chuyển khoản phải được thực hiện riêng như nội dung trang hóa đơn. Không có payment provider call. DB tạm bị hủy cùng Compose project sau khi nghiệm thu.

## Đối chiếu độc lập trong suite

- **Purchasing → stock:** `tests/integration/test_mysql_purchasing.py::test_real_routes_create_partially_receive_fully_receive_and_reject_duplicate_after_close` kiểm route/state/stock; `test_replayed_partial_payload_is_idempotent_but_distinct_receipt_is_counted` kiểm replay; `test_database_transaction_rolls_back_stock_lines_movements_and_status_on_failure` kiểm rollback; `test_validation_cancellation_and_invalid_state_transitions_preserve_stock` kiểm transition/hủy.
- **Stock → POS → invoice/report:** `tests/integration/test_mysql_sales.py::test_payment_updates_stock_pet_and_revenue_once` kiểm thanh toán trừ stock và revenue một lần; `test_concurrent_payment_cannot_sell_last_unit_twice` kiểm concurrency.
- **Invoice/refund → stock/report:** `test_partial_refund_is_idempotent_and_net_revenue_uses_refund_date` và `test_refund_route_persists_partial_full_retry_and_rolls_back_failures` kiểm ledger, net revenue, retry và rollback.
- **Customer ↔ pet ↔ invoice:** browser workflow xác nhận customer profile hiện thú cưng đã mua và pet profile quay lại đúng customer.
- **Assistant:** MySQL route tests kiểm tenant/session, staff denial, record links và service data; browser cards kiểm thông tin, không có mutation/provider.

## Ranh giới và trạng thái

- PASS: UI → route → service → MySQL cho PO receiving, POS paid invoice, refund và report trên cùng SKU.
- PASS: invalid input/transaction failure trong integration tests giữ trạng thái trước commit.
- PASS: worker unavailable → healthy được kiểm riêng trên QA; export artifact được tạo/tải từ local storage.
- NOT TESTED: real payment/refund network, multi-instance production concurrency, provider payload, S3, SMTP delivery, production DB.
- QA readiness không chứng minh schema dev đã migrate. Dev schema không được kết nối/chỉnh sửa trong Phase 6.1.
