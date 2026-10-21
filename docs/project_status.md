# Trạng thái PetCare Manager

Cập nhật: 2026-10-19. Nhánh làm việc: solo/khang-petcare. Commit gốc: 1c62a48. Chưa push, merge main, tạo PR hoặc tag.

## Phạm vi hiện hành

- Nền tảng web multi-store SaaS dùng chung database: Flask + Jinja HTML, CSS và JavaScript thuần; hiện mới là baseline phát triển, chưa public-launch-ready.
- MySQL/InnoDB; database phát triển riêng petcare_shop_dev.
- Quản lý tài khoản, khách hàng, thú cưng bán lẻ, sản phẩm/tồn kho, hóa đơn và báo cáo.
- Trợ lý hỏi đáp theo dữ liệu cửa hàng, có endpoint AI tạo sinh tùy chọn; context không chứa PII khách hàng.
- Ảnh hồ sơ thú cưng với thuộc tính ngoại hình; tìm ảnh đọc candidate theo lô, chỉ giữ top-12 trong RAM, xếp hạng màu trung tâm/toàn ảnh, cấu trúc và AI Vision opt-in. So sánh vẫn tuyến tính theo inventory; có lệnh dry-run/reindex descriptor cũ theo batch.
- Camera laptop chụp một khung hình để tìm; điện thoại có camera gốc và QR link qua LAN opt-in.
- Khám, tiêm, lịch hẹn và dịch vụ spa không thuộc phạm vi app mới; mã/tài liệu clinic cũ được lưu ở docs/archive/.

## Đã hoàn thiện

- App factory, blueprint, đăng nhập/đăng xuất, CSRF, session có user/tenant/version đã ký, thu hồi phiên sau đổi mật khẩu hoặc đổi trạng thái membership; membership/role được tải lại ở mỗi request.
- Schema hiện có 19 bảng gồm `schema_migrations`, tenants, users/account_tokens/email_outbox, tenant memberships/invitations/owner transfers/export jobs, dữ liệu nghiệp vụ, audit và throttle; business data tenant-scoped, composite foreign keys chống ghép chéo; migration cộng thêm backfill DB cũ vào `main`, không DROP.
- Cửa hàng mới có thể được provision qua `python -m petcare.database.create_store`; user nhiều membership chọn/đổi cửa hàng, role khác nhau theo từng store.
- Tên hiển thị/mật khẩu là thuộc tính toàn nền tảng; admin không sửa hồ sơ toàn cục của user nhiều membership, còn người dùng đổi tên ở cài đặt tài khoản sau re-auth.
- Admin tạo/thu hồi liên kết mời dùng một lần, 7 ngày; với SMTP cấu hình, lời mời gửi qua encrypted outbox; môi trường local chưa có SMTP dùng link thủ công. Người nhận gắn tài khoản đã xác minh đúng email hoặc tạo tài khoản mới. Email tài khoản có thể xác minh; khôi phục mật khẩu dùng token một lần. SMTP provider thật chưa được kiểm tra.
- Operator có CLI export; store-admin gửi yêu cầu nền vào MySQL queue, worker snapshot tenant và tạo bundle AES-GCM gồm CSV, ảnh và manifest checksum. Passphrase được mã hóa tạm bằng Fernet, worker lease/retry, recheck role, audit hoàn tất, phân quyền status/download theo requester + tenant và tự dọn artifact theo retention; password/token hashes không được xuất.
- CRUD khách hàng, sản phẩm (mô tả, ảnh, ngưỡng nhập lại riêng) và thú cưng; điều chỉnh tồn kho có lý do.
- Hóa đơn snapshot; thanh toán transaction, khóa hàng, trừ kho và ghi người mua; unpaid hủy được, paid bất biến.
- Dashboard, báo cáo doanh thu/hàng bán/tồn; layout responsive tiếng Việt.
- Timestamp lưu UTC; mỗi tenant chọn múi giờ IANA hợp lệ, ngày báo cáo theo lịch địa phương qua DST, timestamp hiển thị theo giờ cửa hàng. Migration +07 chỉ chạy một lần và readiness kiểm marker.
- Runtime dùng MySQL connection pool giới hạn theo process; session reset khi trả pool và UTC/tenant context được đặt lại trên mỗi checkout. Production xác thực TLS MySQL qua `DB_SSL_CA`, CA và hostname đều được kiểm tra.
- Chủ/admin có trang cài đặt tenant để đổi tên và múi giờ; slug và currency giữ nguyên. Owner được hiển thị riêng, không thể bị admin thường khóa/hạ quyền; bàn giao cho admin khác cần re-auth hai phía, chấp thuận 72 giờ, có thể thu hồi và ghi audit.
- `/metrics` tùy chọn, bearer-protected, cho Prometheus xem queue depth/age và worker up mà không xuất tenant/job PII; để trống `OPS_METRICS_TOKEN` thì endpoint 404.
- Hướng dẫn setup, sử dụng, tìm ảnh, trợ lý và báo cáo tổng kết được cập nhật cho phạm vi cửa hàng.
- Composer hóa đơn có tìm kiếm/phân trang server-side cho khách hàng, sản phẩm, thú cưng; trang admin có nhật ký transaction cho hóa đơn, tồn kho, và thay đổi hồ sơ khách hàng/sản phẩm/thú cưng/tài khoản.

## Bằng chứng chạy trên máy hiện tại

- Python 3.13.3; Flask 3.1.3; Flask-WTF 1.3.0; mysql-connector-python 9.7.0; MySQL Server 8.4.11.
- .venv/bin/python -m compileall -q run.py main.py petcare tests — đạt.
- Toàn bộ suite unit/web/MySQL trên database `petcare_codex_<random>_test` mới tạo, cấp quyền scoped rồi xóa sau kiểm thử — đạt 197/197 vào 2026-10-19. Bao gồm locale persistence, nhãn audit VI/EN, thông báo validation, response no-store cho phiên đăng nhập, tenant isolation, camera/AI, export, account, inventory, timezone, image processing, quota và worker. Lượt xác minh mới nhất chạy compileall, cú pháp JavaScript, `git diff --check`, Bandit 1.9.4 theo baseline (không phát hiện mới) và `pip-audit` (không phát hiện CVE đã biết); Trivy gần nhất có bằng chứng ngày 2026-10-18, không chạy lại vì binary không có trong môi trường hiện tại.
- `petcare_shop_dev` đã initialize additive; `/readyz` và `/workersz` đều trả HTTP 200 `ready` sau khi web, email worker và export worker khởi động lại.
- `docker compose config --quiet`, `docker compose build web email-worker export-worker`, `node --check` và `git diff --check` đạt; sau migrate dev, app local `/healthz`, `/readyz`, `/workersz`, `/login` đều 200. Email/export workers đang chạy với heartbeat mới.
- Sau khi bổ sung danh mục demo, petcare_shop_dev đã initialize và seed hai lần: 2 users, 13 customers (12 hồ sơ demo mới, giữ nguyên dữ liệu có sẵn), 22 products, 10 pets, 4 ảnh thú cưng demo và 7 hóa đơn demo đã thanh toán. Lịch sử tồn có 36 dòng. Không có ảnh sản phẩm seed sẵn; ảnh mặt hàng được tải lên từ form admin.
- `petcare_shop_dev` đã chạy additive initialize cho account tokens và encrypted email outbox/expiry; không chạy seed trong lần migrate này. Các hàng hiện có được giữ lại; `/readyz` trả 200.
- Flask client: login/CSS trả 200; trang cần đăng nhập redirect 302 khi chưa có session.
- Trình duyệt đăng nhập admin thành công; dashboard, form bán và trang chi tiết hóa đơn hoạt động. Luồng bán qua giao diện tạo và thanh toán hóa đơn 2.250.000 ₫ gồm hai sản phẩm và Miu; tồn kho, doanh thu và trạng thái thú cưng được cập nhật. Dữ liệu walkthrough được dọn khỏi DB test và tồn kho khôi phục.
- Trang `/store/settings` được mở trên browser IAB sau khi restart app; menu quản trị xuất hiện và form đọc được bằng accessibility tree. Browser chỉ đọc; kiểm tra POST, audit và validation chạy trên MySQL test DB riêng.
- Web integration xác nhận form tạo khách hàng/sản phẩm/thú cưng, trang chi tiết và route thanh toán có CSRF; DB test được khôi phục sau kiểm thử.
- Trang đăng nhập đã được xem ở khung 628 × 627; sửa lỗi minh họa đè lên chữ và kiểm tra lại sau khi khởi động lại Flask.
- Trang tìm ảnh được mở trực tiếp; trợ lý trên DB phát triển trả danh sách sản phẩm và tồn thấp. Migration cộng thêm các cột ảnh/ngoại hình, mô tả và ngưỡng nhập hàng; giữ dữ liệu hiện có.
- UI tìm ảnh sau nâng cấp hiển thị nút camera laptop, lựa chọn camera điện thoại và cảnh báo xin quyền; MySQL integration xác nhận QR chỉ sinh khi bật LAN. Không cấp quyền hoặc bật camera trong lúc nghiệm thu.
- Docker container riêng petcare-manager-mysql khỏe mạnh, MySQL 8.4.11; port chỉ bind vào 127.0.0.1:3306.

## Cập nhật source cho demo — 2026-10-20

- Seed hiện định nghĩa 74 hồ sơ thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster) và 68 ảnh. 64 ảnh chó/mèo mới được tạo tổng hợp bằng AI; hồ sơ/ảnh đều hư cấu để demo.
- Trợ lý local được mở rộng để tra cứu doanh thu ngày/tuần/tháng, sản phẩm và thú cưng theo các thuộc tính có trong hồ sơ. Giao diện tìm ảnh và icon ở luồng thú cưng được làm rõ hơn; giới hạn của xếp hạng local được ghi trực tiếp trên trang.
- Các con số vận hành/kiểm thử phía trên là bằng chứng lịch sử cho bộ seed 10 thú cưng/4 ảnh. Lượt này chưa chạy seed lên MySQL, chưa chạy test và chưa bật lại ứng dụng; cần nạp seed trên database `_dev` trước buổi demo.

## Chạy cục bộ

- URL hiện tại khi server đang chạy: http://127.0.0.1:5000.
- Tài khoản demo: admin / Admin@123, staff1 / Staff@123; chỉ dùng với database demo local.
- Bí mật được lưu trong .env đã gitignore; .env.example chỉ chứa placeholder.
- Database trống dùng dữ liệu thật có thể khởi tạo admin đầu tiên bằng `python -m petcare.database.create_admin`; xác nhận tên database và nhập mật khẩu ẩn qua terminal.

## Giới hạn còn lại

- Chưa kiểm setup sạch trên Windows.
- App chưa triển khai Internet/HTTPS, kiểm thử tải hoặc nghiệm thu hệ thống sao lưu ngoài máy. SaaS có invitation email qua outbox, public signup route mặc định tắt, email verify/recovery và self-service export mã hóa; còn thiếu billing, deletion/retention workflow, cấu hình bucket production, kiểm live SMTP và review độc lập về bảo mật cô lập.
- Giá, hóa đơn và báo cáo dùng Decimal/DECIMAL theo currency tenant; tenant mới chọn currency ISO và IANA timezone khi onboarding, hóa đơn snapshot mã tiền, timestamp lưu UTC rồi hiển thị theo giờ cửa hàng. Locale UI vẫn tiếng Việt; chưa có thuế đa vùng, FX/đổi currency, online payment, refund hay trả hàng.
- Camera laptop trực tiếp cần localhost/HTTPS; trên điện thoại truy cập LAN dùng trình chụp ảnh gốc thay cho video trực tiếp do giới hạn secure-context của trình duyệt. LAN access mặc định tắt.
- Tìm ảnh local dùng histogram màu vùng trung tâm/toàn ảnh và cấu trúc toàn ảnh; nền/framing vẫn có thể ảnh hưởng, đây chưa phải object detector/embedding đã huấn luyện. Ảnh truy vấn được gửi tới app server, không lưu; chỉ gửi AI endpoint nếu AI Vision bật. Tạo sinh chat và AI Vision cần endpoint tương thích cấu hình; AI Vision mặc định tắt.
- Báo cáo tổng kết chính được cập nhật; các trang báo cáo/slide ghi tên từng thành viên vẫn là ghi chép của phiên bản clinic và cần tác giả rà soát trước khi nộp.
