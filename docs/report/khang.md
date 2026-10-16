# Báo cáo Cá nhân — Khang (docs/report/khang.md)

- **Họ và tên**: Khang
- **Vai trò**: Trưởng nhóm điều phối, Kỹ sư Kiến trúc & Bảo mật
- **Mục tiêu đóng góp**: 25% khối lượng công việc

---

## 1. Nhiệm vụ đảm nhiệm & Mã nguồn phụ trách

1. **Bộ khung ứng dụng & Điều phối**:
   - `main.py`: Điểm khởi chạy duy nhất của chương trình.
   - `petcare/app.py`: Bộ điều khiển `PetCareApp`, một `tk.Tk` root duy nhất, quản lý phiên đăng nhập và điều hướng chuyển đổi Frame.
2. **Bảo mật & Xác thực**:
   - `petcare/security.py`: Triển khai hàm băm mật khẩu PBKDF2-HMAC-SHA256 với 100.000 vòng lặp và salt ngẫu nhiên 16 bytes. Hàm kiểm tra so sánh an toàn `compare_digest`.
   - `petcare/repositories/user_repo.py`: SQL có tham số cho bảng `users`.
   - `petcare/services/auth_service.py`: Xác thực đăng nhập, sinh `AuthSession`, kiểm tra phân quyền Admin/Nhân viên, bảo vệ Admin cuối cùng.
3. **Chủ nuôi & Hồ sơ Tổng hợp**:
   - `petcare/repositories/owner_repo.py` & `petcare/services/owner_service.py`: CRUD chủ nuôi, kiểm tra định dạng tên, SĐT, địa chỉ; cơ chế chuyển sang `deactivated` bảo toàn lịch sử.
   - `petcare/ui/login_view.py`, `petcare/ui/users_view.py`, `petcare/ui/owners_view.py`.
   - `petcare/ui/pet_profile_view.py`: Màn hình hồ sơ bệnh án tổng hợp 4 tab (Khám, Tiêm, Hẹn, Dịch vụ & Chi phí).
   - `petcare/ui/theme.py`: Hệ thống màu sắc, kiểu dáng ttk cho toàn bộ ứng dụng.
4. **Kiểm thử đảm nhiệm**:
   - `tests/test_auth_service.py`, `tests/test_owner_service.py`, `tests/test_ui_navigation.py`.

---

## 2. Kết quả đạt được & Tự đánh giá

- Hoàn thành 100% các chức năng được phân công theo đúng cam kết trong `REPO_GUIDE.md`.
- Toàn bộ unit tests do Khang phụ trách đạt 100% tỷ lệ pass.
- Đảm bảo ứng dụng chạy mượt mà, không giật lag, không lỗi rò rỉ giao dịch.
