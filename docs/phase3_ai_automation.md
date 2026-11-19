# Phase 3 — AI và Automation

Ngày cập nhật: 25/10/2026. Giữ Flask/Jinja/JavaScript thuần và MySQL hiện có; không thêm dịch vụ nền hoặc schema mới. Schema vẫn **20 bảng**. Module `petcare.i18n` đang làm dở được giữ nguyên; nội dung mới VI/EN dùng template/copy riêng.

## 3.1. Trợ lý có card thao tác

- Parser tách ý định, thời gian, giá và thuộc tính. Tra cứu loài/giống, màu lông/mắt, giới tính, tên/mã và giá được biên dịch thành SQL tham số hóa trên toàn danh mục đang bán của tenant; không lọc từ bản preview 100 sản phẩm/250 thú cưng.
- COUNT chạy trên toàn bộ tập khớp; LIMIT 12 chỉ giới hạn số card trả về. Các trường truy vấn, bảng và toán tử lấy từ danh sách cố định trong code; câu hỏi/LLM không được tạo SQL.
- JSON trả tổng số khớp, loại, ID, mã/tên, giá Decimal dạng chuỗi, trạng thái/tồn, ảnh riêng tư và đường dẫn hồ sơ do server tạo. Card sản phẩm mở trang chi tiết đọc được cả bởi Staff.
- Chế độ local hoạt động khi không cấu hình endpoint. Khi có LLM, chỉ gửi số đếm chính xác và tối đa 12 bản ghi liên quan, không gửi thông tin cá nhân khách hàng; card luôn lấy từ MySQL. Provider lỗi/timeout vẫn trả card và câu trả lời local.
- Gợi ý demo: “Hôm nay còn mèo nào?”, “Tìm mèo lông trắng dưới 3 triệu”, “Tìm sản phẩm thức ăn cho mèo”. “Dưới/trên” không bao gồm biên; “tối đa/tối thiểu/từ…đến…” có biên; “khoảng N” là ±10%.

## 3.2. Gợi ý bổ sung tồn kho

Chỉ lấy số lượng trong **hóa đơn paid**, theo ngày địa phương của cửa hàng, gồm hôm nay và 13/29 ngày trước:

- `rate14 = sold14 / 14`, `rate30 = sold30 / 30`.
- Ưu tiên rate14 khi sold14 > 0; nếu không có bán trong 14 ngày nhưng có trong 30 ngày thì dùng rate30.
- `days_left = stock × window / sold`. Không có bán trong 30 ngày thì days_left không xác định, dùng `reorder_level` làm fallback.
- Cảnh báo khi `stock <= reorder_level` hoặc `days_left <= 7`.
- Kế hoạch 14 ngày: `target = max(reorder_level + 1, ceil(sold × 14 / window))`; `suggested_qty = max(0, target - stock)`.
- Không có lịch sử: target = reorder_level + 1. Phép ceil dùng số nguyên để không phát sinh nhập dư do sai số của phân số như 5/14.

Dashboard ưu tiên tối đa 5 cảnh báo; trang Sản phẩm có danh sách cảnh báo và hồ sơ mỗi mặt hàng có giải thích đầy đủ. Gợi ý không tự nhập kho và chưa tính lead time nhà cung cấp, mùa vụ hoặc ngày hết hàng trong quá khứ. Chỉ điều chỉnh tồn qua luồng quản lý kho đã có.

## 3.3. Bản tin, biểu đồ, Excel và bản in

- Bộ lọc nhanh Hôm nay/7 ngày/30 ngày/Tháng này; ngày tùy chọn được diễn giải trong timezone tenant, khoảng UTC nửa mở.
- Biểu đồ SVG cục bộ, có tooltip và bảng ngày bao gồm cả ngày doanh thu bằng 0. So sánh kỳ trước cùng số ngày; nền bằng 0 hiển thị chưa có cơ sở so sánh, không tạo phần trăm vô hạn.
- Bản tin Python ghi số hóa đơn đã thu, thay đổi doanh thu, ngày cao nhất và mặt hàng bán chạy theo số lượng. Không phụ thuộc mạng/LLM.
- Một tập dữ liệu được dùng cho tổng, bảng ngày, chi tiết, bản tin và biểu đồ. Khi render, server ký một snapshot có người dùng/tenant, hiệu lực 15 phút. Nút Xuất Excel gửi snapshot qua POST có CSRF; file không truy vấn lại giao dịch nên khớp bản đang xem cả khi dữ liệu mới phát sinh. Muốn số mới, tải lại trang.
- Excel có 4 sheet: **Tong quan**, **Doanh thu ngay**, **Chi tiet**, **San pham ban chay**. Có tiêu đề, kỳ/timezone/thời điểm chốt, định dạng VNĐ/currency tenant, ngày có kiểu dữ liệu ngày, bộ lọc và cố định tiêu đề ở bảng chi tiết. Tên/mã được ghi dạng text, không thực thi công thức/hyperlink từ dữ liệu. Số tiền vượt độ chính xác 15 chữ số của Excel được giữ dạng text chính xác.
- `In / Lưu PDF` mở hộp thoại in trình duyệt; bỏ navigation/trợ lý/điều khiển, tự mở bảng chi tiết và khôi phục trạng thái sau khi in. Tồn kho là tại thời điểm chốt, không phải tồn cuối kỳ.
- Giới hạn MVP: tối đa 366 ngày và 5.000 dòng hàng mỗi báo cáo. Vượt giới hạn thì yêu cầu chọn kỳ ngắn hơn; không âm thầm cắt chi tiết.
- Dependency mới duy nhất của ứng dụng: `XlsxWriter>=3.2,<4.0`. Chạy `python -m pip install -r requirements.txt` trước khi khởi động trên máy khác.

## 3.4. Tìm ảnh và gợi ý thuộc tính

- Bộ lọc loài và available/sold/inactive/tất cả được áp dụng trong truy vấn MySQL trước khi xếp hạng. Danh mục đến 5.000 cá thể đang bán được quét chính xác theo lô để tránh bỏ sót do LSH; danh mục lớn hơn dùng chỉ mục LSH và giao diện báo rõ phạm vi xếp hạng có thể bỏ sót.
- Mỗi kết quả có điểm thành phần màu, cấu trúc sáng/tối và thuộc tính; nhãn giải thích tông màu lông trùng hoặc cấu trúc/màu ảnh gần nhau. Đây là xếp hạng tham khảo, không phải xác suất nhận dạng.
- Khi chọn ảnh ở form thêm/sửa pet, gợi ý xuất hiện tự động qua POST có CSRF, admin-only, giới hạn byte/pixel, quota và semaphore có sẵn. Ảnh phân tích không được lưu thành hồ sơ.
- Local chỉ ước lượng màu vùng ảnh, có thể gồm nền; không đoán loài/giống/mắt. Khi bật `AI_VISION_ENABLED=1` cùng endpoint/model, Vision gợi ý loài, giống khi đủ căn cứ, màu/hoa văn/độ dài lông, màu mắt, kích cỡ và dáng; bộ so khớp chuẩn hóa synonym Việt/Anh và đối chiếu với hồ sơ cửa hàng. Lỗi mạng, JSON hỏng hoặc nội dung trống quay về màu local với thông báo.
- Người dùng bấm **Điền vào trường đang trống** để áp dụng; không ghi đè trường đã nhập. AbortController bỏ yêu cầu cũ khi đổi ảnh. Lưu hồ sơ vẫn qua service validation/transaction hiện có.

## Nghiệm thu

Xem `docs/test_results.md` và `docs/demo_scenarios.md`. Bộ test dùng MySQL `_test` riêng; kiểm thử LLM/Vision có phản hồi mô phỏng và lỗi mạng, không khẳng định đã nghiệm thu nhà cung cấp AI trực tuyến khi chưa cấu hình endpoint thật.
