# Phase 5.3A — Vision Evaluation Engineering

Ngày: 2026-11-10. Phạm vi: xây dựng harness đánh giá độc lập, khóa outbound provider trong test, tăng kiểm thử UX/accessibility và giữ nguyên kiến trúc Flask/Jinja/MySQL. Không gọi provider thật; không sửa schema DB.

## Kết quả triển khai

- Thêm scorer provider-neutral ở `petcare/vision/evaluation.py` và CLI `scripts/vision_evaluation/evaluate.py`. Scorer chỉ đọc manifest/prediction JSON, không mở ảnh để gửi mạng và không gọi provider.
- Thêm manifest synthetic có version, trạng thái quyền sử dụng, nguồn nhãn, split, trường được chấm và danh sách scenario còn thiếu; thêm prediction fixture cho mock deterministic.
- Thêm 9 test harness kiểm tra confusion counts/metrics, abstention, field bỏ trống, telemetry, determinism, exact ID matching và chặn path traversal.
- Mở rộng client hiện có, không thêm framework/provider SDK: giới hạn request 8 MiB, chuẩn hóa lỗi HTTP/network, retry tối đa một lần chỉ cho lỗi tạm thời; không retry 4xx/429 hoặc output không hợp lệ. Timeout cấu hình hiện hữu vẫn áp dụng; response cap 512 KB và chặn redirect được giữ.
- Trong `APP_ENV=test`, client chặn provider egress bên ngoài; chỉ cho phép IP loopback dạng literal khi `AI_TEST_ALLOW_LOOPBACK_PROVIDER=1`. Mặc định vẫn chặn cả loopback. Thêm kiểm tra cấu hình `AI_VISION_MAX_RETRIES` (0–1) và tùy chọn `AI_REASONING_EFFORT`.
- UI có hành động bỏ qua gợi ý, đưa focus về input ảnh, giữ nguyên trường đã nhập và không tự lưu. Tắt fade opacity ở motion entrance để tránh chữ giảm tương phản trong animation.
- Thêm axe-core 4.14.0 vào package/lock riêng của test a11y; CI browser job chạy `npm ci` và `npm audit`; không thêm dependency runtime.

## Hợp đồng trường Vision

Trường hiển thị trong biểu mẫu thú cưng: `species` (tối đa 80 ký tự), `breed` (100), `coat_color` (80), `eye_color` (60), `appearance_tags` (255). Adapter/parser cho phép các quan sát `coat_pattern`, `coat_length`, `size`, `shape`; dịch vụ ánh xạ các mục này vào mô tả ngoại hình `appearance_tags`. Không có field chẩn đoán sức khỏe, tuổi, danh tính hay hành động.

Không biết/không đủ bằng chứng được biểu thị bằng field vắng hoặc rỗng và trạng thái `ambiguous`/`unrecognized` theo response contract hiện có; một số chuỗi unknown rõ ràng được chuẩn hóa thành abstention. Không có confidence score được bịa hoặc sử dụng.

Người dùng admin xem từng gợi ý, có thể bỏ qua hoặc bấm áp dụng vào trường đang trống. Field đã điền không bị ghi đè; không có POST lưu riêng hay tự submit form. Lưu dữ liệu chỉ xảy ra khi admin chủ động submit form pet hiện hữu.

## Quy trình chạy cục bộ

```sh
python scripts/vision_evaluation/evaluate.py \
  --manifest tests/fixtures/vision/evaluation/manifest.json \
  --predictions tests/fixtures/vision/evaluation/mock_predictions.json \
  --json-out docs/assets/vision-evaluation/mock-results.json \
  --markdown-out /tmp/vision-evaluation-mock.md
```

Lệnh chỉ tính điểm dữ liệu đã có. Không cần key, endpoint hoặc mạng. Để chạy regression trong môi trường dự án: `python -m unittest discover -s tests -v`; JS: `node --test tests/js/*.test.cjs`; browser QA: `python scripts/browser_smoke/run_smoke.py` với biến môi trường MySQL test và storage cô lập theo `docs/QA_TEST_ISOLATION.md`.

## Bằng chứng tại Phase 5.3A

| Gate | Kết quả | Giới hạn |
|---|---|---|
| Python | PASS — 405/405, 0 skip | MySQL QA disposable; không áp dụng dev/production. Verbose run log được tạo trong temp QA và xóa cùng data sau khi kiểm tra. |
| JavaScript | PASS — 36/36 | Node local. |
| Chromium browser | PASS — 16/16 | App thật trên MySQL test, mock Vision loopback; tất cả 16 test gồm case Vision/a11y mới. Browser traces/screenshots ở temp QA được xóa; axe summary được giữ ở docs assets. |
| Vision axe | PASS trong 5 trạng thái | 0 violation nghiêm trọng/nguy cấp; một contrast check của glyph mũi tên trang trí là `incomplete`, không phải pass xác nhận bằng mắt. |
| Bandit CI gate | PASS | Lệnh baseline của CI trả exit 0; còn warning `nosec` B608 baseline đã có, xem `docs/CI_SECURITY_REVIEW.md`. |
| pip-audit | PASS | Lock runtime và browser: không có advisory đã biết ở lần quét. |
| npm audit / pip check | PASS | axe package: 0 vulnerability; Python: không dependency conflict. |
| Python compile / diff check | PASS | `compileall` và `git diff --check` exit 0. |
| Compose / Docker | PASS | `docker compose config --quiet`; build local `petcare-manager-web:phase53a-local` thành công. Không deploy. |
| Health/readiness | PASS trên QA | Browser server chỉ khởi động tiếp sau khi `/readyz=200` trên schema test. Dev `/readyz` không được sửa hoặc retest bằng migration. |
| Hosted CI / Trivy | NOT TESTED | Không push và không khởi chạy remote workflow; Trivy chưa chạy. |

## Data boundary

QA MySQL chạy trong Docker Compose project riêng, volume tmpfs; schema `petcare_phase53a_test`, media và kết quả browser ở `/tmp/petcare-phase53a-qa`. QA config có quyền file riêng và không in secret ra log. Không kết nối hoặc mutate `petcare_shop_dev` hay production. Checkpoint trước thay đổi nằm tại `/Users/heisenbon/Documents/Codex/petcare-phase53a-checkpoint-20261110`.

## Rủi ro còn lại

- Độ chính xác model thật: **NOT MEASURED**; hai hình minh họa không thể làm mẫu đại diện.
- Provider ngoài, egress, retention thực tế, latency, token/cost thực và credential rotation: **NOT TESTED**.
- Client chỉ tương thích OpenAI Chat Completions. Output được parse/allowlist sau phản hồi; chưa ép JSON mode/provider schema.
- Không xác minh bằng screen reader, true browser zoom 200%, Safari/Firefox hay audit WCAG toàn ứng dụng. Không có hosted CI run.
- Retry một lần có thể cộng thêm chi phí/lỗi lặp khi mở provider; Phase 5.3B nên cấu hình `AI_VISION_MAX_RETRIES=0` khi giới hạn số request.

Xem [benchmark spec](VISION_BENCHMARK_SPEC.md), [results](VISION_EVALUATION_RESULTS.md), [privacy/cost](VISION_PRIVACY_AND_COST.md) và [Phase 5.3B approval gate](PHASE53B_PROVIDER_APPROVAL.md).
