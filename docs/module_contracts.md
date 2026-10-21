# Hợp đồng module web cửa hàng

## AuthService

- authenticate(username, password): trả user tối thiểu hoặc None; mật khẩu so bằng hash.
- load_active_user(user_id): tải lại trạng thái active/role từ MySQL; không giữ hash trong session.
- create_user/update_user/list_users: admin-only, mật khẩu mới phải băm, không khóa admin hoạt động cuối cùng hoặc tự khóa mình.

## CustomerService

- list_customers(actor_id, search, include_inactive): khách được tìm theo tên/SĐT.
- create_customer/update_customer(actor_id, data): kiểm tra họ tên, điện thoại, địa chỉ.
- set_active(actor_id, customer_id, active): ngừng dùng mềm, không xóa lịch sử.

## ProductService

- create_product(actor_id, data): admin-only; tạo sản phẩm cùng movement tồn đầu nếu > 0.
- update_product: chỉ cập nhật mã/tên/danh mục/giá; không sửa tồn.
- adjust_stock(actor_id, product_id, data): admin-only; delta khác 0, lý do bắt buộc, tồn không âm, movement cùng transaction.
- list_products/get_product: truy vấn sản phẩm và lịch sử tồn.

## PetService

- create_pet/update_pet: admin-only; mỗi hàng là một cá thể để bán.
- Ngày sinh phải hợp lệ/không tương lai; cân nặng dương; giá Decimal không âm theo precision của currency tenant.
- set_inactive chỉ tác động available/inactive; cá thể sold không chỉnh/sửa/đổi người mua.

## InvoiceService

- create_invoice(actor_id, data, items): khách active, ít nhất một mặt hàng; đọc giá từ MySQL và tạo snapshot. Unpaid chưa trừ tồn.
- pay_invoice(actor_id, invoice_id): lock hóa đơn, mặt hàng theo thứ tự ổn định; kiểm tra lại active/stock/available; giảm tồn, ghi movement, gắn buyer và paid trong một transaction.
- Kết quả đã trả: already_paid; không lặp tác dụng.
- cancel_invoice chỉ hủy unpaid; giữ snapshot dòng hóa đơn.

## ReportService

- dashboard(actor_id): tổng quan tồn, khách, thú cưng và doanh thu hôm nay.
- report(actor_id, start, end): doanh thu và hóa đơn paid theo paid_at, top sản phẩm, số thú cưng đã bán và tồn.

## AssistantService và PetImageService

- `answer(actor_id, question, history)`: yêu cầu người dùng đang active; context chỉ gồm số liệu cửa hàng, tồn kho, danh mục sản phẩm và thuộc tính thú cưng; dùng bộ trả lời local hoặc endpoint đã cấu hình.
- `search_similar(actor_id, image_bytes)`: chỉ lấy thú cưng available; xác thực/chuẩn hóa ảnh, xếp hạng theo descriptor hồ sơ và metadata; model vision chỉ được gọi khi endpoint có cấu hình và `AI_VISION_ENABLED=1`.
- Ảnh chuẩn hóa được lưu bằng UUID có tiền tố tenant cho upload mới qua backend local/S3-compatible; object S3 được đặt dưới namespace cửa hàng. Tên UUID cũ vẫn đọc được. MySQL giữ descriptor để tìm; photo route xác thực quyền tenant và khớp namespace trước khi đọc. Thay ảnh cập nhật DB trước khi dọn file cũ; dọn ảnh cũ chỉ khi DB xác nhận không còn bản ghi nào tham chiếu.

## Repository và transaction

Repository nhận kết nối và không commit. Service dùng petcare.database.connection.transaction() cho mọi luồng nhiều bước. Placeholder MySQL là %s. Các thao tác mutation xác minh actor từ bảng users trong DB.
