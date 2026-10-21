# Báo cáo Cá nhân — Nhàn (docs/report/nhan.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](final_report.md) và [dàn ý slide hiện hành](../slides/final_slides.md).


- **Họ và tên**: Nhàn
- **Vai trò**: Kỹ sư Cơ sở Dữ liệu & Quản lý Tài chính
- **Mục tiêu đóng góp**: 25% khối lượng công việc

---

## 1. Nhiệm vụ đảm nhiệm & Mã nguồn phụ trách

1. **Cơ sở Dữ liệu & Transaction**:
   - `petcare/config.py`: Quản lý đường dẫn dự án độc lập với thư mục chạy.
   - `petcare/database/connection.py`: Mở kết nối, bật `PRAGMA foreign_keys = ON;`, cung cấp transaction context manager.
   - `petcare/database/schema.sql`: 10 bảng dữ liệu chuẩn hóa, khóa ngoại và chỉ mục.
   - `petcare/database/initialize.py`: Tạo bảng an toàn bằng `CREATE TABLE IF NOT EXISTS`, không xóa DB cũ.
   - `petcare/database/seed.py`: Dữ liệu mẫu an toàn (idempotent: chạy nhiều lần không nhân đôi dữ liệu).
2. **Lượt Dịch vụ, Hóa đơn & Doanh thu**:
   - `petcare/repositories/visit_repo.py` & `petcare/services/visit_service.py`: Quản lý các lượt dịch vụ chung, truy vấn lượt chưa thanh toán theo chủ.
   - `petcare/repositories/invoice_repo.py` & `petcare/services/invoice_service.py`: Lập hóa đơn, chống tính phí lặp (`visit_id UNIQUE`), thanh toán trực tiếp an toàn, bảo vệ hóa đơn paid, hủy hóa đơn unpaid giải phóng visit.
   - `petcare/repositories/report_repo.py` & `petcare/services/report_service.py`: Tính tổng doanh thu theo `paid_at`, số ca khám, thú cưng tiêm phòng, cơ cấu loài, top dịch vụ.
   - `petcare/ui/visits_view.py`, `petcare/ui/invoices_view.py`, `petcare/ui/revenue_view.py`.
3. **Tài liệu & Kiểm thử**:
   - `docs/billing_rules.md`: Quy tắc tài chính, tiền tệ và hóa đơn.
   - `docs/backup_restore.md`: Hướng dẫn sao lưu và phục hồi cơ sở dữ liệu.
   - `tests/test_invoice_service.py`, `tests/test_report_queries.py`.

---

## 2. Kết quả đạt được & Tự đánh giá

- Đảm bảo tính nhất quán tuyệt đối về tiền tệ và doanh thu: Một lượt dịch vụ chỉ tính tiền 1 lần; thanh toán 2 lần không nhân đôi doanh thu; hóa đơn paid được bảo vệ bất biến.
- Seed chạy lại nhiều lần không tạo trùng lặp dữ liệu.
- Toàn bộ unit tests đạt 100% tỷ lệ pass.
