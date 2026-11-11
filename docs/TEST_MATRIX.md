# Ma trận kiểm thử và độ phủ chức năng

## Phase 6.0 — kiểm chứng baseline phát hành — 2026-11-11

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python + MySQL regression | PASS local | **421/421 PASS, 0 skip** trên MySQL 8.4 schema QA `_test` mới, tmpfs; `/readyz=200`. Lượt đầu sai cấu hình password ở harness; lượt chạy chuẩn sau đó pass toàn bộ. |
| JavaScript | PASS local | **40/40 PASS** với `node --test tests/js/*.test.cjs`. |
| Full Playwright | PASS local | **18/18 PASS, 0 skip**, app Flask và MySQL `_test` thật, storage/browser artifacts riêng; `/healthz=200`, `/readyz=200`. Vision chỉ dùng mock/offline. |
| Browser diagnostics / Axe | PASS theo scope | 0 page error và failed request; một staff 403 `/users/` là hành vi quyền mong đợi. Axe 31 scans: 0 violations, 36 incomplete; screen reader/zoom thật/cross-browser còn thiếu. |
| Bandit / dependency security | PASS local | Lệnh Bandit đúng CI + baseline exit 0; hai pip-audit không có advisory; `npm audit` 0 vulnerabilities. Cảnh báo B608/nosec đã có vẫn được in. |
| Runtime/build checks | PASS local | `pip check`, compileall, `docker compose config --quiet`, Docker image build và kiểm tra `.agents/`/`skills-lock.json` không có trong image đều pass. |
| Screenshot preservation | PASS | `PETCARE_PRESERVE_DOC_ASSETS=1`; SHA-256 hai ảnh `docs/assets/phase55/` trước/sau full browser suite không đổi. |
| Development/production data | NOT TOUCHED | Chỉ schema QA disposable `_test`, tmpfs và storage tạm; không kết nối/mutate dev hoặc production. |
| Hosted Actions | PENDING PUSH | Sẽ ghi link và kết quả run thật sau push; platform Python 3.11/3.12/3.13, source security, container và browser jobs chưa tính là pass trước khi hoàn tất. |

Release evidence: [Phase 6.0 report](PHASE60_RELEASE_VERIFICATION.md). Acceptance kế tiếp: [Phase 6.1 plan](PHASE61_ACCEPTANCE_PLAN.md).

## Phase 5.5 — Operations overview — 2026-11-11

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Full Python + MySQL regression | PASS | `.venv/bin/python -m unittest discover -s tests -q`: **421/421 PASS, 0 skip**, MySQL 8.4 schema mới kết thúc `_test`, Compose tmpfs. Có thêm 6 unit tests cho aggregation/quyền/lỗi/empty/range; test MySQL purchasing hiện đối chiếu service facts, tenant override, staff denial, provider off, stock và PO state không đổi. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **40/40 PASS**, thêm 2 test grouped overview, text an toàn, allowlisted links và trạng thái nguồn không sẵn sàng. |
| Full Chromium / Playwright | PASS | `scripts/browser_smoke/run_smoke.py`: **18/18 PASS, 0 skip**, MySQL/storage riêng; `/healthz=200`, `/readyz=200`. Vision browser tests vẫn chỉ dùng mock/offline. |
| Operations overview E2E | PASS | Admin tạo fixture QA cô lập; 3 câu hỏi cũ (restock, PO, top products) thành 3 POST; một prompt tổng quan thành 1 POST. Bài test xác nhận card đọc từ MySQL, viewport/panel bounds, mở product/PO/report thật; targeted rerun sau kiểm bounds: **1/1 PASS**. |
| Responsive / UX effort | PASS theo kịch bản | Kiểm `documentElement.scrollWidth` và panel bounds ở 320/390/768/1440 px. Kịch bản test đếm 6 tương tác (mở assistant + chọn restock + 2 lần nhập/gửi) trước, 2 lần chọn (mở assistant + prompt tổng quan) sau. Đây là interaction count tự động, không phải nghiên cứu thời gian với người dùng. |
| Axe | PASS có giới hạn | Hai overview scan: **0 violation**, mỗi scan 3 incomplete items. Screen reader, 200% zoom thật, Safari/Firefox và toàn bộ WCAG chưa kiểm. |
| Browser diagnostics | PASS theo scope | Overview test không có console/page/network/HTTP lỗi. Trong full suite có một 403 dự kiến cho staff tại `/users/` và console message đi cùng; không có failed request hoặc page error. |
| Bandit CI gate | PASS | Lệnh CI với baseline `.security/bandit-baseline.json`, exit 0. Còn cảnh báo `nosec encountered (B608)` đã có trong baseline; Phase 5.5 không thêm SQL. |
| Dependency / package | PASS | Hai `pip-audit` lockfiles không có known vulnerabilities; `npm audit --prefix tests/a11y` 0 vulnerabilities; `pip check` sạch. Không thêm dependency. |
| Compile / build / Compose / diff | PASS | `compileall`, QA Compose config, Docker image `petcare-manager-web:phase55-verification`, `git diff --check`. |
| Database health / isolation | PASS trên QA | Browser runner chờ `/readyz=200` và kiểm `/healthz=200` trên schema `_test` mới, tmpfs. Không kết nối hoặc thay đổi `petcare_shop_dev`/production. |
| Provider / services bên ngoài | NOT TESTED, cố ý tắt | AI API endpoint/key/model unset; Vision disabled hoặc mock; không gọi real AI, SMTP, S3. |
| CI hosted / production | NOT RUN trong phase này | Không push và không kích hoạt workflow mới; Docker build local có chạy. |

Ảnh browser đã lưu ở [Phase 5.5 assets](assets/phase55/). Các file trace/diagnostic thô ở thư mục QA `/tmp`; không chứa dữ liệu production và không được đưa vào Git. Python/JS/Playwright là các suite riêng, không cộng thành phần trăm coverage.

## Phase 5.4 — Multi-module assistant — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Full Python regression | PASS | `.venv/bin/python -m unittest discover -s tests -v`: **415/415, 0 skip**, fresh MySQL 8.4 disposable schema `petcare_phase54_final_test`. Baseline 405; +7 capability unit tests, +1 MySQL route test, +2 ambiguity/negation assertions in existing unit tests. |
| Assistant MySQL route | PASS | Tạo synthetic low-stock product cùng ordered/partial/received/cancelled POs; kiểm current tenant, server links, stock, admin/staff boundary. Request tenant override + injection phrase không thay scope; provider mock configured nhưng `complete` không gọi. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **38/38**, baseline 36; thêm 2 structured insight/safe text/retry tests. |
| Full Playwright Chromium | PASS | `scripts/browser_smoke/run_smoke.py`: **17/17, 0 skip**, baseline 16. Browser Flask + disposable schema/storage; browser readiness startup `/healthz=200`, `/readyz=200`. Assistant scenario rerun after intent hardening: **1/1 PASS** on disposable `petcare_phase54_ui3_test`, port 5080. |
| Assistant browser / responsive | PASS theo scope | Suggestion → assistant route → real MySQL; card, status, locale-local timestamp, price, record link; Enter/Escape/focus; viewport 320/390/768/1440 không overflow. Screenshot tại [assets/phase54](assets/phase54/). |
| Assistant axe/accessibility | PASS có giới hạn | 3 axe states, 0 violations; 40 incomplete nodes. Manual keyboard flows pass. Screen reader, zoom thật và toàn WCAG chưa kiểm. |
| Bandit CI gate | PASS | Bandit 1.9.4, đúng baseline/arguments CI; exit 0. Có `nosec encountered (B608)` warnings, không có finding mới vượt gate. |
| Dependencies / package | PASS | `pip-audit` runtime + browser locks: không có known vulnerabilities; `npm audit --prefix tests/a11y`: 0 vulnerabilities; `pip check` sạch. |
| Compile / Compose / Docker / diff | PASS | `compileall`; `docker compose -p ... -f compose.qa-test.yml config --quiet`; `docker build -t petcare-phase54-audit:20261110 .`; `git diff --check`. |
| Provider, Vision, external services | NOT TESTED / không dùng | Không gọi AI/Vision thật, SMTP hoặc S3; QA AI endpoint/key/model empty, Vision disabled. Browser Vision suite trước đây chỉ dùng mock loopback. |
| Production/development schema / hosted CI | NOT TESTED | Không truy cập hay mutate dev/prod DB; `/readyz` 200 chỉ trên disposable QA. GitHub-hosted Actions/Trivy chưa chạy. |

Lần browser đầu dừng 1 case vì `axe-core` chưa được cài; `npm ci --prefix tests/a11y` cài theo lock, sau đó full suite 17/17 pass. Lượt assistant mục tiêu đầu tiên dùng port 5061 bị Chromium chặn (`ERR_UNSAFE_PORT`); chạy lại trên 5080 đạt 1/1. Full Python/JS, security, dependency, package, build và diff gates đều xanh.

## Phase 5.2 — Vision workflow — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Full Python regression | PASS | python -m unittest discover -s tests -v: **389/389**, OK, 0 skip trên petcare_phase52_test. |
| Vision MySQL route | PASS | Target riêng 1/1: CSRF/admin/session tenant, provider mock, không lưu ảnh suggestion, metadata đã bỏ. |
| JavaScript | PASS | node --test tests/js/*.test.cjs: **34/34**, gồm render an toàn, apply blank-only, stale-response, retry/cancel. |
| Full Chromium | PASS | scripts/browser_smoke/run_smoke.py: **15/15**, Flask thật, schema/storage riêng; assertions kiểm page errors, request failures và HTTP errors. |
| Vision image/provider scenarios | PASS theo mock | JPEG/PNG/WebP, MIME/extension mismatch, corrupt/empty/unsupported/pixel-limit, valid/malformed/ambiguous/503/timeout/retry, staff denial và bounded concurrency. |
| Responsive / keyboard | PASS theo scope | Document width khớp tại 320/390/768/820/1024/1440 px; apply bằng Enter và không ghi đè manual value. |
| Health / readiness | PASS trên test schema | Flask test client /healthz=200, /readyz=200; browser process chờ readiness trước test. |
| Bandit / dependency audit | PASS local | Command đúng CI exit 0; B608 baseline warnings không làm gate fail. Hai pip-audit lockfiles: “No known vulnerabilities found”. |
| Runtime/package/build | PASS local | pip check, compileall, Compose parse, Docker build và git diff --check pass. |
| Accuracy / provider thật | NOT TESTED | Mock deterministic + hình synthetic; không gọi provider trả phí/live, không tính precision/recall. |
| A11y đầy đủ / hosted CI | NOT TESTED | Không có screen-reader/axe/zoom cross-browser audit mới, Trivy CLI hoặc hosted Actions result. |

Full notes: [Phase 5.2 implementation](PHASE52_VISION_IMPLEMENTATION.md), [evaluation](PHASE52_VISION_EVALUATION.md), [security](PHASE52_VISION_SECURITY.md), [UX evidence](PHASE52_VISION_UX.md).

## Phase 5.1.1 — Regression recovery — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Full Python regression | PASS, lặp lại 2 lần | `python -m unittest discover -s tests -v`: **380/380**, 0 failure/error/skip; hai log độc lập trong thư mục artifact `petcare-phase511-regression-*`. |
| Unit / web / MySQL integration | PASS | Unit **228/228**, web **86/86**, MySQL integration **66/66** trên MySQL 8.4 disposable QA schema `petcare_phase511_test`. |
| AI Assistant feature regression | PASS theo scope | Pytest target: **8 passed**, 13 subtests; dữ liệu và storage cô lập. Không gọi AI provider thật. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **31/31**, 0 skip. |
| Full Playwright Chromium | PASS, lặp lại 2 lần | `scripts/browser_smoke/run_smoke.py`: **11/11**, 0 skip. Mỗi lượt có 11 diagnostic entries, 0 page errors, 0 failed requests, 0 HTTP bất ngờ; 403 `/users/` của staff là expected. |
| Bandit CI gate | PASS | Chạy đúng command từ `.github/workflows/ci.yml`, exit 0. Có cảnh báo `nosec encountered (B608)` tại các câu SQL đã được rà soát; xem [CI security review](CI_SECURITY_REVIEW.md). |
| Dependency, package và cú pháp | PASS | `pip-audit` cho `requirements.lock` và `requirements-browser.lock`: không có known vulnerabilities; `pip check`, `compileall`, Compose config parse và Docker build đều pass. |
| Test database readiness | PASS trên schema disposable | `/readyz=200` trước browser runs. Schema chỉ nằm trên tmpfs; ứng dụng test bị khóa vào `petcare_phase511_test`. `petcare_shop_dev` và production không được dùng hoặc thay đổi. |
| Hosted CI / external providers / full accessibility | NOT TESTED | Không có GitHub-hosted run; SMTP, live AI/Vision, S3 không được gọi; keyboard/screen-reader/axe audit toàn ứng dụng chưa chạy lại. Dev DB readiness vẫn là vấn đề riêng và cần quy trình/approval ở [DB readiness remediation](DB_READINESS_REMEDIATION.md). |

Kết quả Phase 5.1.1 thay thế trạng thái full-suite thất bại ghi ban đầu trong bảng Phase 5.1 bên dưới. Thất bại lịch sử được giữ để truy vết; không xem là baseline hiện tại.

## Phase 5.1 — AI assistant sales insight — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Benchmark grounding | PASS theo scope | Baseline 0/2; sau thay đổi 2/2: Vietnamese suggestion qua Chromium/MySQL và English injection/tenant-override qua API/MySQL so với report service. |
| Pytest backend | PASS theo scope | `.venv/bin/python -m pytest -q tests/unit tests/web`: **314 passed**, 422 subtests. Bộ mới + integration target: **8 passed**, 13 subtests. Pytest 9.2.0 chỉ cài trong `.venv`, không đổi lock. |
| MySQL assistant integration | PASS theo scope | `test_assistant_top_products_uses_current_tenant_sales_report`: staff request, active tenant, attempted tenant override, forbidden cross-tenant service call, anonymous route và no provider call. Dùng schema `_test` hiện có. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **31/31**, gồm XSS-safe top-product cards và URL allowlist. |
| Playwright feature | PASS theo scope | Test mới chạy riêng trên Flask thật: **1/1**, viewport 390×844, suggestion → `/assistant/chat` → MySQL report fact/card/link. `/readyz=200`. Screenshot: [mobile assistant](assets/phase51/assistant-top-products-mobile.png). |
| Full Python regression | FAIL | `.venv/bin/python -m unittest discover -s tests -v`: **380 tests**, 2 failures, 15 errors, 0 skip trên QA schema hiện có. Traces gồm fixture không chọn tenant tường minh, catalog count 23 khác expectation 22 và demo date cũ. Không sửa/xóa dữ liệu QA để ép xanh. |
| Full browser regression | FAIL / feature isolated PASS | Run 11 tests có 6 failures và 1 error. Legacy product photo references không tồn tại trong storage riêng, fixture gặp actor đa tenant, export job còn pending. Lỗi selector trong test insight đã sửa; chạy riêng sau sửa PASS. Không chạy lại suite đầy đủ trên QA state không sạch. |
| Bandit CI gate | PASS | Dùng đúng command `.github/workflows/ci.yml`; exit 0, warning `nosec encountered (B608)` trong baseline. |
| Dependency, syntax, package | PASS | Hai `pip-audit` lockfiles: no known vulnerabilities; `pip check`, full `compileall`, `git diff --check` PASS. |
| Compose/container | PASS | `docker compose config --quiet` và `docker build --tag petcare-manager-web:phase51-local .` PASS. |
| AI provider/Vision/SMTP/S3 | NOT TESTED | Không có paid provider call hoặc live external integration. |
| Database scope | PASS / LIMITATION | QA `_test` guard + connection verified; `/readyz=200`. Không truy cập dev/production. Không thể provision schema QA mới vì DB user thiếu quyền `CREATE DATABASE`; schema hiện có không được dọn. |

Xem [Phase 5.1 implementation](PHASE51_AI_IMPLEMENTATION.md), [evaluation](PHASE51_AI_EVALUATION.md) và [security](PHASE51_AI_SECURITY.md). Các bảng Sprint 4.3 và cũ phía dưới giữ lại làm lịch sử, không phải kết quả Phase 5.1.

## Sprint 4.3 — Purchasing, Reports, Operations — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL integration | PASS | `.venv/bin/python -m unittest discover -s tests -v`: **372/372, 0 skip** trên schema QA `petcare_phase3_browser_test`. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **30/30**, gồm POS retry sau lỗi lookup và fill-remaining purchase interaction. |
| Playwright Chromium | PASS | `scripts/browser_smoke/run_smoke.py`: **10/10, 0 skip** trên Flask process thật; purchase/report/export/POS recovery có MySQL QA assertions. |
| Responsive matrix | PASS | Purchasing list/detail, report, tenant export pending/ready tại 320/390/768/820/1024/1440 px; mỗi state assert `documentElement.scrollWidth == viewport`. Ảnh [visual QA](PHASE43_VISUAL_QA.md). |
| Purchase lifecycle | PASS theo scope | Tạo đơn không tăng stock; partial/full receive, cancellation route, UI fill-remaining keyboard, status/stock/movements được đối chiếu với MySQL; integration suite có rollback/invalid-state/idempotency cases. |
| Report filters/export | PASS theo scope | 7-day/custom date được browser kiểm; revenue/invoice count khớp report service; mobile product values đọc được; XLSX download signature `PK`. |
| Tenant export worker | PASS theo scope | Admin tạo pending job; worker one-shot chạy; DB ready/size/expiry được kiểm; browser tải artifact đúng kích thước. Không giải mã nội dung. |
| POS lookup recovery | PASS theo scope | Browser inject một 503 duy nhất; retry GET thành công, cart vẫn có line; JS test tương ứng pass. |
| Axe | PASS theo scan | axe-core 4.14.0 quét **26 trạng thái, 0 violations**; 39 incomplete node instances (36 color-contrast, 3 label-content-name-mismatch) cần AT/manual review; không phải pass WCAG. |
| Bandit CI security gate | PASS | Lệnh source-security chính xác trong `.github/workflows/ci.yml`, baseline đang dùng; exit 0. B608 `nosec encountered` warnings còn nhưng không có finding làm fail. |
| Dependency audits | PASS | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: không có vulnerability đã biết tại thời điểm chạy. |
| Package, syntax, compose, diff | PASS | `pip check`, `compileall`, `docker compose config --quiet`, `git diff --check`. Compose check chỉ parse config. |
| QA health/readiness | PASS | Browser runner chờ `/readyz=200` trước khi chạy; chỉ schema `_test` được initialize/seed. |
| Dev/production database | NOT MODIFIED | Không migration/schema/data write trong sprint. Dev readiness 503 là baseline cũ; không probe lại trong lượt này. |
| Hosted CI, real providers, screen reader/zoom | NOT TESTED | GitHub-hosted Actions/Trivy, SMTP/AI/Vision/S3, Safari/Firefox, assistive technology và browser zoom 200% thật chưa chạy. |

Evidence details: [Sprint 4.3 implementation report](PHASE43_IMPLEMENTATION_REPORT.md) and [browser/visual QA](PHASE43_VISUAL_QA.md). Baseline Phase 4.2 below is retained as historical evidence.

## Phase 4.2 — Product, inventory, POS và customer/pet quality — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL integration | PASS | `.venv/bin/python -m unittest discover -s tests -v` trên MySQL QA `petcare_phase3_browser_test`: **372/372, 0 skip, 30.685 s**. Baseline trước sprint: 371/371. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **28/28, 0 skip**. Baseline trước sprint: 28/28. |
| Playwright browser smoke | PASS | `scripts/browser_smoke/run_smoke.py`: **6/6, 0 skip, 35.706 s**. QA server chờ `/readyz=200`; kết quả ở [browser-results](assets/phase42/after/results.json). Baseline trước sprint: 4/4. |
| Product list responsive | PASS | Thực tế Chromium ở 320/390/768/820/1024/1440px; tìm product theo code; data, status, stock, action hiển thị; document width bằng viewport. 320/390 render card; desktop giữ table. |
| Product create/detail/edit | PASS trong phạm vi workflow | Browser tạo synthetic product, native validation stock âm, mở detail, đổi giá qua edit và xem stock ledger. Form create/edit screenshot ở docs/assets/phase42. |
| Inventory correctness | PASS | MySQL-backed browser: stock 2, delta -3 rejected/stock remains 2, delta +1 recorded; after paid sale of 2 stock=1 and invoice movement=-2. Existing integration tests tiếp tục cover transaction, rollback, overflow/concurrency. |
| POS search, keyboard, cart, checkout | PASS | Empty search feedback rồi valid product search; Enter trên card thêm hàng và focus tới quantity; sticky summary count/total khớp estimate; overstock request bị server validation từ chối và giữ error; qty 2 tạo/pay invoice thành công. 6 widths không tràn document. |
| Payment idempotence / persistence | PASS theo scope | Sau payment route success, gọi lại service cùng paid invoice trả `already_paid`; stock ledger và final quantity đối chiếu MySQL. Existing integration suite cover concurrent pay/rollback. Không có gateway thật. |
| Customer purchased pets >12 | PASS | Tạo 13 pet liên hệ qua paid invoice; page 1 có 12, page 2 chứa pet 13; query page hóa đơn còn nguyên. Detail 320/390/768/820/1024/1440px không overflow. |
| Customer activation/deactivation roles | PASS | Browser thực sự activate/deactivate customer QA và xác nhận trạng thái; role restrictions staff trên admin route tiếp tục trả 403 expected. |
| Axe / keyboard / contrast | PASS theo phạm vi scan | axe-core 4.14.0, 13 screens, **0 violations**; test keyboard POS/customer pagination/stock form. Axe có 13 `incomplete` node results cần manual review; screen reader, browser chrome zoom 200% và full WCAG audit chưa chạy. |
| Network/console | PASS có expected denial | 0 page errors, 0 failed requests; 1 console error/HTTP 403 `/users/` trong staff permission check được xác nhận là expected. |
| Bandit exact CI gate | PASS | Lệnh `source-security` trong `.github/workflows/ci.yml`, baseline `.security/bandit-baseline.json`, exit 0; B608 `nosec encountered` warnings vẫn xuất hiện nhưng không có finding mới làm fail gate. |
| Dependency audits | PASS | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: “No known vulnerabilities found”. |
| Python compilation / packages / config | PASS | `compileall`, `pip check`, `docker compose config --quiet`, `git diff --check` đều exit 0. |
| QA/dev DB boundary | PASS / NOT CHANGED | Smoke chỉ initialize/seed schema `_test`, readiness 200. `petcare_shop_dev` không được sửa; dev `/readyz=503` remains. |
| Hosted CI, other browsers, real integrations | NOT TESTED | Không có hosted Actions result, real browser-zoom UI, Safari/Firefox, SMTP/AI/Vision/S3 hoặc production validation. |

Screenshots before/after và máy scan được lưu tại [Phase 4.2 visual QA](PHASE42_VISUAL_QA.md) và `docs/assets/phase42/`.

## Phase 3.5 — browser final stabilization — 2026-11-09

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL integration | PASS | `.venv/bin/python -m unittest discover -s tests -v` trên `petcare_phase3_automated_test` cô lập: **369 tests, 33.513 s, OK**, không có skip. Baseline trước Phase 3.5: 369/369. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **28/28**, 0 fail/skip. Baseline trước Phase 3.5: 28/28. |
| Playwright browser smoke | PASS | `scripts/browser_smoke/run_smoke.py`: **3/3 tests, 7.844 s** trên Flask process thật + MySQL `petcare_phase3_browser_test`; report và trace/screenshot ở `/var/folders/h8/kq90jvq96b33gb79fnxcqjgh0000gn/T/petcare-phase35-browser-final-i5ka8nbh`. |
| Refund UI + persistence | PASS trong browser scope | Dialog dismiss không POST/mutation; zero và over-refund bị từ chối; partial/full refund và duplicate request key được đối chiếu giữa feedback, invoice/refund rows, stock movements và stock. Không có payment gateway. |
| Browser routes/role/responsive/keyboard/a11y smoke | PASS trong scope | Admin mở dashboard/customers/pets/products/invoices/purchasing/reports; staff vào customers nhưng nhận 403 `/users/`; POS mobile 390×844, tablet nav 820×1180, keyboard Tab order và tên control/landmark cơ bản đạt assertion. Không phải WCAG audit toàn site. |
| Network/console diagnostics | PASS có expected denial | Không failed requests hoặc JS exceptions. Browser ghi nhận 403 `/users/` và console message do expected denial; harness chỉ allowlist message này khi response 403 được xác nhận. |
| CI browser job integration | WIRED / NOT TESTED hosted | Job `browser-smoke` thêm vào `.github/workflows/ci.yml`; YAML parse PASS, service MySQL `_test`, readiness trong runner và artifact upload cấu hình 7 ngày. GitHub Actions hosted workflow chưa được chạy. |
| Bandit exact CI command | PASS | `.venv/bin/bandit -q -r petcare scripts main.py run.py wsgi.py -x petcare/templates,petcare/static -b .security/bandit-baseline.json`: exit 0. Hai suppression hẹp B404/B603 chỉ áp dụng cho subprocess gọi `sys.executable` + repository `run.py`, không shell, không user input; URL probe chuyển sang `http.client`, SQL cleanup dùng placeholders cố định. Cảnh báo baseline B608 hiện hữu vẫn được ghi như trước. |
| Dependency audits | PASS | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: cả hai “No known vulnerabilities found” tại lần quét. |
| Clean dependency install | PASS | Tạo venv tạm mới trên Python 3.13; `pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock`, `pip check` và `python -m playwright --version` thành công (Playwright 1.64.1). CI matrix Python 3.11/3.12/3.13 hosted chưa chạy. |
| Package consistency / compile | PASS | `.venv/bin/python -m pip check`: không có requirement conflict; `python -m compileall -q run.py main.py petcare tests scripts/browser_smoke`: exit 0. |
| Compose / workflow YAML / diff | PASS | `docker compose config --quiet`; Ruby YAML parser cho `.github/workflows/ci.yml`; `git diff --check` đều exit 0. Đây không phải hosted Actions validation. |
| App health/readiness QA | PASS | Flask process thật trên QA schema: `GET /healthz=200`, `GET /readyz=200`. App smoke runner cũng từ chối tiếp tục cho tới khi `/readyz=200`. |
| Development readiness | BLOCKED / NO-GO | Read-only `petcare_shop_dev`: MySQL 8.4.11, 20 tables, 184 columns, chỉ marker UTC, schema contract false; Flask `GET /readyz=503`. Không chạy schema mutation. Chi tiết và backup gate ở [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md). |
| Cleanup QA | PASS | Sau browser run, count invoice note `Playwright refund fixture %`, customer `Browser refund QA %` và product code `PW-%` đều bằng 0 trong schema browser QA. |
| Trivy / hosted CI / provider thật | NOT TESTED | Trivy CLI và GitHub-hosted workflow chưa chạy; SMTP, AI/AI Vision và S3 không cấu hình/không gọi. |

Kết quả baseline Phase 3.5: Python **369/369**, JS **28/28**, browser **3/3**. Không thay business code; thay đổi code giới hạn ở browser runner, CI wiring và browser lock. Xem [BROWSER_SMOKE_CI_REPORT.md](BROWSER_SMOKE_CI_REPORT.md), [PHASE35_RELEASE_BASELINE.md](PHASE35_RELEASE_BASELINE.md) và [PHASE4_HANDOFF.md](PHASE4_HANDOFF.md).

## Phase 3 — hoàn thiện chức năng và tối ưu — 2026-11-09

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL integration | PASS | Full suite trên schema MySQL tự động riêng `petcare_phase3_automated_test`: **369 tests, 31.122 s, OK**, không skip. Trước Phase 3: 366/366. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **28/28**, tăng từ 27/27. |
| Regression mới | PASS | Ba Python test: migration sửa named money checks legacy, refund route partial/full/replay/rollback, heading export theo trạng thái. Một JS regression POS: cart preview/count/tổng theo dữ liệu giỏ. |
| Python compilation | PASS | `python -m compileall -q run.py main.py petcare tests scripts`. |
| Package consistency | PASS | `.venv/bin/python -m pip check`: không có dependency conflict. |
| Dependency advisory scan | PASS | `pip-audit -r requirements.lock`: không tìm thấy advisory đã biết tại lần quét. |
| Bandit CI security gate | PASS | Đúng lệnh trong `.github/workflows/ci.yml`, gồm baseline `.security/bandit-baseline.json`: exit 0. Các B608 `nosec` được Bandit nhắc là các statement đã được review/allowlist hẹp; gate không có finding mới. |
| Docker/Compose | PASS | `docker compose config --quiet` và `docker build --tag petcare-manager-web:phase3 .` thành công. |
| Live health/readiness | PASS có giới hạn | Flask thật trên `127.0.0.1:5056`: `/healthz` 200, `/readyz` 200 với schema browser QA; clone dev `/readyz` 200. `/workersz` 503 do không chạy worker nền. |
| Dev database | BLOCKED pending approval | `petcare_shop_dev` vẫn 20 bảng, một marker migration và `/readyz` 503. Chỉ truy vấn read-only; không initializer/DDL/DML/seed trên DB này. |
| Dev schema migration clone | PASS | Clone từ dev read-only có 20 bảng/729 dòng/1 marker; chạy initializer trên `petcare_phase3_dev_clone` thành 26 bảng/4 marker, readiness 200. Dữ liệu nghiệp vụ không đổi, sáu bảng nghiệp vụ mới rỗng. Initializer chạy lặp lại thành công. |
| Browser responsive và workflow | VERIFIED/PARTIAL | Browser thật: role admin/staff và 403; profile cập nhật rồi phục hồi; export mismatch bị từ chối, job ready và bundle tải; mobile POS 390×844, tablet nav 820×1180, desktop 1440×900. Refund submit trong browser chưa xác minh; refund route có MySQL integration test. Chi tiết trong [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md). |
| Browser console | PASS theo phạm vi quan sát | `dev.logs` error/warning trả `[]` sau các workflow. `/favicon.ico` 404 vẫn còn; `/static/favicon.svg` 200. Network request panel chưa được thu thập. |
| Trivy/GitHub Actions | NOT TESTED | Trivy CLI chưa cài; workflow GitHub Actions không được chạy trong lượt này. |
| Diff whitespace | PASS | `git diff --check` sau cập nhật code/tài liệu, exit 0. |

### Bằng chứng chức năng Phase 3

| ID | Workflow | Trạng thái | Bằng chứng và giới hạn |
|---|---|---|---|
| P3-01 | Hoàn tiền qua route + MySQL | PASS | Test route đăng nhập admin và CSRF, tạo hóa đơn tổng hợp rồi thanh toán, partial refund, replay cùng idempotency key, full refund, từ chối over-refund và inject audit failure. DB xác nhận hóa đơn vẫn paid, số tiền/quantity hoàn, stock movement và tồn nhất quán; lỗi giữa transaction không để lại khoản hoàn hay đổi tồn. Không gọi gateway hoặc chuyển tiền. Browser form không được submit do confirm dialog chưa được điều khiển. |
| P3-02 | Tenant export UI + worker | VERIFIED | Browser kiểm mismatch passphrase, xếp job hợp lệ, worker one-shot hoàn tất và trang hiển thị `ready`; artifact tải về có header `PCEXP001`, size 2,283,927 byte, được lưu ngoài repo dưới `/tmp` với mode 0600. Không giải mã hoặc đọc nội dung. Worker thường trực chưa chạy. |
| P3-03 | Account/RBAC | VERIFIED một phần | Staff cập nhật display name, thấy feedback, rồi khôi phục tên ban đầu. Staff mở dashboard được; direct `/users/` bị từ chối. Không submit đổi mật khẩu, recovery, xác minh email hoặc luồng gửi mail. |
| P3-04 | Tablet/mobile/desktop | VERIFIED tại viewport lấy mẫu | 820×1180: nav overflow ngang có scrollbar/fade, `Reports` mở được; 390×844: cart preview một món/55.000 VND, anchor tới order summary, document width 390; 1440×900 desktop không tràn ngang. Không rà toàn bộ trang/breakpoint hay accessibility toàn site. |
| P3-05 | Migration tiền trên clone | PASS | Constraint cùng tên nhưng còn kiểm `_vnd` được thay bằng check trên `unit_price`, `sale_price`, `line_total`; kiểm tra 0 hàng lỗi trước ALTER. Viết giá âm/tổng dòng sai bị MySQL từ chối (3819). Dev schema chưa được sửa. |

Các schema `petcare_phase3_automated_test`, `petcare_phase3_browser_test`, `petcare_phase3_dev_clone` và media/export dưới `/tmp/petcare-phase3` được cô lập. Không ghi dữ liệu hoặc schema vào `petcare_shop_dev` hay production. Test browser export chỉ tải bundle mã hóa; file được giữ trong thư mục riêng có quyền hạn chế và không được giải mã.

Trạng thái mỗi dòng chỉ áp dụng cho workflow và môi trường nêu ở cột bằng chứng; không suy rộng thành kiểm thử production.

Ghi chú thứ tự chạy: full Python 369-test suite chạy sau các regression code Phase 3 chính. Thay đổi cuối cùng sau full suite chỉ là CSS fade ở tablet; `tests.web.test_design_tokens` chạy riêng **2/2 PASS** sau thay đổi đó và browser 820×1180 xác nhận fade/navigation. Các thay đổi tiếp sau là tài liệu; `git diff --check` chạy lại sau khi hoàn tất.

## Phase 2 — browser E2E và regression — 2026-11-09

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL integration | PASS | `python -m unittest discover -s tests -q` trên schema `petcare_phase2_automated_test` riêng: **366 tests, 36.2 s, OK**, không báo skip. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **27/27**, gồm regression mới invalid quantity không cộng vào estimate. |
| Compile / package consistency | PASS | `python -m compileall -q run.py main.py petcare tests scripts`; `pip check`: không có broken requirements. |
| Dependency security | PASS | `pip-audit -r requirements.lock`: no known vulnerabilities tại 2026-11-09. |
| Bandit CI | PASS | Đúng lệnh `.github/workflows/ci.yml`, Bandit 1.9.4 + baseline, exit 0. Có cảnh báo audit log `nosec encountered (B608)`; không có finding mới chặn gate. |
| Compose parse | PASS | `docker compose config --quiet`, exit 0. Container image build không chạy lại Phase 2; build đã PASS ở Phase 1.5. |
| Trivy | NOT TESTED | Trivy filesystem/image scan chưa chạy trong Phase 2. |
| Browser auth/screens | VERIFIED/PARTIAL | Owner/admin + staff đăng nhập; modules chính được mở và nhiều workflow thật được thực hiện. Ma trận chi tiết ở [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md). |
| Browser responsive | PARTIAL | 320×720 dashboard, 390×844 dashboard/POS, 820×1180 reports, 1440×900 các routes chính. Không kiểm mọi screen ở mọi breakpoint. |
| Browser console | PASS theo observed tab | `dev.logs` error/warning rỗng. Network request panel chưa có qua CUA. |
| Safe probes | PASS/PARTIAL | App/test DB: `/healthz` 200, `/readyz` 200, `/workersz` 503 (không có worker). `/metrics` 404 (đã tắt). |
| Safe data | PASS | Dùng schema `_test` mới cho integration và schema `_test` browser riêng; media ở `/tmp`; không mutation dev/prod. |

Hai Python regression test đã được bổ sung ở Phase 2 trước lượt full suite: pet/product submitted values sau server validation error. Một JavaScript regression mới cho quantity 0. Full suite đã xác nhận toàn bộ.

Browser QA tạo synthetic `QA Browser Customer`, `QA Pet Browser`, `QA Browser Product`, `QA Browser Supplier`, invoice #8/#9 và PO #1/#2 trong `petcare_phase2_browser_test`; không xóa schema/volume sau lượt chạy. XLSX report tải về local Downloads. Đây là artifact test, không phải production data.

Dev database chưa được đọc/ghi lại trong Phase 2. Trạng thái 20 tables/readiness 503 dưới đây là baseline Phase 1.5; remediation tiếp tục cần review/approval theo [DB_READINESS_REMEDIATION.md](DB_READINESS_REMEDIATION.md).

Xem [FULL_E2E_AUDIT.md](FULL_E2E_AUDIT.md), [MODULE_COMPLETENESS_MATRIX.md](MODULE_COMPLETENESS_MATRIX.md), [TEST_COVERAGE_GAPS.md](TEST_COVERAGE_GAPS.md) để phân biệt verified, partial và not tested.

Ngày chạy: 2026-11-09. Trạng thái gắn với phạm vi workflow được nêu trong cột bằng chứng; PASS không khẳng định mọi trường hợp có thể có đã được kiểm tra.

## Môi trường và kết quả lệnh

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Cài dependency runtime | PASS | Virtualenv sạch `/tmp/petcare-phase15-verify-venv`, Python 3.13.3; `pip install -r requirements.txt -c requirements.lock` thành công. |
| Python compile | PASS | `python -m compileall -q run.py main.py petcare tests`, exit 0. |
| Python unit + web + MySQL integration | PASS | `python -m unittest discover -s tests -v` với `PETCARE_TEST_DB_NAME=petcare_audit_dc5a5cb2a2ab_test` và media/export dirs trong `/tmp`; 364 tests, 0 failures, 0 skipped. Log: `/tmp/petcare-phase15-python-tests.log`. |
| Purchase-order MySQL integration | PASS | 4 test mới trong `tests/integration/test_mysql_purchasing.py`: route create, partial/full receipt, replay idempotency, cancel/invalid states, stock ledger và rollback. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`; 26 tests, 26 pass. |
| Dependency resolution | PASS | Virtualenv lock mới; `python -m pip check`: “No broken requirements found.” |
| Dependency advisory scan | PASS | `pip-audit -r requirements.lock`: “No known vulnerabilities found” tại lần quét. |
| Security source scan | PASS | Lệnh Bandit exact CI exit 0 sau review/suppression hẹp ba B608 trong scope. |
| Compose parse | PASS | `docker compose config --quiet`, exit 0. |
| Container build | PASS | `docker build --tag petcare-manager-web:phase15 .` thành công; image `linux/arm64`, Python 3.12. |
| Trivy container/filesystem scan | NOT TESTED | Trivy CLI không cài; GitHub Actions security scan chưa chạy. |
| Diff whitespace | PASS | `git diff --check` chạy lại sau khi cập nhật tài liệu Phase 1.5, exit 0. |
| MySQL integration khi không cấu hình DB test | BLOCKED | Test cần DB riêng hậu tố `_test`. Lần chạy Phase 1.5 cấu hình DB riêng nên 63 integration tests chạy thật, không skip. |

MySQL test DB `petcare_audit_dc5a5cb2a2ab_test` là schema audit riêng trên MySQL 8.4.11 local. Bộ test chạy initializer/seed chỉ vào database này; thư mục ảnh/export được đặt dưới `/tmp/petcare-phase15-test-storage`. Không chạy migration, seed hay test ghi dữ liệu vào `petcare_shop_dev` hoặc `petcare_shop_test`. Không drop schema test. Bốn migration/index/route lifecycle tests purchasing dùng row tổng hợp và xóa đúng row chúng tạo.

## Ma trận theo workflow

| ID | Chức năng / workflow | Trạng thái | Bằng chứng thực thi và giới hạn |
|---|---|---|---|
| T-01 | Khởi động Flask và trang đăng nhập | PASS | Chạy `python run.py`; `GET /healthz` 200, `GET /login` 200; `GET /` redirect 302 sang đăng nhập. |
| T-02 | Chuyển locale trên màn hình đăng nhập | PASS | Trình duyệt mở ứng dụng thật, chọn English → Tiếng Việt và bấm Apply; POST `/language` trả 302 và trang đăng nhập render lại tiếng Việt. Test web kiểm allowlist và chặn redirect cross-origin. |
| T-03 | Readiness của database và worker | PARTIAL | `petcare_shop_dev` vẫn trả `/readyz` 503; không ghi schema dev. Schema `_test` có migration Phase 1.5 và readiness đạt. `/workersz` 503 khi không có fresh heartbeat. |
| T-04 | Login/logout, session version, khóa account và role refresh | PASS | MySQL tests: login/logout audit; password change thu hồi cookie; role change áp dụng ngay session cũ; khóa account làm logout request tiếp theo; account profile yêu cầu re-auth. |
| T-05 | Multi-tenant isolation và quyền | PASS | Integration test store data/catalog code isolation, admin/staff routes, store switch và membership/role; unit/web tests kiểm chặn cross-tenant selection, CSRF và 403. |
| T-06 | Khách hàng: tạo nhanh trong POS, tạo form, validation và trạng thái | PASS theo phạm vi đã chạy | MySQL tests quick customer + CSRF 201, invalid phone giữ form value; browser MySQL tạo customer synthetic, deactivate/reactivate bằng staff và đối chiếu state. Không phải audit toàn bộ filter boundaries. |
| T-07 | Khách hàng: hồ sơ, lịch sử, thú cưng đã mua và phân trang | PASS theo phạm vi đã chạy | Web tests kiểm independent `page`/`pet_page`; Playwright + MySQL 13-pet fixture xác nhận 12 record ở page 1, pet #13 ở page 2, giữ invoice page và responsive customer detail ở sáu widths. Không bao phủ mọi currency/filter boundary bằng browser. |
| T-08 | Sản phẩm/catalog và điều chỉnh tồn | PASS theo phạm vi đã chạy | Browser tạo/search/detail/edit sản phẩm; negative stock adjustment bị từ chối, `+1` được ghi vào ledger; MySQL tests tiếp tục cover atomic/concurrent adjustment và int overflow. Ảnh upload và stock form narrow viewport chưa chạy. |
| T-09 | Hồ sơ thú cưng, ảnh riêng tư và tìm ảnh local | PASS | Integration test upload ảnh + visual search trên MySQL profile, private photo burst, lọc species/status; unit test descriptors, palette image, upload byte limit và legacy descriptor. |
| T-10 | POS/invoice, thanh toán và tồn kho | PASS theo phạm vi đã chạy | Browser kiểm empty/valid search, keyboard Enter add + focus quantity, sticky summary/estimate, overstock server error, paid invoice persistence và repeat payment `already_paid`; MySQL integration cover concurrent payment/rollback. Không có gateway thật hoặc network-loss replay. |
| T-11 | Hủy invoice và validation biên | PASS | Unit/web/integration tests kiểm empty/mismatched item arrays, invalid quantity/customer, insufficient stock và trạng thái cancelled/paid; các giao dịch ghi thật vào DB test. |
| T-12 | Refund, partial return và disposition | PASS | MySQL test partial refund idempotent, net revenue theo ngày hoàn, pet trả về quarantine/không còn buyer. UI admin/staff authorization được web tests kiểm bằng test client. |
| T-13 | Nhà cung cấp và purchase order | PASS cho workflow đã nêu | 4 MySQL tests mới kiểm route create, line validation, nhận một phần/đủ, replay cùng key idempotent, key tái dùng payload khác bị từ chối, cancel/invalid transitions, stock/ledger consistency và rollback sau lỗi giữa transaction. Không suy rộng thành browser E2E. |
| T-14 | Báo cáo và XLSX snapshot | PASS | MySQL tests ngày địa phương qua DST và reconcile paid/restock/frozen export; web tests kiểm invalid period, snapshot binding, locale và XLSX export contract. |
| T-15 | Assistant local/catalog | PASS | Unit tests intent/query/response; MySQL integration tests current shop context, lọc sau preview và JSON validation. |
| T-16 | Provider AI/AI Vision bên ngoài | PARTIAL | Thử lỗi/fallback/quota và nội dung context bằng test; không gửi request tới provider thật, vì audit không cấu hình endpoint/key và không có yêu cầu chi phí bên ngoài. |
| T-17 | Gợi ý attributes từ ảnh | PARTIAL | Test admin gate, ảnh thiếu, quota/busy slot và lỗi API; chưa xác thực với model/provider thật hoặc đánh giá độ chính xác dữ liệu. |
| T-18 | Signup, email verification/reset, invitation, owner transfer | PARTIAL | MySQL integration bao gồm signup activation, invite single-use/revoke, owner transfer/re-auth, session revoke, encrypted outbox/retry. SMTP giao ra Internet không cấu hình/không chạy. |
| T-19 | Tenant export queue, quyền download và bundle crypto | PASS | Integration tests export encrypted/checksummed/tenant-isolated, self-service step-up auth/download; unit tests tampered payload/path/permissions. |
| T-20 | Activity audit, metrics và worker heartbeat | PARTIAL | Integration tests audit events, metrics bearer access và fresh heartbeat requirements; live dev app không có workers nên probe unavailable, metrics không bật token. |
| T-21 | Backup/restore operator CLI | PARTIAL | Unit tests backup/verify validation; không chạy backup/restore MySQL thật vì sẽ chạm dữ liệu ngoài schema test. |
| T-22 | Giao diện và responsive/accessibility | PARTIAL | Chromium kiểm product/POS/customer detail ở 320/390/768/820/1024/1440, keyboard stock/POS/pagination, axe 4.14.0 có 0 violations trong 13 targeted scans; còn 13 `incomplete` node results và chưa có screen reader, browser chrome zoom 200%, Safari/Firefox hoặc audit tất cả template. Network/console ghi 0 failed requests/page errors; 403 `/users/` là expected staff denial. |
| T-23 | Clinic, appointment, vaccination và dịch vụ spa | NOT IN SCOPE | README/REPO_GUIDE đặt ngoài phiên bản retail web; test xác nhận route dịch vụ clinic cũ không đăng ký. |
| T-24 | Production launch/container | PARTIAL | Compose config và local image build pass; không khởi chạy production container/deployment vì production secrets/services chưa được cấp. |

## Phân bố tự động

- Tổng Python test cases hiện hành ở Phase 4.2: **372 đạt, 0 fail, 0 skip** trên schema QA riêng. Số này không tương đương phần trăm coverage.
- JavaScript test cases hiện hành: **28 đạt**.
- Python test modules: unit, web và integration theo `tests/`; JS suites: invoice, motion, POS và UI.
- Không tạo coverage report/branch coverage trong lần audit này; số test không phải phần trăm coverage.
- Evidence log thành công: `/tmp/petcare-phase15-python-tests.log` trên máy audit; log không được copy vào repository vì có thể chứa dữ liệu test.

Lưu ý lịch sử: lần audit ban đầu có 360 Python và 59 MySQL integration tests; sau Phase 1.5 có thêm bốn test MySQL purchasing. Lần suite đầu tiên sau thay đổi Phase 1.5 có failure do translations/readiness marker và record synthetic còn lại từ teardown test chưa thành công; sau khi sửa và dọn riêng dữ liệu test, toàn suite đạt như số hiện hành ở trên.

# Phase 5.3A update — 2026-11-10

| Area | Status | Evidence / limitation |
|---|---|---|
| Python full suite | PASS | `python -m unittest discover -s tests -v`: **405 tests, OK, 0 skipped** on disposable `petcare_phase53a_test`; verbose log was removed with temp QA after recording the result. |
| Vision evaluator | PASS | 9 new unit tests exercise score math, abstention, omitted labels, recovery/telemetry, determinism, pending scenario coverage, exact ID set and path traversal rejection. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **36/36**. Includes dismiss behavior and motion-opacity regression. |
| Chromium | PASS | `python scripts/browser_smoke/run_smoke.py`: **16/16**, zero skips; app starts only after `/readyz=200` on QA MySQL. Browser traces/screenshots and raw results were removed with temp QA; accessibility summary is versioned under docs assets. |
| Vision accessibility | PASS, scoped | Axe 4.14.0 scanned five Vision states; each had 0 violations. One decorative-arrow contrast node is `incomplete`; no screen reader or true 200% zoom. |
| Egress guard | PASS, mocked | Tests in `tests/unit/test_ai_client.py` confirm test environment blocks external provider destinations and allows explicit literal loopback only. No live provider call. |
| Bandit | PASS | Exact CI command in `.github/workflows/ci.yml` exits 0 with repository baseline; existing B608 `nosec` warning lines remain and are disclosed in `CI_SECURITY_REVIEW.md`. |
| Dependency audit | PASS | `pip-audit -r requirements.lock`, `pip-audit -r requirements-browser.lock`: no known vulnerabilities. `npm --prefix tests/a11y audit`: 0 vulnerabilities. |
| Package / compile | PASS | `pip check`, `python -m compileall -q petcare scripts tests`, `git diff --check` exit 0. |
| Container / compose | PASS local | `docker compose --env-file /tmp/petcare-phase53a-qa/qa.env -p petcare-phase53a-20261110 -f compose.qa-test.yml config --quiet`; `docker build --tag petcare-manager-web:phase53a-local .` succeeds. No deploy/push. |
| Health/readiness | PASS in QA | Browser runners launch Flask and poll `/readyz` until HTTP 200. Unit/web suite covers `/healthz`; no development schema probe/mutation in this phase. |
| Evaluation result | PASS, mock mechanics only | Two synthetic samples, 4 labels, mock fixture exact match; all real model accuracy, latency and cost fields remain NOT MEASURED/null. See `VISION_EVALUATION_RESULTS.md`. |
| Hosted CI / Trivy / real integrations | NOT TESTED | No push, hosted workflow, real provider, SMTP, S3 or Trivy run. |

Test storage and MySQL service were disposable/tmpfs under `/tmp/petcare-phase53a-qa`; the container, test credentials, storage, logs, screenshots and traces were removed after validation. No `petcare_shop_dev` or production database was modified. Python/JS/browser counts are separate suites and must not be added as if they were one coverage percentage.

# Phase 5.3B update — 2026-11-10

| Kiểm tra | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| Provider live / image egress | BLOCKED / 0 attempts | Đã chủ động dừng trước request theo approval gate. Dataset có 2 ảnh synthetic mechanics-only, nhưng 0 ảnh có quyền egress được chứng minh. |
| Vision evaluator offline | PASS ở baseline 5.3A; NOT RERUN trong preflight này | Harness deterministic/mock; metric không nói về model thật. |
| Model quality, abstention, schema validity | NOT TESTED | Không có authorized dataset và không gọi provider. |
| Provider latency / token / cost | NOT TESTED | Usage telemetry null; image token cost unknown. |
| Python full suite | PASS | `.venv/bin/python -m unittest discover -s tests -q`: **405 tests, OK, 0 skip** trên schema MySQL disposable tmpfs `petcare_53b_2d3c062c_test`. |
| JavaScript | PASS | `node --test tests/js/*.test.cjs`: **36/36**. |
| Chromium / Playwright | PASS sau chạy lại | `python scripts/browser_smoke/run_smoke.py`: **16/16**, 0 skip trên DB tmpfs mới, port app 52037, mock Vision loopback. Lần đầu dùng port 5061 và Chromium trả `ERR_UNSAFE_PORT`; chạy lại bằng port an toàn đã PASS. |
| Offline Vision evaluator | PASS, mechanics only | CLI chạy trên 2 fixture synthetic; usage/cost/latency null. Không provider request. |
| Database health/readiness | PASS trên QA; development/production NOT PROBED | `/healthz=200`, `/readyz=200` từ test client trên MySQL QA sau migrations. Không đụng `petcare_shop_dev`/production. |
| Python compile / package | PASS | `compileall` trên source copy cô lập; `pip check`: No broken requirements found. |
| Bandit CI gate | PASS | Lệnh workflow + baseline exit 0. Baseline `nosec` B608 warnings được in ra, không có finding mới làm fail gate. |
| Python dependency audits | PASS | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: no known vulnerabilities. |
| JavaScript dependency audit | PASS | `npm ci` theo lockfile; `npm audit --prefix tests/a11y`: 0 vulnerabilities. `node_modules` này được tạo tạm vì trước run không tồn tại. |
| Compose / Docker / diff | PASS | `docker compose config --quiet`; Docker build PASS từ context tạm chỉ gồm Dockerfile, lock/requirements, root entrypoints và `petcare/`; `git diff --check` PASS. Không push/deploy. |
| Security/privacy project controls | BLOCKED | Chưa có provider project/key, region/retention configuration hoặc hard limit được xác minh. Public docs review không xác nhận account settings. |

Tách provider live suite khỏi CI và giữ guard `APP_ENV=test`; chỉ dùng mock/local egress trong regression tự động. Không diễn giải bước chuẩn bị gói approval là provider execution.
