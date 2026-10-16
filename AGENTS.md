# Quy ước phát triển PetCare Manager (AGENTS.md)

Tài liệu này cung cấp hướng dẫn và quy ước phát triển cho các kỹ sư và AI agent khi làm việc trên repository `petcare-manager`.

## 1. Kiến trúc hệ thống

Ứng dụng tuân theo mô hình 3 lớp phân tách trách nhiệm rõ ràng:
- **UI Layer (`petcare/ui/`)**: Xây dựng bằng `tkinter` và `ttk`. Chỉ phụ trách hiển thị, thu thập input của người dùng và gọi xuống `Service`. Tuyệt đối không chứa câu lệnh SQL trong callback UI.
- **Service Layer (`petcare/services/`)**: Quản lý nghiệp vụ, kiểm tra tính hợp lệ dữ liệu (validation), kiểm tra phân quyền (`admin` vs `staff`), điều phối giao dịch (transactions). Quản lý `commit()` và `rollback()`.
- **Repository Layer (`petcare/repositories/`)**: Thực thi các câu lệnh SQL có tham số (`?`), nhận kết nối `conn` hoặc factory. Tuyệt đối không tự ý commit transaction khi đang trong luồng điều phối của Service.

## 2. Quy tắc dữ liệu & Bảo mật

- **SQLite**: Luôn kích hoạt `PRAGMA foreign_keys = ON;` trên mọi kết nối mới.
- **Bảo mật mật khẩu**: Sử dụng thuật toán PBKDF2-HMAC-SHA256 với salt ngẫu nhiên (`os.urandom(16)`), không lưu mật khẩu dạng plaintext.
- **Tiền tệ**: Lưu số nguyên (`INTEGER`) đơn vị VND. Không dùng float để tránh sai số dấu phẩy động.
- **Giao dịch khám & tiêm**: Tạo hồ sơ khám (`examinations`) hoặc tiêm (`vaccinations`) phải luôn tạo bản ghi lượt dịch vụ (`service_visits`) tương ứng trong cùng một transaction.
- **Hóa đơn & Thanh toán**:
  - Mỗi lượt dịch vụ (`service_visits`) chỉ được xuất hiện trên đúng một hóa đơn (`visit_id UNIQUE` trên `invoice_items`).
  - Hóa đơn đã thanh toán (`paid`) là bất biến (immutable), không được sửa hoặc hủy.
  - Thanh toán hóa đơn đã thanh toán phải trả về trạng thái `already_paid`, không ghi nhận thêm doanh thu.
  - Doanh thu tính theo ngày thanh toán `paid_at` của các hóa đơn có trạng thái `paid`.
  - Hủy hóa đơn `unpaid` phải xóa các chi tiết `invoice_items` để giải phóng `visit_id`, giữ bản ghi `invoices` với trạng thái `cancelled`.
- **Bảo tồn dữ liệu**:
  - `initialize.py` chỉ chạy `CREATE TABLE IF NOT EXISTS`, không xoá hoặc reset cơ sở dữ liệu đã có.
  - `seed.py` phải có tính bất biến/idempotent (kiểm tra tồn tại trước khi chèn, không tạo dữ liệu trùng lặp khi chạy lại).

## 3. Lệnh kiểm tra và vận hành

### macOS / Linux:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m compileall -q main.py petcare tests
.venv/bin/python -m petcare.database.initialize
.venv/bin/python -m petcare.database.seed
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python main.py
```

### Windows (PowerShell):
```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m compileall -q main.py petcare tests
.venv\Scripts\python.exe -m petcare.database.initialize
.venv\Scripts\python.exe -m petcare.database.seed
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe main.py
```

## 4. Quy ước mã nguồn & Kiểm thử

- Đường dẫn tệp luôn dùng `petcare/config.py` tính từ vị trí mã nguồn, không phụ thuộc vào thư mục làm việc hiện tại (`cwd`).
- Mọi logic nghiệp vụ trọng yếu phải có unit test trong thư mục `tests/` sử dụng SQLite in-memory hoặc tệp tạm thời.
- Giao diện người dùng sử dụng tiếng Việt có dấu, rõ ràng, nhất quán và thân thiện.
