# Nội dung Slide Báo cáo — Khang (docs/slides/khang.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](../report/final_report.md) và [dàn ý slide hiện hành](final_slides.md).


## Slide 1: Giới thiệu & Vai trò Điều phối
- Họ tên: Khang
- Nhiệm vụ: Trưởng nhóm, Thiết kế Kiến trúc & Module Bảo mật, Chủ nuôi
- Tỷ lệ đóng góp: 25%

## Slide 2: Kiến trúc 3 Lớp & Điều phối Frame
- Single Tk root duy nhất, vòng lặp mainloop ổn định.
- Phân tầng nghiêm ngặt: UI -> Service -> Repository -> SQLite.
- Callback giao diện tuyệt đối không chứa SQL.

## Slide 3: Bảo mật Mật khẩu & Phân quyền
- Thuật toán PBKDF2-HMAC-SHA256, 100.000 vòng lặp, salt ngẫu nhiên 16 bytes.
- Cơ chế bảo vệ Admin cuối cùng.
- Phiên làm việc `AuthSession` bất biến.

## Slide 4: Quản lý Chủ nuôi & Hồ sơ Tổng hợp
- CRUD chủ nuôi, tìm kiếm nhanh, kiểm tra định dạng số điện thoại.
- Cơ chế `deactivated` (`active=0`) bảo toàn lịch sử.
- Màn hình `PetProfileView` 4 tab: Khám bệnh, Tiêm phòng, Lịch hẹn, Lượt dịch vụ & Chi phí.
