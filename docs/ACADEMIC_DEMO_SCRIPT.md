# Kịch bản demo học thuật — 8–12 phút

**Tài khoản:** dùng mật khẩu tự chọn khi launcher nhắc; không hiển thị mật khẩu trên slide/log. `admin` chạy nghiệp vụ, `staff1` minh họa giới hạn quyền. Mọi dữ liệu là tổng hợp trong một QA database tmpfs.

## Bản trình bày chính

| Thời gian | Chuyển màn hình và thao tác | Kết quả cần chỉ ra |
|---|---|---|
| 0:00–1:00 | Mở dashboard, giới thiệu bài toán cửa hàng và stack Flask/Jinja/MySQL. Nêu đây là tenant demo dùng dữ liệu giả. | Dashboard và trạng thái cửa hàng; không có giao dịch tiền thật. |
| 1:00–2:00 | Vào Khách hàng → Thêm; nhập tên/số giả QA và lưu. Vào Thú cưng → Thêm; tạo hồ sơ mèo synthetic với giá, chưa có người mua. | Customer mới được lưu; pet có status available, chưa có buyer. |
| 2:00–3:00 | Vào Sản phẩm → Thêm; tạo SKU demo, tồn 0. Tạo nhà cung cấp. | Tồn đầu được ghi nhận qua ledger; product chưa có sẵn. |
| 3:00–4:00 | Purchasing → Tạo đơn; thêm 8 đơn vị SKU. Mở chi tiết; xác nhận trạng thái ordered và tồn vẫn 0. Nhận 3 rồi nhận 5 còn lại. | Trạng thái chuyển ordered → partially_received → received; stock 0→3→8; mỗi lần nhận có movement. |
| 4:00–6:00 | POS → thêm 2 sản phẩm và pet mới, chọn customer. Tạo invoice; mở hóa đơn, xác nhận thu tiền giả lập. | Invoice gắn customer + hai loại mặt hàng; sau pay, product còn 6 và pet chuyển sold/buyer gắn customer. Chỉ có thao tác trạng thái nội bộ, không payment gateway. |
| 6:00–7:00 | Trong chi tiết hóa đơn, hoàn một product unit với “nhận lại, có thể bán”. | Refund ledger là bản ghi riêng; stock trở lại 7, tổng hoàn 75.000 VND, doanh thu thuần 2.575.000 VND theo fixture này. Tiền hoàn thực tế phải thực hiện riêng ngoài app. |
| 7:00–8:00 | Reports → chọn kỳ tháng; đối chiếu transaction/refund và stock ledger. | Report đọc dữ liệu MySQL, có thể theo dõi lại product/invoice. |
| 8:00–9:00 | Users → Export data; nhập lại mật khẩu hiện tại và passphrase tạm; chờ job ready, tải file `.pcarexport`. | Worker QA xử lý và mã hóa export; passphrase không đưa vào file/báo cáo. |
| 9:00–10:00 | Dashboard → mở Assistant → “Bán chạy tuần này”. | Kết quả xếp hạng là query/service report từ MySQL tenant; không trình bày như suy luận LLM. |
| 10:00–11:00 | Thú cưng → Thêm; chọn synthetic photo; xem gợi ý Vision; apply. | Local demo mock trả lời cố định; người dùng phải review, chỉ field trống được điền và chưa lưu hồ sơ. |
| 11:00–12:00 | Đăng xuất; đăng nhập `staff1`; mở Khách hàng rồi thử `/users/`. Kết thúc với test/limitations. | Customer GET 200; route user admin trả 403. Nhắc 428 Python, 41 JS, 18 browser smoke/22 axe scans, 0 axe violations; production NO-GO. |

### Rehearsal đo được

Connected UI rehearsal chạy trên Flask thật + isolated MySQL + local workers: **14 bước PASS trong 17.76 giây** từ khi bắt đầu browser workflow tới DB reconciliation, không tính startup/reset. Đây là tốc độ automation headless, không phải thời lượng người thuyết trình. Bản 8–12 phút ở trên là khung có lời giải thích và chưa được stopwatch một presenter độc lập đo.

## Bản rút gọn 3–5 phút

1. Dashboard → giới thiệu dữ liệu giả và tenant (20 giây).
2. Mở product tồn 0 và PO → nhận hàng → chỉ ra stock/ledger (60 giây).
3. POS bán product + pet → pay → refund một đơn vị → report (100 giây).
4. Assistant top-products + Vision mock apply nhưng không save (60 giây).
5. Staff vào customers, bị chặn ở users; tóm tắt kiểm thử và giới hạn (40 giây).

Bản ngắn bỏ tạo hồ sơ/supplier mới và export worker để giữ nhịp; nên reset QA trước khi bắt đầu.

## Điểm reset và an toàn

- Chạy `scripts/demo/classroom.sh --target qa`; nhập `r` để khởi tạo lại sample seed sạch sau demo.
- Không dùng “delete all”, SQL drop thủ công hoặc schema `petcare_shop_dev`.
- Dùng tên/phone/email synthetic; không nhập PII thật.
- Chỉ trình bày refund giả lập; app ghi ledger, không gửi tiền.

## Fallback khi lỗi

- **DB:** kiểm `docker info`, launcher logs và `/readyz`; dừng tại đó, không đổi sang dev DB. Có thể dùng screenshot trong `docs/assets/phase62` để trình bày kiến trúc.
- **Browser automation:** app dùng được bằng browser thường; chỉ automation bị bỏ qua. Nếu UI login hỏng thì chuyển slide/report và đánh dấu demo live FAIL.
- **Worker:** kiểm `/workersz`; bỏ phần export nếu worker không healthy, không tự đánh dấu export ready.
- **Vision mock:** bỏ phần mock; giải thích Vision là review-only và provider thật chưa test. Không bật real endpoint.
- **Internet:** runtime demo không cần provider ngoài sau khi image/packages đã cache. Nếu cần pull chưa có cache, hoãn demo hoặc trình bày tài liệu/screenshot.
