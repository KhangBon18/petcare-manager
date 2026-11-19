# Phase 4.2 — Báo cáo triển khai

Ngày: 2026-11-10. Phạm vi là sản phẩm, tồn kho, POS và một lát cắt nhỏ để hoàn tất các quality gap customer/pet của Phase 4.1. Đây không phải tuyên bố sẵn sàng production.

## Tóm tắt điều hành

- Giữ Flask/Jinja/MySQL, vanilla JS, routes, RBAC, CSRF, giá/tiền, tồn kho, trạng thái hóa đơn và transaction boundaries hiện có.
- Sửa cách hiển thị danh sách sản phẩm ở màn hình ≤680px: bảng nhiều cột chuyển thành card có nhãn từng dữ liệu; phần bảng desktop và dữ liệu truy vấn không đổi.
- Bổ sung phân trang riêng cho thú cưng đã mua trên customer detail (12 hồ sơ/trang). Khách có hơn 12 record giờ có đường đi đến record tiếp theo; phân trang hóa đơn không bị ảnh hưởng.
- Xác nhận luồng chỉnh tồn kho, POS, thanh toán và invoice persistence trên MySQL QA bằng dữ liệu tổng hợp. POS đã có sticky cart summary ở mobile nên được giữ lại; không thêm drawer trùng lặp.
- Sửa nhãn accessible không khớp text hiển thị và hai màu chữ có tương phản dưới 4,5:1.
- Không phát hiện hoặc sửa lỗi tài chính/kế toán/tồn kho phía business logic. Không thay schema hoặc dữ liệu dev/prod.

## Phát hiện và kết quả

| ID / Severity | Reproduction; observed → expected | Root cause | Affected files / fix | Evidence / verification / regression risk |
|---|---|---|---|---|
| UX42-01 · P2 · FIXED | Mở `/products/` ở 320px; bảng 5–6 cột cắt tồn kho/trạng thái/hành động → trên màn hẹp mỗi field cần thấy được mà không kéo cả bảng. | Product table chỉ có desktop layout; wrapper cho phép cuộn ngang nhưng không đưa các field quan trọng vào một màn hình nhỏ. | `petcare/templates/products/index.html`, `petcare/static/css/app.css`; CSS breakpoint ≤680px chuyển rows thành card có nhãn, giữ table semantics. | Chromium browser test 320/390px xác nhận field/action hiển thị; ở 320/390/768/820/1024/1440 `documentElement.scrollWidth == viewport`. Rủi ro thấp-vừa, CSS/template; kiểm regression bằng screenshots và count/search assertions. |
| UX42-02 · P2 · FIXED | Tạo customer có 13 thú cưng đã mua; detail chỉ hiện 12 và không báo/có cách tới record cuối → người dùng cần biết tổng và mở tất cả record theo trang. | Read service trả danh sách bounded 12 nhưng không có count hoặc phân trang pet độc lập. | `customer_repo.py`, `customer_service.py`, `customer_routes.py`, `customers/detail.html`; tenant-scoped COUNT, `LIMIT/OFFSET`, query `pet_page`, 12/page. | Flask/MySQL/Chromium fixture có 13 pet: page 1 có 12, page 2 mở pet #13; invoice `page` được giữ; sáu widths không overflow. Rủi ro thấp-vừa, query/template; xác minh page state độc lập và tenant scope. |
| A11Y42-01 · P2 · FIXED | Quét axe POS/Product/customer detail: `#378b74` với chữ trắng 4,11:1, link hóa đơn `#4d876f` 4,19:1 → chữ thường cần ≥4,5:1; accessible name cần giữ visible name. | Màu component cũ chưa đạt contrast; `aria-label` custom trên account/assistant không chứa đúng text hiển thị. | `petcare/static/css/app.css`, `petcare/templates/base.html`; chuyển hai màu sang `#287a62`, bỏ mismatch, đánh dấu avatar trang trí `aria-hidden`. | Tính từ luminance: màu mới 5,18:1 trên trắng; axe-core 4.14.0 quét 13 trạng thái, 0 violations. Rủi ro thấp, CSS/template; cần tiếp tục review các axe `incomplete` thủ công. |

Không có P0/P1 được xác nhận. Không thêm feature ngoài phạm vi, không đổi contract tài chính. Rủi ro còn lại là kiểm tra thủ công screen reader/contrast cho các kết quả axe `incomplete` và kiểm tra device/browser ngoài Chromium.

## Thay đổi trong sprint này

### Ứng dụng và kiểm thử

- `petcare/templates/products/index.html`, `petcare/static/css/app.css`: thêm data labels và mobile product cards; cải thiện contrast của nút trợ lý/link hóa đơn.
- `petcare/repositories/customer_repo.py`, `petcare/services/customer_service.py`, `petcare/routes/customer_routes.py`, `petcare/templates/customers/detail.html`: query và điều hướng `pet_page` độc lập với trang hóa đơn.
- `petcare/templates/base.html`: accessible names khớp text hiển thị; avatar tên user không đọc lặp.
- `scripts/browser_smoke/test_browser_smoke.py`: chạy MySQL-backed Product → stock → POS → paid invoice flow, staff customer activate/deactivate, dữ liệu 13 pets, keyboard selection/focus, responsive dimensions, diagnostics và axe scan.
- `tests/unit/test_customer_profile_service.py`, `tests/web/test_customer_profile.py`: pagination/tenant/page-state regressions.

Working tree có nhiều thay đổi pre-existing trước Phase 4.2. Không có thao tác stage/commit/reset/clean. Checkpoint đã tạo ở `/Users/heisenbon/Documents/Codex/petcare-phase42-checkpoint-20261110`; chi tiết ở README/checksums/patch trong thư mục đó.

### Dữ liệu và an toàn

- Browser/MySQL integration chỉ dùng schema `petcare_phase3_browser_test` có hậu tố `_test` và storage QA riêng. Runner kiểm tra `DB_NAME == PETCARE_TEST_DB_NAME`, khởi động app local và đợi `/readyz=200`.
- Không gọi initializer/seed/migration trên `petcare_shop_dev` hay production. Trạng thái dev `/readyz=503` không đổi và tiếp tục là việc cần xử lý riêng qua backup/approval gate.
- Fixture synthetic được cleanup; không copy credential, browser trace/cookie hay runtime log vào repository.

## Test evidence trước và sau

| Suite / gate | Baseline trước sprint | Kết quả Phase 4.2 | Bằng chứng |
|---|---:|---:|---|
| Python unit + web + MySQL integration | 371/371 | **372/372 PASS, 0 skip** | `.venv/bin/python -m unittest discover -s tests -v`, `petcare_phase3_browser_test`, 30,685 s. |
| JavaScript | 28/28 | **28/28 PASS, 0 skip** | `node --test tests/js/*.test.cjs`, 80 ms. |
| Playwright Chromium | 4/4 | **6/6 PASS, 0 skip** | `scripts/browser_smoke/run_smoke.py`, 35,706 s. Report ở [results.json](assets/phase42/after/results.json), scans ở [axe-results.json](assets/phase42/after/axe-results.json), request summary ở [browser-diagnostics.json](assets/phase42/after/browser-diagnostics.json). |
| Axe accessibility | Chưa chạy | **13 scans, 0 violations** | axe-core 4.14.0 được nạp cục bộ qua cùng origin; không nới CSP. 13 mục `incomplete` còn cần review thủ công, chi tiết trong visual QA. |
| Bandit CI gate | Pass theo baseline trước sprint | **PASS, exit 0** | Đúng lệnh `source-security` trong `.github/workflows/ci.yml`, dùng `.security/bandit-baseline.json`; Bandit có log B608 `nosec encountered`, gate không có finding mới vượt baseline. |
| Dependency advisories | Pass baseline | **PASS** | `pip-audit -r requirements.lock` và `pip-audit -r requirements-browser.lock`: không có vulnerability đã biết tại lần quét. |
| Package / syntax / Compose / diff | Pass baseline | **PASS** | `pip check`, `compileall`, `docker compose config --quiet`, `git diff --check`. |
| QA readiness | 200 | **200 trong smoke startup** | Runner chỉ tiếp tục sau khi Flask thật trả `/readyz=200` trên schema QA. `/healthz` cũng được kiểm qua integration/preflight suite. |
| Development readiness | 503 | **503, NOT CHANGED** | Không mở dev DB trong Phase 4.2; trạng thái và remediation nằm ở tài liệu DB hiện hành. |
| Hosted CI / container image / external services | Chưa xác minh | **NOT TESTED** | Không có GitHub Actions hosted run, production DB, browser khác Chromium, SMTP thật, AI/Vision provider thật hoặc S3 trong sprint này. |

Browser mở product list, POS và customer detail tại 320, 390, 768, 820, 1024, 1440px; product detail tại 320px; product create/edit và stock adjustment history tại 1440px. Product/POS/customer detail ở các kích thước đã assert không tràn viewport. Kiểm tra “200%” dùng effective viewport 720px như phép mô phỏng reflow, không điều khiển browser chrome zoom. Browser ghi 0 page exception và 0 failed request; một `GET /users/` 403 của staff được xác nhận là expected permission denial.

## Tiếp theo

Ưu tiên Sprint 4.3 theo [PHASE42_NEXT_SPRINT.md](PHASE42_NEXT_SPRINT.md). Giữ dev DB migration ngoài phạm vi cho tới khi hoàn tất backup/restore evidence và quy trình phê duyệt riêng.
