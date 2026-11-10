# Báo cáo audit — PetCare Manager

Ngày: 2026-11-09. Phạm vi: repository hiện có và các thay đổi đang nằm trong working tree lúc audit bắt đầu. Mục tiêu là audit/documentation, không viết lại ứng dụng.

## Tóm tắt điều hành

PetCare Manager là ứng dụng web quản lý cửa hàng thú cưng đa tenant, dùng Flask/Jinja/vanilla JS và MySQL. Phạm vi hiện hành là khách hàng, sản phẩm, thú cưng bán lẻ, POS/hóa đơn, tồn kho, nhập hàng, hoàn tiền, báo cáo, trợ lý, tài khoản và vận hành tenant; clinic/appointment không thuộc bản web hiện tại.

Môi trường chạy đúng khi schema đầy đủ: sau khi tạo một MySQL database test mới, cô lập và chỉ chứa dữ liệu tổng hợp, **360/360 Python tests (unit, web và MySQL integration) đạt, không skip**; **26/26 JavaScript tests đạt**. pip check, pip-audit, compileall, Compose config parse và git diff --check đạt. Không có P0/data loss defect nào được xác nhận trong lần chạy.

Hai vấn đề P1 cần xử lý trước khi coi môi trường/CI xanh: database dev cấu hình hiện tại chưa đạt readiness; Bandit gate thoát 1 vì ba B608 mới chưa được baseline ghi nhận. Ngoài ra, purchase-order lifecycle còn thiếu integration test MySQL riêng và requirements chưa khóa phiên bản cụ thể.

### Bằng chứng chạy ứng dụng

- python run.py khởi động Flask development server trên 127.0.0.1:5055; log chỉ ra cảnh báo development server như dự kiến.
- GET /healthz → 200; GET /login → 200; GET / → 302 về /login. Trang đăng nhập và CSS/JS local được mở bằng browser automation; Apply language đổi English sang Tiếng Việt thành công.
- Với DB đang trong .env (petcare_shop_dev), GET /readyz → 503. Kết nối chỉ đọc xác nhận MySQL 8.4.11, 20 bảng, thiếu năm bảng purchase/refund và schema contract trả false. GET /workersz → 503 vì không có heartbeat worker mới.
- Một DB mới riêng có hậu tố _test được tạo trên host local; quyền được cấp chỉ cho schema này. Sau initializer có 25 bảng và readiness contract true. Toàn bộ integration suite chạy trên DB riêng này và pass. Media/export test nằm trong /tmp. Không có lệnh write, initialize, seed, drop hoặc migrate chạy trên petcare_shop_dev hay petcare_shop_test có dữ liệu trước đó.
- Trình duyệt chỉ được duyệt trực quan màn login ở viewport 722×778. Các route authenticated được thực thi qua Flask web/integration tests; console/network panel, keyboard/screen-reader và tất cả breakpoint không được duyệt thủ công.

## Findings theo mức độ

Không có P0 được chứng minh. P1 dưới đây gồm một blocker dữ liệu môi trường và một blocker CI, không phải kết luận rằng mọi nghiệp vụ ứng dụng đều lỗi.

### AUD-DB-01 — Database dev hiện tại không đạt schema readiness

- **Severity:** P1 — môi trường audit không thể được báo ready.
- **Affected:** database petcare_shop_dev; petcare/routes/health_routes.py; petcare/database/readiness.py; petcare/database/initialize.py; petcare/database/purchasing.sql; petcare/database/refunds.sql.
- **Reproduction:** tại repo, dùng cấu hình hiện hành chạy python run.py, sau đó GET /readyz; truy vấn read-only danh sách bảng/schema contract.
- **Observed:** route trả 503; schema hiện có 20 bảng và thiếu suppliers, purchase_orders, purchase_order_items, invoice_refunds, invoice_refund_items. Readiness trả false.
- **Expected:** sau khi DB dev được nâng cấp theo migration hiện hành và có đầy đủ schema contract, /readyz trả 200. Readiness 503 trong trạng thái chưa đủ schema là hành vi đúng của probe.
- **Evidence:** HTTP 503 và schema_contract_is_ready=False trên DB dev; fresh isolated test schema sau initializer có 25 bảng, readiness true; 360 tests trên DB mới đều đạt.
- **Likely root cause:** schema local hiện hành đi sau source code/migrations.
- **Recommended solution:** backup petcare_shop_dev; xác minh nguồn gốc timestamp/migration markers; sau đó chạy initializer có chủ đích trên DB dev và kiểm tra row counts/contract. Không xóa/reset DB.
- **Estimated regression risk:** thấp–trung bình; migration có thay đổi schema/backfill, nên kiểm backup và dữ liệu sau khi chạy.
- **Verification criteria:** schema contract true, /readyz 200, dữ liệu cũ giữ nguyên và suite MySQL integration xanh.
- **Classification:** blocker của môi trường hiện tại; chưa chứng minh source defect.

### AUD-CI-01 — Bandit source-security job thất bại trên B608 mới

- **Severity:** P1 — gate source-security chặn pipeline khi chạy cùng working tree này.
- **Affected:** .github/workflows/ci.yml; .security/bandit-baseline.json; petcare/database/readiness.py:159-180; petcare/repositories/tenant_cleanup_repo.py:70-74.
- **Reproduction:** chạy đúng lệnh CI: bandit -q -r petcare scripts main.py run.py wsgi.py -x petcare/templates,petcare/static -b .security/bandit-baseline.json.
- **Observed:** Bandit 1.9.4 exit 1 với 3 issue B608 mới. Hai cảnh báo là placeholder-count được dựng từ các tập tên cột/constraint cố định và truyền giá trị bằng bind parameters; cảnh báo còn lại dùng table name từ _EMPTY_TENANT_TABLES là tuple hằng số. Source review không thấy user-controlled identifier trong ba chỗ này; cảnh báo chưa chứng minh SQL injection.
- **Expected:** source-security job pass sau khi review các truy vấn mới, ghi lý do allowlist/false-positive phù hợp và đồng bộ baseline.
- **Evidence:** chạy lệnh CI local trả 1; locations nêu trên; các giá trị row/table-name đầu vào được giới hạn bằng hằng số ở source.
- **Likely root cause:** baseline chưa được cập nhật khi các module mới được thêm; B608 nhận diện f-string tạo danh sách SQL identifiers.
- **Recommended solution:** giữ invariant allowlist rõ ràng, thêm xử lý false-positive có justification hoặc đổi cấu trúc câu truy vấn để scanner hiểu; cập nhật baseline chỉ sau review. Không suppress toàn rule.
- **Estimated regression risk:** thấp nếu chỉ làm rõ allowlist/baseline; trung bình nếu đổi cách dựng truy vấn.
- **Verification criteria:** lệnh Bandit giống CI exit 0 và review xác nhận mọi identifier vẫn lấy từ tập hằng số, values vẫn bind-param.

### AUD-QA-01 — Purchase-order lifecycle chưa có integration coverage MySQL riêng

- **Severity:** P2 — regression risk cho nghiệp vụ nhập hàng.
- **Affected:** petcare/services/purchase_service.py; petcare/repositories/purchase_repo.py; petcare/routes/purchasing_routes.py; tests/web/test_purchasing.py; tests/integration/.
- **Reproduction:** chạy full suite và xem test inventory: route/web tests cho supplier/order search/create/receive/cancel patch service; không có test integration MySQL chuyên cho create → partial receive → receive hoàn tất/cancel của purchase order.
- **Observed:** 360 test suite đạt, nhưng SQL/transaction lifecycle cho purchase orders không được chứng minh bằng DB integration test riêng. Một integration test phase-three kiểm restock/report, không bao phủ đầy đủ order lifecycle.
- **Expected:** integration test dùng schema _test thật chứng minh stock movement, quantity received, status transition, duplicate receipt/cancel và rollback.
- **Evidence:** 49 integration test methods trong test_mysql_web.py và 9 trong test_mysql_sales.py; không có test method trong đó nêu purchase-order lifecycle; tests/web/test_purchasing.py kiểm route qua mock.
- **Likely root cause:** test suite ưu tiên sales/refund, phần purchasing mới được kiểm ở unit/web layer.
- **Recommended solution:** thêm 1–2 MySQL integration workflows cho order create, partial/final receive, repeated receive/cancel và inventory ledger; tận dụng DB _test CI có sẵn.
- **Estimated regression risk:** trung bình/cao do trạng thái order và kho được ghi cùng giao dịch.
- **Verification criteria:** test MySQL mới xác nhận order status, quantity_received, stock quantity và stock_movements; lỗi giữa transaction rollback hết.

### AUD-REL-01 — Dependency resolver không tái tạo bộ phiên bản cố định

- **Severity:** P2 — build reproducibility.
- **Affected:** requirements.txt; Dockerfile; .github/workflows/ci.yml.
- **Reproduction:** tạo virtualenv trống và chạy pip install -r requirements.txt vào thời điểm khác nhau.
- **Observed:** requirements dùng khoảng phiên bản như Flask>=3,<4, Pillow>=12,<14 và không có constraints/lock/hash file cho runtime. CI/Docker install trực tiếp các khoảng này nên bản build có thể resolve phiên bản minor/patch khác.
- **Expected:** release/build được tái tạo bằng bộ dependency đã test, trong khi nâng cấp vẫn chủ động.
- **Evidence:** nội dung requirements, lệnh install trong Dockerfile và workflow; audit env hiện resolve Flask 3.1.3, Pillow 13.0.0 và các phiên bản hiện hành. pip-audit -r requirements.txt báo không có vulnerability đã biết tại ngày audit.
- **Likely root cause:** dự án dùng range để hỗ trợ nhiều runtime nhưng không pin deployment set.
- **Recommended solution:** thêm constraints/lock file đơn giản cho app/runtime và cập nhật theo đợt có CI; không đổi framework hoặc thêm hệ thống build phức tạp.
- **Estimated regression risk:** trung bình khi cập nhật; thấp khi chỉ tái lập phiên bản đang chạy.
- **Verification criteria:** build sạch dùng cùng constraints tạo cùng phiên bản; unit/web/MySQL/JS tests và pip-audit xanh.

## Đánh giá kỹ thuật

- **Architecture:** ranh giới route/service/repository/database rõ; app factory và hooks tập trung; worker riêng; có compatibility facade được ghi trong docs.
- **Business/database:** transaction helpers rollback lỗi; MySQL dùng row locks cho payment/refund/inventory; tenant context reset khi checkout; decimal/currency snapshot; MySQL integration tests chạy thật trong lần audit.
- **Security:** CSRF, role reload theo membership, password/session revocation, no-store authenticated responses, security headers, encrypted mail/export và private media có bằng chứng test. Không phát hiện credential trong output audit. B608 đang là gate finding cần xử lý nhưng không được kết luận là injection khi chưa có input-controlled identifier.
- **AI:** local-first deterministic assistant; remote endpoint có opt-in. Không đo chi phí/provider quality/safety trên mạng thật. Local image ranker là heuristic color/composition, không phải detector/embedding nhận diện thú cưng.
- **Observability:** có liveness/readiness/worker probes, audit events và token-protected aggregate metrics. Live dev DB chưa ready; workers không chạy nên health probe unavailable.
- **Performance/scaling:** pool size/worker concurrency có giới hạn; trang danh sách phân trang; photo search có LSH nhưng fallback/score vẫn có đường tuyến tính theo tài liệu kiến trúc. Chưa chạy benchmark tải.
- **UI/UX:** login screen và locale switch đã quan sát. Không kết luận về visual quality toàn bộ trang authenticated, responsive/a11y tổng thể hay lỗi console.
- **Deployment (initial audit):** Compose config parse pass; container build, production TLS/SMTP/S3/AI chưa chạy tại thời điểm ghi nhận ban đầu. Phase 1.5 bổ sung kết quả Docker image build pass; xem `docs/STABILIZATION_REPORT.md`.

## Hạn chế và điều không thể kết luận

- Audit tree đã có nhiều thay đổi source/docs/tests chưa commit trước khi bắt đầu. Audit không reset hoặc ghi đè chúng; chỉ tạo các tài liệu audit được yêu cầu.
- Chỉ test data trong DB audit riêng và thư mục /tmp được dùng; DB dev/test có sẵn không bị sửa.
- Không drop database audit sau test để tránh thao tác xóa dữ liệu; nó được giữ nguyên dưới tên petcare_audit_dc5a5cb2a2ab_test.
- Test suite không tương đương browser E2E cho tất cả màn hình. Browser trực tiếp chỉ duyệt login/locale; workflow khác dựa trên unit/web/MySQL integration test.
- Initial audit did not run external SMTP, remote AI/vision, S3, Prometheus có token, Docker image build, restore backup, load benchmark hoặc production deployment. Phase 1.5 đã build image cục bộ; không chạy restore, tải benchmark hoặc production deployment.

## Cập nhật Phase 1.5 — 2026-11-09

Phần này supersede trạng thái audit ban đầu cho CI, coverage purchasing và dependency lock. Các quan sát ở trên vẫn là historical baseline. Source hiện yêu cầu 26 bảng vì Phase 1.5 bổ sung `purchase_order_receipt_requests`; trước thay đổi này fresh schema có 25 bảng. `petcare_shop_dev` vẫn có 20 bảng, chỉ có marker `datetime_storage_utc_v1`, và không bị ghi.

### AUD-DB-01 — Còn BLOCKED, chờ phê duyệt

- **Mức độ:** P1, environment readiness.
- **Affected:** `petcare_shop_dev`; `petcare/database/readiness.py`; `petcare/database/initialize.py`; `petcare/database/purchasing.sql`; `petcare/database/refunds.sql`.
- **Observed:** dev thiếu 6 bảng hiện hành, cột PO/refund trên `stock_movements`, unique invoice-item index, migration index/FK/check và ba marker purchasing/refund/receipt-idempotency. Marker UTC đã tồn tại.
- **Evidence:** MySQL 8.4.11 read-only; `schema_contract_is_ready=False`; `/readyz=503`; aggregate orphan checks 0, duplicate invoice-item composite groups 0.
- **Root cause:** schema hiện tại thiếu các migration bổ sung purchasing/refund và migration mới Phase 1.5. Lý do vận hành khiến migration chưa chạy không được xác định.
- **Hành động đề xuất:** backup + recovery rehearsal, rồi sau phê duyệt chạy `python -m petcare.database.initialize`; không reset/drop/seed.
- **Regression risk:** trung bình do MySQL DDL auto-commit và FK/index/check có thể từ chối nếu dữ liệu lệch; marker UTC ngăn chạy lại chuyển đổi 7 giờ.
- **Verification:** đủ cột/FK/index/markers; dữ liệu trước/sau khớp; `/readyz=200`; test schema `_test` và suite pass.
- **Trạng thái:** chưa áp dụng vì user yêu cầu giữ nguyên DB dev và xin xác nhận trước mọi schema mutation.

### AUD-CI-01 — FIXED

- **Mức độ:** P1 CI source-security gate.
- **Affected:** `petcare/database/readiness.py`; `petcare/repositories/tenant_cleanup_repo.py`.
- **Reproduction ban đầu:** Bandit 1.9.4 exact CI command exit 1 với ba B608.
- **Observed sau review:** hai placeholder-count SQL queries dùng set/map module constants; table identifier dùng `_EMPTY_TENANT_TABLES` literal. Values vẫn bind-param; không có untrusted value shaping SQL structure.
- **Hành động:** thêm rationale và `# nosec B608` ngay trên ba statement đã xác minh; không blanket-suppress, không sửa baseline.
- **Regression risk:** thấp; invariants hằng số được giữ.
- **Verification:** exact command từ workflow exit 0. Chi tiết tại `docs/CI_SECURITY_REVIEW.md`.

### AUD-QA-01 — FIXED

- **Mức độ:** P2.
- **Affected:** purchase service/repository/routes và `tests/integration/test_mysql_purchasing.py`.
- **Observed ban đầu:** không có MySQL lifecycle tests riêng.
- **Hành động:** thêm 4 MySQL tests bao phủ create qua route, item validation, partial/full receive, cancel, state transitions, stock/ledger, idempotent replay và rollback sau lỗi giữa transaction.
- **Regression risk:** trung bình vì receipt và inventory commit cùng transaction; tests chạy trên schema `_test`.
- **Verification:** 4/4 tests pass; toàn suite có 364/364 pass, 0 skip.

### AUD-QA-02 — Nhận hàng partial có thể bị cộng lặp nếu request được gửi lại

- **Mức độ:** P2, correctness/inventory.
- **Affected:** `petcare/routes/purchasing_routes.py`; `petcare/templates/purchasing/detail.html`; `petcare/services/purchase_service.py`; `petcare/repositories/purchase_repo.py`; `petcare/database/purchasing.sql`; `petcare/database/readiness.py`.
- **Tái hiện trước sửa:** tạo đơn 4 sản phẩm; POST nhận 2; gửi lại cùng payload khi đơn còn partial. Quan sát trước fix: lượng nhận thành 4 và đơn chuyển `received`, dù payload có thể là network retry.
- **Expected:** retry cùng request không làm tăng tồn; lần giao hàng mới cần request identity mới.
- **Root cause:** partial receiving trước đó chỉ cộng số lượng, không có idempotency key được lưu bền.
- **Hành động:** UUID hidden form token + `purchase_order_receipt_requests` unique theo tenant/key, lưu hash payload trong cùng transaction; retry cùng key/nội dung trả trạng thái hiện tại; key dùng với nội dung khác bị từ chối.
- **Regression risk:** trung bình vì additive table/migration mới và form hiện hành cần key. Rollout làm dev readiness cần migration.
- **Verification:** integration replay/altered-payload/rollback tests pass; schema `_test` readiness pass sau initializer. Chưa áp dụng migration lên dev.

### AUD-REL-01 — FIXED ở mức exact-version runtime constraints

- **Mức độ:** P2 build reproducibility.
- **Affected:** `requirements.lock`, `requirements.txt`, `Dockerfile`, `.github/workflows/ci.yml`.
- **Hành động:** thêm exact constraints từ clean install; CI/Docker/docs cùng cài `-r requirements.txt -c requirements.lock`; audit lock bằng `pip-audit -r requirements.lock`.
- **Regression risk:** trung bình khi refresh versions; thấp cho bộ đang pin.
- **Verification:** clean venv Python 3.13.3 install pass; `pip check` pass; pip-audit không có known advisory; toàn suite pass. Python 3.11/3.12 cần xác minh qua CI matrix.

### Kết quả sau thay đổi

- Python: 364/364 pass, zero skipped; 63 là MySQL integration tests.
- JavaScript: 26/26 pass.
- Bandit exact CI command: exit 0. `pip-audit`, compileall, pip check, Compose parse và diff whitespace: pass.
- `/healthz` và `/readyz` trên test DB: pass sau migration Phase 1.5. `/readyz` trên dev: 503 và chờ phê duyệt.
- Docker image build: VERIFIED ở Phase 1.5; Trivy scan: NOT TESTED. Authenticated browser/responsive/accessibility, SMTP, AI/Vision và S3: NOT TESTED như ma trận.
- Không commit. Branch/worktree không đổi vì working tree ban đầu có thay đổi chưa commit; checkpoint file-by-file nằm ngoài repository, không chứa secrets.
