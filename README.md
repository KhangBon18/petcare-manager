# PetCare Manager — quản lý cửa hàng thú cưng

Ứng dụng web quản trị nhiều cửa hàng trên cùng nền tảng, với backend Python + Flask, giao diện HTML/CSS/JavaScript thuần và MySQL. Mỗi cửa hàng có membership, quyền và dữ liệu riêng. Phạm vi nghiệp vụ gồm khách hàng, sản phẩm có tồn kho, từng cá thể thú cưng để bán, hóa đơn và báo cáo. Bản hiện tại là nền tảng SaaS multi-tenant đang phát triển; chưa đủ điều kiện để gọi là global launch-ready.

Ứng dụng chọn tiếng Việt hoặc English theo `Accept-Language`; người dùng có thể đổi ngôn ngữ từ màn hình đăng nhập hoặc thanh điều hướng. Bản English hiện bao phủ đăng nhập, điều hướng, dashboard, trợ lý, khách hàng, sản phẩm, hồ sơ thú cưng, hóa đơn, báo cáo, tìm bằng ảnh/camera, cài đặt tài khoản/cửa hàng, onboarding, quản lý thành viên, xuất dữ liệu, bàn giao chủ cửa hàng và các màn hình lỗi. Email hệ thống, một số thông báo/validation server, nội dung cũ trong nhật ký và định dạng locale vẫn cần nghiệm thu; lựa chọn ngôn ngữ hiện lưu trong session trình duyệt.

Khám bệnh, tiêm phòng, lịch hẹn chăm sóc và dịch vụ spa thuộc phiên bản desktop cũ; bản đặc tả cũ được lưu trong docs/archive/. Không chuyển dữ liệu clinic sang dữ liệu hàng hóa.

## Yêu cầu

- Python 3.11 trở lên (Pillow 13 đã bỏ hỗ trợ Python 3.10).
- MySQL 8.0.16 trở lên, InnoDB và utf8mb4.
- Trình duyệt hiện đại.
- Khi cần cài MySQL mới: dùng [hướng dẫn cài MySQL chính thức cho macOS](https://dev.mysql.com/doc/refman/8.4/en/macos-installation.html) hoặc [hướng dẫn MySQL chính thức cho Windows](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html). Windows khuyến nghị MSI và MySQL Configurator; macOS có gói cài đặt DMG.
- Dùng database riêng petcare_shop_dev. Không trỏ ứng dụng vào database clinic hoặc database sản xuất.

## Cài đặt trên macOS / Linux

Tại thư mục gốc repo:

1. Tạo và kích hoạt môi trường ảo:

   python3 -m venv .venv
   source .venv/bin/activate

2. Cài thư viện:

   python -m pip install -r requirements.txt

3. Tạo file cấu hình local:

   cp .env.example .env

   Sửa DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD và đặt SECRET_KEY ngẫu nhiên. `DB_POOL_SIZE` điều chỉnh số kết nối tối đa mỗi process (mặc định 5); tính tổng theo số web worker và worker nền để không vượt connection budget MySQL. Production cần thêm `DB_SSL_CA` trỏ tới CA bundle MySQL được mount read-only để xác thực chứng chỉ và hostname. Không commit .env.

   Tài khoản có thể xác minh email và khôi phục mật khẩu. Email được ghi vào outbox MySQL với payload mã hóa, sau đó worker gửi và retry lỗi tạm thời. Để thử luồng đầy đủ, cấu hình `MAIL_HOST`, `MAIL_PORT`, `MAIL_FROM`, `MAIL_OUTBOX_KEY` và thông tin SMTP trong `.env`; tạo key bằng lệnh trong `.env.example` rồi giữ ổn định trong secret store. Production bắt buộc TLS STARTTLS. Nếu không cấu hình SMTP, app không thể gửi link verify/reset.

4. Tạo database và user riêng trong MySQL bằng tài khoản quản trị MySQL. Ví dụ SQL (đổi mật khẩu trước khi chạy):

   CREATE DATABASE petcare_shop_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'petcare_app'@'127.0.0.1' IDENTIFIED BY 'change-this-local-password';
   GRANT ALL PRIVILEGES ON petcare_shop_dev.* TO 'petcare_app'@'127.0.0.1';
   FLUSH PRIVILEGES;

   Nếu ứng dụng kết nối qua 127.0.0.1 thay vì socket, MySQL có thể phân biệt localhost và 127.0.0.1. Điều chỉnh host của DB user theo cấu hình server local.

5. Khởi tạo schema cộng thêm an toàn và dữ liệu demo cho môi trường học tập/dev. Database single-store cũ sẽ được backfill vào store `main`; migration không xóa dữ liệu:

   python -m petcare.database.initialize
   python -m petcare.database.seed

6. Chạy ứng dụng:

   python run.py

   Mở terminal thứ hai tại thư mục dự án để chạy export worker:

   python -m petcare.services.tenant_export_worker_cli

   Nếu cấu hình SMTP, mở terminal thứ ba cho email worker:

   python -m petcare.services.mail_worker

7. Mở http://127.0.0.1:5000.

   Health checks: `/healthz` xác nhận process web còn hoạt động, `/readyz` kiểm tra web + MySQL/schema; `/workersz` chỉ trả `ready` khi cả email worker và export worker ghi heartbeat thành công trong 90 giây gần nhất. Bản ghi tiến trình quá 30 ngày được email worker dọn theo lịch. Nếu chỉ chạy web mà không chạy đủ hai worker, các trang web vẫn phục vụ nhưng `/workersz` báo `unavailable`.

## Cài đặt trên Windows PowerShell

1. Tạo môi trường ảo và cài thư viện:

   py -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt

2. Sao chép .env.example thành .env. Cập nhật thông tin kết nối MySQL và SECRET_KEY bằng trình soạn thảo.

3. Tạo database petcare_shop_dev và MySQL user local riêng với charset utf8mb4; cấp quyền trên đúng database đó. Không dùng tài khoản root trong cấu hình ứng dụng.

4. Khởi tạo schema, dữ liệu demo và chạy:

   python -m petcare.database.initialize
   python -m petcare.database.seed
   python run.py

   Để bật xử lý export nền, chạy `python -m petcare.services.tenant_export_worker_cli` trong terminal khác; nếu cấu hình SMTP thì chạy `python -m petcare.services.mail_worker` thêm một terminal nữa.

5. Mở http://127.0.0.1:5000.

## MySQL bằng Docker Desktop (tùy chọn)

Docker Desktop đã có trên máy phát triển hiện tại. Tạo .env từ .env.example, đặt hai mật khẩu local riêng và SECRET_KEY, rồi chạy:

   docker compose up -d mysql

Đợi database healthy, sau đó chạy initialize, seed và Flask như trên. Compose chỉ mở cổng 3306 trên 127.0.0.1 và dùng volume riêng petcare_manager_mysql_data.

Để chỉ chạy MySQL như môi trường phát triển trên host: `docker compose up -d mysql`. Khi chạy ứng dụng trong container lần đầu, khởi tạo schema trước rồi mới mở web:

   docker compose run --rm web python -m petcare.database.initialize
   docker compose up -d --build web email-worker export-worker

Trong môi trường demo/dev, có thể nạp dữ liệu tổng hợp sau khi schema sẵn sàng bằng `docker compose run --rm web python -m petcare.database.seed`. Không chạy lệnh seed trên production. Compose giữ cổng web trên loopback và dùng chung volume riêng cho ảnh cùng export worker. Để dừng container nhưng giữ dữ liệu: `docker compose down`. Không dùng `docker compose down -v` trừ khi chủ động muốn xóa toàn bộ dữ liệu trong volume.

### Backup local / Docker Compose

Backup MySQL cùng ảnh hồ sơ thú cưng và sản phẩm. Lệnh tạo hỏi passphrase hai lần; verify hỏi lại để xác thực bundle và checksum:

   python scripts/petcare_backup.py create --media-source host
   python scripts/petcare_backup.py verify backups/petcare-YYYYMMDDTHHMMSSZ.pcarebackup

`create` hỏi passphrase hai lần; `verify` hỏi lại passphrase. `host` dành cho ứng dụng Flask chạy trên máy; nếu app chạy trong container, dùng `--media-source compose` để lấy ảnh từ volume của web. Chi tiết khôi phục và chuyển backup `.tar.gz` cũ sang bundle mã hóa nằm trong [docs/backup_restore.md](docs/backup_restore.md).

### Export dữ liệu một cửa hàng

Với quyền database phù hợp, export theo slug vào một bundle mã hóa mới rồi xác minh xác thực và manifest/checksum:

```bash
python -m petcare.database.export_tenant export main /secure/private/main-export.pcarexport
python -m petcare.database.export_tenant verify /secure/private/main-export.pcarexport
python -m petcare.database.export_tenant decrypt /secure/private/main-export.pcarexport /secure/private/main-export.zip
```

Lệnh `export` hỏi passphrase hai lần và không đưa bí mật vào command line. Hãy dùng ít nhất 12 ký tự, giữ passphrase riêng khỏi file export và lưu bản dự phòng an toàn: quên passphrase thì không thể khôi phục dữ liệu. Bundle dùng AES-256-GCM với khóa dẫn xuất PBKDF2-HMAC-SHA256, salt và nonce ngẫu nhiên. Nó gồm CSV từng bảng, metadata tenant, ảnh sản phẩm/thú cưng và SHA-256; không chứa password hash hoặc token hash. Text CSV có thể bị bảng tính hiểu là công thức sẽ được trung hòa bằng dấu nháy đơn; số âm và ngày vẫn giữ dạng dữ liệu. Export dùng snapshot đọc nhất quán, chỉ lấy một tenant, không ghi đè file có sẵn và tạo file quyền `0600`. `verify` xác thực mã hóa và checksum mà không trích xuất; `decrypt` chỉ tạo ZIP quyền riêng tư mới sau khi xác thực thành công. ZIP giải mã chứa dữ liệu cá nhân: giới hạn người truy cập và xóa theo chính sách lưu trữ của đơn vị. Lệnh operator này không xóa tenant hay thay thế backup/restore vận hành.

Quản trị viên cửa hàng cũng có thể vào **Tài khoản → Xuất dữ liệu cửa hàng** để yêu cầu export tenant đang chọn. Luồng xác nhận lại mật khẩu, xếp job MySQL và giao worker riêng tạo bundle mã hóa; trang trạng thái tự cập nhật, các yêu cầu gần đây có thể mở lại. Chỉ người tạo trong đúng tenant tải được file. Passphrase chờ xử lý được mã hóa bằng `TENANT_EXPORT_JOB_KEY`, xóa sau khi worker hoàn tất; file được giữ tối đa `TENANT_EXPORT_RETENTION_HOURS` giờ (mặc định 24), sau đó worker dọn file và job. Production phải dùng cùng key ổn định cho web/worker và local storage chỉ khi hai service có chung durable volume; multi-instance nên dùng `TENANT_EXPORT_STORAGE_BACKEND=s3`. Trong key rotation, giữ key cũ tạm thời ở `TENANT_EXPORT_JOB_FALLBACK_KEYS` cho tới khi job cũ hoàn tất. Vẫn cần lưu passphrase của bundle riêng để giải mã sau này.

ZIP tenant export tạo bởi phiên bản cũ chưa được mã hóa; có thể xác minh rồi chuyển bằng `python -m petcare.database.export_tenant encrypt /secure/private/old-export.zip /secure/private/new-export.pcarexport`. Giữ file ZIP cũ riêng tư cho tới khi bundle mới đã verify và được sao lưu an toàn.

## Triển khai production

`run.py` dùng Flask development server và chỉ dành cho phát triển. Image Docker chạy qua Gunicorn (`wsgi:app`) với access log không ghi query string, nơi có thể chứa từ khóa khách hàng hoặc invite token. Production bắt buộc dùng database riêng không có hậu tố `_dev`/`_test`, biến môi trường `SECRET_KEY` ngẫu nhiên riêng (không dùng giá trị tự sinh theo worker), `APP_ENV=production`, `COOKIE_SECURE=1`, `PUBLIC_BASE_URL=https://<domain-tin-cậy>` và TLS sau reverse proxy. Chỉ đặt `TRUST_PROXY=1` khi app chỉ nhận request qua đúng một proxy tin cậy và proxy ghi đè forwarded IP/protocol; ứng dụng không tin forwarded host/port. Endpoint Prometheus `/metrics` mặc định tắt; nếu bật, cấp `OPS_METRICS_TOKEN` từ secret manager và chỉ cho monitoring riêng tư truy cập. Hướng dẫn vận hành nằm trong [docs/operations.md](docs/operations.md); launch gates nằm trong [docs/launch_readiness.md](docs/launch_readiness.md).

Trên production, cấp cho tài khoản runtime của web chỉ `SELECT`, `INSERT`, `UPDATE`, `DELETE` trên database cửa hàng. Chạy `python -m petcare.database.initialize` bằng tài khoản migration riêng có `CREATE`, `ALTER`, `INDEX`, `REFERENCES` và quyền đọc metadata; không cấp quyền DDL cho web runtime và không dùng MySQL `root`. Các lệnh cài local ở phần trên dùng cho dev, không phải cấu hình quyền production.

Initializer đọc `MIGRATION_DB_USER`/`MIGRATION_DB_PASSWORD` chỉ trong job migration; production từ chối chạy nếu thiếu tài khoản riêng hoặc tài khoản trỏ sang database khác. Tham khảo [hướng dẫn quyền MySQL](docs/database_privileges.md); không truyền migration secret vào service web.

Xem [hướng dẫn cấu hình, IAM và chuyển ảnh sang S3](docs/media_storage.md) trước khi đổi backend; cấu hình S3 không tự di chuyển ảnh local hiện có.

Ảnh dùng filesystem riêng ở chế độ local. Với nhiều app instance, đặt `MEDIA_STORAGE_BACKEND=s3`, `MEDIA_S3_BUCKET` và `MEDIA_S3_REGION`; SDK dùng IAM/workload identity nếu không khai báo access key pair. Bucket phải private, bật chặn public access và encryption. Custom S3 endpoint production bắt buộc HTTPS. Route ảnh vẫn đi qua app để xác minh đăng nhập, membership và quyền sở hữu tenant; không bật public ACL/CDN bypass. Tenant export có thể đóng gói ảnh từ backend này. `scripts/petcare_backup.py` chỉ hỗ trợ ảnh local và từ chối tạo backup khi chọn S3 để tránh thiếu ảnh.

GitHub Actions được cấu hình tại `.github/workflows/ci.yml`: chạy unit/web/MySQL integration trên MySQL 8.4 với Python 3.11–3.13, audit dependency Python bằng `pip-audit`, quét Python source bằng Bandit, quét secret cả source tree và production container bằng Trivy, đồng thời build và quét image. Hosted run cần xanh trước mỗi release.

## Tài khoản và dữ liệu demo

Seed idempotent tạo dữ liệu hoàn toàn tổng hợp trong store `main`, có nhãn demo:

- Mã cửa hàng: `main`
- Admin: admin / Admin@123
- Nhân viên: staff1 / Staff@123
- 12 hồ sơ khách demo với số điện thoại giả có đầu `00000000`.
- 22 sản phẩm có mã, danh mục, mô tả, giá, tồn kho và ngưỡng bổ sung riêng.
- 74 cá thể thú cưng: 35 chó, 37 mèo, 1 thỏ và 1 hamster; 68 hồ sơ có ảnh AI tổng hợp (32 chó, 32 mèo và 4 ảnh mẫu cũ).
- Ảnh và hồ sơ là dữ liệu hư cấu phục vụ học tập/demo, không đại diện cho thú cưng hoặc hàng tồn tại cửa hàng thật.
- 7 hóa đơn demo đã thanh toán để báo cáo có dữ liệu lịch sử; tồn kho được cập nhật qua luồng bán thật.

Chỉ chạy `python -m petcare.database.seed` trên database tên kết thúc bằng `_dev` hoặc `_test` để nạp danh mục mới vào MySQL. Dữ liệu demo được chèn lặp an toàn, không ghi đè sản phẩm, khách hàng, mật khẩu hoặc hồ sơ đã có. Những dữ liệu seed trong database hiện tại được giữ nguyên; vì thế các hàng cũ có thể khác dữ liệu mẫu mới.

Để dùng database mới với dữ liệu thật: tạo database riêng, cấu hình `.env`, chạy `python -m petcare.database.initialize`, rồi chạy `python -m petcare.database.create_admin`. Lệnh tạo admin yêu cầu xác nhận đúng tên database, nhập mật khẩu qua prompt ẩn và chỉ hoạt động khi database chưa có tài khoản. Sau đó đăng nhập, tạo nhân viên trong **Tài khoản**, rồi nhập danh mục và khách hàng thật. Không chạy seed demo trên database thật. Mật khẩu được băm PBKDF2-HMAC-SHA256; ứng dụng không lưu mật khẩu rõ.

Để provision thêm cửa hàng trong cùng database, dùng `python -m petcare.database.create_store` trong terminal tương tác. Lệnh xác nhận database, tạo slug/tenant và owner; có thể gắn thêm một username hiện có nếu nhập đúng mật khẩu hiện tại. Admin của cửa hàng có thể vào **Tài khoản → Mời thành viên** để tạo lời mời theo email một lần (hết hạn sau 7 ngày) và thu hồi lời mời. Owner bàn giao vai trò từ **Tài khoản → Bàn giao chủ cửa hàng**: owner và admin được chọn đều phải xác thực lại; admin mục tiêu phải chấp nhận trong vòng 72 giờ. Khi SMTP hoạt động và email người nhận đã xác minh, hệ thống gửi email thông báo nhưng vẫn bắt buộc đăng nhập và chấp thuận trong ứng dụng. Self-service `/signup` có feature flag `PUBLIC_SIGNUP_ENABLED=0` mặc định; account owner chỉ có quyền sau khi xác minh email. Không bật signup công khai trước khi có billing/plan limits, terms/privacy, edge abuse controls và email provider đã kiểm live. Khi đăng nhập, nhập slug cửa hàng; tài khoản có nhiều membership có thể đổi cửa hàng từ sidebar.

## Luồng dùng thử

1. Đăng nhập admin.
2. Mở Sản phẩm để xem danh mục demo có mô tả, tồn kho và mức cảnh báo bổ sung.
3. Chọn một khách, sản phẩm và thú cưng demo để lập hóa đơn; server tự tính tổng từ giá hiện hành.
4. Trước khi thanh toán, kiểm tra tồn kho đang hiển thị; tạo hóa đơn chưa trừ tồn.
5. Xác nhận thanh toán; tồn kho từng mặt hàng được trừ đúng số lượng và thú cưng chuyển sang Đã bán, gắn với khách mua.
6. Mở Báo cáo để đối chiếu doanh thu. Gửi lại thao tác thanh toán không làm thay đổi số liệu lần hai.

Form hóa đơn tìm khách hàng/mặt hàng trực tiếp trên máy chủ, tải mỗi lần 25 kết quả. Admin xem **Nhật ký hoạt động** để kiểm tra các lần tạo/thu/hủy hóa đơn, điều chỉnh tồn và thay đổi tài khoản.

## Trợ lý cửa hàng và tìm thú cưng bằng ảnh

- Nút **Hỏi trợ lý** trả lời tổng quan, doanh thu hôm nay/tuần/tháng, tồn thấp, tìm sản phẩm và lọc thú cưng theo loài, giống, màu lông/mắt, giới tính hoặc mức giá; có hướng dẫn luồng hóa đơn và tìm bằng ảnh. Câu trả lời local lấy dữ liệu từ MySQL, không cần API key. Câu trả lời tạo sinh chỉ bật khi cấu hình endpoint; giao diện hiển thị rõ nguồn trả lời. Nút **Xóa cuộc trò chuyện** xóa lịch sử trong trang hiện tại, dừng chờ kết quả trên trình duyệt và ngăn gửi lịch sử đó ở lượt sau.
- Trang **Tìm bằng ảnh** xếp hạng thú cưng đang bán theo đặc trưng màu và bố cục ảnh hồ sơ đã lưu, sau đó bổ sung mức khớp với màu lông, màu mắt và đặc điểm do cửa hàng ghi nhận. Màu ưu tiên vùng trung tâm để giảm ảnh hưởng của nền; bố cục toàn khung vẫn có thể ảnh hưởng. Admin thêm ảnh và thông tin ngoại hình trong hồ sơ thú cưng. Ảnh hồ sơ được đổi tên ngẫu nhiên, loại metadata và lưu riêng tư theo backend media đã cấu hình (local mặc định).
- Chế độ cục bộ không phải mô hình nhận diện vật thể: ảnh tham khảo được so sánh với ảnh hồ sơ, không tự phát hiện mắt/giống/chủ thể trong ảnh. Điểm tương tự chỉ để tham khảo. Có thể bật AI Vision để phân tích loài, màu lông, hoa văn, màu mắt và dáng qua endpoint AI tương thích OpenAI.
- Để bật câu trả lời tạo sinh: đặt `AI_API_BASE_URL`, `AI_MODEL` và nếu cần `AI_API_KEY` trong `.env`. Endpoint cần hỗ trợ `/v1/chat/completions`. Trợ lý chỉ gửi phần dữ liệu cửa hàng phù hợp câu hỏi; tùy mục có thể gồm tên/giá sản phẩm hoặc tên/đặc điểm thú cưng, không tự gửi hồ sơ khách hàng. Câu hỏi và tối đa 8 tin nhắn chat trước đó vẫn được gửi tới endpoint; không nhập dữ liệu nhạy cảm nếu chính sách nhà cung cấp chưa được duyệt. Hộp chat thông báo nội dung trao đổi khi AI đang bật. Production yêu cầu HTTPS; chỉ bật `AI_ALLOW_HTTP_ENDPOINT=1` cho endpoint nội bộ trên mạng tin cậy.
- Muốn bật phân tích ảnh: chỉ khi endpoint hỗ trợ ảnh, đặt thêm `AI_VISION_ENABLED=1`. Ảnh tải lên để tìm kiếm sẽ được gửi tới endpoint đã cấu hình; mặc định mục này là `0`. Khi AI Vision tắt, ảnh tìm kiếm vẫn được gửi tới máy chủ ứng dụng nhưng không gửi tới endpoint AI và không lưu thành hồ sơ.
- Giới hạn ảnh hồ sơ/sản phẩm/tìm kiếm là 5 MB mỗi ảnh; ảnh được chuẩn hóa, bỏ metadata và lưu ở filesystem local hoặc bucket S3-compatible riêng tư. MySQL lưu tên file, metadata hồ sơ và descriptor để xếp hạng. Backup local chỉ dùng với backend local; S3 cần backup/versioning theo provider.
- Trên POSIX, ảnh mới dùng quyền riêng tư cho thư mục/tệp. Trước khi nâng cấp một máy đã có ảnh cũ, chạy `.venv/bin/python -m petcare.vision.secure_photo_permissions` (hoặc `python -m ...` trong môi trường đã kích hoạt) để siết quyền các ảnh hiện có.

### Quét ảnh bằng camera

- Trên laptop, mở **Tìm bằng ảnh** rồi nhấn **Bật camera máy tính**. Trình duyệt chỉ xin quyền sau cú nhấn này; xem khung hình trực tiếp, nhấn **Chụp ảnh & tìm** để gửi một ảnh vào luồng tìm hiện có. Nhấn **Tắt camera** hoặc rời trang để đóng camera.
- Trên điện thoại cùng Wi‑Fi, nút chọn ảnh có thể mở camera sau. Muốn mở trang trên điện thoại bằng QR, lấy IP Wi‑Fi riêng của laptop (macOS: `ipconfig getifaddr en0`; Windows: chạy `ipconfig` và lấy IPv4 của Wi‑Fi), đặt trong `.env`:

  ```env
  LAN_ACCESS_ENABLED=1
  APP_PORT=5001
  LAN_ACCESS_BASE_URL=http://192.168.1.25:5001
  ```

  Thay IP ví dụ bằng IP thật rồi khởi động lại `python run.py`. Dùng cổng trống; macOS có thể đã dành cổng 5000 cho AirPlay Receiver, nên ví dụ dùng 5001. Hai thiết bị cần cùng Wi‑Fi; nếu tường lửa hỏi, chỉ cho phép kết nối trên mạng riêng. Quét QR ở trang tìm bằng ảnh, đăng nhập trên điện thoại, rồi chụp/chọn ảnh. Kết quả hiện trên điện thoại. Khi không cần nữa, đặt `LAN_ACCESS_ENABLED=0` và khởi động lại.
- Cấu hình LAN mặc định tắt; nếu thiếu URL hợp lệ, máy chủ tiếp tục chỉ nghe trên localhost. Chỉ dùng trên mạng tin cậy vì HTTP LAN không mã hóa. Camera trực tiếp qua `getUserMedia` cần localhost hoặc HTTPS; trên điện thoại LAN dùng camera gốc qua trình chọn ảnh vì trình duyệt thường chặn camera trực tiếp trên HTTP.
- Production không chấp nhận QR LAN dùng HTTP. Nếu cần stream camera trực tiếp trên điện thoại, dùng một origin HTTPS đáng tin; camera gốc qua trình chọn ảnh vẫn hoạt động trên mạng LAN HTTP riêng.
- Tính năng chụp một khung hình để tìm, không truyền video liên tục. Tìm cục bộ vẫn xếp hạng theo màu và bố cục ảnh hồ sơ, không phát hiện giống hay loài như Google Lens; bật endpoint AI Vision riêng nếu cần phân tích ngữ nghĩa.
- Descriptor ảnh cũ vẫn đọc được và được tìm theo luồng tương thích cho tới khi reindex. Chạy `.venv/bin/python -m petcare.vision.reindex_pet_descriptors` để xem trước rồi thêm `--apply` để cập nhật descriptor và chỉ mục SimHash theo batch; lệnh không sửa ảnh gốc và mặc định không ghi database.

## Cấu hình bảo mật

- Session chỉ giữ user id; trạng thái active và role được đọc lại từ MySQL trong mỗi request.
- Các request thay đổi dữ liệu dùng POST và CSRF token.
- Tổng hóa đơn, snapshot tên/giá, tồn kho và trạng thái bán được xác thực phía server.
- Mật khẩu MySQL và SECRET_KEY chỉ nằm trong .env. Không đưa .env, DB dump, dữ liệu khách thật hoặc .venv lên Git.
- Mặc định chỉ chạy trên localhost; LAN chỉ bật chủ động bằng cấu hình nêu trên. Không cấu hình Flask debug hoặc mở cổng công khai cho dữ liệu thật.

## Kiểm tra

- Biên dịch cú pháp: python -m compileall -q run.py main.py petcare tests
- Unit và web tests: python -m unittest discover -s tests -v
- Test MySQL tích hợp: cấu hình DB_HOST/DB_PORT/DB_USER/DB_PASSWORD và PETCARE_TEST_DB_NAME trỏ tới database test riêng có hậu tố _test. Không chạy fixture test trên DB làm việc.

Phần test nào cần MySQL thật sẽ không được tính là đã nghiệm thu nếu không có server MySQL test hoạt động.

## Hỗ trợ sự cố thường gặp

- Connection refused / can't connect: đảm bảo MySQL đang chạy và DB_HOST/DB_PORT đúng.
- Access denied: kiểm tra DB_USER, DB_PASSWORD và host được cấp quyền trong MySQL.
- Unknown database: tạo petcare_shop_dev trước khi initialize.
- Port 3306 đang dùng: chọn cổng khác và cập nhật DB_PORT.
- Lỗi schema/check constraint: xác nhận MySQL 8.0.16+; không chạy schema này trên SQLite.
