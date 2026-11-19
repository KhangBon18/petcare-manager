# PetCare Manager — UI/UX Redesign Results (v2 "Spruce & Saffron")

Nhánh: `feature/petcare-ui-ux-redesign` (local, tách từ `feature/ai-4.0-pet-image-matching` @ `b372b22`). Không push, không merge, không động tới `main`, `solo/khang-petcare`, Draft PR #3 hay ZIP nộp bài AI-3.4.

Tài liệu liên quan: [UIUX_REDESIGN_AUDIT.md](UIUX_REDESIGN_AUDIT.md) · [UIUX_DESIGN_SYSTEM.md](UIUX_DESIGN_SYSTEM.md) · [UIUX_REFERENCE_RESEARCH.md](UIUX_REFERENCE_RESEARCH.md)

## 1. Before / After (ảnh render thật, Playwright Chromium, CSDL QA `*_test`)

| Màn hình | Before | After |
|---|---|---|
| Đăng nhập | ![](assets/uiux-redesign/before-01-login-desktop.webp) | ![](assets/uiux-redesign/after-01-login-desktop.webp) |
| Dashboard | ![](assets/uiux-redesign/before-02-dashboard-desktop.webp) | ![](assets/uiux-redesign/after-02-dashboard-desktop.webp) |
| Dashboard mobile 390 | ![](assets/uiux-redesign/before-02-dashboard-mobile.webp) | ![](assets/uiux-redesign/after-02-dashboard-mobile.webp) |
| POS | ![](assets/uiux-redesign/before-03-pos-desktop.webp) | ![](assets/uiux-redesign/after-03-pos-desktop.webp) |
| Sản phẩm | ![](assets/uiux-redesign/before-04-products-desktop.webp) | ![](assets/uiux-redesign/after-04-products-desktop.webp) |
| Thú cưng | ![](assets/uiux-redesign/before-08-pets-desktop.webp) | ![](assets/uiux-redesign/after-08-pets-desktop.webp) |
| Hồ sơ + thư viện ảnh | ![](assets/uiux-redesign/before-09-pet-detail-gallery-desktop.webp) | ![](assets/uiux-redesign/after-09-pet-detail-gallery-desktop.webp) |
| Tìm bằng ảnh | ![](assets/uiux-redesign/before-10-image-search-desktop.webp) | ![](assets/uiux-redesign/after-10-image-search-desktop.webp) |
| Trợ lý AI | ![](assets/uiux-redesign/before-11-assistant-desktop.webp) | ![](assets/uiux-redesign/after-11-assistant-desktop.webp) |
| Báo cáo | ![](assets/uiux-redesign/before-13-reports-desktop.webp) | ![](assets/uiux-redesign/after-13-reports-desktop.webp) |

Bộ đầy đủ 39 ảnh BEFORE/AFTER (desktop 1440, tablet 834, mobile 390) tái tạo bằng `scripts/ui_capture/capture_screens.py --label before|after` (lưu ngoài repo).

## 2. Thay đổi theo module

| Module | Thay đổi chính |
|---|---|
| Shell / Sidebar | Sidebar spruce tối (desktop), nhóm `Bán hàng · Hàng hóa · Công cụ AI · Quản trị`, vạch saffron cho mục đang mở, brand mark "thẻ vòng cổ", nền sidebar kéo hết chiều cao; bỏ ghi chú sidebar và footer. Tablet/mobile giữ thanh ngang / bottom bar cũ, restyle sáng |
| Topbar | Sticky, nền mờ, control 36–40px |
| Dashboard | Lời chào + 3 hành động nhanh; 4 KPI bấm được (dẫn tới báo cáo/khách/sản phẩm/thú cưng), KPI cảnh báo tồn kho tô màu; bố cục 2 cột: biểu đồ + hóa đơn gần đây \| tồn kho sắp hết + gợi ý nhập + lối tắt; bỏ "Mẹo nhỏ", "Bắt đầu nhanh", doanh thu 7 ngày trùng lặp (thành lối tắt) |
| POS | Ô tìm kiếm có icon, bộ lọc segmented, lưới thẻ tự co giãn, trạng thái chọn/nhấn rõ, tổng tiền font display |
| Sản phẩm / Kho / Nhập hàng | Bảng mật độ kiểu Stripe, tiêu đề cột sentence case, icon tìm kiếm SVG, tag/stock/status thống nhất |
| Khách hàng | Bảng CRM gọn, avatar brand, status không xuống dòng |
| Thú cưng | Lưới 4 cột tự co, thẻ ảnh vuông `contain` (giữ trọn con vật — yêu cầu sản phẩm), zoom nhẹ khi hover, status pill nổi trên ảnh |
| Hồ sơ thú cưng | Ảnh lớn, danh sách chi tiết 2 cột, thư viện 5 ảnh có padding chuẩn, file input được style, ảnh chính viền brand |
| Tìm bằng ảnh | "Search studio" 2 cột: vùng thả ảnh lớn + camera \| bộ lọc + nút tìm + tuyên bố giới hạn nhận diện (luôn hiển thị) + ghi chú quyền riêng tư; giải thích ONNX, hướng dẫn điện thoại, mẹo thêm ảnh gom vào "Cách hoạt động & giới hạn" |
| Kết quả tìm ảnh | Chip loài đã nhận diện màu positive, badge thứ hạng trên ảnh, tách nhóm "khớp ảnh lưu" / "tương đồng – cần nhân viên đối chiếu" giữ nguyên |
| Trợ lý AI | Mô tả header 1 dòng, segmented scope, prompt 2 cột, composer bo lớn có focus ring cả khối; thông báo phạm vi khách mua và nguyên tắc an toàn giữ nguyên |
| Báo cáo | Nút kỳ dạng pill, KPI/biểu đồ thống nhất; công thức gợi ý nhập gom vào "Cách tính" |
| Hóa đơn | "PRODUCT/PET" chưa dịch → tag `Sản phẩm/Thú cưng` (sửa lỗi bản địa hóa) |
| Cài đặt / Tài khoản | Form, status, nút thống nhất; status pill không vỡ dòng |
| Đăng nhập | Panel spruce + mosaic 3 ảnh thú cưng tổng hợp của dự án (WebP, 62 KB), tiêu đề một màu, bỏ eyebrow/footer chữ hoa |
| Văn bản | Gỡ 75 nhãn eyebrow ALL-CAPS; 13 chuỗi mới có bản dịch EN |

## 3. Kết quả kiểm thử (trên MySQL `*_test` cô lập)

| Hạng mục | Kết quả |
|---|---|
| Python / MySQL `unittest` | **553/553 OK** |
| JavaScript `node --test` | **48/48 OK** |
| Playwright Chromium E2E (`run_smoke.py`) | **34/34 OK** (lần chạy đầu phát hiện 6 hồi quy thật — contrast, `outline:none` trên input, tràn 320px, ảnh bị crop, tỉ lệ khung ảnh hồ sơ — đã sửa tận gốc, không chỉnh kỳ vọng test) |
| axe-core WCAG 2.0/2.1 A+AA (serious/critical) | **0 vi phạm** trên 39 tổ hợp (13 trang × desktop/tablet/mobile) — `scripts/ui_capture/audit_a11y.py` |
| Tràn ngang | 0 trang |
| Focus bàn phím | 6 tab stop đầu của mỗi trang đều có chỉ báo hiển thị |
| Bandit (baseline) | **No issues identified** |
| CSP | Không inline style/script mới, không CDN/font ngoài; SVG chevron/ icon dùng data URI trong CSS (style-src `'self'`) |

Test được cập nhật (chỉ các assertion bám vào nhãn trang trí đã gỡ có chủ đích): `tests/web/test_pages.py`, `test_customer_profile.py`, `test_phase3_modules.py`, `tests/integration/test_mysql_web.py` — thay bằng nội dung vẫn hiển thị (vẫn kiểm tra bản dịch EN).

## 4. Vấn đề còn lại & khuyến nghị

1. Sidebar chưa có chế độ thu gọn (collapse) — nên thêm khi có lưu trạng thái người dùng.
2. Nhiều template vẫn là chuỗi Jinja một dòng dài; nên tách dần khi chỉnh tiếp.
3. `app.css` vẫn chứa nhiều màu hardcode cũ; `ui.css` ghi đè ở tầng hiển thị. Bước tiếp theo: hợp nhất dần vào token.
4. Một số liên kết văn bản còn ký tự "→" và vài đoạn ghi chú dài (refund, export) có thể rút gọn thêm.
5. Ảnh SaaSFrame không khảo sát được (anti-bot checkpoint) — không vượt qua.

