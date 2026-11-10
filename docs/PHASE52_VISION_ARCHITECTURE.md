# Phase 5.2 — Kiến trúc Vision

## Luồng xử lý

1. Admin mở form pets hiện có và chọn ảnh. Trình duyệt chặn nhanh file quá 5 MiB và tạo preview; client validation không thay kiểm tra server.
2. JavaScript gửi multipart photo tới POST /pets/suggest-attributes với CSRF header. Request cũ bị hủy khi đổi ảnh; status được cập nhật qua aria-live.
3. Flask auth, CSRF, account/IP throttle và image-processing semaphore chạy trước handler. Quyền admin và tenant lấy từ actor/session server-side.
4. Route giới hạn upload; pet_image_service xác thực JPEG/PNG/WebP bằng Pillow, kiểm tra kích thước/pixel, áp EXIF orientation, thu nhỏ tối đa 1600 px và re-encode JPEG bỏ metadata.
5. Bytes chuẩn hóa được phân tích bằng descriptor màu cục bộ. Chỉ khi AI_VISION_ENABLED và client cấu hình thì gọi adapter provider hiện hữu; mặc định vẫn off.
6. Parser nhận JSON object với field chuỗi allowlist, chuẩn hóa Unicode/control characters và giới hạn độ dài. Kết quả rỗng/sai/provider lỗi được phân biệt; giữ local fallback khi có thể.
7. Route trả JSON có trạng thái, gợi ý, màu và warning có kiểm soát. UI render text, không HTML; nút apply chỉ ghi vào field trống. Người dùng tự submit form create/edit theo workflow hiện hành.

## Ranh giới dữ liệu và quyền

- POST /pets/suggest-attributes admin-only, CSRF-protected, có account/IP throttle và giới hạn số tác vụ ảnh đồng thời.
- Tenant id không lấy từ payload; integration test gửi tenant giả nhưng service dùng tenant của session.
- Gợi ý chỉ giữ bytes trong bộ nhớ; endpoint không lưu ảnh vào pet storage hoặc database. Ảnh chỉ thành ảnh hồ sơ nếu admin submit form create/edit.
- Không có schema, model, migration, dependency hay service queue mới. Hợp đồng route hiện hữu được mở rộng tương thích bằng status/provider_status/code.
- Provider timeout, response-size và redirect policy kế thừa client hiện hành; Phase 5.2 không xác minh provider bên ngoài.

## Module boundaries

| Tầng | Module | Trách nhiệm |
|---|---|---|
| UI | petcare/templates/pets/form.html, petcare/static/js/pet_attributes.js, photo_preview.js | Chọn ảnh, accessible status, preview, render an toàn và apply có chủ ý. |
| HTTP/auth | petcare/routes/pet_routes.py, petcare/app_hooks.py | CSRF/auth hiện hành, JSON status, throttle/semaphore và không tiết lộ lỗi nội bộ. |
| Business/image | petcare/services/pet_image_service.py, petcare/vision/* | Xác thực/chuẩn hóa bytes, local descriptor, parser và fallback. |
| Provider adapter | petcare/ai/client.py | OpenAI-compatible transport tái sử dụng; không bật provider mặc định. |
| Persistence | pet service/repository hiện có | Không ghi trong suggestion request; form create/edit giữ trách nhiệm persistence riêng. |
| QA | tests/fixtures/vision, tests/unit, tests/web, tests/integration, scripts/browser_smoke/test_vision_e2e.py | Synthetic input, fake HTTP provider, MySQL/Chromium verification. |

## Failure handling

Input thiếu/sai trả 400; auth denial 403; rate-limit/busy 429 và Retry-After; lỗi nội bộ 500 với câu trả lời chung. Provider malformed/ambiguous/unavailable không biến thành nhận định chắc chắn; local color fallback được gắn nhãn không chắc chắn. Cancel phía trình duyệt dừng chờ phía client, không cam kết dừng công việc đã bắt đầu ở server.
