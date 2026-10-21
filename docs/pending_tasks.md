# Theo dõi nhiệm vụ

## Baseline đã có

- Web Flask + HTML/CSS/JavaScript thuần, MySQL/InnoDB; phạm vi cửa hàng gồm khách hàng, thú cưng bán lẻ, sản phẩm/tồn kho, hóa đơn và báo cáo.
- Nền shared-database multi-tenant, membership/role theo store, composite FK, migration cộng thêm và kiểm cô lập MySQL.
- Kiến trúc SaaS được chốt theo hướng nhiều cửa hàng dùng chung nền tảng và MySQL với tenant isolation; mỗi cửa hàng quản lý được tên và múi giờ riêng. Slug giữ ổn định, currency không đổi sau onboarding cho tới khi có quy trình FX/ledger.
- Danh tính `owner` được hiển thị riêng và không thể bị admin thường hạ quyền/khóa qua màn thành viên; bàn giao owner có re-auth từ hai phía, expiry 72 giờ, revoke, throttle, audit và email thông báo tùy cấu hình.
- Email invitation dùng một lần/7 ngày, gắn đúng email nhận, không lưu token thô; SMTP delivery đi qua encrypted transactional outbox, local có link fallback; link tuyệt đối lấy từ `PUBLIC_BASE_URL`.
- Operator export CLI và store-admin export UI gồm CSV, metadata, ảnh và SHA-256; bundle mã hóa bằng passphrase, verify không trích xuất, decrypt chỉ tạo ZIP riêng tư sau xác thực. UI admin dùng job MySQL/worker, mã hóa passphrase khi chờ, step-up password, tenant/requester scoped status/download, audit, throttle, retry/lease và xóa artifact sau retention. Tenant deletion/retention lifecycle vẫn cần thiết cho SaaS.
- Trợ lý local, endpoint AI tùy chọn; tìm ảnh hồ sơ, camera laptop và trình chụp điện thoại; AI Vision opt-in. Tìm ảnh dùng center-weighted color features; descriptor cũ có dry-run/batch reindex. Media có backend local và S3-compatible; tenant export đọc media từ backend đã cấu hình.
- Email toàn nền tảng có luồng xác minh/khôi phục, token hash một lần, throttle DB, response chống dò địa chỉ và thu hồi phiên cũ khi reset. Outbox MySQL mã hóa payload, worker claim bằng lease và retry lỗi tạm thời; production đòi SMTP STARTTLS cùng key mã hóa ổn định.
- Danh tính tài khoản toàn nền tảng được tách khỏi membership theo tenant; store admin không sửa tên/mật khẩu khi user có nhiều membership, còn chủ tài khoản tự đổi tên sau xác thực lại.
- Public signup route đã có nhưng mặc định tắt; email xác minh mới kích hoạt quyền owner, worker dọn đăng ký chưa xác minh sau 7 ngày.
- Lần kiểm đầy đủ mới nhất đạt 197/197 unit/web/MySQL integration tests trên MySQL test database tạm, độc lập và được xóa sau lượt chạy (2026-10-19). Bộ kiểm bao gồm locale browser/session và lưu theo tài khoản, open-redirect defense, dashboard English/currency format, trợ lý local/AI tiếng Anh và giới hạn context, tenant isolation, media, quotas, timezone/DST, workers, export, inventory concurrency, audit label, dynamic validation, authenticated no-store headers và image backpressure; chi tiết trong [test results](test_results.md). Dependency audit gần nhất không tìm thấy CVE đã biết; S3 provider thật vẫn cần nghiệm thu.
- CI đã cấu hình SHA-pinned GitHub Actions, Bandit baseline, Trivy source-tree secret scan, và Trivy HIGH/CRITICAL + secret scan trên image; các local scan đạt ngày 2026-10-18. Cần xác nhận hosted workflow xanh và yêu cầu independent review security trước release; baseline 38 finding cùng bốn suppression SBOM có hạn vẫn phải được review định kỳ.

## Trước public pilot / global launch

- Subscription/billing và plan limits trước khi mở public signup; route signup đã có feature flag mặc định off. Invitation/account email qua outbox nhưng SMTP chưa được thử với provider thật; cần cấu hình protected queue metrics vào monitoring, alert delivery và bounce/complaint flow. `/workersz` cùng `/metrics` cung cấp trạng thái tổng hợp nhưng chưa gửi cảnh báo. Cần terms/privacy và CAPTCHA/WAF/edge abuse controls trước khi mở đăng ký.
- Tenant deletion/retention workflow có legal hold và quy trình khôi phục; export tải từ UI đã có cho admin, nhưng quyền dữ liệu và lifecycle chưa được rà soát độc lập.
- Nghiệm thu export-worker với MySQL production-like và S3 provider đã chọn; kiểm thử retry sau worker crash, key rotation, retention deletion và quyền tải qua nhiều app instance.
- Locale VI/EN có chọn theo `Accept-Language` và picker trong session; các luồng bán hàng, cài đặt tài khoản/cửa hàng, onboarding, thành viên, export, bàn giao ownership và khung audit đã có English. Cần rà mọi email/thông báo/validation server và nội dung lịch sử audit; lưu preference theo tài khoản và nghiệm thu date/number/currency formats. Tax rules và luồng đổi currency/FX vẫn mở. Timezone IANA theo tenant, UTC storage, report windows qua DST và hiển thị giờ địa phương đã được triển khai; currency không thể đổi sau khi tạo tenant.
- Live AI provider: chọn nhà cung cấp, cấu hình secrets/data region, đánh giá chất lượng/latency/cost và retention với dữ liệu thật.
- Provision private object bucket, least-privilege IAM, versioning/lifecycle, encrypted off-site backup and managed-production restore rehearsal; local Compose restore rehearsal passed. Monitoring/alerts, WAF/rate limits and incident response also remain.
- Dedicated production runtime/migration database credentials are supported in code; production account provisioning and a migration run with the deployment provider's secret manager still need to be completed and verified.
- Independent security/isolation review, review Bandit/Trivy exceptions, hosted GitHub Actions green run, migration rehearsal, performance/load tests under concurrency and at larger tenant sizes (preliminary synthetic catalog and end-to-end image-search baselines at 20,000 rows are recorded in `docs/launch_readiness.md`) và cài đặt sạch trên Windows.
- Người nộp rà soát đóng góp cá nhân trong docs/report/ và docs/slides/; xác nhận release/PR sau khi review.

## Ranh giới hiện tại

Local app ở `http://127.0.0.1:5000` là development server, không phải production deployment. Không nhận dữ liệu khách hàng thật hoặc tuyên bố global-launch-ready cho tới khi các gate trong [launch readiness](launch_readiness.md) được xử lý.
