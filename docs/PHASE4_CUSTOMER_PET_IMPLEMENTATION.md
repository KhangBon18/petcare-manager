# Phase 4.1 — Triển khai customer và pet

Ngày: 2026-11-10. Phạm vi thực thi chỉ tập trung vào shared location cues và hành trình customer/pet; giữ Flask/Jinja, CSS/JS thuần, permission, route và API/HTML form contracts hiện có.

## Trải nghiệm đã thay đổi

1. **Breadcrumb dùng chung:** [`templates/partials/breadcrumbs.html`](../petcare/templates/partials/breadcrumbs.html) được include trong [`templates/base.html`](../petcare/templates/base.html). Trang dashboard và blueprint hiện có có nhãn cấp hiện tại; customer/pet detail, edit, create và pet image search có cấp điều hướng phù hợp. Bỏ các back-link trùng ở form/detail customer/pet.
2. **Danh sách khách hàng trên mobile:** [`templates/customers/index.html`](../petcare/templates/customers/index.html) giữ bảng/filter trên desktop; card list hiện ở ≤680px. Từng card có trạng thái, liên kết gọi điện, hóa đơn và form sửa/bật-tắt trạng thái có CSRF + confirm. CSS chừa vùng thao tác khỏi nút trợ lý nổi; Playwright kiểm tra các target không chồng lấp. CTA, search, active filter, phân trang và empty state hiện hữu vẫn dùng.
3. **Khách hàng ↔ pet đã mua:** [`customer_service.py`](../petcare/services/customer_service.py) bổ sung `purchased_pets` cho profile. [`customer_repo.py`](../petcare/repositories/customer_repo.py) truy vấn `pets.buyer_id` tenant-scoped, mới nhất trước, giới hạn 12 dòng và lấy tổng bằng `COUNT(*) OVER()` (MySQL 8). Trang customer hiển thị trạng thái, mã/tên/giống và link đến pet; khi vượt 12 thì có ghi chú + link danh sách pet. Empty state nói rõ quan hệ này chỉ xuất hiện sau hóa đơn đã thanh toán.
4. **Liên kết ngược từ pet:** [`templates/pets/detail.html`](../petcare/templates/pets/detail.html) biến buyer đã ghi nhận thành link profile customer; không hiện buyer nếu backend chưa có `buyer_name`.
5. **Form pet:** [`templates/pets/form.html`](../petcare/templates/pets/form.html) nhóm field đang có thành thông tin cơ bản, nhận diện, ảnh/giá; không thêm yêu cầu dữ liệu. Form customer giữ cấu trúc hiện tại, chỉ dùng breadcrumb chung.
6. **Style và ngôn ngữ:** tokens semantic được mở rộng trong [`static/css/tokens.css`](../petcare/static/css/tokens.css), style mới đặt trong [`static/css/app.css`](../petcare/static/css/app.css), text mới đi qua [`i18n.py`](../petcare/i18n.py).

## Truy vết workflow và contract

| Hành trình | Luồng đã thực thi | Quy tắc được giữ |
|---|---|---|
| Tạo customer | Browser → `/customers/new` POST → `customer_routes`/`customer_service` → repository trong tenant transaction → redirect + flash. Invalid phone giữ lại tên và chỉ field lỗi được đánh dấu. | Route/POST/CSRF/server validation/flash redirect không đổi. |
| Sửa customer | Browser → `/customers/<id>/edit` POST → service → tenant-scoped update/audit → redirect + success. | Không thay payload hoặc permission hiện có. |
| Tạo/sửa pet | Browser → `/pets/new`, `/pets/<id>/edit` → service/repository; invalid weight 0 bị browser native constraint chặn, sau đó sửa hợp lệ và save. | Giữ field, business rules, CSRF và redirect hiện có. |
| Liên kết dữ liệu | Tạo pet QA; POS lập invoice cho customer, thanh toán thành công; kiểm tra customer profile có pet và pet profile có link buyer. | Buyer relation do server/payment flow gán; UI không tự tạo relation, giá hoặc trạng thái. |

`/customers/<id>` là HTML profile, không phải API JSON mới. `get_customer_profile()` có thêm khóa nội bộ `purchased_pets`; không đổi endpoint, HTTP method, JSON contract hoặc quyền. DB dev `petcare_shop_dev` không được mở hay migrate trong quá trình triển khai/kiểm thử.

## Test bổ sung

- `tests/unit/test_customer_profile_service.py`: service trả collection `purchased_pets`.
- `tests/web/test_customer_profile.py`: card/list semantics, breadcrumb, English strings, buyer link.
- `tests/integration/test_mysql_sales.py`: sau payment MySQL thật, customer profile thấy pet đúng một lần.
- `tests/web/test_design_tokens.py`: token/style hooks và semantic markup.
- `scripts/browser_smoke/test_browser_smoke.py`: invalid/valid create customer, edit; invalid/valid create pet, edit; sale + buyer/purchased pet navigation; responsive smoke; cleanup fixture.

Chi tiết về kích thước viewport, ảnh và browser diagnostics ở [PHASE4_VISUAL_QA.md](PHASE4_VISUAL_QA.md). Test suite sau thay đổi: Python 371/371, JavaScript 28/28, Playwright 4/4, không có test skip. Đây là kiểm chứng local trên schema QA; chưa phải hosted CI hoặc production validation.

## Ranh giới

Không đổi sidebar hierarchy toàn ứng dụng, không tái thiết kế dashboard/sản phẩm/POS/báo cáo, không thêm appointment hoặc health records. Màn customer profile hiển thị tối đa 12 pet mới mua; danh sách toàn bộ pet vẫn là trang hiện hữu. Không thực hiện migration DB.
