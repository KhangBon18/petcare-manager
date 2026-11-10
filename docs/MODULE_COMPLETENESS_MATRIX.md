# Ma trận độ hoàn thiện module

## Cập nhật Phase 5.4 — 2026-11-10

| Module | Trạng thái | Bằng chứng mới nhất và giới hạn |
|---|---:|---|
| AI Assistant — inventory restock | A/B | `assistant/chat` dùng `restock_service`, trả exact warning total, số liệu 14/30 ngày và tối đa 8 priority cards. MySQL route + browser desktop/mobile PASS; service hiện đọc toàn bộ active products. |
| AI Assistant — purchase status | A/B | `assistant/chat` dùng `purchase_service`, status counts bốn enum và tối đa 8 đơn; admin-only, staff denial, tenant override/prompt injection test PASS. Không có write actions. |
| AI Assistant — top products/legacy intents | A/B | Top-products insight vẫn giữ report route/service và 5-item limit; generic catalog/revenue/pet responses giữ nguyên. Arbitrary natural language/custom dates chưa hỗ trợ. |
| Assistant UI / accessibility | B | Cards, local-source labels, empty/denied/unavailable/clarification states, keyboard retry/focus và responsive bounds đã chạy ở 320/390/768/1440. 3 axe scans assistant: 0 violations, 40 incomplete nodes; screen reader/zoom chưa chạy. |
| Generative AI / Vision provider | E | Phase 5.4 không gọi provider thật hoặc truyền ảnh; Vision mock-only coverage hiện có. Real accuracy/privacy/cost/retention vẫn chưa đo và pilot gates chưa hoàn tất. |

Evidence: [implementation](PHASE54_IMPLEMENTATION.md), [capabilities](PHASE54_AI_CAPABILITIES.md), [evaluation](PHASE54_AI_EVALUATION.md), [security](PHASE54_AI_SECURITY.md), [UX](PHASE54_AI_UX.md).

## Cập nhật Phase 5.2 — 2026-11-10

| Module | Trạng thái | Bằng chứng mới nhất và giới hạn |
|---|---:|---|
| Pet profile / image input | A/B | Admin form suggestion, Pillow validation/normalization, local fallback, apply blank-only và Flask/MySQL workflow chạy trên Chromium. Sáu viewport, keyboard và error/retry cases đạt. |
| AI Vision provider | E/B | Provider contract được kiểm với loopback mock; default off. Accuracy, provider thật, privacy/retention/region/cost và licensed-image benchmark chưa được xác minh; xem [Phase 5.3 readiness](PHASE53_PROVIDER_READINESS.md). |
| Vision security | B | Admin/CSRF/tenant, size/pixel/format, metadata stripping, output allowlist, safe text, rate/concurrency được test; không gọi provider thật. |
| Shared accessibility | B | Input label, aria-live/aria-busy và keyboard apply được kiểm trong workflow; screen reader, axe mới, 200% zoom và full WCAG chưa chạy. |

Evidence: [Phase 5.2 implementation](PHASE52_VISION_IMPLEMENTATION.md), [architecture](PHASE52_VISION_ARCHITECTURE.md), [evaluation](PHASE52_VISION_EVALUATION.md), [UX](PHASE52_VISION_UX.md). Bảng Phase 5.1 và Sprint 4.3 phía dưới giữ lịch sử.

## Cập nhật Phase 5.1 — 2026-11-10

| Module | Trạng thái | Bằng chứng mới nhất và giới hạn |
|---|---:|---|
| AI Assistant — local/report insight | B | Top products theo period đã đi từ assistant route qua report service/repository MySQL; kiểm role/tenant, VI/EN, empty/invalid, injection và link UI. Grounding 2/2 cho benchmark nhỏ; full regression QA chưa xanh. |
| Generative AI provider | E | Client/fallback vẫn tồn tại; không gọi endpoint thật. Timeout, malformed output, token/cost/latency chưa đo. |
| AI Vision | E/B | Local photo descriptor/color path còn hiện hữu; Vision thật và labelled-image metrics chưa chạy. Xem [handoff Phase 5.2](PHASE52_VISION_HANDOFF.md). |

Evidence chi tiết: [Phase 5.1 implementation](PHASE51_AI_IMPLEMENTATION.md), [evaluation](PHASE51_AI_EVALUATION.md), [security](PHASE51_AI_SECURITY.md), [UX](PHASE51_AI_UX.md). Bảng Sprint 4.3 phía dưới được giữ làm lịch sử.

## Cập nhật Sprint 4.3 — 2026-11-10

| Module | Trạng thái | Bằng chứng mới nhất và giới hạn |
|---|---:|---|
| Purchasing | A/B | Browser tạo PO, check không tăng tồn lúc đặt, partial/full receive, fill-remaining bằng keyboard, cancel; đối chiếu state/stock/stock movements trên MySQL QA. List/detail responsive ở 6 viewport; concurrency chưa stress-test. |
| Reports | A/B | Filter 7 ngày/custom, revenue/invoice count khớp report service, mobile product cards có quantity/revenue, XLSX tải được. PDF/print dialog và large-scale performance chưa chạy. |
| Operations / tenant export | A/B | Authenticated job pending, worker thật one-shot, ready/download size được kiểm; pending/ready responsive ở 6 viewport. S3/daemon/SMTP, decrypt, browser failure codes chưa được thử thật. |
| POS lookup recovery | B | Injected 503 hiện retry action, request lần sau thành công và cart giữ nguyên; service/invoice contract không đổi. |
| Shared accessibility | B | Axe 4.14.0: 26 sampled scans/0 violations sau contrast/header/named-region fixes. 39 incomplete node instances cần AT/manual review; screen reader, full WCAG và browser zoom 200% thật chưa xác minh. |
| AI/AI Vision | E | Local fallback/context tests hiện có; real provider/Vision chưa được gọi. Phase 5 handoff đặt kế hoạch đánh giá bằng dữ liệu synthetic/staging. |

Chi tiết: [PHASE43_IMPLEMENTATION_REPORT.md](PHASE43_IMPLEMENTATION_REPORT.md), [PHASE43_VISUAL_QA.md](PHASE43_VISUAL_QA.md), [PHASE5_AI_HANDOFF.md](PHASE5_AI_HANDOFF.md). Bảng Phase 4.2 phía dưới giữ trạng thái lịch sử.

## Cập nhật Phase 4.2 — 2026-11-10

Các dòng dưới đây là trạng thái mới nhất cho modules được đụng/kiểm tra; các mốc Phase 3.5 bên dưới giữ lịch sử.

| Module | Trạng thái | Bằng chứng và giới hạn mới nhất |
|---|---:|---|
| Product catalog | A/B | Search, create, detail, edit được chạy trên Chromium/MySQL QA. List chuyển thành card ≤680px và giữ bảng desktop; sáu viewport được đo document width. Loading under network throttle, ảnh sản phẩm và catalog quy mô lớn chưa chạy. |
| Inventory / stock ledger | A/B | Stock adjustment UI reject số âm, yêu cầu lý do, history hiển thị invoice/purchase/refund columns; browser cross-check delta +1 và sale -2 với MySQL, cuối cùng 1 còn từ 3. Service/tenant/permission/transaction không đổi. Stock edit/history ở viewport hẹp chưa xác minh. |
| POS / invoice | A/B | Item empty/valid search, customer selection, keyboard Enter selection + focus quantity, mobile cart count/total, overstock error, paid invoice và idempotent repeat đã chạy. Sáu widths không tràn document. Loading/network failure, browser submit replay, device/touch và payment gateway chưa xác minh. |
| Customer detail purchased pets | A | `pet_page` phân trang 12 record độc lập với invoice history; browser MySQL fixture có 13 paid pets và kiểm page 1/2 ở sáu widths. |
| Shared accessibility shell | B | axe 4.14.0 có 0 violations trên 13 targeted states; accessible labels và two low-contrast colors đã sửa. 13 incomplete node results, screen reader, real browser zoom 200% và audit mọi route chưa xong. |

Full execution details: [PHASE42_IMPLEMENTATION_REPORT.md](PHASE42_IMPLEMENTATION_REPORT.md), [PHASE42_VISUAL_QA.md](PHASE42_VISUAL_QA.md).

Ngày 2026-11-09. Phân loại A–E theo bằng chứng trong lượt browser/test này:

- **A** hoạt động đúng trong workflow đã thử.
- **B** hoạt động nhưng có UX/coverage cần cải thiện.
- **C** còn thiếu một phần chức năng theo code hiện hành.
- **D** có defect đang làm hỏng feature.
- **E** bị chặn hoặc chưa xác minh thực tế.

| Module | Routes / luồng | Nhóm | Bằng chứng và giới hạn |
|---|---|---:|---|
| Runtime/config | `/login`, `/healthz`, `/readyz`, `/workersz` | A/B | Flask Phase 3 khởi động lại thành công; browser QA `/healthz` và `/readyz` 200; clone `petcare_phase3_dev_clone` `/readyz` 200. `/workersz` vẫn 503 vì không chạy worker nền. Dev schema giữ 20 bảng/readiness 503; không ghi. |
| Auth/session | `/login`, `/logout`, `/stores/switch`, `/language` | B | Owner/admin và staff login/logout; store switch giữa tenant; chưa chạy invalid-password/rate-limit/browser recovery trong lượt này (backend tests có). |
| Dashboard | `/dashboard` | A | Metrics/activity/restock render; 390×844 mobile không overflow ở lượt Phase 2; 820×1180 tablet và 1440×900 desktop được mở ở Phase 3. |
| Customers | `/customers/`, detail/new/edit/active/deactivate | A/B | Search, create invalid/valid, detail, edit và persistence PASS; deactivate/reactivate và mọi pagination/filter boundary chưa đi hết bằng browser. |
| Pets / media | `/pets/`, detail/new/edit/active/deactivate, find-similar, suggest-attributes | B | CRUD create/read, form validation recovery, photo upload, local similarity PASS. Camera, deactivation, mọi field boundary và Vision thật chưa thử. |
| Products / inventory | `/products/`, detail/new/edit/stock/active/deactivate | A/B | Search, create duplicate/valid, edit, stock adjustment và ledger đã thấy. Active/deactivate và concurrency chỉ dựa test tự động. |
| POS / invoice | `/invoices/`, new, detail, pay, cancel, refund | B | Create/pay/cancel đã chạy ở DB QA; invalid quantity estimate được sửa. Mobile cart bar thực tế hiện count/tổng và link `#pos-order`; browser 390×844 xác nhận 1 món/55.000 VND và link tới giỏ. MySQL route integration mới cover refund partial/full, duplicate request, over-refund, stock/ledger consistency và rollback. Browser refund POST chưa xác minh vì confirm dialog không được browser control giữ lại; không có payment gateway. |
| Purchasing | `/purchasing/`, new/detail/receive/cancel, suppliers | A/B | Supplier create, PO create, partial/full receive và cancel đã chạy; stock/state hiển thị đúng. Request replay/idempotency, rollback và invalid payload được cover integration suite, không browser replay. |
| Reports/export | `/reports/`, `/reports/export.xlsx`, `/users/export` | A/B | Report filter và XLSX vẫn PASS. Tenant export browser: mismatch bị từ chối; yêu cầu hợp lệ queue job trong schema QA; worker one-shot hoàn tất; UI status `ready`, heading sau fix là “Export ready”; gói tải xuống có header `PCEXP001` và giữ ở `/tmp` với mode 0600. Worker chạy liên tục, print/PDF và passphrase decrypt chưa được browser-tested. |
| Local assistant | `/assistant/chat` | A | Panel hiển thị rõ local mode, query low-stock trả kết quả từ store. Chưa thử hết intent/empty/error/rate-limit qua browser. |
| Generative AI | Optional provider trong `petcare/ai/client.py` | E | Mã và fallback được unit/integration test; endpoint/key trống, provider thật không gọi. |
| AI Vision / gợi ý attributes | `/pets/suggest-attributes`, image search | E/B | Local color suggestion và image ranking được thử; model Vision thật, độ chính xác và provider privacy chưa xác minh. |
| Store settings | `/store/settings` | B | Trang render và staff bị 403; update valid/invalid chỉ cover backend tests, không submit browser. |
| Team, invitation, ownership | `/users/`, `/users/ownership`, `/users/invitations/*` | E | Trang owner/team render, trang ownership báo chưa có target admin; không gửi invite, tạo credential, transfer hay accept. SMTP off. |
| Account/password/email | `/account/settings`, recovery/verify/reset | B/E | Browser staff cập nhật display name bằng account seed, nhận feedback và khôi phục tên gốc; thay đổi/recovery/email/password credentials chưa submit. SMTP off. |
| Tenant export | `/users/export`, status/download | A/B | Browser submit mismatch và queue job thành công; worker local xử lý job (attempt đầu thất bại vì lệnh test dùng sai media path, retry đúng config đạt `ready`); tải bundle mã hóa được. Heading theo trạng thái đã sửa. Quyền tenant/requester, crypto, retention và failure logic còn integration tests riêng; SMTP/S3 không tham gia. |
| Activity/audit | `/activity/` | B | Admin page render, staff nhận 403; filter/history semantics không rà hết bằng browser. |
| Metrics | `/metrics` | E | Trả 404 vì `OPS_METRICS_TOKEN` để trống; đây là cấu hình disabled. |
| Responsive / navigation | Dashboard/POS | B | Tablet 820×1180 có horizontal overflow trong nav (`830 > 642`), CSS scrollbar và fade hint; Reports mở được qua nav. Mobile POS ở 390×844 có preview và anchor; `document.scrollWidth=390`, không tràn ngang. Desktop dashboard 1440×900 `document.scrollWidth=1440`. Chưa kiểm mọi trang tại mọi breakpoint. |
| Accessibility | Tất cả templates | E/B | Quan sát spot DOM labels/landmarks của POS; chưa có screen reader, contrast, keyboard toàn site, zoom 200% hay WCAG audit. |
| Browser network | Tất cả routes | E | Console error/warning rỗng sau browser checks Phase 3. `/static/favicon.svg` trả 200; request mặc định `/favicon.ico` còn 404. `/workersz` 503 do worker không chạy nền; `/metrics` disabled. Network panel request-level vẫn chưa có trong CUA. |
| Clinic/appointment/vaccination | Không có route web hiện hành | Ngoài scope | Các module này nằm trong archive/legacy; scope hiện hành là quản lý cửa hàng thú cưng. |

Không có module nào được xếp D sau khi fix và retest các lỗi đã xác nhận. Các mục E có thể vẫn hoạt động theo unit/MySQL tests; E chỉ nói chưa xác minh bằng browser/provider thật ở Phase 2.
