# Báo cáo Trạng thái Dự án (project_status.md)

Cập nhật vào: 2026-10-16

## 1. Hiện trạng triển khai

- **Tiến độ tổng thể**:
  - [x] Tạo tài liệu quy ước `AGENTS.md`.
  - [x] Lập kế hoạch chi tiết 5 mốc tại `docs/implementation_plan.md`.
  - [x] **Mốc 1: Nền tảng Dữ liệu, Chủ nuôi và Thú cưng (HOÀN THÀNH)**.
  - [x] **Mốc 2: Đăng nhập, Quyền, Dịch vụ, Khám, Tiêm & Lịch hẹn (HOÀN THÀNH)**.
  - [x] **Mốc 3: Lượt dịch vụ, Hóa đơn, Thanh toán & Báo cáo thống kê (HOÀN THÀNH)**.
  - [x] **Mốc 4: Tích hợp Giao diện Tkinter hoàn chỉnh & Kiểm thử tích hợp (HOÀN THÀNH)**.
  - [ ] Mốc 5: Hoàn thiện tài liệu, nghiệm thu & bàn giao tag v1.0.0 (Bắt đầu).

## 2. Quyết định kỹ thuật & Chi tiết Mốc 4

1. **Giao diện người dùng Tkinter/ttk đồng bộ (`petcare/ui/`)**:
   - `theme.py`: Áp dụng phong cách hiện đại, bảng màu chuẩn doanh nghiệp, font chữ Segoe UI rõ ràng, định dạng tiền tệ VND (`format_vnd`).
   - `common.py`: Cung cấp các component dùng chung: `DataTable` (Treeview cuộn 2 chiều, helper quản lý data), `HeaderBar`, `StatCard`, và các hộp thoại thông báo.
   - `login_view.py`: Đăng nhập an toàn, hiển thị hướng dẫn tài khoản demo Admin/Nhân viên.
   - `users_view.py`: Quản lý tài khoản và phân quyền người dùng (chỉ Admin).
   - `owners_view.py`: Danh sách khách hàng, tìm kiếm, thêm/sửa, chuyển sang xem thú cưng liên kết.
   - `pets_view.py`: Danh sách thú cưng, lọc theo giống loài, tìm kiếm, thêm/sửa, liên kết sang xem hồ sơ tổng hợp.
   - `pet_profile_view.py`: Hồ sơ bệnh án tổng hợp gồm 4 tab chi tiết: Khám bệnh, Tiêm phòng, Lịch hẹn và Toàn bộ lượt dịch vụ & chi phí.
   - `services_view.py`: Bảng giá dịch vụ niêm yết (Admin đổi giá/thêm mới, Nhân viên chỉ xem).
   - `examinations_view.py`: Ghi nhận ca khám bệnh, triệu chứng, chẩn đoán, đơn thuốc và tự động sinh lượt dịch vụ kèm phí.
   - `vaccinations_view.py`: Quản lý tiêm phòng, theo dõi các mũi tiêm sắp đến hạn (trong vòng 30 ngày) và đánh dấu hoàn thành nhắc nhở.
   - `appointments_view.py`: Quản lý lịch hẹn khám/chăm sóc spa, cập nhật trạng thái `planned` -> `completed` / `cancelled`.
   - `visits_view.py`: Quản lý toàn bộ các lượt dịch vụ đã thực hiện và trạng thái thanh toán hóa đơn.
   - `invoices_view.py`: Lập hóa đơn từ các lượt chưa tính tiền của cùng một chủ nuôi, thanh toán trực tiếp tại quầy, hủy hóa đơn chưa thanh toán và xem hóa đơn chi tiết.
   - `reports_view.py` & `revenue_view.py`: Bảng điều khiển thống kê tổng quan (doanh thu thực thu, số hóa đơn, số ca khám, số thú cưng tiêm phòng, cơ cấu loài và top dịch vụ phổ biến).
   - `app.py`: Điều khiển toàn bộ ứng dụng trên một `Tk` root duy nhất, quản lý phiên làm việc (`AuthSession`), điều hướng mượt mà, phân quyền hiển thị sidebar.
2. **Kiểm thử liên chức năng**:
   - `tests/test_integration_flow.py`: Kiểm tra tự động 100% kịch bản Lan/Miu theo `REPO_GUIDE.md`:
     Tạo chị Lan -> Thêm mèo Miu -> Đặt lịch hẹn -> Khám bệnh -> Tiêm phòng vaccine Dại -> Dịch vụ tắm spa -> Kiểm tra 3 lượt chưa thanh toán (530.000 đ) -> Lập hóa đơn -> Thanh toán trực tiếp -> Thanh toán lần 2 trả về `already_paid` -> Bảo vệ không cho hủy đơn đã trả -> Đối chiếu báo cáo doanh thu và top dịch vụ.
   - `tests/test_ui_navigation.py`: Kiểm thử tự động khả năng khởi chạy, đăng nhập và điều hướng qua lại giữa tất cả các màn hình giao diện không xảy ra lỗi.

## 3. Lịch sử kiểm tra thực tế

- Toàn bộ 34 tests trong test suite đều đạt 100%:
  - `test_appointment_service.py`: 2 tests
  - `test_auth_service.py`: 5 tests
  - `test_catalog_service.py`: 3 tests
  - `test_exam_service.py`: 3 tests
  - `test_integration_flow.py`: 1 test
  - `test_invoice_service.py`: 5 tests
  - `test_owner_service.py`: 5 tests
  - `test_pet_service.py`: 5 tests
  - `test_report_queries.py`: 1 test
  - `test_ui_navigation.py`: 1 test
  - `test_vaccination_service.py`: 3 tests

## 4. Bước tiếp theo (Mốc 5)

Tiến hành triển khai **Mốc 5: Hoàn thiện tài liệu, nghiệm thu và bàn giao**:
1. Cập nhật `README.md` với đầy đủ hướng dẫn chạy cho Windows (PowerShell) và macOS (Terminal), phiên bản Python, tài khoản demo, kịch bản dùng thử.
2. Cập nhật các tài liệu kỹ thuật trong thư mục `docs/`:
   - `docs/architecture.md`: Kiến trúc 3 lớp UI -> Service -> Repository.
   - `docs/erd.md`: Sơ đồ ERD và quan hệ giữa 10 bảng dữ liệu.
   - `docs/billing_rules.md`: Toàn bộ quy tắc tính phí, hóa đơn, thanh toán và bảo toàn doanh thu.
   - `docs/acceptance_tests.md`: 10 ca kiểm thử nghiệm thu theo `REPO_GUIDE.md`.
   - `docs/demo_scenarios.md`: Kịch bản demo từng bước để bảo vệ đồ án.
   - `docs/backup_restore.md`: Hướng dẫn sao lưu và phục hồi cơ sở dữ liệu SQLite.
   - `docs/test_results.md`: Tổng kết kết quả kiểm thử toàn diện.
3. Cập nhật `CHANGELOG.md`.
4. Kiểm tra môi trường sạch, cam kết Git và chuẩn bị đưa bản v1.0.0 lên `main`.
