# Chuẩn bị bảo vệ — lời dẫn 8–12 phút

## Kịch bản 10 phút

| Thời gian | Thao tác chính xác | Kết quả cần chỉ ra / lời dẫn |
|---|---|---|
| 0:00–0:50 | Đăng nhập `admin` trên store `main`, mở Dashboard. | “Đây là ứng dụng quản lý cửa hàng thú cưng theo tenant, xây dựng bằng Flask, Jinja, MySQL và JavaScript tăng cường tương tác. Demo dùng synthetic data.” |
| 0:50–1:50 | Customers → New: tạo một khách giả; Pets → New: tạo hồ sơ cat với giá và trạng thái available. | “Route nhận form; service kiểm tra dữ liệu/quyền; repository ghi MySQL. Pet chưa bán nên chưa có buyer.” |
| 1:50–2:40 | Products → New: tạo SKU demo, số lượng đầu 0. Tạo supplier. | “Tồn được đối chiếu qua stock movement ledger, không phải chỉ thay một con số trên giao diện.” |
| 2:40–4:00 | Purchasing → New order 8 đơn vị; mở chi tiết; nhận 3 rồi nhận 5. | “Khi tạo đơn chưa nhận hàng, tồn vẫn 0; sau lần đầu order partially_received, stock 3; sau lần hai order received, stock 8.” |
| 4:00–5:35 | POS → thêm 2 đơn vị sản phẩm và pet vừa tạo, chọn customer, tạo hóa đơn, mở detail, bấm thanh toán mô phỏng. | “Hóa đơn ban đầu unpaid. Sau thanh toán, sản phẩm giảm 2, pet đổi trạng thái sold và được gắn buyer. Không có payment gateway hay tiền thật.” |
| 5:35–6:30 | Invoice detail → refund 1 product unit, disposition resell; vào Reports. | “Refund được ghi ở bảng riêng, không sửa lại hóa đơn đã thanh toán. Tồn của sản phẩm được cộng lại theo disposition. Báo cáo đọc transaction/refund từ MySQL.” |
| 6:30–7:20 | Users → export, dùng password/passphrase tạm theo giao diện, chờ job và tải bundle. | “Route chỉ enqueue job; worker xử lý export và heartbeat giúp `/workersz` báo trạng thái. Bundle được mã hóa; không đưa passphrase vào report.” |
| 7:20–8:10 | Dashboard → Assistant → chọn “Bán chạy tuần này”. | “Assistant demo lấy insight từ truy vấn/rule local trên dữ liệu tenant; nếu có provider LLM thì đó là adapter tùy chọn, chưa phải nguồn evidence của buổi demo.” |
| 8:10–8:55 | Pets → New → mở Vision suggestion, xem field, apply, không submit form. | “QA dùng mock cố định trả JSON synthetic, không hiểu ảnh. Apply chỉ điền trường trống; người dùng xem lại và quyết định lưu.” |
| 8:55–9:35 | Đăng xuất, vào bằng `staff1`, mở Customers rồi `/users/`. | “Staff có quyền nghiệp vụ giới hạn; route quản trị phải trả 403. Quyền được đọc lại từ membership phía server.” |
| 9:35–10:00 | Kết luận bằng test matrix/status. | “Python 428/428, JavaScript 41/41, Playwright 18/18; CI 6/6. Đây là release học thuật local; production chưa được duyệt.” |

Kịch bản này lấy thao tác và kết quả từ [academic demo script](ACADEMIC_DEMO_SCRIPT.md). Các số từ fixture có thể thay đổi nếu dữ liệu đã được operator tạo thêm; reset bằng `r` trước demo để bắt đầu sạch.

## Lời mở đầu ngắn

“Bài toán của em là theo dõi khách hàng, thú cưng, hàng tồn và giao dịch trong một cửa hàng mà dữ liệu vẫn liên kết được. Em tách web route, service nghiệp vụ và repository MySQL để mỗi lớp có trách nhiệm rõ ràng. Từng cửa hàng được xác định theo membership của user; các thao tác kho/bán hàng dùng transaction và ledger để có thể kiểm tra lại.”

## Những câu hỏi kỹ thuật có thể gặp

### 1. Vì sao có app factory `create_app()`?

`petcare/app_factory.py::create_app()` tạo Flask app, nạp cấu hình, kiểm tra cấu hình, đăng ký CSRF/request hooks, blueprints, error handlers và template helpers. Cách này giúp tạo app riêng cho runtime/test config và hạn chế import side effect. `run.py` là launcher phát triển/QA; `wsgi.py` cung cấp app cho Gunicorn.

### 2. Route, service, repository khác nhau thế nào?

Route trong `petcare/routes/` tiếp nhận request HTTP/form, gọi service, rồi trả template/redirect/JSON. Service trong `petcare/services/` xác thực input, quyền và chuyển trạng thái nghiệp vụ. Repository trong `petcare/repositories/` chứa các câu truy vấn tham số hóa và persistence. Database constraints là lớp bảo vệ cuối cùng, không thay cho validation service.

### 3. Nêu ví dụ một hàm Python quan trọng.

- `petcare/services/purchase_service.py::create_purchase_order()` xác thực quyền, supplier, product và line item rồi tạo order trong transaction; tạo order không tự tăng tồn.
- `receive_purchase_order()` khóa order/line/product liên quan, kiểm số lượng còn lại, cập nhật received quantity, stock movement và trạng thái trong cùng transaction. Lần nhận lặp dùng request key/payload fingerprint để chặn duplicate.
- `petcare/services/invoice_service.py::create_invoice()` lưu snapshot invoice/items ở trạng thái unpaid; `pay_invoice()` mới khóa invoice/items, kiểm tồn, cập stock hoặc trạng thái pet và ghi audit.
- `petcare/services/refund_service.py::refund_invoice()` chỉ áp dụng invoice đã paid, ghi refund/item ledger riêng và hoàn tồn theo disposition.

### 4. Transaction rollback hoạt động ra sao?

`petcare/database/connection.py::transaction()` là context manager. Code nghiệp vụ chạy trong `with transaction()`: nếu hết khối bình thường thì `commit()`, nếu exception thì `rollback()` rồi ném exception tiếp, cuối cùng trả connection về pool. Ví dụ receiving phải ghi cùng lúc số lượng nhận, tồn kho, movement và status; nếu một bước fail thì rollback để không lưu trạng thái nửa chừng. Một bài học cần nêu: đảm bảo tất cả writes quan trọng thật sự nằm trong cùng transaction/connection.

### 5. Tenant isolation được thực hiện ở đâu?

`require_actor()` lấy user và membership đang hoạt động trong MySQL, kiểm role, rồi gọi `set_tenant_context()` trên connection. Repository query thêm điều kiện tenant hoặc dùng session variable `@petcare_tenant_id`. Composite keys/foreign keys liên kết child với parent cùng tenant. Tenant ID không được tin từ hidden field/client làm quyền. Đây là schema dùng chung có tenant key; không phải database riêng cho từng cửa hàng.

### 6. `owner`, `admin`, `staff` có nghĩa gì?

Schema membership hỗ trợ owner/admin/staff. Login service ánh xạ owner sang role ứng dụng `admin` cho business routes. QA seed có `admin` username thuộc role owner và `staff1` thuộc role staff. Vì vậy câu giải thích không nên nói QA có một membership admin riêng.

### 7. Assistant có phải ChatGPT/LLM không?

Không trong cấu hình demo. Assistant có intent/rule cục bộ và một số truy vấn/report-backed insight đọc dữ liệu tenant; optional provider adapter tồn tại nhưng demo launcher cô lập để không gọi provider thật. Không dùng kết quả demo để khẳng định chất lượng, độ chính xác hoặc chi phí của một LLM.

### 8. Vision mock khác Vision thật thế nào?

`scripts/demo/vision_mock.py` chỉ nhận synthetic JPEG request hợp lệ rồi trả trường gợi ý cố định (cat/domestic shorthair/gray/green). Mock không phân loại nội dung ảnh. Trong code còn có pipeline descriptor cục bộ cho tìm ảnh tương tự và adapter gợi ý có thể nối provider; nhưng trong demo không có đánh giá model/provider thật. Gợi ý không tự lưu hồ sơ; người dùng xem lại và quyết định.

### 9. Thanh toán/hoàn tiền có chuyển tiền không?

Không. `pay_invoice()` cập nhật trạng thái và stock nghiệp vụ. Refund ghi ledger và có thể cập nhật stock disposition. Không có tích hợp payment gateway; chuyển tiền hoàn thực tế nằm ngoài ứng dụng.

### 10. Vì sao stock movement cần thiết?

Ledger ghi lại delta, nguyên nhân, actor và tham chiếu nghiệp vụ để có thể đối chiếu nguồn thay đổi tồn. Chỉ lưu quantity hiện tại sẽ khó truy nguyên sai lệch. PO receiving, invoice payment và refund cần cập nhật quantity cùng ledger trong cùng transaction.

### 11. Đã kiểm thử những gì? Có phải coverage 100%?

Bằng chứng ở release baseline: Python 428/428, JavaScript 41/41, Playwright 18/18, GitHub Actions 6/6; cross-browser Playwright chromium/firefox/webkit 3/3 engine. Không đồng nghĩa test bao phủ mọi hành vi/OS, không thay kiểm thử provider thật, screen reader hay production load. Không tuyên bố coverage 100% hoặc WCAG compliance.

### 12. Vì sao production vẫn NO-GO?

SMTP, S3, payment provider, LLM/Vision provider thật, deployment/TLS/backup/restore theo production và accessibility thật chưa được nghiệm thu trong scope này. Release hiện tại dành cho demo học thuật local với dữ liệu tổng hợp.

## Fallback 3–5 phút

1. Dashboard, giải thích tenant và dữ liệu tổng hợp.
2. Mở PO đã seed, chỉ trạng thái/stock; nếu không có order sẵn thì bỏ bước tạo mới.
3. Mở invoice/report đã có, giải thích pay/refund và stock ledger; không tạo giao dịch nhiều nếu thời gian ngắn.
4. Mở Assistant và Vision mock, nói rõ hai khác biệt với provider/model thật.
5. Dùng `staff1` để chỉ 403 trên `/users/`; kết thúc bằng status và limits.

Nếu UI hoặc DB gặp lỗi, không giả lập kết quả: chuyển sang sơ đồ [architecture](ACADEMIC_ARCHITECTURE.md), [ERD](ACADEMIC_DATABASE_ERD.md) và screenshots QA trong `docs/assets/phase62/`, rồi ghi live demo là blocked.

## Cách trình bày Python

Giữ phần giải thích ở mức môn Python: hàm, module/import, dictionary/list, exception, context manager, decorator route, transaction, parameterized query, dataclass/role checks. Không cần trình bày framework nội bộ dài. Mỗi lần nêu “đã làm” hãy chỉ vào code/test thực tế hoặc nói đó là giới hạn/chưa test.
