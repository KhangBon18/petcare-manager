# Kịch bản Slide Báo cáo Chung (final_slides.md)

## Slide 1: Trang Bìa
- **Đề tài**: PetCare Manager — Hệ thống Quản lý Phòng khám & Chăm sóc Thú cưng
- **Công nghệ**: Python, Tkinter/ttk, SQLite
- **Nhóm sinh viên**: Khang, Quân, Quý, Nhàn
- **Mục tiêu**: Báo cáo nghiệm thu phiên bản hoàn chỉnh v1.0.0

## Slide 2: Mục tiêu & Yêu cầu Nghiệp vụ
- Ứng dụng desktop chạy cục bộ độc lập trên Windows/macOS.
- Quy trình khép kín: Tiếp nhận khách hàng -> Hồ sơ thú cưng -> Bệnh án/Tiêm chủng/Hẹn -> Thu ngân -> Báo cáo tài chính.
- Bảo đảm tính toàn vẹn dữ liệu, không có nút thông báo giả, không dữ liệu hardcode.

## Slide 3: Kiến trúc Phần mềm 3 Lớp (Three-Tier)
- **UI Layer (`petcare/ui/`)**: Tkinter/ttk, giao diện tiếng Việt, 1 Tk root duy nhất, không chứa SQL.
- **Service Layer (`petcare/services/`)**: Nghiệp vụ, validation, phân quyền, điều phối transaction.
- **Repository Layer (`petcare/repositories/`)**: SQL có tham số, nhận kết nối `conn`, không tự commit.
- **Cơ sở dữ liệu**: SQLite 3, luôn kích hoạt `PRAGMA foreign_keys = ON;`.

## Slide 4: Thiết kế Dữ liệu & Sơ đồ ERD
- 10 bảng dữ liệu chuẩn hóa: `users`, `owners`, `pets`, `services`, `service_visits`, `examinations`, `vaccinations`, `appointments`, `invoices`, `invoice_items`.
- Ràng buộc bất biến cốt lõi:
  - `visit_id UNIQUE` trên `invoice_items` chống tính phí lặp.
  - `visit_id UNIQUE` trên `examinations` và `vaccinations` gắn liền 1-1 với lượt dịch vụ.

## Slide 5: Quy tắc Tài chính & Bảo toàn Doanh thu
- Đơn vị tiền tệ: Số nguyên VND.
- Snapshot giá: Thay đổi bảng giá niêm yết không sửa đổi các lượt dịch vụ đã phát sinh.
- Hóa đơn `paid` là bất biến: Không thể sửa, không thể hủy.
- Thanh toán lặp trả về `already_paid`, không ghi nhận thêm doanh thu.
- Hủy hóa đơn `unpaid` xóa dòng chi tiết để giải phóng `visit_id`.

## Slide 6: Kết quả Kiểm thử Toàn diện
- Compileall: 100% ĐẠT, 0 lỗi cú pháp.
- 34 Unit tests & Integration tests tự động: 100% PASS.
- Luồng tích hợp Lan & Miu: Hoàn thành liền mạch từ tạo chủ đến xuất hóa đơn và đối chiếu báo cáo.
- Kiểm thử khởi chạy và điều hướng 10 màn hình GUI không lỗi.
- Khởi tạo DB và Seed chạy lặp an toàn (idempotent).

## Slide 7: Demo Ứng dụng (Trực tiếp)
- Đăng nhập Admin & Staff (phân quyền động).
- Tiếp nhận chị Lan và mèo Miu.
- Khám bệnh, tiêm phòng, lịch hẹn, dịch vụ tắm spa.
- Lập hóa đơn và thanh toán trực tiếp tại quầy.
- Tra cứu bảng điều khiển thống kê doanh thu theo ngày.

## Slide 8: Kết luận & Bàn giao
- Hoàn thành đầy đủ 100% phạm vi bắt buộc của đồ án theo `REPO_GUIDE.md`.
- Hướng dẫn cài đặt và chạy chi tiết cho cả Windows và macOS.
- Đóng gói bản phát hành chính thức v1.0.0.
- Cảm ơn Thầy Cô và Hội đồng đánh giá!
