# Phase 6.2 — kết quả accessibility

## Đã kiểm chứng

- Axe: **22 scans** trên Chromium và Firefox ở dashboard, form, POS/cart, reports, assistant và Vision suggestion states; **0 violations**. Có **73 incomplete nodes** cần đánh giá thủ công; incomplete không đồng nghĩa pass.
- Final screenshots dùng viewport captures (390px và 1440px) để kiểm tra nav cố định, mobile cart, report controls và Vision suggestion panel; xem [visual evidence](assets/phase62/chromium-dashboard-390.png).
- Cross-browser runner kiểm form control accessible names, main landmark, keyboard activation của Vision apply, responsive widths 390/1440 px, assistant controls, POS cart interactions và form state preservation.
- Python/Playwright acceptance baseline trước Phase 6.2 đã có keyboard/regression checks cho dialog, lookup, validation, POS, Vision state và worker progress; Phase 6.2 JS suite là 41/41.
- Nút đóng assistant có accessible label; assistant insight cards được nhóm bằng `role="group"`.

## Giới hạn rõ ràng

- Axe không phải chứng nhận WCAG. 73 incomplete results chưa được giải quyết như audit thủ công.
- **Browser zoom 200%: NOT TESTED.** CUA có thể mở sign-in page nhưng không có browser chrome zoom control; app shortcut không đổi mức zoom. Chrome app attach thấy profile/tab cá nhân nên dừng trước khi tương tác thêm.
- **VoiceOver / screen reader: NOT TESTED.** Không có phiên Safari/VoiceOver độc lập an toàn đã xác nhận trong môi trường này.
- WebKit không chạy axe vì axe-core thêm inline style ảnh hưởng phép đo CSP. WebKit vẫn chạy luồng cấu trúc, form labels, keyboard và viewport.
- Contrast và toàn bộ WCAG success criteria chưa được đo thủ công.

## Kết luận

Accessibility evidence: **PASS theo automated scope; PARTIAL tổng thể**. Không tuyên bố tuân thủ WCAG đầy đủ. Bước kế tiếp là kiểm zoom 200%, VoiceOver/NVDA thực, focus order, contrast và các axe incomplete trên browser session dành riêng cho QA.
