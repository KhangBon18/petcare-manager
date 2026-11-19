# Ca nghiệm thu bản web cửa hàng

1. Admin và Staff đăng nhập được; mật khẩu sai bị từ chối; logout dùng POST/CSRF.
2. Staff bị chặn thao tác CRUD tài khoản, giá, tạo thú cưng và điều chỉnh tồn cả ở URL lẫn service.
3. Khóa/hạ quyền user trong DB làm phiên cũ mất quyền ngay request kế tiếp.
4. Seed chạy lại không tạo người dùng, sản phẩm, khách hoặc thú cưng trùng.
5. Thêm/sửa/tìm khách; khách inactive không dùng để lập hóa đơn, hóa đơn cũ vẫn xem được.
6. Thêm/sửa cá thể; ngày sinh tương lai, cân nặng sai, giá/quantity không nguyên hoặc âm bị chặn.
7. Tạo sản phẩm và điều chỉnh tồn có lý do; tồn không được âm.
8. Lập hóa đơn snapshot giá từ DB; sửa giá danh mục không đổi invoice đã lập.
9. Bán 2 sản phẩm 100.000 VND, 1 sản phẩm 50.000 VND và thú cưng 2.000.000 VND cho một khách mẫu tạo tổng 2.250.000 VND; trước thanh toán tồn và buyer chưa đổi.
10. Thanh toán cập nhật stock/movement/pet/invoice nguyên tử; thanh toán lại không thay đổi dữ liệu.
11. Hai giao dịch cạnh tranh cùng mua cá thể/hàng tồn cuối chỉ một giao dịch thành công.
12. Hủy unpaid không tăng tồn; paid không sửa/hủy; unpaid/cancelled không vào doanh thu.
13. Tổng client bị sửa, thiếu CSRF, GET gọi thao tác mutation, tên chứa HTML đều được xử lý an toàn.
14. Báo cáo khớp paid_at và ngày kết thúc; restart app/MySQL dữ liệu vẫn còn.
15. Cài theo README trên MySQL 8.0.16+; ghi riêng môi trường Windows nếu không thử trực tiếp.
16. Tài khoản đã đăng nhập hỏi trợ lý về tồn/sản phẩm/doanh thu; câu trả lời khớp dữ liệu hiện hành, endpoint AI để trống vẫn hoạt động cục bộ, request thiếu CSRF bị chặn.
17. Admin tải ảnh hợp lệ khi tạo/sửa hồ sơ; ảnh được chuẩn hóa, descriptor lưu trong MySQL và media lưu qua backend local hoặc S3-compatible; ảnh không hợp lệ/quá 5 MB bị từ chối.
17a. Admin tải ảnh sản phẩm JPEG/PNG/WebP; MySQL chỉ lưu tên file, ảnh chuẩn hóa lưu ngoài database và route ảnh yêu cầu đăng nhập.
18. Tìm bằng ảnh chỉ xếp hạng cá thể available; ảnh trùng khớp hồ sơ đứng đầu; nhân viên được tìm nhưng không được tạo/sửa hồ sơ.
19. Khi cấu hình AI Vision, trang hiển thị rõ ảnh sẽ được gửi ra endpoint; khi tắt, truy vấn chỉ xử lý local.
20. Với seed demo hiện tại, trợ lý local lọc chó/mèo theo giống, màu lông và mắt, giới tính và ngân sách; hỏi “mèo lông trắng mắt xanh dưới 5 triệu” phải đối chiếu các điều kiện độc lập với hồ sơ MySQL. Nguồn câu trả lời hiển thị là local khi chưa cấu hình endpoint.
21. Danh mục seed có 74 hồ sơ và 68 ảnh tổng hợp; tìm ảnh xếp hạng các thú cưng đang bán, ghi rõ điểm là tham khảo và không tuyên bố nhận diện vật thể. Chụp ảnh laptop/điện thoại theo quyền trình duyệt và thiết lập LAN đã bật.
22. Hỏi “Chó lông đen đang bán” phải tìm chó, còn “Cát vệ sinh còn mấy?” phải truy vấn sản phẩm/tồn kho, không bị nhầm “cát” thành mèo; câu “Cho tôi hỏi cách dùng” vẫn đi vào trợ giúp chung.
