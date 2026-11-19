# Phạm vi Dự án (scope.md)

Tài liệu này xác định ranh giới phạm vi triển khai cho phiên bản v1.0.0 của PetCare Manager.

---

## 1. Phạm vi Bắt buộc (In-Scope - Đã hoàn thành 100%)

- **Nền tảng**: Python 3.10 - 3.13, Tkinter/ttk, SQLite 3. Chạy cục bộ trên Windows và macOS.
- **Xác thực & Người dùng**:
  - Đăng nhập phiên làm việc, phân quyền `admin` và `staff`.
  - Quản lý tài khoản người dùng, đổi mật khẩu, băm mật khẩu PBKDF2-HMAC-SHA256 với salt ngẫu nhiên.
  - Bảo vệ tài khoản Quản trị viên hoạt động duy nhất.
- **Khách hàng & Bệnh nhân**:
  - Quản lý chủ nuôi (`owners`), kiểm tra tính hợp lệ số điện thoại, địa chỉ.
  - Quản lý thú cưng (`pets`), kiểm tra ngày sinh, cân nặng không âm, chủ sở hữu phải tồn tại và đang hoạt động.
  - Xem hồ sơ bệnh án tổng hợp (`PetProfileView`) với 4 tab: Khám, Tiêm, Hẹn, Chi phí.
  - Cơ chế ngừng theo dõi (`active=0`) thay vì xóa vật lý khi có dữ liệu lịch sử liên kết.
- **Y tế & Chăm sóc**:
  - Quản lý danh mục dịch vụ và giá niêm yết (chỉ Admin được thêm/sửa/đổi giá).
  - Hồ sơ khám bệnh (`examinations`): triệu chứng, chẩn đoán, thuốc; tạo lượt dịch vụ `service_visits` trong cùng transaction.
  - Tiêm phòng (`vaccinations`): tên vaccine, ngày tiêm, ngày hẹn tiêm nhắc; tạo lượt dịch vụ trong cùng transaction. Bảng theo dõi nhắc nhở đến hạn trong 30 ngày.
  - Lịch hẹn (`appointments`): lên lịch khám/spa, cập nhật trạng thái `planned`/`completed`/`cancelled`, không tự phát sinh phí.
  - Lượt dịch vụ (`service_visits`): ghi nhận trực tiếp dịch vụ chăm sóc/tắm spa/xét nghiệm.
- **Tài chính & Thu ngân**:
  - Lập hóa đơn (`invoices`): gom các lượt chưa tính tiền của cùng một chủ nuôi.
  - Ràng buộc tính phí một lần: mỗi lượt chỉ xuất hiện trên đúng một hóa đơn (`visit_id UNIQUE`).
  - Thanh toán trực tiếp tại quầy: chuyển sang `paid`, ghi nhận `paid_at`. Thanh toán lặp trả về `already_paid`.
  - Hủy hóa đơn `unpaid`: xóa chi tiết `invoice_items` để giải phóng `visit_id`, giữ header `cancelled`.
  - Bảo vệ hóa đơn `paid`: bất biến, cấm sửa và cấm hủy.
- **Báo cáo Thống kê**:
  - Doanh thu thực thu chỉ tính từ các hóa đơn đã thanh toán theo ngày `paid_at`.
  - Thống kê số hóa đơn hoàn tất, số ca khám bệnh, số lượng thú cưng duy nhất đã tiêm phòng.
  - Phân bố thú cưng theo loài, danh sách dịch vụ phổ biến nhất.

---

## 2. Phạm vi Ngoài Dự án / Hướng Phát triển Tương lai (Out-of-Scope)

- **Không mở rộng web/cloud/mobile**: Dự án tập trung hoàn thiện desktop app cục bộ.
- **Không tích hợp cổng thanh toán trực tuyến** (MoMo, VNPay, Stripe,...): Chỉ hỗ trợ thanh toán trực tiếp tại quầy.
- **Không quản lý xuất nhập tồn kho thuốc nâng cao**: Thuốc điều trị lưu trữ dưới dạng văn bản chỉ định trong hồ sơ khám.
- **Tính năng mở rộng đề xuất giai đoạn 2**:
  - Tích hợp biểu đồ trực quan hóa matplotlib.
  - Quản lý ảnh chụp thú cưng (`assets/pets/`).
  - Tự động gửi SMS/Email nhắc lịch tiêm phòng.
