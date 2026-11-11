# Phase 6.0 — xác minh baseline phát hành

Ngày kiểm tra: 2026-11-11. Repository: `KhangBon18/petcare-manager`.

## Trạng thái Git và checkpoint

- Branch: `solo/khang-petcare`; upstream: `origin/solo/khang-petcare`.
- Baseline local/remote đã fetch trước khi phát hành: `4bb9d0821f71266b47470a2acf0c83d077536a28`; ahead/behind lúc đó `0/0`.
- Trước staging không có staged change. Thay đổi Phase 5.5 được review và chuẩn bị đưa lên branch này; không đổi branch, không rewrite lịch sử và không dùng force push.
- Checkpoint bền vững trước thao tác phát hành: `/Users/heisenbon/Documents/Workspace Code/NNLTPython/.release-checkpoints/phase60-preflight-20261111/`. Git bundle, tracked diff và tar untracked đã được xác minh; các file `.agents/`, `docs/skills.md`, `skills-lock.json` được checkpoint nhưng loại khỏi release.
- Không có `.env`, credential thật, dump database, virtualenv hay QA database được đưa vào release.

## Thay đổi được xác minh

- Assistant operations overview gọi các service read-only hiện có; truy cập admin/tenant được kiểm ở server; không gọi provider hoặc ghi dữ liệu.
- Unit, MySQL integration, JavaScript và browser smoke được mở rộng cho overview, purchasing facts, quyền, tenant scope, trạng thái không sẵn sàng và giao diện responsive.
- Browser smoke dùng `PETCARE_PRESERVE_DOC_ASSETS=1` để lưu các ảnh Phase 4.3/5.4/5.5 vào thư mục artifact tạm trong lúc xác minh.
- Thêm `.agents/` và `skills-lock.json` vào `.dockerignore`: Dockerfile dùng `COPY . .`; kiểm tra image sau build xác nhận hai mục tooling này không có trong `/app`.
- Hai ảnh Phase 5.5 hiện có không bị ghi đè. SHA-256 trước/sau browser suite giữ nguyên:
  - `operations-overview-mobile-bottom.png`: `c46af35f7752c0ace6a541091fb09ec6c0d34354dd8a016e5088e73f0f35a897`
  - `operations-overview-mobile-top.png`: `2b939a9cf4b7d29c949f1dce5f2e53fd5c5dea2674229e02b67c6282f703c8e2`

## Regression và quality gates local

| Gate | Kết quả | Bằng chứng / giới hạn |
|---|---|---|
| Python unit, web, MySQL integration | **PASS — 421/421**, 0 skip | `python -m unittest discover -s tests -q`; MySQL 8.4 schema `_test` mới, tmpfs; `/readyz=200`. |
| JavaScript | **PASS — 40/40** | `node --test tests/js/*.test.cjs`. |
| Playwright Chromium | **PASS — 18/18**, 0 skip | `python scripts/browser_smoke/run_smoke.py`; schema và storage QA riêng; `/healthz=200`, `/readyz=200`. Bao gồm Assistant, Vision mock/offline và các browser journeys hiện có. |
| Browser diagnostics | **PASS theo suite** | 0 page errors và failed requests; một console/HTTP 403 `/users/` được xác nhận là staff bị chặn đúng quyền. |
| Axe | **0 violations**, có incomplete | 31 state scans, 36 incomplete cần xem xét thủ công; không chứng minh WCAG đầy đủ, screen reader hoặc zoom/browser coverage đầy đủ. |
| Bandit | **PASS** | Đúng lệnh CI và `.security/bandit-baseline.json`; exit 0. Cảnh báo B608/nosec hiện có vẫn được in. |
| Python dependency audit | **PASS** | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: không có known vulnerabilities tại thời điểm quét. |
| JavaScript dependency audit | **PASS** | `npm audit --prefix tests/a11y`: 0 vulnerabilities. |
| Package / compilation | **PASS** | `pip check`; `python -m compileall -q petcare scripts tests`. |
| Compose / container | **PASS** | `docker compose config --quiet`; `docker build --tag petcare-manager-web:phase60-release .`; image chạy với user `petcare`, không chứa `.agents/` hoặc `skills-lock.json`. Build context sau exclude là 285 KB. |
| Diff hygiene | **PASS tại lượt kiểm tra** | `git diff --check`; phải chạy lại sau cập nhật tài liệu cuối. |

Lượt Python đầu dùng QA harness có hai giá trị mật khẩu khác nhau cho MySQL/app, dẫn tới MySQL 1045 và lỗi readiness. Harness được sửa để dùng cùng một mật khẩu ngẫu nhiên; chạy lại trên container/schema mới cho kết quả 421/421. Đây là lỗi setup của lượt chạy đầu, không phải lỗi ứng dụng.

## Ranh giới dữ liệu và dịch vụ

- Chỉ dùng MySQL QA mới kết thúc `_test`, tmpfs, project Compose riêng và storage dưới thư mục tạm.
- Không kết nối, migrate, seed, ghi hoặc xóa dữ liệu trong `petcare_shop_dev` hay production.
- Không gọi AI/AI Vision thật, SMTP, S3 hoặc payment gateway; Vision browser coverage dùng mock loopback.
- QA artifacts không nằm trong repository. Không đưa chúng vào staging.

## Commit, push và hosted GitHub Actions

Mục này được cập nhật sau khi commit/push để ghi lại revision và kết quả thật từ GitHub Actions; không suy diễn hosted CI từ kết quả local.

| Hạng mục | Kết quả |
|---|---|
| Commit(s) | Pending push verification |
| Final local/remote HEAD | Pending push verification |
| Push branch | Pending push verification |
| GitHub Actions run URL | Pending hosted run |
| Python 3.11 / 3.12 / 3.13 | Pending hosted run |
| Source security / container / browser smoke | Pending hosted run |
| Final working tree and upstream | Pending push verification |

## Còn lại trước khi production

- Hoàn tất hosted CI cho revision được push; không xem local tests là thay thế.
- Nghiệm thu thủ công Phase 6.1, nhất là keyboard/screen reader, zoom 200%, browser ngoài Chromium và hành trình qua các vai trò.
- Provider thật, SMTP, S3, payment gateway, worker daemon, hiệu năng/tải và quyền dữ liệu bên ngoài chưa được kiểm chứng.
- Không thay schema development trước backup/restore evidence và phê duyệt riêng; trạng thái readiness development lịch sử là 503.

**Kết luận:** baseline local đã được kiểm tra bằng full Python/JavaScript/Playwright và các gate liệt kê ở trên. Chưa xác nhận hosted CI hoặc production readiness cho đến khi mục commit/push/Actions được điền bằng kết quả thực.
