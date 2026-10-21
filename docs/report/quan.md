# Báo cáo Cá nhân — Quân (docs/report/quan.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](final_report.md) và [dàn ý slide hiện hành](../slides/final_slides.md).


- **Họ và tên**: Quân
- **Vai trò**: Kỹ sư Quản lý Thú cưng & Tiêm chủng
- **Mục tiêu đóng góp**: 25% khối lượng công việc

---

## 1. Nhiệm vụ đảm nhiệm & Mã nguồn phụ trách

1. **Quản lý Thú cưng (Pets)**:
   - `petcare/repositories/pet_repo.py`: SQL cho bảng `pets`, tìm kiếm đa tiêu chí, kiểm tra lịch sử liên quan.
   - `petcare/services/pet_service.py`: Kiểm tra hợp lệ dữ liệu thú cưng (ngày sinh không ở tương lai, cân nặng >= 0, chủ sở hữu phải tồn tại và đang active). Bảo vệ thú cưng có lịch sử bằng cơ chế ngừng theo dõi (`active=0`). Chặn đổi chủ nếu đã có hóa đơn.
   - `petcare/ui/pets_view.py`: Giao diện danh sách thú cưng, lọc theo giống loài, tìm kiếm, form thêm/sửa modal.
2. **Quản lý Tiêm phòng & Lịch nhắc (Vaccinations)**:
   - `petcare/repositories/vaccination_repo.py`: SQL cho bảng `vaccinations`, truy vấn các mũi tiêm đến hạn trong 30 ngày, đánh dấu hoàn thành nhắc nhở.
   - `petcare/services/vaccination_service.py`: Ghi nhận mũi tiêm vaccine và tự động đồng bộ lượt dịch vụ trong cùng một transaction. Kiểm tra logic ngày tiêm và ngày hẹn tiêm nhắc lại.
   - `petcare/ui/vaccinations_view.py`: Giao diện lịch sử tiêm phòng và bảng theo dõi lịch nhắc đến hạn.
3. **Tài liệu & Kiểm thử**:
   - `docs/erd.md`: Sơ đồ thực thể quan hệ 10 bảng dữ liệu.
   - `docs/data_dictionary.md`: Từ điển dữ liệu chi tiết từng cột và ràng buộc.
   - `tests/test_pet_service.py`, `tests/test_vaccination_service.py`.

---

## 2. Kết quả đạt được & Tự đánh giá

- Hoàn thành đầy đủ các ràng buộc y tế về tiêm phòng và lịch nhắc vaccine.
- Bảo vệ toàn vẹn lịch sử thú cưng, ngăn chặn xóa nhầm khi đã có bệnh án.
- Unit tests đạt tỷ lệ thành công 100%.
