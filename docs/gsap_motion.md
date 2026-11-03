# GSAP motion — PetCare Manager

Cập nhật **29/10/2026**, sau mốc `v1.0-demo-ready`. Chỉ nâng cấp giao diện/animation; giữ nghiệp vụ Python, schema, i18n và tag đã đóng băng.

## Skill được cài ở đâu?

Repository hướng dẫn: https://github.com/greensock/gsap-skills, checkout `aed9cfd3277740755f6bfc1155c7aa645403b760`.

- Clone nguồn: `~/.codex/skill-sources/gsap-skills/`.
- Cài cho Codex tại `~/.codex/skills/`: `gsap-core`, `gsap-timeline`, `gsap-performance`, `gsap-utils`, `gsap-scrolltrigger`, `gsap-plugins`, `gsap-react`, `gsap-frameworks`.
- Dùng installer GitHub của skill-installer, chế độ git với ref cố định. Kiểm nội dung SKILL.md đã cài trùng checkout nguồn.
- Bộ hướng dẫn được Codex tự nhận từ lượt chat tiếp theo. Trong lượt triển khai này đã đọc và áp dụng **Core, Timeline, Performance** trực tiếp; skill là hướng dẫn cho agent, không phải server/script phải chạy cùng Flask.

Runtime thật nằm trong `petcare/static/vendor/gsap/`, phiên bản **3.15.0**, tải từ npm bằng `npm pack --ignore-scripts`, xác minh integrity SHA-512. Giữ copyright header và source map; nguồn/checksum/license trong [vendor README](../petcare/static/vendor/gsap/README.md). GSAP runtime có standard license riêng; không nhầm với MIT của repo skill. Flask chạy trực tiếp, không cần npm install/build hoặc CDN khi demo offline.

## Những thay đổi nhìn thấy

| Khu vực | Hiệu ứng / tinh chỉnh |
|---|---|
| Login | Copy, minh họa và thẻ đăng nhập vào theo timeline nhẹ |
| Dashboard | Heading → stat cards → panel/biểu đồ; stagger ngắn, giữ nguyên số tiền |
| Biểu đồ | Cột SVG tăng từ đáy bằng scaleY; thêm grid mảnh, không sửa height/data/labels |
| POS | Danh mục mới vào nhẹ sau lookup; ảnh dòng hàng và tổng phản hồi khi chọn hàng; modal vào nhẹ, Esc/focus theo luồng cũ |
| Trợ lý | Panel, tin nhắn và card hiện nhẹ; Enter/khóa gửi và focus giữ nguyên |
| Toast / cards | Toast có GSAP khi sẵn sàng, CSS fallback khi thiếu thư viện; tăng độ rõ của selected/focus/nav, thêm chiều sâu card |

## Cấu trúc và nguyên tắc

- `petcare/static/js/motion.js`: lớp tùy chọn `window.PetCare.motion` với `reveal(nodes)` và `feedback(nodes)`; các hook trong app/assistant/POS chỉ gọi API nếu có.
- `petcare/static/css/motion.css`: phần polish riêng, dùng màu `#287A62`, không nhân bản stylesheet hay breakpoint chính.
- `base.html`: CSS + GSAP local → motion.js → script hiện có, đều dùng defer. Không nới CSP `script-src 'self'; style-src 'self'`, không thêm inline script/eval.
- `business_chart.html`: grid SVG chỉ trình bày; đường tính doanh thu/snapshot/export không đổi.
- Animate transform/opacity, không tween tiền, text, width/height/layout. Không thêm scroll hijacking, pinning, loop vô hạn hoặc đếm số doanh thu giả.
- Nội dung HTML mặc định luôn nhìn thấy; entrance chỉ giảm opacity đến 0,72 trong thời gian ngắn, không đợi animation mới cho thao tác. Giữ server-validation/focus đứng yên khi có error summary.
- `gsap.matchMedia()` chỉ bật trên screen và `prefers-reduced-motion: no-preference`; khi đổi preference/print sẽ cleanup. Reduced motion vẫn dùng giao diện đầy đủ.
- Active tweens có chủ sở hữu; phản hồi liên tục revert tween trước, hoàn tất trả lại style gốc. Timeline entrance dùng `context.ignore()` để tránh double-revert SVG; tự lưu/khôi phục style/transform/data-svg-origin của cột.
- Pagehide, BFCache pageshow, background và before/after print có lifecycle; không replay entrance khi quay lại/in xong. Giới hạn 12 target mỗi reveal, tối đa 60 cột và stagger có tổng thời lượng giới hạn. Không tuyên bố FPS khi chưa benchmark thiết bị yếu.

## Kiểm chứng 29/10/2026

- **285/285 Python tests**: 171 unit, 57 web, 57 MySQL integration, không fail/error/skip; **35,962 giây**. MySQL dùng database `_test` mới, media riêng; không reset hoặc chạy test vào database dev.
- **26/26 JavaScript tests**: 19 regression cũ + 7 motion tests về thiếu GSAP, reduced motion, không tween dữ liệu, focus validation, phản hồi liên tục/hidden nodes, print/BFCache và cleanup khi đổi preference/background.
- 2 web tests mới kiểm thứ tự defer, asset offline/pinned checksum/license header và giữ CSP nghiêm ngặt.
- Chrome thực tế: dashboard/AI/POS; 2 lần chọn FOOD-001 → 1 dòng số lượng 2, tổng 200.000 VND; modal focus tên, Esc trả nút mở và giữ giỏ. Không tạo khách/hóa đơn hoặc thanh toán trên dev trong lượt này.
- Trợ lý local “Tìm mèo lông trắng dưới 3 triệu” trả card Mây/Mực/Sữa; số liệu/URL hồ sơ vẫn do MySQL/backend quyết định.
- SVG sau animation sạch style/transform/data-svg-origin, không lỗi CSP/JS trong console. Màn hình báo cáo 390×844 không tràn ngang, nút export/in còn thao tác được; viewport đã reset.
- Reduced motion và lifecycle in kiểm bằng regression JavaScript; không đổi preference hệ điều hành và không xuất PDF mới trong lượt này. Không thực hiện audit WCAG hoặc benchmark FPS đầy đủ.
- JS/Jinja syntax, diff whitespace, i18n byte-for-byte và tag demo giữ nguyên. Dev server đã reload template mới ở **http://127.0.0.1:5055**, readiness 200.

Bộ skill chỉ hướng dẫn cách viết motion. Các plugin React/ScrollTrigger đã cài cho những công việc sau, nhưng không đưa vào bundle này vì ứng dụng hiện dùng Flask + vanilla JS.
