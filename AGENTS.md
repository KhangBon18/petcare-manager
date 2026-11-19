# Quy ước phát triển PetCare Manager

## Kiến trúc hiện hành

Bản hiện hành là nền tảng web multi-store SaaS cho cửa hàng thú cưng, chạy cục bộ trong phát triển và dùng chung ứng dụng/schema MySQL cho nhiều tenant. Backend dùng Python 3.11+ và Flask; giao diện dùng Jinja HTML, CSS và JavaScript thuần; dữ liệu lưu trong MySQL 8.0.16+ (InnoDB, utf8mb4). Không dùng Tkinter hay SQLite cho ứng dụng hiện hành.

- Route nhận request, kiểm tra CSRF, gọi service và render/redirect.
- Service áp dụng quyền và quy tắc nghiệp vụ, đồng thời sở hữu commit/rollback.
- Repository chứa SQL tham số hóa MySQL; không tự commit.
- Template hiển thị dữ liệu; tiền và quyền luôn được kiểm tra phía server.
- Kết nối lấy cấu hình từ biến môi trường; không ghi bí mật vào Git.

## Quy tắc cửa hàng

- Danh mục chính gồm khách hàng, thú cưng bán lẻ, sản phẩm có tồn kho, hóa đơn và báo cáo.
- Không triển khai khám bệnh, tiêm phòng, lịch hẹn chăm sóc, dịch vụ hay lượt dịch vụ trong phiên bản web.
- Tiền dùng MySQL `DECIMAL(20,4)` và Python `Decimal`; validate theo precision của currency tender hiện hành và lưu mã tiền snapshot trên hóa đơn. Chưa có FX, thuế đa vùng hay đổi currency sau onboarding. Số lượng sản phẩm là số nguyên dương.
- Tồn kho không âm. Điều chỉnh tồn phải có lý do và ghi stock_movements.
- Hóa đơn lưu snapshot tên/mã/giá. Client không quyết định tổng.
- Chưa thanh toán không trừ tồn và chưa gắn người mua cho thú cưng.
- Thanh toán dùng một transaction InnoDB: khóa hóa đơn/hàng, kiểm tra lại tồn và cá thể, ghi stock movement, cập nhật thú cưng rồi đánh dấu paid. Lỗi ở bất kỳ bước nào phải rollback.
- Thanh toán lặp là bất biến, hóa đơn paid không sửa/hủy. Hủy unpaid giữ snapshot và không thay tồn.
- Không xóa cứng khách hàng/hàng hóa có lịch sử. Hàng đã bán không trở lại danh sách bán.
- Mật khẩu phải được băm; session có chữ ký lưu user id, tenant id và `session_version`, còn role/membership được tải lại từ MySQL ở mỗi request. Đổi mật khẩu hoặc khóa/mở lại membership phải thu hồi phiên cũ.
- Admin quản lý người dùng, giá, danh mục, thú cưng bán và điều chỉnh tồn. Staff quản lý khách hàng, lập/thanh toán hóa đơn và xem báo cáo.
- Mọi thao tác thay đổi dữ liệu dùng POST có CSRF. GET chỉ đọc.

## Lệnh phát triển

- Cài dependency: python -m pip install -r requirements.txt
- Khởi tạo schema: python -m petcare.database.initialize
- Nạp demo: python -m petcare.database.seed
- Chạy web: python run.py
- Kiểm thử: python -m unittest discover -s tests -v

Các test tích hợp cần MySQL test database riêng, không dùng DB làm việc. Không thay MySQL bằng SQLite/mock rồi báo đã nghiệm thu MySQL. Không xóa/reset database hiện có. Dùng DB mới, ví dụ petcare_shop_dev.

Tài liệu desktop cũ được lưu trong docs/archive/REPO_GUIDE_DESKTOP.md để tra cứu lịch sử; các quy tắc hiện hành trong tệp này có ưu tiên cao hơn tài liệu lịch sử.
