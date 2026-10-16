# Kiến trúc Hệ thống PetCare Manager (architecture.md)

Tài liệu này mô tả chi tiết kiến trúc phần mềm, nguyên tắc thiết kế và luồng dữ liệu của ứng dụng PetCare Manager.

---

## 1. Mô hình Kiến trúc 3 Lớp (Three-Tier Architecture)

Ứng dụng được thiết kế phân tầng nghiêm ngặt nhằm tách biệt giao diện người dùng, quy tắc nghiệp vụ và truy xuất dữ liệu:

```
+--------------------------------------------------------------+
|                   TẦNG GIAO DIỆN (UI Layer)                  |
|    petcare/ui/: Tkinter/ttk, Screens, Widgets, Dialogs       |
+--------------------------------------------------------------+
                               | Gọi phương thức (Truyền data & Session)
                               v
+--------------------------------------------------------------+
|                  TẦNG NGHIỆP VỤ (Service Layer)              |
|  petcare/services/: AuthService, OwnerService, PetService,   |
|   CatalogService, ExamService, VaccinationService,           |
|   AppointmentService, VisitService, InvoiceService, Report   |
+--------------------------------------------------------------+
                               | Mở kết nối, điều phối Transaction
                               v
+--------------------------------------------------------------+
|                 TẦNG DỮ LIỆU (Repository Layer)              |
|  petcare/repositories/: UserRepository, OwnerRepository,     |
|   PetRepository, CatalogRepository, ExamRepository, ...      |
+--------------------------------------------------------------+
                               | Thực thi SQL có tham số (?)
                               v
+--------------------------------------------------------------+
|                     SQLite Cơ sở Dữ liệu                     |
|           data/petcare.db (PRAGMA foreign_keys = ON;)        |
+--------------------------------------------------------------+
```

### Nguyên tắc bất biến giữa các tầng:
1. **UI Layer (`petcare/ui/`)**:
   - Chỉ chịu trách nhiệm hiển thị giao diện, thu thập sự kiện người dùng và gọi xuống Service layer.
   - **Tuyệt đối không chứa câu lệnh SQL trong callback giao diện**.
   - Không trực tiếp can thiệp hoặc kết thúc giao dịch cơ sở dữ liệu.
2. **Service Layer (`petcare/services/`)**:
   - Trung tâm xử lý logic nghiệp vụ và kiểm tra tính hợp lệ dữ liệu (validation).
   - Kiểm tra phân quyền dựa trên `AuthSession` (`is_admin()` vs `is_staff()`).
   - Điều phối giao dịch (`transaction(conn)`): Quản lý `commit()` khi toàn bộ các thao tác thành công hoặc `rollback()` khi có ngoại lệ.
   - Không phụ thuộc hay import bất kỳ widget nào của UI.
3. **Repository Layer (`petcare/repositories/`)**:
   - Chứa các hàm thực thi SQL với tham số an toàn (`?`) chống SQL Injection.
   - Nhận đối tượng kết nối `conn` của transaction hiện tại từ Service.
   - **Không tự ý commit hoặc rollback** để tránh phá vỡ tính nguyên tố (atomicity) của transaction do Service điều phối.

---

## 2. Quản lý Giao dịch Kép (Atomic Transactions)

Trong y tế thú cưng, một ca khám bệnh hoặc tiêm phòng luôn đồng thời tạo ra một bản ghi hồ sơ chuyên môn và một lượt tính phí dịch vụ. PetCare Manager đảm bảo tính toàn vẹn tuyệt đối:

```
[Bác sĩ tạo ca khám] -> ExamService.record_exam()
                             |
                   +---------+---------+ (Mở Transaction chung)
                   |                   |
                   v                   v
      VisitRepository.create_visit()  ExamRepository.create()
      (Tạo lượt dịch vụ với snapshot   (Lưu triệu chứng, chẩn đoán
       giá niêm yết hiện tại)          và liên kết visit_id UNIQUE)
                   |                   |
                   +---------+---------+
                             |
            [Tất cả thành công? --> conn.commit()]
            [Bất kỳ lỗi nào?   --> conn.rollback()]
```

- Ràng buộc `visit_id UNIQUE` trên bảng `examinations` và `vaccinations` ngăn chặn ở mức cơ sở dữ liệu việc một lượt dịch vụ bị liên kết lặp.
- Nếu việc ghi ca khám thành công nhưng lưu đơn thuốc hoặc lượt dịch vụ phát sinh lỗi, toàn bộ thao tác sẽ bị rollback về trạng thái ban đầu.

---

## 3. Kiến trúc Cửa sổ Duy nhất (Single Root Tk)

- Ứng dụng chỉ sử dụng đúng một vòng lặp sự kiện `mainloop()` và một đối tượng `tk.Tk()`.
- Việc chuyển đổi giữa màn hình đăng nhập và các màn hình chức năng được thực hiện bằng cách thay thế các đối tượng `ttk.Frame` con trong `content_frame`.
- Các hộp thoại nhập liệu (Thêm chủ nuôi, Thêm thú cưng, Chi tiết hóa đơn) sử dụng `tk.Toplevel(transient=root, grab_set=True)` giúp giữ luồng thao tác tập trung và không tạo thêm instance Tk độc lập.

---

## 4. Quản lý Phiên & An ninh

- Sau khi đăng nhập thành công, hệ thống tạo đối tượng bất biến `AuthSession(user_id, username, role, full_name)`.
- Mật khẩu không bao giờ được lưu trữ dạng thô hay lưu trong `AuthSession`.
- Mật khẩu lưu trong cơ sở dữ liệu được mã hóa bằng `PBKDF2-HMAC-SHA256` với 100.000 vòng lặp và salt ngẫu nhiên 16 bytes.
- Hệ thống bảo vệ Admin cuối cùng: Không cho phép hạ quyền hay vô hiệu hóa tài khoản Quản trị viên hoạt động duy nhất.
