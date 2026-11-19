# Nội dung Slide Báo cáo — Quý (docs/slides/quy.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](../report/final_report.md) và [dàn ý slide hiện hành](final_slides.md).


## Slide 1: Nghiệp vụ Y tế & Báo cáo Hoạt động
- Họ tên: Quý
- Nhiệm vụ: Kỹ sư Nghiệp vụ Y tế, Bảng giá, Lịch hẹn & Thống kê
- Tỷ lệ đóng góp: 25%

## Slide 2: Danh mục Dịch vụ & Phân quyền Bảng giá
- Quản lý gói dịch vụ và giá niêm yết (VND >= 0).
- Kiểm tra quyền tại Service: Chỉ Admin được đổi giá; Staff chỉ được xem.
- Đổi giá niêm yết không ảnh hưởng đến giá của các lượt dịch vụ trong quá khứ.

## Slide 3: Khám bệnh & Lịch hẹn
- Ghi nhận triệu chứng, chẩn đoán, đơn thuốc.
- Giao dịch kép: Tạo ca khám và lượt dịch vụ trong cùng 1 transaction atomic.
- Quản lý lịch hẹn: Lên kế hoạch tiếp đón, **tuyệt đối không tự tạo chi phí**.

## Slide 4: Thống kê & Kịch bản Nghiệm thu
- Ghép nối màn hình thống kê hoạt động và nhúng doanh thu.
- Xây dựng 10 ca kiểm thử nghiệm thu chi tiết và kịch bản demo bảo vệ đồ án.
