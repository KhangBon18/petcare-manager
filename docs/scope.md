# Phạm vi PetCare Manager — phiên bản cửa hàng

## Trong phạm vi

- Python + Flask; Jinja HTML, CSS và JavaScript thuần.
- MySQL 8.0.16+, InnoDB, utf8mb4.
- Người dùng Admin/Staff, phiên đăng nhập và phân quyền theo trạng thái hiện hành trong DB.
- Khách hàng và lịch sử mua hàng.
- Từng cá thể thú cưng đang bán, giá riêng, trạng thái available/sold/inactive và người mua sau khi thanh toán.
- Sản phẩm có mã, danh mục, giá theo currency cửa hàng, tồn kho và lịch sử điều chỉnh.
- Hóa đơn gồm sản phẩm số lượng nguyên và thú cưng đơn chiếc; snapshot giá/tên; thanh toán hoặc hủy unpaid.
- Dashboard và báo cáo doanh thu theo paid_at, sản phẩm bán chạy, thú cưng đã bán, tồn kho.
- Trợ lý hỏi đáp cửa hàng dựa trên context tổng hợp; endpoint AI tương thích OpenAI là tùy chọn.
- Ảnh hồ sơ thú cưng, trường màu lông/mắt/đặc điểm và trang xếp hạng ảnh tương tự; phân tích AI Vision opt-in.
- Giao diện responsive tiếng Việt, chạy cục bộ.

## Ngoài phạm vi phiên bản đầu

Không có khám, tiêm, lịch hẹn chăm sóc, dịch vụ spa, lịch nhắc, thanh toán online, tài khoản mua hàng công khai, triển khai Internet, detector/embedding thị giác đã huấn luyện, nhà cung cấp, đặt hàng online, PDF hoặc email/SMS. AI tạo sinh và AI Vision cần endpoint do người vận hành cấu hình; cấu hình trống vẫn hỗ trợ demo cục bộ.

## Nguyên tắc dữ liệu

Dùng database riêng petcare_shop_dev. Không chuyển clinic SQLite hay bản dump cũ tự động. Không ghi dữ liệu cá nhân vào seed. Hóa đơn đã trả và lịch sử tồn được bảo toàn.
