# Từ điển Dữ liệu (data_dictionary.md)

Tài liệu này định nghĩa chi tiết từng bảng, trường dữ liệu, kiểu dữ liệu và ràng buộc của cơ sở dữ liệu SQLite trong PetCare Manager.

---

### 1. Bảng `users` (Tài khoản người dùng)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã định danh người dùng |
| `username` | TEXT | UNIQUE, NOT NULL | Tên đăng nhập hệ thống |
| `password_hash` | TEXT | NOT NULL | Chuỗi băm mật khẩu PBKDF2-HMAC-SHA256 |
| `salt` | TEXT | NOT NULL | Chuỗi salt ngẫu nhiên 16 bytes (dạng hex) |
| `role` | TEXT | NOT NULL, CHECK in ('admin', 'staff') | Vai trò người dùng |
| `full_name` | TEXT | NOT NULL | Họ và tên đầy đủ |
| `active` | INTEGER | NOT NULL DEFAULT 1, CHECK in (0, 1) | 1: Đang hoạt động, 0: Đã khóa |
| `created_at` | TEXT | NOT NULL | Thời điểm tạo tài khoản (ISO 8601) |

---

### 2. Bảng `owners` (Chủ nuôi)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã định danh chủ nuôi |
| `full_name` | TEXT | NOT NULL | Họ và tên khách hàng |
| `phone` | TEXT | NOT NULL | Số điện thoại liên lạc (8-15 chữ số) |
| `address` | TEXT | NOT NULL | Địa chỉ liên hệ |
| `active` | INTEGER | NOT NULL DEFAULT 1, CHECK in (0, 1) | 1: Đang theo dõi, 0: Ngừng theo dõi |
| `created_at` | TEXT | NOT NULL | Thời điểm tạo hồ sơ (ISO 8601) |

---

### 3. Bảng `pets` (Thú cưng)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã định danh thú cưng |
| `owner_id` | INTEGER | NOT NULL, REFERENCES owners(id) | Khóa ngoại trỏ đến chủ sở hữu |
| `name` | TEXT | NOT NULL | Tên thú cưng |
| `species` | TEXT | NOT NULL | Loài (Chó, Mèo,...) |
| `breed` | TEXT | NULLABLE | Giống loài cụ thể |
| `sex` | TEXT | NOT NULL, CHECK in ('male', 'female', 'unknown') | Giới tính |
| `birth_date` | TEXT | NULLABLE | Ngày sinh (YYYY-MM-DD, không ở tương lai) |
| `weight_kg` | REAL | NULLABLE, CHECK >= 0 | Cân nặng tính theo kilogram |
| `coat_color` | TEXT | NULLABLE | Màu lông |
| `active` | INTEGER | NOT NULL DEFAULT 1, CHECK in (0, 1) | 1: Đang theo dõi, 0: Ngừng theo dõi |
| `created_at` | TEXT | NOT NULL | Thời điểm tạo hồ sơ (ISO 8601) |

---

### 4. Bảng `services` (Danh mục dịch vụ)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã dịch vụ |
| `name` | TEXT | UNIQUE, NOT NULL | Tên dịch vụ |
| `category` | TEXT | NOT NULL | Phân loại (Khám bệnh, Tiêm phòng, Chăm sóc, Xét nghiệm) |
| `price_vnd` | INTEGER | NOT NULL, CHECK >= 0 | Giá niêm yết hiện hành (VND) |
| `active` | INTEGER | NOT NULL DEFAULT 1, CHECK in (0, 1) | 1: Đang cung cấp, 0: Ngừng cung cấp |
| `created_at` | TEXT | NOT NULL | Thời điểm tạo dịch vụ |

---

### 5. Bảng `service_visits` (Lượt sử dụng dịch vụ)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã lượt dịch vụ |
| `pet_id` | INTEGER | NOT NULL, REFERENCES pets(id) | Thú cưng sử dụng dịch vụ |
| `service_id` | INTEGER | NOT NULL, REFERENCES services(id) | Gói dịch vụ đã thực hiện |
| `performed_at` | TEXT | NOT NULL | Thời điểm thực hiện dịch vụ |
| `unit_price_vnd` | INTEGER | NOT NULL, CHECK >= 0 | Đơn giá snapshot tại thời điểm thực hiện |
| `notes` | TEXT | NULLABLE | Ghi chú ca thực hiện |

---

### 6. Bảng `examinations` (Hồ sơ khám bệnh)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã hồ sơ khám bệnh |
| `pet_id` | INTEGER | NOT NULL, REFERENCES pets(id) | Thú cưng được khám |
| `visit_id` | INTEGER | NOT NULL, UNIQUE, REFERENCES service_visits(id) | Lượt dịch vụ liên kết (1-1) |
| `exam_date` | TEXT | NOT NULL | Ngày khám bệnh (YYYY-MM-DD) |
| `symptoms` | TEXT | NOT NULL | Triệu chứng lâm sàng ban đầu |
| `diagnosis` | TEXT | NOT NULL | Chẩn đoán của bác sĩ thú y |
| `medicines` | TEXT | NULLABLE | Đơn thuốc hoặc chỉ định điều trị |

---

### 7. Bảng `vaccinations` (Hồ sơ tiêm phòng)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã hồ sơ tiêm phòng |
| `pet_id` | INTEGER | NOT NULL, REFERENCES pets(id) | Thú cưng được tiêm |
| `visit_id` | INTEGER | NOT NULL, UNIQUE, REFERENCES service_visits(id) | Lượt dịch vụ liên kết (1-1) |
| `vaccine_name` | TEXT | NOT NULL | Tên loại vaccine đã tiêm |
| `injection_date` | TEXT | NOT NULL | Ngày tiêm vaccine |
| `next_due_date` | TEXT | NULLABLE | Ngày hẹn tiêm nhắc lại |
| `reminder_resolved`| INTEGER | NOT NULL DEFAULT 0, CHECK in (0, 1) | 0: Chưa nhắc, 1: Đã hoàn thành nhắc nhở |

---

### 8. Bảng `appointments` (Lịch hẹn)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã lịch hẹn |
| `pet_id` | INTEGER | NOT NULL, REFERENCES pets(id) | Thú cưng hẹn khám/chăm sóc |
| `type` | TEXT | NOT NULL | Loại dịch vụ dự kiến (Khám, Tiêm, Spa,...) |
| `scheduled_at` | TEXT | NOT NULL | Thời gian hẹn |
| `status` | TEXT | NOT NULL, CHECK in ('planned', 'completed', 'cancelled') | Trạng thái lịch hẹn |
| `note` | TEXT | NULLABLE | Yêu cầu của khách hàng |
| `created_at` | TEXT | NOT NULL | Thời điểm tạo lịch hẹn |

---

### 9. Bảng `invoices` (Hóa đơn)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã hóa đơn thanh toán |
| `owner_id` | INTEGER | NOT NULL, REFERENCES owners(id) | Khách hàng thanh toán |
| `created_at` | TEXT | NOT NULL | Thời điểm lập hóa đơn |
| `status` | TEXT | NOT NULL, CHECK in ('unpaid', 'paid', 'cancelled') | Trạng thái hóa đơn |
| `paid_at` | TEXT | NULLABLE | Thời điểm thanh toán thành công (ISO 8601) |
| `note` | TEXT | NULLABLE | Ghi chú thu ngân |

---

### 10. Bảng `invoice_items` (Chi tiết hóa đơn)
| Tên cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã dòng chi tiết |
| `invoice_id` | INTEGER | NOT NULL, REFERENCES invoices(id) | Hóa đơn chứa dòng này |
| `visit_id` | INTEGER | NOT NULL, UNIQUE, REFERENCES service_visits(id) | Lượt dịch vụ tính phí (UNIQUE: chỉ tính 1 lần) |
| `service_name_snapshot` | TEXT | NOT NULL | Ảnh chụp tên dịch vụ tại thời điểm lập hóa đơn |
| `pet_name_snapshot` | TEXT | NOT NULL | Ảnh chụp tên thú cưng tại thời điểm lập hóa đơn |
| `amount_vnd` | INTEGER | NOT NULL, CHECK >= 0 | Số tiền thu của dòng này (VND) |
