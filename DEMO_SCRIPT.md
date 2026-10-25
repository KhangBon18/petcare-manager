# PetCare Manager — kịch bản bảo vệ 8 phút

## Chuẩn bị trước buổi bảo vệ

Tại thư mục dự án, kích hoạt `.venv`, cấu hình `.env` với MySQL local, database `_dev`, `SECRET_KEY` cố định và ảnh local. Chỉ khi chưa có bộ demo: chạy `python -m petcare.database.initialize`, rồi `python -m petcare.database.seed`. Seed đầy đủ có thể mất lâu hơn 5 giây; làm trước buổi trình bày để bổ sung ảnh thiếu. Không reset database hoặc volume Docker.

Mở hai terminal có cùng `.env`:

```sh
# Terminal 1 — giữ chạy suốt buổi
python run.py
```

```sh
# Terminal 2 — ngay trước khi lên trình bày
python run.py prepare-demo
```

Chỉ bắt đầu khi thấy **SẴN SÀNG** và exit code 0. Lệnh kiểm tra MySQL/schema, quyền Admin/Staff, tồn cho đơn mẫu, thú cưng có ảnh và `/readyz` của đúng server/database; cập nhật ngày cho đúng 7 marker giao dịch mẫu đã thu. Có `--json` cho kiểm tra tự động. Ngân sách chạy 4,7 giây; khi quá hạn hoặc có lỗi trả exit 1, không báo sẵn sàng. Đo trên máy nghiệm thu: 0,76 / 0,67 giây kể cả khởi động Python; đây là phép đo, không bảo đảm cho mọi máy.

Mở **http://127.0.0.1:5055**, cửa hàng `main`, chọn Tiếng Việt. Tài khoản seed nếu chưa đổi: `admin / Admin@123`, `staff1 / Staff@123`. Preflight không đặt lại mật khẩu. Ghi lại **mã thú cưng và tổng tiền** mà lệnh vừa in; đừng ghi nhớ số dashboard vì ngày và giao dịch thay đổi.

## Trình bày theo thứ tự

| Thời gian | Thao tác | Ý chính cần nói / kết quả cần thấy |
|---|---|---|
| 0:00–0:45 | Đăng nhập Admin, mở Tổng quan | “Python + Flask + MySQL quản lý bán hàng; thú cưng là từng cá thể.” Chỉ doanh thu hôm nay, biểu đồ 7 ngày và bản tin tự động. |
| 0:45–1:30 | Đăng xuất, đăng nhập Staff | Staff có bán hàng/báo cáo; menu quản trị tài khoản không có. Nếu cần minh họa, truy cập `/users/` nhận từ chối quyền. |
| 1:30–3:30 | Hóa đơn → Lập hóa đơn | Tìm `FOOD-001`, chọn số lượng **2**; `ACC-001` số lượng **1**; thêm **mã thú cưng preflight vừa chọn**, số lượng luôn **1**. Bấm **+ Thêm nhanh**, nhập khách hư cấu và số điện thoại chưa dùng (ví dụ `0000099911`); thấy khách được chọn, giỏ hàng vẫn còn. Thêm ghi chú rồi tạo hóa đơn. |
| 3:30–4:15 | Kiểm tra chi tiết → Xác nhận thanh toán | Trước thu tiền: trạng thái chưa thanh toán, chưa trừ tồn/đổi chủ. Tổng mẫu với Miu `PET-001` và giá seed là **2.250.000 VND**. Xác nhận đã thu: trạng thái Đã thanh toán, nút thanh toán biến mất. “Server tính tiền và khóa dòng trong một transaction; bấm lặp không trừ kho lần hai.” |
| 4:15–5:00 | Tổng quan → Ưu tiên bổ sung tồn kho → mở sản phẩm | Sau đơn mẫu, `ACC-001` chạm ngưỡng: tồn từ 5 xuống 4, gợi ý nhập 2 nếu dữ liệu ban đầu còn nguyên. Chỉ công thức tốc độ = lượng bán paid / 14 hoặc 30 ngày, ngày tồn = tồn / tốc độ; hàng mới dùng ngưỡng nhập lại. Đây là gợi ý, không tự nhập kho. |
| 5:00–6:00 | Hỏi trợ lý, nhập lần lượt các câu bên dưới | Đếm toàn danh mục, card có ảnh/giá/trạng thái, nút mở hồ sơ. “Tra cứu local vẫn hoạt động khi không có API; LLM là tùy chọn.” Enter gửi, Esc đóng. |
| 6:00–7:00 | Tìm bằng ảnh → Loài `Mèo`, trạng thái `Đang bán` | Chọn `assets/demo/pets/may-calico.png` → Tìm hồ sơ tương tự. Mây đứng đầu với ảnh seed còn nguyên. Chỉ thanh điểm và lý do màu sắc/cấu trúc/thuộc tính, mở hồ sơ. Điểm là xếp hạng tham khảo, không phải xác suất nhận diện. |
| 7:00–8:00 | Báo cáo → 7 ngày → Xuất Excel → In / Lưu PDF | Chỉ doanh thu/so sánh kỳ trước/bản tin; mở Excel gồm 4 sheet và đối chiếu tổng đang xem. File dùng cùng snapshot đã ký, hiệu lực 15 phút. In xem trước có bảng chi tiết; chọn Lưu PDF hoặc hủy hộp thoại khi chỉ demo. |

Câu hỏi trợ lý để copy:

```text
Hôm nay còn mèo nào?
Tìm mèo lông trắng dưới 3 triệu
Sản phẩm nào sắp hết?
Doanh thu hôm nay?
```

Câu đầu phải trả danh sách mèo đang bán. Câu thứ hai lọc cả màu và giá; thú đã bán không còn trong card đang bán. Với dữ liệu chuẩn, Mây/Mực/Sữa phù hợp câu thứ hai; Miu vừa bán sẽ không xuất hiện. Số kết quả thay đổi theo dữ liệu thực tế.

## Xử lý nhanh khi có sự cố

- **MySQL/web chưa sẵn sàng:** `docker compose up -d mysql` nếu dùng MySQL Compose; giữ terminal web chạy rồi gọi lại preflight. Chỉ chạy một server trên cổng 5055. Nếu báo cấu hình/database khác, khởi động lại đúng server và `.env`.
- **Thiếu marker/ảnh:** chạy seed đầy đủ trước buổi bảo vệ rồi kiểm tra lại. Preflight chỉ kiểm tra ảnh đã gắn, không tạo ảnh hoặc nạp lại dữ liệu trong 5 giây.
- **Đã demo một lần:** không đưa thú đã bán trở lại kho. Chạy preflight để lấy cá thể tiếp theo/tổng mới. Nếu thiếu sản phẩm, Admin nhập/điều chỉnh kho qua UI với lý do. Không reset dữ liệu để diễn lại.
- **Validation:** nhập lại trường được báo lỗi; dữ liệu hợp lệ trong form/giỏ hàng vẫn giữ. Nếu để form mở quá lâu và CSRF hết hạn, mở form mới trước khi diễn; không tắt CSRF.
- **Mất mạng/không có API key:** tiếp tục tra cứu và tìm ảnh local; không cần cấu hình provider để bảo vệ. Không tuyên bố đã kết nối LLM trực tuyến khi chưa cấu hình.
- **Excel hết hạn:** tải lại trang báo cáo, chọn lại kỳ rồi xuất; đối chiếu theo thời điểm chốt trên màn hình. Không so file cũ với màn hình đã có giao dịch mới.

Kiểm thử tranh chấp đơn vị tồn cuối cùng và thanh toán lặp đã chạy tự động trên MySQL `_test` riêng; không cần tạo tranh chấp thủ công trong buổi demo. Phạm vi bảo vệ là MVP local; email/cloud/triển khai production không nằm trong kịch bản này.
