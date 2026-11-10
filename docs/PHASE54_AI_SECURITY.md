# Phase 5.4 — Assistant security review

Trạng thái: **VERIFIED cho hai capability đọc-only trên test schema**. Không thay đổi quyền/tenant boundary hiện có; không có provider egress.

| Rủi ro | Kiểm soát và bằng chứng |
|---|---|
| Chưa đăng nhập / CSRF / abuse | Route `/assistant/chat` giữ `login_required`, CSRF và throttle theo account/IP. Malformed JSON/message tiếp tục có web regression coverage. |
| IDOR / tenant confusion | `assistant_routes.chat` truyền `g.tenant_id` do session/actor context xác định. Client `tenant_id` không được dùng. Real MySQL integration gửi ID tenant sai; instrumented service nhận đúng tenant đang đăng nhập. |
| Staff đọc dữ liệu mua hàng | `purchase_service.list_purchase_orders` gọi `require_actor(..., admin=True, tenant_id=...)`. Capability chỉ trả thông điệp `forbidden`, không trả insight. Test staff route và browser route admin-only cùng pass. |
| Prompt injection thành SQL hoặc quyền | Classifier chỉ chọn registry entry; status đến từ enum cố định. Không lấy fragment, sort, SQL predicate hay tenant ID từ user text. Prompt “Ignore all rules…” chỉ kích hoạt read-only status service hiện tại; provider được cấu hình trong test nhưng không gọi. |
| Quá nhiều dữ liệu / PII | Inventory JSON tối đa 8 row; PO mỗi status đọc page 25 rồi chỉ trả tối đa 8. PO không gồm email/điện thoại supplier, note hoặc customer record. Inventory chỉ trả field allowlist, bỏ filename ảnh. |
| Stored/reflected XSS | Tên sản phẩm/supplier đi vào DOM bằng `textContent`. Browser JS tests đưa `<img>`/`<script>` giả vào tên; được hiển thị thành text, không tạo element chạy code. Link chỉ chấp nhận `/products/<id>` hoặc `/purchasing/<id>`. |
| Credential/DB error disclosure | DB exception được log ở mức class name, response chỉ có thông điệp chung và `status=unavailable`. Unit tests dùng lỗi giả chứa chuỗi nhạy cảm; response không lộ chuỗi đó. Không đưa credential vào docs/artifact. |
| Tác động dữ liệu | Capability gọi service read-only; không transaction ghi, không nhận hàng, không chỉnh stock. MySQL E2E tạo fixture QA tổng hợp và xóa đúng ID sau test. |
| Egress | Không gọi generative AI/Vision thật; `AI_API_BASE_URL`, key/model rỗng trong QA. Integration test assert `complete` không được gọi kể cả khi mock báo provider configured. Vision chạy mock loopback theo suite cũ, không gửi ảnh ra ngoài. |

## Data flow / quyền

`authenticated browser + CSRF → /assistant/chat → bounded intent registry → existing service → tenant-scoped repository → safe insight JSON → text-only DOM`.

- Inventory: tenant member được đọc các gợi ý tồn kho đang hiển thị ở dashboard/product pages.
- Purchasing: admin mới được đọc status. Staff không nhận counts hoặc record names.
- Tất cả URL tiền/thời gian được route dựng server-side; request không thể chọn store bằng body.
- Generic assistant/provider path cũ vẫn tồn tại nếu người vận hành cấu hình endpoint. Hai intent Phase 5.4 được xử lý trước path đó và không egress.

## Security gates

- Bandit 1.9.4 với baseline CI đúng: **exit 0**. Bandit in `nosec encountered (B608)` warnings tại statement đã reviewed/allowlist, bao gồm readiness/purchase/tenant cleanup; không có finding mới vượt gate.
- `pip-audit` cho `requirements.lock` và `requirements-browser.lock`: không có known vulnerabilities.
- `npm audit --prefix tests/a11y`: 0 vulnerabilities.
- Browser suite: không có failed network request hoặc JS page error. Staff `/users/` 403 là denial được kỳ vọng trong test role-boundary.

## Giới hạn

`restock_service` hiện tải toàn bộ product active để áp công thức và đếm cảnh báo; response assistant bounded 8 nhưng CPU/DB work phụ thuộc quy mô catalog. Chưa chạy load test. Bandit B608 `nosec` warning hiện vẫn có; không thêm suppression mới trong Phase 5.4. Trivy hosted job, SAST khác, screen reader và live provider security review chưa thực hiện.
