# PetCare Manager — UI/UX Reference Research

> Mục đích: ghi lại các mẫu giao diện từ sản phẩm thật được dùng làm **cảm hứng thiết kế** cho bản redesign v2. Không sao chép bố cục pixel-by-pixel, không dùng tài sản thương hiệu, mã nguồn hay hình ảnh độc quyền.

## Phương pháp

- Ngày khảo sát: 18/11/2026.
- Subagent trình duyệt (Chrome DevTools) bị chặn vì Chrome chưa bật remote debugging → chuyển sang Playwright Chromium headless mở **trang công khai**, chụp màn hình viewport 1440×900 và cuộn tới phần minh họa sản phẩm.
- **SaaSFrame** (`https://www.saasframe.io`) trả về *Vercel Security Checkpoint* (HTTP 429, trang chống bot) → **dừng lại, không vượt qua**, không dùng nguồn này.
- `https://attio.com/platform` trả về 404; dùng trang chủ Attio (có ảnh chụp ứng dụng thật).
- Polaris (`polaris-react.shopify.com`) render phía client, chỉ lấy được khung tài liệu; mẫu Shopify được tham khảo qua trang POS công khai.
- Đã tham khảo skill `ui-ux-pro-max` (chạy cục bộ, chỉ đọc CSV) và `frontend-design` để đối chiếu nguyên tắc.

## Bảng tham chiếu

| # | Nguồn (URL đã mở) | Mẫu / màn hình | Vì sao hiệu quả | Áp dụng cho PetCare | Module |
|---|---|---|---|---|---|
| 1 | https://linear.app | Ứng dụng mẫu: sidebar tối, nhóm "Workspace / Favorites" viết thường, item 13px, icon xám nhạt | Điều hướng nằm trên một bề mặt riêng, tách hẳn nội dung; nhãn nhóm không viết hoa nên ít "ồn" | Sidebar spruce tối, nhãn nhóm sentence case (`Bán hàng`, `Hàng hóa`, `Công cụ AI`, `Quản trị`), item 38px | Sidebar |
| 2 | https://linear.app/changelog | Danh sách cập nhật dày đặc, phân cấp bằng cỡ chữ thay vì khung | Ít khung, nhiều khoảng trắng, đọc nhanh | Bỏ eyebrow ALL-CAPS phía trên mọi tiêu đề; heading tự mang phân cấp | Toàn bộ |
| 3 | https://attio.com | Ảnh ứng dụng: sidebar có "Quick actions" + tìm kiếm, header "Home" + hành động phải | Hành động thường dùng luôn trong tầm tay | Thanh "quick-actions" ngay cạnh lời chào Dashboard (Thêm thú cưng / Thêm khách / Lập hóa đơn) | Dashboard |
| 4 | https://attio.com | Lời chào "Good morning, Alex" + ô soạn thảo lớn + chip gợi ý | Biến màn hình đầu thành điểm bắt đầu hành động | Composer AI bo lớn, focus-ring cả khối, chip gợi ý gọn | AI Assistant |
| 5 | https://stripe.com (cuộn tới demo bảng) | Bảng khách hàng: hàng ~32px, avatar tròn nhỏ, cột số căn phải, đường kẻ mảnh | Mật độ cao nhưng vẫn dễ quét | Bảng dữ liệu: header sentence case 11.5px, hàng 11px padding, số `tabular-nums`, hover nhẹ | Products, Customers, Invoices, Reports |
| 6 | https://stripe.com | Ô "Get Stripe product recommendations": textarea lớn, bộ đếm ký tự, nút gửi bên trong khung | Tập trung một hành động, thông tin phụ nhỏ | Composer AI: nút Gửi nằm trong khung, meta nhỏ màu faint | AI Assistant |
| 7 | https://docs.stripe.com/dashboard/basics | Breadcrumb + H1 lớn + mô tả 1 dòng; nhãn nhóm sidebar | Wayfinding rõ, tiêu đề mạnh | Breadcrumb nhỏ phía trên H1 24–30px, mô tả ≤ 64ch | Page header |
| 8 | https://www.shopify.com/pos | Thẻ ảnh lớn, đường kẻ mảnh trên tiêu đề, mô tả 2 dòng | Ảnh là nội dung chính | Thẻ thú cưng ảnh 4:3 `object-fit: cover`, zoom nhẹ khi hover, status pill nổi trên ảnh | Pets, Image search |
| 9 | https://www.shopify.com/pos | Phân đoạn "Single store / Multiple stores / On the go" | Lựa chọn song song, trọng số ngang nhau | Bộ lọc POS dạng segmented control (Tất cả / Sản phẩm / Thú cưng) | POS |
| 10 | https://squareup.com/us/en/point-of-sale | Tiêu đề hiển thị lớn, nút pill viền + nút đặc | Phân cấp hành động chính/phụ rõ | Nút primary đặc + secondary viền nhẹ; nút kỳ báo cáo dạng pill | Buttons, Reports |
| 11 | https://squareup.com/us/en/point-of-sale | Ảnh minh họa POS: lưới mặt hàng có ảnh, giỏ hàng bên phải | Mô hình quen thuộc với thu ngân | Giữ lưới mặt hàng + giỏ sticky, thẻ có trạng thái chọn (viền brand + nền nhạt) và phản hồi nhấn `scale(.985)` | POS |
| 12 | https://www.saasui.design | Thư viện màn hình thật (Asana, Amplitude, Cal.com…) | Cho thấy chuẩn "SaaS hoàn thiện": ít đổ bóng, viền mảnh, 1 màu nhấn | Hairline-first: panel viền 1px + shadow 1px, chỉ lớp nổi (menu, dialog, launcher) mới có shadow rõ | Toàn bộ |
| 13 | https://stripe.com | Số liệu lớn kèm nhãn nhỏ, màu trung tính | KPI đọc trong 1 giây | Thẻ KPI: nhãn 13px, giá trị 22–27px font rounded, dòng phụ faint; thẻ có thể bấm dẫn tới module | Dashboard |
| 14 | ui-ux-pro-max (skill cục bộ) | Pre-delivery checklist: SVG icon, contrast 4.5:1, focus visible, reduced-motion, 375/768/1024/1440 | Chuẩn chất lượng tối thiểu | Áp dụng nguyên checklist; **từ chối** gợi ý "Vibrant block-based" + Google Fonts CDN (không hợp app vận hành, vi phạm CSP `'self'`) | QA |

## Điều KHÔNG áp dụng

- Không sao chép bố cục, logo, màu thương hiệu (tím Stripe, đen Linear) hay ảnh của bất kỳ sản phẩm nào.
- Không thêm landing page marketing (ứng dụng nội bộ, không cần).
- Không tải font/CDN ngoài: CSP hiện tại chỉ cho `'self'`; dùng font hệ thống `ui-rounded` / SF Pro Rounded cho tiêu đề.

