# Danh sách Kiểm tra Bàn giao (release_checklist.md)

Tài liệu này xác nhận tình trạng sẵn sàng bàn giao cho phiên bản **v1.0.0** của dự án PetCare Manager.

---

## 1. Kiểm tra Mã nguồn & Cấu trúc

- [x] Không còn màn hình nào dùng `PendingView` hay mô phỏng giả lập.
- [x] Không có câu lệnh SQL nào nằm trong callback giao diện UI.
- [x] Kiến trúc 3 tầng chuẩn hóa: UI -> Service -> Repository.
- [x] Mật khẩu được mã hóa an toàn bằng PBKDF2-HMAC-SHA256, không lưu plaintext.
- [x] Tiền tệ được lưu kiểu số nguyên VND.
- [x] Kích hoạt `PRAGMA foreign_keys = ON;` trên tất cả kết nối.
- [x] Bật ràng buộc `visit_id UNIQUE` trong `invoice_items` bảo đảm không tính tiền 2 lần.
- [x] Đường dẫn tệp sử dụng `pathlib.Path` tính từ vị trí dự án, chạy độc lập không phụ thuộc `cwd`.

---

## 2. Kiểm thử Tự động & Nghiệm thu

- [x] `python3 -m compileall -q main.py petcare tests`: 100% ĐẠT, không lỗi cú pháp.
- [x] `python3 -m unittest discover -s tests -v`: 34/34 tests ĐẠT (100% Success).
- [x] Kịch bản tích hợp Lan & Miu (`tests/test_integration_flow.py`): ĐẠT.
- [x] Kiểm thử khởi tạo và điều hướng giao diện (`tests/test_ui_navigation.py`): ĐẠT.
- [x] Chạy lặp lại `seed.py` 2 lần liên tiếp: ĐẠT, không tạo dữ liệu trùng (idempotent).
- [x] Chạy `initialize.py`: ĐẠT, không xóa hay reset database hiện tại.

---

## 3. An toàn Git & Môi trường Sạch

- [x] `.gitignore` bao gồm: `.venv/`, `__pycache__/`, `*.pyc`, `data/*.db`, `.DS_Store`.
- [x] Không đưa file cơ sở dữ liệu cá nhân hay thư mục `.venv` lên Git.
- [x] Không chứa mật khẩu thật hoặc khóa bí mật trong mã nguồn.
- [x] Tài khoản demo ghi rõ ràng trong `README.md`.

---

## 4. Tài liệu Bàn giao

- [x] `README.md`: Hướng dẫn cài đặt và chạy riêng cho Windows và macOS.
- [x] `CHANGELOG.md`: Nhật ký thay đổi v1.0.0.
- [x] `AGENTS.md`: Quy ước kỹ thuật và lệnh kiểm tra.
- [x] `docs/implementation_plan.md`: Kế hoạch 5 mốc hoàn thiện.
- [x] `docs/project_status.md`: Báo cáo trạng thái 100% hoàn thành.
- [x] `docs/architecture.md`: Kiến trúc hệ thống và luồng giao dịch.
- [x] `docs/erd.md`: Sơ đồ thực thể quan hệ 10 bảng dữ liệu.
- [x] `docs/billing_rules.md`: Toàn bộ quy tắc tính phí và bảo toàn doanh thu.
- [x] `docs/acceptance_tests.md`: 10 ca kiểm thử nghiệm thu.
- [x] `docs/demo_scenarios.md`: Kịch bản demo từng bước cho buổi bảo vệ.
- [x] `docs/backup_restore.md`: Hướng dẫn sao lưu và phục hồi dữ liệu SQLite.
- [x] `docs/test_results.md`: Báo cáo kết quả kiểm thử toàn diện.
- [x] `docs/scope.md`, `module_contracts.md`, `data_dictionary.md`, `user_guide.md`.
