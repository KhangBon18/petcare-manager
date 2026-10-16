# Nội dung Slide Báo cáo — Nhàn (docs/slides/nhan.md)

## Slide 1: Cơ sở Dữ liệu & Tài chính
- Họ tên: Nhàn
- Nhiệm vụ: Kỹ sư Cơ sở Dữ liệu, Lượt dịch vụ, Hóa đơn & Quản lý Doanh thu
- Tỷ lệ đóng góp: 25%

## Slide 2: Khởi tạo Database & Seed An toàn
- `initialize.py`: Tạo bảng an toàn bằng `CREATE TABLE IF NOT EXISTS`.
- `seed.py`: Nạp dữ liệu demo với tính chất idempotent (chạy lặp không nhân đôi bản ghi).
- `config.py`: Đường dẫn tuyệt đối chuẩn hóa theo dự án, không phụ thuộc `cwd`.

## Slide 3: Hóa đơn & Quy tắc Tính phí Một lần
- Gom các lượt dịch vụ chưa thanh toán của cùng một chủ nuôi.
- Ràng buộc `visit_id UNIQUE` bảo đảm mỗi lượt chỉ tính tiền đúng 1 lần.
- Snapshot tên dịch vụ, tên thú cưng và giá tiền vào `invoice_items`.
- Hủy hóa đơn `unpaid` xóa chi tiết để giải phóng `visit_id`.

## Slide 4: Thanh toán Trực tiếp & Doanh thu
- Thanh toán chuyển sang `paid`, lưu `paid_at`. Hóa đơn `paid` là bất biến.
- Thanh toán lặp trả về `already_paid`, không cộng dồn doanh thu.
- Doanh thu tính theo ngày thanh toán `paid_at`, xử lý chính xác ranh giới ngày.
- Quy trình sao lưu và phục hồi database SQLite an toàn.
