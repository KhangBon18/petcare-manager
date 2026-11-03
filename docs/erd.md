# ERD — cửa hàng thú cưng

Quan hệ:

- tenants 1—n tenant_users; users n—n tenants qua membership `tenant_users` với role/status riêng từng cửa hàng.
- tenants 1—n tenant_invitations; lời mời dùng một lần lưu hash token, role, người tạo/người nhận và trạng thái hạn/thu hồi.
- users 1—n account_tokens; account token xác minh email/đặt lại mật khẩu chỉ lưu hash, có purpose, expiry và trạng thái sử dụng.
- email_outbox là hàng đợi toàn nền tảng độc lập với tenant; payload người nhận/nội dung được mã hóa bằng key riêng, worker áp dụng lease, retry và expiry.
- Mỗi bản ghi customers, products, pets, invoices, invoice_items, invoice_refunds, invoice_refund_items, stock_movements và audit_events thuộc đúng một tenant.
- users 1—n invoices (người lập) và stock_movements (người ghi).
- customers 1—n invoices; customers 1—n pets đã mua.
- invoices 1—n invoice_items.
- invoices 1—n invoice_refunds; invoice_refunds 1—n invoice_refund_items.
- invoice_refund_items tham chiếu đúng invoice_item nguồn trong cùng tenant và invoice; stock_movements có thể liên kết về dòng hoàn tạo ra lượng nhập trả.
- products 1—n invoice_items; products 1—n stock_movements.
- pets 1—0..1 invoice_items; pets có buyer_id tới customers sau khi bán.
- invoices 1—n stock_movements do giao dịch bán tạo.

Một invoice_item dùng đúng một loại mặt hàng: product hoặc pet. Dòng sản phẩm có quantity nguyên dương; dòng thú cưng có quantity bằng 1. Hóa đơn lưu snapshot mã/tên/giá để thay đổi danh mục không làm đổi lịch sử.

Các khóa ngoại composite dùng `(tenant_id, id)` hoặc `(tenant_id, user_id)` để không thể gắn khách, thú cưng, sản phẩm, nhân viên hay hóa đơn từ tenant khác. Mã hàng và mã thú cưng có unique key theo tenant.

Thú cưng có trạng thái available/sold/inactive. Trước thanh toán buyer_id/sold_at rỗng; sau thanh toán chúng được gắn khách hàng và thời điểm bán. Nếu nhận lại thú cưng, hồ sơ được gỡ buyer/time và chuyển available hoặc inactive. Sản phẩm giữ số tồn hiện tại; mọi nhập/điều chỉnh/bán/nhận trả bán lại tạo stock_movement trong cùng transaction với thay đổi tồn.

Hóa đơn paid không bị sửa khi hoàn. Sổ hoàn tiền ghi khóa yêu cầu, phương thức, currency/giá/số lượng snapshot, số tiền, actor và disposition; tổng số lượng hoàn mỗi dòng không thể vượt số lượng bán. Hoàn tiền có thể một phần hoặc toàn bộ; ghi nhận thanh toán lại thực tế nằm ngoài hệ thống.

Hồ sơ `pets` còn lưu màu lông, màu mắt, tags ngoại hình, tên file ảnh local và descriptor JSON. Các thuộc tính ảnh không tạo bảng/quan hệ mới; AI Vision cũng không lưu dữ liệu nhận dạng bổ sung vào schema.
