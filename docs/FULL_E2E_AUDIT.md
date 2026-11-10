# Kiểm toán E2E toàn ứng dụng — Phase 2

Ngày: 2026-11-09. Đây là đánh giá bằng chứng của lượt kiểm thử browser và bộ tự động hiện tại, không phải chứng nhận production-ready.

## Tóm tắt

- Đã chạy Flask thật trên cổng `5056`, dùng hai schema MySQL riêng có hậu tố `_test`; không thay đổi schema `petcare_shop_dev` hoặc production.
- Đã đăng nhập bằng tài khoản owner/admin và staff được seed. Đã đi qua các trang chính, thực hiện CRUD tổng hợp, bán hàng, nhập hàng, báo cáo, tìm ảnh và trợ lý local.
- Không phát hiện lỗi P0/P1. Ba lỗi giao diện có thể tái hiện đã được sửa và kiểm tra lại: mất dữ liệu form pet/product khi lỗi validation, ước lượng POS sai với quantity 0, và chữ bị tách ở màn hình nhỏ.
- Python: **366/366 PASS**, không có skip/error trong lần chạy đầy đủ. JavaScript: **27/27 PASS**. Bandit theo đúng lệnh CI exit 0; `pip-audit` báo không có advisory đã biết.
- Health và readiness của schema tự động: `/healthz` 200, `/readyz` 200. `/workersz` 503 do không chạy email/export worker. `/metrics` 404 vì metrics bị tắt.
- SMTP, AI/AI Vision từ provider thật, S3, tenant export job, luồng refund, screen reader/WCAG đầy đủ và bắt request thất bại trong DevTools chưa được xác minh.

## Môi trường và ranh giới dữ liệu

| Thành phần | Kết quả |
|---|---|
| Branch / working tree | `solo/khang-petcare`; giữ nguyên các thay đổi có sẵn; có checkpoint ngoài `/tmp` tại `/Users/heisenbon/Documents/Codex/petcare-phase2-checkpoint-20261109`; không commit. |
| App | Flask thật, `http://127.0.0.1:5056`, cấu hình cục bộ trong `/tmp/petcare-phase2-e2e/app.env`; dịch vụ đã dừng sau kiểm thử. |
| Browser data | Schema `petcare_phase2_browser_test`; chứa customer, pet, product, invoice, supplier và purchase order tổng hợp do lượt này tạo. |
| Automated tests | Schema mới `petcare_phase2_automated_test`; initializer/seed và integration tests chỉ ghi vào schema này. |
| Media/export | `/tmp/petcare-phase2-e2e`; không chép secrets vào repository hoặc báo cáo. |
| Provider thật | MAIL, AI, AI Vision, S3 để trống/tắt. Không gửi email, ảnh hay câu hỏi ra bên ngoài. Không có payment gateway; trạng thái “paid” chỉ là chuyển trạng thái nội bộ trong DB QA. |
| Dev DB | Baseline Phase 1.5: 20 bảng, `/readyz` 503. Không truy cập ghi, migrate, seed hoặc thay schema dev trong Phase 2; con số/status này chưa đo lại ở lượt này. |

## Luồng đã thực sự chạy

| Luồng | Trạng thái | Bằng chứng |
|---|---|---|
| Đăng nhập và dashboard | VERIFIED | Login thật bằng owner/admin và staff. Dashboard hiển thị số liệu tenant tương ứng; tenant QA thứ hai rỗng. |
| Customer | VERIFIED một phần | Tìm kiếm; tạo phone `123` bị từ chối và giữ dữ liệu; tạo customer tổng hợp với phone hợp lệ; mở detail, sửa address, điều hướng lại và thấy dữ liệu đã lưu. |
| Pet | VERIFIED một phần | Tìm theo tên/trạng thái, mở detail; số cân âm bị native validation chặn; ngày sinh tương lai bị server từ chối; sau fix form giữ lại dữ liệu; tạo pet tổng hợp với ảnh local, mở lại hồ sơ và chạy tìm ảnh tương tự. |
| Product và inventory | VERIFIED một phần | Tìm SKU; duplicate SKU bị từ chối và giữ/escape dữ liệu form; tạo product QA, sửa mô tả, điều chỉnh tồn +2 và thấy stock ledger/giá trị mới. |
| POS / invoice | VERIFIED | Tạo invoice tổng hợp 12.000 VND; xác nhận thanh toán nội bộ làm stock giảm 1; tạo invoice thứ hai rồi hủy khi chưa trả, giao diện báo tồn kho không đổi. Quantity 0 bị form chặn; sau fix estimated total bằng 0. Không có tiền thật chuyển. |
| Purchasing | VERIFIED | Tạo supplier QA; tạo PO 5 × 10.000 VND; nhận 2 rồi nhận tiếp 3; trang detail cho thấy trạng thái `Partially received` → `Fully received`, stock 9 → 11 → 14. PO khác bị đóng khi chưa nhận; stock giữ 14. Integration suite còn kiểm replay/idempotency, rollback và invalid transition trên MySQL. |
| Reports | VERIFIED một phần | Ngày bắt đầu sau ngày kết thúc hiện thông báo rõ; khoảng hợp lệ xuất XLSX tổng hợp; tệp tải xuống có định dạng Excel hợp lệ. Print/PDF chưa chạy. |
| Assistant | VERIFIED local | Panel hiển thị rõ `Local lookup · generative AI is not connected`, cam kết không gọi endpoint bên ngoài; truy vấn low-stock trả item từ MySQL và nhãn `Local lookup · current MySQL data`. |
| Store/team/ownership/activity/account | PARTIAL | Các trang admin/store settings, team, ownership, activity, account settings, password recovery và tenant export form đã mở; không tạo lời mời, đổi quyền, đổi mật khẩu, yêu cầu export hay gửi email. |
| Staff permissions | VERIFIED một phần | Staff mở customer/pet/product read, POS, invoice, reports/account; direct GET tới product/pet write, purchasing, store settings, users và activity hiển thị trang 403. Menu admin bị ẩn. |
| Tenant isolation | VERIFIED một đường | Sau khi chuyển sang tenant QA rỗng, mở product ID của tenant `main` nhận “Product not found” rồi quay về list; tên/giá sản phẩm không bị lộ. |

## Runtime và chất lượng

| Kiểm tra | Trạng thái | Kết quả |
|---|---|---|
| Python suite | PASS | `python -m unittest discover -s tests -q` với schema `petcare_phase2_automated_test`: 366 test, 36.2 giây, `OK`; không có skip được báo. |
| JavaScript suite | PASS | `node --test tests/js/*.test.cjs`: 27/27. |
| Python compile | PASS | `python -m compileall -q run.py main.py petcare tests scripts`. |
| Package consistency | PASS | `pip check`: `No broken requirements found.` |
| Dependency advisory scan | PASS | `pip-audit -r requirements.lock`: `No known vulnerabilities found`. |
| Bandit CI gate | PASS | Lệnh `.github/workflows/ci.yml` exit 0 với `bandit==1.9.4` và baseline hiện hành; stdout có cảnh báo `nosec encountered (B608)` tại các suppression hẹp, không có finding mới chặn CI. |
| Compose config | PASS | `docker compose config --quiet`, exit 0. |
| Health/readiness tự động | PASS | `/healthz` 200; `/readyz` 200; schema QA đáp ứng contract. |
| Worker/metrics probes | EXPECTED UNAVAILABLE | `/workersz` 503 vì không chạy worker; `/metrics` 404 vì token chưa cấu hình. Đây không phải exception ứng dụng. |
| Console | PASS theo quan sát | `dev.logs({levels:[error,warning]})` trả mảng rỗng trong tab kiểm thử. |
| Network panel | NOT TESTED | API CUA có console log nhưng không cung cấp danh sách request/response Network. Flask access log chỉ cho thấy 404 `favicon.ico`, 404 `/metrics` (đã tắt) và 503 `/workersz` (worker chưa chạy); không thấy 500/traceback. |
| Trivy / image security scan | NOT TESTED | CLI/action Trivy không chạy trong lượt này. Image build đã PASS ở Phase 1.5, chưa build lại Phase 2. |

## Responsive và accessibility

- Đã quan sát bằng browser ở 320×720, 390×844, 820×1180 và 1440×900. Dashboard/POS ở mobile và reports ở tablet được chụp/quan sát trực tiếp.
- `documentElement.scrollWidth` không vượt viewport tại 320, 390 hoặc 820 px. Ở 820 px, thanh điều hướng desktop có `scrollWidth` lớn hơn `clientWidth` và tự cuộn ngang; người dùng vẫn có thể kéo để tới links còn lại nhưng dấu hiệu cuộn chưa rõ.
- Sau fix, giá trị tiền không bị ngắt giữa chuỗi tại 320/390 px; nhãn bottom navigation một dòng tại 320 px.
- Kiểm tra DOM trên POS: có `main`, `nav`, `header`, `lang=en`; không phát hiện control POS không có label/ARIA name hoặc button hiển thị không tên.
- Chưa chạy axe/WAVE, bàn phím toàn site, screen reader, contrast, zoom 200%, reduced-motion browser matrix hay từng route ở mọi breakpoint. Đây là lấy mẫu responsive/accessibility, không phải WCAG certification.

## Findings

- **P0/P1: không có lỗi đã xác nhận.**
- **E2E-01 (P2, đã sửa):** lỗi server-side validation ở pet/product create làm mất giá trị đã nhập. Root cause là render form không nhận `request.form`. Route/template nay giữ submitted values; 2 regression test Python và browser retry đã PASS.
- **E2E-02 (P2, đã sửa):** POS dùng `Math.max(1, parseInt(...))`, làm quantity 0 trông như quantity 1 trong estimated total. Nay chỉ cộng số nguyên dương, không vượt `max`; JS regression và browser invalid-state cùng cho total 0.
- **E2E-03 (P2, đã sửa):** `overflow-wrap:anywhere` làm tiền và bottom labels vỡ chữ ở viewport nhỏ. Thêm media rules cục bộ; kiểm tra lại bằng screenshot/DOM tại 320 và 390 px.
- **UX-04 (P3, chưa sửa):** nav ngang ở tablet cần swipe/scroll, không có cue rõ.
- **UX-05 (P3, chưa sửa):** POS xếp catalog trước order summary trên mobile nên cần cuộn xuống để tới giỏ.
- **NET-01 (P3, chưa sửa):** trình duyệt yêu cầu `/favicon.ico` nhưng server trả 404; không ảnh hưởng workflow.

## Giới hạn và quyết định

1. Không dùng migration lên `petcare_shop_dev`; remediation vẫn ở `docs/DB_READINESS_REMEDIATION.md`, cần người dùng duyệt trước mọi mutation.
2. Payment/refund gateway, SMTP, provider AI, AI Vision và S3 chưa thử thật. Chỉ bật khi có cấu hình được duyệt và chốt chính sách dữ liệu/chi phí.
3. Giữ hai schema QA và volume MySQL riêng để có thể xem lại kết quả; chúng không phải dev/prod. Không xóa schema hoặc volume trong lượt này.
4. Xem chi tiết browser trong [BROWSER_TEST_RESULTS.md](BROWSER_TEST_RESULTS.md), UX trong [UX_ISSUES.md](UX_ISSUES.md), độ hoàn thiện trong [MODULE_COMPLETENESS_MATRIX.md](MODULE_COMPLETENESS_MATRIX.md), AI trong [AI_INTEGRATION_AUDIT.md](AI_INTEGRATION_AUDIT.md), thứ tự thực hiện trong [MASTER_UPGRADE_ROADMAP.md](MASTER_UPGRADE_ROADMAP.md).
