# Báo cáo tổng kết — PetCare Manager

**Phiên bản:** web quản lý cửa hàng thú cưng
**Phạm vi:** nền tảng quản trị multi-store SaaS, hiện chạy/kiểm thử local
**Ngày cập nhật:** 02-11-2026

## 1. Bài toán và phạm vi

PetCare Manager hỗ trợ cửa hàng quản lý khách hàng, từng cá thể thú cưng bán lẻ, sản phẩm có tồn kho, hóa đơn và doanh thu. Dự án ban đầu hướng tới phòng khám desktop. Theo yêu cầu điều chỉnh, phiên bản hiện hành chuyển giao diện sang HTML/CSS, database sang MySQL và loại bỏ nghiệp vụ khám, tiêm, lịch hẹn chăm sóc cùng danh mục dịch vụ. Source và tài liệu clinic trước đó được giữ trong docs/archive/.

Phiên bản này có nền tenant dùng chung MySQL cho nhiều cửa hàng, không phải trang thương mại điện tử công khai. Chưa có billing SaaS, thanh toán/hoàn tiền tự động qua cổng thanh toán hoặc triển khai Internet.

## 2. Công nghệ và kiến trúc

- Backend: Python 3.13.3, Flask 3.1.3, Jinja2.
- Giao diện: HTML, CSS và JavaScript thuần, responsive, tiếng Việt.
- Database: MySQL Server 8.4.11, InnoDB, utf8mb4; driver mysql-connector-python 9.7.0.
- Phân lớp: route/blueprint → service → repository → MySQL; cấu hình bí mật từ .env.
- Timestamp được chuẩn hóa UTC trong MySQL; mỗi cửa hàng có IANA timezone riêng để lọc ngày và hiển thị thời gian.
- Source schema có 25 bảng sau migration P1.2/P1.3; database phát triển hiện giữ 20 bảng và chưa chạy hai migration mới. Tenant-scoped queries cùng composite foreign keys chặn tham chiếu chéo store; `initialize` chỉ bổ sung schema, không xóa dữ liệu.

## 3. Chức năng

- Đăng nhập theo store slug, CSRF, mật khẩu băm, membership/role theo cửa hàng được tải lại từ MySQL ở mỗi request; user nhiều membership có thể chuyển store.
- Quản lý khách hàng, sản phẩm, từng thú cưng và điều chỉnh tồn kho có lý do.
- Admin tạo và thu hồi link mời dùng một lần, hạn 7 ngày; người nhận có thể liên kết tài khoản đã có hoặc tạo tài khoản mới. Link gửi thủ công; chưa xác minh email.
- Operator export một tenant thành bundle `.pcarexport` mã hóa AES-256-GCM, chứa ZIP CSV/metadata/ảnh với SHA-256 manifest; có verify và decrypt sau xác thực; password/token hashes bị loại trừ.
- Backup local/Compose gồm MySQL và ảnh được mã hóa thành `.pcarebackup`; có verify/decrypt sau xác thực và chuyển đổi backup plaintext cũ.
- POS hai vùng: catalog ảnh/giá/tồn có tìm kiếm và phân trang, giỏ hàng và tổng tiền; modal thêm nhanh khách hàng giữ các mặt hàng đã chọn. Nhật ký admin ghi các giao dịch và thao tác tồn kho quan trọng cùng transaction.
- Lập hóa đơn unpaid từ dữ liệu database; server tính tiền và lưu snapshot tên/giá.
- Admin quản lý nhà cung cấp, nhận hàng từng phần và ghi nhận trả hàng/hoàn tiền theo dòng; hoàn tiền tạo sổ riêng, bảo toàn hóa đơn paid và đồng bộ tồn/trạng thái pet/audit bằng transaction.
- Báo cáo, dashboard và trợ lý tính doanh thu thuần theo thời điểm thu/hoàn. Ghi nhận hoàn không thực hiện chuyển tiền; cần hoàn tất thanh toán ngoài hệ thống.
- Thanh toán nguyên tử: khóa hóa đơn và hàng tồn, xác minh khả năng bán, trừ kho, ghi stock movement, gắn người mua và cập nhật trạng thái hóa đơn.
- Dashboard, báo cáo doanh thu thực thu, hàng bán và tồn; giá/hóa đơn dùng Decimal/DECIMAL theo currency tenant, mã tiền được snapshot ở hóa đơn.
- Trợ lý local truy vấn context MySQL cho tổng quan, doanh thu theo ngày/tuần/tháng, tồn kho, sản phẩm và thú cưng; hỗ trợ lọc hồ sơ theo giống, màu lông/mắt, giới tính và mức giá. Endpoint AI tạo sinh là tùy chọn; PII khách hàng không nằm trong context gửi.
- Hồ sơ ảnh/thuộc tính ngoại hình và xếp hạng ảnh tương tự có bộ lọc loài/trạng thái, điểm thành phần/lý do; upload gợi ý thuộc tính có duyệt, giữ dữ liệu nhập tay và fallback local khi Vision lỗi.
- Trợ lý biên dịch điều kiện thành truy vấn SQL trên toàn danh mục đang bán, đếm chính xác và trả tối đa 12 card ảnh/giá/trạng thái/đường dẫn hồ sơ; card giữ nguyên khi LLM lỗi.
- Gợi ý nhập kho có giải thích dùng lượng bán paid 14/30 ngày, ước tính ngày tồn, kế hoạch 14 ngày; fallback ngưỡng cho hàng chưa bán, chỉ gợi ý và không tự đổi tồn.
- Báo cáo/Dashboard có biểu đồ theo ngày, kỳ nhanh, tăng trưởng kỳ trước và bản tin Python. Excel bốn sheet từ snapshot có chữ ký/CSRF/TTL 15 phút; in/PDF qua trình duyệt, tự mở chi tiết và khôi phục sau in.

## 4. Quy tắc toàn vẹn

Tạo hóa đơn chưa trừ tồn và chưa đánh dấu thú cưng đã bán. Thanh toán thực hiện trong một MySQL transaction; nếu còn thiếu hàng hoặc cá thể đã được bán, toàn bộ thao tác rollback. Thanh toán lặp không trừ kho lần hai. Hóa đơn unpaid có thể hủy; lịch sử hóa đơn paid không sửa hoặc hủy. Các transaction cạnh tranh được kiểm tra bằng MySQL thật.

## 5. Kiểm thử và nghiệm thu

- Nghiệm thu P1.3 ngày 2026-11-02: **321/321 Python tests** (189 unit, 73 web, 59 MySQL integration) trên MySQL 8.4 test riêng; **26/26 JavaScript tests**. Migration lặp lại được; luồng trả/hoàn, hoàn một phần, idempotency, giới hạn số lượng và doanh thu thuần được kiểm tra. Compileall, cú pháp JavaScript và `git diff --check` đạt.
- Playwright kiểm tra hóa đơn ở desktop 1440×1000 và mobile 390×844: không tràn ngang; nút trợ lý không che trường hoàn, panel vừa màn hình, Esc đóng và trả focus; các trường cuối mobile cuộn lên phía trên thanh điều hướng. Console sạch. Không thực hiện giao dịch hoàn trong trình duyệt; các dòng MySQL integration đã được dọn.
- Database phát triển `petcare_shop_dev` không chạy migration, không bị ghi dữ liệu; vẫn có 20 bảng. Migration chỉ được xác minh trên container MySQL test cô lập.
- Compile toàn bộ source và tests bằng compileall: đạt.
- Mốc nghiệm thu Phase 4 ngày 2026-10-25 đạt 283/283 Python tests (171 unit, 55 web, 57 MySQL integration) và 19/19 JavaScript tests. Bộ kiểm bao gồm currency/minor-unit, UTC migration/export, tenant timezone/DST, pool session isolation, email outbox/onboarding, tenant isolation, AI boundaries, lưu locale theo tài khoản, nhãn audit đa ngôn ngữ, response dữ liệu đã đăng nhập không bị cache, concurrency giao dịch/kho/media và worker/export. SMTP provider thật và bucket S3 thật chưa được nghiệm thu.
- Diễn tập local backup/restore dùng MySQL Compose và database test tách biệt khớp 13 khách, 22 sản phẩm, 10 thú cưng, 7 hóa đơn; 9 ảnh được trích xuất. Chưa có bằng chứng restore từ dịch vụ backup managed production.
- Seed trong source hiện định nghĩa 22 sản phẩm, 12 khách mẫu, 74 thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster), 68 ảnh hồ sơ và 7 hóa đơn lịch sử. 64 ảnh chó/mèo được tạo tổng hợp bằng AI; toàn bộ hồ sơ/ảnh demo là hư cấu.
- Số lượng 10 thú cưng/4 ảnh ở phần kiểm thử backup/restore là snapshot lịch sử ngày 2026-10-18. Database dev đã seed ngày 2026-10-25: 14 khách hàng, 22 sản phẩm, 74 thú cưng, 68 ảnh và 7 hóa đơn demo. Seed cộng thêm, giữ dữ liệu cũ; chạy lại làm mới ngày của đúng giao dịch mẫu và bổ sung ảnh thiếu, không trừ kho lặp.
- Integration kiểm tra thanh toán, snapshot, tồn kho, bán thú cưng, idempotency và hai request cạnh tranh mua đơn vị tồn cuối.
- Khởi tạo database demo và chạy seed hai lần; số lượng bản ghi không tăng ở lần chạy sau.
- Đăng nhập tài khoản Admin qua Chrome, mở dashboard và xác nhận các mục cửa hàng hiển thị.
- Setup Windows, triển khai Internet/HTTPS và kiểm tải chưa thuộc bằng chứng nghiệm thu. Public onboarding route có feature flag mặc định tắt; SaaS billing, tenant deletion/retention, review isolation độc lập, managed object storage, đa ngôn ngữ đầy đủ, tax/FX và đổi currency chưa hoàn tất. Giá và hóa đơn hỗ trợ currency per tenant bằng Decimal, nhưng đây chưa phải triển khai global. Account email verification/recovery và outbox mã hóa có trong code; SMTP chưa live-test, queue alerts/bounce flow chưa có.
- Chế độ tìm cục bộ so sánh histogram màu vùng trung tâm/toàn ảnh và lưới độ sáng, chưa phải object detection hay embedding đã huấn luyện. Tạo sinh chat và AI Vision cần endpoint cấu hình; nhánh AI trực tuyến chưa nghiệm thu do chưa cấu hình endpoint. Ảnh truy vấn được xử lý ở app server, không lưu thành hồ sơ và chỉ gửi endpoint AI khi AI Vision bật.
- POS đã kiểm tra bằng Chrome tại 1280×800, 768×1024 và 390×844: không tràn ngang, ảnh tải được, giỏ hàng giữ qua thêm nhanh khách hàng/đổi bộ lọc, Esc trả focus. Dashboard bổ sung doanh thu 7 ngày qua. Module i18n đang làm dở được giữ nguyên.

- Phase 3 nghiệm thu Excel/chi tiết khớp 100% snapshot màn hình ngay cả khi dữ liệu thay đổi sau render; PDF mẫu 2 trang đã được render kiểm tra. Ảnh/card/thuộc tính và mobile kiểm tra trên trình duyệt; provider LLM/Vision chỉ kiểm phản hồi/lỗi mô phỏng khi chưa cấu hình endpoint thật. Giới hạn báo cáo MVP 366 ngày/5.000 dòng có thông báo phục hồi, không âm thầm cắt dữ liệu.

## 6. Chạy ứng dụng

Thực hiện theo README.md: tạo virtualenv, cài dependencies, cấu hình .env, tạo database/user MySQL, chạy initialize và seed, rồi chạy python run.py. Truy cập http://127.0.0.1:5055. Demo credentials chỉ dành cho database demo local; không dùng cho dữ liệu thật.

## 7. Hướng phát triển

P1.3 đã được kiểm thử trên database MySQL tạm và trình duyệt desktop/mobile. Trước triển khai Internet cần diễn tập migration trên staging có backup/rollback, bật HTTPS và giám sát, xác minh SMTP/AI cùng dịch vụ lưu trữ ngoài, và hoàn thiện chính sách quyền riêng tư/retention. Billing SaaS, thuế/FX đa vùng và chuyển tiền tự động qua cổng thanh toán vẫn ngoài phạm vi.
