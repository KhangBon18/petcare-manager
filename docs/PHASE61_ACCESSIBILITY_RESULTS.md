# Phase 6.1 — kết quả UI/accessibility

## Responsive và kiểm tra trực quan

- Chromium scenarios dùng widths 320/390/768/820/1024/1440px trên shared shell, customer/pet profiles, product/inventory, purchasing list/detail và các trang chính tương ứng; tests assert `document.documentElement.scrollWidth === viewport width` và không phát hiện overflow ở các điểm chạy.
- POS mobile kiểm catalog, cart count/total, chọn khách, quantity và anchor; mỗi module không được test ở mọi breakpoint.
- Đã xem ảnh QA dashboard 320px, POS 390px và report 390px: card/hierarchy đọc được, nav cố định, form/report không tràn ngang. Đây là kiểm tra bằng mắt ở các trang cụ thể, không phải usability study.
- Firefox/WebKit login rồi mở customer, pet, product, invoice/POS, purchasing, reports tại 390px: mỗi route trả 200 và không tràn ngang. Workflow sâu chạy Chromium.
- WebKit phát 19 cảnh báo CSP từ chối inline style khi JS hiệu ứng GSAP thử thay transform; ba linked stylesheets vẫn tải và page vẫn hiển thị. Firefox không có console error. WebKit giao dịch sâu chưa chạy.

## Keyboard và axe

- Playwright kiểm Enter trên POS/purchase fill-remaining, Tab/Shift+Tab/focus-visible trên customer pagination/Vision, và focus trả về assistant launcher khi đóng. Đây là các luồng chính, không phải keyboard audit cho mọi control.
- axe-core **4.14.0**: 31 main scans, 0 violations, 36 incomplete occurrences; Vision 5 states, 0 violations và 5 incomplete icon/contrast cases. Không suy luận WCAG pass từ axe.
- Review incomplete:
  - `aria-prohibited-attr` trên `.assistant-catalog`: source đặt `aria-label` trên `div` không có role; axe nói label không được hỗ trợ tốt. Cần xác nhận screen reader; có thể thêm role phù hợp hoặc bỏ label.
  - `color-contrast`: target text trong SVG chart, glyph/icon `aria-hidden`, background không xác định do ảnh/chồng lấp. Chưa có contrast meter/AT để kết luận từng màu.
  - `label-content-name-mismatch` nút đóng assistant: visible `×` khác aria-label chữ; glyph là biểu tượng, nhưng speech-input/screen-reader behavior chưa xác minh.
- Ảnh trực quan cho thấy màu text thường dùng ink/muted trên nền sáng; điều này không thay thế đo contrast cho trạng thái/overlay.

## Chưa được kiểm tra

- **Zoom trình duyệt thật 200%: NOT TESTED.** Một số browser test đặt layout viewport 720px như approximation của desktop 1440px ở 200%; không phải zoom thật.
- **Screen reader: NOT TESTED.** Không chạy VoiceOver/NVDA/JAWS trong môi trường này.
- Contrast ratios từng component, high-contrast/forced-colors, reduced-motion đầy đủ và WCAG 2.2 AA toàn ứng dụng: **NOT TESTED**.

## Kết luận

Không có axe violation và không thấy overflow tại viewport đã quan sát. Có thể demo học thuật nếu không quảng bá WCAG conformance; Phase 6.2 nên chạy screen reader/200% zoom và xác minh incomplete semantic/contrast bằng thiết bị thực.
