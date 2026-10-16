# Báo cáo Trạng thái Dự án (project_status.md)

Cập nhật vào: 2026-10-16  
Chế độ làm việc: **Solo với Khang** (`solo/khang-petcare`)

---

## 1. Hiện trạng triển khai

- **Tiến độ tổng thể**:
  - [x] Tạo tài liệu quy ước `AGENTS.md`.
  - [x] Lập kế hoạch chi tiết 5 mốc tại `docs/implementation_plan.md`.
  - [x] **Mốc 1: Nền tảng Dữ liệu, Chủ nuôi và Thú cưng (HOÀN THÀNH)**.
  - [x] **Mốc 2: Đăng nhập, Quyền, Dịch vụ, Khám, Tiêm & Lịch hẹn (HOÀN THÀNH)**.
  - [x] **Mốc 3: Lượt dịch vụ, Hóa đơn, Thanh toán & Báo cáo thống kê (HOÀN THÀNH)**.
  - [x] **Mốc 4: Tích hợp Giao diện Tkinter hoàn chỉnh & Kiểm thử tích hợp (HOÀN THÀNH)**.
  - [x] **Mốc 5: Bộ tài liệu kiến trúc, nghiệm thu, slide và hướng dẫn (HOÀN THÀNH)**.
  - [x] **Vòng sửa lỗi QC độc lập (4 lỗi QC trọng yếu) (HOÀN THÀNH)**.

---

## 2. Chi tiết xử lý 4 lỗi QC độc lập

### Lỗi 1: Kiểm tra phiên đăng nhập và phân quyền realtime từ CSDL
- **Vấn đề**: Phiên đăng nhập cũ trong bộ nhớ (`AuthSession`) vẫn giữ quyền thao tác sau khi tài khoản bị khóa (`active = 0`) hoặc admin bị hạ quyền (`role = 'staff'`).
- **Giải pháp**:
  - Bổ sung `AuthService.verify_session(conn, session, required_role)` kiểm tra trực tiếp từ bảng `users` tại thời điểm thực thi nghiệp vụ: kiểm tra tài khoản còn tồn tại, `active == 1` và quyền thực tế trong DB.
  - Áp dụng đồng bộ cho toàn bộ các service (`AuthService`, `CatalogService`, `OwnerService`, `PetService`, `ExamService`, `VaccinationService`, `AppointmentService`, `VisitService`, `InvoiceService`, `ReportService`).
  - Bổ sung unit test: `test_logged_in_staff_deactivated_is_blocked` và `test_logged_in_admin_demoted_is_blocked` trong `tests/test_auth_service.py`.

### Lỗi 2: Kiểm tra và chuẩn hóa thời gian hẹn `scheduled_at` trong `AppointmentService`
- **Vấn đề**: `create_appointment` chấp nhận chuỗi bất kỳ như `"abc-not-a-date"`.
- **Giải pháp**:
  - Xây dựng mô-đun chuẩn hóa thời gian `petcare/date_utils.py` với `parse_datetime` và `normalize_datetime`.
  - Kiểm tra tính hợp lệ của ngày giờ thực tế (từ chối chuỗi không phải ngày giờ, ngày không tồn tại theo lịch như 31/02).
  - Chuẩn hóa lưu trữ thống nhất theo định dạng `YYYY-MM-DD HH:MM` giúp sắp xếp và lọc chính xác.
  - Dữ liệu sai báo lỗi rõ ràng (`ValueError`) và không tạo bản ghi rác trong CSDL.
  - Bổ sung unit test: `test_create_appointment_invalid_date_rejected` và `test_create_appointment_date_normalization` trong `tests/test_appointment_service.py`.

### Lỗi 3: Chuẩn hóa ngày khám `exam_date` và đồng bộ báo cáo
- **Vấn đề**: `ExamService` chấp nhận định dạng `YYYYMMDD` nhưng lưu nguyên chuỗi 8 ký tự vào DB, khiến các truy vấn báo cáo theo khoảng ngày `YYYY-MM-DD` bị bỏ sót bản ghi.
- **Giải pháp**:
  - Bổ sung hàm `normalize_date` và `parse_date` trong `petcare/date_utils.py`. Chuẩn hóa toàn bộ ngày tháng (`examinations.exam_date`, `vaccinations.injection_date`, `vaccinations.next_due_date`, `pets.birth_date`, `service_visits.performed_at`, bộ lọc `start_date`/`end_date` của `ReportService`) về chuẩn ISO `YYYY-MM-DD`.
  - Bảo toàn dữ liệu cũ: Trong `initialize_database()`, tự động chạy truy vấn nâng cấp chuyển đổi các bản ghi cũ 8 ký tự `YYYYMMDD` sang `YYYY-MM-DD` một cách an toàn và idempotent.
  - Bổ sung unit test: `test_record_exam_date_normalization_and_report_match` và `test_legacy_data_migration` trong `tests/test_exam_service.py`.

### Lỗi 4: Tách biệt kiểm tra môi trường Tk với lỗi ứng dụng trong `test_ui_navigation.py`
- **Vấn đề**: Khối `try...except Exception` bao bọc cả `tk.Tk()` và `PetCareApp()`, khiến lỗi logic trong ứng dụng bị nuốt và chuyển nhầm thành `skipTest`.
- **Giải pháp**:
  - Chỉ bắt `tk.TclError` quanh `tk.Tk()` để skip khi môi trường thực sự thiếu display.
  - Khởi tạo `PetCareApp` bên ngoài try-catch: Bất kỳ lỗi khởi tạo nào của ứng dụng sẽ gây fail test ngay lập tức.
  - Bổ sung unit test `test_app_initialization_error_not_masked_as_skip` chứng minh lỗi ứng dụng không bị che giấu.

---

## 3. Kết quả kiểm tra thực tế

- **Môi trường thực thi**: macOS (Python 3.13.3, Tkinter 8.6, SQLite 3.49.1).
- **Trạng thái biên dịch (`compileall`)**: 100% hợp lệ, không có lỗi cú pháp.
- **Toàn bộ 41 unit/integration tests đều đạt (Passed: 41, Failed: 0, Errors: 0, Skipped: 0)**:
  - `test_appointment_service.py`: 4 tests (gồm 2 test mới cho QC 2)
  - `test_auth_service.py`: 7 tests (gồm 2 test mới cho QC 1)
  - `test_catalog_service.py`: 3 tests
  - `test_exam_service.py`: 5 tests (gồm 2 test mới cho QC 3)
  - `test_integration_flow.py`: 1 test luồng tích hợp toàn diện
  - `test_invoice_service.py`: 5 tests
  - `test_owner_service.py`: 5 tests
  - `test_pet_service.py`: 5 tests
  - `test_report_queries.py`: 1 test
  - `test_ui_navigation.py`: 2 tests (gồm 1 test mới cho QC 4)
  - `test_vaccination_service.py`: 3 tests

---

## 4. Hướng dẫn khởi chạy nghiệm thu cục bộ

```bash
# Kích hoạt môi trường và khởi chạy ứng dụng
.venv/bin/python main.py
```
- Tài khoản Quản trị: `admin` / `Admin@123`
- Tài khoản Nhân viên: `staff1` / `Staff@123` hoặc `staff` / `Staff@123`
