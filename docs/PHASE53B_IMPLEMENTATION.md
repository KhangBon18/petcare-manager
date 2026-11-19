# Phase 5.3B — Kết quả tiền kiểm an toàn

Ngày: 2026-11-10. Trạng thái: **PRE-FLIGHT HOÀN TẤT; LIVE PILOT BLOCKED**. Không gọi API provider thật, không gửi ảnh ra ngoài, không bật AI Vision cho người dùng và không sửa DB development/production.

## Phạm vi đã làm

- Đọc các tài liệu Phase 5.3A và approval protocol; kiểm tra manifest, prediction fixture, adapter, cấu hình Vision, checkpoint và Git diff.
- Xác minh checkpoint Phase 5.1.1, 5.2, 5.3A và Phase 5.3B. Checksum của các tệp Phase 5.3B hợp lệ. Checkpoint Phase 5.3B nằm ngoài repo tại `/Users/heisenbon/Documents/Codex/petcare-phase53b-checkpoint-20261110`.
- So sánh model bằng tài liệu nhà cung cấp chính thức hiện hành; phân biệt tính năng công bố, tương thích adapter và điều kiện tài khoản chưa xác minh.
- Đối chiếu quyền dữ liệu: manifest có hai ảnh synthetic mechanics-only, nhưng không có bằng chứng cấp quyền gửi tới nhà cung cấp. Số ảnh đủ điều kiện egress: **0**.
- Chốt lý do NO-GO và yêu cầu dataset/consent, chính sách vùng/retention, giới hạn chi phí, local guard, số lần gọi, credentials và abort procedure trước bất kỳ request nào.

## Quyết định model

**Ứng viên ưu tiên có điều kiện:** OpenAI GPT-6 Luna (`gpt-6-luna`) qua `https://api.openai.com/v1/chat/completions`. Đây là lựa chọn hợp lý nhất để thử tương thích vận chuyển vì tài liệu hiện hành xác nhận image input, Chat Completions và structured outputs; adapter hiện tại đã tạo Chat Completions với image data URI. Giá token text niêm yết thấp cho prompt ngắn.

Đây không phải kết luận về độ chính xác hay lựa chọn đã được duyệt. App chưa gửi JSON Schema `response_format`; client hiện parse/validate sau response. Chưa xác minh live tính tương thích các tham số model hiện có (`temperature`, token limit và `reasoning_effort`) với model này. Giai đoạn tiếp theo cần một request contract/provider schema test riêng trước khi dùng ảnh được duyệt.

Claude Haiku 5.5 và Gemini 3.1 Flash-Lite vẫn là ứng viên đối chiếu, nhưng không có kết quả chất lượng nào. Gemini có lớp OpenAI compatibility đang beta và có thể nhận data URI image; tuy nhiên hard spend cap có thể trễ khoảng 10 phút. Claude có Messages API/structured output và workspace spend controls nhưng cần adapter/message-auth contract riêng. Bảng chi tiết, pricing và các đánh đổi ở [PHASE53B_MODEL_EVALUATION.md](PHASE53B_MODEL_EVALUATION.md).

## Data readiness và NO-GO

Dataset đang có `petcare-vision-synthetic-mechanics` v1.0.0: 2 hình synthetic, 4 nhãn construction ở `species`/`coat_color`, không có nhãn độc lập do hai annotator, không có ảnh held-out độc lập và không có mẫu unknown/abstention. Các edge scenarios còn pending; fixture GIF/corrupt/empty/oversized chỉ dùng kiểm tra xử lý ảnh. Các metric mock 1.0 trước đây là harness mechanics, không phải kết quả model.

Không có dataset identity với giấy phép/consent egress được ghi nhận. Theo điều kiện trong yêu cầu, **dừng trước live evaluation**. Không dùng dữ liệu pet/customer thật để lấp khoảng trống.

## An toàn, cấu hình và mã nguồn

- Provider vẫn off mặc định (`AI_VISION_ENABLED=0`); trong môi trường `APP_ENV=test`, test guard chặn external host.
- Nếu sau này được duyệt, candidate staging cần `AI_VISION_MAX_RETRIES=0`, credential server-side từ secret manager, API key riêng, schema test riêng, file storage tạm và network egress chỉ tới hostname được duyệt.
- App chưa có global cap 50 provider attempts, cumulative-dollar guard, concurrency-one reservation hoặc hostname allowlist. Không coi rate limit theo phút hiện tại là giới hạn tổng.
- Project hard-spend control của OpenAI có thể dừng request bằng `429`, nhưng nhà cung cấp nêu rõ enforcement không tức thời và spend có thể vượt nhẹ. Vì vậy không thể cam kết tổng charge tuyệt đối ≤ USD 1 chỉ bằng cài đặt provider cap.
- Phase này chỉ thêm tài liệu. Không đổi Python/JavaScript, test, config runtime, dependency, schema DB hoặc lockfile. Không stage/commit/reset/clean/stash.

## Git và checkpoint

- Branch/HEAD lúc tiền kiểm: `solo/khang-petcare` / `8634300f4b5ad4700d6702a048220d6597c4e200`.
- Có 1.146 status records trước cập nhật tài liệu: 112 modified tracked, 1.034 untracked; không có staged changes. Nội dung gồm app/backend/frontend, test/fixtures, CI/scripts, 144 mục docs và `.agents/skills` untracked (khoảng 25 MB). Không có đường dẫn credential được đưa vào checkpoint; danh sách loại trừ rỗng. Không kết luận ai là tác giả của thay đổi có trước.
- Checkpoint Phase 5.3B có tracked patch, staged patch rỗng, danh sách untracked, archive untracked, trạng thái/HEAD/branch, hướng dẫn restore và SHA-256 manifest. Checksum đã xác minh PASS trước khi sửa docs.
- Không tạo commit trong phase. Đề xuất sau này: (1) harness/fixtures/tests; (2) transport, quota và security guard; (3) UI/manual-review thay đổi; (4) docs/results. Trước đó cần clean review checkout và tách hunk có trước từ checkpoint; không stage file pre-dirty nguyên khối.

## Chuyển giao

Pilot hiện **BLOCKED** chờ dataset/consent, security/privacy/region decision, model request-contract verification, cost control khả thi và phê duyệt rõ ràng. Hồ sơ và gói cần duyệt nằm ở [PHASE53B_PROVIDER_PILOT.md](PHASE53B_PROVIDER_PILOT.md). Chỉ sau khi có dataset hợp lệ và approval cụ thể mới lập kế hoạch provider request. Không tự bật trong luồng người dùng.

## Hồi quy offline sau tiền kiểm

Môi trường QA là MySQL 8.4 disposable Compose service, loopback port riêng, schema `_test`, DB data trong tmpfs, media/log/browser output trong `/tmp`, provider config rỗng/off và test egress guard bật. Không kết nối development/production.

| Gate | Kết quả |
|---|---|
| Python | PASS — 405/405, 0 skip. |
| JavaScript | PASS — 36/36. |
| Playwright/Chromium | PASS — 16/16, 0 skip với port app 52037 và mock Vision loopback. Lần chạy đầu dùng 5061 bị `ERR_UNSAFE_PORT`; chạy lại trên port an toàn đạt. |
| Vision evaluation CLI | PASS trên mock fixture; 2 synthetic rows, provider accuracy vẫn NOT MEASURED. |
| App health/readiness | PASS trên QA — `/healthz=200`, `/readyz=200`. |
| Bandit CI command | PASS với baseline hiện tại; B608 `nosec` warnings được ghi nhận, không fail gate. |
| pip-audit (runtime + browser), `pip check`, npm audit | PASS; không có vulnerability đã biết trong hai Python lock scans, không dependency conflict, npm reports 0 vulnerabilities. |
| Compile, Compose config, Docker build, `git diff --check` | PASS. Docker build dùng context tạm đã loại `.env`, `.agents`, docs, tests và `.venv`; image chỉ local, không push. |

Regression tự động là offline/mock; không kiểm provider thật, SMTP, S3, hosted CI, Trivy hoặc development readiness trong Phase 5.3B.
