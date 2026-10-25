# PetCare Manager — cửa hàng thú cưng

Phiên bản hiện hành là ứng dụng quản trị nội bộ chạy trên localhost, dùng Python + Flask + MySQL, với giao diện HTML/CSS. Không dùng Tkinter cho UI. Phần mềm không phải website thương mại điện tử công khai.

## Phạm vi

- Đăng nhập và phân quyền Admin/Staff, quản lý tài khoản.
- Khách hàng: thêm, sửa, tìm kiếm và ngừng sử dụng mà vẫn giữ lịch sử.
- Thú cưng là từng cá thể của cửa hàng để bán, có mã, thông tin, giá, trạng thái và người mua sau khi thanh toán.
- Sản phẩm có mã, danh mục, giá, tồn kho và nhật ký nhập/điều chỉnh.
- Hóa đơn POS hai vùng với catalog ảnh/giá/tồn, giỏ hàng và modal thêm nhanh khách hàng; sản phẩm theo số lượng, từng cá thể thú cưng có số lượng 1.
- Thanh toán quầy theo transaction; tồn và trạng thái thú cưng chỉ thay đổi sau thanh toán.
- Báo cáo doanh thu theo ngày, kỳ so sánh, bản tin Python, Excel từ snapshot đã ký và bản in PDF qua trình duyệt.
- Trợ lý tra cứu toàn danh mục trả card hồ sơ; gợi ý nhập kho có công thức từ lượng bán paid 14/30 ngày; tìm ảnh có bộ lọc/giải thích và gợi ý thuộc tính có duyệt.
- Giao diện tiếng Việt, responsive trên desktop và màn hình thông dụng.

Khám bệnh, tiêm phòng, lịch nhắc, lịch hẹn chăm sóc, dịch vụ spa và lượt dịch vụ đã ra khỏi phạm vi. Mô tả desktop cũ được lưu ở docs/archive/.

## Cấu trúc

- run.py: chạy Flask ở 127.0.0.1:5055.
- petcare/__init__.py: app factory, đăng ký blueprint và CSRF.
- petcare/config.py: cấu hình từ môi trường/.env.
- petcare/auth.py, security.py: session, phân quyền và băm mật khẩu.
- petcare/database/: kết nối MySQL, schema, initialize và seed.
- petcare/routes/: auth, dashboard, users, customers, pets, products, invoices, reports.
- petcare/services/: xác thực dữ liệu, quyền và transaction.
- petcare/repositories/: truy vấn MySQL tham số hóa.
- petcare/templates/: HTML/Jinja; petcare/static/: CSS/JS.
- tests/: unit, web và test tích hợp MySQL có cấu hình DB test riêng.

## Chạy local

1. Cài Python 3.11+, MySQL 8.0.16+ và tạo một database/user local riêng tên petcare_shop_dev.
2. Tạo venv, cài requirements, sao chép .env.example thành .env và điền kết nối DB local cùng SECRET_KEY.
3. Khởi tạo schema bằng python -m petcare.database.initialize.
4. Tạo dữ liệu demo bằng python -m petcare.database.seed trên `_dev`/`_test`; chạy lại khi chuẩn bị để làm mới ngày mẫu và bù ảnh thiếu, không trừ kho lặp. Schema có 20 bảng; seed chuẩn có 12 khách, 22 sản phẩm, 74 thú cưng, 68 ảnh và 7 hóa đơn.
5. Chạy python run.py và mở http://127.0.0.1:5055.

Chi tiết từng hệ điều hành và cách nghiệm thu nằm trong README.md. Không đưa .env, database dump cá nhân hoặc dữ liệu thật lên Git.

## Tổng duyệt nhanh Phase 4

Giữ `python run.py` chạy, rồi ở terminal thứ hai gọi `python run.py prepare-demo` (hoặc thêm `--json`). Lệnh có ngân sách 4,7 giây, kiểm đúng server/MySQL và chỉ làm mới timestamp của marker demo đã thu; exit 0 mới xác nhận sẵn sàng. Seed đầy đủ thực hiện trước đó. Theo [DEMO_SCRIPT.md](DEMO_SCRIPT.md) để trình bày; xem [ma trận nghiệm thu](docs/phase4_acceptance.md).
