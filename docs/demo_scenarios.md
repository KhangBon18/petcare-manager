# Demo nhanh — cửa hàng thú cưng

Dùng MySQL database local mới, chạy initialize và seed. Nếu database `_dev` đã có, chạy seed lại để bổ sung 64 hồ sơ chó/mèo và ảnh mới. Đăng nhập admin / Admin@123.

1. Mở Sản phẩm: kiểm tra danh mục nhiều nhóm, mã hàng, mô tả, giá, tồn và ngưỡng cảnh báo.
2. Mở Thú cưng: xem danh mục 74 hồ sơ (35 chó, 37 mèo, 1 thỏ, 1 hamster); Miu mã PET-001 đang bán với giá 2.000.000 VND.
3. Lập hóa đơn cho Khách demo 01: 2 thức ăn, 1 phụ kiện, 1 Miu.
4. Kiểm tra tổng 2.250.000 VND và trạng thái chưa thanh toán.
5. Ghi lại tồn đang hiển thị, thanh toán; xác nhận tồn giảm đúng và Miu đã bán cho Khách demo 01.
6. Gửi lại thanh toán; thấy thông báo đã xử lý trước đó, không tăng doanh thu.
7. Mở báo cáo; lọc ngày hôm nay và đối chiếu giao dịch vừa thanh toán cùng các giao dịch demo lịch sử.
8. Trước khi thanh toán hóa đơn, mở **Hỏi trợ lý** và hỏi “Sản phẩm nào sắp hết?”, “Doanh thu tháng này là bao nhiêu?”, “Có mèo lông trắng dưới 5 triệu không?” và “Tìm sản phẩm thức ăn cho mèo”. Đối chiếu dữ liệu với Sản phẩm/Báo cáo. Chế độ local dùng MySQL và không cần API key.
9. Mở **Tìm bằng ảnh**, chọn một trong 68 hồ sơ có ảnh, tải ảnh hoặc chụp bằng camera laptop/điện thoại. Kết quả xếp hạng tham khảo theo màu và bố cục ảnh; đây chưa phải nhận diện vật thể bằng mô hình.
10. Các hồ sơ và ảnh demo được tạo tổng hợp bằng AI, là dữ liệu hư cấu; không chạy seed trên production.

Để demo phân tích ngôn ngữ/ảnh bằng mô hình, cấu hình endpoint chat-completions trong `.env`; bật `AI_VISION_ENABLED=1` chỉ với endpoint hỗ trợ vision. Nếu chưa cấu hình, giao diện ghi rõ đang dùng tra cứu local; trợ lý vẫn trả lời theo dữ liệu MySQL và tìm ảnh vẫn xếp hạng ảnh hồ sơ.
