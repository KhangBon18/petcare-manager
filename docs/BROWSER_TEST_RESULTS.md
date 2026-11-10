# Kết quả kiểm thử browser thật

## Bổ sung Phase 3 — 2026-11-09

Chạy Flask thật tại `127.0.0.1:5056` với schema `petcare_phase3_browser_test`; file media/export tạm nằm dưới `/tmp/petcare-phase3`. App dùng seed user trong môi trường localhost; không ghi mật khẩu hay token vào tài liệu.

| Workflow | Vai trò | Trạng thái | Bằng chứng thực tế |
|---|---|---|---|
| `/account/settings` | Staff | VERIFIED một phần | Đổi display name thành giá trị QA, nhận flash success; sau đó phục hồi `Nhân viên cửa hàng` và xác nhận lại. Không đổi mật khẩu/email hoặc gửi email. |
| `/users/` | Staff | VERIFIED denied | Direct route hiện “You do not have access”; admin session sau đó vẫn truy cập được chức năng quản trị. |
| `/users/export` và `/users/export/jobs/1` | Admin | VERIFIED | Mật khẩu bảo vệ không khớp bị từ chối. Yêu cầu hợp lệ tạo job; lượt worker đầu dùng media path sai trong lệnh kiểm tra nên job còn pending; chạy lại worker one-shot với cùng schema và đúng `/tmp/petcare-phase3` media/export config cho trạng thái `ready`. Browser thấy heading “Export ready” và download link. Bundle tải xuống có magic `PCEXP001`, 2,283,927 byte; được chuyển khỏi Downloads vào `/tmp/petcare-phase3/downloads`, directory/file permission 0700/0600. Chỉ kiểm tra header và size; không giải mã, không mở dữ liệu. |
| `/invoices/1` → refund | Admin | NOT TESTED qua browser | Invoice demo được xem và refund control hiện rõ giới hạn cash/bank transfer. Click submit không tạo trạng thái; CUA không giữ native confirm dialog. Không ghi refund từ browser và không thực hiện chuyển tiền. Route/transaction được kiểm riêng bằng MySQL integration test. |
| POS `/invoices/new` | Admin | VERIFIED UI, không submit | 390×844: thêm FOOD-005 vào client-side cart; preview hiện `1 item in order`, `55,000 VND`; “View order” đưa tới `#pos-order`, summary và nút Create invoice hiện trên màn hình. `document.scrollWidth=390`; không tạo hóa đơn. |
| Dashboard navigation | Admin | VERIFIED tại 820×1180 và 1440×900 | Tablet nav `scrollWidth=830`, `clientWidth=642`; scrollbar/fade được áp dụng và Reports mở được qua nav. Document rộng đúng 820 px. Desktop document rộng đúng 1440 px, navigation đầy đủ. |
| Browser console | — | PASS theo phạm vi quan sát | Sau workflow, `dev.logs({levels:['error','warning']})` trả `[]`. `/static/favicon.svg` 200; `/favicon.ico` tiếp tục 404. Network request panel chưa được thu thập. |

Tất cả browser writes ở lượt này đi vào schema QA riêng. Profile được phục hồi về giá trị gốc. POS chỉ thay đổi trạng thái trình duyệt; không submit invoice. Export artifact được giữ ngoài repository và không giải mã. Accessibility đầy đủ, các route khác tại mọi viewport, email, SMTP, AI/Vision và S3 vẫn `NOT TESTED`.

## Kết quả Phase 2 — 2026-11-09

Các mục dưới đây là bằng chứng lịch sử của Phase 2 và không bao gồm các thay đổi/profile/export đã được kiểm ở phần Phase 3 phía trên.

Ngày 2026-11-09. Dùng in-app Chromium/Playwright DOM automation với Flask ở `127.0.0.1:5056`, không phải mock Flask test client. Các record dùng prefix `QA Browser`/`E2E-` chỉ tồn tại trong schema `petcare_phase2_browser_test`.

## Tài khoản và tenant

| Ngữ cảnh | Kiểm tra |
|---|---|
| `admin` trên `main` | Menu owner/admin, dashboard, catalog, invoice, report, purchasing, store/team/activity. UI ghi `Administrator`; membership owner được kiểm thử backend ở suite MySQL. |
| `staff1` trên `main` | Dashboard và module staff; direct GET cho endpoint admin-only hiển thị 403. |
| `e2e-owner` | Tenant QA riêng hiển thị số liệu rỗng. Đã thử direct product ID của tenant `main`, kết quả không tìm thấy. |

Mật khẩu test không được đưa vào báo cáo. Login sử dụng account/password seed chỉ trong localhost.

## Viewport và quan sát trực quan

| Viewport | Màn hình | Kết quả |
|---|---|---|
| 320×720 | Dashboard | Không tràn ngang. Sau fix, `130,000 VND` một dòng; các nhãn bottom nav không bị tách chữ. |
| 390×844 | Dashboard, POS | Không tràn ngang. Metric tiền một dòng; POS product cards hai cột vừa viewport. Cart/order summary nằm sau catalog nên cần cuộn. |
| 820×1180 | Reports | Không tràn ngang ở document. Thanh nav có thể cuộn ngang; lúc đầu chỉ một phần link hiện trong khung. |
| 1440×900 | Các route admin/staff | Side navigation đầy đủ; bảng rộng có horizontal scroller riêng; pages render được. |

## Route và hành vi

| Module / route | Vai trò | Trạng thái | Bằng chứng thực tế |
|---|---|---|---|
| `/login`, `/dashboard` | Owner/admin, staff | VERIFIED | Hai account đăng nhập; dashboard thay nội dung theo tenant/account. |
| `/customers/`, `/customers/13`, `/customers/new`, `/customers/13/edit` | Owner/admin | VERIFIED | Search, create invalid phone (server message), create valid synthetic customer, detail, edit address, persistence sau redirect. |
| `/pets/`, `/pets/75`, `/pets/new`, `/pets/75/edit`, `/pets/find-similar` | Owner/admin | VERIFIED một phần | Search tên/status; detail ảnh; negative weight bị browser chặn; future birth date bị server từ chối nhưng giá trị được giữ; sửa ngày, upload ảnh local, tạo hồ sơ, mở lại và similarity search. Không thử camera. |
| `/products/`, `/products/25`, `/products/new`, `/products/25/edit` | Owner/admin | VERIFIED | Search SKU; duplicate code bị từ chối, field values giữ; tạo product QA có ảnh; edit mô tả; điều chỉnh stock +2 và thấy ledger. |
| `/invoices/`, `/invoices/new`, `/invoices/8`, `/invoices/9` | Owner/admin, staff read/create | VERIFIED một phần | Tạo invoice 12.000 VND; payment state nội bộ và stock thay đổi; hủy invoice chưa thanh toán và stock không đổi. Refund controls được xem nhưng không submit. |
| `/purchasing/`, `/purchasing/new`, `/purchasing/1`, `/purchasing/2`, `/purchasing/suppliers*` | Owner/admin | VERIFIED | Tạo supplier, PO 5 units, nhận 2 rồi 3; PO thứ hai đóng khi chưa nhận. Tồn 9→11→14 ở PO1, PO2 vẫn 14. Không xóa record QA. |
| `/reports/` | Owner/admin, staff | VERIFIED một phần | Ngày đảo thứ tự hiện lỗi; khoảng 2026-11-01→09 hiển thị report; Export Excel tải XLSX. Print/PDF chưa thử. |
| `/assistant/chat` qua panel | Owner/admin, staff | VERIFIED local | Mở panel, thấy local mode và cảnh báo không gọi endpoint AI; truy vấn low-stock trả kết quả gắn với catalog DB. |
| `/account/settings`, `/account/password/forgot` | Owner/admin | PARTIAL | GET và nội dung page được xem; không gửi reset/verify email. |
| `/store/settings`, `/users/`, `/users/ownership`, `/users/new`, `/users/export`, `/activity/` | Owner/admin | PARTIAL | Page render; ownership cho biết chưa có admin đủ điều kiện. Không thay đổi profile/quyền, mời user, tạo tài khoản, bắt đầu export hay chuyển ownership. |
| Staff direct GET: `/pets/new`, `/products/new`, `/products/25/edit`, `/store/settings`, `/users/`, `/purchasing/`, `/activity/` | Staff | VERIFIED denied | Trang “You do not have access”; menu admin không xuất hiện. |
| `/healthz`, `/readyz`, `/workersz`, `/metrics` | Public probe | VERIFIED | Safe app: 200/200/503/404. Worker chưa chạy; metrics tắt. |

## Validation, error và recovery

1. Customer phone quá ngắn: message lỗi; không ghi record; sửa thành phone hợp lệ thì submit thành công.
2. Pet ngày sinh tương lai: server từ chối. Trước fix route trả lại form rỗng; sau fix tên, mã, loài, giới tính, ngày, cân nặng, giá và fields khác còn nguyên; chỉnh ngày hợp lệ rồi lưu được.
3. Product code trùng: server từ chối. Sau fix mã/tên/category/price/reorder/description/stock giữ nguyên; ký tự test `<duplicate-code>` được escape.
4. POS quantity 0: input validity `false`; trước fix estimated total 12.000 VND, sau fix thành 0 VND và submit vẫn bị browser ngăn.
5. Report start > end: page báo không thể để start date sau end date; sửa khoảng ngày hợp lệ và mở report/export được.
6. Cross-tenant product ID: không trả tên/giá record từ tenant khác; trang quay về list với “Product not found”.

## Console, request và persistence

- Browser tab `dev.logs` với levels error/warning trả `[]` sau các workflow đã chạy.
- Flask access log không có 500/traceback. Có `GET /favicon.ico` 404; `/metrics` 404 (disabled) và `/workersz` 503 (worker absent) đúng cấu hình.
- Network panel đầy đủ **NOT TESTED**: CUA hiện chỉ cung cấp console logs, không cung cấp list failed requests hoặc request timings. Một lần mở `/metrics` 404 tạo trang lỗi Chromium; đã khôi phục bằng tab mới, đây là probe disabled chứ không phải lỗi route chức năng.
- Persistence được kiểm bằng redirect/detail/list trên customer, pet, product, invoice và purchase order. Purchase stock hiển thị trực tiếp trên trang detail; MySQL integration suite kiểm stock ledger, idempotency và rollback.

## Không chạy trong browser

Không submit refund/thu tiền thật; không gửi email; không gọi endpoint trả phí AI/Vision; không sử dụng camera; không đổi password/profile/role; không bắt đầu tenant data export; không in PDF. Những thao tác trên là `NOT TESTED` ngoài phần logic được kiểm bằng unit/integration tests.
