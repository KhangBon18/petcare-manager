# Phạm vi coverage và khoảng trống còn lại

## Cập nhật Phase 5.2 — 2026-11-10

| Phạm vi | Trạng thái hiện tại | Khoảng trống / giới hạn |
|---|---|---|
| Python regression | VERIFIED | 389/389 pass, 0 skip trên petcare_phase52_test. |
| Vision route/storage/security | VERIFIED theo mock scope | MySQL route test xác nhận session tenant, admin, CSRF, không lưu ảnh suggestion và metadata removal; không dùng dữ liệu thật. |
| Vision browser/JS | VERIFIED theo smoke scope | 34 JavaScript và 15 Chromium tests pass; viewport 320–1440, retry/error states và safe apply. |
| Vision model quality | NOT TESTED | Synthetic illustrations và deterministic mock không đo precision/recall/abstain. Cần ảnh có quyền, nhãn độc lập và ngưỡng per-field. |
| Live provider, SMTP, S3 | NOT TESTED | Không phát sinh egress/chi phí; provider staging chưa được phê duyệt hoặc đo retention/region/cost. |
| A11y and hosted CI | PARTIAL / NOT TESTED | Keyboard apply, labels và aria-live được kiểm; chưa screen reader/axe/full WCAG, Trivy CLI hoặc hosted GitHub Actions. |
| Dev readiness | NOT RESOLVED / NOT TOUCHED | Phase 5.2 chỉ dùng test schema; dev readiness 503 là trạng thái baseline trước đó. Không chạy migration hay ghi dev/production. |

Verification details: [Phase 5.2 results](PHASE52_VISION_IMPLEMENTATION.md), [evaluation](PHASE52_VISION_EVALUATION.md), [security](PHASE52_VISION_SECURITY.md), [provider gate](PHASE53_PROVIDER_READINESS.md).

## Cập nhật Phase 5.1.1 — 2026-11-10

| Phạm vi | Trạng thái hiện tại | Khoảng trống / giới hạn |
|---|---|---|
| Python regression | VERIFIED | 380/380 pass trong hai lượt độc lập; unit 228, web 86, MySQL integration 66. Không có skipped test. |
| Purchase order MySQL lifecycle | VERIFIED theo integration scope | 66 MySQL integration tests cùng full suite pass trên schema disposable; các fixture dùng tenant tường minh và dọn audit/data do test tạo. Hosted CI chưa quan sát. |
| AI Assistant regression | VERIFIED theo local/mock scope | 8 pytest pass, 13 subtests; JavaScript và browser full regression cũng pass. Không xác minh provider thật, chi phí, rate limits hoặc live model drift. |
| Browser regression | VERIFIED theo smoke scope | Playwright 11/11 trong hai lượt; không có page error, failed request hoặc HTTP bất ngờ. 403 `/users/` với staff là expected authorization. Đây không phải kiểm thử CRUD end-to-end mọi route. |
| Test isolation | VERIFIED local | MySQL 8.4 service dùng tmpfs, schema test riêng, app/storage/browser artifacts dưới thư mục tạm quyền owner-only; teardown kiểm tra fixture và audit orphan không còn. Không dùng `petcare_shop_dev` hoặc production. |
| Security/dependency gates | VERIFIED local | Bandit command CI exit 0; hai lockfiles qua `pip-audit`; `pip check` pass. Bandit có `nosec` B608 warnings được giải thích trong `CI_SECURITY_REVIEW.md`. GitHub-hosted workflow chưa chạy. |
| Environment and UI assurance | NOT TESTED / PARTIAL | Chưa chạy GitHub-hosted CI, SMTP, live AI/Vision, S3, screen reader, axe/WAVE, keyboard-only toàn site, zoom 200%, accessibility audit đầy đủ, load/performance hoặc branch coverage. |
| Dev database readiness | NOT RESOLVED | `petcare_shop_dev` không thuộc test environment; trạng thái readiness trước đó 503. Không chạy DDL hoặc sửa dữ liệu trong Phase 5.1.1. Tham khảo [DB readiness remediation](DB_READINESS_REMEDIATION.md), cần backup/restore evidence và approval trước triển khai. |

Chi tiết kết quả có thể tái lập: [Phase 5.1.1 final results](PHASE511_FINAL_TEST_RESULTS.md), [QA isolation](QA_TEST_ISOLATION.md), [start readiness](PHASE52_START_READINESS.md).

## Cập nhật Phase 3.5 — 2026-11-09

| Workflow | Trạng thái Phase 3.5 | Khoảng trống còn lại |
|---|---|---|
| Refund browser submit/confirmation | VERIFIED trên QA | Admin browser test dismiss/accept native confirm, zero/over-refund, partial/full, retry cùng request key; UI feedback và MySQL refund ledger/stock được so sánh. Tài chính chỉ mô phỏng trong app, không gọi gateway. |
| Browser smoke CI | WIRED, local PASS | 3/3 Playwright tests pass trên MySQL + app process riêng; GitHub Actions workflow YAML parse pass nhưng hosted runner chưa được thực thi. Trivy chưa chạy. |
| Customer/pet/product/POS/purchasing/reports browser | VERIFIED navigation smoke | Admin đăng nhập và mở routes đại diện; POS thực hiện chọn item/giỏ mobile; chưa chạy CRUD browser end-to-end cho mỗi module. Purchase receiving lifecycle đã có MySQL integration suite ở Phase 1.5, nhưng không thuộc browser smoke này. |
| Role restrictions | VERIFIED một cặp route | Staff được customers và bị chặn `/users/`; các tổ hợp route/role còn lại không được duyệt toàn diện bằng browser. |
| Browser responsive/accessibility | PARTIAL | Tablet nav 820×1180, POS mobile 390×844, keyboard Tab trên stock form và DOM smoke cho main landmark/button/control labels đạt; chưa chạy screen reader, axe/WAVE, contrast, zoom 200% hay toàn bộ viewport matrix. |
| Network/console | VERIFIED theo smoke scope | Playwright không ghi request thất bại hay JS exceptions. 403 `/users/` là expected; browser diagnostic JSON giữ event/status. Không đo latency/performance hoặc kiểm tra mọi route. |
| Dev schema readiness | BLOCKED, GO/NO-GO = NO-GO | Dev read-only 20 tables/184 columns, marker UTC đơn, sáu bảng và bốn cột thiếu, `/readyz=503`; không thấy violation trong ba money invariant và tenant_id NULL checks. Chưa có backup dev mới/restorable được xác minh, nên chưa đủ điều kiện xin duyệt thực thi migration. |
| External integrations | NOT TESTED thật | SMTP delivery, remote AI/AI Vision, S3, worker daemon/heartbeat và provider failure/cost behavior chưa được gọi trong Phase 3.5. |

Test counts giữ ở **369 Python / 28 JavaScript**; thêm 3 browser smoke tests riêng, không cộng vào Python product suite. Không có coverage percentage, branch coverage, load test hoặc production acceptance claim.

## Cập nhật Phase 3 — 2026-11-09

Các dòng Phase 2 bên dưới là lịch sử tại thời điểm đó. Tình trạng mới sau khi chạy browser và MySQL suite riêng:

| Workflow | Trạng thái Phase 3 | Khoảng trống còn lại |
|---|---|---|
| Refund | VERIFIED qua route/MySQL integration | Partial/full refund, replay, over-refund, stock/ledger consistency và rollback đã chạy trên DB QA. Browser POST chưa xác minh vì CUA không giữ được native confirm dialog; không có payment gateway và không chuyển tiền thật. |
| Tenant export | VERIFIED một phần bằng browser thật | Mismatch bị từ chối; valid request được queue, worker one-shot tạo job `ready`, bundle mã hóa tải về. Chỉ xác minh header/kích thước; không giải mã. Không kiểm worker daemon liên tục, retry exhaustion hoặc S3. |
| Account/profile | VERIFIED một phần | Đổi display name và phục hồi giá trị gốc trên browser. Password change/reset, email verification, mail delivery chưa submit. |
| Role-based access | VERIFIED một phần | Admin/staff browser: dashboard staff được phép, `/users/` bị từ chối. Chưa duyệt mọi route/permission combination trên UI. |
| Browser error/recovery | PARTIAL | Export passphrase mismatch và form profile feedback được thử; browser console errors/warnings rỗng. Thiếu request-level network log và automation CI. |
| Responsive | VERIFIED tại viewport lấy mẫu | 390×844 POS cart bar, 820×1180 tablet navigation fade, 1440×900 desktop không tràn ngang. Các route, zoom, bàn phím và screen reader chưa rà hết. |
| Dev database readiness | BLOCKED pending explicit approval | Read-only clone của `petcare_shop_dev` được migrate thành công; dev vẫn 20 bảng, readiness 503, không có ghi schema/dữ liệu. Cần người dùng duyệt trước DDL và xác nhận backup/restore cho DB dev. |
| Accessibility | NOT TESTED đầy đủ | Chưa chạy keyboard-only toàn site, screen reader, contrast/WCAG, zoom 200% hoặc axe/WAVE. |
| Network requests | PARTIAL | Console error/warning rỗng; `/favicon.ico` 404 vẫn tồn tại, SVG 200. CUA không cung cấp danh sách request thất bại/thời gian. |
| SMTP/AI/AI Vision/S3 | NOT TESTED thật | Provider credentials intentionally blank; không gửi dữ liệu hoặc phát sinh phí. Mocks/local flows không chứng minh nhà cung cấp thật. |
| Trivy/GitHub Actions | NOT TESTED | Trivy CLI không cài và workflow CI hosted không chạy trong lượt này. |
| Load/branch coverage | NOT TESTED | Không có benchmark, concurrency stress hoặc branch-coverage report. |

Quality gates Phase 3: Python **369/369**, JS **28/28**, Bandit CI exact command PASS, `pip-audit`, `pip check`, compileall, Compose config, Docker image build và `git diff --check` PASS. Clone migration readiness PASS; development readiness vẫn BLOCKED. Bằng chứng theo lệnh xem [TEST_MATRIX.md](TEST_MATRIX.md) và [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md).

## Cập nhật Phase 2 — 2026-11-09

Browser audit Phase 2 đã chạy trên app thật, tài khoản owner/admin và staff, với DB/storage QA riêng. Do đó dòng Phase 1.5 dưới đây “browser journeys NOT TESTED” là lịch sử của giai đoạn đó; trạng thái mới:

| Workflow | Trạng thái Phase 2 | Khoảng trống |
|---|---|---|
| Dashboard, customers, pets, products, POS, invoice, purchasing, reports, local assistant | VERIFIED một phần bằng browser | Không rà mọi field/state ở mọi route; xem [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md). |
| Role admin/staff, tenant switch/isolation | VERIFIED một phần | Chưa tạo tài khoản admin thứ hai; chưa chạy toàn bộ invitation/ownership flow bằng UI. |
| Responsive | PARTIAL | 320/390/820/1440 px được lấy mẫu; không test mọi màn hình ở tất cả kích thước/zoom. Tablet nav cần cuộn ngang. |
| Accessibility | NOT TESTED đầy đủ | Spot check labels/landmarks POS; thiếu keyboard-only, screen reader, axe/WAVE, contrast và zoom audit. |
| Console | VERIFIED | Browser console error/warning rỗng. |
| Failed network requests | NOT TESTED đầy đủ | CUA không expose Network request list; access log cho thấy 404 favicon/metrics và 503 workersz dự kiến, không có 500/traceback. |
| Refund UI | PARTIAL | Form/detail xem được; không ghi refund ledger qua browser. Integration/unit suite vẫn cover service/business rules. |
| Report PDF/print | NOT TESTED | XLSX đã tải; không mở print dialog. |
| Account recovery, email verification, invitations, ownership transfer | NOT TESTED qua browser | SMTP không cấu hình; không submit email/token/password actions. |
| Tenant export job | NOT TESTED qua browser | Job/status/download không khởi chạy; backend có suite riêng. |
| Real AI/AI Vision, SMTP, S3 | BLOCKED/NOT TESTED | Endpoint/credential intentionally blank; không gửi dữ liệu/không phát sinh phí. Local assistant/image descriptor đã chạy. |
| Dev DB migration/readiness | BLOCKED pending approval | Không ghi schema dev; baseline `/readyz` 503. Xem `DB_READINESS_REMEDIATION.md`. |
| Trivy / image scan | NOT TESTED | Không chạy Trivy trong lượt này. |
| Performance/load/branch coverage | NOT TESTED | Chỉ correctness smoke và regression suite; không đo coverage percentage hay tải đồng thời. |

Regression fixes E2E-01/E2E-02/E2E-03 đã được re-run bằng full suite; không ghi thêm behavior chưa quan sát.

Ngày: 2026-11-09. Trạng thái mỗi mục chỉ áp dụng cho bằng chứng trong cột kết quả, không suy rộng thành browser E2E hoặc production acceptance.

## Purchase-order lifecycle

**VERIFIED:** `tests/integration/test_mysql_purchasing.py` chạy bốn workflow trên MySQL `_test` thật:

- Tạo đơn qua route có CSRF; tạo snapshot giá/tổng; tồn kho không tăng khi mới đặt.
- Nhận một phần, nhận hết, kiểm stock movements/quantity/status; nhận sau khi đã đóng bị chặn.
- Từ chối sản phẩm lặp, quantity không hợp lệ, over-receive, cancel/receive sau state đóng; hủy đơn đang nhận dở giữ nguyên lượng đã nhận.
- Replay cùng UUID + cùng payload không tăng tồn; dùng lại UUID với payload khác bị conflict; một UUID mới là lần nhận mới.
- Lỗi được chèn sau khi line đầu đã ghi movement làm rollback stock, received quantity, trạng thái, receipt request và audit event.

Fixture chỉ dùng supplier/product/order tổng hợp sinh UUID, ghi vào schema test riêng, và xóa đúng các row do test tạo. Không dùng business data ở DB dev.

## Các giới hạn còn lại

| Workflow | Trạng thái | Khoảng trống |
|---|---|---|
| Purchase routes + service + repository + MySQL | PASS theo bốn workflow trên | Chưa có tải đồng thời nhiều admin gửi cùng request key; khóa order và unique request key được kiểm qua logic/DDL, chưa có stress test concurrency. |
| Dev database readiness | BLOCKED | Không chạy migration trên `petcare_shop_dev`; cần backup và xác nhận người dùng. Không có quyền tạo schema để clone đúng schema cũ 20 bảng. |
| Browser authenticated journeys | NOT TESTED trong Phase 1.5 | Không duyệt dashboard/catalog/POS/purchasing/report/admin bằng browser thật; trước đây chỉ quan sát login và locale. |
| Responsive/accessibility/browser console/network | NOT TESTED | Chưa kiểm viewport matrix, keyboard/screen reader, contrast hoặc failed browser requests. |
| SMTP/remote AI/AI Vision/S3 | NOT TESTED thật | Không có giao dịch provider thật; test hiện tại chỉ cover local/fallback/quota/validation. |
| Docker image | VERIFIED | `docker build --tag petcare-manager-web:phase15 .` thành công trên Docker Desktop; linux/arm64, Python 3.12. Container runtime acceptance chưa chạy. |
| Trivy filesystem/image scan | NOT TESTED | Trivy CLI không cài; GitHub Actions Trivy/secret scan chưa chạy. |
| Python branch coverage/performance/load | NOT TESTED | Không tạo coverage percentage/benchmark trong lượt này. |
| MySQL migration rehearsal từ schema dev cũ | BLOCKED | Runtime user không có quyền `CREATE DATABASE`; root socket không kết nối được. Chỉ chạy migration mới trên schema test hiện hữu đã có data tổng hợp. |

## Lệnh và phạm vi đã chạy

Lần Phase 1.5 cuối: 364 Python tests (unit, web, MySQL integration), 0 skip; 63 MySQL integration tests gồm bốn test purchasing mới. JavaScript 26/26. Bandit exact CI command exit 0; pip-audit khóa runtime; `pip check`, compileall, health/readiness test schema, Compose parse và `git diff --check` được ghi trong `docs/TEST_MATRIX.md`.
# Cập nhật Phase 5.3A — 2026-11-10

| Phạm vi | Trạng thái | Khoảng trống / bằng chứng |
|---|---|---|
| Vision harness | VERIFIED | Scorer/CLI deterministic; 9 unit tests. Kiểm tra path/manifest/prediction và per-field metric. |
| Synthetic benchmark | VERIFIED chỉ mechanics | 2 synthetic illustrations, 4 labels; mock prediction exact match. Không phải model output hoặc đại diện thực tế. |
| Real model accuracy | NOT MEASURED | Không có provider call, authorized real dataset hay latency/token/cost telemetry. |
| Scenario coverage | PARTIAL | Clear synthetic examples/processing errors có fixture; ambiguous, lighting, occlusion, multiple pets, non-pet, missing evidence và conflicting attributes đang chờ ảnh có quyền/nhãn độc lập. |
| Provider/network safety | VERIFIED trong test | External destination bị chặn trong APP_ENV=test; loopback cần cờ rõ. Runtime egress allowlist, provider budget enforcement và live privacy semantics chưa xác minh. |
| Human review | VERIFIED trong browser scope | Apply blank-only, no autosave, dismiss/keyboard recovery; không test mọi pet form/browser combination. |
| Browser/a11y | PARTIAL | Chromium 16/16; axe năm trạng thái 0 violations, một contrast node incomplete. Screen reader, true browser zoom 200%, cross-browser, full WCAG chưa test. |
| Reproducibility/dependencies | VERIFIED local | Locks audited, `pip check`, npm audit, compile, Compose config, Docker build pass. Hosted CI/platform matrix NOT TESTED. |
| External integrations | NOT TESTED | Provider thật, SMTP, S3 chưa gọi. |
| Dev/production DB | NOT TOUCHED | Chỉ MySQL disposable schema; không chạy DDL/DML/migration trên DB dev/production. |

Chi tiết: [benchmark](VISION_BENCHMARK_SPEC.md), [results](VISION_EVALUATION_RESULTS.md), [privacy/cost](VISION_PRIVACY_AND_COST.md), [browser/a11y](VISION_ACCESSIBILITY_QA.md), [Phase 5.3B gate](PHASE53B_PROVIDER_APPROVAL.md).
