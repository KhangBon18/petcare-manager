# Roadmap nâng cấp tổng thể

Ngày lập: 2026-11-09. Bảo toàn scope retail Petcare Manager; chưa đề xuất thay framework hay viết lại kiến trúc.

## Cập nhật Phase 5.2 — Vision stabilization — 2026-11-10

- **DONE local/test:** gợi ý thuộc tính ngoại hình trong form thú cưng hiện có; admin review, apply chỉ vào ô trống, không auto-save. Output field allowlist/cap, provider/fallback status và JSON errors rõ ràng.
- **Verification:** Python **389/389**, JavaScript **34/34**, Chromium **15/15**; MySQL route integration, viewport 320–1440, /healthz=200, /readyz=200, exact Bandit gate, both pip-audit locks, pip check, compileall, Compose config và Docker build pass.
- **Data/DB:** chỉ schema disposable petcare_phase52_test trên Compose tmpfs và storage tạm. petcare_shop_dev/production không được kết nối hoặc sửa. Không có schema migration.
- **Limitations:** mock loopback + synthetic illustrations chỉ kiểm pipeline, không đo accuracy. Hosted CI, Trivy secret scan, screen reader, live provider, SMTP/S3 chưa chạy. Provider thật **NO-GO** cho đến approval/data rights/privacy/retention/region/budget và benchmark per-field.
- **Hồ sơ:** [implementation](PHASE52_VISION_IMPLEMENTATION.md), [architecture](PHASE52_VISION_ARCHITECTURE.md), [evaluation](PHASE52_VISION_EVALUATION.md), [security](PHASE52_VISION_SECURITY.md), [UX](PHASE52_VISION_UX.md), [Phase 5.3 readiness](PHASE53_PROVIDER_READINESS.md).
- **Thứ tự kế tiếp:** (1) không mở dev readiness migration trước backup/approval hiện hành; (2) hoàn tất dataset + benchmark/provider approvals; (3) chạy staging smoke và hosted CI; (4) tiếp tục screen-reader/a11y audit; (5) chỉ sau đó cân nhắc bật provider; optional features giữ ngoài scope.

## Cập nhật Phase 5.1.1 — Regression recovery — 2026-11-10

- **DONE local:** regression fixtures được sửa để truyền tenant tường minh, chọn record có tenant/deterministic ordering, và dọn audit/record do test sở hữu. Thêm `compose.qa-test.yml` để chạy MySQL 8.4 QA disposable trên tmpfs; app, DB, media và Playwright chỉ dùng vùng test tạm.
- **Verification:** Python **380/380** hai lượt (unit 228, web 86, MySQL integration 66); AI target **8 passed + 13 subtests**; JavaScript **31/31**; Playwright **11/11** hai lượt. Bandit CI command, pip-audit cho hai lockfiles, `pip check`, compileall, Compose parse, Docker build và `git diff --check` PASS.
- **Root cause classification:** các test thất bại ở baseline QA tái sử dụng được quy về tenant fixture không tường minh, lựa chọn record thiếu scope/determinism và media/database fixture contamination. Không tái hiện được defect logic ứng dụng trên DB/storage sạch; historical traces không đầy đủ nên lỗi cũ không được trích dẫn như exception đã tái hiện.
- **Limitations:** GitHub-hosted CI, live SMTP/AI/Vision/S3, full accessibility, load/branch coverage chưa được kiểm thử. `petcare_shop_dev` readiness không được kiểm tra lại trong sprint này; không có schema/data mutation nào dev/prod.
- **Phase 5.2:** **GO có điều kiện** cho implementation/evaluation chỉ trên schema `_test` disposable, synthetic/được phép media, mock/provider staging không phát sinh phí ngoài phê duyệt hiện có. **NO-GO** cho live provider, dev/prod DB mutation hoặc tuyên bố production readiness nếu chưa có approval và kiểm chứng riêng.
- **Hồ sơ:** [recovery](PHASE511_REGRESSION_RECOVERY.md), [test isolation](QA_TEST_ISOLATION.md), [final test results](PHASE511_FINAL_TEST_RESULTS.md), [Phase 5.2 start readiness](PHASE52_START_READINESS.md), [coverage gaps](TEST_COVERAGE_GAPS.md).

## Cập nhật Phase 5.1 — 2026-11-10

Ghi chú: đây là hồ sơ lịch sử trước regression recovery. Các kết quả full-suite FAIL bên dưới đã được thay thế bởi Phase 5.1.1; xem [ma trận kiểm thử hiện tại](TEST_MATRIX.md).

- **DONE local:** assistant có truy vấn top sản phẩm theo kỳ từ report service/MySQL tenant hiện tại; trả lời VI/EN, tối đa 5 sản phẩm, ngày/kỳ, quantity/revenue và link hồ sơ. Nhánh insight không gọi provider.
- **Verification:** baseline grounding 0/2, sau thay đổi 2/2 theo hai case cụ thể; unit+web pytest 314 passed, AI unit+MySQL target 8 passed, JS 31/31, browser test mới 1/1. Full Python regression 380 tests có 2 failures/15 errors/0 skip; full browser 11 tests có 6 failures/1 error ở QA fixture/storage cũ. Bandit, pip audits, compile, package check, Compose parse, diff check và Docker build PASS.
- **DB/privacy:** chỉ dùng schema QA hậu tố `_test`; readiness `/readyz=200`; không thay schema dev/production, không gọi provider thật, Vision, SMTP hay S3. QA user không có quyền tạo schema mới nên không dọn dữ liệu cũ.
- **Hồ sơ:** [implementation](PHASE51_AI_IMPLEMENTATION.md), [capability](PHASE51_AI_CAPABILITY_MATRIX.md), [evaluation](PHASE51_AI_EVALUATION.md), [security](PHASE51_AI_SECURITY.md), [UX](PHASE51_AI_UX.md), [Vision handoff](PHASE52_VISION_HANDOFF.md).
- **Kế tiếp:** xử lý test-isolation/media fixtures và chạy lại full regression trên schema QA sạch được provision đúng quyền; sau đó Phase 5.2 đánh giá Vision bằng bộ ảnh synthetic/được phép và provider staging có budget approval.

## Cập nhật Sprint 4.3 — 2026-11-10

- **DONE local:** purchasing list/detail responsive cards, điền số còn thiếu có keyboard feedback và giữ bước submit thủ công; PO lifecycle browser đối chiếu stock/movements trên MySQL QA.
- **DONE local:** report product cards và selected-period semantics; custom range/XLSX và giá trị report được kiểm với service.
- **DONE local:** tenant export pending → worker one-shot → ready/download; metadata và nội dung hướng dẫn theo một số error code được bổ sung.
- **DONE local:** POS catalog retry phục hồi sau HTTP 503 mà giữ cart; axe contrast/header findings được sửa.
- **Verification:** Python 372/372, JS 30/30, Playwright 10/10, axe 26 targeted scans/0 violations, Bandit CI exact gate, both pip-audit lockfiles, pip check, compileall, Compose parse và diff check PASS. Hosted CI chưa quan sát.
- **DB boundary:** chỉ schema `petcare_phase3_browser_test` (`_test`) và local QA storage; readiness QA 200. Dev/production schema không bị sửa.
- **Hồ sơ:** [Sprint 4.3 report](PHASE43_IMPLEMENTATION_REPORT.md), [Purchasing UX](PHASE43_PURCHASING_UX.md), [Reports UX](PHASE43_REPORTS_UX.md), [Operations UX](PHASE43_OPERATIONS_UX.md), [visual QA](PHASE43_VISUAL_QA.md), [Phase 5 AI handoff](PHASE5_AI_HANDOFF.md).

## Cập nhật Sprint 4.2 — 2026-11-10

- **DONE local:** product list ≤680px thành card có nhãn field; POS mobile sticky summary được giữ sau khi test xác nhận count/total/anchor; inventory negative-stock validation, stock ledger và paid checkout đối chiếu với MySQL QA.
- **DONE local:** customer purchased-pet relation phân trang 12/trang độc lập với invoice history; 13-record browser fixture cho thấy pet thứ 13 ở page 2. Không có database schema change.
- **DONE local:** hai màu chữ dưới contrast target và hai accessible-name mismatch được sửa. Axe 4.14.0: 13 targeted scans/0 violations; có 13 `incomplete` results còn cần manual review.
- **Verification:** Python 372/372, JS 28/28, Playwright 6/6, exact Bandit CI gate, both pip-audit locks, `pip check`, compile, Compose parse và diff check PASS. Hosted CI chưa quan sát.
- **DB boundary:** chỉ dùng `petcare_phase3_browser_test` `_test`; QA readiness 200. `petcare_shop_dev` vẫn readiness 503 và không bị sửa.
- **Hồ sơ:** [Sprint 4.2 report](PHASE42_IMPLEMENTATION_REPORT.md), [Product/Inventory UX](PHASE42_PRODUCT_INVENTORY_UX.md), [POS UX](PHASE42_POS_UX.md), [visual QA](PHASE42_VISUAL_QA.md), [next sprint](PHASE42_NEXT_SPRINT.md).

## Cập nhật Phase 3.5 — 2026-11-09

- Browser refund flow đã chạy thật trên Flask + MySQL QA: confirm accept/dismiss, zero/over-refund, partial/full, retry cùng request key, ledger và tồn kho đều được đối chiếu. Smoke runner được nối vào GitHub Actions; local suite **3/3 PASS**. Hosted GitHub Actions job chưa chạy trong lượt này.
- Python **369/369 PASS**, JavaScript **28/28 PASS**, Bandit đúng lệnh CI PASS, `pip-audit` cho runtime/browser lock PASS, `pip check`, compileall, Compose parse, workflow YAML parse và `git diff --check` PASS.
- Dev preflight đọc lại: 20 bảng, một marker, thiếu sáu bảng, bốn cột, bốn index và các FK purchasing/refund; `/readyz=503`. Không có backup dev mới/restorable được xác minh trong repository, nên migration có quyết định **NO-GO**. Xem [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md).
- Phase 4 có thể bắt đầu product modernization trên schema `_test`; trước bất kỳ mutation dev nào phải hoàn tất backup/restore evidence và nhận xác nhận tường minh.

Độ phức tạp: S = tối đa 1 ngày; M = 2–5 ngày; L = hơn 5 ngày. Ước lượng tương đối, cần chia nhỏ trước khi thực hiện.

## 1. Sửa defect còn lại

| Ưu tiên | Module / vấn đề | Giải pháp | Lợi ích / phụ thuộc | Độ phức tạp | Tiêu chí nghiệm thu |
|---|---|---|---|---:|---|
| P1 | `petcare_shop_dev` readiness 503 và money checks cũ | **Phase 3 đã rehearsal trên clone**: 20→26 bảng, marker 1→4, readiness clone 200; phát hiện check constraint còn tham chiếu cột `_vnd` sau `CREATE TABLE IF NOT EXISTS` và bổ sung migration kiểm dữ liệu rồi thay check trên cột Decimal. DB dev chưa thay đổi. Chỉ triển khai theo `docs/DB_READINESS_REMEDIATION.md` sau backup/restore được xác minh và duyệt DDL. | Khôi phục readiness và bảo toàn invariant tiền; DDL MySQL auto-commit vẫn cần kiểm soát. | M | Sau phê duyệt, `/readyz` dev 200, check bảo vệ cột Decimal, row counts nghiệp vụ giữ nguyên ngoài marker và bảng mới rỗng. |
| P2 | Pet/product form recovery, POS estimate và mobile money (3 fix Phase 2) | Giữ regression tests hiện có. | Ngăn tái phát lỗi nhập liệu và tính giá. | S | Full Python/JS pass; browser giữ values, estimate 0 và tiền không vỡ chữ. |
| P2 | Tablet nav, POS cart mobile, tiêu đề trạng thái tenant export (3 fix Phase 3) | Giữ breakpoint regression và trạng thái export có điều kiện theo job. | Làm rõ thao tác và kết quả công việc ở viewport/luồng tương ứng. | S | Browser thấy fade nav tại 820 px, cart preview ở 390 px, export heading khớp `ready`; không tràn trang. |
| P3 | NET-01 `/favicon.ico` vẫn 404 | Giữ icon SVG cùng-origin; cân nhắc alias same-origin cho `.ico` nếu access logs cần sạch. | Loại bỏ một request mặc định thất bại. | S | `/static/favicon.svg` 200; nếu thêm alias thì `/favicon.ico` 200 và không phát sinh lỗi console. |

## 2. Hoàn tất luồng và QA

| Ưu tiên | Module / vấn đề | Giải pháp | Lợi ích / phụ thuộc | Độ phức tạp | Tiêu chí nghiệm thu |
|---|---|---|---|---:|---|
| P2 · DONE LOCAL / CI WIRED | Browser regression chưa chạy trong CI | Phase 3.5 thêm Playwright smoke job dùng MySQL service/schema riêng, app process thật, isolated storage, diagnostics, screenshots/traces và artifact upload. Local browser suite 3/3 pass. | Bảo vệ UI/API contract qua mỗi thay đổi. | M | Local suite đã pass; lần chạy GitHub Actions hosted vẫn cần quan sát sau push/PR. |
| P2 | Invitation, password recovery, email verification, ownership transfer | Bổ sung browser workflow synthetic/test-only và mail outbox stub; không gửi SMTP thật. | Nâng độ tin cậy onboarding/admin security. | M | Token one-time/expiry, role, requester/tenant isolation và recovery states được assert trên browser + MySQL. |
| P2 · DONE theo smoke scope | Refund submit chưa xác minh qua browser | Browser 3.5 điều khiển confirm dialog và đối chiếu UI với MySQL ledger/tồn. Route/MySQL suite hiện có tiếp tục bao phủ rollback. | Xác nhận trải nghiệm form và phản hồi route cùng business rules đã kiểm. | S–M | Đã pass partial/full, invalid, replay, cancel-confirm; không gọi payment gateway. CI hosted chưa chạy. |
| P2 · DONE theo smoke scope | Network requests chưa capture | Playwright lưu method/path/status và failed-request tổng hợp; không lưu headers hay bodies. | Phân biệt lỗi request với 403 role restriction dự kiến. | S–M | Không có failed request hoặc response lỗi bất ngờ trong smoke; 403 `/users/` của staff được xác nhận là expected. |
| P2 | Accessibility audit mới là spot check | Keyboard-only, axe/WAVE, screen reader spot check trên login, dashboard, POS, pet image, reports, dialogs. | Bắt lỗi focus order/name/contrast không thấy từ DOM-only. | M | Không có critical/serious accessibility finding; labels, landmarks, focus, dialog close/return focus và zoom 200% đạt acceptance cụ thể. |

## 3. Cải thiện backend và vận hành

| Ưu tiên | Module / vấn đề | Giải pháp | Lợi ích / phụ thuộc | Độ phức tạp | Tiêu chí nghiệm thu |
|---|---|---|---|---:|---|
| P2 | `/workersz` 503 khi chưa bật workers | Cho local/dev profile rõ worker mode; health panel phân biệt web-ready với worker-not-configured. Không giả heartbeat. | Tăng khả năng chẩn đoán. | S | `/readyz` vẫn chỉ kiểm DB/schema; `/workersz` chỉ 200 với heartbeat thật, hướng dẫn config local hiển thị rõ. |
| P2 · VERIFIED Python 3.13 | Lockfile reproducibility | Runtime `requirements.lock` có từ Phase 1.5; Phase 3.5 thêm exact browser-only `requirements-browser.lock`, cài cả hai cùng runtime vào clean venv. | Giảm dependency drift, tách Playwright khỏi runtime. | S | Clean Python 3.13 install + `pip check` + Playwright 1.64.1 PASS; full suites/audits PASS ở checkout. Matrix hosted Python 3.11–3.13 vẫn chưa quan sát. |
| P3 | Network/slow external work | Đo baseline; chỉ tách queue nếu SMTP/AI/export thực tế gây blocking. Không thêm queue orchestration nếu không có dữ liệu. | Hạn chế enterprise complexity, có số liệu trước khi tối ưu. | M | Load test có ngưỡng latency/error được sản phẩm chấp nhận và kết quả lặp lại được. |

## 4. UI/UX modernization có kiểm soát

| Ưu tiên | Module / vấn đề | Giải pháp | Lợi ích / phụ thuộc | Độ phức tạp | Tiêu chí nghiệm thu |
|---|---|---|---|---:|---|
| P3 · DONE Phase 3 | Tablet navigation cuộn ngang | Scrollbar styling và fade ở mép phải trong 681–980 px. Browser 820×1180 mở được Reports qua nav; document không overflow. | Tăng khả năng thấy phần menu bị khuất. | S | Retest browser: nav `scrollWidth 830`/`clientWidth 642`, fade CSS được áp dụng; desktop nav không bị đổi. |
| P3 · DONE Phase 3 | POS cart ở dưới catalog mobile | Thêm thanh cart sticky có count/tổng và link tới `#pos-order`. | Bớt cuộn trong workflow bán hàng. | S | Browser 390×844: 1 món/55.000 VND, link đưa tới order summary; JS regression preview pass; không gửi invoice. |
| P2 · DONE Phase 3 | Tiêu đề tenant export luôn ghi “Processing request” | Heading thay theo pending/processing/ready/failed/expired; test VI/EN. | Tránh trạng thái trang mâu thuẫn với worker/download. | S | Job `ready` hiển thị “Export ready” và link download; web test cho đủ năm trạng thái. |
| P3 | Thiếu favicon | Static icon brand. | Hoàn thiện trình duyệt/tab. | S | Request trả 200. |

## 5. Cải thiện AI

| Ưu tiên | Module / vấn đề | Giải pháp | Lợi ích / phụ thuộc | Độ phức tạp | Tiêu chí nghiệm thu |
|---|---|---|---|---:|---|
| P2 | Provider thật chưa được đánh giá | Dùng endpoint staging được duyệt, bộ câu hỏi/ảnh tổng hợp, mock fallback và theo dõi latency/cost. Chỉ dùng data synthetic trước. | Biết chất lượng/cost trước khi bật cho store thật. | M | Structured output chính xác, fallback khi timeout/429/malformed, không rò PII, budget/latency giới hạn, không gọi production data. |
| P2 | Vision chưa có accuracy benchmark | Tạo evaluation set ảnh có quyền, precision/recall cho loài/màu/giống; giữ người dùng duyệt mọi gợi ý. | Không biến output model thành sự thật dữ liệu. | M | Báo cáo metric theo field và failure class; local fallback không mất input; không auto-save. |
| P3 | Local assistant intent | Mở rộng câu hỏi chỉ khi có nhu cầu từ users; giữ exact count/preview semantics. | Cải thiện hữu ích mà không bắt buộc provider trả phí. | S–M | Bộ intent đa ngôn ngữ, không hallucinate totals, fallback local được kiểm bằng tests. |

## 6. Optional features

Chưa bắt đầu clinic/appointments/vaccinations, loyalty, multi-warehouse hoặc analytics nâng cao. Đây là scope mới; cần yêu cầu sản phẩm/academic rubric riêng. Chỉ xem xét sau khi migrations, browser regression, security/provider và accessibility gates đạt.

## Thứ tự triển khai sau Sprint 4.3

1. Review axe incomplete bằng keyboard-only, screen reader và browser chrome zoom 200%; ghi rõ browser/AT/criterion, không xem axe là chứng nhận WCAG.
2. Browser-test export failure/error mapping và permission/requester transitions; giữ SMTP/S3 tắt, dùng fixtures `_test`.
3. Quan sát GitHub Actions hosted jobs, Trivy secret/image gates và browser artifacts; local checks chưa chứng minh hosted workflow.
4. Trước DDL trên `petcare_shop_dev`, tạo backup mới, verify và diễn tập restore riêng; sau đó xin duyệt tường minh. Xem [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md).
5. Phase 5: đánh giá AI/Vision trên staging được duyệt với câu hỏi/ảnh tổng hợp, budget, latency, egress, fallback và accuracy criteria. Xem [AI handoff](PHASE5_AI_HANDOFF.md); không tự bật production.
6. Chỉ thêm clinic/loyalty/warehouse hoặc scope học thuật mở rộng sau khi có yêu cầu sản phẩm riêng.

## Cập nhật Phase 5.3B — provider evaluation preflight — 2026-11-10

- **PRE-FLIGHT HOÀN TẤT; live pilot BLOCKED.** Không gọi provider, không truyền ảnh, không bật Vision cho users và không sửa DB development/production.
- Manifest có 2 ảnh synthetic mechanics-only/4 construction labels; ảnh đủ điều kiện egress có chứng cứ hiện là **0**. Không có annotator independence, held-out real split hoặc abstention examples. Real accuracy/latency/token/cost vẫn **NOT MEASURED**.
- Candidate để xem xét: OpenAI GPT-6 Luna qua Chat Completions do gần adapter hiện có và model docs xác nhận image/structured output; chưa xác minh request parameters/account privacy/region. OpenAI hard spend enforcement có thể trễ và hơi vượt; hiện chưa có app-level global attempt/spend guard.
- Đề xuất 50 attempts / 0 retries / USD 1 cần approval, chưa được cấu hình. Không thể khẳng định tổng spend tuyệt đối ≤ USD 1 bằng provider cap hiện tại.
- **Thứ tự tiếp theo:** (1) nhận dataset ≤50 ảnh cùng rights/consent egress và labels/rubric độc lập; (2) quyết định provider project/region/retention/privacy; (3) triển khai offline-test local fail-closed count/spend guard và verify exact model request schema; (4) xin approval package cụ thể; (5) chỉ khi approved mới chạy staging pilot một request/ảnh, rồi chấm offline; (6) giữ production provider tắt và manual apply/no autosave.
- **Regression xác nhận Phase 5.3B:** Python 405/405, JS 36/36, Playwright 16/16 sau chọn port Chromium an toàn, Vision offline CLI PASS; Bandit baseline, pip/npm audit, `pip check`, compile, Compose, Docker build, health/readiness QA và diff check PASS. Provider live/quality metrics NOT TESTED; không chạy hosted CI/Trivy.
- Hồ sơ: [implementation](PHASE53B_IMPLEMENTATION.md), [provider pilot gate](PHASE53B_PROVIDER_PILOT.md), [model evaluation](PHASE53B_MODEL_EVALUATION.md), [cost/latency](PHASE53B_COST_AND_LATENCY.md), [security](PHASE53B_SECURITY_REVIEW.md), [Phase 5.4 handoff](PHASE54_AI_INTEGRATION_HANDOFF.md).

## Cập nhật Phase 5.4 — assistant đa module — 2026-11-10

- **DONE / VERIFIED local:** thêm inventory restock insight và purchase-order status insight qua service có sẵn. Inventory dành cho thành viên active trong tenant; purchasing chỉ admin. Cả hai read-only, deterministic, tối đa 8 rows, route tự tạo same-origin link/nhãn tiền/thời gian.
- **Regression:** Python 413/413 (0 skip), JavaScript 38/38, Playwright 17/17 (0 skip); disposable MySQL route/browser; `/healthz=200`, `/readyz=200`; Bandit gate pass; hai pip-audit không có known vulnerabilities, npm audit 0, `pip check`, compileall, Compose config, Docker build và diff check pass. Xem [test matrix](TEST_MATRIX.md) và [implementation](PHASE54_IMPLEMENTATION.md).
- **Bảo mật/evaluation:** prompt injection và payload tenant override không đổi query scope; staff không thấy PO data; new intent không gọi provider dù test mock đánh dấu configured. Axe targeted 3 state: 0 violations, 40 incomplete nodes chờ kiểm tra thủ công.
- **Git/DB:** có restorable checkpoint, working tree có thay đổi từ trước; không stage/commit/reset/clean/stash. Chỉ các schema QA `_test` Compose tmpfs được dùng; không chạm dev/prod schema.
- **Giới hạn:** deterministic phrase matching; không hiểu tự do, không nhận date range tùy chỉnh. `restock_service` đọc mọi product active để tính exact count; response assistant chỉ trả 8. Không chạy screen reader/zoom thật, hosted CI, provider thật hay load test catalog lớn.

### Thứ tự triển khai tiếp theo

1. **Sửa lỗi hiện có:** chưa phát hiện lỗi P0/P1 trong scope Phase 5.4. Xem xét profiling inventory aggregation khi có catalog lớn; không thay công thức tồn kho nếu chưa có regression đối chiếu.
2. **Hoàn tất chức năng:** thu thập câu hỏi người dùng thật (ẩn danh/synthetic) để xác nhận alias VI/EN/clarification; nếu cần custom period, dùng period allowlist/report service hiện tại, không truyền ngày tự do vào SQL.
3. **Ổn định kiến trúc:** giữ registry nhỏ và service boundaries. Chỉ trích query aggregate khi benchmark chứng minh cần; thêm test exact count/tenant/filter trước tối ưu. Không thêm framework/queue.
4. **Frontend/UX:** đọc 40 axe incomplete bằng keyboard-only, assistive technology và zoom browser thật; xác minh panel, focus, contrast, clipping và retry với người dùng. Safari/Firefox chỉ thêm nếu môi trường học thuật/product yêu cầu.
5. **AI:** giữ hai capability deterministic. Chỉ mở cổng pilot provider khi hoàn tất rights/consent dataset, independent rubric, privacy/region/retention, request compatibility, cost/attempt guard và phê duyệt nêu trong `PHASE53B_PROVIDER_PILOT.md`.
6. **Optional:** không thêm chức năng tự tạo/nhận/hủy PO hoặc sửa tồn bằng chat, appointment, loyalty hay warehouse trong Phase 5.5 mặc định; cần scope/product approval riêng.

Handoff: [Phase 5.5](PHASE55_HANDOFF.md); chi tiết [capabilities](PHASE54_AI_CAPABILITIES.md), [evaluation](PHASE54_AI_EVALUATION.md), [security](PHASE54_AI_SECURITY.md), [UX](PHASE54_AI_UX.md).
# Phase 5.3A update — 2026-11-10

Vision quality infrastructure is implemented with a no-provider scoring harness, synthetic-only fixture set, guarded mock transport, bounded retry and targeted keyboard/axe browser checks. Mock score is mechanics-only; real model accuracy remains **NOT MEASURED**. No real provider, dev DB or production DB was touched. Local gates: Python 405/405, JavaScript 36/36, Chromium 16/16; Bandit CI gate, lockfile audits, pip/npm checks, compile, Compose config and local Docker build pass. GitHub-hosted CI and Trivy remain NOT TESTED. Details: [Phase 5.3A implementation](PHASE53A_IMPLEMENTATION.md), [benchmark](VISION_BENCHMARK_SPEC.md), [privacy/cost](VISION_PRIVACY_AND_COST.md), [approval protocol](PHASE53B_PROVIDER_APPROVAL.md).

### Next work, ordered by risk

1. **Fix existing defects:** retain safe adapter error normalization and no-external-egress test guard; review the existing baseline B608 `nosec` warnings independently before widening/altering the Bandit baseline.
2. **Complete unfinished functionality:** collect authorized and independently annotated Vision samples; complete ambiguous/poor-light/occluded/multi-pet/non-pet/missing-evidence/conflict scenarios. Do not activate a provider until Phase 5.3B gates are signed.
3. **Refactor/stabilize architecture:** only after evidence, consider provider-specific response-format support and provider transport adapter. Keep Flask/Jinja/MySQL and the current request boundary; avoid unrelated rewrites.
4. **Frontend/UX:** follow up with manual screen-reader, true 200% browser zoom, reduced-motion and cross-browser review; preserve manual apply, dismiss, no autosave and stale-response protection.
5. **AI capability:** execute an explicitly approved capped staging pilot, then evaluate on held-out licensed data. Make no accuracy claim from mock output.
6. **Optional features:** provider comparisons, confidence displays, bulk suggestions, or automated form updates are deferred; add only with a separately approved product need and safety evidence.
