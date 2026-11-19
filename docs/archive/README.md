# Tài liệu lịch sử

Thư mục này giữ lại kế hoạch, phạm vi, mã nguồn và test của bản desktop Tkinter/SQLite để tham khảo. Chúng không phải đặc tả chạy của ứng dụng web hiện hành.

File `desktop_data/quan_ly_thu_cung.sql` chỉ chứa câu lệnh tạo một database cũ; nó không có bảng hay dữ liệu và không được dùng để cài đặt PetCare Manager hiện hành. Schema đang dùng nằm tại `petcare/database/schema.sql`.

## Lịch sử đối soát với `main` (`5f43633`)

- Trên nhánh `main`, commit lịch sử `5f43633` (`2026-10-16`, kế tiếp `92cf654`) từng cập nhật `data/quan_ly_thu_cung.sql` thành một bản dump MySQL học tập đơn lẻ (`quan_ly_cua_hang_thu_cung`, gồm 4 bảng `khach_hang`, `san_pham`, `tai_khoan`, `thu_cung` kèm dữ liệu mẫu plaintext trong `tai_khoan`).
- Khi nhánh phát triển web `solo/khang-petcare` tách nhánh từ `8c7c176` (`v1.0.0`), file gốc `data/quan_ly_thu_cung.sql` đã được chuyển vào `docs/archive/desktop_data/quan_ly_thu_cung.sql`, dẫn tới xung đột `modify/delete` trên PR `#8` (`solo/khang-petcare` -> `main`).
- Để đồng bộ hai nhánh **không viết lại lịch sử** mà vẫn giữ kho mã phát hành an toàn:
  1. Commit `5f43633` được giữ nguyên trong cây lịch sử Git thông qua merge commit đối soát từ `origin/main`.
  2. File lỗi thời `data/quan_ly_thu_cung.sql` không được khôi phục về thư mục gốc và bản dump chứa dữ liệu mẫu plaintext không được ghi đè vào `docs/archive/desktop_data/quan_ly_thu_cung.sql`.
  3. Toàn bộ schema và migration đang hoạt động của PetCare Manager vẫn duy trì nguyên vẹn trong `petcare/database/`.

