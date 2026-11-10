# Phase 5.1 — UX trợ lý bán chạy

## Điều chỉnh nhỏ

- Thêm suggestion “Bán chạy tuần này” cạnh các câu hỏi hiện có; English UI hiển thị “Top products this week”.
- Trợ lý giữ loading state và hiện reply cùng nhãn nguồn “Báo cáo bán hàng · dữ liệu MySQL của cửa hàng hiện tại”.
- Card hiển thị tên/mã sản phẩm, số lượng bán ròng, doanh thu và link mở hồ sơ. Nếu không có rows, hiện thông báo rõ ràng.
- Không thêm widget mới hoặc tự thực hiện thao tác ghi. Field giá trị được dựng bằng DOM/text, không render HTML từ data.

## Browser evidence

Playwright đã đăng nhập, mở panel, chọn suggestion, gửi request tới Flask thật và đối chiếu card với report service trên MySQL QA ở viewport 390×844. Bài test độc lập PASS 1/1; `/readyz=200`. Không có Axe scan cho state mới; browser suite đầy đủ còn lỗi môi trường như mô tả trong [evaluation](PHASE51_AI_EVALUATION.md).

Ảnh chụp test: [assistant insight trên mobile](assets/phase51/assistant-top-products-mobile.png). Ảnh là QA dashboard hiện có cùng assistant panel; không phải redesign hoặc kiểm thử mọi breakpoint.

## Accessibility và responsive còn thiếu

- Đã giữ nút suggestion là button, landmark group có `aria-label`, response nối vào `aria-live="polite"`; browser smoke có accessibility check tên control/landmark.
- JS unit kiểm text an toàn, link allowlist, source/metrics. Test Playwright kiểm 390 px và không tràn ngang.
- Chưa kiểm bàn phím đến từng card/link, screen reader announcement, contrast/Axe ở state mới, tablet riêng, zoom 200%, Firefox/Safari hoặc thiết bị thật.
