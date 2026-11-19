# Báo cáo Phase 1.5 — ổn định và mở rộng coverage

Ngày: 2026-11-09

Phạm vi: sửa an toàn, cộng thêm, không redesign UI/kiến trúc và không ghi vào DB dev.

## Tóm tắt

- Thêm migration request ledger để nhận diện retry cho purchase-order partial receiving; replay đúng UUID/nội dung không ghi stock lần hai.
- Bổ sung bốn MySQL integration tests thực tế cho purchase-order lifecycle, transition, validation và rollback.
- Giải quyết ba cảnh báo B608 bằng suppression có lý do tại từng câu đã rà soát; không dùng blanket suppression.
- Thêm `requirements.lock` exact-version từ clean install và áp dụng constraints ở README, CI và Dockerfile.
- Điều kiện schema trên DB dev vẫn chưa đạt. Không chạy migration/seed/write trên `petcare_shop_dev`; phải có backup và phê duyệt tường minh.

## Kết quả kiểm thử

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| Cài đặt dependencies khóa | VERIFIED | Virtualenv mới Python 3.13.3 cài `-r requirements.txt -c requirements.lock` thành công. |
| Python suite | VERIFIED | 364/364 pass, 0 skip trên MySQL `_test` cô lập. |
| Purchase integration | VERIFIED | 4/4 test mới pass; route thật, MySQL, CSRF, stock ledger và rollback. |
| JavaScript | VERIFIED | 26/26 pass. |
| Bandit | VERIFIED | Câu lệnh exact CI exit 0. |
| pip-audit | VERIFIED | `pip-audit -r requirements.lock`: không tìm thấy advisory đã biết. |
| pip check | VERIFIED | `No broken requirements found.` |
| Python compilation | VERIFIED | `compileall -q run.py main.py petcare tests` exit 0. |
| Compose parse | VERIFIED | `docker compose config --quiet` exit 0. |
| Docker image | VERIFIED | `docker build --tag petcare-manager-web:phase15 .` thành công; image `linux/arm64`, Python 3.12. |
| Trivy image scan | NOT TESTED | CLI `trivy` không có trong môi trường; GitHub Actions image/secret scan chưa chạy. |
| `/healthz`, `/readyz` trên schema test | VERIFIED | Liveness và readiness được kiểm bằng app Flask với DB `_test` đã migrate. |
| `/readyz` trên DB dev | BLOCKED | Vẫn trả 503; không áp dụng migration theo yêu cầu. |
| Git whitespace | VERIFIED | `git diff --check` exit 0. |

Hai lần chạy full suite đầu sau thay đổi phát hiện lỗi cần sửa: thiếu English translations, fixture readiness đếm sai số marker, và record test synthetic còn lại sau một lần teardown thất bại. Đã thêm bản dịch, sửa fixture, dọn riêng dữ liệu test theo prefix trong schema `_test`, sau đó chạy lại toàn suite thành công. Không sửa/đụng dữ liệu ngoài schema `_test`.

## Git và an toàn dữ liệu

Checkout có nhiều thay đổi người dùng từ trước ở source, tests và docs; không chuyển branch/worktree vì có thể tách/mất quan hệ giữa các thay đổi đó. Không commit. Đã lưu bản copy và SHA-256 checkpoint cho các file trước khi chạm vào chúng tại `/tmp/petcare-phase15-checkpoint-20261109` (không bao gồm `.env`/credentials). Chỉ thay đổi file trong phạm vi Phase 1.5; record test được tạo trong `_test` riêng. `petcare_shop_dev` chỉ có truy vấn metadata/count/integrity read-only.

## Trạng thái audit issue

| Issue | Mức độ | Trạng thái hiện tại |
|---|---|---|
| AUD-DB-01 | P1 | BLOCKED chờ backup và xác nhận trước khi chạy initializer trên dev. |
| AUD-CI-01 | P1 | FIXED; exact Bandit gate pass. |
| AUD-QA-01 | P2 | FIXED; bốn MySQL lifecycle tests mới pass. |
| AUD-QA-02 | P2 | FIXED; retry cùng request key/payload được idempotent bằng bảng ledger cộng thêm. |
| AUD-REL-01 | P2 | FIXED ở mức exact-version runtime constraints; chưa tạo hash lock/bit-for-bit container lock. |

## Giới hạn còn lại

Không tuyên bố production-ready. DB dev chưa ready; migrations DDL chưa được áp dụng/diễn tập đầy đủ từ schema cũ. UI authenticated/responsive/accessibility, Trivy scan, SMTP, AI thật, AI Vision và S3 chưa được xác minh. Docker image đã build thành công nhưng chưa chạy acceptance trên container. Không có benchmark hoặc branch coverage.

## Bước kế tiếp

1. Nhận xác nhận để chuẩn bị/ap dụng migration DB dev sau khi backup và recovery rehearsal.
2. Chạy browser acceptance cho authenticated journeys, responsive và accessibility bằng isolated test data.
3. Chạy đầy đủ GitHub CI và Trivy scan; container build đã pass cục bộ. Hoàn tất kiểm tra SMTP/AI/S3 chỉ trên staging và credentials được cấp.
