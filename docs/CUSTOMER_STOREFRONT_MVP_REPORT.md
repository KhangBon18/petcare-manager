# Customer Storefront MVP 1.0 — Architecture, Security, Migration & QA Report

**Project**: PetCare Manager  
**Branch**: `feature/customer-storefront-mvp` (branched from UI checkpoint `b84e09e`)  
**Visual Design Direction**: Option A — *Premium SaaS Light*  
**Database Migration**: `storefront_orders_v1` (additive, idempotent)

---

## 1. Kiến trúc tổng thể & Cách tái sử dụng hệ thống lõi

Storefront MVP 1.0 được tích hợp trực tiếp vào ứng dụng Flask/MySQL hiện hữu thông qua hai Blueprint độc lập rõ ranh giới tin cậy (`trust boundary`):

1. **`storefront` Blueprint (`/shop`)** — [storefront_routes.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/routes/storefront_routes.py)
   - Dành cho khách vãng lai (guest) và khách hàng có tài khoản cửa hàng (`customer_accounts`).
   - Không yêu cầu `@login_required` của nhân viên, nhưng bị ràng buộc chặt chẽ bởi CSRF, rate limit theo IP (`request_throttle_service`), `Cache-Control: no-store` cho mọi route riêng tư (`/shop/cart`, `/shop/checkout`, `/shop/orders*`, `/shop/login`, `/shop/register`, `/shop/account`), và tách biệt hoàn toàn với `users` / `tenant_users` / dashboard ERP.
2. **`orders` Blueprint (`/orders`)** — [order_routes.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/routes/order_routes.py)
   - Dành riêng cho nhân viên (`staff`) và quản trị viên (`admin`) đã đăng nhập nội bộ (`@login_required`).
   - Cho phép lọc, xem chi tiết, xác nhận (`confirm`), đánh dấu đang chuẩn bị (`prepare`), từ chối (`reject`), hủy (`cancel`), và hoàn tất thanh toán (`complete_payment`).
   - Khi thu tiền (`complete_payment`), [storefront_service.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/services/storefront_service.py) tái sử dụng luồng nghiệp vụ chuẩn để tạo/liên kết khách hàng CRM (`customers`), tạo hóa đơn thật (`invoices` + `invoice_items`), ghi nhận xuất kho (`stock_movements`), chuyển `pets.sale_status = 'sold'` và mở khóa `customer_order_pet_locks`.

```
Khách hàng (Guest / Customer Session)
   │
   ▼
/shop/*  ──▶ storefront_routes.py ──▶ storefront_service / storefront_auth_service
   │                                         │
   ├─▶ /shop/image-search ──▶ storefront_vision_service (AI-4.0 ONNX, public pets only, scrubbed DTO)
   ├─▶ /shop/ai-assistant ──▶ storefront_ai_service (Isolated AI, refuses financials/PII/costs)
   └─▶ /shop/checkout ─────▶ customer_orders (pending / unpaid) + request_key idempotency

Nhân viên / Admin (Staff Session @login_required)
   │
   ▼
/orders/* ─▶ order_routes.py ──▶ storefront_service.process_order_action()
   │
   ├─ confirm / prepare ──▶ INSERT customer_order_pet_locks (chống bán trùng POS & đơn khác)
   └─ complete_payment  ──▶ invoices + stock_movements + pets.sale_status='sold'
```

---

## 2. Ma trận phân quyền: Khách hàng (Public / Customer) vs Nhân viên & Admin

| Chức năng / Dữ liệu | Guest (Chưa đăng nhập) | Customer (`customer_accounts`) | Staff (`users.role='staff'`) | Admin (`users.role='admin'`) |
|---|---|---|---|---|
| Xem sản phẩm & thú cưng công khai (`/shop`, `/shop/products`, `/shop/pets`) | Có (chỉ SP `active=1`, thú `available`) | Có | Có | Có (kể cả nội bộ `/products/`, `/pets/`) |
| Tìm kiếm bằng ảnh AI-4.0 (`/shop/image-search`) | Có (chỉ thú `available`, không hiện mô tả nội bộ) | Có | Có | Có |
| Trợ lý AI mua sắm (`/shop/ai-assistant`) | Có (bị chặn doanh thu/giá nhập/tồn nội bộ/PII) | Có | Có | Có (dùng `/assistant/` cho nội bộ) |
| Giỏ hàng & Đặt đơn `pending`/`unpaid` (`/shop/cart`, `/shop/checkout`) | Có (lưu token tra cứu đơn ký HMAC trong session) | Có (gắn `customer_account_id`) | Có (khi mua trên `/shop`) | Có (khi mua trên `/shop`) |
| Tra cứu & Hủy đơn khi còn `pending`/`confirmed` | Chỉ qua `order_code + số điện thoại` hoặc HMAC token trong session | Mọi đơn có `customer_account_id` khớp + cùng tenant | Xem/xử lý toàn bộ đơn của tenant tại `/orders/` | Toàn bộ đơn của tenant tại `/orders/` |
| Cổng nội bộ (`/dashboard`, `/orders/`, `/invoices/`, `/reports/`, `/customers/`) | Chặn (`302 -> /login`) | **Chặn tuyệt đối (`302 -> /login`)** | Được phép theo RBAC nhân viên | Toàn quyền quản trị tenant |
| Giá vốn, nhà cung cấp, báo cáo tài chính, nhật ký kiểm toán | Không truy cập được | Không truy cập được | Theo phân quyền POS | Toàn quyền |

### Bảo vệ chống rò rỉ & chống gian lận tích hợp
- **Tách session & tenant**: Session khách lưu `customer_account_id`, `customer_tenant_id`, `customer_session_version`; session nhân viên lưu `user_id`, `tenant_id`, `session_version`. Nhân viên chưa login nội bộ không mở được `/orders/`; khách hàng không bao giờ leo thang thành `staff`.
- **Chống sửa giá từ trình duyệt**: Checkout đọc giá trực tiếp từ bảng `products` và `pets` trong MySQL (`price_cart_snapshot` & khóa `FOR UPDATE`), bỏ qua mọi giá phía client.
- **Chống mua vượt tồn & đặt trùng thú cưng**: Truy vấn `reserved_product_quantities(..., lock=True)` và `locked_pet_ids(..., lock=True)` dùng đọc hiện hành (`FOR UPDATE`) trên InnoDB để khóa tồn kho dự giữ từ đơn `confirmed`/`preparing`; khóa `PRIMARY KEY (tenant_id, pet_id)` trên `customer_order_pet_locks` bảo đảm chỉ tối đa 1 đơn online xác nhận được cùng 1 thú cưng, và [invoice_service.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/services/invoice_service.py) chặn thu tiền POS nếu thú cưng đang bị khóa cho đơn online.
- **Báo cáo tài chính không bị méo**: Các đơn ở trạng thái `pending`, `confirmed`, `preparing`, `cancelled`, `rejected` chưa tạo dòng `invoices`; chỉ khi nhân viên thu tiền (`complete_payment`) mới phát sinh `invoices` thật.

---

## 3. Migration CSDL (`storefront_orders_v1`) & Rollback

### Bảng bổ sung trong [storefront.sql](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/database/storefront.sql)
1. `customer_accounts`: tài khoản người mua hàng, scoped theo `tenant_id`, mật khẩu băm qua chuẩn bảo mật hệ thống, có `session_version` và `active`.
2. `customer_orders`: đơn hàng trực tuyến với `order_code`, `request_key` (idempotency chống submit đúp), `customer_account_id`, `customer_id`, `invoice_id`, `processed_by`, `fulfillment_method` (`pickup` / `cod_delivery`), `payment_method` (`pay_at_store` / `cod`), `payment_status` (`unpaid` / `paid`), `order_status` (`pending` / `confirmed` / `preparing` / `ready_completed` / `rejected` / `cancelled`).
3. `customer_order_items`: dòng chi tiết `product` hoặc `pet`, ràng buộc CHECK bảo đảm thú cưng luôn có `quantity = 1` và `line_total = unit_price * quantity`.
4. `customer_order_pet_locks`: `PRIMARY KEY (tenant_id, pet_id)` bảo đảm tính duy nhất ở mức CSDL cho thú cưng đang giữ chỗ.

### Tính an toàn khi nâng cấp & Rollback
- **Nâng cấp (Forward / Idempotent)**: `initialize_database()` trong [initialize.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/petcare/database/initialize.py) áp dụng `storefront.sql` và ghi nhận marker `storefront_orders_v1` trong `schema_migrations`, chạy lặp lại an toàn không phá dữ liệu cũ (`CREATE TABLE IF NOT EXISTS`).
- **Rollback an toàn**:
  - Bước 1 (Ứng dụng): Quay lại commit nền `cab2446` hoặc tắt route `/shop` & `/orders` trước khi đụng schema; toàn bộ dữ liệu POS (`invoices`, `products`, `pets`, `customers`) không bị thay đổi cấu trúc.
  - Bước 2 (CSDL nếu cần gỡ sạch bảng storefront trên môi trường staging/dev): `DROP TABLE IF EXISTS customer_order_pet_locks, customer_order_items, customer_orders, customer_accounts;` và `DELETE FROM schema_migrations WHERE version = 'storefront_orders_v1';` (chỉ thực hiện khi chưa có hoặc đã đối soát hết `customer_orders`).

---

## 4. Phạm vi kiểm thử E2E & Trực quan trình duyệt

Suite [test_storefront_e2e.py](file:///Users/heisenbon/Documents/Workspace%20Code/NNLTPython/petcare-manager/scripts/browser_smoke/test_storefront_e2e.py) kiểm tra đầy đủ hành trình thực tế trên Chromium:
1. Trang chủ công khai `/shop`: kiểm tra sản phẩm/thú cưng hiển thị ảnh hợp lệ, `0` lỗi console/broken images, `axe-core` WCAG 2.1 A/AA `0` lỗi critical/serious.
2. Duyệt & xem chi tiết sản phẩm `/shop/products`, thêm vào giỏ, cập nhật badge `#sf-cart-count`.
3. Trợ lý AI mua sắm `/shop/ai-assistant`: hỏi so sánh `FOOD-001` & `FOOD-002` trả về thẻ sản phẩm hợp lệ; hỏi `"Doanh thu tháng này bao nhiêu?"` bị từ chối trong `.sf-notice`.
4. Tìm thú cưng bằng ảnh `/shop/image-search`: tải ảnh mèo cam thật (`real-cat-orange-hold-01.jpg`), hệ thống AI-4.0 trả về đúng `Cam Xoài Storefront`, mở chi tiết và thêm vào giỏ.
5. Kiểm tra giỏ hàng `/shop/cart` (đồng bộ 2 dòng sản phẩm + thú cưng).
6. Đăng ký tài khoản khách hàng `/shop/register` và xác nhận tài khoản khách bị chặn khi truy cập `/orders/`.
7. Đặt đơn COD tại `/shop/checkout` tạo mã `ORD-YYYYMMDD-XXXXXX` ở trạng thái `pending` / `unpaid`.
8. Xem lịch sử đơn tại `/shop/account`.
9. Kiểm tra responsive tại `834px`, `390px`, `320px` (không tràn ngang, không vỡ ảnh, đạt chuẩn `axe-core`).
10. Đăng nhập nhân viên tại `/login`, mở `/orders/`, xác nhận đơn (`confirm`), hoàn tất & thu tiền (`complete_payment`) tạo `invoice` thật và chuyển trạng thái `ready_completed`.

Ảnh chụp màn hình lưu tại thư mục `docs/assets/storefront-mvp1/` (gồm `home-1440.png`, `home-390.png`, `products-1440.png`, `product-detail-1440.png`, `pet-detail-1440.png`, `pets-1440.png`, `cart-1440.png`, `checkout-1440.png`, `order-confirmation-1440.png`, `customer-account-1440.png`, `ai-assistant-1440.png`, `image-search-1440.png`, `staff-orders-1440.png`, `staff-order-detail-1440.png`).

---

## 5. Checklist phát hành (Release Readiness Checklist)

- [x] Toàn bộ unit & web security tests (`tests/unit`, `tests/web`) xanh sau chỉnh sửa cuối cùng.
- [x] JS unit tests (`node --test tests/js/*.test.cjs`) xanh.
- [x] MySQL integration tests (`tests/integration/` — ngoại trừ Gemini network smoke) xanh trên schema `*_test` sạch, gồm concurrency stock/pet lock race & tenant isolation.
- [x] Full Playwright browser smoke (`scripts/browser_smoke/run_smoke.py`) xanh ở desktop (`1440px`), tablet (`834px`), mobile (`390px`, `320px`) với `0` lỗi `axe-core` critical/serious.
- [x] Quét bảo mật tĩnh `bandit -r petcare -lll -q` không có cảnh báo mức High.
- [x] Bảo toàn các nhánh ổn định (`main`, `solo/khang-petcare`, `feature/petcare-ui-ux-redesign`), PR #3, file ZIP nộp học thuật và các file untracked không liên quan; không push/merge tự động.

