# Checklist Nghiệm thu Người dùng & Giao diện (`USER_ACCEPTANCE_CHECKLIST.md`)

Ngày kiểm chứng thực tế trên Chromium: `2026-11-19` · Schema kiểm thử cô lập: `petcare_demo_stage_test` · Nhánh nguồn: `feature/demo-staging-readiness` (từ `solo/khang-petcare` `5c34b98`).

---

## 1. Nghiệm thu 3 Vai trò Người dùng (Role-Based UAT)

### Vai trò ADMIN (`admin` · `owner`)
- [x] Đăng nhập `/login` thành công và mở `/dashboard` ([ảnh 1440px](assets/demo-readiness/02-admin-dashboard-1440.png)).
- [x] Quản lý sản phẩm `/products/` hiển thị đủ 22 mặt hàng kèm ảnh minh họa sản phẩm ([ảnh 1440px](assets/demo-readiness/04-products-1440.png)).
- [x] Quản lý thú cưng `/pets/` hiển thị 74 hồ sơ thú cưng phân biệt ảnh lưu trữ và nhãn `Minh họa` ([ảnh 1440px](assets/demo-readiness/05-pets-1440.png)), xem chi tiết gallery đa ảnh `/pets/<id>` ([ảnh 1440px](assets/demo-readiness/05b-pet-gallery-1440.png)).
- [x] Kiểm tra nhập hàng & tồn kho `/purchasing/`, xem báo cáo `/reports/`.
- [x] Truy vấn Trợ lý AI nội bộ `/assistant/chat` ([ảnh 1440px](assets/demo-readiness/07-internal-ai-1440.png)): tóm tắt tồn kho (`ACC-001` còn 5), bán chạy 7 ngày (`CARE-001`), cảnh báo an toàn thú y.
- [x] Tìm thú cưng bằng ảnh `/pets/find-similar` ([ảnh 1440px](assets/demo-readiness/06-image-search-1440.png)).

### Vai trò STAFF (`staff1` · `staff`)
- [x] Đăng nhập `/login` và thao tác quầy POS `/invoices/new` ([ảnh 1440px](assets/demo-readiness/03-pos-1440.png)).
- [x] Xem nhập hàng `/purchasing/` và hàng đợi đơn online `/orders/` ([ảnh 1440px](assets/demo-readiness/15-staff-orders-1440.png)).
- [x] Chặn vượt quyền: `staff1` truy cập `/users/` bị từ chối quyền quản trị (403/redirect).
- [x] Xác nhận đơn → chuẩn bị → bàn giao/giao COD → xác nhận thu tiền COD tường minh (`payment_confirmed=1`, đúng `collected_amount`).

### Vai trò CUSTOMER (`demo.customer@example.invalid`)
- [x] Mở `/shop` ([Desktop 1440px](assets/demo-readiness/08-shop-home-1440.png), [Tablet 834px](assets/demo-readiness/08-shop-home-834.png), [Mobile 390px](assets/demo-readiness/08-shop-home-390.png), [Small Mobile 320px](assets/demo-readiness/08-shop-home-320.png)).
- [x] Duyệt & xem chi tiết sản phẩm ([ảnh 1440px](assets/demo-readiness/09-shop-product-detail-1440.png)), thú cưng ([ảnh 1440px](assets/demo-readiness/10-shop-pet-detail-1440.png)), tài khoản cá nhân ([Mobile 390px](assets/demo-readiness/13-shop-account-390.png)).
- [x] Tìm thú cưng bằng ảnh công khai `/shop/image-search` (nhận diện mèo thật, trả ảnh cùng loài).
- [x] Hỏi Trợ lý mua sắm `/shop/ai-assistant` ([ảnh 1440px](assets/demo-readiness/14-shop-assistant-1440.png)): gợi ý sản phẩm, so sánh giá/đơn giá, gợi ý thú cưng, từ chối câu hỏi doanh thu/lợi nhuận nội bộ.
- [x] Thêm sản phẩm vào giỏ ([Giỏ hàng](assets/demo-readiness/11-shop-cart-1440.png)), chặn vượt tồn kho (cả HTML5 `max` lẫn POST phía server), đặt đơn COD ([Checkout](assets/demo-readiness/12-shop-checkout-1440.png)), tự hủy đơn đang `Chờ xác nhận` (qua hộp thoại xác nhận), xem lịch sử đơn hàng.

---

## 2. Luồng Giao dịch End-to-End & Bảo vệ Kho/Thanh toán

- [x] Khách đặt đơn COD → DB ghi nhận `order_status='pending'`, `payment_status='unpaid'`, `invoice_id=NULL`.
- [x] Nhân viên xác nhận (`confirm`) → chuẩn bị (`prepare`) → đã giao (`fulfill`): xác nhận **`order_status='fulfilled'` vẫn giữ `payment_status='unpaid'` và chưa tạo hóa đơn**.
- [x] Nhân viên thu tiền (`complete_payment` kèm checkbox xác nhận + khớp `collected_amount`) → đơn chuyển `ready_completed`, `payment_status='paid'`, tự động tạo hóa đơn `status='paid'`, tồn kho sản phẩm giảm chính xác (`23 -> 22`).
- [x] Tab khách hàng trên `/shop/orders/<order_code>` hiển thị đồng bộ `Hoàn tất` · `Đã thanh toán`.
- [x] Chống bán trùng thú cưng ở mức DB qua `customer_order_pet_locks` (`PRIMARY KEY (tenant_id, pet_id)`) và idempotency đơn hàng qua `uq_customer_orders_tenant_request` (kiểm chứng thêm trong `test_storefront_mysql.py`).

---

## 3. Nghiệm thu AI Vision & AI Assistant

| Kịch bản kiểm tra | Kết quả quan sát thực tế |
| :--- | :--- |
| Upload ảnh mèo thật (`real-cat-orange-hold-01.jpg`) | PASS — Tự nhận diện loài **Mèo**, trả ứng viên mèo kèm chú thích không khẳng định danh tính cá thể |
| Upload ảnh chó thật (`real-dog-golden-hold-01.jpg`) | PASS — Tự nhận diện loài **Chó**, không gán nhầm nhãn xác suất nhận diện |
| Upload ảnh không phải thú cưng (`real-neg-food-hold-04.jpg`) | PASS — Từ chối an toàn, không trả cá thể ngẫu nhiên |
| Upload ảnh nhiều thú cưng (`real-multi-catdog-hold-01.jpg`) | PASS — Abstain với `data-abstention-reason="multiple_animals_detected"` |
| Ảnh minh họa danh mục (`is_illustrative=True`) | PASS — Cô lập trong `catalog_visuals.py`, không nạp vào `pet_reference_photos` |
| Trợ lý Storefront AI (`pet_recommendation` / `product_recommendation`) | PASS — Đã sửa `TypeError` `needs_*_clarification(..., prior_turn_count)`, phản hồi `HTTP 200` offline fallback mượt mà |
| Trợ lý Storefront AI câu hỏi doanh thu/lợi nhuận | PASS — Từ chối lịch sự theo chính sách bảo mật dữ liệu nội bộ |

---

## 4. Visual QA 4 Viewport (1440px, 834px, 390px, 320px) & Accessibility

Đã quét **60 lượt kiểm tra giao diện (15 màn hình × 4 kích thước màn hình)** trên Chromium thực:
- **Horizontal Overflow**: **0/60** (đã sửa lỗi tràn khung ngang trên `/shop/account` 390px & 320px bằng `min-width: 0` cho `.sf-panel` và `minmax(0, 1fr)` cho `.sf-split-layout`).
- **Ảnh hỏng / thiếu ảnh (`naturalWidth === 0`)**: **0/60** sau khi ảnh và network idle hoàn tất.
- **Lỗi Console / JS / HTTP 500**: **0**.
- **`axe-core` WCAG 2.0/2.1 AA (serious/critical)**: **0 vi phạm** trên desktop `1440px` và mobile `390px` (đã nâng độ tương phản `.page-heading p` sang `--color-muted` và bổ sung `.visually-hidden` cho label ẩn trong `storefront.css`).

