# Phase 6.2 — handoff trình diễn học thuật

## Quick start

Dùng Docker Engine/Compose, Python 3.11+ (Python 3.13 đã được xác minh), và checkout repo hiện tại. Tạo venv ngoài repository, cài lockfiles, rồi chạy duy nhất lệnh QA launcher:

```sh
python3 -m venv /tmp/petcare-demo-venv
. /tmp/petcare-demo-venv/bin/activate
python -m pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock
scripts/demo/classroom.sh --target qa
```

Nhập hai mật khẩu mới, khác nhau, tối thiểu 16 ký tự tại prompt ẩn. Không dùng password mặc định, không ghi chúng vào report hoặc shell history. Launcher khởi tạo MySQL `_test` trong tmpfs, synthetic seed, local Vision mock, Flask, mail/export workers và private temp storage. URL chỉ bind loopback. Cần thấy `/readyz=200` và `/workersz=200`.

- `admin`: account được seed với tenant membership `owner`; app ánh xạ membership này sang quyền admin trên cửa hàng.
- `staff1`: membership `staff`, customer access; `/users/` bị chặn bằng 403.
- Roles membership được schema hỗ trợ: `owner`, `admin`, `staff`; launcher seed một owner và một staff.
- Nhập `r` ở prompt để reset đúng QA project; `q` hoặc Ctrl-C để cleanup. Không đụng DB ngoài project này.

Không chạy migration/seed lên `petcare_shop_dev` hoặc production. Không cấu hình provider AI, SMTP, S3 hay payment.

## Demo flow

Dùng [Academic demo script](ACADEMIC_DEMO_SCRIPT.md) cho trình tự 8–12 phút, bản rút gọn, expected results và fallback. Connected rehearsal script `python -m scripts.demo.classroom_rehearsal` kiểm luồng bằng UI và MySQL QA; kết quả/thời gian được ghi ở [Phase 6.2 report](PHASE62_IMPLEMENTATION_REPORT.md).

## Browser QA handoff

- Local UI: URL được in bởi launcher.
- Primary routes: `/dashboard`, `/customers/`, `/pets/`, `/pets/find-similar`, `/products/`, `/invoices/new`, `/purchasing/`, `/reports/`, `/users/export`, `/assistant/chat`, `/healthz`, `/readyz`, `/workersz`.
- Contracts giữ nguyên: `docs/API_CONTRACT.md`, đặc biệt tenant-scoped routes, invoice/payment/refund, idempotent PO receive, report export và review-only Vision.
- Responsive/accessibility/browser findings: [Phase 6.2 accessibility](PHASE62_FINAL_ACCESSIBILITY.md) và [cross-browser report](PHASE62_CROSS_BROWSER_REPORT.md).
- Browser runner không phải production user session. Browser zoom 200% và native screen reader chưa test.
