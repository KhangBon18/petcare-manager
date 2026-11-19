# Phase 6.2 — triển khai và nghiệm thu cuối

Ngày kiểm tra: 2026-11-11. Branch giữ nguyên: `solo/khang-petcare`. Mục tiêu là làm demo học thuật lặp lại được, thu hẹp rủi ro tài khoản demo, và hoàn tất kiểm tra đa trình duyệt. Không có commit/push.

## Kết quả

- **Tài khoản demo:** `petcare/database/seed.py` chỉ cấp tài khoản seed trong `APP_ENV=test` + `PETCARE_DEMO_MODE=1`, yêu cầu mật khẩu khác nhau do môi trường cung cấp và tối thiểu 16 ký tự; không còn mật khẩu mặc định trong source. Bổ sung 7 regression tests trong `tests/unit/test_demo_seed.py`.
- **Cách khởi chạy an toàn:** thêm `scripts/demo/classroom.sh --target qa`. Script từ chối biến cấu hình DB được thừa kế, dùng Compose project/ngẫu nhiên, database `_test` trong tmpfs, storage tạm có marker, port loopback, local worker và Vision mock. Chỉ reset đúng project mà launcher vừa tạo; exit sẽ cleanup.
- **Rehearsal đầu-cuối:** `scripts/demo/classroom_rehearsal.py` chạy **PASS**, 14 bước trên Flask UI + MySQL QA: tạo customer/pet/product/supplier/PO, nhận 3+5, POS product+pet, pay, refund 1 product unit, report, worker export/download, assistant, Vision mock và staff permission boundary. Đo **17.76 giây** automation từ đầu workflow đến DB reconciliation (không tính startup/reset); không gồm lời thuyết trình.
- **Reconciliation:** QA rows khớp customer 13, pet 75, product 23, supplier 1, PO 1, invoice 8; PO `received`, 2 receipt movements, stock cuối 7; invoice 2.650.000 VND, refund 75.000 VND, net 2.575.000 VND; pet buyer cùng customer.
- **Browser diagnostics:** 0 page errors, 0 failed requests ngoài expected download event, 0 unexpected HTTP errors và 0 console errors. Export artifact download được; tên file `.pcarexport`.
- **QA health/schema:** `/healthz=200`, `/readyz=200`, `/workersz=200`; schema MySQL isolated có 26 bảng và 4 migration markers, DB hậu tố `_test`, port chỉ bind loopback.
- **Đa trình duyệt:** sửa runner để lưu screenshot theo đúng viewport thay vì full-page capture; giữ CSP nghiêm.
- **A11y regression:** đóng nút assistant có accessible name, insight grouping có role rõ ràng; WebKit tránh GSAP ghi inline style dưới CSP chặt. Có thêm kiểm thử JS.

## Bằng chứng kiểm tra

- Python/MySQL suite trên schema QA disposable mới: **428/428 PASS, 0 skipped**. Bao gồm các module unit/web/integration và 5 purchase-order MySQL lifecycle tests.
- JavaScript: **41/41 PASS** với `node --test tests/js/*.test.cjs`.
- Full Chromium browser/vision suite: **18/18 PASS** trong 61.857 giây trên schema MySQL disposable riêng, gồm browser refund, PO, export worker, assistant, Vision provider states và accessibility axe flow.
- Chromium/Firefox/WebKit representative UI: **3/3 engines PASS**; 22 axe scans ở Chromium/Firefox, 0 violations. WebKit được kiểm cấu trúc, labels và responsive flow; axe instrumentation bỏ qua WebKit để CSP measurement không bị nhiễu.
- **Final quality gates:** Bandit exact CI command exit 0; emitted existing “nosec encountered (B608)” notices but no failed gate. `pip-audit` runtime/browser locks: no known vulnerabilities; `npm audit`: 0 vulnerabilities; `pip check`: clean; compileall/py_compile, Compose config, Docker image build và `git diff --check`: PASS.
- **Hosted CI:** không chạy trong phase này; Phase 6.0 hosted result 6/6 là baseline cũ, không đại diện checkout hiện tại.
- `/healthz`, `/readyz`, `/workersz` trả 200 trên classroom QA trước reset/rehearsal; production và `petcare_shop_dev` không được dùng.
- **Không kết luận production-ready hoặc WCAG conformant.** Zoom trình duyệt 200% và screen reader chưa được xác minh an toàn trong native browser profile.

## Git / release

Branch vẫn là `solo/khang-petcare`; không stage, commit hoặc push tự động. Có pre-existing Phase 6.1 edits/untracked files trong working tree, được giữ nguyên; xem [git change inventory](GIT_CHANGE_INVENTORY.md) nếu cần đối chiếu. Trước commit, review và stage theo nhóm: demo/security, UI/accessibility, tests, docs và screenshots.
