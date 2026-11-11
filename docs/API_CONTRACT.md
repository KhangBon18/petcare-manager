# Hợp đồng HTTP/API hiện hành

Ứng dụng là Flask server-rendered web app, không có API version prefix hoặc OpenAPI spec. Bảng dưới kiểm kê các route ứng dụng hiện đăng ký (79 rules; không tính static route của Flask). JSON routes được mô tả riêng; các route HTML render Jinja hoặc redirect.

## Quy tắc chung

- Auth session ký bằng Flask secret chứa user id, tenant id và session_version. Mỗi request authenticated tải lại active membership, tenant và role từ MySQL.
- @login_required redirect browser tới /login nếu chưa đăng nhập. @admin_required thêm kiểm tra admin; staff bị 403. Tenant scope đến từ actor context, không lấy từ client làm quyền.
- Flask-WTF CSRFProtect áp dụng cho POST. JSON POST dùng token trong header X-CSRFToken hoặc cơ chế CSRF token của form.
- Các trang/JSON chứa dữ liệu signed-in có Cache-Control private, no-store; response chung có CSP, nosniff, frame deny, referrer/permissions policy.
- Không có versioning/schema generation; các JSON response được kiểm bằng unit/web/integration tests. Field/schema thay đổi cần cập nhật tests và tài liệu này.
- Mọi form write trả HTML flash + redirect hoặc giữ form/errors. JSON write trả JSON status. 404/403/413/500 có template error.

## Route inventory theo blueprint

| Blueprint | Rules, methods và path | Access / mục đích |
|---|---|---|
| main | GET /; GET /dashboard | Public root chuyển vào login/dashboard; dashboard yêu cầu đăng nhập và tải dữ liệu tenant. |
| auth | POST /language; GET,POST /login; POST /logout; POST /stores/switch; GET,POST /signup | Locale allowlist; login/logout; chuyển store theo membership; signup nếu bật public signup. |
| account | GET,POST /account/settings; POST /account/profile; POST /account/verification/resend; GET,POST /account/email/verify; GET,POST /account/password/forgot; GET,POST /account/password/reset | Settings/profile yêu cầu login; token verify/reset là public, single-use/rate-limited. |
| customers | GET /customers/; GET /customers/<customer_id>; GET,POST /customers/new; GET,POST /customers/<customer_id>/edit; POST /customers/<customer_id>/active; POST /customers/<customer_id>/deactivate | Signed-in, tenant scoped. Customer detail accepts independent `page` (invoice history) and `pet_page` (purchased pets) query values. |
| pets | GET /pets/; GET,POST /pets/find-similar; POST /pets/suggest-attributes; GET /pets/photo/<filename>; GET /pets/<pet_id>; GET,POST /pets/new; GET,POST /pets/<pet_id>/edit; POST /pets/<pet_id>/deactivate; POST /pets/<pet_id>/active | Read/photo/search yêu cầu login; create/edit/active và attribute suggestion admin-only. Ảnh kiểm tenant ownership. |
| products | GET /products/; GET /products/<product_id>; GET,POST /products/new; GET,POST /products/<product_id>/edit; GET /products/photo/<filename>; POST /products/<product_id>/stock; POST /products/<product_id>/active; POST /products/<product_id>/deactivate | Signed-in; thay đổi catalog/stock admin-only. |
| invoices | GET /invoices/; GET,POST /invoices/new; GET /invoices/lookups/customers; POST /invoices/customers/quick; GET /invoices/lookups/items; GET /invoices/<invoice_id>; POST /invoices/<invoice_id>/refund; POST /invoices/<invoice_id>/pay; POST /invoices/<invoice_id>/cancel | Signed-in; refund admin-only. Payment/cancel/refund là POST + CSRF và service kiểm transaction/idempotency. |
| purchasing | GET /purchasing/; GET /purchasing/products; GET,POST /purchasing/new; GET /purchasing/<purchase_order_id>; POST /purchasing/<purchase_order_id>/receive; POST /purchasing/<purchase_order_id>/cancel; GET /purchasing/suppliers; GET,POST /purchasing/suppliers/new; GET,POST /purchasing/suppliers/<supplier_id>/edit; POST /purchasing/suppliers/<supplier_id>/activate; POST /purchasing/suppliers/<supplier_id>/deactivate | Admin-only; sản phẩm tìm kiếm là JSON; tạo/nhận/hủy purchase order ghi stock movement qua service. Nhận hàng yêu cầu UUID `receipt_request_key` do trang chi tiết sinh; cùng key và cùng lượng nhận được replay an toàn, còn dùng lại key cho nội dung khác bị từ chối. |
| reports | GET /reports/; POST /reports/export.xlsx | Signed-in; report date range và export snapshot gắn user + tenant. |
| assistant | POST /assistant/chat | Signed-in + CSRF + per-account/IP throttle; local-first, optional provider. |
| audit | GET /activity/ | Admin xem activity theo tenant. |
| store | GET,POST /store/settings | Admin cập nhật tên/timezone cửa hàng. |
| users | GET /users/; POST /users/invitations; POST /users/invitations/<invitation_id>/revoke; GET /users/ownership; POST /users/ownership; POST /users/ownership/<transfer_id>/cancel; POST /users/ownership/<transfer_id>/accept; GET,POST /users/invitations/accept; GET,POST /users/new; POST /users/<user_id>/update; GET,POST /users/export; GET /users/export/jobs/<job_id>; GET /users/export/jobs/<job_id>/status; GET /users/export/jobs/<job_id>/download | Hầu hết admin; invitation accept public; token pages no-store/no-referrer. Export queue/status/download bị giới hạn theo tenant + requester. |
| health | GET /healthz; GET /readyz; GET /workersz | Public JSON probes. /healthz liveness; /readyz MySQL/schema contract; /workersz fresh email/export heartbeats. |
| metrics | GET /metrics | Tắt nếu OPS_METRICS_TOKEN trống (404); nếu bật yêu cầu Authorization: Bearer token. Payload chỉ tổng hợp, response không cache. |

Dynamic path parameters là số nguyên ID, trừ filename ảnh; ảnh chỉ dùng identifier do hệ thống cấp và route vẫn truy vấn quyền sở hữu. Flask static endpoint GET /static/<path:filename> phục vụ assets same-origin.

## JSON contracts

### Assistant chat

- Request: POST /assistant/chat, Content-Type application/json: {"message": string, "history"?: array}.
- Success: JSON từ assistant service, tối thiểu có `reply` và `mode` (`local` hoặc `ai`); catalog items có server-generated URL/price/status/photo fields khi có kết quả. Các intent dữ liệu xác định có thể thêm `insight`:
  - `operations_overview`: `{kind,purchasing:{status,open_total,status_counts,items,url},inventory:{status,total,target_days,warning_days,items},sales:{status,period,start_date,end_date,currency_code,items,url}}`. Admin-only; `purchasing` tổng hợp hai trạng thái đang cần xử lý (`ordered`, `partially_received`) bằng `purchase_service`, `inventory` dùng `restock_service`, `sales` dùng `report_service.top_products_for_period` cho `7d`. Danh sách trong từng nhóm tối đa 5; counts được lấy từ service/repository hiện có. Sales là top sản phẩm bán ròng dương, không phải tổng doanh thu hóa đơn. URL do server tạo: sản phẩm, đơn nhập, `/purchasing/`, và báo cáo đúng ngày. Mỗi nguồn ngoài purchasing có thể trả `status:"unavailable"`; top-level `status:"partial"` khi một nguồn phụ lỗi. Không trả partial data cho user bị từ chối quyền.
  - `top_products`: `{kind, period, start_date, end_date, currency_code, items:[{product_id:int,code:string,name:string,quantity_sold:int,revenue:string,url:string,revenue_label:string}]}`. Ngày là ISO; kỳ là enum `today`, `7d`, `week`, `last_week`, `month`, `last_month`; tối đa 5 sản phẩm bán ròng dương.
  - `inventory_restock`: `{kind,total,target_days,warning_days,items:[{product_id,name,code,stock_qty,reorder_level,sold_14,sold_30,days_left,suggested_qty,basis,url}]}`. Chỉ các sản phẩm đạt ngưỡng cảnh báo; tối đa 8 item. `total` là số cảnh báo chính xác trong tenant hiện tại. Dữ liệu theo quy tắc tồn kho 14/30 ngày hiện có; không nhận ngày tùy chỉnh.
  - `purchase_status`: `{kind,total,status_counts,selected_statuses,items:[{purchase_order_id,supplier_name,status,created_at,created_at_label,item_count,ordered_units,received_units,total_amount,currency_code,url,amount_label}]}`. Admin-only; counts phản ánh đủ bốn trạng thái hiện hỗ trợ; tối đa 8 đơn gần nhất. `selected_statuses` rỗng nếu không lọc hoặc chứa một nhóm trạng thái được ánh xạ từ câu hỏi. Không trả thông tin liên hệ nhà cung cấp hoặc khách hàng.
- Capability inventory, purchasing và operations overview luôn trả `mode:"local"`, không gọi AI provider. Các URL, nhãn thời gian và tiền được server tạo; tenant lấy từ phiên đăng nhập, không từ payload. Payload `tenant_id` gửi kèm bị bỏ qua. Mọi capability là chỉ đọc.
- Với các intent trên, `status` tùy chọn là `clarification`, `forbidden` hoặc `unavailable`; overview thêm `ok` hoặc `partial` khi có dữ liệu. Không có `insight` khi chưa truy vấn hoặc bị từ chối. Overview dùng kỳ bán hàng 7 ngày gần nhất theo timezone tenant; khoảng ngày khác nhận clarification. Yêu cầu số lượng lớn vẫn bị giới hạn theo cap của capability (8 cho từng intent Phase 5.4, 5 cho overview).
- Errors: 400 malformed/non-string/invalid message; 429 rate limit với Retry-After; service validation trả 400. Request cần auth + CSRF.

### POS customer/items

- GET /invoices/lookups/customers?q=…&page=… → {items:[{id, full_name, phone}], pagination:{…}}.
- GET /invoices/lookups/items?q=…&product_page=…&pet_page=… → {products:[{id,code,name,unit_price,stock_qty,photo_url}], pets:[{id,code,name,sale_price,photo_url}], product_pagination:{…}, pet_pagination:{…}}. Giá trả chuỗi decimal.
- POST /invoices/customers/quick, JSON customer fields (full_name, phone, optional address) → 201 {customer:{id, full_name, phone}}; invalid body/fields → 400 {error, errors}. Requires signed-in session and CSRF.

### Purchasing product lookup

GET /purchasing/products?q=… → {items:[…]}; admin-only. Validation/service error → 400 {error}. Kết quả phục vụ form purchase; giá/tổng vẫn được kiểm phía server khi tạo order.

### Attribute suggestion

POST /pets/suggest-attributes multipart/form-data với field `photo`; admin-only + CSRF. Server đọc tối đa 5 MB và dùng Pillow kiểm tra định dạng thực JPEG/PNG/WebP, không dựa vào tên file hay MIME client; ảnh được định hướng theo EXIF, resize tối đa 1600 px, re-encode JPEG và bỏ metadata trước khi xử lý/provider. Request gợi ý chỉ giữ bytes trong bộ nhớ và không lưu ảnh vào hồ sơ/storage.

Thành công 200 giữ các field tương thích `suggestions`, `colors`, `mode`, `warning` và thêm `status`, `provider_status`. `status` là `observations` (provider trả được field hợp lệ), `uncertain` (ước lượng local/fallback), `unrecognized` (không có thuộc tính dùng được), hoặc `provider_unavailable` (không có fallback). `mode` vẫn là `vision` hoặc `local`; `provider_status` là `used`, `partial`, `ambiguous`, `invalid_output`, `unavailable` hoặc `disabled`. `suggestions` chỉ gồm field allowlist `species`, `breed`, `coat_color`, `eye_color`, `appearance_tags` với độ dài phù hợp form. Unknown fields như confidence, URL, HTML hoặc action bị loại bỏ; không có confidence được bịa. Frontend hiển thị bằng text node và chỉ áp dụng vào field trống sau khi người dùng bấm.

JSON lỗi có `{status, code, error}`: thiếu/ảnh sai → 400 `invalid_input`; throttled hoặc worker bận → 429 `rate_limited` kèm `Retry-After`; lỗi xử lý nội bộ → 500 `processing_error` với thông điệp chung. Admin-only authorization denial trả HTTP 403 theo error template chung hiện hành. Provider bị tắt mặc định (`AI_VISION_ENABLED=0`); nếu bật trong QA, endpoint trỏ tới mock loopback. Không gọi provider ngoài trong bộ kiểm thử Phase 5.2.

Verification Phase 5.2: request/response contract chạy qua Flask + MySQL test schema và Chromium mock-provider; xem PHASE52_VISION_IMPLEMENTATION.md. Hosted CI và provider thật chưa được xác minh.

### Report export

POST /reports/export.xlsx gửi snapshot token từ trang report bằng JSON hoặc form body. Thành công trả XLSX, content type application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; snapshot thiếu/hết hạn/sai user-tenant → 400 JSON {error}. Export không nhận tổng tiền do client tự tính.

### Tenant export status

GET /users/export/jobs/<job_id>/status, admin trong cùng tenant/requester → JSON {status, attempt}; khi ready có download_url và expires_at; khi failed có message. Response no-store. Download trả file mã hóa pcarexport, không trả ZIP giải mã.

### Health, readiness, workers và metrics

- GET /healthz → 200 {"status":"ok"} nếu Flask process đang đáp ứng.
- GET /readyz → 200 {"status":"ready"} khi MySQL/schema contract đầy đủ; 503 {"status":"unavailable"} nếu connector/schema chưa sẵn sàng.
- GET /workersz → 200 {"status":"ready"} chỉ khi cả worker bắt buộc có heartbeat mới; nếu không là 503 unavailable.
- GET /metrics → 404 khi tắt; 401 khi token thiếu/sai; 503 nếu database lỗi; 200 Prometheus text khi token hợp lệ và DB truy cập được.
- /readyz có thể trả X-PetCare-Demo-Database chỉ ở local nonproduction "_dev"/"_test", request loopback, phục vụ preflight signature; header này không chứa database password.

## HTML form semantics

### Customer detail pagination

`GET /customers/<customer_id>?page=<invoice_page>&pet_page=<purchased_pet_page>` renders the customer profile. Each list paginates independently at 12 records per page. Omitting either parameter selects page 1 for that list. Invalid/out-of-range values are normalized by the existing page-window service. Links for purchased pets preserve the current invoice `page`; invoice-history links preserve the current `pet_page` when present. This changes only HTML navigation; there is no JSON response/schema change.

Form create/edit có field validation phía service; lỗi được render cùng submitted values. CSRF thiếu/sai bị Flask-WTF từ chối. POS gửi danh sách item type/id + quantity; client không quyết định giá. Invoice payment/repeated payment, refunds và stock adjustment gọi service transaction. Purchase receiving nhận UUID idempotency key cùng danh sách item/quantity; key cùng nội dung được nhận diện là retry và không tạo thêm tồn kho, key dùng lại với nội dung khác bị từ chối. Một key mới biểu thị lần giao hàng mới.
