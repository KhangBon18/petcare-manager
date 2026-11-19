# Handoff Phase 5.2 — AI Vision và đa phương thức

## Hiện trạng để tiếp nối

- Ảnh thú cưng hiện đi qua `petcare/routes/pet_routes.py` và `petcare/services/pet_image_service.py`.
- Tìm ảnh tương tự đang dùng descriptor/index cục bộ, xếp hạng màu/bố cục/metadata; score là thứ hạng, không phải xác suất.
- Attribute suggestion bị giới hạn theo allowlist; khi Vision tắt, local path chỉ gợi ý trường có hỗ trợ màu/descriptor.
- Vision provider chỉ chạy khi `AI_VISION_ENABLED` cùng endpoint/model được cấu hình. Không gọi provider thật ở Phase 5.1.
- Upload/media path đã có kiểm tra kích thước/loại ảnh và tenant ownership; xem code hiện hành và [AI integration audit](AI_INTEGRATION_AUDIT.md) trước khi mở rộng.

## Đề xuất thứ tự công việc

1. Chốt một task cụ thể trước (ví dụ gợi ý màu/loài cho hồ sơ), giới hạn fields và để nhân viên xác nhận; không tự tạo/cập nhật hồ sơ.
2. Tạo bộ ảnh synthetic hoặc được cấp phép, có nhãn độc lập; đo precision/recall từng field và tỷ lệ abstain. Không dùng một score tổng thể làm “độ chính xác”.
3. Kiểm tra pipeline resize/metadata stripping, MIME thực, dung lượng, EXIF/định vị, retention, tenant isolation và error states trước khi egress.
4. Mocks timeout, malformed JSON, thiếu field, sai enum, provider 429/5xx và fallback; output phải qua allowlist/types, loại bỏ field chưa đủ tin cậy.
5. Nếu staging provider được phê duyệt, chỉ gửi ảnh test đã duyệt, đặt quota/budget, timeout, endpoint allowlist và retention; ghi nhận latency/cost aggregate, không log ảnh/PII/API key.
6. Thêm Playwright trên desktop/mobile, keyboard, screen-reader spot check và ảnh evidence; giữ cờ provider off mặc định trong test.

## Không nằm trong Phase 5.1

Không thay model, không bật Vision thật, không dùng ảnh khách hàng/production, không đưa AI vào quyết định giá/sale-status và không cho AI thực hiện thao tác ghi. Trước egress thật cần duyệt riêng endpoint, credentials, privacy/retention và ngân sách.
