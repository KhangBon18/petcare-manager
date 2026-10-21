# Báo cáo tổng kết — PetCare Manager

**Phiên bản:** web quản lý cửa hàng thú cưng
**Phạm vi:** nền tảng quản trị multi-store SaaS, hiện chạy/kiểm thử local
**Ngày cập nhật:** 20-10-2026

## 1. Bài toán và phạm vi

PetCare Manager hỗ trợ cửa hàng quản lý khách hàng, từng cá thể thú cưng bán lẻ, sản phẩm có tồn kho, hóa đơn và doanh thu. Dự án ban đầu hướng tới phòng khám desktop. Theo yêu cầu điều chỉnh, phiên bản hiện hành chuyển giao diện sang HTML/CSS, database sang MySQL và loại bỏ nghiệp vụ khám, tiêm, lịch hẹn chăm sóc cùng danh mục dịch vụ. Source và tài liệu clinic trước đó được giữ trong docs/archive/.

Phiên bản này có nền tenant dùng chung MySQL cho nhiều cửa hàng, không phải trang thương mại điện tử công khai. Chưa có đăng ký công khai, billing, refund, đặt hàng hoặc triển khai Internet.

## 2. Công nghệ và kiến trúc

- Backend: Python 3.13.3, Flask 3.1.3, Jinja2.
- Giao diện: HTML, CSS và JavaScript thuần, responsive, tiếng Việt.
- Database: MySQL Server 8.4.11, InnoDB, utf8mb4; driver mysql-connector-python 9.7.0.
- Phân lớp: route/blueprint → service → repository → MySQL; cấu hình bí mật từ .env.
- Timestamp được chuẩn hóa UTC trong MySQL; mỗi cửa hàng có IANA timezone riêng để lọc ngày và hiển thị thời gian.
- Schema hiện có 17 bảng gồm `schema_migrations`, tenants, users/account_tokens/email_outbox, membership/invitation/export jobs, các bảng nghiệp vụ, audit và throttle; tenant-scoped queries cùng composite foreign keys chặn tham chiếu chéo store.

## 3. Chức năng

- Đăng nhập theo store slug, CSRF, mật khẩu băm, membership/role theo cửa hàng được tải lại từ MySQL ở mỗi request; user nhiều membership có thể chuyển store.
- Quản lý khách hàng, sản phẩm, từng thú cưng và điều chỉnh tồn kho có lý do.
- Admin tạo và thu hồi link mời dùng một lần, hạn 7 ngày; người nhận có thể liên kết tài khoản đã có hoặc tạo tài khoản mới. Link gửi thủ công; chưa xác minh email.
- Operator export một tenant thành bundle `.pcarexport` mã hóa AES-256-GCM, chứa ZIP CSV/metadata/ảnh với SHA-256 manifest; có verify và decrypt sau xác thực; password/token hashes bị loại trừ.
- Backup local/Compose gồm MySQL và ảnh được mã hóa thành `.pcarebackup`; có verify/decrypt sau xác thực và chuyển đổi backup plaintext cũ.
- Form hóa đơn tra cứu khách hàng/mặt hàng từ MySQL theo trang; nhật ký admin ghi các giao dịch và thao tác tồn kho quan trọng cùng transaction.
- Lập hóa đơn unpaid từ dữ liệu database; server tính tiền và lưu snapshot tên/giá.
- Thanh toán nguyên tử: khóa hóa đơn và hàng tồn, xác minh khả năng bán, trừ kho, ghi stock movement, gắn người mua và cập nhật trạng thái hóa đơn.
- Dashboard, báo cáo doanh thu thực thu, hàng bán và tồn; giá/hóa đơn dùng Decimal/DECIMAL theo currency tenant, mã tiền được snapshot ở hóa đơn.
- Trợ lý local truy vấn context MySQL cho tổng quan, doanh thu theo ngày/tuần/tháng, tồn kho, sản phẩm và thú cưng; hỗ trợ lọc hồ sơ theo giống, màu lông/mắt, giới tính và mức giá. Endpoint AI tạo sinh là tùy chọn; PII khách hàng không nằm trong context gửi.
- Hồ sơ ảnh/thuộc tính ngoại hình và xếp hạng ảnh tương tự; AI Vision tùy chọn.

## 4. Quy tắc toàn vẹn

Tạo hóa đơn chưa trừ tồn và chưa đánh dấu thú cưng đã bán. Thanh toán thực hiện trong một MySQL transaction; nếu còn thiếu hàng hoặc cá thể đã được bán, toàn bộ thao tác rollback. Thanh toán lặp không trừ kho lần hai. Hóa đơn unpaid có thể hủy; lịch sử hóa đơn paid không sửa hoặc hủy. Các transaction cạnh tranh được kiểm tra bằng MySQL thật.

## 5. Kiểm thử và nghiệm thu

- Compile toàn bộ source và tests bằng compileall: đạt.
- Lần kiểm đầy đủ mới nhất (2026-10-19) đạt 197/197 unit, web và MySQL integration tests trên database MySQL tạm, biệt lập và được xóa sau kiểm thử. Bộ kiểm bao gồm currency/minor-unit, UTC migration/export, tenant timezone/DST, pool session isolation, email outbox/onboarding, tenant isolation, AI boundaries, lưu locale theo tài khoản, nhãn audit đa ngôn ngữ, response dữ liệu đã đăng nhập không bị cache, concurrency giao dịch/kho/media và worker/export. SMTP provider thật và bucket S3 thật chưa được nghiệm thu.
- Diễn tập local backup/restore dùng MySQL Compose và database test tách biệt khớp 13 khách, 22 sản phẩm, 10 thú cưng, 7 hóa đơn; 9 ảnh được trích xuất. Chưa có bằng chứng restore từ dịch vụ backup managed production.
- Seed trong source hiện định nghĩa 22 sản phẩm, 12 khách mẫu, 74 thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster), 68 ảnh hồ sơ và 7 hóa đơn lịch sử. 64 ảnh chó/mèo được tạo tổng hợp bằng AI; toàn bộ hồ sơ/ảnh demo là hư cấu.
- Số lượng 10 thú cưng/4 ảnh ở phần kiểm thử backup/restore là snapshot lịch sử ngày 2026-10-18. Database dev chưa được seed lại trong lượt cập nhật 2026-10-20; cần chạy seed trên database `_dev` trước demo để nạp danh mục mới. Seed cộng thêm và giữ các hồ sơ cũ.
- Integration kiểm tra thanh toán, snapshot, tồn kho, bán thú cưng, idempotency và hai request cạnh tranh mua đơn vị tồn cuối.
- Khởi tạo database demo và chạy seed hai lần; số lượng bản ghi không tăng ở lần chạy sau.
- Đăng nhập tài khoản Admin qua Chrome, mở dashboard và xác nhận các mục cửa hàng hiển thị.
- Setup Windows, triển khai Internet/HTTPS và kiểm tải chưa thuộc bằng chứng nghiệm thu. Public onboarding route có feature flag mặc định tắt; SaaS billing, tenant deletion/retention, review isolation độc lập, managed object storage, đa ngôn ngữ đầy đủ, tax/FX và đổi currency chưa hoàn tất. Giá và hóa đơn hỗ trợ currency per tenant bằng Decimal, nhưng đây chưa phải triển khai global. Account email verification/recovery và outbox mã hóa có trong code; SMTP chưa live-test, queue alerts/bounce flow chưa có.
- Chế độ tìm cục bộ so sánh histogram màu vùng trung tâm/toàn ảnh và lưới độ sáng, chưa phải object detection hay embedding đã huấn luyện. Tạo sinh chat và AI Vision cần endpoint cấu hình; nhánh AI trực tuyến chưa nghiệm thu do chưa cấu hình endpoint. Ảnh truy vấn được xử lý ở app server, không lưu thành hồ sơ và chỉ gửi endpoint AI khi AI Vision bật.
- Thay đổi trợ lý, biểu tượng UI và seed demo ngày 2026-10-20 chưa chạy compile/test hoặc nghiệm thu trên trình duyệt. Các kết quả 197/197 và backup/restore nêu trên là bằng chứng trước lượt cập nhật này; cần chạy seed `_dev` và ca nghiệm thu mới trước buổi demo.

## 6. Chạy ứng dụng

Thực hiện theo README.md: tạo virtualenv, cài dependencies, cấu hình .env, tạo database/user MySQL, chạy initialize và seed, rồi chạy python run.py. Truy cập http://127.0.0.1:5000. Demo credentials chỉ dành cho database demo local; không dùng cho dữ liệu thật.

## 7. Hướng phát triển

Sau khi người dùng nghiệm thu bản nội bộ, có thể xem xét viết lại các đóng góp cá nhân, chụp ảnh minh chứng trên máy nộp, setup Windows, xuất PDF/in hóa đơn, biểu đồ, hoàn tiền/trả hàng và triển khai máy chủ có HTTPS. Các hạng mục đó chưa nằm trong phạm vi hiện tại.
