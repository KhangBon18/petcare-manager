# Hợp đồng Giao tiếp Giữa các Module (module_contracts.md)

Tài liệu này xác định các cam kết đầu vào, đầu ra và ngoại lệ của các phương thức cốt lõi tại tầng Service và Repository.

---

## 1. Tầng Service (Nghiệp vụ)

### `AuthService`
- `login(username: str, password: str) -> AuthSession`
  - *Đầu vào*: Tên đăng nhập và mật khẩu thô.
  - *Cam kết*: Trả về `AuthSession(user_id, username, role, full_name)` nếu thành công; không trả hash hay salt. Ném `ValueError` nếu sai tài khoản/mật khẩu hoặc tài khoản bị khóa.
- `create_user(session: AuthSession, username: str, password: str, role: str, full_name: str) -> int`
  - *Cam kết*: Yêu cầu `session.is_admin()`. Ném `PermissionError` nếu là Staff. Băm mật khẩu PBKDF2 và trả về `user_id`.

### `OwnerService`
- `create_owner(session: AuthSession, data: dict) -> int`
  - *Cam kết*: Yêu cầu `session.is_staff()`. Kiểm tra họ tên, định dạng SĐT (8-15 chữ số), địa chỉ. Trả về `owner_id`.
- `delete_or_deactivate_owner(session: AuthSession, owner_id: int) -> str`
  - *Cam kết*: Trả về `"deleted"` nếu chủ chưa có thú cưng/hóa đơn; trả về `"deactivated"` (đặt `active=0`) nếu đã có dữ liệu liên quan.

### `PetService`
- `create_pet(session: AuthSession, data: dict) -> int`
  - *Cam kết*: Yêu cầu chủ nuôi tồn tại và đang hoạt động (`active=1`). Kiểm tra tên, loài, giới tính, cân nặng >= 0, ngày sinh không ở tương lai. Trả về `pet_id`.
- `update_pet(session: AuthSession, pet_id: int, data: dict) -> bool`
  - *Cam kết*: Chặn đổi chủ nuôi nếu thú cưng đã có hóa đơn trong hệ thống.
- `delete_or_deactivate_pet(session: AuthSession, pet_id: int) -> str`
  - *Cam kết*: Trả về `"deleted"` nếu thú cưng chưa có lịch sử; trả về `"deactivated"` nếu đã có hồ sơ y tế, lịch hẹn hoặc hóa đơn.

### `CatalogService`
- `create_service(session: AuthSession, data: dict) -> int`
  - *Cam kết*: Chỉ Admin có quyền. Kiểm tra tên, danh mục, giá >= 0. Trả về `service_id`.
- `update_service(session: AuthSession, service_id: int, data: dict) -> bool`
  - *Cam kết*: Chỉ Admin có quyền. Đổi giá trong danh mục không làm thay đổi giá của các lượt dịch vụ đã phát sinh trong quá khứ.

### `ExamService`
- `record_exam(session: AuthSession, data: dict) -> tuple[int, int]`
  - *Cam kết*: Tạo đồng thời bản ghi `service_visits` (với snapshot giá niêm yết hiện tại) và bản ghi `examinations` (với `visit_id UNIQUE`) trong cùng một giao dịch. Tự động rollback nếu có ngoại lệ. Trả về `(exam_id, visit_id)`.

### `VaccinationService`
- `record_vaccination(session: AuthSession, data: dict) -> tuple[int, int]`
  - *Cam kết*: Kiểm tra ngày tiêm (không ở tương lai) và ngày hẹn nhắc (phải sau ngày tiêm). Tạo đồng thời `service_visits` và `vaccinations` trong cùng transaction. Trả về `(vaccination_id, visit_id)`.

### `AppointmentService`
- `create_appointment(session: AuthSession, data: dict) -> int`
  - *Cam kết*: Kiểm tra thú cưng tồn tại, thời gian hẹn. **Không tạo lượt dịch vụ hoặc phát sinh chi phí**.

### `VisitService`
- `record_service_usage(session: AuthSession, pet_id: int, service_id: int, performed_at=None, notes=None) -> int`
  - *Cam kết*: Ghi nhận trực tiếp lượt dịch vụ chăm sóc/tắm spa/xét nghiệm. Trả về `visit_id`.
- `get_unbilled_visits_by_owner(session: AuthSession, owner_id: int) -> list[dict]`
  - *Cam kết*: Lấy các lượt dịch vụ của thú cưng thuộc chủ nuôi chưa nằm trong hóa đơn nào.

### `InvoiceService`
- `create_invoice(session: AuthSession, owner_id: int, visit_ids: list[int], note=None) -> int`
  - *Cam kết*: Kiểm tra tất cả các `visit_id` phải thuộc về đúng `owner_id`. Chặn các lượt đã được lập hóa đơn. Snapshot tên dịch vụ, tên thú cưng và giá tiền vào `invoice_items`. Trạng thái ban đầu: `unpaid`.
- `pay_invoice(session: AuthSession, invoice_id: int) -> str`
  - *Cam kết*: Chuyển trạng thái `paid` và lưu `paid_at`. Nếu đã trả tiền trước đó, trả về `"already_paid"` mà không đổi doanh thu. Ném `ValueError` nếu hóa đơn đã bị hủy.
- `cancel_invoice(session: AuthSession, invoice_id: int) -> bool`
  - *Cam kết*: Chỉ cho phép hủy hóa đơn `unpaid`. Xóa các dòng `invoice_items` để giải phóng `visit_id`, cập nhật status sang `cancelled`. Ném `ValueError` nếu cố tình hủy hóa đơn `paid`.

### `ReportService`
- `get_summary(session: AuthSession, start_date=None, end_date=None) -> dict`
  - *Cam kết*: Tính doanh thu từ các hóa đơn có trạng thái `paid` trong kỳ (ranh giới bao trọn 23:59:59 ngày kết thúc). Trả về tổng tiền, số hóa đơn, số ca khám, số thú cưng tiêm phòng, cơ cấu loài và top dịch vụ phổ biến.

---

## 2. Tầng Repository (Truy xuất SQL)

- Mọi phương thức Repository nhận `conn: sqlite3.Connection`.
- Sử dụng câu lệnh SQL có tham số (`?`).
- **Repository không tự gọi `conn.commit()` hoặc `conn.rollback()`**. Quyền quyết định giao dịch thuộc về tầng Service thông qua `with transaction(conn):`.
