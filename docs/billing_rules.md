# Quy tắc hóa đơn và tồn kho

1. Chỉ khách hàng đang hoạt động được dùng cho hóa đơn mới.
2. Server đọc sản phẩm/thú cưng và giá từ MySQL; không nhận tổng tiền do trình duyệt gửi.
3. Hóa đơn unpaid lưu snapshot giá/tên nhưng chưa trừ kho hay gắn buyer.
4. Trước thanh toán, InnoDB khóa hóa đơn; khóa product/pet theo id ổn định; xác thực lại status, active, stock và sale_status.
5. Một transaction giảm stock_qty, thêm stock_movement, chuyển thú cưng sang sold/gắn người mua, rồi đánh dấu invoice paid với paid_at.
6. Khi lỗi, rollback tất cả. Hóa đơn thanh toán lặp trả already_paid, không tạo doanh thu hoặc thay đổi tồn lần hai.
7. Unpaid có thể hủy; dòng snapshot được giữ, kho không đổi. Paid không thể sửa hoặc hủy.
8. Mọi điều chỉnh tồn có lý do. Transaction khóa dòng sản phẩm để ghi đúng tồn trước/sau; cập nhật số lượng, stock movement và audit event cùng một transaction.
9. Tồn kho nằm trong giới hạn kiểu MySQL `INT` có dấu: 0–2.147.483.647. Thao tác vượt giới hạn hoặc làm tồn âm bị từ chối trước khi ghi movement/audit.
10. Không sửa tồn bằng form giá; không xóa cứng dữ liệu có tham chiếu.
11. Báo cáo tính doanh thu theo paid_at trong khoảng [đầu ngày, đầu ngày sau ngày cuối]. Hóa đơn unpaid/cancelled bị loại.
