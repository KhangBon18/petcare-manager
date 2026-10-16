# Nhật ký Thay đổi (CHANGELOG.md)

## [1.0.0] - 2026-10-16

### Hoàn thiện toàn bộ hệ thống PetCare Manager

#### 1. Cơ sở dữ liệu & Bảo mật
- Thiết lập kết nối SQLite chuẩn với `PRAGMA foreign_keys = ON;`.
- Định nghĩa schema 10 bảng dữ liệu chuẩn hóa, khóa ngoại và chỉ mục tối ưu.
- Khởi tạo cơ sở dữ liệu an toàn (`initialize.py`), không xóa database cũ.
- Nạp dữ liệu mẫu (`seed.py`) có tính idempotent (chạy lặp lại không tạo dữ liệu trùng).
- Băm mật khẩu người dùng với PBKDF2-HMAC-SHA256, 100.000 vòng lặp và salt ngẫu nhiên 16 bytes.

#### 2. Tầng Nghiệp vụ & Dịch vụ (Service Layer)
- Phân quyền đăng nhập Admin và Nhân viên (`AuthService`), bảo vệ Admin cuối cùng.
- Quản lý chủ nuôi (`OwnerService`) và thú cưng (`PetService`) với đầy đủ ràng buộc kiểm tra hợp lệ.
- Bảo vệ lịch sử: Ngừng theo dõi (`active=0`) thay vì xóa khi chủ nuôi hoặc thú cưng đã có dữ liệu liên quan. Chặn đổi chủ khi thú cưng đã có hóa đơn.
- Quản lý bảng giá (`CatalogService`): Chỉ Admin có quyền đổi giá và thêm dịch vụ.
- Ghi nhận ca khám (`ExamService`) và tiêm phòng (`VaccinationService`) tự động đồng bộ lượt dịch vụ trong cùng một giao dịch (atomic transaction).
- Quản lý lịch nhắc vaccine đến hạn và đánh dấu hoàn thành nhắc nhở.
- Quản lý lịch hẹn (`AppointmentService`): Đảm bảo lịch hẹn không tự động sinh phí trước.
- Quản lý hóa đơn (`InvoiceService`): Gom lượt dịch vụ cùng chủ, chống tính phí lặp (`visit_id UNIQUE`), snapshot tên và giá, thanh toán trực tiếp an toàn (`already_paid`), hủy đơn unpaid giải phóng lượt dịch vụ, bảo vệ tuyệt đối đơn paid.
- Thống kê doanh thu (`ReportService`): Doanh thu chỉ tính từ các hóa đơn đã thanh toán theo ngày `paid_at`, thống kê số ca khám, thú cưng tiêm phòng, cơ cấu loài và dịch vụ phổ biến.

#### 3. Tầng Giao diện Người dùng (UI Layer)
- Xây dựng trên một `Tk` root duy nhất với cơ chế điều hướng Frame mượt mà.
- Giao diện tiếng Việt 100%, thiết kế hiện đại, bảng màu trực quan, bảng Treeview cuộn 2 chiều.
- Đầy đủ 10 màn hình chức năng: Đăng nhập, Chủ nuôi, Thú cưng, Hồ sơ tổng hợp (4 tab), Khám bệnh, Tiêm phòng & Lịch nhắc, Lịch hẹn, Lượt dịch vụ, Hóa đơn & Thu ngân, Thống kê doanh thu, Quản lý tài khoản (Admin).

#### 4. Kiểm thử & Đóng gói
- Xây dựng 34 unit tests và integration tests, đạt 100% tỷ lệ thành công.
- Kịch bản nghiệm thu luồng nghiệp vụ Lan & Miu chạy thành công từ đầu đến cuối.
- Kiểm thử tự động khởi tạo GUI và điều hướng tất cả các màn hình giao diện.
- Bộ tài liệu kỹ thuật hoàn chỉnh trong `docs/`: `architecture.md`, `erd.md`, `billing_rules.md`, `acceptance_tests.md`, `demo_scenarios.md`, `backup_restore.md`, `test_results.md`, `project_status.md`.
