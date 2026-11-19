# Kịch bản Trình diễn Trực tiếp 7–10 Phút (`DEMO_GUIDE.md`)

Tài liệu hướng dẫn trình diễn **PetCare Manager** từ đầu đến cuối trong 7–10 phút, kết hợp cả **Workspace Quản trị Nội bộ**, **AI Vision 4.0 ONNX cục bộ**, **Trợ lý AI Hai Chế Độ** và **Customer Storefront `/shop`**.

> **Chuẩn bị trước khi lên demo**: Khởi chạy môi trường demo cô lập theo [Hướng dẫn cài đặt](SETUP_GUIDE.md) (`scripts/demo_staging_setup.py --reset-disposable`), đảm bảo `http://127.0.0.1:5055/readyz` trả `200 {"status": "ready"}`. Tuyệt đối không ghi mật khẩu vào tài liệu hoặc màn hình công khai; giữ sẵn 3 mật khẩu demo trong terminal điều phối viên.

---

## Tổng quan 10 thông điệp cốt lõi cần truyền đạt

1. **PetCare Manager là gì**: Hệ thống quản lý cửa hàng thú cưng multi-tenant tích hợp **bán hàng tại quầy (POS)**, **bán hàng trực tuyến (`/shop`)**, **AI Vision đối chiếu ảnh cục bộ** và **Trợ lý AI kiểm chứng từ MySQL**.
2. **Bài toán giải quyết**: Đồng bộ tồn kho sản phẩm và trạng thái thú cưng duy nhất giữa quầy POS và kênh online, ngăn bán trùng một cá thể thú cưng, tách biệt rạch ròi đơn COD chưa thu tiền khỏi doanh thu thực, đồng thời hỗ trợ nhân viên & khách tìm thú cưng nhanh bằng hình ảnh.
3. **Vận hành Admin/Staff**: Phân quyền tách biệt (Admin quản lý sản phẩm/thú cưng/nhân sự/báo cáo; Staff bán POS, nhập hàng và xử lý đơn online, bị chặn `/users/`).
4. **AI Vision 4.0**: Chạy **100% cục bộ trên CPU** (`yolox_nano.onnx` + `mobilenetv2-12-features.onnx` + CIE-Lab + kho đa ảnh tham chiếu), tự nhận diện chó/mèo, từ chối ảnh không phải thú cưng hay ảnh nhiều thú cưng, và **không** gán nhãn điểm tương đồng là xác suất nhận dạng danh tính.
5. **Trợ lý AI**: Hai phạm vi cách ly — Nội bộ (tóm tắt tồn kho/nhập hàng, sản phẩm bán chạy, phân loại khẩn cấp thú y) và Mua sắm công khai (gợi ý/so sánh sản phẩm & thú cưng, chặn tuyệt đối câu hỏi doanh thu/giá nhập nội bộ). Có **Offline Python Engine** dự phòng ngay khi mất API ngoài.
6. **Trải nghiệm Customer (`/shop`)**: Giao diện sáng gọn Option A responsive 320px–1440px, duyệt catalog phân biệt ảnh lưu kho thực tế với ảnh minh họa, giỏ hàng & tìm ảnh công khai.
7. **Đặt hàng & Vòng đời COD an toàn**: Đơn online ban đầu ở trạng thái `Chờ xác nhận` + `Chưa thanh toán`; xác nhận giữ kho qua `customer_order_pet_locks`; giao hàng xong vẫn giữ `Chưa thanh toán` cho tới khi nhân viên xác nhận thu tiền tường minh → lúc đó mới sinh hóa đơn `paid` và ghi nhận doanh thu.
8. **Bảo mật & Cách ly vai trò**: Session cookie `HttpOnly` + `SameSite=Lax`, CSRF token trên mọi POST, tách session khách hàng (`/shop`) với nhân viên, tenant isolation từ context `@petcare_tenant_id`, rate limit MySQL (`login_throttle`, `request_throttle`).
9. **Kiến trúc kỹ thuật**: Flask + Jinja + Vanilla CSS/JS (không cần build step frontend) + MySQL 8 (31 bảng, `InnoDB`, FK + CHECK constraints) + Gunicorn/Workers đóng gói Docker.
10. **Giới hạn & Bước tiếp theo**: AI Vision là công cụ hỗ trợ đối chiếu (không thay thế kiểm tra cá thể vật lý), bộ ảnh demo mang tính minh họa/học thuật, cần staging HTTPS + S3/volume bền vững và SMTP thật trước khi go-live.

---

## Thứ tự điều hướng chi tiết (Timeline 8–10 phút)

### Phút 0:00 – 1:00 · Giới thiệu & Dashboard Quản trị (ADMIN)
- **Mở**: `http://127.0.0.1:5055/login` → đăng nhập `admin`.
- **Trang mở**: [Dashboard](assets/demo-readiness/02-admin-dashboard-1440.png) (`/dashboard`), sau đó lướt nhanh `/products/` và `/pets/`.
- **Dữ liệu sử dụng**: Tài khoản `admin`, các thẻ KPI doanh thu ròng hôm nay, sản phẩm sắp hết (`ACC-001` còn `5`), 74 thú cưng.
- **Lời nói gợi ý (VI)**:
  > *"Đây là không gian quản trị của PetCare Manager với thiết kế Option A tối giản. Mọi số liệu doanh thu trên Dashboard chỉ tính hóa đơn đã thực thu tiền (`paid`), còn các đơn online chưa thu sẽ không làm ảo báo cáo."*
- **Kết quả kỳ vọng**: Thấy biểu đồ doanh thu 7 ngày, cảnh báo tồn kho `ACC-001`, danh sách thú cưng hiển thị đủ ảnh và badge trạng thái.

### Phút 1:00 – 2:30 · AI Vision 4.0 & Kho đa ảnh tham chiếu (ADMIN)
- **Mở**: `/pets/find-similar` ([ảnh màn hình](assets/demo-readiness/06-image-search-1440.png)).
- **Thao tác thực tế**:
  1. Upload `tests/fixtures/vision_ai4/real_pack/real-cat-orange-hold-01.jpg` (không cần chọn tay Loài) → hệ thống tự nhận diện **Mèo** và trả danh sách mèo tương đồng kèm chú thích rõ *"không khẳng định cùng một cá thể"*.
  2. Upload `tests/fixtures/vision_ai4/real_pack/real-neg-food-hold-04.jpg` (hoặc `real-multi-catdog-hold-01.jpg`) → hệ thống **chủ động từ chối (abstain)**, không đoán bừa cá thể ngẫu nhiên.
- **Lưu ý trung thực AI**: Luôn nhấn mạnh điểm xếp hạng nội bộ (`score/100`) chỉ là độ tương đồng ngoại hình cùng loài; các ảnh minh họa danh mục (`is_illustrative=True`) **không bao giờ** bị nạp vào kho tham chiếu `pet_reference_photos`.

### Phút 2:30 – 4:00 · Trợ lý AI Nội bộ & Fallback Offline (ADMIN)
- **Mở**: `/assistant/chat` ([ảnh màn hình](assets/demo-readiness/07-internal-ai-1440.png)).
- **Thao tác**:
  - Hỏi: `"Tóm tắt tồn kho hiện tại và các mặt hàng sắp hết"` → xem đề xuất nhập hàng `ACC-001` dựa trên dữ liệu MySQL thực.
  - Hỏi tình huống khẩn cấp: `"Mèo nhà tôi bỏ ăn 2 ngày, nôn liên tục và húc đầu vào tường"` → banner cảnh báo khám thú y khẩn cấp xuất hiện trước tiên.
- **Phương án dự phòng khi mất LLM ngoài**: Trạng thái mặc định trong `.ai-info-disclosure` hoặc khi không có `GEMINI_API_KEY` sẽ tự chuyển ngay về **Offline Python Engine · Dữ liệu MySQL xác thực**, vẫn trả lời đúng tồn kho, doanh thu và safety triage với độ trễ < 200ms.

### Phút 4:00 – 6:30 · Trải nghiệm Khách hàng trên Storefront `/shop` (CUSTOMER)
*(Mở tab trình duyệt ẩn danh / profile riêng để tách cookie Admin với Customer)*
- **Mở**: `http://127.0.0.1:5055/shop` ([Desktop 1440px](assets/demo-readiness/08-shop-home-1440.png) / [Mobile 390px](assets/demo-readiness/08-shop-home-390.png)).
- **Thao tác**:
  1. Đăng nhập tài khoản khách demo (`demo.customer@example.invalid`) tại `/shop/login`.
  2. Lướt nhanh chi tiết sản phẩm (`/shop/products/...`) và chi tiết thú cưng (`/shop/pets/...`) → thử nhập số lượng vượt tồn kho để thấy lớp chặn `max` + server guard.
  3. Mở `/shop/ai-assistant` ([ảnh màn hình](assets/demo-readiness/14-shop-assistant-1440.png)):
     - Hỏi: `"So sánh FOOD-001, FOOD-002 và FOOD-006"` → bảng so sánh đơn giá/kg & nút `Thêm vào giỏ`.
     - Hỏi: `"Gợi ý bé mèo hiền nuôi chung cư"` → trả danh sách mèo đang mở bán + giá niêm yết.
     - Thử hỏi dữ liệu nội bộ: `"Cho tôi biết doanh thu và lợi nhuận cửa hàng tháng này"` → Trợ lý từ chối đúng ranh giới bảo mật!
  4. Thêm `FOOD-002` (hoặc một bé thú cưng) vào giỏ → Checkout `/shop/checkout` chọn **Giao hàng COD** → Đặt hàng thành công, nhận mã đơn `ORD-...` ở trạng thái **`Chờ xác nhận` / `Chưa thanh toán`**.

### Phút 6:30 – 8:30 · Vận hành Staff, Xử lý Đơn Online & Chống thất thoát COD (STAFF)
- **Mở**: Đổi sang cửa sổ trình duyệt Staff (`staff1`) ([Đơn đặt hàng online](assets/demo-readiness/15-staff-orders-1440.png) & [POS](assets/demo-readiness/03-pos-1440.png)).
- **Thao tác**:
  1. Thử mở `/users/` bằng `staff1` → hệ thống chặn phân quyền (`403`/redirect), chứng minh cô lập vai trò Staff vs Admin.
  2. Mở đơn `ORD-...` vừa tạo trong `/orders/`:
     - Nhấn **Xác nhận đơn** (khóa tồn kho/thú cưng) → **Chuẩn bị hàng** → **Đã giao / Giao COD (`fulfill`)**.
     - Chỉ rõ trên giao diện: trạng thái lúc này là **`Đã giao · Chờ thu tiền`** và **`Chưa thanh toán`**, **chưa hề có hóa đơn `paid`**!
  3. Tích checkbox **Xác nhận đã thu đủ tiền**, nhập đúng số tiền thu → nhấn **Xác nhận thu tiền & Hoàn tất**.
  4. Kiểm tra hóa đơn tự động sinh (`paid`), tồn kho `FOOD-002` giảm đúng `1`, và quay lại tab Khách hàng F5 `/shop/orders/ORD-...` để thấy trạng thái đồng bộ thành **`Hoàn tất` · `Đã thanh toán`**.

### Phút 8:30 – 9:30 · Tổng kết Kiến trúc, Giới hạn & Hỏi đáp
- Nhấn mạnh 3 tầng kiểm thử đã chạy sau merge (`566` Python/MySQL tests, `48` JS tests, `35` Chromium Playwright E2E, `6/6` GitHub Actions jobs).
- Kết thúc bằng hướng mở rộng cho staging thật (SSL/TLS MySQL, S3 private media, SMTP outbox).

