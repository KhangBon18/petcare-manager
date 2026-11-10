# Phase 4.2 — Visual và accessibility QA

Ngày: 2026-11-10. Chromium chạy ứng dụng Flask thật, dùng tài khoản QA và MySQL schema disposable `petcare_phase3_browser_test`; seed/test fixture chỉ nằm ở schema kết thúc `_test`. Ảnh chụp dùng fixture tổng hợp. Không có credentials, session cookies, traces hoặc request bodies trong repository.

## Viewport và screenshots

Trước khi sửa, ghi nhận product list và POS tại đủ sáu chiều rộng 320, 390, 768, 820, 1024 và 1440px. Sau sửa, cùng sáu chiều rộng được mở cho product list và POS; customer detail với 13 purchased pets cũng được mở tại đủ sáu chiều rộng. Script assert `document.documentElement.scrollWidth == viewport width` cho các route tương ứng.

| Width | Products before | Products after | POS before | POS after | Customer detail after |
|---:|---|---|---|---|---|
| 320 | [before](assets/phase42/before/products-list-320.png) | [after](assets/phase42/after/products-list-after-320.png) | [before](assets/phase42/before/pos-320.png) | [after](assets/phase42/after/pos-after-320.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-320.png) |
| 390 | [before](assets/phase42/before/products-list-390.png) | [after](assets/phase42/after/products-list-after-390.png) | [before](assets/phase42/before/pos-390.png) | [after](assets/phase42/after/pos-after-390.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-390.png) |
| 768 | [before](assets/phase42/before/products-list-768.png) | [after](assets/phase42/after/products-list-after-768.png) | [before](assets/phase42/before/pos-768.png) | [after](assets/phase42/after/pos-after-768.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-768.png) |
| 820 | [before](assets/phase42/before/products-list-820.png) | [after](assets/phase42/after/products-list-after-820.png) | [before](assets/phase42/before/pos-820.png) | [after](assets/phase42/after/pos-after-820.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-820.png) |
| 1024 | [before](assets/phase42/before/products-list-1024.png) | [after](assets/phase42/after/products-list-after-1024.png) | [before](assets/phase42/before/pos-1024.png) | [after](assets/phase42/after/pos-after-1024.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-1024.png) |
| 1440 | [before](assets/phase42/before/products-list-1440.png) | [after](assets/phase42/after/products-list-after-1440.png) | [before](assets/phase42/before/pos-1440.png) | [after](assets/phase42/after/pos-after-1440.png) | [13 pets](assets/phase42/after/customer-detail-purchased-pet-1440.png) |

Browser cũng chụp product detail 320px, create/edit/inventory history 1440px, customer pet page 2 ở 320px và effective-width 720px cho product/POS/customer. 720px mô phỏng viewport CSS hữu dụng ở desktop 1440px khi browser zoom 200%; test không bật zoom qua browser chrome.

## Quan sát accessibility

- axe-core 4.14.0 được nạp cục bộ từ QA tooling qua route cùng origin, không đưa dependency vào runtime và không sửa CSP.
- 13 scans bao phủ customer pet pages 1–2 desktop/mobile, product list/create/detail/inventory form, POS empty/cart và invalid product stock. Kết quả cuối: **0 axe violations**, trong đó 0 critical/serious.
- Một lượt quét sớm bắt đầu trong lúc POS cards đang ở entrance fade và báo blended contrast; lần cuối đợi animation ngắn nhất 0,7 giây trước khi scan và ghi 0 violations. Không đổi muted POS text colors dựa trên frame chuyển động.
- `incomplete` còn lại (13 node results) cần review thủ công: bottom navigation có thể che nội dung khi axe xét document dài; pseudo/icon-only arrow, remove-line `×` và mũi tên trong button không phải nội dung text đủ để scanner tự phán; một color contrast context chưa giải được tự động. Đây không được tính là pass tự động.
- Keyboard test: product selection bằng Enter chuyển focus tới quantity; customer pet pagination có visible `:focus-visible`/outline; stock adjustment form qua Tab tới reason field. Native quantity/initial stock limits và server error focus được quan sát.
- Chưa dùng screen reader, Safari/Firefox hoặc thiết bị cảm ứng thật. Contrast review chỉ trên các screen axe scan; không phải WCAG certification.

## Browser diagnostics và artefact

- Playwright suite: 6/6 PASS; 0 skip. 6 test cases bao gồm 13-pet customer flow, product/stock/POS checkout, deactivate/reactivate, module nav, refund regression và staff authorization.
- Tất cả six diagnostics records: 0 JS/page exceptions và 0 failed requests. Có một expected `GET /users/` 403 và một console message tương ứng khi xác nhận staff bị chặn.
- File evidence: [browser result](assets/phase42/after/results.json), [axe scans](assets/phase42/after/axe-results.json), [network/console summary](assets/phase42/after/browser-diagnostics.json).
- Các ảnh baseline và after đặt tại `docs/assets/phase42/before/` và `docs/assets/phase42/after/`; browser traces và runtime logs không được đưa vào repo.
