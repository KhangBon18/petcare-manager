# Phase 5.3B — Chi phí và độ trễ

Ngày cập nhật: 2026-11-10. **Live provider calls: 0.** Không có image-token usage, output usage, wall-clock latency hoặc invoice/provider cost measurement.

## Giá candidate OpenAI GPT-6 Luna

Tài liệu OpenAI công bố Standard short-context GPT-6 Luna ở $0.10/1M input tokens và $0.50/1M output tokens. Image input tính theo tokenization phụ thuộc model và image processing; kích thước JPEG không cho phép suy ra token usage chính xác.

Theo proposed pilot cap 50 attempts, app cap 700 completion tokens/request sẽ cho output-only arithmetic ceiling: `50 × 700 × $0.50 / 1,000,000 = $0.0175`. Đây không phải tổng ước tính: input image + prompt, cached/long-context/region/service tier, thuế hoặc giá theo account chưa cộng. `AI_REASONING_EFFORT=none` và `max_completion_tokens=700` là config candidate cần kiểm contract, chưa được áp dụng.

**Expected total spend: chưa xác định.** Không có eligible image set để đo image tokenization và chưa có account/project pricing/settings. Không tuyên bố 50 ảnh chắc chắn dưới $1.00.

## Spend controls và giới hạn

- Đề xuất ban đầu (chưa được duyệt): tối đa 50 provider attempts, 0 automatic retries, concurrency 1, budget target USD 1.00.
- CI/test egress guard chỉ bảo vệ `APP_ENV=test`; nó không phải production provider cap. Client có retry tối đa 1 lần cho lỗi tạm thời theo default; staging buộc phải đặt 0 và assert attempt ledger.
- Ứng dụng hiện không có tổng attempt counter 50, cumulative USD guard, per-run atomic reservation hoặc request allowlist. Rate limit theo phút không thay cho giới hạn tổng.
- OpenAI có hard spend limit ở project/org, nhưng docs nói enforcement không tức thời và recorded spend có thể vượt nhẹ. Alert chỉ thông báo, không dừng request. Vì vậy provider cap không bảo đảm hard maximum USD 1.00.
- Gemini project cap có tính experimental và khoảng 10 phút billing latency/overage. Anthropic có organization/workspace spending limits; cần xác nhận account enforcement và in-flight behavior. Không có provider nào được cấu hình để thực nghiệm ở lượt này.

Nếu tiếp tục thiết kế local guard, guard phải fail closed trước request: giới hạn request count; serialize requests; tính worst-case request debit từ image preprocessing/token-accounting rules + prompt + response cap; reserve trước khi gửi; không gọi nếu usage/cost bound không xác định; settle theo returned usage; dừng ngay khi có lỗi telemetry/ledger. Provider cap vẫn là lớp bổ sung, không thay local guard.

## Latency

Không có p50/p95 thực tế. “Fastest/low latency” hoặc “efficient” trên model pages là định vị nhà cung cấp, không dùng làm SLA. Pilot nếu được duyệt sẽ lưu `latency_ms` monotonic theo từng request, gồm error/timeouts, và báo median/p95 theo mẫu cùng số response hợp lệ; không tính latency mock thành latency provider. Ngưỡng 8 giây trong approval protocol hiện chỉ là proposed acceptance target.

## Sau khi có quyền và dữ liệu

1. Chốt exact project pricing/region/model snapshot; lấy output token cap/usage semantics.
2. Cấu hình separate API project/key, hard cap nhỏ nhất khả dụng, pre-alert và local ledger guard.
3. Trên ≤50 ảnh approved, chạy 1 request/sample, không retry, tuần tự; reconciliation trước khi tiếp tục sau mỗi batch.
4. Ghi attempt ID, pseudonymous sample ID, model, wall time, usage fields, estimated/actual amount, HTTP/error class và parser version; không ghi body, ảnh, key, provider response raw hoặc PII.
5. Stop khi cạn quota, usage ledger mismatch, cost không thể bound, output safety/tenant issue, request vượt 50, retry xảy ra hoặc provider region/config lệch approval.

Nguồn: [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [image cost calculator](https://developers.openai.com/api/docs/guides/image-cost-calculator), [OpenAI spend limits](https://developers.openai.com/api/docs/guides/spend-limits), [Gemini billing](https://ai.google.dev/gemini-api/docs/billing), [Claude rate/spend limits](https://platform.claude.com/docs/en/api/rate-limits). Giá/controls truy cập 2026-11-10, phải xác minh lại tại approval.
