# Nội dung Slide Báo cáo — Quân (docs/slides/quan.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](../report/final_report.md) và [dàn ý slide hiện hành](final_slides.md).


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
