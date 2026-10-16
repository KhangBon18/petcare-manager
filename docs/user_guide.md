# Hướng dẫn Sử dụng Phần mềm (user_guide.md)

Chào mừng bạn đến với tài liệu hướng dẫn sử dụng phần mềm **PetCare Manager**. Phần mềm cung cấp giao diện đồ họa tiếng Việt dễ thao tác, giúp tối ưu hóa công tác quản lý phòng khám và spa thú cưng.

---

## 1. Đăng nhập Hệ thống

1. Khởi chạy phần mềm (`python main.py`).
2. Màn hình đăng nhập xuất hiện ở chính giữa.
3. Nhập tên đăng nhập và mật khẩu:
   - Quản trị viên: `admin` / `Admin@123`
   - Nhân viên lễ tân/bác sĩ: `staff1` / `Staff@123`
4. Nhấn phím `Enter` hoặc click nút **"Đăng nhập"**.

---

## 2. Quản lý Chủ nuôi & Thú cưng

### Thêm Chủ nuôi Mới:
1. Nhấp chọn mục **"🐾 Chủ nuôi"** trên thanh menu bên trái.
2. Bấm nút **"+ Thêm chủ nuôi"**.
3. Điền họ và tên, số điện thoại (từ 8 đến 15 chữ số), địa chỉ.
4. Bấm **"Lưu thông tin"**.

### Thêm Thú cưng:
1. Nhấp chọn mục **"🐶 Thú cưng"**.
2. Bấm nút **"+ Thêm thú cưng"**.
3. Chọn chủ nuôi từ danh sách, nhập tên thú cưng, chọn loài (Chó, Mèo,...), giống, giới tính, cân nặng và ngày sinh.
4. Bấm **"Lưu thông tin thú cưng"**.

### Xem Hồ sơ Bệnh án Tổng hợp:
- Nhấp đúp vào bất kỳ thú cưng nào trên bảng danh sách, hoặc chọn thú cưng và bấm **"Xem hồ sơ tổng hợp"**.
- Cửa sổ hồ sơ bệnh án hiển thị 4 tab:
  - **Khám bệnh**: Triệu chứng, chẩn đoán, đơn thuốc và chi phí.
  - **Tiêm phòng**: Tên vaccine, ngày tiêm, ngày hẹn tiêm nhắc lại.
  - **Lịch hẹn**: Các cuộc hẹn khám hoặc chăm sóc.
  - **Lượt Dịch vụ & Chi phí**: Tổng hợp tất cả các dịch vụ đã sử dụng.

---

## 3. Khám bệnh, Tiêm phòng & Lịch hẹn

### Ghi nhận Ca Khám bệnh:
1. Vào mục **"🩺 Khám bệnh"** -> Bấm **"+ Ghi nhận ca khám mới"**.
2. Chọn thú cưng, chọn gói dịch vụ khám (giá tiền tự động hiển thị).
3. Nhập triệu chứng, chẩn đoán và đơn thuốc điều trị.
4. Bấm **"Lưu hồ sơ khám bệnh"**. Hệ thống tự động ghi nhận bệnh án và đồng bộ 1 lượt tính phí dịch vụ.

### Ghi nhận Tiêm phòng & Theo dõi Lịch nhắc:
1. Vào mục **"💉 Tiêm phòng"** -> Bấm **"+ Ghi nhận mũi tiêm mới"**.
2. Chọn thú cưng, gói dịch vụ tiêm, tên vaccine cụ thể (ví dụ: Rabisin) và ngày hẹn tiêm nhắc lại.
3. Bấm **"Lưu hồ sơ tiêm phòng"**.
4. Các mũi tiêm sắp đến hạn (trong vòng 30 ngày) sẽ tự động xuất hiện ở bảng trên cùng. Khi khách hàng đưa thú cưng đến tiêm nhắc lại, chọn dòng đó và bấm **"Đánh dấu đã xử lý nhắc"**.

### Đặt Lịch hẹn:
1. Vào mục **"📅 Lịch hẹn"** -> Bấm **"+ Đặt lịch hẹn mới"**.
2. Chọn thú cưng, loại dịch vụ hẹn (Khám, Tiêm, Tắm spa) và thời gian hẹn.
3. Bấm **"Xác nhận đặt lịch"**.
4. Khi khách hàng đến đúng hẹn, bấm **"Đánh dấu Hoàn thành"**.

---

## 4. Lập Hóa đơn & Thu ngân

1. Vào mục **"💳 Hóa đơn"** -> Bấm **"+ Lập hóa đơn mới"**.
2. Chọn khách hàng (chủ nuôi).
3. Bảng bên dưới sẽ tự động hiển thị danh sách tất cả các lượt dịch vụ chưa thanh toán của khách hàng đó.
4. Có thể chọn một hoặc nhiều lượt dịch vụ để thanh toán. Tổng tiền tạm tính sẽ tự động cộng dồn.
5. Bấm **"Tạo hóa đơn"**. Hóa đơn được tạo với trạng thái **"Chưa thanh toán"** (`unpaid`).
6. Khi khách hàng thanh toán tại quầy:
   - Chọn hóa đơn trong danh sách -> Bấm **"Thanh toán trực tiếp"** -> Xác nhận thu tiền.
   - Hóa đơn chuyển sang trạng thái **"Đã thanh toán"** (`paid`) và ghi nhận thời điểm thanh toán.
7. Nếu khách hàng chưa thanh toán và muốn chỉnh sửa lại: Chọn hóa đơn -> Bấm **"Hủy hóa đơn (Unpaid)"** để giải phóng các lượt dịch vụ lập lại.

---

## 5. Thống kê & Báo cáo Doanh thu

1. Vào mục **"📊 Thống kê"**.
2. Chọn khoảng ngày cần xem báo cáo (hoặc bấm nhanh nút **"Hôm nay"**, **"Tháng này"**).
3. Bấm **"Xem báo cáo"**.
4. Hệ thống phân tích và hiển thị:
   - **Doanh thu thực thu**: Tổng số tiền thực tế đã thu từ các hóa đơn đã thanh toán.
   - **Số hóa đơn thanh toán**: Số lượng giao dịch hoàn tất.
   - **Số lượt khám bệnh**: Tổng số ca bệnh án trong kỳ.
   - **Thú cưng tiêm phòng**: Số lượng thú cưng duy nhất đã được bảo vệ bằng vaccine.
   - **Phân bố theo loài**: Tỷ lệ phần trăm và số lượng chó, mèo.
   - **Top dịch vụ phổ biến**: Danh sách dịch vụ mang lại doanh thu cao nhất.
