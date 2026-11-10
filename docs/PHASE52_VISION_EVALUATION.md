# Phase 5.2 — Đánh giá Vision

## Bộ dữ liệu và phạm vi

Manifest tests/fixtures/vision/manifest.json mô tả ảnh synthetic mèo/chó, WebP, GIF không hỗ trợ, ảnh hỏng/rỗng, PNG vượt 20 triệu pixel và PNG mang đuôi/MIME không khớp. Đây là minh họa hình học, không phải ảnh thật hoặc tập đánh giá model.

## Kết quả kiểm tra

| Case | Kết quả |
|---|---|
| JPEG/PNG/WebP hợp lệ | PASS: decode, chuẩn hóa JPEG, metadata EXIF không còn. |
| Extension/MIME sai nhưng bytes là PNG hợp lệ | PASS: server dựa vào format thực tế, filename không thành server path. |
| GIF, ảnh hỏng, file rỗng | PASS: từ chối input và UI có thông báo. |
| 4600×4600 ảnh nén nhỏ | PASS: bị chặn theo giới hạn pixel. |
| Model output có confidence/URL/HTML/field lạ | PASS: field ngoài contract bị bỏ; HTML không thực thi. |
| Field sai kiểu, rỗng hoặc quá dài | PASS: sai kiểu bỏ qua, string normalize/cap theo field, fallback được giữ. |
| Mock provider valid, malformed, ambiguous, 503, timeout | PASS trong browser integration; retry và local uncertain state được kiểm. |
| Admin/staff, tenant, CSRF, concurrency | PASS theo MySQL/web/Chromium: staff bị 403, tenant lấy từ session, request đồng thời vượt slot nhận 429. |
| UI apply | PASS: keyboard Enter áp dụng vào ô trống; giá trị đã nhập vẫn giữ nguyên. |

## Regression evidence

- Python 389/389, 0 skip; JavaScript 34/34; Chromium 15/15.
- MySQL route integration target 1/1; database petcare_phase52_test có hậu tố _test.
- Browser viewport matrix: 320, 390, 768, 820, 1024, 1440 px; document width khớp viewport trong Vision form.
- /healthz=200, /readyz=200. Bandit CI command, pip-audit runtime/browser, pip check, compileall, Docker build và Compose parse đạt.

## Không đo độ chính xác

Mock trả JSON do test định nghĩa. Nó chứng minh transport, parsing, authorization, fallback, UI và metadata handling; không chứng minh model nhận dạng đúng loài, giống, màu hoặc shape. Không tính precision/recall/abstain accuracy từ hình minh họa. Màu cục bộ có thể gồm nền ảnh và UI nêu rõ giới hạn này.

## Còn thiếu trước benchmark chất lượng

1. Xin bộ ảnh có quyền sử dụng, cân bằng theo loài/giống/ánh sáng/góc/chất lượng và tách tập phát triển/đánh giá.
2. Nhãn độc lập cho từng field và quy tắc thống nhất khi ảnh mơ hồ/không nhìn thấy đặc điểm.
3. Báo precision/recall và tỷ lệ abstain riêng từng field, khoảng tin cậy và phân tích lỗi theo điều kiện ảnh.
4. Chốt ngưỡng chấp nhận và người duyệt nghiệp vụ trước thử staging provider.
5. Chỉ sau khi privacy, egress, retention, region và budget được duyệt mới gửi media evaluation đã được cấp phép.

Kết luận: workflow kỹ thuật được kiểm thử với mock; model accuracy là NOT TESTED.
