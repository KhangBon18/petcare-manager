# PetCare Manager — Quản lý Phòng khám Thú cưng

Ứng dụng desktop hoàn chỉnh quản lý phòng khám và dịch vụ chăm sóc thú cưng được xây dựng bằng **Python + Tkinter/ttk + SQLite** theo thiết kế kiến trúc 3 lớp phân tầng nghiêm ngặt ([REPO_GUIDE.md](REPO_GUIDE.md)).

Dự án phát triển bởi nhóm: **Khang, Quân, Quý, Nhàn**.

---

## Tính năng Chính

- **Xác thực & Phân quyền**: Đăng nhập Admin và Nhân viên. Mật khẩu được mã hóa an toàn bằng PBKDF2-HMAC-SHA256 kèm salt ngẫu nhiên.
- **Quản lý Chủ nuôi & Thú cưng**: Hồ sơ thông tin cá nhân, thể trạng, giống loài. Bảo vệ lịch sử: Ngừng theo dõi (`active=0`) thay vì xóa khi đã có dữ liệu liên kết.
- **Hồ sơ Khám bệnh**: Ghi nhận triệu chứng, chẩn đoán, kê đơn thuốc và tự động liên kết lượt tính phí dịch vụ trong cùng một giao dịch (transaction).
- **Tiêm phòng & Lịch nhắc**: Ghi nhận mũi tiêm vaccine, ngày hẹn tiêm nhắc lại, bảng theo dõi nhắc nhở đến hạn trong vòng 30 ngày.
- **Lịch hẹn**: Đặt lịch tiếp đón khám/chăm sóc spa; đảm bảo lịch hẹn không tự động sinh phí trước.
- **Lượt Dịch vụ & Hóa đơn**:
  - Ghi nhận các lượt dịch vụ chăm sóc, tắm spa, xét nghiệm.
  - Gom các lượt chưa tính tiền của cùng một chủ nuôi để lập hóa đơn.
  - Đảm bảo mỗi lượt dịch vụ chỉ được tính tiền một lần duy nhất (`visit_id UNIQUE`).
  - Hóa đơn chưa thanh toán (`unpaid`) có thể hủy để giải phóng lượt dịch vụ.
  - Thanh toán trực tiếp tại quầy; hóa đơn đã thanh toán (`paid`) là bất biến.
- **Báo cáo & Thống kê**: Bảng điều khiển phân tích tổng doanh thu thực thu theo kỳ, số ca khám, số thú cưng tiêm phòng, cơ cấu loài và danh sách dịch vụ phổ biến nhất.

---

## Yêu cầu Hệ thống

- **Phiên bản Python**: Đã kiểm tra và tương thích từ Python **3.10** đến **3.13** (Kiểm tra chính thức trên macOS với Python 3.13.3 và Tkinter Tcl/Tk 8.6).
- **Thư viện**: Hoàn toàn sử dụng thư viện chuẩn của Python (`tkinter`, `sqlite3`, `unittest`, `hashlib`, `dataclasses`).

---

## Hướng dẫn Cài đặt và Khởi chạy

Mở cửa sổ dòng lệnh tại thư mục gốc của dự án (`petcare-manager`). Không cần activate môi trường ảo vì các lệnh bên dưới gọi trực tiếp Python trong thư mục `.venv`.

### 1. Dành cho Windows (PowerShell)

```powershell
# Bước 1: Tạo môi trường ảo
py -m venv .venv

# Bước 2: Cài đặt phụ thuộc (nếu có)
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Bước 3: Khởi tạo cấu trúc cơ sở dữ liệu SQLite (an toàn, không xóa DB cũ)
.venv\Scripts\python.exe -m petcare.database.initialize

# Bước 4: Nạp dữ liệu tài khoản và dịch vụ mẫu (chạy lặp an toàn, không nhân đôi dữ liệu)
.venv\Scripts\python.exe -m petcare.database.seed

# Bước 5: Chạy toàn bộ 34 ca kiểm thử tự động
.venv\Scripts\python.exe -m unittest discover -s tests -v

# Bước 6: Khởi chạy giao diện ứng dụng
.venv\Scripts\python.exe main.py
```

### 2. Dành cho macOS / Linux (Terminal)

```bash
# Bước 1: Tạo môi trường ảo
python3 -m venv .venv

# Bước 2: Cài đặt phụ thuộc (nếu có)
.venv/bin/python -m pip install -r requirements.txt

# Bước 3: Khởi tạo cấu trúc cơ sở dữ liệu SQLite (an toàn, không xóa DB cũ)
.venv/bin/python -m petcare.database.initialize

# Bước 4: Nạp dữ liệu tài khoản và dịch vụ mẫu (chạy lặp an toàn, không nhân đôi dữ liệu)
.venv/bin/python -m petcare.database.seed

# Bước 5: Chạy toàn bộ 34 ca kiểm thử tự động
.venv/bin/python -m unittest discover -s tests -v

# Bước 6: Khởi chạy giao diện ứng dụng
.venv/bin/python main.py
```

---

## Tài khoản Dùng thử (Demo)

Dữ liệu mẫu sau khi chạy `seed.py` cung cấp sẵn các tài khoản sau:

| Tên đăng nhập | Mật khẩu | Vai trò | Quyền hạn |
|---|---|---|---|
| `admin` | `Admin@123` | Quản trị viên (Admin) | Toàn quyền hệ thống, quản lý tài khoản nhân viên, đổi giá và thêm dịch vụ |
| `staff1` | `Staff@123` | Nhân viên (Staff) | Quản lý chủ nuôi, thú cưng, khám bệnh, tiêm phòng, lịch hẹn, lập hóa đơn, thanh toán và xem báo cáo |
| `staff2` | `Staff@123` | Nhân viên (Staff) | Tương tự `staff1` |

---

## Kịch bản Dùng thử Nhanh (Lan & Miu)

Sau khi mở ứng dụng:
1. Đăng nhập bằng `staff1` / `Staff@123`.
2. Vào **Chủ nuôi**: Thêm chị *Nguyễn Thị Lan*, SĐT: *0901234567*.
3. Vào **Thú cưng**: Thêm mèo *Miu* (Loài: Mèo, Cân nặng: 3.5 kg, Giới tính: Cái) cho chị Lan. Nhấp đúp vào Miu để xem Hồ sơ tổng hợp.
4. Vào **Lịch hẹn**: Đặt lịch hẹn khám định kỳ cho Miu.
5. Vào **Khám bệnh**: Ghi nhận ca khám cho Miu (Khám bệnh tổng quát - 150.000 đ, Triệu chứng: Hắt hơi, Chẩn đoán: Viêm mũi).
6. Vào **Tiêm phòng**: Ghi nhận tiêm vaccine Dại cho Miu (Tiêm vaccine Dại - 180.000 đ, hẹn tiêm nhắc sau 1 năm).
7. Vào **Lượt dịch vụ**: Ghi nhận thêm dịch vụ chăm sóc *Tắm vệ sinh & Cắt tỉa lông* (200.000 đ).
8. Vào **Hóa đơn**: Bấm *+ Lập hóa đơn mới*, chọn chị Lan. Hệ thống tự gom 3 lượt trên (Tổng tiền: 530.000 đ). Bấm *Tạo hóa đơn*.
9. Bấm *Thanh toán trực tiếp*: Xác nhận thu tiền tại quầy. Hóa đơn chuyển sang trạng thái *Đã thanh toán*.
10. Vào **Thống kê**: Chọn ngày hôm nay để xem doanh thu thực thu cập nhật 530.000 đ cùng top dịch vụ tương ứng.

---

## Cấu trúc Thư mục Dự án

```
petcare-manager/
├── main.py                     # Điểm chạy duy nhất của ứng dụng
├── requirements.txt            # Thư viện ngoài (dự án dùng thư viện chuẩn)
├── REPO_GUIDE.md               # Quy định thiết kế và hợp đồng ban đầu
├── AGENTS.md                   # Quy ước kỹ thuật và hướng dẫn phát triển
├── data/
│   └── petcare.db              # SQLite database cục bộ (được gitignore an toàn)
├── docs/                       # Tài liệu thiết kế, kiến trúc và kiểm thử
│   ├── architecture.md         # Kiến trúc 3 lớp, transaction và bảo mật
│   ├── erd.md                  # Sơ đồ thực thể quan hệ 10 bảng dữ liệu
│   ├── billing_rules.md        # Toàn bộ quy tắc tính phí và bảo toàn doanh thu
│   ├── acceptance_tests.md     # 10 kịch bản nghiệm thu chi tiết
│   ├── demo_scenarios.md       # Kịch bản demo từng bước bảo vệ đồ án
│   ├── backup_restore.md       # Hướng dẫn sao lưu và phục hồi dữ liệu
│   ├── test_results.md         # Báo cáo kết quả kiểm thử toàn diện
│   └── project_status.md       # Nhật ký trạng thái hoàn thiện dự án
├── petcare/                    # Package mã nguồn chính
│   ├── app.py                  # Controller Tkinter, phiên và điều hướng
│   ├── config.py               # Đường dẫn tuyệt đối chuẩn hóa theo dự án
│   ├── security.py             # Băm mật khẩu PBKDF2-HMAC-SHA256
│   ├── database/               # Quản lý kết nối, schema và dữ liệu mẫu
│   │   ├── connection.py       # Kết nối SQLite, bật PRAGMA foreign_keys
│   │   ├── schema.sql          # Định nghĩa 10 bảng dữ liệu chuẩn
│   │   ├── initialize.py       # Tạo bảng an toàn (CREATE TABLE IF NOT EXISTS)
│   │   └── seed.py             # Nạp dữ liệu demo an toàn (idempotent)
│   ├── repositories/           # Tầng thực thi SQL có tham số
│   ├── services/               # Tầng nghiệp vụ, phân quyền và transaction
│   └── ui/                     # Tầng giao diện Tkinter/ttk thuần tiếng Việt
└── tests/                      # Bộ kiểm thử tự động toàn diện (34 unit & integration tests)
```

---

## Lưu ý Kỹ thuật

- **Bảo toàn dữ liệu**: Database được lưu độc lập trên máy của mỗi thành viên tại `data/petcare.db`. Không commit file database, thư mục `.venv` hay file cache lên Git.
- **Độc lập nền tảng**: Mã nguồn sử dụng `Path` chuẩn hóa trong `petcare/config.py`, chạy mượt mà trên cả Windows và macOS mà không bị lỗi đường dẫn cứng.
