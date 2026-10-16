# Kịch bản Dùng thử & Báo cáo Demo (demo_scenarios.md)

Tài liệu này cung cấp kịch bản demo mẫu từng bước giúp 4 thành viên (Khang, Quân, Quý, Nhàn) tự tin trình diễn và bảo vệ đồ án trước giảng viên.

---

## 1. Chuẩn bị Trước Buổi Báo cáo

Mở terminal tại thư mục dự án và khởi động ứng dụng:
```bash
# macOS
.venv/bin/python main.py

# Windows PowerShell
.venv\Scripts\python.exe main.py
```

Tài khoản sử dụng:
- **Admin**: `admin` / `Admin@123`
- **Nhân viên**: `staff1` / `Staff@123`

---

## 2. Kịch bản Trình diễn 4 Phân cảnh

### Phân cảnh 1: Đăng nhập, An toàn Mật khẩu & Phân quyền (Khang trình bày)
1. Mở màn hình đăng nhập, cố tình nhập sai mật khẩu để giảng viên thấy hệ thống báo lỗi rõ ràng.
2. Đăng nhập tài khoản `admin` / `Admin@123`.
3. Giải thích:
   - Mật khẩu được băm bằng PBKDF2-HMAC-SHA256, 100.000 vòng lặp kèm salt ngẫu nhiên, hoàn toàn không lưu plaintext trong SQLite.
   - Khi ở tài khoản Admin, thanh điều hướng bên trái hiển thị đầy đủ mục **"👥 Quản lý Tài khoản"** và **"⚙️ Bảng giá"** cho phép thêm/sửa dịch vụ và đổi giá.
4. Đăng xuất, đăng nhập lại bằng tài khoản `staff1` / `Staff@123`.
   - Mục Tài khoản tự động ẩn khỏi menu điều hướng.
   - Vào mục Bảng giá: Nút thêm/sửa giá bị ẩn; nếu nhân viên cố tình gọi code nghiệp vụ bên dưới cũng sẽ bị chặn tại Service layer (`PermissionError`).

---

### Phân cảnh 2: Tiếp nhận Khách hàng Lan & Thú cưng Miu (Quân trình bày)
1. Nhấn vào mục **"🐾 Chủ nuôi"**:
   - Thao tác tìm kiếm nhanh theo tên hoặc số điện thoại.
   - Nhấn **"+ Thêm chủ nuôi"**: Nhập chị `Nguyễn Thị Lan`, SĐT `0901234567`, Địa chỉ `123 Nguyễn Huệ, Quận 1`.
2. Nhấn nút **"Xem thú cưng của chủ"** hoặc chuyển sang tab **"🐶 Thú cưng"**:
   - Nhấn **"+ Thêm thú cưng"**: Chọn chủ là chị Lan, tên `Miu`, loài `Mèo`, giống `Mèo Anh lông ngắn`, giới tính `Cái`, cân nặng `3.5` kg, ngày sinh `2024-03-15`.
   - Thử nghiệm ngoại lệ: Nếu nhập cân nặng âm hoặc ngày sinh tương lai, hệ thống từ chối ngay.
3. Nhấp đúp vào Miu để mở **"Hồ sơ tổng hợp (PetProfileView)"**:
   - Hiển thị đầy đủ thông tin cá nhân và 4 tab lịch sử (hiện tại chưa có ca khám nào).

---

### Phân cảnh 3: Khám bệnh, Tiêm phòng & Lịch hẹn (Quý trình bày)
1. Nhấn vào mục **"📅 Lịch hẹn"**:
   - Nhấn **"+ Đặt lịch hẹn mới"**: Chọn Miu, loại dịch vụ `Khám tổng quát & Tiêm phòng`.
   - Nhấn mạnh với thầy cô: *Lịch hẹn này chỉ lưu thời gian dự kiến tiếp đón, hoàn toàn không phát sinh chi phí hay tạo lượt dịch vụ trước*.
2. Nhấn vào mục **"🩺 Khám bệnh"**:
   - Nhấn **"+ Ghi nhận ca khám mới"**: Chọn Miu, gói dịch vụ `Khám bệnh tổng quát` (150.000 đ), triệu chứng `Hắt hơi nhẹ`, chẩn đoán `Viêm đường hô hấp trên`, kê đơn `Thuốc nhỏ mũi và men vi sinh`.
   - Nhấn Lưu: Giải thích kiến trúc giao dịch kép — Hệ thống vừa tạo bệnh án vừa tự động tạo 1 bản ghi `service_visits` với giá 150.000 đ trong cùng 1 transaction.
3. Nhấn vào mục **"💉 Tiêm phòng"**:
   - Nhấn **"+ Ghi nhận mũi tiêm mới"**: Chọn Miu, gói `Tiêm vaccine Dại` (180.000 đ), tên vaccine `Rabisin`, ngày hẹn tiêm nhắc lại sau 1 năm.
   - Chỉ cho thầy cô thấy bảng **"Lịch nhắc tiêm phòng đến hạn"** đã ghi nhận và có nút Đánh dấu đã xử lý nhắc nhở.
4. Nhấn vào mục **"📋 Lượt dịch vụ"**:
   - Nhấn **"+ Ghi nhận dịch vụ Chăm sóc / Spa"**: Chọn Miu làm thêm dịch vụ `Tắm vệ sinh & Cắt tỉa lông` (200.000 đ).
   - Danh sách lượt dịch vụ hiển thị rõ 3 lượt của Miu đang ở trạng thái **"Chưa tính tiền"**.

---

### Phân cảnh 4: Lập Hóa đơn, Thanh toán & Thống kê Doanh thu (Nhàn trình bày)
1. Nhấn vào mục **"💳 Hóa đơn"**:
   - Nhấn **"+ Lập hóa đơn mới"**: Chọn khách hàng `Nguyễn Thị Lan`.
   - Bảng bên dưới tự động nạp chính xác 3 lượt chưa tính tiền của Miu (150k + 180k + 200k).
   - Nhấn **"Tạo hóa đơn"**: Tổng tiền được tính đúng là `530.000 đ`, trạng thái `unpaid`.
   - Kiểm tra lại danh sách lượt chưa tính tiền của chị Lan: Đã trở về 0.
2. Thử nghiệm tính toàn vẹn:
   - Thử cố tình tạo hóa đơn lần 2 với các lượt này -> Bị chặn với lỗi `Lượt dịch vụ đã được lập hóa đơn trước đó`.
3. Thực hiện thanh toán trực tiếp:
   - Chọn hóa đơn của chị Lan, nhấn **"Thanh toán trực tiếp"** -> Xác nhận thu tiền tại quầy.
   - Hóa đơn chuyển sang trạng thái `paid`, lưu thời gian thanh toán `paid_at`.
   - Nhấn Thanh toán lại -> Báo `Hóa đơn đã được thanh toán trước đó`, không cộng dồn tiền.
   - Nhấn Hủy hóa đơn -> Hệ thống từ chối vì hóa đơn `paid` là bất biến.
4. Nhấn vào mục **"📊 Thống kê"**:
   - Chọn xem báo cáo hôm nay.
   - Thầy cô đối chiếu số liệu:
     - Doanh thu thực thu khớp đúng số tiền các đơn đã thanh toán.
     - Lượt khám bệnh tăng thêm 1.
     - Số thú cưng tiêm phòng ghi nhận mèo Miu.
     - Top dịch vụ phổ biến xếp hạng đúng các dịch vụ vừa thanh toán.

---

## 3. Câu hỏi Phản biện Thường gặp & Cách Trả lời

**Q1: Tại sao không gộp bảng examinations và vaccinations vào bảng service_visits?**
> *Trả lời*: Bảng `service_visits` đóng vai trò là bảng dòng chi phí chung (ledger) cho mọi hoạt động có thu phí (khám, tiêm, tắm spa, siêu âm). `examinations` lưu đặc thù y khoa (triệu chứng, chẩn đoán, thuốc), còn `vaccinations` lưu đặc thù tiêm chủng (tên vaccine, hạn nhắc lại). Tách riêng giúp dữ liệu chuẩn hóa, quan hệ 1-1 qua `visit_id UNIQUE` vừa đảm bảo tính module hóa vừa bảo đảm tính toàn vẹn.

**Q2: Nếu cửa hàng đổi giá dịch vụ thì các hóa đơn trong quá khứ có bị sai không?**
> *Trả lời*: Không bị sai. Khi tạo lượt dịch vụ, giá tại thời điểm đó được snapshot cố định vào `service_visits.unit_price_vnd`. Khi lập hóa đơn, giá và tên dịch vụ lại được snapshot vào `invoice_items`. Việc đổi giá trong danh mục `services` chỉ áp dụng cho các lượt dịch vụ phát sinh sau này.

**Q3: Cơ sở dữ liệu có bị mất khi tắt ứng dụng không?**
> *Trả lời*: Dữ liệu được lưu trữ thật trên ổ đĩa tại file `data/petcare.db` theo chuẩn SQLite ACID. Mọi giao dịch đều được commit và mở lại ứng dụng vẫn đọc đầy đủ 100%.
