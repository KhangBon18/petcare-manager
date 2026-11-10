# Sprint 4.3 — Purchasing UX

## Workflow và nguyên tắc

Routes purchasing hiện hành vẫn là nguồn sự thật. Sprint thay presentation và thêm tiện ích điền input; không thêm trạng thái đơn hay business rule.

List mobile trình bày PO id/ngày, supplier, lượng received/ordered, lượng remaining cho đơn đang hoạt động, item count, giá trị và detail link. Detail mobile trình bày từng sản phẩm với ordered, received, remaining, current stock, unit cost và line total; desktop tiếp tục dùng table.

Nút **Điền số còn thiếu** đặt từng input vào lượng còn lại còn nhận được; input đã disable không đổi. Feedback thông báo tổng. Nút không gửi request; người dùng vẫn xác nhận bằng **Xác nhận nhận hàng** và server tiếp tục kiểm tra quantity/state/permission.

## Browser evidence

Trước sprint: [list 320](assets/phase43/before/purchasing-list-320.png) tràn ngang, theo DOM width measurement; [detail 320](assets/phase43/before/purchasing-detail-320.png). Sau: [list mobile](assets/phase43/after/purchasing-list-320.png), [list desktop](assets/phase43/after/purchasing-list-1440.png), [detail ordered mobile](assets/phase43/after/purchasing-detail-ordered-320.png), [detail desktop](assets/phase43/after/purchasing-detail-ordered-1440.png), [partial](assets/phase43/after/purchasing-detail-partial-320.png), [received mobile](assets/phase43/after/purchasing-detail-received-320.png), [received desktop](assets/phase43/after/purchasing-detail-received-1440.png).

Browser mở list/detail tại 320/390/768/820/1024/1440 px, assert document width bằng viewport và xác nhận đúng table/card breakpoint. Workflow thật tạo PO, xác nhận tồn không đổi khi mới đặt, nhận một phần, dùng keyboard Enter trên fill-remaining, nhận hết, so sánh status/received qty/stock/2 movements với MySQL QA, rồi cancel PO khác và xác nhận stock không đổi.

Integration tests hiện hành còn cover invalid quantity/transition, over-receive, replay key, transaction rollback và consistency. Fixture chỉ dùng schema _test, dữ liệu UUID cleanup. Concurrent receive nhiều admin chưa stress-test.

## Accessibility và rủi ro

Axe trước sửa thấy label progress contrast 4.16:1 và header cột action rỗng. CSS đổi #708078 → #56675e; cột được đặt nhãn THAO TÁC. Scan sau sửa không có violation ở sampled states. Keyboard Enter được xác minh; screen reader, real zoom 200% và toàn bộ form validation matrix chưa chạy.

Review các kết quả axe incomplete cũng phát hiện table-scroll region có tên chung, mất ngữ cảnh danh sách. Wrapper nay có role region; shared JS giữ tên hiện có và ghép hint phím cuộn. Browser assert region name có “Danh sách đơn nhập”. Màu #56675e trên trắng có contrast 6.00:1 theo WCAG relative-luminance calculation.

Rủi ro thấp-vừa: thay template/CSS/JS client-side; persistence/state/transactions không thay đổi.
