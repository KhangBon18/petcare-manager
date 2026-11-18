# PetCare Manager — UI/UX Redesign Audit

> Phạm vi: toàn bộ giao diện Flask/Jinja của PetCare Manager trên nhánh `feature/petcare-ui-ux-redesign` (tách từ `feature/ai-4.0-pet-image-matching` @ `b372b22`). Ảnh BEFORE chụp thật bằng Playwright Chromium trên CSDL QA cô lập `petcare_ai40_demo_test` (74 thú cưng, 22 sản phẩm, 12 khách hàng tổng hợp) ở 1440×900, 834×1112 và 390×844.

## 1. Kiểm kê skill đã cài

| Skill | Vị trí | Mục đích | Chọn? | Lý do |
|---|---|---|---|---|
| `frontend-design` (anthropics/skills) | `.agents/skills/frontend-design/SKILL.md` | Định hướng thẩm mỹ riêng, tránh template, quy tắc chữ & copy | **Chọn** | Dẫn dắt việc chọn hướng "Spruce & Saffron", loại bỏ eyebrow ALL-CAPS, mũi tên "→", cliché cream/terracotta; nguyên tắc "một điểm táo bạo" |
| `web-design-guidelines` (vercel-labs) | `.agents/skills/web-design-guidelines/SKILL.md` | Checklist accessibility, form, focus, loading/error | **Chọn (áp dụng nội dung)** | Skill yêu cầu tải checklist từ GitHub; không tải để tránh truy cập mạng ngoài phạm vi — áp dụng các nguyên tắc tương ứng qua axe-core + kiểm tra focus/overflow tự động |
| `playwright-cli` (project-local) | `.agents/skills/playwright-cli/SKILL.md` | Điều khiển trình duyệt, chụp màn hình | **Chọn (tinh thần)** | Dùng Playwright Python có sẵn trong `.venv` (cùng engine Chromium) qua script tái sử dụng `scripts/ui_capture/` để chụp BEFORE/AFTER lặp lại được |
| `ui-ux-pro-max` (nextlevelbuilder, rev `713eef5`) | `.agents/skills/ui-ux-pro-max/.claude/skills/ui-ux-pro-max/` | Kho dữ liệu màu/chữ/pattern + checklist | **Chọn một phần** | Đã rà soát script (chỉ đọc CSV, không mạng/subprocess) rồi chạy `search.py --design-system`. Áp dụng checklist (SVG icon, contrast 4.5:1, focus, reduced-motion, breakpoint); **bác bỏ** đề xuất "Vibrant & Block-based", landing pattern và Google Fonts CDN (không hợp app vận hành, vi phạm CSP) |
| `book-to-skill` | `.agents/skills/book-to-skill/` | Chuyển sách thành skill | Không chọn | Không liên quan đến redesign |

Không có `.claude/skills/` hay `.codex/skills/` trong repo. Không cài/cập nhật skill mới.

## 2. Top 15 vấn đề UI/UX (xếp theo tác động người dùng)

| # | Vấn đề | Bằng chứng (BEFORE) | Tác động |
|---|---|---|---|
| 1 | Quá nhiều chữ giải thích: 78 nhãn eyebrow ALL-CAPS, mô tả dài dưới mọi tiêu đề, khối "Mẹo nhỏ", 3 bước minh họa | Dashboard, Tìm ảnh, Trợ lý AI | Mất trọng tâm, khó quét |
| 2 | Sidebar phẳng, 8 mục ngang hàng không nhóm, chỉ có nhãn "CỬA HÀNG"; sidebar không kéo hết chiều cao | Mọi trang desktop | Điều hướng chậm, trông chưa hoàn thiện |
| 3 | Dashboard thiếu phân cấp: biểu đồ, gợi ý nhập, doanh thu 7 ngày (trùng biểu đồ), lối tắt, "Mẹo nhỏ" xếp chồng dọc | `02-dashboard-desktop` | Không thấy ngay việc cần làm |
| 4 | Trang Tìm ảnh: 3 đoạn văn dài + khối hướng dẫn điện thoại chiếm 1/3 màn hình trước khi tới vùng tải ảnh | `10-image-search-desktop` | Tăng ma sát cho tác vụ chính |
| 5 | Ảnh thú cưng nhỏ, khung pastel thừa, lưới 3 cột | `08-pets-desktop` | Ảnh — nội dung quan trọng nhất — bị yếu |
| 6 | Bảng dữ liệu tiêu đề lẫn ALL-CAPS và sentence case ("SẢN PHẨM" cạnh "Thao tác", "Số điện thoại") | Sản phẩm, Khách hàng | Thiếu nhất quán |
| 7 | Thẻ KPI viền trên 3px xanh, số liệu nặng 800, không bấm được | Dashboard, Báo cáo | Nặng nề, không dẫn tới chi tiết |
| 8 | Trợ lý AI: header 3 dòng mô tả + 2 badge dài + thanh ngữ cảnh trước khi tới khung chat | `11-assistant-desktop` | Khung chat bị đẩy xuống |
| 9 | Login: minh họa mèo CSS trẻ con, câu chữ nhấn màu một từ, footer chữ hoa | `01-login-desktop` | Ấn tượng đầu "đồ án sinh viên" |
| 10 | Nút và trạng thái thiếu phản hồi nhấn; hover lift ngẫu nhiên trên mọi thẻ | Toàn bộ | Cảm giác kém tinh tế |
| 11 | Select dùng mũi tên mặc định, file input mặc định hệ điều hành | Form thú cưng, thư viện ảnh | Không đồng bộ |
| 12 | Ký tự "⌕" làm icon tìm kiếm, "PRODUCT" chưa dịch ở chi tiết hóa đơn | Toolbar bảng, hóa đơn | Thô, lỗi bản địa hóa |
| 13 | Công thức gợi ý nhập hàng (2 đoạn kỹ thuật) hiện luôn | Dashboard, Sản phẩm | Quá tải thông tin |
| 14 | Status pill bị xuống 3 dòng ở bảng tài khoản | `14-users-desktop` | Lỗi bố cục |
| 15 | Footer "PetCare Manager • Quản lý cửa hàng thú cưng" và ghi chú sidebar lặp lại vô nghĩa | Mọi trang | Nhiễu thị giác |

## 3. Phân loại văn bản (Phase 6)

| Loại | Xử lý | Ví dụ |
|---|---|---|
| A — vận hành | Giữ | Giá, tồn kho, trạng thái, ngày, mã |
| B — validation/an toàn/bảo mật/giới hạn AI | **Giữ nguyên** | Cảnh báo không xác nhận cùng cá thể, ghi chú AI Vision tắt/bật, thông báo phạm vi khách mua, cảnh báo dữ liệu thưa, xác nhận ảnh đúng cá thể |
| C — giải thích hữu ích | Rút gọn / `details.ui-disclosure` | Cách hoạt động ONNX, hướng dẫn điện thoại, công thức gợi ý nhập, mô tả header trợ lý |
| D — trang trí | Xóa | 75 eyebrow, "Mẹo nhỏ", "Đây là tình hình cửa hàng…", footer, sidebar note, 3 bước minh họa, "Doanh thu 7 ngày" trùng lặp (chuyển thành lối tắt) |

