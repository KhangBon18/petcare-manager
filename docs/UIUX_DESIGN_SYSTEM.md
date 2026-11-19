# PetCare Manager — Design System v2 "Spruce & Saffron"

Tệp nguồn: [tokens.css](../petcare/static/css/tokens.css) (token) và [ui.css](../petcare/static/css/ui.css) (component). Thứ tự nạp: `tokens.css → app.css → motion.css → ui.css`. `app.css` giữ cơ chế bố cục và component nghiệp vụ cũ; `ui.css` định nghĩa ngôn ngữ thị giác dùng chung.

## 1. Hướng nghệ thuật

| Hướng | Nhận diện | Bảng màu | Ưu | Rủi ro | Kết luận |
|---|---|---|---|---|---|
| A. Premium Minimal SaaS | Trắng/xám, 1 màu brand, rất ít khung | Trắng, xám lạnh, xanh | Gọn, an toàn | Vô danh, dễ giống template | Không chọn riêng |
| B. Warm Premium Petcare | Ấm, ảnh thú cưng, góc bo mềm | Kem + đất nung | Gần chủ đề | Dễ rơi vào cliché "cream + terracotta" (skill `frontend-design` cảnh báo), trẻ con | Lấy *ảnh thật + chữ rounded* |
| C. Modern Operational Dashboard | Sidebar tối, bảng dày, số liệu rõ | Tối + trung tính | Hiệu quả cho thu ngân/quản lý | Lạnh, nặng nếu lạm dụng | Lấy *mật độ + sidebar tối* |

**Chọn: lai B + C → "Spruce & Saffron".** Tiêu chí: (1) phù hợp người dùng vận hành nhiều giờ/ngày, (2) có một điểm nhận diện riêng, (3) tương thích CSP/không CDN, (4) không phá bố cục/selector hiện có, (5) đạt WCAG AA.

- **Điểm táo bạo duy nhất:** sidebar màu spruce đậm + thẻ thương hiệu hình "thẻ tên vòng cổ" màu saffron (bo `11 11 11 3px`). Saffron cũng đánh dấu mục đang mở (vạch 3px) — không dùng ở nơi khác ngoài icon trợ lý.
- **Mọi thứ còn lại im lặng:** nền xám-lá `#f4f6f4`, bề mặt trắng, viền 1px, gần như không đổ bóng.
- **Ảnh thú cưng là nội dung chính:** thẻ ảnh 4:3 phủ kín, trang đăng nhập dùng mosaic ảnh tổng hợp của dự án.

## 2. Token

### Màu
| Token | Giá trị | Dùng cho |
|---|---|---|
| `--color-brand` | `#1d6a53` | Nút chính, liên kết, trạng thái chọn |
| `--color-brand-strong` | `#164a3b` | Hover nút chính |
| `--color-brand-soft` / `--color-brand-faint` | `#e5f0ea` / `#f1f7f3` | Nền icon, chip, hover |
| `--color-accent` | `#eeb04a` | Brand mark, vạch nav đang mở, icon AI |
| `--nav-bg` | `#11291f` | Sidebar desktop |
| `--color-canvas` / `--color-surface` | `#f4f6f4` / `#fff` | Nền trang / bề mặt |
| `--color-ink` / `--color-ink-strong` | `#16201c` / `#34463f` | Chữ chính / nhãn |
| `--color-muted` / `--color-faint` | `#5b6863` / `#87938d` | Chữ phụ / metadata |
| `--color-border` / `-strong` / `-subtle` | `#e2e7e4` / `#cfd7d3` / `#edf1ee` | Viền panel / input / phân tách |
| Semantic | positive `#1f6b47`, warning `#8a5a12`, danger `#a23f35`, info `#2f5a83` (+ bản `-soft`) | Trạng thái |

### Chữ
- `--font-ui`: font hệ thống (SF Pro Text / Segoe UI Variable / Roboto).
- `--font-display`: `ui-rounded` (SF Pro Rounded) → Nunito → Segoe UI Variable Display. Dùng cho H1–H3, số KPI, tổng tiền — tạo cá tính "thân thiện nhưng trưởng thành" mà không tải font ngoài.
- Thang: 11.5 / 12.5 / 14 / 16 / 19 / 24 / 30px. Trọng số: 400 / 550 / 620 / 700. Số liệu: `tabular-nums`.
- Không ALL-CAPS cho nhãn; tiêu đề cột bảng tự chuyển sentence case (`thead th` lowercase + `::first-letter` uppercase, đơn vị tiền tệ giữ nguyên qua `.th-unit`).

### Khoảng cách, hình khối, chiều cao
- Lưới 4px: `--space-1..8` = 4, 8, 12, 16, 24, 32, 40, 56.
- Bo góc: `xs 6` (tag), `sm 8` (control, nút), `md 10` (thẻ con), `lg 14` (panel), `pill`.
- Control: `34` (small) / `40` (mặc định) / `46` (login). Icon: 16 / 18 / 20.
- Sidebar 236px, topbar 60px (sticky, nền mờ `backdrop-filter`).

### Bóng & viền
- `--shadow-xs` cho panel/thẻ (gần như phẳng), `--shadow-sm` khi hover, `--shadow-float` chỉ cho menu, dialog, launcher, panel trợ lý.

### Chuyển động
- `--motion-fast 120ms`, `--motion-standard 180ms`, `--motion-slow 260ms`; easing `--ease-standard`, `--ease-out`.
- Breakpoint: mobile ≤ 680, tablet 681–980, desktop ≥ 981, wide ≥ 1280.

## 3. Component primitives

| Primitive | Class | Ghi chú |
|---|---|---|
| Nút chính / phụ / nhẹ / nguy hiểm | `.button-primary`, `.button-secondary`, `.button-light`, `.button-danger-outline` | 40px, phản hồi nhấn `translateY(1px)` |
| Nút nhỏ / icon | `.button-small`, `.icon-button` | |
| Liên kết văn bản / hành động bảng | `.text-link`, `.table-action`, `.danger-link` | Hover có nền nhạt |
| Input / Select / Textarea / File | `input`, `select`, `textarea`, `::file-selector-button` | Select dùng chevron SVG nội tuyến (data URI, hợp CSP) |
| Search field / Filter toolbar | `.search-form`, `.table-toolbar` | Icon SVG thay ký tự `⌕` |
| Tabs / segmented | `.pos-filters`, `.ai-scope-switcher`, `.business-chart-controls` | `aria-pressed` / `aria-current` giữ nguyên |
| Dropdown | `.account-menu-panel`, `.mobile-admin-menu nav` | Animation `ui-pop` |
| Modal | `.quick-customer-dialog` (`<dialog>`) | Backdrop spruce 42% |
| Toast / Flash | `.toast`, `.flash-*` | |
| Card / Panel | `.panel`, `.stat-card`, `.pet-card`, `.quick-card` | Hairline-first |
| Data table | `table`, `th`, `td` | Mật độ kiểu Stripe |
| Status | `.status-pill` (chấm màu), `.category-tag`, `.stock-number`, `.count-pill` | Không xuống dòng |
| Empty / Loading | `.empty-state`, `.table-empty`, `.dashboard-empty`, `.ui-skeleton` | |
| Pagination | `.pagination` | |
| Disclosure (mới) | `details.ui-disclosure > summary + .ui-disclosure-body` | Mẫu "xem thêm" thống nhất cho nội dung C |
| Note (mới) | `.ui-note` | Ghi chú bảo mật/giới hạn gọn, không lấn nội dung |
| Nav item / Sidebar section | `.nav-link`, `.nav-group-label`, `.side-caption` | Nhãn nhóm `aria-hidden`, chỉ hiện ở desktop |

## 4. Quy tắc nội dung (Phase 6)

- **A** (thông tin vận hành) và **B** (validation/an toàn/bảo mật/giới hạn AI): giữ nguyên.
- **C** (giải thích hữu ích): rút gọn hoặc đưa vào `ui-disclosure` (vd. công thức gợi ý nhập hàng, cách hoạt động của tìm ảnh, hướng dẫn camera điện thoại).
- **D** (trang trí): xóa (75 nhãn eyebrow ALL-CAPS, sidebar note, footer, thẻ "Mẹo nhỏ", 3 bước minh họa tìm ảnh, mô tả dài ở header).
- Không thay chữ cần thiết bằng icon mơ hồ; nhãn mới đều có bản dịch EN trong `petcare/i18n.py`.

## 5. Chuyển động & khả năng tiếp cận

- Chỉ một chuyển động vào trang (`ui-rise` cho tiêu đề), còn lại là phản hồi hành động: hover, nhấn, mở menu/dialog/disclosure, zoom ảnh nhẹ.
- `prefers-reduced-motion: reduce` tắt toàn bộ animation/transform trang trí.
- Focus luôn là viền 2px brand (saffron trên sidebar tối); mục tiêu chạm ≥ 38px desktop, ≥ 44px mobile.

