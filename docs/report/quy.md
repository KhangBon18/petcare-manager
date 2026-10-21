# Báo cáo Cá nhân — Quý (docs/report/quy.md)

> **Lưu ý về phiên bản:** Nội dung dưới đây ghi nhận đóng góp cho bản desktop phòng khám trước khi đổi yêu cầu. Cần tác giả rà soát và viết lại theo web MySQL/cửa hàng trước khi nộp; xem [báo cáo tổng kết hiện hành](final_report.md) và [dàn ý slide hiện hành](../slides/final_slides.md).


- **Họ và tên**: Quý
- **Vai trò**: Kỹ sư Nghiệp vụ Y tế & Báo cáo Hoạt động
- **Mục tiêu đóng góp**: 25% khối lượng công việc

---

## 1. Nhiệm vụ đảm nhiệm & Mã nguồn phụ trách

1. **Danh mục Dịch vụ & Giá (Services)**:
   - `petcare/repositories/catalog_repo.py`: SQL cho bảng `services`.
   - `petcare/services/catalog_service.py`: Kiểm tra giá >= 0, kiểm tra quyền Admin khi đổi giá và thêm dịch vụ mới; Staff chỉ có quyền xem.
   - `petcare/ui/services_view.py`: Giao diện danh mục dịch vụ và phân quyền thao tác.
2. **Khám bệnh & Lịch hẹn (Examinations & Appointments)**:
   - `petcare/repositories/exam_repo.py` & `petcare/services/exam_service.py`: Ghi nhận ca khám bệnh, triệu chứng, chẩn đoán, thuốc và liên kết lượt dịch vụ trong cùng transaction.
   - `petcare/repositories/appointment_repo.py` & `petcare/services/appointment_service.py`: Quản lý đặt lịch hẹn, cập nhật trạng thái; bảo đảm lịch hẹn không tự động sinh phí trước.
   - `petcare/ui/examinations_view.py`, `petcare/ui/appointments_view.py`.
3. **Báo cáo Thống kê & Nghiệm thu**:
   - `petcare/ui/reports_view.py`: Bảng điều khiển thống kê tổng quan (ghép số liệu hoạt động và nhúng phần doanh thu).
   - `docs/acceptance_tests.md`: 10 ca kiểm thử nghiệm thu chi tiết.
   - `docs/demo_scenarios.md`: Kịch bản demo từng bước bảo vệ đồ án.
   - `tests/test_catalog_service.py`, `tests/test_exam_service.py`, `tests/test_appointment_service.py`.

---

## 2. Kết quả đạt được & Tự đánh giá

- Triển khai thành công logic giao dịch kép cho khám bệnh, không để phát sinh lỗi lệch lượt dịch vụ.
- Đảm bảo lịch hẹn không phát sinh chi phí trước.
- Toàn bộ unit tests đạt 100% tỷ lệ pass.
