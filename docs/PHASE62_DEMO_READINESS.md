# Phase 6.2 — mức sẵn sàng demo học thuật

**Kết luận:** CONDITIONAL GO cho demo local, synthetic data, database tạm và workers local. Không dùng cho production.

## Khởi chạy từ checkout sạch

Yêu cầu Docker Engine/Compose, Python 3.11+ (đã xác minh Python 3.13), Node/npm chỉ khi chạy a11y/browser test. Cài dependencies bằng lockfiles:

```sh
python3 -m venv /tmp/petcare-demo-venv
. /tmp/petcare-demo-venv/bin/activate
python -m pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock
```

Khởi chạy duy nhất bằng:

```sh
scripts/demo/classroom.sh --target qa
```

Launcher yêu cầu admin/staff demo passwords khác nhau từ prompt ẩn hoặc hai biến môi trường dài tối thiểu 16 ký tự. Không ghi password vào command history, log hay báo cáo. Mở URL loopback được launcher in ra. Đăng nhập `admin` hoặc `staff1` với mật khẩu vừa chọn.

- `admin`: user account `admin` được seed với tenant membership `owner`; app ánh xạ `owner` thành quyền admin cho luồng cửa hàng.
- `staff1`: tenant membership `staff`; được vào `/customers/`, bị từ chối `/users/` (403).
- Schema hỗ trợ role membership `owner`, `admin`, `staff`; launcher seed một owner và một staff, không tạo riêng một membership `admin` thứ hai.

Launcher khởi tạo schema/migration, synthetic seed, local Vision mock, mail/export worker và Flask. `/readyz` và `/workersz` phải healthy trước khi demo. Nhập `r` reset **chỉ** Compose project QA này cùng tmpfs schema; `q` hoặc Ctrl-C dừng và dọn đúng storage tạm có marker. Không chạy song song nhiều project từ cùng biến môi trường.

Lượt nghiệm thu Phase 6.2 xác minh schema có **26 bảng / 4 migration markers**; `/healthz`, `/readyz`, `/workersz` đều HTTP 200. Cả reset (`r`) và shutdown (`q`) chỉ áp dụng cho project do launcher tạo.

## Tích hợp và dữ liệu

- MySQL 8.4 QA, schema `_test` trong tmpfs; ảnh/export/log lưu ở thư mục temporary riêng.
- Email/provider integrations không cấu hình; không SMTP, S3, payment gateway hay external AI.
- Vision mock bind loopback và trả nhận xét cố định dựa theo synthetic request, không phân tích ảnh để đánh giá model.
- Assistant top-products/operations insight lấy query/service thật từ MySQL; các trả lời intent cục bộ khác theo rule. Provider LLM tùy chọn bị launcher cô lập, không phải capability đã được xác minh trong demo này.
- Mất Internet không ảnh hưởng flow app nếu Python packages, container image và browser đã cài trước. Lần đầu build image có thể cần pull image trước khi offline.
- Mở UI thủ công chỉ cần browser hiện có. Connected automation cần `python -m playwright install chromium`; cross-browser axe cần `python -m playwright install chromium firefox webkit` và `npm ci --prefix tests/a11y`. Cài/cache trước khi dùng offline.

## Rehearsal / reset

Rehearsal UI tự động: `python -m scripts.demo.classroom_rehearsal` với app, browser, DB QA đang chạy. **PASS, 14 bước / 17.76 giây browser automation** (không tính launcher startup/reset). Script tạo customer/pet/product/supplier/PO, nhận 3+5, bán product + pet, thanh toán, hoàn một unit, report, export worker/download, assistant, Vision mock, staff permission check và cuối cùng đối chiếu DB. Kết quả reconciliation: PO received, receipt movements 2, product stock 7; invoice 2.650.000 VND, refund 75.000 VND, net 2.575.000 VND; pet buyer trùng customer. 0 page errors, 0 unexpected failed requests/HTTP errors/console errors. Nó ghi 7 screenshot viewport không chứa thông tin đăng nhập và report summary ở temp.

Kết quả đo thực tế được ghi trong [demo script](ACADEMIC_DEMO_SCRIPT.md) sau khi lượt connected rehearsal hoàn tất. Reset bằng cách nhập `r` ở launcher prompt; không dùng SQL drop trên DB khác.

## Fallback

- DB/Compose startup fail: kiểm `docker info`, port/health output; đừng chuyển sang `petcare_shop_dev`. Demo dừng nếu readiness không 200.
- Browser automation fail: dùng UI thủ công cùng launcher; test runner là kiểm chứng, không phải dependency của app runtime.
- Worker fail: `/workersz` không 200 thì bỏ phần export, ghi BLOCKED; không giả lập kết quả worker.
- Vision mock fail: bỏ Vision live interaction và nêu local fallback/review-only; không bật real provider.
- Internet unavailable: chạy nếu image và locked wheels đã cache. Nếu thiếu, dùng screenshot/report đã tạo như phương án trình bày, nhưng đánh dấu live demo blocked.
