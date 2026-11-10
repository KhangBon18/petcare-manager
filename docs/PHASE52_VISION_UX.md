# Phase 5.2 — UX và browser evidence

## Hành vi người dùng

1. Admin chọn JPEG/PNG/WebP trong form pet hiện có.
2. Preview xuất hiện; ảnh quá lớn hoặc không đọc được có phản hồi inline.
3. Panel báo đang phân tích, sau đó hiển thị gợi ý/provider status hoặc local color estimate.
4. Người dùng có thể retry, dừng chờ hoặc bỏ qua.
5. Nút “Điền vào trường đang trống” điền field trống; field đã nhập giữ nguyên. Người dùng kiểm tra và submit form theo workflow cũ.

Không thêm trang, route ghi riêng hoặc thao tác tự lưu. Local color estimate được ghi rõ là có thể gồm nền; local mode không suy đoán loài/mắt.

## Kiểm thử giao diện chạy thật

Chromium đăng nhập admin, chọn fixture synthetic, thấy loading và structured result, dùng Enter để apply, xác nhận field đã nhập không bị ghi đè. Case invalid/corrupt/empty/oversized, extension/MIME mismatch, provider 503/timeout/malformed/ambiguous, retry, staff 403 và concurrency chạy qua Flask thật.

Viewport đo: 320, 390, 768, 820, 1024 và 1440 px; document scrollWidth khớp width tại từng kích thước. Browser runner bắt pageerror, failed requests và HTTP errors; 15/15 tests pass. Ảnh: [390 px](assets/phase52/vision-suggestions-390.png), [1440 px](assets/phase52/vision-suggestions-1440.png).

## Accessibility đã kiểm và giới hạn

- Input file có label; status dùng role=status/aria-live polite; panel giữ aria-busy.
- Apply dùng được bằng keyboard Enter; form values không bị ghi đè.
- Loading, error, uncertain/local, success, retry và cancel-wait đều có feedback.
- Chưa chạy axe riêng, screen reader, high contrast, browser zoom 200%, Safari/Firefox hoặc test thiết bị cảm ứng. Không tuyên bố WCAG compliance.

Cancel chỉ abort fetch/chờ phía trình duyệt; request đã tới Flask/provider có thể vẫn hoàn tất. UI nói rõ dừng chờ, không khẳng định đã hủy job phía server.

## Ghi chú visual audit

Form giữ hierarchy, spacing và component hiện hành ở desktop/mobile. Màn hình mobile dài nên bottom navigation cố định nằm trên nội dung khi full-page screenshot; đây là behavior shell hiện có và trang vẫn cuộn được. Evidence chụp sau khi đóng toast tạm, không chứa dữ liệu khách hàng hoặc ảnh thật.
