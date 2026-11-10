# Phase 4.1 — Design system

Ngày cập nhật: 2026-11-10

Phạm vi: shell dùng chung, khách hàng và thú cưng. Đây là quy ước nhỏ, bám vào CSS/Jinja hiện có; chưa thay framework hoặc xây design system runtime riêng.

## Hướng thiết kế

Giữ cảm giác cửa hàng thú cưng thân thiện nhưng ưu tiên khả năng đọc và thao tác: xanh rừng làm màu hành động, nền trung tính sáng, bề mặt trắng, trạng thái rõ bằng màu + chữ. Dùng spacing đều, đường viền nhẹ và typography hệ thống để ứng dụng vẫn tải nhanh, same-origin và dễ sửa trong dự án học tập.

## Token và cách dùng

Nguồn token là [`static/css/tokens.css`](../petcare/static/css/tokens.css); component CSS nằm trong [`static/css/app.css`](../petcare/static/css/app.css).

| Vai trò | Token / giá trị hiện tại | Cách dùng |
|---|---|---|
| Brand | `--color-brand` (`#287a62`), `--color-brand-strong` (`#1f624f`) | Primary action, liên kết và active navigation |
| Brand tint | `--color-brand-soft` (`#e8f3ed`) | Active state và nền nhẹ |
| Canvas / surface | `#f5f7f6` / `#fff` | Nền trang / card và form |
| Ink / muted | `#202d2a` / `#58665e` | Nội dung chính / mô tả và metadata |
| Border | `#e2e9e5`, `#edf1ee` | Viền card / phân tách nhẹ |
| Positive | `#326b49`, `#e5f5ea` | Trạng thái hoàn tất |
| Warning | `#80511f`, `#fff2dd` | Cảnh báo cần chú ý |
| Danger | `#9a4c47`, `#fff0ed` | Lỗi, trạng thái nguy hiểm; nút ngừng khách dùng viền đỏ nhạt |
| Focus | `rgba(40, 122, 98, .35)` | Focus-visible trên breadcrumb/link |

- Font: system UI stack (`--font-ui`); không tải font ngoài.
- Spacing có sẵn: 4, 8, 12, 16, 24, 32 px (`--space-1` … `--space-6`).
- Radius có sẵn: 8, 12, 16 px (`--radius-sm` … `--radius-lg`).
- Ưu tiên token semantic trong CSS mới; alias cũ vẫn còn để tránh làm hỏng các trang chưa migrate.
- Không thêm thư viện, CDN hay hiệu ứng mới cho Phase 4.1.

## Layout và điều hướng

- Desktop giữ sidebar/header và vùng nội dung hiện hữu; Phase 4.1 thêm breadcrumb dùng chung ngay dưới shell, trước tiêu đề trang.
- Breadcrumb dùng `nav[aria-label]`, danh sách có thứ tự và `aria-current="page"`; các cấp trước là liên kết. Trang customer/pet detail/edit có đường dẫn quay lại qua cấp cha.
- Mobile tiếp tục dùng thanh điều hướng đáy sẵn có. Không đổi quyền hoặc route của menu.
- Customer list chuyển từ bảng cuộn ngang sang card ở breakpoint `680px`; từ 681px trở lên bảng hiện tại tiếp tục dùng trong vùng scroll của bảng. Danh sách pet giữ component/card hiện có.
- Nội dung dài được phép cuộn theo chiều dọc; kiểm tra ở 320, 390, 768, 820 và 1440 px không tạo document overflow trong các tuyến được chạy.

## Component và trạng thái

- Giữ quy ước button `primary`, `secondary`, `light` và pill trạng thái đang dùng; không đổi hành vi POST/CSRF.
- Form khách hàng và thú cưng vẫn dùng label, validation service và phục hồi giá trị đã nhập. Kiểm tra `weight_kg` ngoài miền dùng native constraint trên trình duyệt; lỗi service vẫn hiển thị theo cơ chế hiện hành.
- Empty/error/success dùng lại các thông báo và flash hiện có. Phase này không thêm spinner tổng quát, toast mới hay modal framework.
- Customer mobile card thể hiện tên, trạng thái, điện thoại, địa chỉ, số hóa đơn, sửa và bật/tắt trạng thái bằng các điều khiển thật.
- Hóa đơn/pet liên quan là liên kết rõ ràng; chỉ xem pet được gán buyer theo dữ liệu hiện hữu.

## Khả năng truy cập

- Dùng heading theo cấu trúc trang, landmark, tên accessible cho nav/section, `aria-current`, label field và liên kết điện thoại dạng `tel:`.
- Focus-visible được nhận diện trên breadcrumb/link mới; form POST vẫn là HTML native, CSRF giữ nguyên.
- Browser smoke có kiểm tra keyboard/accessible-name cơ bản và native validation. Đây chưa phải chứng nhận WCAG: chưa chạy axe, screen reader, kiểm tra contrast định lượng hoặc zoom 200%.

## Những phần chưa được chuẩn hóa trong sprint này

Các trang sản phẩm, hóa đơn, báo cáo và mua hàng vẫn giữ component hiện có. Không diễn giải token file là hệ thống đã áp dụng đầy đủ trên mọi trang; chỉ các component trong phạm vi trên đã được điều chỉnh/kiểm tra.
