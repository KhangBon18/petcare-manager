# Câu hỏi bảo vệ — guide kỹ thuật

### Vì sao chọn Flask và MySQL?

Flask phù hợp ứng dụng Python theo module/blueprint và dễ minh họa vòng đời HTTP trong môn học. MySQL/InnoDB cung cấp transactions, row locking, foreign keys, unique/check constraints và schema phù hợp dữ liệu quan hệ cửa hàng. Hiện trạng là Flask/Jinja/MySQL; không thay framework.

### Request đi qua routes, services, repositories thế nào?

Route ở `petcare/routes/` kiểm authentication/request shape, gọi service; service xác thực input, permission và state transition rồi mở transaction; repository trong `petcare/repositories/` thực hiện parameterized SQL. Route chuyển result/error thành HTML redirect/flash hoặc JSON. Ví dụ `invoice_routes.py` → `invoice_service.py` → `invoice_repo.py`.

### Transaction bảo vệ tồn kho ra sao?

`pay_invoice` kiểm invoice chưa thanh toán và khóa các record được cập nhật; cập nhật stock hoặc pet ownership, status/paid time và stock ledger trong transaction. Nếu bước lỗi, connection rollback, không giữ một phần state. Purchase receiving tương tự validate quantity còn thiếu, lock order/lines và ghi receipt movement cùng cập nhật state.

### Tenant isolation được thực thi ở đâu?

Membership trong `tenant_users` tạo tenant context từ session; client không thể tự chọn tenant bằng payload để vượt quyền. Service truyền tenant context, repository lọc `tenant_id`, và composite foreign keys ràng buộc cùng tenant. Role check bổ sung cho thao tác admin. Integration tests kiểm tenant override/forbidden cases.

### POS giữ hàng nhất quán và chống duplicate thế nào?

Tạo invoice chưa trừ kho; chỉ payment confirmation mới trừ. Request/payment path khóa invoice và kiểm state để retry không thu lại. Database `invoice_items`/status constraints và unit tests bảo vệ invariant. Cần phân biệt safeguard đã test với load/concurrency soak chưa chạy.

### PO receive chống ghi nhận lại thế nào?

Receipt POST mang `request_key` và payload fingerprint trong `purchase_order_receipt_requests` với unique tenant/key. Retry cùng request không tăng stock hai lần; reuse key với payload khác bị từ chối. Stock movement giữ ledger nhận hàng và foreign keys gắn PO/item. MySQL integration lifecycle đã chạy trên disposable schema.

### Refund có hoàn tiền thật không?

Không. Refund thêm bản ghi bất biến vào `invoice_refunds` và `invoice_refund_items`; invoice gốc vẫn giữ. Disposition `resell` có thể tăng tồn; `quarantine` và `not_returned` không đưa hàng có thể bán trở lại. Tiền mặt/chuyển khoản phải thực hiện ngoài app; không tích hợp gateway.

### Assistant lấy dữ kiện thế nào?

Top-product/operations insight dùng service/repository query theo tenant và kỳ thời gian; local intent formatter deterministic. Một số câu khác có thể gọi adapter tới provider nếu cấu hình; dữ liệu context được giới hạn theo intent. Demo launcher không bật real provider. Không mô tả output database/rule như advanced LLM reasoning.

### Vision mock có chứng minh độ chính xác model không?

Không. `scripts/demo/vision_mock.py` trả JSON cố định cho synthetic request để kiểm flow provider adapter, UI review và fill-empty behavior. Ảnh không được model phân loại; accuracy của LLM/Vision thật chưa đo.

### Kiểm thử có những lớp nào?

- Unit: validation, service/rule helpers, access guards.
- Web: Flask client routes, response/error/status, session/CSRF behavior.
- Integration: MySQL transaction/state/foreign keys/tenant queries.
- Browser: Playwright Chromium full smoke; cross-browser representative Chromium/Firefox/WebKit; axe scans.
- Security: Bandit exact CI config và pip/npm audits.

Phase 6.2 kết quả cuối nằm trong [TEST_MATRIX.md](TEST_MATRIX.md); suites khác loại, không cộng thành phần trăm coverage.

### Còn gì trước production?

Không go production: chưa kiểm dev schema drift qua migration rollout, chưa có backup restore rehearsal được chấp nhận cho dev, chưa test real SMTP/S3/AI/payment, chưa chạy native screen reader/200% zoom và chưa đánh giá tải/concurrency. Cần release review, secrets/infra configuration, hosted CI mới và backup/restore evidence trước rollout.
