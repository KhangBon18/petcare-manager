# Phase 4 — Kế hoạch tiếp theo sau Sprint 4.1

Ngày: 2026-11-10. Sprint 4.1 đã hoàn thành lát cắt customer/pet và navigation cues dùng chung. Không coi đây là tuyên bố ứng dụng đã production-ready; database development vẫn có readiness 503 theo baseline, còn visual accessibility và provider thật chưa xác minh.

## Thứ tự đề xuất

| Ưu tiên | Nhóm | Hạng mục tiếp theo | Tiêu chí hoàn tất | Rủi ro hồi quy |
|---|---|---|---|---|
| P1 | Fix defects hiện hữu | Không có defect P0/P1 mới được xác nhận trong các route vừa chạy. Tiếp tục giữ mọi form/server validation/tenant scoping và xử lý regression browser nếu xuất hiện từ integration. | Full suite + browser smoke xanh sau mỗi thay đổi; không đổi response/permission ngoài chủ đích. | Cao nếu sửa service/payment; thấp nếu chỉ CSS |
| P2 | UX và khả năng truy cập | Chạy axe hoặc công cụ tương đương trên dashboard/customer/pet; review bằng keyboard và screen reader; kiểm contrast/zoom 200%, empty/error state và mobile nav thật. | Issue list theo WCAG criterion, screenshot/evidence, mọi form control/link có accessible name/focus. | Thấp đến vừa |
| P2 | UX customer/pet | Kiểm tra khách có >12 pet liên quan, danh sách rất dài, filter/search/page state; rà soát deactivation/reactivation trên mobile. Nếu người dùng cần duyệt toàn bộ relation, thiết kế pagination rõ thay cho chỉ link về pet list. | Browser MySQL test với >12 relation; link/summary đúng; không làm tăng query không giới hạn. | Vừa, có DB/query |
| P2 | Stabilize kiến trúc | Hoàn thiện CI hosted matrix/baseline, chuẩn hóa test artifact retention, xác minh lockfile install từ môi trường sạch; xem xét chỉ refactor CSS token khi có kiểm kê toàn trang. Không refactor app factory/routes trong sprint UI nếu không có defect cụ thể. | GitHub Actions xanh, `pip check`, pip-audit và suite có kết quả lưu lại. | Vừa |
| P2 | Hoàn thiện product flows | Ưu tiên browser CRUD cho trạng thái customer, pet image/active và role staff/admin; mở rộng tablet/form validation nếu có evidence; tiếp tục giữ retail scope. | Flow thật trên disposable MySQL, test valid/invalid/empty, transaction và permission. | Vừa đến cao |
| P3 | AI | Nếu tiếp tục pet image suggestions/local assistant, lập bộ ảnh synthetic có consent, đo độ ổn định/precision, latency, cost và fallback trước khi sửa giao diện/provider. | Eval được lặp, không gửi dữ liệu thật khi chưa có approval, graceful provider-offline test. | Vừa; có privacy/cost |
| P3 | Tính năng tùy chọn | Chỉ sau nghiên cứu người dùng mới xem xét saved customer views, segmentation hoặc portal. Appointment, grooming và hồ sơ y tế nằm ngoài scope hiện tại. | Có yêu cầu người dùng + scope chốt + API/data impact review trước build. | Cao nếu thêm domain mới |

## Phân loại backlog rõ ràng

1. **Sửa defect:** tiếp tục từ issue có reproduction; không có finding sản phẩm P0/P1 xác nhận trong tuyến UI đã test. Mobile customer table clipping là vấn đề usability được xử lý bằng card view.
2. **Hoàn thiện chức năng đang dang dở:** chưa phát hiện phần dang dở mới trong customer/pet flow chạy; ưu tiên đánh giá đầy đủ related-pet browsing và các trạng thái customer/pet theo role.
3. **Refactor/ổn định:** xác minh hosted CI, sạch-install và đồng bộ CSS tokens có chọn lọc. Tránh thay framework hoặc chuẩn hóa mọi trang trong một lần.
4. **Frontend/UX:** accessibility audit, test detail/form ở nhiều breakpoints trước/sau, focus, empty/error/success và navigation trên mobile.
5. **AI:** eval riêng cho tính năng có sẵn; test offline, quota/cost, privacy, false suggestions và human confirmation. Phase 4.1 không thay đổi AI.
6. **Tính năng tùy chọn:** saved filters/portal chỉ khi có scope được phê duyệt; không suy diễn từ sản phẩm tham khảo.

## Cổng an toàn và giới hạn hiện tại

- Giữ mọi thay đổi có sẵn trong working tree; trước sprint này đã có nhiều file modified/untracked. Không stage/commit lẫn thay đổi đó và checkpoint bền đã nằm ngoài `/tmp` theo handoff.
- Không chạy migration lên `petcare_shop_dev`; chỉ dùng schema `_test` tách biệt. Dev readiness 503 cần theo quy trình phê duyệt trong tài liệu DB hiện có.
- Provider SMTP/AI/S3 thật, production, Docker deployment và hosted CI chưa được xác minh ở sprint UI này.
- Chi tiết test/ảnh và browser giới hạn: [PHASE4_VISUAL_QA.md](PHASE4_VISUAL_QA.md); implementation: [PHASE4_CUSTOMER_PET_IMPLEMENTATION.md](PHASE4_CUSTOMER_PET_IMPLEMENTATION.md).
