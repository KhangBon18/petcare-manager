# Sprint 4.3 — Báo cáo Purchasing, Reports và Operations

Ngày 2026-11-10. Phạm vi: làm gọn workflow đơn nhập, báo cáo, tenant export và khôi phục lỗi lookup POS đã quan sát. Giữ Flask/Jinja/MySQL, vanilla JS, business rules, schema và HTTP/API contracts. Không phải xác nhận production readiness.

## Tóm tắt

- Đơn nhập có card responsive, hiển thị ordered/received/remaining; trang detail có đủ số liệu dòng hàng và thao tác điền số còn thiếu trước khi người dùng xác nhận.
- Báo cáo có product cards trên mobile với số lượng/doanh thu thực; quick period đang chọn có style và aria-current.
- Tenant export trình bày metadata và hướng dẫn theo một số mã lỗi hiện hành; browser đã chạy pending → worker thật → ready/download trên QA.
- POS catalog 503 có nút retry, giữ cart.
- Axe phát hiện contrast thấp và table header trống; cả hai đã sửa, scan sau sửa không có violation.
- Không sửa service nghiệp vụ, route/API, tiền, migration hoặc schema; không dùng petcare_shop_dev/production.

## Findings

| ID / mức / trạng thái | Evidence và reproduction | Root cause, fix và verify | Regression risk |
|---|---|---|---|
| UX43-01 / P2 / FIXED | Mở /purchasing/?status=ordered ở 320 px. Trước: document tràn ngang; [before](assets/phase43/before/purchasing-list-320.png). Sau: card có supplier, received/ordered, remaining, count, value, detail link; 6 viewport không overflow. | Bảng nhiều cột/action có min-content rộng. Sửa purchasing index/CSS; browser MySQL test đo 320/390/768/820/1024/1440. | Thấp-vừa, template/CSS. |
| UX43-02 / P2 / FIXED | PO detail mobile trước không cho xem đầy đủ line-item fields như desktop. | Chỉ có table layout. Thêm line cards: ordered, received, remaining, current stock, unit cost, total. Browser create/partial/full/cancel đối chiếu state, stock, movements trên MySQL QA. | Thấp-vừa, view-only. |
| UX43-03 / P2 / IMPROVED | Reports products trên viewport hẹp thiếu khả năng quét quantity/revenue cùng tên sản phẩm. | Chỉ render bảng đa cột. Thêm card dùng cùng server result; browser đối chiếu service figures, custom date range và XLSX. | Thấp, read-only. |
| UX43-04 / P2 / IMPROVED | Trang export có hướng dẫn riêng cho requester_access_revoked, passphrase_unavailable, export_job_expired. | Trạng thái chỉ có nội dung lỗi chung. Cập nhật Jinja metadata/error copy. Browser chạy pending/ready/worker/download; error-code copy chưa chạy browser E2E trong sprint. | Thấp, template. |
| UX43-05 / P2 / FIXED | Inject lookup HTTP 503 trong POS; trước đó không có nút phục hồi. Sau: retry GET thành công, cart giữ nguyên. | Thiếu retry control/handler. Sửa invoice form/pos.js; browser + JS regression. | Thấp-vừa, UI-only. |
| A11Y43-01 / P2 / FIXED | Axe ghi contrast 4.16:1 của .purchase-summary-progress > small (yêu cầu 4.5:1) và empty action-column header. | Đổi màu #708078 thành #56675e, đặt heading THAO TÁC. Axe 4.14.0 scan sau sửa không còn violation. | Thấp. |
| A11Y43-02 / P2 / FIXED | Axe incomplete đánh dấu vùng div cuộn có aria-label nhưng chưa có role phù hợp để expose named region. | Đặt role=region trên keyboard-scroll wrapper và thêm browser assertion cho accessible region name. Retest bằng Playwright/axe. | Thấp; semantics-only. |
| A11Y43-03 / P2 / FIXED | Shared table-scroll helper thay accessible name cụ thể “Danh sách đơn nhập” bằng hướng dẫn cuộn chung khi bảng overflow. | `app.js` nay giữ context label sẵn có và ghép hướng dẫn keyboard; browser kiểm tên region. Contrast #56675e trên trắng được tính lại là 6.00:1. | Thấp; chỉ accessible naming. |
| QA43-01 / P2 / FIXED | Bandit CI gate fail sau thêm browser test do passphrase QA tĩnh, subprocess call chưa giải thích, cleanup nuốt mọi exception. | Random passphrase theo fixture; suppression B603 chỉ tại module subprocess cố định, shell=False; cleanup dùng local QA storage đúng adapter và không nuốt lỗi. Exact Bandit CI gate exit 0. | Thấp, test-only. |

Không xác nhận P0/P1 trong sprint. Severity P2 ở đây mô tả usability/quality, không phải lỗi dữ liệu nghiệp vụ.

## Hành vi được bảo toàn

- Create PO không tăng stock. Receive vẫn qua route/service/repository hiện hành; “Điền số còn thiếu” chỉ thay input và không submit. Server tiếp tục xác thực state/quantity/permission/transaction.
- Report card, table, custom dates và XLSX lấy cùng report service/snapshot; không đổi endpoint.
- Tenant export polling/status/download/worker và requester/tenant checks không đổi; UI metadata không đổi JSON.
- POS retry chỉ gọi lại lookup GET; không đổi invoice/payment/stock.
- Không thêm framework hoặc runtime dependency.

## Files của sprint

App: petcare/templates/purchasing/index.html, petcare/templates/purchasing/detail.html, petcare/templates/reports/index.html, petcare/templates/users/export_job.html, petcare/templates/invoices/form.html, petcare/static/css/app.css, petcare/static/js/app.js, petcare/static/js/purchasing.js, petcare/static/js/pos.js, petcare/i18n.py.

QA: scripts/browser_smoke/test_browser_smoke.py, tests/js/pos.test.cjs, tests/js/purchasing.test.cjs.

Docs: PHASE43_IMPLEMENTATION_REPORT.md, PHASE43_PURCHASING_UX.md, PHASE43_REPORTS_UX.md, PHASE43_OPERATIONS_UX.md, PHASE43_VISUAL_QA.md, PHASE5_AI_HANDOFF.md, MASTER_UPGRADE_ROADMAP.md, MODULE_COMPLETENESS_MATRIX.md, TEST_MATRIX.md.

## Regression results

| Gate | Baseline | Sau sprint |
|---|---:|---:|
| Python unit/web/MySQL | 372/372 | 372/372 PASS, 0 skipped |
| JavaScript | 28/28 | 30/30 PASS |
| Playwright Chromium | 6/6 | 10/10 PASS, 0 skipped |
| Axe | 13 scans | 26 scans, 0 violations; incomplete còn manual review |
| Bandit exact CI gate | Pass baseline | PASS, exit 0 |
| pip-audit runtime/browser | Pass baseline | PASS, không có known vulnerabilities ở thời điểm chạy |
| pip check, compileall, Compose config, git diff check | Pass baseline | PASS |
| QA readiness | 200 | 200 trong runner trên schema _test |
| Dev/production DB | Dev baseline 503 | NOT MODIFIED; không probe schema lại trong sprint |

Browser suite khởi động Flask thật, dùng petcare_phase3_browser_test và isolated storage. Lượt đầu với scanner tìm ra accessibility findings; sau fix full suite pass. Một lượt tiếp theo phát hiện test teardown truyền sai dạng config; sửa rồi test riêng 1/1 và full suite 10/10 đều pass. Browser artifacts: [visual QA](PHASE43_VISUAL_QA.md). Hợp đồng hiện hành: [API_CONTRACT.md](API_CONTRACT.md).

Bandit exact command theo .github/workflows/ci.yml: bandit -q -r petcare scripts main.py run.py wsgi.py -x petcare/templates,petcare/static -b .security/bandit-baseline.json. B608 nosec warnings hiện hữu tiếp tục hiện nhưng không làm gate fail.

## Giới hạn và thứ tự tiếp theo

1. Review axe incomplete, keyboard-only toàn luồng, screen reader và browser zoom 200%; không xem axe là chứng nhận WCAG.
2. Thử browser error state của export; route/permission matrix rộng hơn.
3. Quan sát GitHub Actions hosted; local gate không chứng minh workflow hosted đã chạy.
4. Không gọi SMTP, real AI/Vision, S3; Phase 5 dùng staging/dữ liệu synthetic sau khi duyệt. Xem [AI handoff](PHASE5_AI_HANDOFF.md).
5. Không sửa dev schema; yêu cầu backup/restore và approval riêng trước bất kỳ DDL nào.
