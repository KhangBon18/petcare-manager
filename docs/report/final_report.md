# Báo cáo Tổng kết Đồ án PetCare Manager (final_report.md)

- **Đề tài**: Xây dựng ứng dụng quản lý phòng khám & chăm sóc thú cưng (PetCare Manager).
- **Công nghệ**: Python 3.10 - 3.13, Tkinter/ttk, SQLite 3.
- **Nhóm sinh viên thực hiện**: Khang, Quân, Quý, Nhàn.
- **Tỷ lệ đóng góp mục tiêu & thực tế**: 25% mỗi thành viên (Tổng 100%).

---

## 1. Giới thiệu Đề tài & Mục tiêu

Phòng khám thú cưng hiện đại đòi hỏi một hệ thống quản lý tập trung từ khâu tiếp nhận khách hàng, quản lý hồ sơ thú cưng, theo dõi lịch khám bệnh và tiêm chủng định kỳ, cho đến lập hóa đơn và thống kê doanh thu.

Đồ án **PetCare Manager** giải quyết trọn vẹn bài toán này bằng ứng dụng desktop trực quan, bảo mật cao, hoạt động độc lập trên cả Windows và macOS với cơ sở dữ liệu SQLite cục bộ tuân thủ chuẩn ACID.

---

## 2. Kiến trúc & Công nghệ Sử dụng

1. **Mô hình 3 lớp phân tầng**:
   - `UI Layer`: Tkinter và ttk, giao diện tiếng Việt thân thiện, một `tk.Tk` root duy nhất, điều hướng Frame mượt mà. Tuyệt đối không chứa SQL trong callback giao diện.
   - `Service Layer`: Xử lý toàn bộ logic nghiệp vụ, xác thực dữ liệu đầu vào, phân quyền Admin/Nhân viên, điều phối transaction (`commit`/`rollback`).
   - `Repository Layer`: Thực thi các truy vấn SQL có tham số an toàn (`?`), nhận kết nối `conn` từ Service và không tự ý kết thúc transaction.
2. **Bảo mật**:
   - Mật khẩu băm bằng `PBKDF2-HMAC-SHA256` với 100.000 vòng lặp và salt ngẫu nhiên 16 bytes.
   - Phiên đăng nhập `AuthSession` bất biến, không lộ hash mật khẩu.
   - Cơ chế bảo vệ Admin hoạt động cuối cùng của hệ thống.
3. **Quản lý Tiền tệ & Hóa đơn**:
   - Lưu trữ số nguyên (`INTEGER`) đơn vị VND.
   - Giao dịch kép: Tạo bệnh án (khám/tiêm) luôn đồng thời tạo lượt dịch vụ liên kết trong cùng 1 transaction.
   - Ràng buộc `visit_id UNIQUE` đảm bảo mỗi lượt dịch vụ chỉ được xuất hiện trên một hóa đơn duy nhất.
   - Hóa đơn đã thanh toán (`paid`) là bất biến. Thanh toán lặp trả về `already_paid`. Hủy hóa đơn `unpaid` giải phóng các lượt dịch vụ.

---

## 3. Kết quả Triển khai & Kiểm định Nghiệm thu

- **Chức năng**: Hoàn thành 100% phạm vi bắt buộc theo `REPO_GUIDE.md`:
  - Đăng nhập & phân quyền (Admin, Staff).
  - Quản lý Chủ nuôi & Thú cưng, bảo vệ lịch sử (`active=0` thay vì xóa).
  - Khám bệnh, Tiêm phòng, Lịch nhắc đến hạn trong 30 ngày.
  - Lịch hẹn tiếp đón (không sinh phí trước).
  - Danh mục dịch vụ và quản lý giá niêm yết.
  - Lập hóa đơn, thanh toán trực tiếp tại quầy, hủy đơn chưa thanh toán.
  - Báo cáo thống kê: Doanh thu thực thu, số ca khám, thú cưng tiêm phòng, cơ cấu loài, top dịch vụ.
- **Kiểm thử tự động**:
  - `python3 -m unittest discover -s tests -v`: **34/34 tests đạt 100% tỷ lệ pass**.
  - Kiểm thử tích hợp trọn vẹn kịch bản Lan & Miu (`tests/test_integration_flow.py`).
  - Kiểm thử khởi tạo giao diện và chuyển đổi 10 màn hình (`tests/test_ui_navigation.py`).
- **Idempotency**: Khởi tạo database (`initialize.py`) và nạp dữ liệu mẫu (`seed.py`) chạy lặp nhiều lần không lỗi, không nhân đôi bản ghi.

---

## 4. Phân công Công việc & Đóng góp Thực tế

| Thành viên | Trách nhiệm chính | Tỷ lệ đóng góp |
|---|---|---|
| **Khang** | Điều phối, kiến trúc app, bảo mật PBKDF2, đăng nhập/phiên/quyền, chủ nuôi, theme, hồ sơ tổng hợp | 25% |
| **Quân** | Thú cưng, tiêm phòng & lịch nhắc, ràng buộc ngày/cân nặng, sơ đồ ERD, từ điển dữ liệu | 25% |
| **Quý** | Danh mục dịch vụ, bảng giá, khám bệnh, lịch hẹn, thống kê tổng hợp, ca nghiệm thu, kịch bản demo | 25% |
| **Nhàn** | Kết nối DB, transaction, schema, initialize, seed, lượt dịch vụ, hóa đơn, doanh thu, sao lưu/phục hồi | 25% |

---

## 5. Kết luận & Hướng Phát triển

Đồ án PetCare Manager đã hoàn thành xuất sắc toàn bộ các mục tiêu đặt ra, đạt chuẩn chất lượng mã nguồn cao, tài liệu đầy đủ và sẵn sàng để nghiệm thu, bàn giao phiên bản v1.0.0.

Hướng phát triển tiếp theo sau khi nghiệm thu v1.0.0 bao gồm:
1. Trực quan hóa số liệu doanh thu bằng biểu đồ `matplotlib`.
2. Quản lý ảnh chụp chân dung thú cưng.
3. Xuất hóa đơn ra định dạng PDF hoặc gửi nhắc nhở tiêm phòng qua SMS/Email.
