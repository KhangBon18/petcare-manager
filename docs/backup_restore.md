# Sao lưu và khôi phục

## Tạo backup

Ứng dụng không lưu ảnh trong MySQL. Với `MEDIA_STORAGE_BACKEND=local`, backup phải có database và hai thư mục ảnh. Với `MEDIA_STORAGE_BACKEND=s3`, tenant export vẫn đóng gói ảnh theo từng cửa hàng; backup vận hành phải bảo vệ database và bucket theo cấu hình provider.

### Chạy ứng dụng Flask trên máy host

1. Khởi động MySQL bằng Docker Compose: `docker compose up -d mysql`.
2. Từ thư mục gốc dự án, chạy:

       python scripts/petcare_backup.py create --media-source host

### Chạy ứng dụng web trong Docker Compose

Đảm bảo cả `mysql` và `web` đang chạy, sau đó chạy:

    python scripts/petcare_backup.py create --media-source compose

Mặc định, bundle `.pcarebackup` được tạo trong `backups/`, một thư mục bị Git và Docker loại trừ. Lệnh hỏi passphrase hai lần; nhập ít nhất 12 ký tự và lưu riêng khỏi bundle. Quên passphrase sẽ khiến backup không khôi phục được. Bundle mã hóa AES-256-GCM bằng khóa dẫn xuất PBKDF2-HMAC-SHA256, có salt/nonce ngẫu nhiên và quyền file 0600. Dữ liệu SQL/ảnh được staging trong thư mục tạm riêng quyền 0700; mật khẩu MySQL chỉ được ghi tạm vào option file quyền 0600 trong container rồi xóa, không nằm trong command line hay log.

`scripts/petcare_backup.py` hiện chỉ hỗ trợ ảnh filesystem local và sẽ dừng nếu `MEDIA_STORAGE_BACKEND=s3`, để không tạo bundle thiếu media. Khi dùng S3, bật chặn public access, mã hóa/versioning và chính sách retention ở provider; dùng backup/export database phù hợp, đồng thời diễn tập khôi phục cả database lẫn object bucket. Tenant export theo một tenant đọc ảnh từ storage backend đã cấu hình và ghi checksum vào bundle mã hóa.

Có thể đặt đích khác:

    python scripts/petcare_backup.py create --output /duong-dan-rieng/petcare.pcarebackup --media-source host

Backup `.tar.gz` được tạo bởi phiên bản cũ chưa được mã hóa. Không dùng chúng như bundle bảo mật. Có thể xác minh manifest/checksum rồi tạo bản mã hóa mới, giữ nguyên file nguồn cho tới khi đã xác minh bản mới:

    python scripts/petcare_backup.py encrypt /duong-dan-rieng/petcare-cu.tar.gz /duong-dan-rieng/petcare-moi.pcarebackup
    python scripts/petcare_backup.py verify /duong-dan-rieng/petcare-moi.pcarebackup

Không lưu passphrase cùng bundle. Bundle vẫn chứa dữ liệu nhạy cảm đã mã hóa, vì vậy chỉ lưu ở nơi được kiểm soát. Công cụ này phù hợp với môi trường local/Compose một máy; không có lịch chạy, retention, point-in-time recovery, off-site replication hay key management tập trung. Production cần backup do nhà cung cấp quản lý, retention, cảnh báo và bản sao vùng độc lập.

## Kiểm tra backup

Trước khi lưu trữ hoặc khôi phục, xác minh toàn bộ checksum và đường dẫn ảnh:

    python scripts/petcare_backup.py verify backups/petcare-YYYYMMDDTHHMMSSZ.pcarebackup

Lệnh verify hỏi passphrase, giải mã vào file tạm quyền 0600, xác thực tag AES-GCM trước khi đọc, kiểm tra manifest, checksum và đường dẫn ảnh, rồi xóa file tạm. Lệnh không kết nối MySQL và không sửa dữ liệu.

## Khôi phục có kiểm soát

Khôi phục thử trước vào một database mới, riêng biệt và các thư mục ảnh trống. Không import đè lên database hoặc thư mục ảnh đang chạy.

1. Xác minh bundle như hướng dẫn trên.
2. Tạo tar.gz riêng tư đã giải mã bằng lệnh dưới đây. Nhập passphrase tại prompt; lệnh chỉ tạo output mới với quyền 0600 sau khi xác thực và checksum thành công:

       python scripts/petcare_backup.py decrypt backups/petcare-YYYYMMDDTHHMMSSZ.pcarebackup /duong-dan-rieng/petcare-restore.tar.gz

   Không đưa tar.gz giải mã lên dịch vụ chia sẻ; xóa theo chính sách lưu trữ sau khi khôi phục.
3. Dùng công cụ quản trị MySQL tạo database mới, ví dụ `petcare_shop_restore`, mã hóa `utf8mb4`. Không dùng tên database đang chạy.
4. Giải nén `database.sql` và `media.tar.gz` từ tar.gz đã giải mã vào một thư mục staging riêng có quyền truy cập hạn chế. Archive ngoài chỉ chứa đúng các file này và manifest:

       umask 077
       mkdir -m 700 /duong-dan-rieng/petcare-restore
       tar -xOf /duong-dan-rieng/petcare-restore.tar.gz database.sql > /duong-dan-rieng/petcare-restore/database.sql
       tar -xOf /duong-dan-rieng/petcare-restore.tar.gz media.tar.gz > /duong-dan-rieng/petcare-restore/media.tar.gz

5. Import `database.sql` vào database mới bằng MySQL admin client hoặc công cụ quản trị tin cậy. Cấu hình client bằng prompt/option file riêng tư; không ghi mật khẩu trong câu lệnh.
6. Giải nén `media.tar.gz` vào staging. Sau đó chép nội dung `pet-images/` và `product-images/` vào thư mục ảnh trống của ứng dụng đã khôi phục; giữ nguyên tên file.
7. Trỏ một instance khôi phục riêng vào database và thư mục ảnh đó. Kiểm tra đăng nhập, khách hàng, hồ sơ thú cưng, sản phẩm, tồn kho và hóa đơn trước khi chuyển traffic.
8. Ghi lại thời gian khôi phục và kết quả. Thực hiện diễn tập định kỳ; một file backup chưa được restore thử chưa chứng minh được khả năng khôi phục.

Gói của công cụ không tạo database đích, không chạy câu lệnh DROP, và không tự import dữ liệu. Việc chọn đúng database đích và cấp quyền nhập là thao tác admin có chủ đích.

### Diễn tập local gần nhất

Ngày 2026-10-18, backup từ `petcare_shop_test` được mã hóa, verify, giải mã và import vào một database `_test` mới có tên ngẫu nhiên. Số dòng nguồn và bản restore khớp: 13 khách hàng, 22 sản phẩm, 10 thú cưng, 7 hóa đơn; 9 file ảnh đã được trích xuất vào staging riêng. Database restore tạm được xóa sau kiểm tra; DB nguồn không bị thay đổi. Đây là bằng chứng cho Compose/local với dữ liệu demo/test, chưa xác nhận quy trình backup/restore của nhà cung cấp managed production.

## Ranh giới vận hành

- Công cụ lấy snapshot nhất quán của bảng InnoDB và chỉ backup đúng một database.
- Nguồn ảnh `host` là cấu hình thư mục ảnh Flask local. Nguồn `compose` là volume `/app/instance` của web container.
- AES-GCM bảo vệ tính bí mật/toàn vẹn của bundle và SHA-256 kiểm tra payload bên trong; chúng không bảo vệ khỏi xóa toàn bộ máy hoặc mất passphrase.
- Các bản backup `.tar.gz` cũ vẫn là plaintext; lệnh `verify` mới chỉ nhận `.pcarebackup`. Chuyển chúng bằng lệnh `encrypt` và chỉ xóa bản cũ theo chính sách lưu trữ.
- Tự động chạy lịch, bản sao off-site, retention, cảnh báo và point-in-time recovery vẫn phải được cấu hình trong nền tảng triển khai trước khi dùng production.
