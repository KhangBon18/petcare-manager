# Hướng dẫn Sao lưu & Phục hồi Dữ liệu (backup_restore.md)

Tài liệu này hướng dẫn cách sao lưu dự phòng (backup) và phục hồi (restore) cơ sở dữ liệu SQLite của ứng dụng PetCare Manager.

---

## 1. Vị trí Lưu trữ Dữ liệu

Cơ sở dữ liệu của ứng dụng được lưu trữ tại:
```
data/petcare.db
```
Đường dẫn này được quản lý tập trung tại `petcare/config.py` và luôn được tính toán tự động dựa trên thư mục gốc của dự án, không phụ thuộc vào thư mục làm việc hiện tại (`cwd`) khi chạy terminal.

---

## 2. Quy trình Sao lưu Dự phòng (Backup)

### Cách 1: Sao lưu trực tiếp khi ứng dụng đã đóng (Đơn giản nhất & An toàn tuyệt đối)
1. Đảm bảo ứng dụng PetCare Manager đã được tắt hoàn toàn (để SQLite giải phóng lock và ghi toàn bộ dữ liệu từ journal/WAL vào file chính).
2. Tạo bản sao file `data/petcare.db` sang thư mục sao lưu, ví dụ:
   ```bash
   # macOS / Linux
   mkdir -p backups
   cp data/petcare.db "backups/petcare_backup_$(date +%Y%m%d_%H%M%S).db"
   ```
   ```powershell
   # Windows PowerShell
   New-Item -ItemType Directory -Force -Path backups
   $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
   Copy-Item "data\petcare.db" -Destination "backups\petcare_backup_$timestamp.db"
   ```

### Cách 2: Sao lưu bằng lệnh SQLite (Online Backup)
```bash
sqlite3 data/petcare.db ".backup 'backups/petcare_online_backup.db'"
```

---

## 3. Quy trình Phục hồi Dữ liệu (Restore)

Khi muốn khôi phục lại dữ liệu từ một bản sao lưu trước đó:
1. **Đóng ứng dụng PetCare Manager** (bắt buộc).
2. Xóa hoặc đổi tên file `data/petcare.db` hiện tại để lưu vết:
   ```bash
   mv data/petcare.db data/petcare_corrupted.db
   ```
3. Chép file sao lưu trở lại đường dẫn `data/petcare.db`:
   ```bash
   cp backups/petcare_backup_YYYYMMDD_HHMMSS.db data/petcare.db
   ```
4. Khởi động lại ứng dụng:
   ```bash
   python main.py
   ```
   Hệ thống sẽ tự động nhận diện và đọc toàn bộ dữ liệu đã được phục hồi.

---

## 4. Lưu ý quan trọng
- Thư mục `data/*.db` đã được cấu hình trong `.gitignore` để tránh vô tình commit dữ liệu cục bộ hoặc thông tin cá nhân lên Git.
- Dữ liệu cơ sở dữ liệu trên mỗi máy thành viên là độc lập; dự án chia sẻ mã nguồn, cấu trúc `schema.sql` và dữ liệu mẫu `seed.py`.
