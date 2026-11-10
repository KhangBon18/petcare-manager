# Phase 4.1 — Nghiên cứu tham khảo sản phẩm

Ngày: 2026-11-10. Các nguồn dưới đây là trang trợ giúp/tài liệu chính thức có thể truy cập công khai. Đã xem nội dung workflow và bố cục được mô tả trong tài liệu; không có phiên đăng nhập dùng thử để quan sát trực tiếp toàn bộ giao diện quản trị. Vì vậy các nhận xét không khẳng định đã kiểm tra màn hình riêng tư hoặc hành vi không được tài liệu công khai mô tả.

## Tham khảo

| Sản phẩm | Nguồn đã xem | Pattern hữu ích | Giới hạn và áp dụng cho Petcare Manager |
|---|---|---|---|
| MoeGo | [Tạo lịch grooming](https://help.moego.pet/en/articles/14008185-grooming-appointment-create-new), [tạo hồ sơ client](https://help.moego.pet/en/articles/14133607-how-to-create-a-client-profile) | Có nhiều điểm bắt đầu cho workflow; profile client nối đến pet; thêm client/pet nhanh mà vẫn có đường dẫn mở form đầy đủ. | Tài liệu mô tả sản phẩm grooming có lịch, dịch vụ và nhân viên. Petcare Manager hiện là retail, nên chỉ dùng pattern điều hướng liên kết record; không thêm appointment/service.
| Gingr | [Customer Portal overview](https://support.gingrapp.com/hc/en-us/articles/28303758802189-Customer-Portal-Feature-Overview) | Hồ sơ người và pet cùng lịch sử dịch vụ/giao dịch giúp khách tự tra cứu và cập nhật; liên hệ và pet được xem như record liên quan. | Đây là tài liệu portal phía khách hàng, không phải ảnh/phiên giao diện admin. Chỉ rút ra cách làm rõ liên kết customer↔pet và lịch sử; không thêm portal, hồ sơ y tế hoặc reservation.
| Shopify | [Customer segmentation](https://help.shopify.com/en/manual/customers/customer-segmentation), [tham chiếu filter](https://help.shopify.com/en/manual/customers/customer-segmentation/reference-guide/shopify-segments) | Danh sách customer dùng filter có ngữ nghĩa rõ; segment có thể dựa trên lịch sử mua hàng và cập nhật theo điều kiện. | Phù hợp định hướng retail nhưng vượt dữ liệu/filter hiện tại. Sprint này giữ search + trạng thái sẵn có, chưa tạo segment, tag hay saved views.
| HubSpot | [View and filter records](https://knowledge.hubspot.com/records/view-and-filter-records), [bố cục record](https://knowledge.hubspot.com/records/work-with-records?tab=tab-crm), [associations](https://knowledge.hubspot.com/records/associate-records) | Index/detail là hai cấp thông tin; record detail chia nhóm dữ liệu và làm nổi record liên quan; bảng có thể mở rộng liên kết. | CRM tổng quát có mức tùy biến và timeline lớn. Áp dụng cấu trúc danh sách → profile và section pet đã mua, không mang toàn bộ CRM timeline/automation vào dự án.

## 3C: Copy — Customize — Create

### Copy

- Dùng pattern quen thuộc: danh sách tìm kiếm → hồ sơ chi tiết → sửa hồ sơ.
- Đặt đường dẫn quay lại trong breadcrumb thay vì để người dùng dò menu.
- Cho liên kết record liên quan xuất hiện ngay trong profile; trên màn hình hẹp dùng card thay cho bảng nhiều cột.
- Giữ search/filter gần danh sách và đưa CTA chính lên đầu workflow.

### Customize

- Mô hình customer–pet–buyer đã có trong database và luồng hóa đơn; UI chỉ đọc liên kết buyer sẵn có. Pet trở thành “đã mua” khi invoice được thanh toán theo business rule hiện hành.
- Giữ Flask + Jinja + CSS + vanilla JS và POST/CSRF/flash hiện tại. Không thay route, role, giá trị tiền, trạng thái giao dịch hoặc dữ liệu mà client được quyền quyết định.
- Nội dung và nhãn song ngữ tiếp tục qua `t()`/`i18n.py`.
- Không đưa appointment, grooming, vaccine, hồ sơ lâm sàng hay các loại dữ liệu mới vào phạm vi.

### Create

- Định hướng riêng của ứng dụng: nền xám xanh sáng, surface trắng, xanh lá dịu, hierarchy chữ gọn và card customer ưu tiên thao tác trên điện thoại.
- Hồ sơ khách hàng có section “Thú cưng đã mua” dẫn thẳng đến pet; hồ sơ pet có liên kết ngược đến buyer.
- Breadcrumbs và card list là điều chỉnh nhỏ, có thể kiểm tra bằng test dễ hiểu, không cần component framework mới.

## Kết luận phạm vi

Các pattern đã chọn hỗ trợ tra cứu record và đi qua quan hệ customer/pet trong retail flow hiện có. Tài liệu đối thủ xác nhận các pattern nói trên; không phải đánh giá chất lượng sản phẩm hoặc benchmark trực tiếp các phiên bản trả phí. Ảnh “before/after” của Petcare Manager được lưu trong thư mục QA local và mô tả tại [PHASE4_VISUAL_QA.md](PHASE4_VISUAL_QA.md).
