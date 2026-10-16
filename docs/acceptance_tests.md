# Kịch bản Nghiệm thu Hệ thống (acceptance_tests.md)

Tài liệu này xác định 10 ca kiểm thử nghiệm thu bắt buộc theo `REPO_GUIDE.md`, bao gồm các bước kiểm tra, kết quả mong đợi và trạng thái kiểm thử thực tế.

---

## Bảng Tổng hợp 10 Ca Nghiệm thu

| STT | Tên ca nghiệm thu | Mục tiêu kiểm tra | Kết quả thực tế |
|---|---|---|---|
| **TC01** | Đăng nhập & Phân quyền | Admin và Nhân viên đăng nhập đúng quyền; Nhân viên đổi giá bị chặn tại Service | **ĐẠT** (Automated in `test_auth_service.py` & `test_catalog_service.py`) |
| **TC02** | Chủ nuôi & Thú cưng | Tạo chị Lan, mèo Miu; lưu DB thật mở lại còn; chặn chủ không tồn tại & cân nặng âm | **ĐẠT** (Automated in `test_owner_service.py` & `test_pet_service.py`) |
| **TC03** | Khám, Tiêm & Lịch hẹn | Hẹn không tự phát sinh phí; khám/tiêm lưu cùng transaction với lượt dịch vụ | **ĐẠT** (Automated in `test_exam_service.py`, `test_vaccination_service.py`, `test_appointment_service.py`) |
| **TC04** | Lập hóa đơn & Độc quyền lượt | Lập hóa đơn gom khám, tiêm, tắm; đổi giá danh mục không đổi lượt cũ; chặn tính phí lặp | **ĐẠT** (Automated in `test_invoice_service.py`) |
| **TC05** | Thanh toán trực tiếp | Thanh toán 2 lần không nhân đôi tiền; hóa đơn unpaid/cancelled không tính vào doanh thu | **ĐẠT** (Automated in `test_invoice_service.py` & `test_report_queries.py`) |
| **TC06** | Hủy & Bảo vệ hóa đơn | Hủy unpaid giải phóng visit; hóa đơn paid bất biến; rollback khi có lỗi dòng chi tiết | **ĐẠT** (Automated in `test_invoice_service.py`) |
| **TC07** | Đối chiếu Thống kê | Khớp số loài, số lượt khám, số thú cưng đã tiêm, doanh thu và top dịch vụ | **ĐẠT** (Automated in `test_report_queries.py` & `test_integration_flow.py`) |
| **TC08** | Lịch nhắc & Trường hợp biên | Báo cáo ranh giới ngày cuối kỳ; lọc mũi tiêm đến hạn/quá hạn trong 30 ngày; xử lý hồ sơ inactive | **ĐẠT** (Automated in `test_vaccination_service.py` & `test_report_queries.py`) |
| **TC09** | Khởi chạy & Sao lưu/Phục hồi | Init DB, seed lặp an toàn, test 100% pass trên môi trường sạch, sao lưu file `.db` | **ĐẠT** (Quy trình kiểm tra sạch độc lập) |
| **TC10** | Luồng tích hợp Lan & Miu | Chạy liền mạch từ tạo chủ/thú cưng -> hẹn -> khám -> tiêm -> tắm -> xuất hóa đơn -> thu tiền -> xem báo cáo | **ĐẠT** (Automated in `test_integration_flow.py`) |

---

## Chi tiết các Ca Nghiệm thu

### TC01: Đăng nhập và Phân quyền
- **Bước 1**: Đăng nhập với tài khoản `staff1` / `Staff@123`.
- **Bước 2**: Gọi hàm `CatalogService.update_service()` hoặc `create_service()`.
- **Kết quả**: Bị từ chối với ngoại lệ `PermissionError: Chỉ Quản trị viên (Admin) mới có quyền...`.
- **Bước 3**: Đăng nhập với `admin` / `Admin@123`, thực hiện thêm/sửa dịch vụ thành công.

### TC02: Tạo chị Lan và mèo Miu
- **Bước 1**: Thêm chủ nuôi Nguyễn Thị Lan (SĐT: 0901234567, Địa chỉ: Quận 1).
- **Bước 2**: Thêm thú cưng mèo Miu cho chị Lan (Cân nặng: 3.5 kg, Ngày sinh: 2024-03-15).
- **Bước 3**: Thử nhập cân nặng -2 kg hoặc ngày sinh tương lai -> Bị hệ thống từ chối với thông báo lỗi.
- **Bước 4**: Thử thêm thú cưng với owner_id không tồn tại -> Bị từ chối.

### TC03: Khám, Tiêm và Lịch hẹn
- **Bước 1**: Tạo lịch hẹn ngày mai cho Miu -> Kiểm tra số lượng bản ghi `service_visits` không đổi.
- **Bước 2**: Ghi nhận ca khám viêm hô hấp -> DB đồng thời tạo 1 ca khám và 1 lượt dịch vụ `service_visits`.
- **Bước 3**: Ghi nhận tiêm vaccine Dại -> DB đồng thời tạo 1 hồ sơ tiêm và 1 lượt dịch vụ `service_visits`.

### TC04: Lập hóa đơn và Bảo toàn giá lịch sử
- **Bước 1**: Ghi thêm dịch vụ tắm vệ sinh cho Miu.
- **Bước 2**: Lập hóa đơn cho chị Lan chọn cả 3 lượt (Khám 150k + Tiêm 180k + Tắm 200k = 530k).
- **Bước 3**: Đổi giá khám trong danh mục lên 250k.
- **Bước 4**: Kiểm tra lại hóa đơn và lượt dịch vụ cũ -> Giá vẫn là 150k (được snapshot bất biến).
- **Bước 5**: Thử tạo hóa đơn mới chứa lại lượt khám đó -> Bị hệ thống chặn ngay lập tức.

### TC05: Thanh toán và Doanh thu
- **Bước 1**: Thanh toán hóa đơn 530k -> Trạng thái chuyển thành `paid`, ghi nhận timestamp `paid_at`.
- **Bước 2**: Gọi thanh toán lại hóa đơn này -> Trả về `already_paid`, không ghi nhận thêm tiền.
- **Bước 3**: Kiểm tra báo cáo doanh thu -> Doanh thu ghi nhận đúng 530k (chỉ tính đơn `paid`).

### TC06: Hủy hóa đơn chưa thanh toán & Bảo vệ hóa đơn đã thanh toán
- **Bước 1**: Tạo 1 hóa đơn unpaid mới có 1 lượt dịch vụ.
- **Bước 2**: Hủy hóa đơn này -> Các dòng `invoice_items` bị xóa, lượt dịch vụ được giải phóng và có thể đưa vào hóa đơn khác.
- **Bước 3**: Thử hủy hóa đơn 530k đã thanh toán ở TC05 -> Hệ thống ném lỗi từ chối, không cho phép hủy.
