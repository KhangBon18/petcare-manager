# PetCare Manager — cấu trúc repo và quy tắc triển khai

Đây là thiết kế bộ khung để nhóm tạo repo `petcare-manager`. Các chức năng sẽ được triển khai theo Excel 5 tuần; tài liệu này chưa phải ứng dụng hoàn chỉnh. Thành viên: Khang, Quân, Quý, Nhàn. Khang điều phối; mỗi người có 50 giờ công việc dự kiến, đóng góp mục tiêu 25%. Ước lượng bao gồm viết code, sửa lỗi, review và tài liệu, cần cân lại cuối tuần theo thực tế.

## Phạm vi bản nộp

Python, Tkinter/ttk, SQLite. Ứng dụng desktop chạy cục bộ trên Windows/macOS. Không đồng bộ DB qua mạng. Chức năng: đăng nhập Admin/Nhân viên, quản lý tài khoản cơ bản, chủ nuôi, thú cưng, khám, tiêm, lịch hẹn khám/chăm sóc đơn giản, dịch vụ, hóa đơn thanh toán trực tiếp và thống kê.

Matplotlib và ảnh thú cưng là phần thêm sau khi các ca bắt buộc đạt; nhắc lịch email/SMS, kho thuốc và thanh toán trực tuyến để hướng phát triển. Thuốc sử dụng lưu bằng văn bản. Mỗi thú cưng một chủ; chặn đổi chủ nếu đã có hóa đơn trong bản đầu để giữ lịch sử nhất quán. Thú cưng có lịch sử được ngừng theo dõi thay vì xóa.

## Cấu trúc cần tạo

Các đường dẫn dưới đây tính từ thư mục gốc repo. Dùng tên file không dấu, import theo package `petcare`. Tạo `__init__.py` trong mọi thư mục Python package. Không tạo sẵn hàng loạt lớp trống có vẻ đã hoàn thành; file nào chưa làm thì ghi rõ nhiệm vụ trong issue.

| Đường dẫn | Nội dung | Phụ trách |
|---|---|---|
| `main.py` | Điểm chạy duy nhất, gọi ứng dụng | Khang |
| `petcare/__init__.py` | Package ứng dụng | Khang |
| `petcare/app.py` | Một Tk root, điều hướng Frame, phiên đăng nhập | Khang |
| `petcare/config.py` | Đường dẫn DB tính theo thư mục dự án; không phụ thuộc cwd | Nhàn |
| `petcare/security.py` | PBKDF2, salt ngẫu nhiên, so sánh mật khẩu an toàn | Khang |
| `petcare/database/__init__.py` | Package DB | Nhàn |
| `petcare/database/connection.py` | Mở kết nối, bật foreign_keys; quản lý giao dịch | Nhàn |
| `petcare/database/schema.sql` | Tạo bảng, khóa, unique, check | Nhàn tổng hợp; cả nhóm review |
| `petcare/database/initialize.py` | Khởi tạo DB mới, không xóa dữ liệu đã có | Nhàn |
| `petcare/database/seed.py` | Dữ liệu demo giả, seed lặp không nhân đôi | Nhàn |
| `petcare/ui/__init__.py` | Package giao diện | Khang |
| `petcare/ui/common.py`, `theme.py` | Widget dùng chung, thông báo, định dạng | Khang |
| `petcare/ui/login_view.py`, `users_view.py`, `owners_view.py` | Đăng nhập, tài khoản, chủ nuôi | Khang |
| `petcare/ui/pet_profile_view.py` | Màn hình hồ sơ tổng hợp; đọc các module | Khang |
| `petcare/ui/pets_view.py`, `vaccinations_view.py` | Thú cưng và tiêm | Quân |
| `petcare/ui/services_view.py`, `examinations_view.py`, `appointments_view.py` | Danh mục, khám, hẹn | Quý |
| `petcare/ui/reports_view.py` | Bảng thống kê; ghép phần số lượng và hoạt động | Quý; Quân cung cấp query |
| `petcare/ui/visits_view.py`, `invoices_view.py`, `revenue_view.py` | Lượt dịch vụ, hóa đơn và doanh thu; revenue_view nhúng vào reports_view | Nhàn |
| `petcare/services/__init__.py` | Package quy tắc nghiệp vụ | Khang |
| `petcare/services/auth_service.py`, `owner_service.py` | Quyền, tài khoản, chủ nuôi | Khang |
| `petcare/services/pet_service.py`, `vaccination_service.py` | Kiểm tra hồ sơ, tiêm và ngày nhắc | Quân |
| `petcare/services/catalog_service.py`, `exam_service.py`, `appointment_service.py` | Danh mục, khám, lịch hẹn | Quý |
| `petcare/services/visit_service.py`, `invoice_service.py`, `report_service.py` | Khoản phí, thanh toán, tổng hợp báo cáo | Nhàn |
| `petcare/repositories/__init__.py` | Package SQL | Nhàn |
| `petcare/repositories/user_repo.py`, `owner_repo.py` | SQL tài khoản/chủ | Khang |
| `petcare/repositories/pet_repo.py`, `vaccination_repo.py` | SQL thú cưng/tiêm/số lượng | Quân |
| `petcare/repositories/catalog_repo.py`, `exam_repo.py`, `appointment_repo.py` | SQL dịch vụ/khám/hẹn/hoạt động | Quý |
| `petcare/repositories/visit_repo.py`, `invoice_repo.py`, `report_repo.py` | SQL lượt dịch vụ/hóa đơn/doanh thu | Nhàn |
| `tests/__init__.py` | Package kiểm thử, dùng unittest và DB tạm | Cả nhóm |
| `tests/test_auth_service.py`, `test_owner_service.py` | Quyền, đăng nhập, ràng buộc chủ | Khang |
| `tests/test_pet_service.py`, `test_vaccination_service.py` | Hồ sơ, ngày, lịch sử | Quân |
| `tests/test_exam_service.py`, `test_catalog_service.py`, `test_appointment_service.py` | Khám, giá dịch vụ, lịch hẹn | Quý |
| `tests/test_invoice_service.py`, `test_report_queries.py` | Giao dịch, chống tính phí lặp, đối chiếu báo cáo | Nhàn; Quý thêm ca hoạt động |
| `data/.gitkeep` | Giữ thư mục dữ liệu; DB cá nhân không commit | Nhàn |
| `assets/.gitkeep` | Tài nguyên chung nếu cần | Khang |
| `docs/scope.md`, `module_contracts.md`, `architecture.md` | Phạm vi, API dùng chung, kiến trúc | Khang |
| `docs/erd.md`, `data_dictionary.md` | ERD, trường và ràng buộc khớp schema | Quân tổng hợp; cả nhóm bổ sung |
| `docs/billing_rules.md`, `backup_restore.md` | Quy tắc tiền và dự phòng | Nhàn |
| `docs/acceptance_tests.md`, `demo_scenarios.md` | Ca nghiệm thu và tình huống demo | Quý |
| `docs/test_results.md`, `release_checklist.md`, `user_guide.md` | Kết quả, bàn giao, hướng dẫn | Cả nhóm |
| `docs/report/khang.md`, `quan.md`, `quy.md`, `nhan.md` | Nội dung báo cáo của từng người | Từng người |
| `docs/report/final_report.md` | Bản ghép; xuất theo định dạng thầy yêu cầu | Khang |
| `docs/slides/khang.md`, `quan.md`, `quy.md`, `nhan.md`, `final_slides.md` | Nội dung slide; bản trình chiếu cuối tạo tuần 5 | Từng người; Nhàn ghép |
| `README.md`, `CHANGELOG.md`, `.gitignore`, `requirements.txt` | Hướng dẫn, thay đổi, loại file cục bộ, thư viện ngoài | Khang; Nhàn review |
| `.github/pull_request_template.md` | Mẫu PR ngắn: thay đổi, kiểm tra, bằng chứng | Khang |

Tkinter, sqlite3 và unittest thuộc thư viện chuẩn nhưng Tkinter phải được kiểm tra trên mỗi bản cài Python. Giai đoạn đầu chưa có thư viện pip bắt buộc: requirements.txt có thể chỉ chứa chú thích. Nếu dùng Matplotlib, ghi phiên bản đã thử trên cả hai hệ điều hành. Chọn cùng một phiên bản Python đã chạy Tkinter được trên cả bốn máy; ghi rõ phiên bản ấy trong README, không tự động đổi giữa dự án.

## Trách nhiệm và luồng gọi

Giao diện lấy dữ liệu và gọi service. Service kiểm tra dữ liệu, quyền và điều phối transaction. Repository chứa SQL có tham số. Các service gọi repository hoặc API dùng chung, không import giao diện. Repository không gọi service. Không đưa SQL vào callback nút bấm.

Ví dụ thêm thú cưng: PetsView gọi PetService.create_pet(session, data); service kiểm tra chủ, ngày sinh và cân nặng rồi gọi PetRepository; UI làm mới sau khi thành công. Không ép dùng kế thừa để thể hiện OOP. Các lớp có trách nhiệm rõ, truyền repository/connection factory vào constructor và dùng dataclass khi hữu ích là đủ.

## Hợp đồng giữa module phải chốt ở K02

| Hàm dự kiến | Đầu vào | Đầu ra và cam kết |
|---|---|---|
| `AuthService.login(username, password)` | Chuỗi đăng nhập | Session chứa user_id, role; hoặc lỗi đăng nhập; không trả password_hash |
| `OwnerService.create_owner(session, data)` | tên, phone, address | owner_id; dữ liệu đã được kiểm tra |
| `PetService.create_pet(session, data)` | owner_id và trường thú cưng | pet_id; chủ phải tồn tại |
| `VisitRepository.create_visit(conn, pet_id, service_id, performed_at, price_vnd)` | Kết nối của transaction hiện tại | visit_id; không tự commit; kiểm tra ở service |
| `ExamService.record_exam(session, data)` | pet_id, service_id, date, symptoms, diagnosis, medicines | exam_id và visit_id; cả hai lưu cùng transaction |
| `VaccinationService.record_vaccination(session, data)` | pet_id, service_id, vaccine, date, next_due | vaccination_id và visit_id; cả hai lưu cùng transaction |
| `AppointmentService.create_appointment(session, data)` | pet_id, type, scheduled_at, note | appointment_id; chưa tạo khoản phí |
| `InvoiceService.create_invoice(session, owner_id, visit_ids)` | Chủ và các lượt chưa tính tiền | invoice_id; đọc lại giá từ DB; cùng chủ; không trùng lượt |
| `InvoiceService.pay_invoice(session, invoice_id)` | hóa đơn unpaid | paid hoặc kết quả already_paid; không ghi nhận tiền lần hai |
| `InvoiceService.cancel_invoice(session, invoice_id)` | hóa đơn unpaid | cancelled; xóa dòng giữ lượt trong cùng transaction để lượt được lập lại |
| `ReportService.summary(session, start_date, end_date)` | Khoảng ngày hợp lệ | dict có doanh thu, lượt khám, thú cưng đã tiêm, loài, dịch vụ phổ biến |

Tên hàm là thiết kế ban đầu. Khi thay đổi, cập nhật docs/module_contracts.md và báo người gọi trước merge. Service có quyền quyết định commit/rollback; repository nhận conn không được tự kết thúc transaction. Khám/tiêm lấy giá từ danh mục và tạo service_visit đúng một lần.

## Thiết kế dữ liệu tối thiểu

| Bảng | Trường chính và quan hệ |
|---|---|
| users | id, username UNIQUE, password_hash, salt, role, active |
| owners | id, full_name, phone TEXT, address; không mặc định SĐT là duy nhất |
| pets | id, owner_id FK, name, species, breed, sex, birth_date, weight_kg, coat_color, active |
| services | id, name, category, price_vnd INTEGER CHECK >= 0, active |
| service_visits | id, pet_id FK, service_id FK, performed_at, unit_price_vnd INTEGER CHECK >= 0 |
| examinations | id, pet_id FK, visit_id UNIQUE FK, exam_date, symptoms, diagnosis, medicines TEXT |
| vaccinations | id, pet_id FK, visit_id UNIQUE FK, vaccine_name, injection_date, next_due_date, reminder_resolved |
| appointments | id, pet_id FK, type, scheduled_at, status planned/completed/cancelled, note |
| invoices | id, owner_id FK, created_at, status unpaid/paid/cancelled, paid_at nullable; tổng tính từ dòng chi tiết |
| invoice_items | id, invoice_id FK, visit_id UNIQUE FK, service_name_snapshot, pet_name_snapshot, amount_vnd INTEGER |

Một chủ có nhiều thú cưng. Một thú cưng có nhiều lượt dịch vụ. Mỗi lần khám/tiêm liên kết đúng một lượt dịch vụ. Một hóa đơn chứa nhiều lượt của các thú cưng cùng chủ. Không đặt một phí khám trong examinations rồi cộng thêm lại phí từ service_visits.

Tổng hóa đơn tính từ invoice_items. Hóa đơn paid bất biến; không xóa lượt đã có hồ sơ khám/tiêm hoặc đã lập hóa đơn. Hủy hóa đơn unpaid xóa các dòng chi tiết để giải phóng visit_id, giữ header cancelled để tra cứu; bản này không giữ chi tiết hóa đơn bị hủy. Nếu cần giữ đầy đủ chi tiết hủy về sau, phải thay cơ chế ràng buộc và thiết kế dữ liệu.

Giữ service_visits và các hồ sơ đã tạo bất biến về pet_id, service_id và giá trong bản đầu. Sửa nội dung y tế không được tạo khoản phí mới. Các giá trị ngày lưu dạng ISO; quyết định thống nhất giờ cục bộ Asia/Ho_Chi_Minh cho đồ án. Doanh thu theo paid_at; ngày kết thúc lấy hết ngày, truy vấn đến trước 00:00 ngày kế tiếp. Số lượt khám tính examinations; số thú cưng đã tiêm dùng COUNT DISTINCT pet_id; dịch vụ phổ biến tính các lượt thuộc hóa đơn paid.

## Quyền và tính toàn vẹn

Admin quản lý tài khoản và danh mục/giá dịch vụ, đồng thời dùng toàn bộ chức năng nghiệp vụ. Nhân viên quản lý chủ/thú cưng, hồ sơ, lịch hẹn, lượt dịch vụ, hóa đơn và xem báo cáo. Kiểm tra tại service, không chỉ ẩn nút. Không khóa admin hoạt động cuối cùng. Khi gọi service cần xác minh tài khoản hiện còn active; không tin mã vai trò do form nhập.

SQL luôn dùng placeholder. Bật PRAGMA foreign_keys = ON khi mở kết nối. Dùng DB tạm cho test, không thử bằng cách phá dữ liệu làm việc. Ngăn bấm Lưu hai lần tại UI; UNIQUE visit_id bảo vệ chống lập hóa đơn lặp. Thanh toán lại trả already_paid; không có cơ chế chuyển tiền thật trong đồ án.

## Chạy dự án sau khi bộ khung được triển khai

Các lệnh sau là giao diện lệnh nhóm cần xây, chưa chạy được chỉ từ tài liệu này.

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m petcare.database.initialize
.venv\Scripts\python.exe -m petcare.database.seed
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS Terminal:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m petcare.database.initialize
.venv/bin/python -m petcare.database.seed
.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
```

Không cần activate venv khi gọi trực tiếp đường dẫn Python. seed chỉ tạo dữ liệu giả và tài khoản demo được ghi rõ trong README, không dùng dữ liệu cá nhân hoặc mật khẩu thật. Schema.sql CREATE TABLE IF NOT EXISTS không tự cập nhật cấu trúc DB đã có: trước khi thay schema phải chốt cách migration hoặc tạo DB demo mới có sao lưu; không âm thầm reset DB đang dùng.

## Git và review

Tạo repo petcare-manager; main luôn chứa bản chạy được. Nhánh theo task: feature/k01-app-owners, feature/q01-pets, feature/y01-services, feature/n01-database. Mỗi PR gắn mã task, mô tả thay đổi và cách kiểm tra. Review vòng Khang → Quân → Quý → Nhàn → Khang; đây là người review, không phải người tự làm thay.

Sau N01, các module CRUD bắt đầu ghép. Sau N03, khám/tiêm dùng API lượt dịch vụ chung. Sau N05, thống kê lấy dữ liệu paid. Cập nhật main ít nhất giữa và cuối tuần; không chờ đến tuần 5. schema.sql do Nhàn tổng hợp; app.py và common.py do Khang quản lý; reports_view.py do Quý quản lý, revenue_view.py do Nhàn quản lý. Các file tài liệu chung thêm đoạn theo heading, báo nhau trước sửa cùng vùng.

Đưa vào .gitignore: .venv/, __pycache__/, *.pyc, .DS_Store, data/*.db, data/*.db-*, data/*.sqlite*, .env và bản xuất demo cục bộ. Seed và schema được commit; DB mỗi người không commit. Chỉ tạo tag v1.0.0 khi bốn người xác nhận ca nghiệm thu và thử clone mới.

## Sử dụng bảng tiến độ

Mỗi người cập nhật trạng thái và bằng chứng ở sheet tên mình; không nhập lại % ở Tiến độ chung. Chỉ Hoàn thành sau khi đầu ra đạt, PR đã review và người làm giải thích được câu hỏi trong task. Đang làm chưa được tính hoàn thành. Mỗi người có 10 task, 50 giờ dự kiến; 6 giờ tương ứng 12%, 4 giờ tương ứng 8% công việc cá nhân. Tiến độ nhóm là trung bình bốn tiến độ cá nhân theo mục tiêu 25% mỗi người. Đây là tiến độ theo kế hoạch, không phải điểm đóng góp thực tế.

Nhập ngày bắt đầu dự án ở sheet Tiến độ chung để tính lịch 5 tuần liên tiếp. Đây là lịch 35 ngày tương đối, không phải deadline đã được thầy xác nhận. Nếu ngày nộp thực tế khác, chỉnh kế hoạch và cập nhật công thức/ngày thay vì giả định. Các trường ngày của task mặc định là đầu/cuối tuần; có thể đổi sang ngày cụ thể sau khi nhóm chốt, không ghi task phụ thuộc cùng ngày hoàn thành nếu chưa có API.

Không đưa setup hoặc tự học thành task. Hàng tuần ghi nhận giờ thực tế vào bằng chứng, cân lại công việc nếu chênh lệch. Chưa có task code nào được đánh dấu xong. Task tùy chọn tạo mã mới, không âm thầm thêm vào 50 giờ đã phân bổ.

## Kịch bản nghiệm thu tối thiểu

1. Admin và Nhân viên đăng nhập đúng quyền; Nhân viên gọi trực tiếp service đổi giá phải bị chặn.
2. Tạo chị Lan, mèo Miu; khởi động lại vẫn có hồ sơ; chủ không tồn tại và cân nặng âm bị từ chối.
3. Ghi hẹn khám, kết quả khám, lần tiêm, dịch vụ tắm. Hẹn không tự phát sinh phí; khám/tiêm mỗi lần tạo một lượt.
4. Lập hóa đơn gồm khám, tiêm, tắm đúng chủ; đổi giá danh mục không đổi các lượt cũ. Cố tính cùng lượt lần hai bị chặn.
5. Thanh toán hai lần vẫn một hóa đơn paid và một khoản doanh thu. Hóa đơn unpaid/cancelled không tính doanh thu.
6. Hủy hóa đơn unpaid rồi lập lại được; hóa đơn paid không được hủy/sửa. Gây lỗi dòng chi tiết không để lại hóa đơn dở dang.
7. Đối chiếu số loài, số lượt khám, số thú cưng đã tiêm, doanh thu và dịch vụ phổ biến với dữ liệu mẫu đã biết.
8. Kiểm tra ngày cuối kỳ, lịch nhắc đến hạn/quá hạn, hồ sơ inactive và màn hình không có dữ liệu.
9. Clone mới và tạo DB/seed/test/chạy trên Windows và macOS; phục hồi bản sao DB khi app đã đóng.
10. Mỗi người trình bày module mình và giải thích một module khác theo tình huống Lan/Miu.

Tuần 3 hoàn thành chức năng bắt buộc. Tuần 4 sửa lỗi, kiểm thử và tài liệu. Tuần 5 đóng băng tính năng, nghiệm thu và bảo vệ. Yêu cầu chính thức của giảng viên nếu khác phạm vi này phải được đưa vào scope và cân lại task trước triển khai.
