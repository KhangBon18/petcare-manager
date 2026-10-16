# Báo cáo Kết quả Kiểm thử Toàn diện (test_results.md)

Cập nhật vào: 2026-10-16  
Môi trường thực hiện: macOS, Python 3.13.3, Tkinter (Tcl/Tk 8.6), SQLite 3.

---

## 1. Kết quả Kiểm thử Tự động (Automated Test Suite)

Chạy lệnh kiểm thử toàn diện:
```bash
python3 -m unittest discover -s tests -v
```

### Chi tiết 34 Ca Kiểm thử:

| Module Kiểm thử | Số ca test | Trạng thái | Nội dung kiểm tra |
|---|---|---|---|
| `test_auth_service.py` | 5 | **100% PASS** | Đăng nhập Admin, Nhân viên, mật khẩu sai, băm PBKDF2, Admin tạo user, Staff bị chặn tạo user, bảo vệ Admin cuối |
| `test_owner_service.py` | 5 | **100% PASS** | Thêm chủ nuôi, validation SĐT/tên/địa chỉ, cập nhật, tìm kiếm, xóa vs chuyển sang ngừng theo dõi khi có dữ liệu |
| `test_pet_service.py` | 5 | **100% PASS** | Thêm thú cưng, chủ không tồn tại/inactive bị từ chối, cân nặng âm bị từ chối, ngày sinh tương lai bị từ chối, lọc loài, xóa vs deactivate |
| `test_catalog_service.py` | 3 | **100% PASS** | Admin thêm dịch vụ, Staff bị chặn đổi giá/thêm dịch vụ, kiểm tra giá >= 0, trùng tên dịch vụ |
| `test_exam_service.py` | 3 | **100% PASS** | Ghi nhận ca khám tạo cả khám và lượt dịch vụ trong cùng 1 transaction, đổi giá danh mục không ảnh hưởng giá cũ, validate dữ liệu |
| `test_vaccination_service.py` | 3 | **100% PASS** | Ghi nhận tiêm vaccine và lượt dịch vụ, kiểm tra ngày hẹn tiêm nhắc (phải sau ngày tiêm), lọc lịch nhắc đến hạn trong 30 ngày, đánh dấu hoàn tất |
| `test_appointment_service.py` | 2 | **100% PASS** | Đặt lịch hẹn không tạo bất kỳ khoản phí nào, cập nhật trạng thái `planned` -> `completed` / `cancelled` |
| `test_invoice_service.py` | 5 | **100% PASS** | Lập hóa đơn từ nhiều lượt dịch vụ, chặn lượt khác chủ, chặn tính tiền lặp (`visit_id UNIQUE`), thanh toán trực tiếp, thanh toán lặp trả về `already_paid`, hủy đơn unpaid giải phóng visit, cấm hủy đơn paid |
| `test_report_queries.py` | 1 | **100% PASS** | Tính tổng doanh thu theo `paid_at`, loại trừ đơn unpaid, đếm số ca khám, số thú cưng tiêm phòng (`COUNT DISTINCT`), cơ cấu loài, top dịch vụ |
| `test_integration_flow.py` | 1 | **100% PASS** | **Luồng tích hợp trọn vẹn Lan & Miu**: Tạo Lan -> Miu -> Hẹn -> Khám -> Tiêm -> Tắm -> Lập hóa đơn (530k) -> Thanh toán -> Đối chiếu báo cáo |
| `test_ui_navigation.py` | 1 | **100% PASS** | Khởi chạy `PetCareApp`, hiển thị LoginView, đăng nhập Admin, chuyển đổi mượt mà qua lại giữa 10 màn hình giao diện không lỗi |

**Tổng kết**: **34/34 tests đạt (100% Success)**.

---

## 2. Kiểm tra Cú pháp & Khởi tạo Database

| Lệnh thực thi | Kết quả | Ghi chú |
|---|---|---|
| `python3 -m compileall -q main.py petcare tests` | **ĐẠT** | 0 lỗi cú pháp, 0 cảnh báo |
| `python3 -m petcare.database.initialize` | **ĐẠT** | Tạo an toàn 10 bảng dữ liệu (`CREATE TABLE IF NOT EXISTS`), bảo toàn dữ liệu cũ |
| `python3 -m petcare.database.seed` (chạy 2 lần) | **ĐẠT** | Nạp dữ liệu mẫu thành công; cơ chế idempotent giữ nguyên số lượng bản ghi (không nhân đôi) |
| Kiểm tra khóa ngoại (`PRAGMA foreign_keys = ON;`) | **ĐẠT** | SQLite tự động cưỡng chế khóa ngoại trên mọi kết nối |

---

## 3. Danh sách Kiểm tra Giao diện Thủ công (Manual Checklist)

Dành cho các thành viên (Khang, Quân, Quý, Nhàn) khi chạy trên Windows và macOS:

- [x] Chạy `python main.py`, cửa sổ đăng nhập hiển thị chính giữa với thông tin tài khoản demo.
- [x] Đăng nhập bằng `admin` / `Admin@123`:
  - Thanh bên hiển thị đầy đủ 10 mục điều hướng (có cả "👥 Tài khoản").
- [x] Đăng xuất, đăng nhập bằng `staff1` / `Staff@123`:
  - Thanh bên tự động ẩn mục "👥 Tài khoản".
- [x] Vào mục "🐾 Chủ nuôi":
  - Thêm một chủ nuôi mới -> Danh sách cập nhật tức thì.
- [x] Vào mục "🐶 Thú cưng":
  - Thêm thú cưng thuộc chủ nuôi vừa tạo -> Danh sách cập nhật ngay.
  - Nhấp đúp vào thú cưng -> Mở "Hồ sơ tổng hợp" hiển thị đầy đủ 4 tab.
- [x] Vào mục "🩺 Khám bệnh" & "💉 Tiêm phòng":
  - Ghi nhận ca khám hoặc mũi tiêm -> Giá tiền được tự động lấy từ danh mục dịch vụ.
- [x] Vào mục "💳 Hóa đơn":
  - Chọn chủ nuôi -> Hiển thị danh sách các lượt chưa tính tiền.
  - Bấm "Tạo hóa đơn" -> Hóa đơn được tạo ở trạng thái "Chưa thanh toán".
  - Bấm "Thanh toán trực tiếp" -> Hóa đơn chuyển sang "Đã thanh toán" và ghi nhận giờ trả tiền.
- [x] Vào mục "📊 Thống kê":
  - Chọn ngày hôm nay -> Thẻ doanh thu và top dịch vụ cập nhật ngay lập tức.
- [x] Tắt ứng dụng, mở lại `python main.py`: Dữ liệu vừa nhập vẫn còn nguyên vẹn trong SQLite.
