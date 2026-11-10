# Phase 3.5 — Release Baseline và Stabilization

Ngày: 2026-11-09. Phạm vi: ổn định cổng kiểm thử, browser refund coverage, CI wiring và migration preflight. Đây không phải xác nhận production readiness.

## Repository safety

- Repo: `petcare-manager`, branch `solo/khang-petcare`, HEAD tại đầu lượt `8634300f4b5ad4700d6702a048220d6597c4e200`.
- Trước khi sửa đã tồn tại nhiều tracked edits và untracked files từ phase trước; không stage, revert hay commit các thay đổi đó. Giữ nguyên trạng thái dirty.
- Durable Phase 3 checkpoint và Phase 3.5 pre-edit checkpoint được xác minh SHA-256 thành công tại `/Users/heisenbon/Documents/Codex/petcare-phase3-checkpoint-20261109` và `/Users/heisenbon/Documents/Codex/petcare-phase35-checkpoint-20261109`. Checkpoint 3.5 gồm HEAD, status, tracked/index diffs, danh sách và tar untracked tree.
- Artifact/DB testing chỉ dùng MySQL test container tại port 3307, schema `_test` và storage dưới temp directory. Dev MySQL port 3306 được đọc-only.

## Kết quả trước và sau Phase 3.5

| Gate | Baseline trước | Sau Phase 3.5 |
|---|---:|---:|
| Python unit/web/MySQL | 369/369 PASS | 369/369 PASS, 0 skip, 33.513 s |
| JavaScript | 28/28 PASS | 28/28 PASS |
| Playwright real browser | Refund chưa submit; CI chưa có job | 3/3 PASS, 7.844 s trên Flask/MySQL QA |
| Bandit exact CI command | PASS ở Phase 3 | PASS, exit 0; browser harness không còn finding mới |
| Dependency audit | Runtime lock PASS | Runtime + browser locks PASS; không known advisories |
| Compile / `pip check` / Compose config | PASS | PASS |
| Health/readiness | QA readiness PASS; dev 503 | QA `/healthz=200`, `/readyz=200`; dev `/readyz=503` |
| Hosted CI / Trivy | NOT TESTED | NOT TESTED trong lượt này |

Browser smoke mới nằm ngoài tổng số 369 Python product tests và có 3 test riêng. Không có số branch-coverage hoặc performance benchmark.

## Code và hành vi được ổn định

- Thêm `requirements-browser.lock` exact pin để Playwright không vào runtime dependency set.
- Nối `browser-smoke` job vào `.github/workflows/ci.yml`, với MySQL 8.4 isolated, `_test` schema guard, readiness check, local integrations disabled, trace/screenshot/log/result upload (7 ngày).
- Cài bộ runtime + browser lock vào clean Python 3.13 venv; `pip check` và Playwright version check PASS.
- Thêm browser smoke cho route navigation, role restriction, POS mobile/keyboard/a11y basics và refund lifecycle. Refund dialog native được accept/dismiss qua Playwright; trạng thái UI khớp refund DB ledger và tồn kho.
- Gia cố teardown để dọn fixture ngay cả khi setup lỗi giữa chừng; cleanup dùng câu SQL cố định với bind params thay dynamic placeholder strings.
- Narrow B404/B603 suppressions chỉ cho subprocess giám sát tiến trình Flask từ fixed interpreter/entrypoint, không shell và không request input. CI Bandit gate exact command pass.
- Không thay đổi business behavior, HTTP API hoặc database schema trong Phase 3.5.

## Database decision

`petcare_shop_dev` giữ nguyên. Read-only preflight thấy 20 bảng/184 cột, marker UTC duy nhất, thiếu 6 bảng, 4 cột, 4 index và 18 FK theo current contract. Ba named money checks còn dùng legacy `_vnd`; kiểm tra violations của current Decimal rules bằng 0. `/readyz=503`. Không có backup dev mới/restorable được xác minh trong repo/task evidence; go/no-go là **NO-GO**. Kế hoạch và điều kiện cấp quyền nằm trong [DB_DEV_MIGRATION_APPROVAL.md](DB_DEV_MIGRATION_APPROVAL.md).

## Remaining release risks

- GitHub Actions hosted workflow và Trivy chưa được chạy; local YAML parse không chứng minh remote job pass.
- Accessibility smoke còn hạn chế; keyboard toàn site, screen reader, contrast và zoom chưa audit.
- SMTP, remote AI/AI Vision, S3, worker daemon/heartbeat, production container runtime, load/performance và production backup/restore chưa xác minh.
- Dev readiness còn fail và cần restore-tested backup + explicit user authorization trước DDL.

Phase 4 handoff để bắt đầu **product modernization** trên test/QA environment có ở [PHASE4_HANDOFF.md](PHASE4_HANDOFF.md). Không xem baseline này là production sign-off.
