# Vận hành và giám sát

## Health checks

- `/healthz` trả liveness của web process.
- `/readyz` kiểm tra MySQL và schema contract của web.
- `/workersz` chỉ trả `ready` nếu email worker và export worker có heartbeat thành công trong 90 giây gần nhất. Endpoint này dùng cho liveness, không đo hàng đợi.

## Giới hạn xử lý ảnh

`IMAGE_PROCESSING_CONCURRENCY` giới hạn số request có upload ảnh được giải mã/chuẩn hóa đồng thời trong **mỗi web process**; giá trị hợp lệ là 1–4, mặc định 1. Compose chạy Gunicorn với hai worker process nên mặc định cho phép tối đa hai lượt xử lý ảnh đồng thời trong một web container. Các POST không có file ảnh vẫn đi qua bình thường.

Ảnh hồ sơ thú cưng/sản phẩm còn có quota theo tài khoản và địa chỉ mạng qua bảng MySQL dùng chung: mặc định 12 lần tải/tài khoản/phút và 60 lần/mạng/phút. Khi vượt quota, người dùng được đưa lại form với `Retry-After`; khóa quota là HMAC, IP thô không được lưu. Camera search đã có quota Vision riêng theo tài khoản/mạng.

Khi process đã dùng hết slot, request upload được chuyển về form với thông báo thử lại và header `Retry-After: 2`. Semaphore chỉ chia sẻ trong process; với nhiều web container, tổng giới hạn bằng cấu hình nhân số process. Quota MySQL bảo vệ luồng xử lý lưu ảnh giữa các instance, nhưng request body đã tới ứng dụng trước khi quota được kiểm tra; vẫn cần giới hạn bandwidth/request ở HTTPS edge hoặc WAF. Đây là backpressure để hạn chế nhiều lần giải mã ảnh lớn cùng lúc, không phải bằng chứng tải. Giữ mặc định tới khi đo bộ nhớ/độ trễ trên hạ tầng mục tiêu; chỉ tăng giá trị sau khi load test.

## Prometheus metrics

Endpoint `GET /metrics` bị tắt và trả 404 nếu `OPS_METRICS_TOKEN` để trống. Khi bật, endpoint yêu cầu `Authorization: Bearer <token>`; token phải có ít nhất 32 ký tự. Cấu hình cùng secret qua secret manager cho các web instance và Prometheus, không lưu token trong repo, URL, dashboard hoặc access log. Chỉ cho phép hệ thống giám sát đáng tin cậy truy cập endpoint qua HTTPS/mạng riêng.

Ví dụ gọi từ máy giám sát sau khi đã nạp secret vào biến môi trường:

```bash
curl --fail --silent \
  -H "Authorization: Bearer ${OPS_METRICS_TOKEN}" \
  https://petcare.example/metrics
```

Metrics hiện chỉ xuất số tổng hợp toàn hệ thống, không có tenant ID, username, email, nội dung job hay artifact key:

- `petcare_queue_jobs{queue,status}`: số job pending/processing/failed; export queue có thêm ready.
- `petcare_queue_oldest_pending_seconds{queue}`: tuổi của job pending lâu nhất.
- `petcare_worker_up{worker}`: `1` khi heartbeat gần nhất thành công và còn mới, nếu không là `0`.

Metric scrape trả 503 nếu MySQL không đọc được. Phản hồi được đặt `no-store`; token sai hoặc thiếu nhận 401. `/metrics` không gửi cảnh báo và không thay thế WAF, queue alerting, incident response hoặc backup alerts. Đặt ngưỡng theo dịch vụ/email SLA và lượng tải thực tế của đơn vị; theo dõi 401/503 mà không ghi header Authorization.
