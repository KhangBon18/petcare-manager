# Petcare Manager — tổng quan dự án

## Bài toán

Cửa hàng thú cưng thường theo dõi khách, vật nuôi, hàng hóa, nhập kho và giao dịch ở nhiều bảng tính hoặc công cụ rời rạc. Điều này khiến tồn kho khó đối chiếu và lịch sử giao dịch dễ bị mất liên kết. Petcare Manager là ứng dụng web quản lý cửa hàng nhỏ theo tenant, gom các hồ sơ và nghiệp vụ bán lẻ vào một quy trình.

## Mục tiêu học tập

- Xây dựng ứng dụng Python web bằng Flask.
- Tách xử lý HTTP, quy tắc nghiệp vụ, truy vấn lưu trữ.
- Thiết kế MySQL schema có khóa ngoại, ràng buộc và giao dịch.
- Áp dụng xác thực, phân quyền vai trò và tenant scoping.
- Kiểm tra bằng unit, integration và browser E2E tests.

## Người dùng

- **Owner/admin**: quản lý tenant, người dùng, catalog, nhập hàng, báo cáo, xuất dữ liệu và các thao tác quản trị.
- **Staff**: thực hiện nghiệp vụ cửa hàng được cấp; route quản trị bị giới hạn theo permission.
- **Người quản trị hệ thống**: cấu hình triển khai và worker ngoài luồng người dùng.

## Chức năng hiện có

- Đăng nhập, đăng ký/thiết lập cửa hàng, invitation, xác minh email và đặt lại mật khẩu qua outbox.
- Hồ sơ khách hàng, hồ sơ thú cưng và ảnh; tìm thú cưng tương tự bằng descriptor cục bộ.
- Sản phẩm, tồn kho và stock movement ledger.
- Nhà cung cấp, purchase order, nhận hàng nhiều lần, hủy phần chưa nhận.
- POS tạo hóa đơn; chỉ khi thanh toán mới trừ stock/đánh dấu thú cưng đã bán.
- Refund ghi ledger riêng; tùy disposition có thể nhập lại stock, cách ly hoặc không trả hàng.
- Báo cáo doanh thu/tồn kho và export XLSX.
- Tenant export mã hóa, xử lý qua worker.
- Assistant với truy vấn quy tắc/service và dữ liệu tenant; AI provider là tích hợp tùy chọn.
- Vision gợi ý ảnh theo local feature pipeline hoặc endpoint cấu hình; luôn cần người dùng xem và áp dụng.

## Công nghệ

Python 3.11+, Flask, Jinja templates, JavaScript module scripts, MySQL 8/InnoDB, Playwright, unittest, pytest-compatible web tests, Bandit, pip-audit và Docker Compose. Runtime/browser dependency snapshots nằm trong `requirements.lock` và `requirements-browser.lock`.

## Phạm vi và trạng thái

Đây là ứng dụng học thuật đang phát triển, không phải hệ thống đã chứng nhận production. Bản demo Phase 6.2 dùng dữ liệu tổng hợp, database tạm, mail/export workers local và Vision mock. Không có giao dịch tiền thật. Live SMTP, S3, payment, AI provider quality/cost, native screen reader và browser zoom 200% chưa được kiểm chứng.

## Tài liệu liên quan

- [Kiến trúc Python](ACADEMIC_ARCHITECTURE.md)
- [Database ERD](ACADEMIC_DATABASE_ERD.md)
- [Kịch bản demo](ACADEMIC_DEMO_SCRIPT.md)
- [Q&A bảo vệ](ACADEMIC_DEFENSE_QA.md)
- [Giới hạn đã biết](FINAL_KNOWN_LIMITATIONS.md)
