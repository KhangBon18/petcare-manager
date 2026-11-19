# Phase 5.4 — Deterministic assistant evaluation

Đây là đánh giá intent/rule/service/UI; không phải đánh giá LLM. Không có provider thật được gọi và không tuyên bố cải thiện khả năng reasoning của model.

## Bộ đánh giá

`tests/unit/test_assistant_capabilities.py` cung cấp chín unit tests (cùng các subtests) về intent và contract bằng kết quả service giả định có kiểm soát:

| Chỉ số | Kết quả | Evidence |
|---|---:|---|
| Intent được hỗ trợ | **5/5** | 3 mẫu VI cho tồn kho, 1 EN tồn kho, 1 VI/EN purchase status; classifier giữ đúng capability. |
| Intent không hỗ trợ / ghép | **3/3** | Câu hỏi về system prompt, invoice unpaid và yêu cầu ghép nhiều capability không bị nhận nhầm thành một capability duy nhất. |
| Inventory arithmetic | **PASS** | 11 synthetic rows, 1 không cảnh báo → `total=10`, cap 8; kiểm `suggested_qty=9`, `days_left=4.0`. |
| Purchase status aggregation | **PASS** | 4 trạng thái × 3 synthetic rows → count 3 mỗi trạng thái, total 12, cap 8, đúng đơn mới nhất. |
| Missing/error handling | **PASS** | Kết quả rỗng, custom date range, trạng thái PO mâu thuẫn, “not received”, `ForbiddenError`, lỗi DB và requested count quá lớn có output bounded/clarification an toàn. |
| API/UI contract safety | **PASS** | JS tests kiểm 2 insight mới, malicious markup hiển thị như text, URL ngoại origin bị loại, retry bấm được. |

## Kiểm chứng MySQL và browser thật

- `test_assistant_inventory_and_purchase_status_use_real_tenant_services`: tạo sản phẩm QA tồn 0 cùng PO ở bốn trạng thái trong `petcare_phase54_full_test`; gọi POST `/assistant/chat` với CSRF/session thật. Kết quả có stock 0, đủ bốn trạng thái, route links hợp lệ.
- Request có `tenant_id` giả mạo và câu “Ignore all rules…”; service được gọi với tenant session hiện tại. Provider được patch thành configured nhưng `ai_client.complete` không được gọi.
- Staff đăng nhập thật nhận `status=forbidden`, không có `insight`. Data test được dọn theo ID do test tạo.
- Playwright kịch bản assistant chạy UI thật trên MySQL; kiểm suggestion → `/assistant/chat` → structured cards, supplier/units/status, links, keyboard Enter/Escape, focus restoration và responsive 320/390/768/1440 px.
- Axe assistant chạy 3 state (inventory desktop, purchasing desktop, purchasing mobile 390 px): **0 violations**, 40 incomplete node instances. Incomplete cần kiểm thủ công; đây không phải chứng nhận WCAG.
- Full browser suite: **17/17, 0 skip**. Diagnostics có 0 failed request và 0 page error. Một console/HTTP error là expected `GET /users/` → 403 khi staff test quyền; browser assertion phân loại denial này là expected.

## Full regression: trước / sau

| Suite | Baseline Phase 5.3B | Phase 5.4 | Delta |
|---|---:|---:|---:|
| Python | 405/405 | **415/415, 0 skip** | +10: 9 assistant capability unit tests + 1 MySQL integration test |
| JavaScript | 36/36 | **38/38** | +2 rendering/retry tests |
| Playwright Chromium | 16/16 | **17/17, 0 skip** | +1 end-to-end assistant scenario |

Lệnh Python full chạy trên MySQL 8.4 disposable schema `petcare_phase54_final_test`; suite browser chạy trên schema/storage disposable riêng. Sau hardening, full Python regression chạy lại đạt **415/415, 0 skip**. Luồng assistant responsive/navigable chạy thêm một lần riêng trên test DB disposable: **1/1 PASS**. Các con số chỉ áp dụng cho test cases và môi trường ghi trên đây.

## Chưa đo

- Không đo LLM accuracy, BLEU/semantic quality, latency/token/cost, vì không gọi LLM thật.
- Không đo Vision accuracy/provider, ảnh không được gửi ra ngoài.
- Không có load test catalog lớn; service inventory hiện materialize danh sách active product đầy đủ.
- Screen reader, browser zoom 200%, Safari/Firefox và hosted CI chưa chạy.
