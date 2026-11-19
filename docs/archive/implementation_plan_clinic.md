# Kế hoạch Triển khai PetCare Manager (implementation_plan.md)

Tài liệu này xác định các mốc triển khai (milestones), phạm vi công việc và tiêu chí nghiệm thu cho dự án `petcare-manager`.

---

## Mốc 1: Nền tảng Dữ liệu, Chủ nuôi và Thú cưng
**Mục tiêu**: Thiết lập cấu trúc cơ sở dữ liệu SQLite, cơ chế kết nối an toàn, cơ chế seed dữ liệu mẫu có thể chạy lại an toàn, và triển khai đầy đủ các tầng cho Chủ nuôi (Owners) và Thú cưng (Pets).

- [ ] `petcare/security.py`: Hàm băm mật khẩu PBKDF2-HMAC-SHA256, sinh salt, kiểm tra mật khẩu.
- [ ] `petcare/database/connection.py`: Mở kết nối, bật `PRAGMA foreign_keys = ON;`, hỗ trợ context manager cho transaction.
- [ ] `petcare/database/schema.sql`: 10 bảng dữ liệu chuẩn theo `REPO_GUIDE.md` kèm đầy đủ khóa ngoại, ràng buộc CHECK và UNIQUE.
- [ ] `petcare/database/initialize.py`: Khởi tạo database an toàn (`CREATE TABLE IF NOT EXISTS`), không ghi đè dữ liệu cũ.
- [ ] `petcare/database/seed.py`: Dữ liệu mẫu (admin, staff, các chủ nuôi, thú cưng, dịch vụ), bảo đảm chạy nhiều lần không trùng dữ liệu (idempotent).
- [ ] `petcare/repositories/owner_repo.py`: CRUD và tìm kiếm chủ nuôi.
- [ ] `petcare/repositories/pet_repo.py`: CRUD, tìm kiếm thú cưng theo chủ, loài, tên; đánh dấu ngừng theo dõi (`active=0`).
- [ ] `petcare/services/owner_service.py`: Kiểm tra dữ liệu chủ nuôi (tên, SĐT, địa chỉ), quyền truy cập.
- [ ] `petcare/services/pet_service.py`: Kiểm tra thú cưng (ngày sinh, cân nặng không âm, chủ tồn tại), bảo toàn thú cưng đã có lịch sử.
- [ ] `tests/test_owner_service.py` & `tests/test_pet_service.py`: Kiểm thử tự động với SQLite tạm.

**Tiêu chí nghiệm thu Mốc 1**:
1. Khởi tạo DB và chạy seed 2 lần liên tiếp không lỗi, không nhân đôi bản ghi.
2. Thêm, sửa, tìm kiếm chủ nuôi và thú cưng thành công qua Service.
3. Chặn chủ không tồn tại, cân nặng âm, ngày sinh không hợp lệ.
4. Toàn bộ tests của Mốc 1 vượt qua với 100% tỷ lệ đạt.

---

## Mốc 2: Đăng nhập, Phân quyền, Dịch vụ, Khám bệnh, Tiêm phòng & Lịch hẹn
**Mục tiêu**: Xây dựng hệ thống xác thực người dùng, phân quyền Admin/Staff, danh mục dịch vụ, và các nghiệp vụ y tế cốt lõi (khám bệnh, tiêm chủng gắn liền với lượt dịch vụ, lịch hẹn).

- [ ] `petcare/repositories/user_repo.py`: Quản lý tài khoản người dùng (`users`).
- [ ] `petcare/services/auth_service.py`: Đăng nhập, sinh session (`AuthSession`), quản lý tài khoản, ngăn khóa tài khoản admin cuối cùng.
- [ ] `petcare/repositories/catalog_repo.py`: CRUD danh mục dịch vụ (`services`).
- [ ] `petcare/services/catalog_service.py`: Kiểm tra quyền (chỉ Admin được đổi giá/sửa dịch vụ), giá >= 0.
- [ ] `petcare/repositories/visit_repo.py`: Tạo bản ghi `service_visits` trong transaction.
- [ ] `petcare/repositories/exam_repo.py`: Lưu hồ sơ khám (`examinations`).
- [ ] `petcare/services/exam_service.py`: Lưu khám bệnh và tạo `service_visits` trong cùng một transaction; rollback nếu có lỗi.
- [ ] `petcare/repositories/vaccination_repo.py`: Lưu hồ sơ tiêm chủng (`vaccinations`).
- [ ] `petcare/services/vaccination_service.py`: Lưu tiêm chủng và tạo `service_visits` trong cùng một transaction; kiểm tra ngày tiêm, ngày nhắc.
- [ ] `petcare/repositories/appointment_repo.py`: CRUD lịch hẹn (`appointments`).
- [ ] `petcare/services/appointment_service.py`: Đặt lịch hẹn, đổi trạng thái (planned -> completed/cancelled), không tự tạo phí.
- [ ] `tests/test_auth_service.py`, `tests/test_catalog_service.py`, `tests/test_exam_service.py`, `tests/test_vaccination_service.py`, `tests/test_appointment_service.py`.

**Tiêu chí nghiệm thu Mốc 2**:
1. Đăng nhập thành công với tài khoản demo Admin và Staff; mật khẩu sai bị từ chối; session chứa thông tin vai trò.
2. Nhân viên không được phép tạo hoặc sửa giá dịch vụ (bị từ chối ở service layer).
3. Ghi nhận khám bệnh/tiêm phòng luôn tạo đúng một `service_visits` liên kết trong cùng transaction.
4. Lịch hẹn không tự động sinh phí.
5. Tất cả unit test Mốc 2 chạy đạt.

---

## Mốc 3: Lượt dịch vụ, Hóa đơn, Thanh toán, Lịch sử & Thống kê
**Mục tiêu**: Hoàn thiện chu trình tài chính: thu thập các lượt dịch vụ chưa thanh toán, lập hóa đơn, thanh toán trực tiếp, bảo vệ hóa đơn đã thanh toán, và xuất báo cáo thống kê chính xác.

- [ ] `petcare/repositories/invoice_repo.py`: Tạo hóa đơn, tạo chi tiết hóa đơn `invoice_items` với snapshot tên và giá; cập nhật trạng thái thanh toán.
- [ ] `petcare/repositories/report_repo.py`: Truy vấn số loài, lượt khám, số thú cưng đã tiêm, doanh thu theo kỳ, top dịch vụ phổ biến.
- [ ] `petcare/services/visit_service.py`: Lấy danh sách lượt dịch vụ chưa thanh toán của một chủ nuôi.
- [ ] `petcare/services/invoice_service.py`:
  - Lập hóa đơn: gom các `visit_id` chưa thanh toán của cùng một chủ; kiểm tra chống thanh toán lặp.
  - Thanh toán: cập nhật `paid` và `paid_at`; thanh toán lại trả về `already_paid` mà không ghi nhận doanh thu 2 lần.
  - Hủy hóa đơn: chỉ cho phép hủy hóa đơn `unpaid`; xóa `invoice_items` để giải phóng `visit_id`; hóa đơn `paid` là bất biến.
- [ ] `petcare/services/report_service.py`: Tổng hợp báo cáo thống kê theo khoảng thời gian; xử lý ranh giới thời gian chính xác (00:00:00 đến 23:59:59).
- [ ] `tests/test_invoice_service.py` & `tests/test_report_queries.py`.

**Tiêu chí nghiệm thu Mốc 3**:
1. Một lượt dịch vụ chỉ được đưa vào một hóa đơn; cố tình lập hóa đơn lặp bị chặn.
2. Thay đổi giá trong danh mục không làm thay đổi giá của các lượt dịch vụ đã tạo hoặc các hóa đơn trong quá khứ.
3. Thanh toán 2 lần không nhân đôi doanh thu. Hóa đơn `paid` không thể bị hủy hoặc sửa đổi.
4. Doanh thu khớp 100% với tổng số tiền các hóa đơn `paid` trong kỳ.
5. Tất cả unit test Mốc 3 chạy đạt.

---

## Mốc 4: Tích hợp Giao diện Tkinter hoàn chỉnh & Kiểm thử Toàn diện
**Mục tiêu**: Xây dựng toàn bộ các màn hình giao diện người dùng tiếng Việt bằng `ttk`, kết nối hoàn toàn với Service layer, loại bỏ các Frame thông báo tạm thời (`PendingView`), và thực hiện kiểm thử tích hợp luồng nghiệp vụ.

- [ ] Cập nhật `petcare/ui/theme.py` & `common.py`: Bảng màu thống nhất, phong cách hiện đại, widgets dùng chung (bảng Treeview có thanh cuộn, hộp thoại form, nhãn trạng thái).
- [ ] `petcare/ui/login_view.py`: Màn hình đăng nhập tài khoản.
- [ ] `petcare/ui/users_view.py`: Màn hình quản lý tài khoản (chỉ Admin).
- [ ] `petcare/ui/owners_view.py`: Quản lý danh sách, tìm kiếm, thêm/sửa chủ nuôi.
- [ ] `petcare/ui/pets_view.py`: Quản lý thú cưng theo chủ, tìm kiếm, thêm/sửa, ngừng theo dõi.
- [ ] `petcare/ui/pet_profile_view.py`: Xem hồ sơ tổng hợp toàn diện của thú cưng (thông tin cá nhân, lịch sử khám, tiêm, lịch hẹn, lượt dịch vụ).
- [ ] `petcare/ui/services_view.py`: Quản lý danh mục dịch vụ và giá (phân quyền Admin/Staff).
- [ ] `petcare/ui/examinations_view.py`: Ghi nhận ca khám bệnh, chọn dịch vụ tương ứng.
- [ ] `petcare/ui/vaccinations_view.py`: Ghi nhận tiêm chủng, ngày tiêm, ngày nhắc, chọn dịch vụ tương ứng.
- [ ] `petcare/ui/appointments_view.py`: Đặt và quản lý trạng thái lịch hẹn.
- [ ] `petcare/ui/visits_view.py`: Xem các lượt dịch vụ đã thực hiện và trạng thái thanh toán.
- [ ] `petcare/ui/invoices_view.py`: Lập hóa đơn từ các lượt chưa tính tiền, thanh toán trực tiếp, hủy hóa đơn unpaid, in/xem chi tiết.
- [ ] `petcare/ui/reports_view.py`: Bảng điều khiển thống kê (kết hợp các chỉ số số lượng, biểu đồ tóm tắt bằng bảng và doanh thu).
- [ ] `petcare/app.py`: Tích hợp các view thật vào điều hướng, quản lý phiên đăng nhập hiện tại, ẩn/vô hiệu hóa chức năng theo quyền.
- [ ] `tests/test_integration_flow.py`: Kiểm thử tự động kịch bản trọn vẹn: Tạo chị Lan & mèo Miu -> Đặt lịch hẹn -> Khám bệnh + Tiêm phòng + Dịch vụ tắm -> Lập hóa đơn -> Thanh toán -> Kiểm tra Lịch sử & Báo cáo Doanh thu.

**Tiêu chí nghiệm thu Mốc 4**:
1. Không còn màn hình nào dùng `PendingView` hay thông báo giả.
2. Giao diện mở mượt mà, layout chuẩn, thân thiện trên Windows và macOS.
3. Kịch bản tích hợp Lan/Miu chạy thành công từ đầu đến cuối trong test tự động.

---

## Mốc 5: Hoàn thiện Tài liệu, Kiểm định Clone Sạch & Đóng gói Bàn giao
**Mục tiêu**: Hoàn thiện toàn bộ tài liệu kỹ thuật, cập nhật README chi tiết cho Windows/macOS, kiểm tra clone sạch, cam kết Git theo chuẩn, đưa code lên branch `main` và đánh tag `v1.0.0`.

- [ ] Cập nhật `README.md`: Hướng dẫn chi tiết từng bước cho Windows (PowerShell) và macOS (Terminal), phiên bản Python, tài khoản demo, kịch bản dùng thử.
- [ ] Tạo/Cập nhật tài liệu kỹ thuật trong `docs/`:
  - `docs/architecture.md`: Kiến trúc 3 lớp, luồng dữ liệu, quản lý transaction.
  - `docs/erd.md`: Sơ đồ quan hệ thực thể và cấu trúc 10 bảng dữ liệu.
  - `docs/billing_rules.md`: Toàn bộ quy tắc tính phí, hóa đơn, thanh toán và bảo toàn doanh thu.
  - `docs/acceptance_tests.md`: 10 ca kiểm thử nghiệm thu theo `REPO_GUIDE.md`.
  - `docs/demo_scenarios.md`: Kịch bản demo từng bước để bảo vệ đồ án.
  - `docs/backup_restore.md`: Hướng dẫn sao lưu và phục hồi cơ sở dữ liệu SQLite.
  - `docs/project_status.md`: Báo cáo hiện trạng, kết quả kiểm thử thực tế và bàn giao.
  - `CHANGELOG.md`: Nhật ký thay đổi hoàn thiện phiên bản v1.0.0.
- [ ] Kiểm tra môi trường sạch (clean test run): chạy toàn bộ test suite và compileall.
- [ ] Git commit, push branch, merge vào `main`, tạo và push tag `v1.0.0`.
