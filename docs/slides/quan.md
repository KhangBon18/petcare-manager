# Nội dung Slide Báo cáo — Quân (docs/slides/quan.md)

## Slide 1: Thú cưng & Tiêm chủng
- Họ tên: Quân
- Nhiệm vụ: Kỹ sư Quản lý Thú cưng, Tiêm phòng & Mô hình Dữ liệu ERD
- Tỷ lệ đóng góp: 25%

## Slide 2: Quản lý Thú cưng & Tính toàn vẹn
- Ràng buộc hợp lệ: Tên, loài, cân nặng >= 0, ngày sinh không ở tương lai.
- Chặn đổi chủ nuôi khi thú cưng đã có hóa đơn lịch sử.
- Ngừng theo dõi (`active=0`) thay vì xóa khi đã có bệnh án.

## Slide 3: Tiêm phòng & Lịch nhắc Vaccine
- Ghi nhận mũi tiêm kèm kiểm tra ngày hẹn tiêm nhắc (phải sau ngày tiêm).
- Đồng bộ tạo lượt dịch vụ `service_visits` trong cùng transaction.
- Bảng lọc các mũi tiêm đến hạn trong vòng 30 ngày và đánh dấu hoàn thành.

## Slide 4: Thiết kế ERD & Từ điển Dữ liệu
- 10 bảng dữ liệu chuẩn hóa, khóa ngoại và chỉ mục tối ưu truy vấn.
- Ràng buộc khóa ngoại luôn được bật với `PRAGMA foreign_keys = ON;`.
