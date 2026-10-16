# Theo dõi Nhiệm vụ (pending_tasks.md)

Toàn bộ các nhiệm vụ thuộc phạm vi bắt buộc của đồ án PetCare Manager đã được hoàn thành đầy đủ.

Chi tiết kế hoạch triển khai, trạng thái nghiệm thu và kết quả kiểm thử được lưu trữ tại:
- [docs/implementation_plan.md](implementation_plan.md): Kế hoạch 5 mốc triển khai và tiêu chí nghiệm thu.
- [docs/project_status.md](project_status.md): Báo cáo trạng thái hoàn thành 100% các mốc.
- [docs/acceptance_tests.md](acceptance_tests.md): 10 ca kiểm thử nghiệm thu hệ thống.
- [docs/test_results.md](test_results.md): Kết quả kiểm thử tự động (34/34 tests đạt).

## Danh mục Đề xuất Nâng cao (Giai đoạn tiếp theo)
1. Thêm biểu đồ trực quan hóa doanh thu và số ca khám bằng `matplotlib` (chỉ triển khai sau khi nghiệm thu v1.0.0).
2. Quản lý lưu trữ ảnh đại diện cho từng thú cưng (`assets/pets/`).
3. Xuất hóa đơn ra tệp PDF hoặc in ấn phiếu tiếp nhận bệnh án.
4. Tích hợp gửi thông báo SMS/Email tự động khi lịch tiêm phòng đến hạn.
