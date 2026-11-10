# Sprint 4.3 — Visual và browser QA

## An toàn và môi trường

Runner scripts/browser_smoke/run_smoke.py khởi động run.py thật, chờ /readyz=200 và bắt buộc DB_NAME == PETCARE_TEST_DB_NAME với schema kết thúc bằng _test. Sprint dùng petcare_phase3_browser_test, Chromium, local media/export storage tại /tmp/petcare-phase43-test-storage. Fixtures được tạo và cleanup trong schema QA; không sửa petcare_shop_dev hoặc production.

Working tree đã có thay đổi trước sprint. Checkpoint xác minh trước khi tiếp tục: /Users/heisenbon/Documents/Codex/petcare-phase43-checkpoint-20261110. Không stage, commit, reset, clean hoặc stash. Before/after screenshots nằm trong docs/assets/phase43/{before,after}. Browser traces/logs/results nằm owner-only bên ngoài repo tại /Users/heisenbon/Documents/Codex/petcare-phase43-visual-qa-20261110/after-browser; không chép cookie, headers, passphrase hoặc credentials vào hồ sơ.

## Responsive evidence

Purchasing list/detail, reports và tenant export pending/ready được mở ở 320, 390, 768, 820, 1024, 1440 px; mỗi page assert documentElement.scrollWidth == viewport. Purchase/report kiểm đúng card/table breakpoint; export kiểm pending indicator/ready download. Before: [responsive observations](assets/phase43/before/responsive-observations.json).

| Màn | Trước | Sau |
|---|---|---|
| Purchase list 320 | [before](assets/phase43/before/purchasing-list-320.png) | [after](assets/phase43/after/purchasing-list-320.png) |
| PO detail 320 | [before](assets/phase43/before/purchasing-detail-320.png) | [ordered](assets/phase43/after/purchasing-detail-ordered-320.png), [received](assets/phase43/after/purchasing-detail-received-320.png) |
| Reports 320 | [before](assets/phase43/before/reports-320.png) | [after](assets/phase43/after/reports-320.png) |
| Export 320 | Chưa có baseline | [pending](assets/phase43/after/operations-export-pending-320.png), [ready](assets/phase43/after/operations-export-ready-320.png) |

## Workflow và accessibility

Final browser suite: 10/10 pass, 0 skip. PO create/partial/full/cancel, report filter/XLSX, authenticated export + actual worker/download và POS injected 503/retry đều chạy. Expected injected 503 và browser download net::ERR_ABORTED được chấp nhận chỉ sau khi assertion status/download tương ứng pass; lỗi khác fail diagnostics.

Final diagnostics có đúng một HTTP/console error: staff bị từ chối GET /users/ (403) như role test dự kiến. Không có failed request bất ngờ hoặc page exception trong browser assertions; runtime log có 0 traceback và 0 HTTP 5xx.

Axe-core 4.14.0 local, selected states: 26 scans, 0 violations sau sửa contrast 4.16:1, missing action heading và named table region. Có 39 incomplete node instances lặp qua screen states: 36 color-contrast và 3 label-content-name-mismatch; không phải violation. Color-contrast incomplete chủ yếu là background bị che một phần bởi fixed navigation hoặc icon/SVG/non-text glyph. Review DOM/CSS thấy nav/chart supporting text dùng #58665e (6.04:1 trên trắng); decorative icons có aria-hidden; .remove-line dùng aria-label “Xóa dòng mặt hàng” còn ký hiệu × là visible control glyph. Đây là review code/CSS, không thay thế screen-reader test. Kết quả aria-prohibited-attr của table-scroll được sửa bằng role=region; browser assertion xác nhận accessible name giữ “Danh sách đơn nhập” và thêm keyboard hint.

Các incomplete màu/nội dung glyph vẫn cần AT/device review; chúng chưa được tính là violation hoặc pass conformance. Keyboard smoke gồm Tab và Enter cho fill-remaining. Không xác minh screen reader, toàn site WCAG, browser chrome zoom 200%, Safari/Firefox/device thật, hosted Actions, SMTP/AI/Vision/S3, load test hoặc production DB.

docker compose config --quiet chỉ kiểm syntax Compose; không chứng minh Docker image build/runtime.
