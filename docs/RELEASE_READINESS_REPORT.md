# Báo cáo Sẵn sàng Demo & Staging 1.0 (`RELEASE_READINESS_REPORT.md`)

**Phạm vi đánh giá**: Nhánh tích hợp ổn định `solo/khang-petcare` (`5c34b9840fdaaacae2c8bb3f83e8f9c1e02c1e6f`) cùng các sửa lỗi phát hiện trong quá trình UAT & Visual QA trên nhánh `feature/demo-staging-readiness`.  
**Mục tiêu đánh giá**: Xác nhận tính tái lập môi trường, khả năng trình diễn hoàn chỉnh 3 vai trò, chất lượng hiển thị đa thiết bị, an toàn giao dịch và mức độ sẵn sàng lên môi trường **staging có kiểm soát** *(không bao gồm deploy production công khai)*.

---

## 1. Các lỗi thực tế phát hiện & đã khắc phục trong đợt Demo/Staging QA này

Trong quá trình chạy kiểm thử người dùng thật trên Chromium và audit 4 viewport (vượt ngoài các bộ unit/E2E sẵn có trước đó), nhóm đã phát hiện và sửa triệt để 3 khiếm khuyết thực tế:

1. **HTTP 500 trên Trợ lý mua sắm AI công khai (`/shop/ai-assistant/chat`)**:
   - *Nguyên nhân*: `petcare/services/storefront_ai_service.py` gọi `needs_pet_clarification(merged, prior_turn_count=...)` và `needs_product_clarification(...)` sai tên tham số (`turn_count`), đồng thời không giải nén tuple 3 phần tử `(should_clarify, packed_msg, packed_chips)` trước khi gọi `localize_clarification`.
   - *Khắc phục*: Tách helper `_clarification_response`, sửa đúng chữ ký & giải nén tuple cho cả gợi ý thú cưng và sản phẩm, và bổ sung regression test trong `tests/web/test_storefront_security_and_routes.py`.
2. **Tràn ngang mobile (`scrollWidth = 414 > 390 / 320px`) trên Tài khoản Khách hàng (`/shop/account`)**:
   - *Nguyên nhân*: `.sf-panel` và `.sf-split-layout` (ở breakpoint `@media (max-width: 980px)`) dùng `grid-template-columns: 1fr` thay vì `minmax(0, 1fr)` và thiếu `min-width: 0`, khiến bảng lịch sử đơn hàng đẩy rộng track grid vượt chiều ngang viewport mobile.
   - *Khắc phục*: Bổ sung `.sf-split-layout > * { min-width: 0; }`, `min-width: 0;` cho `.sf-panel` và `minmax(0, 1fr)` trong `petcare/static/css/storefront.css`.
3. **Hiển thị thừa nhãn ẩn & độ tương phản mobile**:
   - *Nguyên nhân*: Storefront (`product_detail.html`, `ai_assistant.html`, `cart.html`) sử dụng `.visually-hidden` nhưng `petcare/static/css/storefront.css` chưa định nghĩa utility này; đồng thời `.page-heading p` trong `petcare/static/css/ui.css` dùng `--color-faint` cho tỷ lệ tương phản sát biên (~4.0–4.5:1) trong lúc reveal.
   - *Khắc phục*: Bổ sung `.visually-hidden` trong `storefront.css` và chuyển `.page-heading p` sang `--color-muted` (`#475569`).

---

## 2. Bộ ảnh chụp Màn hình Thực tế (Real Chromium Screenshots)

Toàn bộ ảnh dưới đây được chụp trực tiếp trên Chromium headless chạy đối ứng server Flask + MySQL `petcare_demo_stage_test`:

- **Admin & Staff Workspace**:
  - [Login 1440px](assets/demo-readiness/01-login-1440.png) · [Admin Dashboard 1440px](assets/demo-readiness/02-admin-dashboard-1440.png) · [POS 1440px](assets/demo-readiness/03-pos-1440.png)
  - [Danh sách sản phẩm 1440px](assets/demo-readiness/04-products-1440.png) · [Danh sách thú cưng 1440px](assets/demo-readiness/05-pets-1440.png) · [Chi tiết thú cưng & Gallery 1440px](assets/demo-readiness/05b-pet-gallery-1440.png)
  - [AI Vision Tìm bằng ảnh 1440px](assets/demo-readiness/06-image-search-1440.png) · [Trợ lý AI Nội bộ 1440px](assets/demo-readiness/07-internal-ai-1440.png) · [Quản lý Đơn online Staff 1440px](assets/demo-readiness/15-staff-orders-1440.png)
- **Customer Storefront (`/shop`) — Responsive 320px đến 1440px**:
  - Trang chủ Storefront: [1440px](assets/demo-readiness/08-shop-home-1440.png) · [834px Tablet](assets/demo-readiness/08-shop-home-834.png) · [390px Mobile](assets/demo-readiness/08-shop-home-390.png) · [320px Small Mobile](assets/demo-readiness/08-shop-home-320.png)
  - Chi tiết & Checkout: [Sản phẩm 1440px](assets/demo-readiness/09-shop-product-detail-1440.png) · [Thú cưng 1440px](assets/demo-readiness/10-shop-pet-detail-1440.png) · [Giỏ hàng 1440px](assets/demo-readiness/11-shop-cart-1440.png) · [Checkout 1440px](assets/demo-readiness/12-shop-checkout-1440.png)
  - [Tài khoản Khách hàng 390px (đã sửa overflow)](assets/demo-readiness/13-shop-account-390.png) · [Trợ lý Mua sắm AI 1440px (đã sửa label input)](assets/demo-readiness/14-shop-assistant-1440.png)

---

## 3. Giới hạn hiện hành cần nêu rõ khi Demo & trước Production

1. **AI Vision là công cụ hỗ trợ, không xác nhận danh tính sinh học**: Chỉ trùng mã băm/gần trùng ảnh lưu kho mới là khớp tệp ảnh; các ứng viên ngoại hình tương đồng cùng loài luôn bắt buộc nhân viên đối chiếu thực tế. Ảnh minh họa danh mục (`is_illustrative=True`) không tham gia đối chiếu sinh trắc học.
2. **Bộ ảnh demo tổng hợp**: 68 ảnh thú cưng lưu trữ và 22 ảnh sản phẩm WebP dùng cho demo học thuật/staging thử nghiệm; khi vận hành thật cần thay bằng ảnh chụp sản phẩm/thú cưng thật của cửa hàng.
3. **Chế độ AI ngoài mặc định tắt (`AI_PROVIDER_APPROVED=0`)**: Khi chưa nạp key API ngoài (như Google Gemini Free Tier), cả AI nội bộ và AI Storefront chạy bằng **Offline Python Engine** an toàn nhưng trả lời dựa theo template dữ liệu MySQL & knowledge base đã duyệt.
4. **Tính năng chưa bật mặc định ở Staging/Local**: SMTP email outbox thực tế, S3 object storage đa node, và cổng thanh toán trực tuyến tự động (hiện hỗ trợ **Thanh toán tại cửa hàng** và **COD xác nhận thu tiền thủ công**).
5. **Thử nghiệm tải thực tế**: Đã kiểm tra concurrency khóa thú cưng/đơn hàng và rate-limit mức đơn vị/integration; chưa chạy stress/load benchmark quy mô lớn hàng nghìn request/giây trên hạ tầng staging thật.

