# Lộ trình cải tiến có ưu tiên

Lộ trình này giữ nguyên phạm vi ứng dụng retail web và framework hiện có. Phase 5.2 đã triển khai một lát cắt Vision nhỏ trên code hiện hành; các mốc mới nhất và phần còn lại được phân biệt dưới đây.

## Cập nhật Phase 5.2 — 2026-11-10

- Hoàn thành gợi ý thuộc tính ngoại hình trong pet form, output allowlist/cap, trạng thái provider/fallback, retry/cancel-wait và apply vào field trống.
- Verification local: Python 389/389, JavaScript 34/34, Chromium 15/15, MySQL route integration, responsive 320–1440 px, Bandit CI gate, hai pip-audit lockfiles, pip check, compileall, Docker build, Compose config, /healthz=200 và /readyz=200.
- Chỉ dùng MySQL disposable petcare_phase52_test trên tmpfs, local test storage, ảnh synthetic và mock loopback. Dev/production không được thay đổi.
- Provider thật/accuracy benchmark vẫn NOT TESTED; NO-GO cho live provider tới khi có dataset rights, privacy/retention/region/egress/budget approval và per-field evaluation. Hosted CI, Trivy local, screen-reader và WCAG full audit chưa chạy.
- Chi tiết: [Phase 5.2 implementation](PHASE52_VISION_IMPLEMENTATION.md), [evaluation](PHASE52_VISION_EVALUATION.md), [security](PHASE52_VISION_SECURITY.md), [UX](PHASE52_VISION_UX.md), [Phase 5.3 provider readiness](PHASE53_PROVIDER_READINESS.md).

## 1. Sửa lỗi hiện có

1. **Nâng schema dev có phê duyệt (P1 / AUD-DB-01).** Backup và xác minh recovery; rà marker/schema/data; sau khi chủ dự án xác nhận, chạy initializer trên DB dev; không reset database. Đạt khi schema contract đầy đủ và `/readyz` trả 200.
2. **Làm xanh security gate (P1 / AUD-CI-01) — HOÀN THÀNH.** Ba B608 đã review; identifier vẫn từ tập hằng số và values bind-param; suppression hẹp được ghi cạnh câu lệnh. Exact CI Bandit command exit 0.
3. Không có P0/data-loss hay lỗi nghiệp vụ được xác nhận trong 360 Python tests và 26 JavaScript tests. Không rewrite các luồng đang đạt.

## 2. Hoàn tất chức năng còn dở

- Không tìm thấy TODO/FIXME/NotImplemented hay stub nghiệp vụ rõ ràng trong code đang chạy.
- SMTP, remote AI/AI Vision, S3 và metrics là tích hợp tùy chọn được bật bằng cấu hình, không được đánh dấu là code còn dở. Nếu yêu cầu demo/prod, cần cung cấp endpoint/account/test secret theo đúng môi trường rồi thực hiện acceptance test an toàn.
- Không thêm clinic, appointment, vaccination hoặc spa vào bản retail web trong lộ trình này; các yêu cầu đó nằm ngoài scope học thuật hiện tại.

## 3. Refactor và ổn định kiến trúc

1. **Tăng integration coverage nhập hàng (P2 / AUD-QA-01) — HOÀN THÀNH.** Bốn test MySQL cô lập cover route/service/repository/transaction, create, partial/full receive, validation, cancel, invalid transition, replay idempotency, movement và rollback.
2. Giữ route → service → repository → MySQL. Tránh chuyển framework/ORM nếu không có bằng chứng về chi phí bảo trì cụ thể.
3. **Tái lập dependency (P2 / AUD-REL-01) — HOÀN THÀNH Ở MỨC CONSTRAINTS.** `requirements.lock` pin exact runtime versions; fresh install và test host Python 3.13 pass. Tiếp tục kiểm trên matrix 3.11/3.12/3.13 qua CI; giữ pip-audit.
4. Khi thay migration, yêu cầu backup, review before/after row counts, readiness contract và kiểm tra timestamp/currency.
5. Định nghĩa một lệnh acceptance thống nhất cho compile, Python suite, JS suite, pip-audit, Bandit và Compose validation; MySQL integration phải luôn dùng tên DB hậu tố _test.

## 4. Cải thiện frontend và UX

1. Tạo dữ liệu demo trong isolated test DB rồi duyệt dashboard, customer, catalog, pet, POS, purchase, report, account và admin journey trên browser thật.
2. Kiểm tra breakpoint phone/tablet/desktop, focus order, keyboard-only, labels/field errors, contrast, empty/loading/error/success state; ghi lại browser console và failed network requests.
3. Xác nhận rõ người dùng thấy trạng thái thật sau mọi write; kiểm tra retry/no-double-submit cho receive, payment, refund, export.
4. Bảo toàn Jinja/CSS/vanilla JS và local assets nếu đáp ứng được yêu cầu; không thêm framework frontend chỉ để làm audit.

## 5. Cải thiện AI

1. Giữ local assistant làm fallback mặc định; giữ disclosure về dữ liệu gửi ra ngoài và không gửi hồ sơ khách hàng không liên quan.
2. Nếu product bật endpoint, dùng test tenant và dữ liệu tổng hợp để kiểm tra prompt injection, blank/oversized/malformed response, timeout, fallback, retry/rate limits và độ chính xác catalog intent.
3. Với Vision, đo chất lượng ranking trên bộ ảnh có nhãn; không mô tả điểm similarity như confidence nhận dạng. Đánh giá data retention/cost/provider location trước production.
4. Thử endpoint thật chỉ khi có provider URL/credentials đã được cấp cho môi trường test; không dùng secret hoặc ảnh thật trong log.
5. **Phase 5.2 technical workflow — DONE; accuracy/provider — PENDING.** Mock/synthetic suite kiểm input, output contract, fallback và UI; không đại diện model quality. Phase 5.3 readiness liệt kê các approval cần có trước staging provider.

## 6. Tính năng tùy chọn

Chỉ cân nhắc theo yêu cầu sản phẩm sau khi scope học thuật đã được bảo vệ: clinic/appointment, import/export CSV cho catalog, quản trị retention/tenant deletion, advanced search hoặc vector index. Các hạng mục này không cần thiết để hoàn tất audit hoặc ổn định luồng retail hiện hành.

## Thứ tự triển khai đề xuất

| Bước | Ưu tiên | Công việc | Điều kiện đạt |
|---|---|---|---|
| 1 | P1 | Backup, recovery rehearsal và nâng schema dev sau khi được xác nhận | `/readyz` 200; dữ liệu cũ đối chiếu được; không reset/drop |
| 2 | P1 | Chạy workflow GitHub CI + container scan trên runner có Docker | Python matrix, JS, pip-audit, Bandit và Trivy/container đều pass |
| 3 | P2 | Browser audit authenticated, responsive và accessibility trên `_test` data | Có evidence screenshot/console/network/keyboard/viewport cho journey chính |
| 4 | P2 | Theo dõi `requirements.lock` trên Python 3.11/3.12/3.13 | Mọi matrix install và test pass; lock update có review/advisory scan |
| 5 | Khi cần | Kiểm tra SMTP/AI/S3/metrics trong staging/test | Provider path/fallback/quota và ranh giới dữ liệu được chấp nhận |
| 6 | Optional | Đánh giá mở rộng ngoài scope retail | Có yêu cầu sản phẩm và tiêu chí riêng, không làm vỡ yêu cầu học thuật |

Không áp dụng migration trên dev trước khi backup/recovery được xác minh và có phê duyệt. Giữ architecture hiện tại; chỉ refactor khi có lỗi/chi phí cụ thể.
