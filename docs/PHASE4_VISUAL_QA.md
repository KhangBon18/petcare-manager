# Phase 4.1 — Visual và browser QA

Ngày: 2026-11-10. Browser automation dùng Playwright Chromium với app Flask thật, session admin/staff và MySQL QA disposable (`petcare_phase3_browser_test`, cổng QA 3307). Ảnh dùng dữ liệu synthetic QA, lưu ngoài repository trong thư mục owner-only `/Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110`; không chứa thông tin credential. Không kết nối `petcare_shop_dev`.

## Ảnh trước triển khai

Before-state được chụp trước thay đổi, trước là 21 response/page checks với HTTP 200 và document width bằng viewport. File `before/metadata.json` ghi URL, title, viewport và browser error list rỗng. Ở 320px trang customer vẫn là bảng cuộn ngang; cột bị cắt khỏi màn hình dù document không tràn ngang.

| View | Ảnh |
|---|---|
| Shell/dashboard 1440px | [shell-dashboard-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/shell-dashboard-1440.png>) |
| Khách hàng list 320px | [customers-list-320.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/customers-list-320.png>) |
| Khách hàng profile 1440px | [customer-detail-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/customer-detail-1440.png>) |
| Form tạo/sửa customer | [customer-new-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/customer-new-1440.png>) · [customer-edit-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/customer-edit-1440.png>) |
| Pet list 320px / profile / forms | [pets-list-320.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/pets-list-320.png>) · [pet-detail-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/pet-detail-1440.png>) · [pet-new-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/pet-new-1440.png>) · [pet-edit-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/before/pet-edit-1440.png>) |

Before-state details/forms được chụp ở desktop; responsive checks trước triển khai có dashboard và customer/pet lists tại 320/390/768/820px. Không có before screenshot riêng cho detail/form từng breakpoint.

## Ảnh sau triển khai

| View | Ảnh |
|---|---|
| Customer list 320px — card thay bảng | [customers-list-320.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/customers-list-320.png>) |
| Customer profile + pet đã mua 1440px | [customer-detail-purchased-pet-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/customer-detail-purchased-pet-1440.png>) |
| Customer detail 320px | [customer-detail-purchased-pet-320.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/customer-detail-purchased-pet-320.png>) |
| Pet profile và buyer link 390px | [pet-detail-buyer-390.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/pet-detail-buyer-390.png>) |
| Form lỗi và form pet | [customer-form-invalid-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/customer-form-invalid-1440.png>) · [pet-form-invalid-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/pet-form-invalid-1440.png>) · [pet-form-new-1440.png](</Users/heisenbon/Documents/Codex/petcare-phase4-visual-qa-20261110/after/pet-form-new-1440.png>) |

## Kịch bản browser và kết quả

`scripts/browser_smoke/run_smoke.py` chạy **4/4 PASS, 0 fail/error/skip**. File `after/results.json` lưu kết quả; trace và runtime log nằm cùng thư mục ảnh.

| Kiểm tra | Kết quả quan sát |
|---|---|
| Admin navigation + responsive shell + POS + basic accessibility | PASS |
| Refund confirm/validation/idempotency/persistence hồi quy | PASS |
| Tạo customer lỗi/sửa, tạo pet lỗi/sửa; thanh toán invoice; chuyển customer→pet→buyer | PASS |
| Staff được phép customer và bị chặn users | PASS; `/users/` trả 403 như chính sách |
| Dashboard, customer/pet list tại 320/390/768/820/1440 | PASS; `documentElement.scrollWidth == viewport` |
| Customer detail và pet detail tại 320/390/768/820/1440 | PASS; document không tràn ngang, liên kết record hoạt động |
| Hành vi list theo kích thước | PASS; customer dùng card ở ≤680px, table ở chiều rộng lớn hơn |
| Hit-target card customer và launcher nổi ở mobile | PASS sau chỉnh CSS; browser kiểm tra hình chữ nhật target không giao nhau tại 320/390px |
| Browser diagnostics | 0 page exception, 0 failed request. Test role có đúng 1 console message và 1 HTTP 403 cho request GET `/users/`; đây là kết quả authorization được assert, không phải request hỏng ngoài dự kiến. |

Test tạo customer gửi phone không hợp lệ (`123`), xác nhận thông báo field và tên còn lại; sau đó tạo/sửa thành công. Test pet đặt `weight_kg=0`, thấy native `rangeUnderflow` và focus vẫn ở field lỗi; sau khi sửa, tạo/sửa thành công. POS lập invoice synthetic rồi thanh toán; customer hiển thị pet liên quan và pet có buyer link. Cleanup chỉ xóa fixture do chính test tạo.

### Giới hạn kiểm tra trực quan

- Accessibility là smoke (keyboard/label/landmark cơ bản), chưa chạy axe, screen reader thực, đo contrast, zoom 200% hay kiểm tra mọi trạng thái lỗi/empty trên mọi breakpoint.
- Chưa kiểm tra Safari/Firefox, thiết bị thật, mạng chậm, performance/lighthouse hoặc browser UI cho toàn bộ module.
- SMTP thật, AI/Vision bên ngoài và S3 không nằm trong test này.
- Lệnh browser suite local PASS trên QA MySQL; GitHub hosted Actions chưa chạy trong lượt này.
