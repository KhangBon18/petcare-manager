# Kế hoạch triển khai — web cửa hàng thú cưng

Kế hoạch này điều chỉnh ứng dụng desktop phòng khám cũ thành web quản lý cửa hàng. Quyết định và yêu cầu chi tiết được lưu tại [WEB_MYSQL_MIGRATION.md](../WEB_MYSQL_MIGRATION.md); bản clinic được giữ trong docs/archive/.

## Mốc 0 — Checkpoint và đổi phạm vi

- [x] Xác nhận nhánh solo/khang-petcare, commit gốc 1c62a48 và giữ nguyên thay đổi có sẵn.
- [x] Lưu tài liệu, mã nguồn và test clinic cũ trong docs/archive/.
- [x] Chuyển hướng dẫn và quy ước hiện hành sang Flask, HTML/CSS/JS thuần, MySQL và cửa hàng bán lẻ.

## Mốc 1 — Nền web, MySQL và đăng nhập

- [x] Flask app factory, cấu hình môi trường, CSRF và session an toàn.
- [x] Schema MySQL, khởi tạo cộng thêm an toàn, seed idempotent.
- [x] Đăng nhập/đăng xuất; tải trạng thái tài khoản và quyền hiện hành từ DB ở mỗi request.
- [x] Giao diện responsive HTML/CSS và dashboard.
- [x] Khởi chạy MySQL 8.4.11 thật, khởi tạo/seed database riêng và đăng nhập bằng trình duyệt.

## Mốc 2 — Danh mục

- [x] CRUD/tìm khách hàng, thú cưng bán lẻ và sản phẩm.
- [x] Admin quản lý giá, trạng thái danh mục, thú cưng và tồn kho.
- [x] Lịch sử điều chỉnh kho có lý do; thú cưng đã bán được bảo vệ khỏi sửa lịch sử.

## Mốc 3 — Hóa đơn và báo cáo

- [x] Lập hóa đơn unpaid từ dữ liệu DB, snapshot tên/giá và tính tổng phía server.
- [x] Thanh toán trong transaction MySQL với khóa dòng; không cho tồn âm hoặc bán trùng thú cưng.
- [x] Hủy unpaid; paid bất biến; thanh toán lặp không thay đổi dữ liệu lần hai.
- [x] Báo cáo doanh thu và hàng bán.
- [x] Integration tests chạy trên MySQL thật trong database riêng petcare_shop_test, gồm thanh toán đồng thời đơn vị cuối.

## Mốc 4 — QC nội bộ và bàn giao

- [x] Unit, web và integration tests; compileall.
- [x] Mở trình duyệt đăng nhập thật, kiểm tra dashboard và điều hướng cửa hàng.
- [x] README và hướng dẫn người dùng cho MySQL, chạy ứng dụng, dữ liệu demo và kiểm thử.
- [x] Cập nhật báo cáo/slide tổng kết hiện hành; gắn nhãn tài liệu đóng góp cũ cần chỉnh lại.
- [x] Giữ nguyên chính sách nhánh: không push, không merge main, không tạo PR/tag phát hành.

## Giới hạn nghiệm thu

- Đã kiểm chứng luồng đăng nhập trên macOS và các luồng nghiệp vụ bằng test trên MySQL 8.4.11. Chưa kiểm setup sạch trên Windows và chưa triển khai server Internet.
- Không tự chuyển dữ liệu clinic cũ sang database cửa hàng. Docker Compose dùng container/volume riêng petcare-manager-mysql và petcare_manager_mysql_data.

## Mốc 5 — Trợ lý và tìm thú cưng bằng ảnh (hoàn tất)

- [x] Trợ lý hỏi dữ liệu tổng hợp cửa hàng, tồn kho và thú cưng; phản hồi cục bộ khi chưa cấu hình endpoint.
- [x] Endpoint chat-completions tùy chọn; context đã loại PII khách hàng; AI Vision bật riêng.
- [x] Hồ sơ có ảnh, màu lông/mắt và tags; ảnh chuẩn hóa, storage backend local/S3-compatible; descriptor màu/cấu trúc được xếp hạng với các thú cưng available.
- [x] Camera laptop chụp trực tiếp để tìm; camera điện thoại mở từ trình chọn ảnh; QR điện thoại qua LAN opt-in, máy chủ mặc định giữ localhost.
- [x] Hoàn thiện backup/user guide/acceptance; trước đợt tenant mới nhất đạt 47/47 unit, web và MySQL integration tests trên database test riêng.
- [x] Bổ sung catalog seed tổng hợp có 22 mặt hàng, 12 khách mẫu, 74 hồ sơ thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster), 68 ảnh demo và 7 giao dịch lịch sử; ảnh/hồ sơ chó mèo mới là dữ liệu hư cấu được tạo tổng hợp bằng AI.
- [ ] Chạy lại seed trên database `_dev` hiện dùng để nạp 64 hồ sơ chó/mèo và ảnh mới trước khi demo; lượt cập nhật 2026-10-20 chỉ chỉnh source, chưa thay đổi DB.
- [x] Thêm lệnh tạo admin đầu tiên có xác nhận tên database, prompt mật khẩu ẩn và từ chối khi DB đã có tài khoản.
- [ ] Cấu hình endpoint thực để trình diễn generative chat/vision trực tuyến nếu môn học yêu cầu mô hình AI thực sự.

## Mốc 6 — Multi-store SaaS foundation (đang hoàn tất)

- [x] Bảng tenants và tenant_users; quyền owner/admin/staff gắn theo từng cửa hàng.
- [x] Lời mời thành viên một lần, 7 ngày, gắn email đích, dùng encrypted outbox để gửi nếu SMTP cấu hình; có fallback thủ công cho local, chống lời mời trùng và có thể thu hồi/hủy email pending; account hiện có phải xác minh đúng email.
- [x] Operator tenant export theo snapshot, ZIP bên trong được mã hóa AES-GCM bằng passphrase, kèm manifest/checksum; xác minh trước khi giải mã; không xuất password hash/token hash.
- [x] Backfill single-store hiện có vào tenant `main` bằng migration cộng thêm, không reset dữ liệu.
- [x] Tenant-scope danh mục, khách, thú cưng, hóa đơn, báo cáo, audit, trợ lý và media; thêm composite foreign keys chống ghép dữ liệu chéo tenant.
- [x] Login chọn store slug, thành viên nhiều store có thể đổi store; role được đọc lại trong mỗi request.
- [x] Lệnh tương tác provision tenant/owner; test MySQL hai tenant, cùng mã hàng, cross-store lookup/invoice/media, role và chuyển store.
- [x] Tài khoản có email toàn nền tảng, xác minh sau khi nhập email, reset mật khẩu token một lần cho email verified; throttle lưu MySQL và reset thu hồi session cũ. SMTP production bắt buộc STARTTLS; payload nằm trong MySQL outbox mã hóa, worker claim lease/retry.
- [x] Chốt hướng multi-store SaaS dùng chung app/schema MySQL; chủ/admin cửa hàng có thể cập nhật tên và múi giờ tenant, còn slug và currency được bảo vệ khỏi thay đổi phá vỡ liên kết hoặc lịch sử tiền tệ.
- [x] Email/export worker ghi heartbeat MySQL theo instance; `/workersz` kiểm tra cả hai queue worker mà không làm web `/readyz` phụ thuộc vào queue; heartbeat cũ tự dọn sau 30 ngày.
- [ ] Hoàn thành review độc lập về isolation/migration; bổ sung billing/plan limits và tenant deletion/retention. Public signup đã có feature flag mặc định tắt. SMTP account/invitation/onboarding flows cần kiểm provider thật, queue alerting/bounce flow. Admin self-service export đã có.
- [x] Self-service tenant export dùng job MySQL + worker riêng, mã hóa passphrase chờ xử lý, xác minh lại quyền tenant admin, retry/lease, lưu object private, trang theo dõi/tải lại và dọn file theo retention.
- [x] Lưu giá bằng Decimal/DECIMAL, áp dụng currency precision, cho chọn currency lúc onboarding và snapshot currency trên hóa đơn; cột VND được migration additive.
- [x] Lưu thời gian UTC, cho chọn timezone IANA theo tenant, lọc ngày nghiệp vụ theo giờ cửa hàng kể cả DST, định dạng timestamp theo locale cửa hàng; chuyển dữ liệu legacy +07 một lần bằng migration marker.
- [ ] Bổ sung i18n giao diện, tax rules, FX/đổi currency có sổ quy đổi và managed deployment; hiện UI vẫn tiếng Việt và tenant không thể đổi currency sau tạo.
