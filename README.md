# PetCare Manager

Đồ án Python của Khang, Quân, Quý, Nhàn. Thiết kế gốc: [REPO_GUIDE.md](REPO_GUIDE.md).

Hiện tại chỉ có bộ khung Tkinter/ttk: một cửa sổ gốc, điều hướng bằng Frame và thông báo nhiệm vụ ở từng màn hình. Chưa có đăng nhập, phân quyền, lưu dữ liệu, schema, seed hay thanh toán. Không có tài khoản demo ở giai đoạn này.

## Chuẩn bị

Dùng Python 3 có Tkinter. Nhóm **chưa chốt phiên bản Python chung**: cả bốn người cần thử Tkinter trên Windows/macOS rồi ghi phiên bản thống nhất vào đây trước khi triển khai nghiệp vụ. Máy dựng bộ khung có Python 3.13.3, Tk 8.6; đây chưa phải xác nhận tương thích cho bốn máy.

Mở terminal tại thư mục chứa `main.py`. Không cần activate môi trường ảo vì các lệnh bên dưới gọi trực tiếp Python trong `.venv`. Hiện `requirements.txt` chỉ chứa chú thích, chưa cần thư viện pip ngoài.

## Windows — PowerShell

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m tkinter
.venv\Scripts\python.exe main.py
```

Lệnh `-m tkinter` phải mở được cửa sổ kiểm tra; đóng cửa sổ đó trước khi chạy ứng dụng. Nếu `py` không có, dùng `python` từ bản Python đã cài. Nếu thiếu Tkinter, sửa bản cài Python để có Tcl/Tk rồi thử lại.

## macOS — Terminal

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tkinter
.venv/bin/python main.py
```

Nếu báo thiếu `_tkinter` hoặc không mở được cửa sổ, dùng bản Python có Tcl/Tk hoạt động và tạo lại `.venv` bằng bản đó. Không cài Tkinter bằng pip.

Có thể chạy từ thư mục khác bằng đường dẫn đến Python và `main.py`, ví dụ `"/duong/dan/petcare-manager/.venv/bin/python" "/duong/dan/petcare-manager/main.py"`. `petcare/config.py` luôn tính `data/petcare.db` theo vị trí dự án, không theo thư mục chạy lệnh. Bộ khung chỉ khai báo đường dẫn, chưa tạo file DB.

**Chưa chạy** `python -m petcare.database.initialize` hoặc `python -m petcare.database.seed`: hai module này dành cho task tuần 1 của Nhàn và chưa tồn tại.

## Cấu trúc và luồng chạy

- `main.py`: điểm chạy duy nhất, gọi `petcare.app.run()`.
- `petcare/app.py`: tạo một `Tk`, bố cục điều hướng, thay Frame nội dung và chạy `mainloop()`.
- `petcare/ui/`: các Frame; hiện `common.py` cung cấp `PendingView` cho mọi màn hình chưa triển khai.
- `petcare/config.py`: đường dẫn dự án, dữ liệu, DB và tài nguyên.
- `petcare/services/`: dành cho kiểm tra dữ liệu, quyền và điều phối giao dịch.
- `petcare/repositories/`: dành cho SQL có tham số; không tự kết thúc giao dịch do service quản lý.
- `petcare/database/`: dành cho kết nối SQLite, schema, initialize và seed.
- `tests/`: dành cho unittest với DB tạm; hiện chưa có test nghiệp vụ.
- `data/`: DB cục bộ mỗi người, không commit. `assets/`: tài nguyên chung.
- `docs/`: nhiệm vụ còn lại và tài liệu; `report/`, `slides/` dành cho bài báo cáo, nội dung slide.
- `.github/`: mẫu pull request.

Luồng hiện tại: `main → app.run → Tk + PetCareApp → show_screen → PendingView`. Bấm điều hướng hủy Frame cũ và tạo Frame mới trong cùng root. Điều hướng này chỉ để xem bộ khung, chưa thể hiện quyền truy cập. Sau này: **UI → service → repository → SQLite**, service không import UI và callback UI không chứa SQL.

## Phần việc tiếp theo

Xem [docs/pending_tasks.md](docs/pending_tasks.md). Chỉ tạo module nghiệp vụ khi làm task tương ứng, không tạo hàng loạt lớp trống. API, schema và seed sẽ được nhóm chốt theo thiết kế và task tuần 1; chưa đánh dấu task hoàn thành chỉ vì có bộ khung.

## Kiểm tra

Windows dùng `.venv\Scripts\python.exe`, macOS dùng `.venv/bin/python` thay cho `python` trong các lệnh:

```bash
python -m compileall -q main.py petcare tests
python -c "import main, petcare.app, petcare.config; print('Import OK')"
python -m unittest discover -s tests -v
```

Hiện unittest sẽ báo **0 test**; kết quả này không xác nhận nghiệp vụ đúng. Kết quả kiểm tra bộ khung được ghi trong [docs/test_results.md](docs/test_results.md). Cần kiểm tra thủ công giao diện trên cả Windows và macOS của nhóm.

## Làm việc nhóm

Nhánh theo task trong REPO_GUIDE; PR ghi mã task, thay đổi và bằng chứng. Review vòng Khang → Quân → Quý → Nhàn → Khang. Không commit DB, `.venv`, dữ liệu cá nhân hoặc file xuất demo; đặt bản xuất cục bộ trong `exports/` hoặc `demo_exports/`. Mỗi thành viên cập nhật tiến độ theo đầu ra thực tế và review.
