# Phase 6.2 — cross-browser report

## Kết quả

| Engine | Kết quả | Scope |
|---|---|---|
| Chromium | PASS | Login, dashboard, customer/pet/product forms, POS/cart, purchasing, reports, assistant, Vision suggestions; axe scans; CSP diagnostics. |
| Firefox | PASS | Cùng representative routes/flows, axe scans và responsive checks. |
| WebKit | PASS có giới hạn | Representative routes, labels, keyboard activation, responsive form/POS/assistant/Vision; axe không chạy do instrumentation ảnh hưởng CSP. |

Tổng: **3/3 engines PASS** (Chromium 6.10s, Firefox 14.80s, WebKit 3.97s); **22 axe scans**, **0 violations**, **73 incomplete nodes**. Kiểm viewport 390px và trang sản phẩm desktop 1440px; kiểm `scrollWidth` để bắt tràn ngang.

## CSP/WebKit warnings

WebKit có phát các sự kiện `style-src-attr` trên `<select>` không có thuộc tính `style`, cùng `style-src-elem` phát sinh trong screenshot instrumentation. Một fixture HTTP tối giản, không chứa app JS/GSAP/inline style, tái hiện cùng thông báo WebKit cho select rỗng dưới strict `style-src 'self'`. Screenshot audit instrumentation tạo nhóm warning riêng. Đây là **browser/test-harness compatibility events**, không phải bằng chứng cho thấy ứng dụng đã ghi inline style.

Đã điều chỉnh `petcare/static/js/motion.js` để Safari/WebKit thoát trước bước GSAP ghi inline style. WebKit ghi 24 empty-select compatibility events và 5 screenshot instrumentation events; Chromium/Firefox ghi 0 harness events. App CSP violation count sau khi loại riêng hai loại harness đã xác minh: **0** cho cả ba engines. CSP policy không được nới lỏng.

Screenshot viewport cuối: [Chromium dashboard](assets/phase62/chromium-dashboard-390.png), [POS/cart](assets/phase62/chromium-pos-390.png), [reports](assets/phase62/chromium-reports-390.png), [Vision suggestions](assets/phase62/chromium-vision-390.png), cùng Firefox/WebKit tương ứng và [desktop products](assets/phase62/chromium-products-1440.png).

## Giới hạn

Đây là kiểm thử headless đại diện, không phải ma trận browser/OS đầy đủ. Không kiểm native zoom 200% hoặc screen reader; WebKit axe chưa chạy. Ảnh trong `docs/assets/phase62/` được tạo từ QA local; xem thêm [kết quả accessibility](PHASE62_FINAL_ACCESSIBILITY.md).
