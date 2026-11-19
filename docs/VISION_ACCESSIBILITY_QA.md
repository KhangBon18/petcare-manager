# Vision Accessibility and Browser QA

Ngày: 2026-11-10. Scope là Vision form và các trạng thái đã chạy trong Chromium; không phải WCAG audit toàn sản phẩm.

## Kiểm tra thực tế

- Chạy `scripts/browser_smoke/run_smoke.py` trên Flask thật và MySQL disposable: **16/16 PASS**, 0 skip. Suite kiểm cả trang Vision và các module browser smoke khác; log summary ở `/tmp/petcare-phase53a-qa/artifacts/results.json`.
- Vision workflow: admin chọn ảnh fixture synthetic; panel loading/suggestions/error/recovery; field apply chỉ vào ô trống; dismissal không thay đổi form fields; staff bị chặn; keyboard Tab focus có thứ tự và focus-visible.
- Axe-core 4.14.0 được nạp trong trang bằng asset cục bộ, không đổi CSP. Scan năm states (empty form, suggestions, dismissed, provider error, recovered): mỗi state **0 axe violations**. Máy đọc kết quả đã lưu tại [`accessibility-axe.json`](assets/vision-evaluation/accessibility-axe.json).
- Axe báo một `incomplete` check cho contrast trên glyph mũi tên trang trí trong nút. Đây không phải confirmed violation; công cụ không kết luận độ tương phản cho non-text-only glyph. Cần review thủ công nếu glyph trở thành icon có nghĩa.
- Test viewport hẹp 720 px như surrogate cho nội dung 200%-equivalent và mobile 390 px; không tràn ngang trong assertions. Responsive browser suite trước đó có 320–1440 px.
- Axe scan ban đầu phát hiện text tương phản thấp do entrance animation giảm opacity; đã bỏ animation opacity, giữ chuyển động vị trí và test đảm bảo animation không làm mờ text.
- Nút “Bỏ qua gợi ý” có accessible name, hoạt động keyboard, đóng panel, giữ values và trả focus về input ảnh. Mũi tên trang trí đặt `aria-hidden`.

## Chưa xác minh

- Screen reader thực tế (VoiceOver/NVDA), speech announcement timing, high contrast, prefers-reduced-motion trên hệ điều hành, Safari/Firefox/WebKit, touchscreen.
- Browser zoom thật ở 200% (720 px là viewport surrogate, không phải thay đổi browser zoom), 400%, mọi trang và mọi role.
- Contrast thủ công với toàn bộ dynamic/theme states và WCAG conformance cấp ứng dụng.
- CI hosted chạy axe workflow; chỉ local CI-equivalent được cài và thực thi.

Kết luận: **PASS theo keyboard/axe/viewport scope ở trên; accessibility tổng thể PARTIAL.** Không tuyên bố WCAG compliance.
