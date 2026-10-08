# Nhiệm vụ chưa triển khai

Tài liệu này là danh sách giao việc của bộ khung, không xác nhận task đã hoàn thành và không thay thế issue của nhóm. Mã và đầu ra task tuần 1 lấy từ bảng tiến độ của nhóm; không tự gán mã mới. Chi tiết thiết kế và chủ sở hữu từng file xem [REPO_GUIDE.md](../REPO_GUIDE.md).

| Thành viên | Nhiệm vụ tiếp theo |
|---|---|
| Khang | Chốt hợp đồng module tại K02; xây `security.py`, đăng nhập/phiên/quyền, tài khoản và chủ nuôi qua UI/service/repository; bổ sung theme và hồ sơ tổng hợp khi có API. |
| Quân | Xây UI/service/repository thú cưng và tiêm; kiểm tra ngày, cân nặng, lịch sử; đóng góp ERD, từ điển dữ liệu và query số lượng. |
| Quý | Xây danh mục dịch vụ, khám và lịch hẹn qua UI/service/repository; ghép thống kê; viết ca nghiệm thu và kịch bản demo. |
| Nhàn | Xây connection/transaction, schema, initialize không xóa dữ liệu và seed lặp an toàn; API lượt dịch vụ, hóa đơn và doanh thu; quy tắc tiền, sao lưu/phục hồi. |
| Cả nhóm | Review schema/API, bổ sung unittest dùng DB tạm; thử trên Windows/macOS và thống nhất phiên bản Python. |

`app.py` hiện thuộc phần bộ khung Khang; `config.py` đã có đường dẫn để Nhàn tiếp tục tích hợp. `common.py` chỉ có Frame thông báo, chưa có widget nghiệp vụ. `revenue_view.py` sau này nhúng trong `reports_view.py`, không mở root riêng.

Chưa tạo các module nghiệp vụ, `schema.sql`, `initialize.py`, `seed.py` và test nghiệp vụ. Khi làm task, tạo đúng tên file trong REPO_GUIDE và cập nhật tài liệu liên quan; không trả về thành công giả.

Các tài liệu còn chờ đầu ra thực tế: `scope.md`, `module_contracts.md`, `architecture.md` (Khang); `erd.md`, `data_dictionary.md` (Quân tổng hợp); `billing_rules.md`, `backup_restore.md` (Nhàn); `acceptance_tests.md`, `demo_scenarios.md` (Quý); `release_checklist.md`, `user_guide.md` (cả nhóm). Mỗi người viết phần của mình trong `report/` và `slides/`; Khang ghép báo cáo, Nhàn ghép slide ở tuần 5. Thư mục được giữ bằng `.gitkeep`, chưa tạo nội dung giả cho bản nộp.
