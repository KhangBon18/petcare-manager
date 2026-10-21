# Petcare Manager — chuyển sang quản lý cửa hàng thú cưng

## 1. Các quyết định đã chốt

- Yêu cầu mới của giảng viên: giao diện HTML/CSS, cơ sở dữ liệu MySQL, thay dịch vụ bằng sản phẩm.
- Sơ đồ mới: Đăng nhập, Khách hàng, Thú cưng, Sản phẩm.
- Khang đã chọn: thú cưng là các cá thể của cửa hàng để bán, không phải hồ sơ bệnh án của thú cưng do khách mang đến.
- Backend vẫn bằng Python. Giải pháp triển khai đề xuất: Flask + Jinja2, HTML/CSS, JavaScript thuần khi cần; MySQL qua mysql-connector-python.
- Đây là ứng dụng quản trị nội bộ chạy trên localhost. Chưa làm website thương mại điện tử công khai, tài khoản khách mua online, cổng thanh toán hoặc deploy Internet.
- Solo với Khang trên nhánh `solo/khang-petcare`. Chỉ push sao lưu nhánh này nếu cần. Không push/merge main, tạo PR hoặc tạo/cập nhật tag phát hành đến khi Khang yêu cầu bàn giao.
- Hoàn thiện bản cơ bản và QC trước, tính năng nâng cao sau. Kế hoạch và cấu trúc Tkinter/SQLite cũ là tài liệu lịch sử, không còn là đặc tả triển khai hiện hành.

Ảnh và lựa chọn trên xác nhận phạm vi chính. Flask, cấu trúc bảng, quy tắc bán hàng và các mốc dưới đây là giải pháp đề xuất để Agent triển khai, không phải nội dung được giảng viên xác nhận từng chi tiết.

## 2. Mục tiêu bản cơ bản

Nhân viên đăng nhập, tìm/tạo khách hàng, quản lý sản phẩm và thú cưng còn bán, lập hóa đơn gồm sản phẩm và/hoặc thú cưng, xác nhận thanh toán tại quầy. Khi thanh toán thành công, tồn sản phẩm giảm đúng số lượng và thú cưng chuyển sang đã bán, gắn người mua. Xem lại hóa đơn, số liệu doanh thu và hàng còn bán được. Dữ liệu tồn tại sau khi tắt/mở ứng dụng.

Không đưa khám bệnh, tiêm phòng, lịch nhắc, lịch hẹn chăm sóc và dịch vụ spa vào menu, DB mới hoặc test bắt buộc. Không chỉ đổi nhãn Dịch vụ thành Sản phẩm trên cấu trúc lượt dịch vụ cũ: sản phẩm có tồn kho, mỗi dòng bán có số lượng và thú cưng chỉ bán được một lần.

| Module | Chức năng phải có | Điều kiện hoàn thành |
|---|---|---|
| Đăng nhập/tài khoản | Admin, Nhân viên, đăng xuất, khóa tài khoản | Quyền được kiểm tra từ user hiện tại trong DB; phiên bị khóa/hạ quyền không giữ quyền cũ |
| Khách hàng | Thêm/sửa/tìm, ngừng sử dụng khi có hóa đơn | Hóa đơn và người mua thú cưng liên kết đúng khách; không mất lịch sử |
| Thú cưng để bán | Mã, tên, loài, giống, giới tính, ngày sinh, cân nặng, màu lông, giá bán, trạng thái | Mỗi hàng là một cá thể; chưa bán chưa có người mua; đã bán có người mua; ảnh để sau |
| Sản phẩm | Mã, tên, danh mục, giá, số lượng tồn, trạng thái; nhập/điều chỉnh tồn có lý do | Tồn không âm, số lượng nguyên; điều chỉnh trực tiếp không dùng để sửa giao dịch bán |
| Hóa đơn | Chọn khách, thêm sản phẩm/số lượng và thú cưng, xem tổng, thanh toán hoặc hủy chưa trả | Server tự tính tiền, snapshot tên/giá; paid không sửa/hủy; thanh toán lặp không tác động lần hai |
| Thống kê | Doanh thu theo paid_at, hóa đơn paid, sản phẩm bán chạy theo số lượng, thú cưng đã bán và tồn hiện tại | Loại hóa đơn chưa trả/hủy; mốc ngày đúng; khớp dữ liệu MySQL thật |

Admin quản lý tài khoản, giá, danh mục, thêm thú cưng và nhập/điều chỉnh tồn. Nhân viên được xem hàng, quản lý khách, lập và thanh toán hóa đơn, xem báo cáo. Quyền chỉnh danh mục/tồn dành cho Admin trong bản đầu. Không có đăng ký tài khoản công khai.

## 3. Phần giữ lại và phần thay

| Thành phần cũ | Cách xử lý |
|---|---|
| Mô hình service/repository, một số kiểm tra tên/SĐT/ngày và bảo mật mật khẩu | Rà soát rồi tái sử dụng phần phù hợp, không giữ nguyên quyền dựa trên role cũ |
| Chủ nuôi | Chuyển thành khách hàng; khách có thể mua sản phẩm mà chưa mua thú cưng |
| Thú cưng gắn chủ bắt buộc | Viết lại thành cá thể hàng hóa; người mua là nullable trước thanh toán |
| Tkinter, Tk root, Frame và test điều hướng Tk | Thay bằng Flask route, Jinja template và CSS; giữ lịch sử trong Git, không còn là dependency chạy web |
| SQLite, PRAGMA, sqlite3.Row, dấu ? và executescript | Viết lại kết nối, cursor và SQL đúng MySQL; không chỉ sửa tên driver |
| Khám/tiêm/hẹn và lượt dịch vụ | Đưa ra khỏi phạm vi hiện hành, không bê các bảng này vào schema mới |
| Hóa đơn dựa trên visit_id UNIQUE | Viết lại dòng bán sản phẩm/thú cưng, số lượng, transaction tồn kho và chống thanh toán lặp |
| File data/quan_ly_thu_cung.sql của Nhàn | Đọc tham khảo các bảng/tên/trường của cửa hàng; giữ bản gốc. Không tự chạy dump có DROP TABLE vào DB hiện có |
| Hồ sơ/dữ liệu clinic cũ | Giữ nguyên bản cũ. Không tự chuyển thú cưng của khách thành thú cưng đang bán |

Trước chuyển đổi, kiểm tra và ghi nhận Git status/commit. Nếu có thay đổi hợp lệ chưa commit, tạo checkpoint sau khi loại file bí mật/DB cục bộ. Không reset/clean/ghi đè. Không cần giữ hai ứng dụng desktop và web cùng hoạt động: lịch sử Git bảo toàn bản desktop, bản hiện hành tập trung web.

## 4. Kiến trúc và cấu trúc repo đích

Trình duyệt gửi request tới Flask. Route đọc form và gọi service. Service kiểm tra quyền, dữ liệu và điều phối transaction. Repository chứa SQL có tham số. Route render Jinja template hoặc redirect sau POST thành công. CSS và JS phục vụ từ static của chính ứng dụng để demo local không phụ thuộc CDN.

| Đường dẫn | Trách nhiệm |
|---|---|
| run.py | Điểm chạy web trên 127.0.0.1, ví dụ cổng 5000 |
| petcare/__init__.py | create_app, đăng ký Blueprint, extension và error handler |
| petcare/config.py | Cấu hình từ môi trường, tên DB và đường dẫn tài nguyên |
| petcare/auth.py | Nạp user hiện tại từ DB, login/admin guards; dùng chung trong service |
| petcare/security.py | Hash/verify mật khẩu; không lưu plaintext |
| petcare/database/connection.py | MySQL connection, dictionary cursor, transaction và cleanup |
| petcare/database/schema.sql | Schema MySQL hiện hành, InnoDB, utf8mb4, ràng buộc/index |
| petcare/database/initialize.py; seed.py | Khởi tạo schema có kiểm soát và nạp demo lặp an toàn |
| petcare/routes/ | auth, users, customers, pets, products, invoices, reports |
| petcare/services/ | auth, customer, pet, product, invoice, report; quy tắc nghiệp vụ |
| petcare/repositories/ | user, customer, pet, product, invoice, report; SQL MySQL |
| petcare/templates/base.html | Layout/sidebar/thông báo dùng chung |
| petcare/templates/auth/; customers/; pets/; products/; invoices/; reports/; users/ | Các trang HTML, form thêm/sửa và chi tiết |
| petcare/static/css/; js/ | Giao diện và tương tác nhỏ, không đặt tính toán tiền làm nguồn tin duy nhất ở JS |
| tests/unit/; tests/integration/; tests/web/ | Kiểm tra logic, MySQL, route/form/phân quyền |
| .env.example | Chỉ biến mẫu: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY |
| requirements.txt; requirements-dev.txt | Phụ thuộc runtime/test thực sự dùng và phiên bản đã thử |
| README.md; AGENTS.md; REPO_GUIDE.md | Hướng dẫn mới về web/MySQL và lệnh chạy/test |
| docs/archive/REPO_GUIDE_DESKTOP.md | Lưu đặc tả desktop cũ; không dẫn Agent tiếp tục triển khai theo bản này |
| docs/scope.md; architecture.md; erd.md; data_dictionary.md; billing_rules.md | Thiết kế khớp bản cửa hàng |
| docs/implementation_plan.md; project_status.md; acceptance_tests.md; test_results.md | Tiến độ theo mốc và bằng chứng đã kiểm tra |

Giữ package petcare để ít thay đổi import không cần thiết. Cấu trúc phải đơn giản, thể hiện OOP ở lớp service/repository. Không thêm React, microservice hoặc API riêng cho từng thao tác nếu form HTML đã đáp ứng.

## 5. Thiết kế dữ liệu đề xuất

Tên bảng có thể map từ script tiếng Việt của Nhàn, nhưng phải có một schema chuẩn duy nhất và data_dictionary giải thích mapping. Không để ứng dụng dùng một schema còn báo cáo/seed dùng schema khác.

| Bảng | Trường và quan hệ tối thiểu |
|---|---|
| users | id, username UNIQUE, password_hash, salt nếu thuật toán cần, full_name, role, active, created_at |
| customers | id, full_name, phone dạng chuỗi, address, active, created_at |
| pets | id, code UNIQUE, name, species, breed, sex, birth_date DATE nullable, weight_kg, coat_color, sale_price_vnd, sale_status available/sold/inactive, buyer_id FK nullable, sold_at nullable |
| products | id, code UNIQUE, name, category, unit_price_vnd, stock_qty nguyên không âm, active |
| invoices | id, customer_id FK, created_by FK users, created_at DATETIME, status unpaid/paid/cancelled, paid_at nullable |
| invoice_items | id, invoice_id FK, item_type product/pet, product_id FK nullable, pet_id FK nullable, item_code_snapshot, name_snapshot, unit_price_vnd, quantity, line_total_vnd hoặc tính từ giá nhân số lượng |
| stock_movements | id, product_id FK, quantity_delta nguyên, reason, created_by FK, invoice_id FK nullable, created_at; ghi nhận nhập/điều chỉnh và trừ do bán |

Đã triển khai: giá/tổng dùng `DECIMAL(20,4)` và Python `Decimal`, Babel/CLDR cung cấp minor unit theo mã tiền tệ. Cửa hàng hiện tại được backfill giá từ các cột VND cũ, hóa đơn lưu `currency_code`, còn `*_vnd` giữ tạm cho tương thích/rollback. Không dùng float cho nghiệp vụ tiền.

Mỗi invoice_item tham chiếu đúng một product hoặc một pet theo item_type. Dòng product có quantity > 0; dòng pet bắt buộc quantity = 1. Một cá thể không được xuất hiện hai lần trong cùng hóa đơn. Không UNIQUE pet_id trên toàn bộ lịch sử invoice_items nếu vẫn giữ dòng của hóa đơn bị hủy/chưa trả; chống bán hai lần bằng transaction và trạng thái bán.

Buyer chỉ gắn khi thanh toán. Người dùng không sửa trực tiếp sale_status thành sold hay buyer_id bằng form thú cưng. Thú cưng sold không được đổi người mua/giá bán lịch sử bằng CRUD. Dùng trạng thái inactive để ngừng bán cá thể chưa bán.

Ngày trong DB dùng DATE/DATETIME thích hợp. Parse/chuẩn hóa input ở server. Báo cáo dùng khoảng từ đầu ngày đến trước đầu ngày kế tiếp, không so sánh chuỗi ngày nhập tự do.

## 6. Quy tắc hóa đơn, tồn kho và chống bán lặp

1. Tạo hóa đơn unpaid phải có khách hàng và ít nhất một dòng. Server đọc tên/giá từ DB, xác thực mã hàng và quantity, tạo snapshot. Client không quyết định tổng tiền.
2. Chưa thanh toán thì chưa trừ tồn, chưa đánh dấu thú cưng đã bán. Bản đầu không có giữ chỗ/đặt cọc. Hóa đơn unpaid không bảo đảm hàng vẫn còn khi thanh toán.
3. Các dòng và snapshot giá giữ nguyên sau khi tạo hóa đơn. Muốn đổi hóa đơn unpaid thì hủy rồi lập lại trong bản cơ bản.
4. Thanh toán bắt đầu một MySQL transaction. Khóa dòng hóa đơn; kiểm tra lại trạng thái. Paid trả already_paid; cancelled bị từ chối.
5. Khóa các sản phẩm và cá thể theo thứ tự ổn định. Gộp số lượng theo sản phẩm, kiểm tra active/tồn và trạng thái available của thú cưng ngay tại thanh toán.
6. Trong cùng transaction, trừ tồn, ghi stock_movements, chuyển thú cưng sang sold và buyer_id của khách trên hóa đơn, rồi đánh dấu invoice paid với paid_at. Bất kỳ bước nào lỗi đều rollback.
7. Hai yêu cầu mua cá thể cuối cùng hoặc đơn vị tồn cuối cùng không được cùng thành công. Chọn cách khóa/cập nhật có điều kiện đúng InnoDB; thêm integration test hai kết nối để chứng minh.
8. Gửi lại thanh toán, double-click hoặc hai tab cùng thanh toán một hóa đơn không được trừ tồn/đổi buyer/ghi doanh thu lần hai. Vô hiệu nút ở UI chỉ là hỗ trợ, không thay bảo vệ tại DB/service.
9. Hủy unpaid giữ hóa đơn cancelled và dòng snapshot, không tăng tồn vì chưa trừ tồn. Paid không được sửa/hủy; refund/trả hàng để nâng cao.
10. Đổi giá hoặc tên danh mục không thay snapshot hóa đơn. Không xóa khách/hàng có lịch sử tham chiếu; dùng active/inactive phù hợp.

Không dùng visit_id hay nguyên tắc xóa invoice_items để giải phóng lượt dịch vụ của bản clinic trong schema bán hàng mới.

## 7. Yêu cầu web và kiểm tra quyền

- Session chỉ lưu định danh tối thiểu. Mỗi request có bảo vệ và mỗi thao tác service cần xác minh tài khoản còn active/quyền hiện tại từ DB. Không tin role gửi từ form/cookie đã cũ.
- Mọi hành động tạo/sửa/xóa/thanh toán/đăng xuất dùng POST với CSRF token; GET không thay đổi dữ liệu. Có thể dùng Flask-WTF/CSRFProtect để tránh tự dựng cơ chế token.
- Mật khẩu băm; SECRET_KEY và mật khẩu MySQL nằm trong .env đã gitignore. .env.example chỉ có placeholder. Session HttpOnly, SameSite phù hợp; cấu hình Secure theo môi trường HTTPS, không gây hỏng localhost HTTP.
- SQL dùng cursor.execute(sql, params) với placeholder MySQL; không nối/f-string dữ liệu người dùng vào SQL. Sort/filter phải có allowlist.
- Jinja giữ autoescape cho dữ liệu nhập; kiểm tra dữ liệu server-side, giữ lại form khi lỗi, thông báo tiếng Việt rõ ràng.
- Sửa lỗi input ngày/giờ không hợp lệ và phiên bị thu hồi ngay trong bản web. Test mở trang không được che lỗi ứng dụng bằng skip vì thiếu dependency/môi trường.
- Giao diện có layout thống nhất, bảng tìm kiếm/lọc/phân trang đơn giản, form thêm/sửa, trang chi tiết hóa đơn và xác nhận thanh toán. Hoạt động trên trình duyệt desktop Windows/macOS và kích thước màn hình thông dụng.

## 8. Chuyển đổi theo mốc và cách nghiệm thu

| Mốc | Công việc | Điều kiện qua mốc |
|---|---|---|
| 0. Checkpoint | Dừng triển khai Tkinter/SQLite, ghi nhận trạng thái, lưu đặc tả cũ, cập nhật AGENTS/REPO_GUIDE/scope | Nhánh solo đúng, thay đổi cũ còn nguyên, không main/PR/tag; tài liệu mới không mâu thuẫn |
| 1. Web và MySQL | Flask factory, cấu hình, schema, seed, đăng nhập/quyền, layout HTML/CSS | Mở localhost, đăng nhập thật với user MySQL; seed chạy hai lần không nhân đôi |
| 2. Danh mục cửa hàng | Khách hàng, thú cưng để bán, sản phẩm, nhập/điều chỉnh tồn | Thêm/sửa/tìm được qua trình duyệt, tắt/mở vẫn có dữ liệu; hàng sold được bảo vệ |
| 3. Bán hàng | Hóa đơn chung sản phẩm/thú cưng, thanh toán và báo cáo | Thanh toán chỉ một lần, không tồn âm/bán trùng, rollback lỗi và số liệu đối chiếu đúng |
| 4. QC và bàn giao nội bộ | Test, UI thực tế, clean setup, README Windows/macOS và trạng thái | Đủ bằng chứng và giới hạn; commit/push chỉ nhánh solo; chưa release |

Agent tự thực hiện các mốc, kiểm tra và sửa lỗi trước khi chuyển tiếp, không đòi Khang duyệt lại lựa chọn triển khai thường lệ. Ghi quyết định/khác biệt vào project_status. Nếu thiếu MySQL hoặc thông số kết nối, hoàn thiện phần không bị chặn, cung cấp bước cấu hình local rõ ràng; báo đúng phần integration chưa chạy. Không thay bằng SQLite hoặc mock rồi kết luận đã kiểm tra MySQL.

Chưa phát triển biểu đồ, upload ảnh, PDF hóa đơn, quản lý nhà cung cấp, đặt hàng online, gửi email/SMS hoặc kho thuốc cho tới khi phần bắt buộc qua QC.

## 9. Kiểm thử bắt buộc và demo chuẩn

Unit test kiểm tra quy tắc thuần. Test tích hợp repository, transaction, khóa và kiểu dữ liệu phải chạy với MySQL thật trong DB test tách biệt, được cấu hình rõ. Test không dùng DB làm việc hoặc dữ liệu cá nhân. Web test dùng Flask test client; kiểm CSRF, đăng nhập, role, mã lỗi và template, không chỉ tìm HTTP 200.

Ca nghiệm thu:

1. Admin/Nhân viên đăng nhập; Nhân viên bị chặn URL/POST quản lý tài khoản/giá/tồn.
2. Tài khoản đang đăng nhập bị khóa/hạ quyền: request và nghiệp vụ sau đó không giữ quyền cũ.
3. Seed lặp, restart app/MySQL và đọc lại dữ liệu; tên tiếng Việt không lỗi mã hóa.
4. Thêm khách Lan; sản phẩm thức ăn 100.000đ tồn 10; phụ kiện 50.000đ tồn 5; cá thể mèo Miu giá 2.000.000đ trạng thái available.
5. Lập hóa đơn Lan mua 2 thức ăn, 1 phụ kiện và Miu: tổng server là 2.250.000đ. Chưa trả: tồn vẫn 10/5, Miu chưa có người mua.
6. Thanh toán: tồn thành 8/4, Miu sold/buyer Lan; doanh thu tăng đúng 2.250.000đ. Gửi lại thanh toán không làm thay đổi lần hai.
7. Hai khách cùng trả hóa đơn mua Miu hoặc hàng còn 1: chỉ một giao dịch thành công. Không còn phần hóa đơn/tồn thay đổi dở dang ở giao dịch thất bại.
8. Hủy unpaid không tăng tồn. Không hủy/sửa paid. Đổi giá danh mục không đổi hóa đơn đã tạo.
9. Số lượng âm/0/số lẻ, tồn âm, thú cưng đã bán, ngày sinh tương lai, giá/tổng bị sửa từ trình duyệt đều bị chặn đúng.
10. Gây lỗi giữa transaction: tồn, thú cưng, invoice, movement cùng rollback. Đối chiếu report theo paid_at và ngày cuối kỳ; unpaid/cancelled không tính doanh thu.
11. Thiếu/sai CSRF token bị chặn, GET không tạo/xóa/thanh toán; HTML nhập vào trường tên hiển thị như văn bản.
12. Setup sạch theo README trên môi trường thật đã có; ghi riêng các bước chưa thử trên Windows. Chụp trang đăng nhập, dashboard, danh mục, form, hóa đơn và báo cáo bằng trình duyệt.

## 10. Dữ liệu và hướng dẫn local

Dùng database mới, ví dụ `petcare_shop_dev`, để tránh đụng SQLite clinic hoặc MySQL của Nhàn. Đọc script của Nhàn để map fields, không chạy các DROP/CREATE DATABASE của dump vào DB hiện hữu. Không tự import tài khoản password plaintext từ dump. Demo user mới được seed với mật khẩu băm.

README phải có: phiên bản Python/MySQL/driver thực sự kiểm tra; tạo venv, cài requirements, tạo MySQL database/user local, điền .env, init schema, seed, run web, test; xử lý cổng/kết nối thường gặp. Khai báo rằng MySQL là tiến trình local cần chạy cùng Flask. Docker Compose có thể thêm như lựa chọn đóng gói sau, không là điều kiện để code ban đầu chạy nếu MySQL local đã có.

Mỗi máy sau bàn giao có DB độc lập; Git chia sẻ schema/seed/mã nguồn. Không commit .env, data cá nhân, database dump cá nhân, .venv hoặc cache. File SQL mẫu sẵn có của thành viên giữ nguyên hoặc lưu tham khảo có ghi chú, không tự xóa.

## 11. Cập nhật tài liệu và báo cáo cuối mốc

Thay hướng dẫn hiện hành Tkinter/SQLite trong README/AGENTS/REPO_GUIDE bằng web/MySQL, đồng thời lưu bản cũ và giải thích thay đổi phạm vi. Cập nhật ERD, billing rules, demo, acceptance tests và trạng thái hiện hành. Báo cáo/slide cũ đánh dấu cần chỉnh theo cửa hàng, không tuyên bố đã hoàn thành khi chỉ còn nội dung clinic.

Mỗi lần bàn giao cho Khang: ghi nhánh, commit, đã push nhánh solo hay chưa, module xong, lệnh test thực tế với passed/failed/skipped, MySQL đã dùng, URL local và ảnh giao diện, giới hạn còn lại. Không tạo PR/merge main/tag. Mã đã qua QC nội bộ mới được Khang quyết định đưa sang giai đoạn bàn giao/nâng cao.

## 12. Tài liệu kỹ thuật đối chiếu

- Flask Quickstart, templates/static/session: https://flask.palletsprojects.com/en/stable/quickstart/
- Flask templates và HTML autoescape: https://flask.palletsprojects.com/en/stable/tutorial/templates/
- Connector/Python execute và tham số: https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-execute.html
- Connector/Python transaction: https://dev.mysql.com/doc/connectors/en/connector-python-example-cursor-transaction.html

Các nguồn trên hỗ trợ cách dùng công nghệ. Schema và quy tắc cửa hàng trong tài liệu này là thiết kế riêng cho đồ án theo phạm vi đã trao đổi.
