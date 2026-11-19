# Trạng thái phát hành học thuật cuối — Phase 6.4

Ngày kiểm tra: 2026-11-11
Source baseline: nhánh `solo/khang-petcare`, commit `691c5275556a038abe315f977ecb803a39e6b4c3` (documentation release commit được tạo sau baseline này).

## Quyết định

- **Nộp học thuật: GO WITH CONDITIONS.** Source và tài liệu hiện có đủ để chuẩn bị submission, sau khi đưa bốn tài liệu Phase 6.4 vào gói nộp và đối chiếu với rubric chính thức mà sinh viên nhận được. Repository không chứa rubric/đề cương chấm điểm chính thức.
- **Demo học thuật: CONDITIONAL GO.** Launcher, database QA, workers và health/readiness đã được chạy thật. Operator phải hoàn tất checklist phòng học trước khi trình bày.
- **Production: NO-GO.** Không có nghiệm thu provider thật, vận hành production hoặc accessibility đầy đủ.
- Phase 6.4 chỉ phát hành bốn tài liệu học thuật; không sửa source/runtime code và không thay đổi database dev/production. Bốn tài liệu được commit/push riêng trên nhánh đã xác minh; không tạo tag hoặc GitHub Release.

## Bằng chứng release

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| Source baseline | VERIFIED | Trước documentation release commit, HEAD là `691c5275556a038abe315f977ecb803a39e6b4c3`. |
| Branch/upstream at start | VERIFIED | `solo/khang-petcare` tracking `origin/solo/khang-petcare`; local/remote ahead-behind `0/0` trước khi commit bốn tài liệu. |
| Working tree trước publish | VERIFIED | Chỉ bốn tài liệu `docs/FINAL_*.md` và các mục tooling local có sẵn `.agents/`, `docs/skills.md`, `skills-lock.json` ở trạng thái untracked; không có source change. Tooling local không được stage hoặc push. |
| Credential tracking | VERIFIED có giới hạn | `git ls-files` trong nhóm `.env` chỉ liệt kê `.env.example`, không có `.env` thật. Local không cài Trivy/Gitleaks; dựa trên CI source-security hiện hành. Không copy secret vào report. |
| GitHub Actions trên source baseline | PASS 6/6 | Run #13 cho commit `691c5275556a038abe315f977ecb803a39e6b4c3`, conclusion `success`, 6 jobs thành công: `source-security`, `container`, `browser-smoke`, `verify (3.11)`, `verify (3.12)`, `verify (3.13)`. [GitHub Actions run #13](https://github.com/KhangBon18/petcare-manager/actions/runs/43008051380), REST metadata cập nhật `2026-11-11T11:00:38Z`. Đây là kết quả source baseline; CI của documentation release commit được theo dõi riêng trên Actions.
| Python/JavaScript/Playwright | PASS theo release baseline | Python `428/428`; JavaScript `41/41`; Chromium Playwright `18/18`. Được ghi ở `docs/PHASE62_IMPLEMENTATION_REPORT.md`; không rerun toàn bộ suite trong Phase 6.4. |
| Launcher/health | PASS trong Phase 6.4 | `scripts/demo/classroom.sh --target qa` khởi động bằng venv của project; `/healthz 200 ok`, `/readyz 200 ready`, `/workersz 200 ready`. Sau `r`, cả ba vẫn 200. `q` exit 0; launcher dọn container/network/process/storage của phiên QA. |
| Database safety | VERIFIED | Chỉ schema QA `_test`/tmpfs do launcher tạo được khởi tạo/reset. Không đọc hoặc mutate `petcare_shop_dev`/production. |
| Browser automation | PASS theo baseline | Chromium/Firefox/WebKit representative run `3/3`; 22 axe scans Chromium/Firefox, 0 violations, 73 incomplete nodes. WebKit engine không chạy axe vì instrumentation làm nhiễu CSP; xem `docs/PHASE62_CROSS_BROWSER_REPORT.md`. |

## Accessibility — kết quả và giới hạn

- **Keyboard/focus login: CHECKED.** Trong browser session cô lập trỏ tới app QA, Tab di chuyển qua skip navigation, language, apply, link logo, Store ID, Username, Password, Sign in và Forgot password. Focus ring nhìn thấy rõ trên skip link và trường Username. Chỉ màn hình login được xem trực tiếp bằng keyboard ở Phase 6.4; không đồng nghĩa mọi workflow đều hoàn chỉnh bằng keyboard.
- **axe: CHECKED có giới hạn.** Reviewer chạy lại 7 trạng thái Chromium: dashboard, customer form, pet form, product form, POS, purchasing, reports. Có 0 violations. Axe incomplete gồm 14 nodes ở rule `color-contrast` (dashboard 8, ba form 1 mỗi trang, reports 3; POS/purchasing 0). Các node đã xem là chart SVG/date labels có background là image hoặc ký tự trang trí (invoice glyph/arrow) mà axe không thể tính contrast tự động. Không xác nhận được lỗi WCAG từ các node này; cũng chưa đo contrast ratio độc lập. Cross-browser snapshot trước đó ghi 73 incomplete nodes tổng.
- **Zoom thật 200%: NOT TESTED.** Automation keyboard shortcut không làm viewport/scale thay đổi, do đó không xem đây là xác minh browser zoom. Kiểm tra 200% phải làm bằng browser chrome thật.
- **VoiceOver: NOT TESTED.** VoiceOver.app có trên máy nhưng không chạy trong phiên rà soát; không xác nhận screen reader announcement.
- **Native Safari: NOT TESTED.** Playwright WebKit đạt representative checks; không phải kết quả Safari desktop. Firefox/WebKit trên macOS/OS khác hoặc thiết bị thật ngoài matrix cũng chưa nghiệm thu.
- Không có xác nhận WCAG 2.1/2.2 conformance.

## Tài liệu học thuật

Đã đối chiếu overview, architecture, ERD, API contract, routes/services/repositories, module inventory, demo script, defense Q&A, AI/Vision limitations và CI/test reports. Các tài liệu chính phản ánh Flask/Jinja/MySQL hiện tại; `docs/archive/` chứa lịch sử desktop cũ, không phải mô tả runtime web hiện hành.

Không tìm thấy tệp rubric, assignment brief hoặc grading sheet chính thức trong repository. Không tự đặt thêm yêu cầu nộp. Sinh viên cần so sánh với thông báo môn học ngoài repo.

## Hạn chế chưa giải quyết trong scope

- Native zoom 200%, VoiceOver/NVDA, đo contrast thật và native Safari chưa test.
- SMTP thật, S3, payment gateway, provider LLM/Vision, cost/latency và quality của model thật chưa test.
- Cross-browser scope là representative Playwright engines, không phải toàn ma trận browser/OS/device.
- Các test counts là suite đã chạy ở release baseline, không phải coverage 100%.
- Không có live production setup, backup/restore drill trên production-like infrastructure hoặc SLA evidence.
- Release chỉ được khuyến nghị cho demo local với dữ liệu tổng hợp; production vẫn NO-GO.

## Files thay đổi ở Phase 6.4

- Tạo: `docs/FINAL_SUBMISSION_CHECKLIST.md`
- Tạo: `docs/FINAL_DEMO_OPERATOR_GUIDE.md`
- Tạo: `docs/FINAL_DEFENSE_PREPARATION.md`
- Tạo: `docs/FINAL_ACADEMIC_RELEASE_STATUS.md`
- Không đổi code/tests/config/database schema. Chỉ bốn tài liệu học thuật được stage/commit/push.
- Giữ nguyên các mục local có sẵn: `.agents/`, `docs/skills.md`, `skills-lock.json`.

## Quy trình tiếp theo

1. Sinh viên mở checklist submission và so với rubric/đề bài chính thức.
2. Trước buổi nói, thực hiện operator preflight, login trên máy chiếu, kiểm tra 200% và screen reader nếu rubric yêu cầu, rồi xác nhận demo role/flow.
3. Giữ credentials, local QA files và local tooling ngoài gói submission.
4. Dùng trang GitHub Actions để kiểm tra workflow của documentation release commit; không suy diễn CI pass từ kết quả của source baseline.
