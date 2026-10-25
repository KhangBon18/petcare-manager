# Demo nhanh — cửa hàng thú cưng

Kịch bản bảo vệ ngắn và lệnh tổng duyệt mới nhất: [DEMO_SCRIPT.md](../DEMO_SCRIPT.md). Ma trận nghiệm thu: [Phase 4](phase4_acceptance.md). Các tình huống bên dưới dùng để tham khảo chi tiết.


## Chuẩn bị trước buổi bảo vệ

Dùng database local có hậu tố `_dev`/`_test`; schema hiện có **20 bảng**. Với database mới, chạy initialize một lần. Trước mỗi buổi demo, kích hoạt venv rồi chạy:

```sh
python -m petcare.database.seed
python run.py
```

Mở http://127.0.0.1:5055, đăng nhập store `main`, admin / Admin@123 (hoặc staff1 / Staff@123). Seed giữ mật khẩu đã đổi, dữ liệu đã chỉnh sửa và ảnh hợp lệ; bổ sung hồ sơ/ảnh còn thiếu. Chỉ đúng các hóa đơn có marker demo được đưa về mốc ngày tương đối; hóa đơn đã hủy không mở lại và hóa đơn đã thanh toán không trừ tồn lần nữa. Seed không khôi phục thú cưng đã bán từ lần demo trước.

Bộ seed chuẩn: **12 khách, 22 sản phẩm, 74 thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster), 68 ảnh, 7 hóa đơn demo**. Dev sau Phase 2 có 14 khách vì giữ thêm hồ sơ cũ; các số lượng còn lại khớp bộ chuẩn. Không có ảnh sản phẩm seed sẵn: thẻ có biểu tượng thay thế hoặc ảnh do admin tải lên. Hồ sơ và ảnh là dữ liệu hư cấu, không chạy seed trên database thật.

## Kịch bản 5–7 phút

1. **Tổng quan:** chỉ doanh thu hôm nay và khối 7 ngày qua; mở báo cáo từ dashboard. Ngày giao dịch luôn tương đối với lần chạy seed mới nhất.
2. **Danh mục:** mở Sản phẩm để xem mã/giá/tồn/ngưỡng nhập; mở Thú cưng để xem ảnh, bộ lọc và từng cá thể.
3. **POS:** Hóa đơn → Lập hóa đơn. Bên trái tìm `FOOD-001`, bấm thẻ hai lần; tìm `ACC-001`, thêm một; chuyển bộ lọc Thú cưng và chọn Miu `PET-001` nếu còn sẵn sàng. Thú cưng chỉ có số lượng 1; tổng theo giá seed mới là 2.250.000 VND. Nếu hồ sơ/giá đã được chỉnh sửa, đối chiếu giá đang hiển thị thay vì giả định số mẫu.
4. **Khách mới:** bấm **+ Thêm nhanh**, nhập khách hư cấu/số điện thoại hợp lệ và lưu. Khách được chọn ngay; mặt hàng, số lượng và tổng tiền vẫn giữ. Có thể đóng bằng Esc và tiếp tục đơn.
5. **Tạo & thu tiền:** ghi nhận tồn hiện tại, tạo hóa đơn unpaid (chưa trừ kho), rồi thanh toán. Tồn giảm đúng; thú cưng được gắn người mua. Gửi lại thanh toán không ghi doanh thu lần hai. Khi demo lặp, chọn cá thể còn sẵn sàng khác hoặc dùng database test riêng; không reset dữ liệu dev để bán lại Miu.
6. **Trợ lý:** hỏi “Hôm nay còn mèo nào?”, “Tìm mèo lông trắng dưới 3 triệu”, “Sản phẩm nào sắp hết?” và “Doanh thu hôm nay là bao nhiêu?”. Enter gửi, Esc đóng; chế độ local truy vấn MySQL không cần API key.
7. **Tìm bằng ảnh:** chọn một ảnh hồ sơ trong 68 ảnh mẫu hoặc camera nếu được cấp quyền. Chờ trạng thái xử lý; kết quả là xếp hạng màu/bố cục tham khảo, chưa phải nhận diện vật thể bằng mô hình.

AI tạo sinh/Vision trực tuyến chỉ hoạt động khi cấu hình endpoint phù hợp; `AI_VISION_ENABLED=1` chỉ dùng với endpoint hỗ trợ vision. Chưa cấu hình API vẫn demo được trợ lý local và xếp hạng ảnh. Xuất dữ liệu dùng worker có sẵn của dự án; UI hiển thị trạng thái chờ/đang xử lý/hoàn tất rõ ràng.


## Điểm nhấn Phase 3 (thêm 3–4 phút)

- Trợ lý: hỏi “Tìm mèo Mây dưới 3 triệu”, kiểm tra card có ảnh/giá, bấm **Mở hồ sơ**. Hỏi “Hôm nay còn mèo nào?” để đối chiếu tổng từ toàn danh mục.
- Dashboard: xem biểu đồ 7 ngày, tăng/giảm kỳ trước và bản tin Python. Mở gợi ý nhập lại; mặt hàng chưa bán có fallback theo ngưỡng.
- Sản phẩm: tìm `FOOD-003`, mở hồ sơ để xem số lượng đã bán 14/30 ngày, tốc độ, ngày tồn và công thức. Số liệu phụ thuộc các giao dịch đang có.
- Báo cáo: chọn 7 ngày, mở bảng ngày/chi tiết, tải Excel và đối chiếu tổng giữa các sheet với màn hình; chọn **In / Lưu PDF** để xem bản gọn, có cả chi tiết.
- Thú cưng: vào form thêm, nhập tay loài trước rồi chọn ảnh mẫu; áp dụng gợi ý và xác nhận loài đã nhập không đổi. Hủy form sau demo nếu không muốn lưu hồ sơ thử.
- Tìm ảnh: chọn `assets/demo/pets/may-calico.png`, lọc Mèo/Đang bán, xem điểm màu/cấu trúc/thuộc tính và nhãn lý do. Có thể dùng trạng thái khác để đối chiếu lịch sử.
- Không cần API key để demo local; LLM/Vision trực tuyến chỉ hoạt động khi có endpoint/model phù hợp. Các ca provider lỗi đã có regression fallback.
