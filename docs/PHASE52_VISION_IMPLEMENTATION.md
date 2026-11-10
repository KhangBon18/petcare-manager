# Phase 5.2 — AI Vision implementation

Ngày: 2026-11-10. Một lát cắt nhỏ trong Flask/Jinja/MySQL hiện hành; không thay framework hoặc schema.

## Lát cắt sản phẩm

Quản trị viên tải ảnh thú cưng trong form tạo/sửa hồ sơ để nhận gợi ý ngoại hình: loài, giống, màu lông, màu mắt và mô tả ngoại hình. Người dùng xem kết quả rồi bấm “Điền vào trường đang trống”. Kết quả không tự ghi database, không ghi đè trường đã nhập và không xác định giá, tình trạng bán hay chẩn đoán sức khỏe.

## Đã triển khai

- Hợp đồng kết quả có status: observations, uncertain, unrecognized, provider_unavailable; provider_status phân biệt disabled, used, partial, ambiguous, invalid_output và unavailable.
- Chỉ giữ thuộc tính allowlist dạng chuỗi; chuẩn hóa Unicode, bỏ control/format characters, giới hạn độ dài theo form, bỏ field lạ và không trả confidence, URL, HTML hay action.
- POST /pets/suggest-attributes trả JSON lỗi có status/code/error. Log chỉ gồm loại exception. Rate limit và semaphore bận trả 429 cùng Retry-After.
- UI có loading, local estimate không chắc chắn, provider error, invalid input, retry và dừng chờ. Dữ liệu render qua textContent; request cũ bị abort/loại bỏ; apply chỉ điền ô trống.
- Photo preview báo lỗi/kích thước dưới input. Server xác thực bytes thật, không tin MIME hay phần mở rộng trình duyệt.
- Tạo fixture ảnh synthetic JPEG/PNG/WebP cùng ảnh sai định dạng, hỏng, rỗng, sai đuôi và ảnh vượt giới hạn pixel.
- Thêm unit, web, MySQL route integration và Chromium workflow với mock OpenAI-compatible chỉ nghe trên 127.0.0.1.

## Kết quả đã xác minh

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| Python unit/web/MySQL | PASS | python -m unittest discover -s tests -v: 389 tests, OK, không skip; petcare_phase52_test. |
| MySQL route workflow | PASS | Test riêng dùng actor/session tenant thật, CSRF, mock provider, metadata stripping và không lưu ảnh suggestion. |
| JavaScript | PASS | node --test tests/js/*.test.cjs: 34/34. |
| Chromium đầy đủ | PASS | scripts/browser_smoke/run_smoke.py: 15/15 trên Flask thật và schema test cô lập; lỗi console/request/HTTP bất ngờ bị assertion kiểm. |
| Responsive workflow | PASS theo các viewport đo | Không tràn ngang ở 320, 390, 768, 820, 1024 và 1440 px. |
| Security/dependencies | PASS local | Bandit đúng CI exit 0; hai pip-audit lock không có vulnerability đã biết; pip check, compileall và git diff --check pass. |
| App/db readiness | PASS trong test | /healthz=200 và /readyz=200 trên petcare_phase52_test. |
| Compose/container | PASS local | docker compose config --quiet và Docker build petcare-manager-web:phase52-local hoàn tất. |

Ảnh evidence: [mobile 390 px](assets/phase52/vision-suggestions-390.png), [desktop 1440 px](assets/phase52/vision-suggestions-1440.png). Fixture chỉ là hình minh họa synthetic.

## Findings và rủi ro còn lại

### VIZ-52-01 — P2 — RESOLVED: provider output chưa có hợp đồng chặt

- **Reproduction:** mock provider trả field lạ, confidence, HTML/URL, sai kiểu hoặc chuỗi quá dài.
- **Observed / expected:** trước thay đổi parser chưa có output status và giới hạn field thống nhất; expected chỉ giữ thuộc tính đúng field/type/length, không coi confidence hay URL model trả là sự thật.
- **Root cause / fix:** parser chỉ kiểm JSON và chuyển thuộc tính chưa đủ chặt sang form; đã thêm allowlist, normalize/cap, bỏ field ngoài contract và provider status.
- **Evidence / regression risk:** unit cases về sai kiểu, field lạ, cap và injection; Python 389/389, JS 34/34, browser 15/15. Risk còn lại thấp trong code mock; model correctness không được suy ra.

### VIZ-52-02 — P2 — RESOLVED: lỗi route thiếu feedback/log boundary thống nhất

- **Reproduction:** gửi input sai hoặc inject exception từ service/provider adapter.
- **Observed / expected:** lỗi cần trả mã/feedback ổn định cho form; không để exception/provider message lọt vào response hoặc log.
- **Root cause / fix:** nhánh unexpected error không có contract JSON nhất quán và log exception có thể chứa chi tiết provider; đã thêm status/code/error chung và chỉ log loại exception.
- **Evidence / regression risk:** route web tests cho missing/invalid/busy/safe 500 và browser retry/error states. Risk thấp; cần giữ kiểm tra này khi mở rộng route.

### VIZ-52-03 — P2 — RESOLVED: form thiếu recovery state rõ

- **Reproduction:** upload ảnh hợp lệ, đổi ảnh khi request trước còn chạy, hoặc giả lập timeout/503.
- **Observed / expected:** người dùng cần biết đang xử lý, request cũ không được thay kết quả mới, có thể retry/dừng chờ và manual fields phải được giữ.
- **Root cause / fix:** UI trước đây chỉ tự gửi sau khi chọn file; đã thêm loading/error/retry/cancel-wait, stale response protection, text-only rendering và apply blank-only.
- **Evidence / regression risk:** 3 dedicated JS tests và Chromium user flow; risk thấp, còn browser/AT coverage giới hạn như dưới.

### VIZ-52-04 — P2 — OPEN / NOT TESTED: chưa có model accuracy benchmark

- **Reproduction:** không thể kết luận field chính xác từ mock JSON hoặc synthetic minh họa.
- **Observed / expected:** chỉ transport/parser/fallback được xác minh; trước khi đưa gợi ý ra thực tế cần per-field precision/recall/abstain trên ảnh có quyền và nhãn độc lập.
- **Root cause / recommendation:** chưa có licensed dataset và approval provider; làm theo [Phase 5.3 readiness](PHASE53_PROVIDER_READINESS.md), không bật provider thật.
- **Risk / verification:** trung bình/cao nếu dùng gợi ý sai làm dữ liệu hồ sơ; đóng finding khi protocol, ngưỡng nghiệp vụ và báo cáo đánh giá được review/duyệt.

### VIZ-52-05 — P2 — PARTIAL: accessibility chưa được audit đầy đủ

- **Reproduction:** kiểm bằng screen reader, zoom 200%, high contrast, Safari/Firefox hoặc cảm ứng.
- **Observed / expected:** label, aria-live, aria-busy và keyboard Enter đã xác minh; không có bằng chứng cho screen reader/WCAG toàn trang.
- **Root cause / recommendation:** lượt này ưu tiên flow mới và browser Chromium; tiếp tục manual/axe audit trước release.
- **Risk / verification:** trung bình; cần kết quả không có blocker trong các browser/AT được hỗ trợ và checklist focus/error announcements.

## Giới hạn

AI_VISION_ENABLED vẫn tắt mặc định. Chromium workflow bật cờ chỉ trong process kiểm thử và gửi ảnh synthetic đến mock loopback. Không gọi provider thật, SMTP hoặc S3. Fixture xác nhận pipeline/response và lỗi giao thức; nó không đo độ chính xác nhận dạng. Không có screen-reader/axe audit mới hoặc hosted GitHub Actions result trong lượt này.

Không sửa petcare_shop_dev hoặc production; không có migration/schema change. Không stage/commit. Xem [architecture](PHASE52_VISION_ARCHITECTURE.md), [evaluation](PHASE52_VISION_EVALUATION.md), [security](PHASE52_VISION_SECURITY.md) và [provider readiness](PHASE53_PROVIDER_READINESS.md).

## Safety checkpoint

Trước khi sửa code, xác minh checkpoint ngoài repository tại /Users/heisenbon/Documents/Codex/petcare-phase511-checkpoint-20261110 và tạo checkpoint Phase 5.2 tại /Users/heisenbon/Documents/Codex/petcare-phase52-checkpoint-20261110; SHA256SUMS của checkpoint mới được kiểm tra. Branch đang dùng là solo/khang-petcare tại HEAD 8634300f4b5ad4700d6702a048220d6597c4e200. Các thay đổi có trước được giữ nguyên; không stage, commit, reset, clean hoặc stash.

## Incremental review/commit proposal

Không có file nào được stage hoặc commit. Vì những file backend/UI chính đã có diff từ trước checkpoint, không nên stage cả file để tạo commit Phase 5.2. Khi chủ dự án muốn commit, trước tiên tách delta bằng cách so checkpoint với trạng thái hiện tại, review từng hunk trong clean worktree, rồi tạo lần lượt: (1) backend response contract + unit/web/MySQL tests; (2) form UX + JS/CSS + browser coverage; (3) synthetic evaluation fixtures, screenshots và documentation. Giữ mọi pre-existing hunk ngoài ba commits này.
