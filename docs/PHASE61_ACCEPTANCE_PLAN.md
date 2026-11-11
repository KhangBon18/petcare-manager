# Phase 6.1 — kế hoạch nghiệm thu project Python

Mục tiêu là xác nhận Petcare Manager chạy ổn định như project web Flask/Jinja/MySQL hiện có và các luồng cửa hàng chính phù hợp để trình bày trong môn học. Đây là kế hoạch cho lượt acceptance tiếp theo; checklist bên dưới chưa được đánh dấu hoàn thành.

## Cổng an toàn trước khi chạy

- Dùng MySQL mới, riêng cho QA, với `DB_NAME` và `PETCARE_TEST_DB_NAME` trùng nhau và kết thúc bằng `_test`. Ưu tiên `compose.qa-test.yml` (tmpfs, project name riêng).
- Dùng thư mục riêng trong `/tmp` cho pet/product images, export và browser artifacts. Xác nhận `/healthz=200`, `/readyz=200` trước khi mở trình duyệt.
- Để AI provider, Vision thật, SMTP và S3 tắt. Vision chỉ dùng mock loopback rõ ràng. Không kết nối, seed, migrate hoặc ghi vào `petcare_shop_dev`/production.
- Không dùng dữ liệu khách hàng thật. Tạo dữ liệu tổng hợp mới và lưu bằng chứng không chứa mật khẩu, token hoặc credential.
- Ghi kết quả từng mục là `PASS`, `FAIL`, `BLOCKED` hoặc `NOT TESTED`; đính kèm lệnh, route, screenshot/log đã làm sạch và các kiểm tra DB phù hợp.

## Checklist nghiệm thu

### 1. Cài đặt sạch và khởi động

- Tạo virtualenv sạch với Python 3.11, 3.12 hoặc 3.13; cài runtime/browser dependencies theo `requirements.txt`, `requirements.lock` và `requirements-browser.lock`.
- Cấu hình biến môi trường local cho QA, khởi động bằng `python run.py`; xác nhận log không lộ secret và tiến trình dừng sạch.
- **Đạt khi:** dependency cài không lỗi, `pip check` sạch, app khởi động được và chỉ lắng nghe địa chỉ/port dự kiến.

### 2. Khởi tạo database QA

- Tạo một Compose project mới với `compose.qa-test.yml`; xác nhận database name có hậu tố `_test`, MySQL chạy trong tmpfs và app user chỉ kết nối schema đó.
- Chạy `python -m petcare.database.initialize`, sau đó seed dữ liệu demo QA bằng `python -m petcare.database.seed`.
- Kiểm tra migration marker, bảng/cột cần thiết, `/healthz` và `/readyz`; dừng đúng Compose project sau khi ghi nhận.
- **Đạt khi:** initializer chạy lặp lại an toàn trên schema QA; không có DDL/DML ngoài schema QA.

### 3. Đăng nhập, vai trò và quyền

- Kiểm tra admin/staff login/logout, CSRF cho POST, session hết hiệu lực sau đổi mật khẩu hoặc khóa membership, refresh role và lỗi đăng nhập.
- Kiểm tra route admin-only, route staff được phép, tenant switching/isolation và truy cập trực tiếp URL bị cấm.
- **Đạt khi:** UI và HTTP status khớp quyền server; không thể đọc/ghi dữ liệu tenant khác hoặc vượt quyền bằng cách sửa payload.

### 4. Khách hàng và thú cưng

- Tạo, tìm, sửa, deactivate/reactivate khách hàng; tạo/sửa thú cưng bán lẻ và gắn khách mua qua luồng hóa đơn.
- Kiểm tra dữ liệu rỗng, giá trị sai, số điện thoại, ảnh riêng tư, phân trang thú cưng đã mua và phục hồi form sau lỗi.
- **Đạt khi:** quan hệ khách hàng/thú cưng và trạng thái lưu đúng trong QA DB; ảnh riêng tư không truy cập trực tiếp nếu chưa được cấp quyền.

### 5. Sản phẩm và tồn kho

- Tạo/sửa/tìm sản phẩm; thử số lượng rỗng, âm, quá giới hạn, code trùng và trạng thái inactive.
- Điều chỉnh tăng/giảm tồn có lý do; đối chiếu `stock_movements`, số dư và gợi ý restock.
- **Đạt khi:** tồn không âm, lỗi không ghi dở transaction, ledger khớp số tồn và sản phẩm không hoạt động không bán được.

### 6. POS, hóa đơn và hoàn tiền

- Kiểm tra giỏ rỗng/đúng/sai, estimate phía UI, tạo hóa đơn, thanh toán, hóa đơn đã trả, hủy unpaid, thanh toán lặp và lỗi giữa transaction.
- Chạy refund một phần/toàn phần, vượt số tiền, retry cùng idempotency key và kiểm tra ledger/tồn kho.
- **Đạt khi:** server tính tổng; thanh toán/hoàn tiền nguyên tử và idempotent theo hợp đồng; dữ liệu/stock không đổi khi giao dịch thất bại. Không dùng payment gateway thật.

### 7. Mua hàng

- Tạo PO hợp lệ; kiểm tra line trùng/sai số lượng; nhận một phần rồi nhận đủ; hủy order còn được phép; thử over-receive, nhận trùng, nhận/hủy order đóng và rollback.
- Đối chiếu trạng thái PO, `received_qty`, tồn kho, stock movements, receipt request/audit và tính nhất quán sau lỗi.
- **Đạt khi:** các state transition đúng quy tắc hiện tại; retry không nhận hàng hai lần; transaction rollback toàn bộ khi có lỗi.

### 8. Báo cáo và tổng quan vận hành

- Thử kỳ mặc định/custom range, boundary ngày, lọc sản phẩm, XLSX và UI rỗng/lỗi.
- So sánh report với service/DB QA; trong tổng quan, xác nhận restock, PO đang xử lý và top products của 7 ngày là ba nguồn riêng biệt.
- **Đạt khi:** kỳ ngày, tiền tệ và tenant khớp dữ liệu nguồn; tổng quan ghi rõ giới hạn/nguồn, không nhầm top products với tổng doanh thu.

### 9. Assistant

- Thử các intent hỗ trợ bằng tiếng Việt/Anh, câu mơ hồ, câu ngoài phạm vi, khoảng ngày không hỗ trợ, lỗi một nguồn dữ liệu, payload tenant giả mạo và role staff.
- Xác nhận output đọc dữ liệu tenant hiện tại qua services hiện có, link cùng origin/đúng record và không gọi provider.
- **Đạt khi:** staff không nhận purchasing overview; câu trả lời lỗi không lộ exception/secret; không có SQL, mutation hoặc hành động tự động phát sinh từ prompt.

### 10. Vision mock demonstration

- Dùng browser flow với mock loopback đã bật rõ ràng; thử ảnh hợp lệ/không hợp lệ, provider timeout/malformed, retry, dismiss và apply vào ô còn trống.
- Xác nhận giá trị người dùng đã nhập không bị ghi đè và gợi ý không tự lưu.
- **Đạt khi:** UI hiển thị trạng thái provider/mock trung thực, lỗi có thể phục hồi, không có ảnh/dữ liệu gửi ra ngoài. Đây không phải đánh giá độ chính xác model.

### 11. Responsive và accessibility

- Chạy tối thiểu viewport 320, 390, 768, 820, 1024 và 1440 px trên dashboard, customer/pet, product, POS, purchasing, reports và assistant.
- Kiểm keyboard-only, focus order/visible focus, labels, dialog/status announcement và axe; kiểm zoom 200% thật, screen reader và ít nhất một browser ngoài Chromium nếu môi trường cho phép.
- **Đạt khi:** thao tác chính vẫn dùng được, không có tràn/clipping/blocker; mọi axe incomplete còn lại được xem thủ công hoặc ghi lý do.

### 12. Lỗi và phục hồi

- Gây lỗi có kiểm soát trên QA: mất kết nối DB, 403/CSRF, 404, 429, provider mock timeout, upload sai, export fail và POST network retry.
- Kiểm tra loading/empty/error/success feedback, retry an toàn, dữ liệu form còn cần thiết và log không chứa credential/PII nhạy cảm.
- **Đạt khi:** không có traceback/500 ngoài dự kiến, thao tác retry không nhân đôi ghi dữ liệu và app hồi phục sau khi dịch vụ QA trở lại.

### 13. Dữ liệu demo và hành trình trình bày

- Nạp seed demo trên QA, không đưa mật khẩu demo vào tài liệu công khai. Tạo một cửa hàng tổng hợp với supplier, sản phẩm, khách hàng và thú cưng bán lẻ.
- Hành trình đề xuất: admin tạo sản phẩm/PO → nhận một phần và nhận đủ → staff tạo khách hàng/hóa đơn/thanh toán → kiểm report → admin xem operations overview → thực hiện hoàn tiền QA và đối chiếu tồn/ledger.
- Thu ảnh chụp đã làm sạch và truy vấn/record IDs tổng hợp để đối chiếu các bước.
- **Đạt khi:** hành trình có thể lặp lại từ database mới bằng hướng dẫn; không phụ thuộc record từ dev/prod hoặc thao tác thủ công không được ghi lại.

### 14. Giới hạn tích hợp bên ngoài

- Ghi rõ SMTP/email, S3, real AI/AI Vision, payment gateway, worker daemon/heartbeat, chi phí/retention/region và dữ liệu có quyền gửi ra ngoài đã được hay chưa kiểm chứng.
- Chỉ chạy các tích hợp thật sau khi có môi trường staging, credentials từ secret store, kiểm soát ngân sách/dữ liệu và phê duyệt phù hợp.
- **Đạt khi:** phần demo không ngụ ý các tích hợp `NOT TESTED` đã hoạt động; giới hạn và điều kiện bật được nêu rõ trong báo cáo nghiệm thu.

## Biểu mẫu ghi kết quả

| Mục | Trạng thái | Bằng chứng/lệnh | Vấn đề hoặc blocker | Người xác nhận |
|---|---|---|---|---|
| 1–14 | NOT TESTED |  |  |  |
