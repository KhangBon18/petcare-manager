# Vision Privacy, Egress and Cost Review

Ngày: 2026-11-10. **Không có ảnh hoặc request nào gửi tới nhà cung cấp thật trong Phase 5.3A.** Nội dung dưới đây là data-flow/risk review, không phải tuyên bố tuân thủ hay phê duyệt xử lý ảnh.

## Dữ liệu đi đâu

1. Admin chọn JPEG/PNG/WebP trên form hiện có. Server kiểm tra bytes/format/pixel, áp EXIF orientation, resize tối đa 1600 px và re-encode JPEG; metadata như EXIF/location bị loại trong đường suggestion.
2. Khi `AI_VISION_ENABLED=0` hoặc provider chưa cấu hình, ứng dụng chạy local descriptor/fallback và không gửi ảnh ra ngoài.
3. Nếu operator bật Vision và cấu hình endpoint/model, adapter mã hóa ảnh JPEG thành data URI base64 trong Chat Completions request. **Ảnh và prompt gửi tới host `AI_API_BASE_URL`;** provider có thể lưu content theo chính sách/API feature/account.
4. Suggestion route không ghi bytes/response vào database hoặc pet media storage. Chỉ form create/edit bình thường lưu ảnh nếu admin chủ động submit. Logs của app không ghi ảnh, request body, prompt, API key hay provider response.

Ảnh vẫn có thể cho thấy mặt người, nhà ở, biển số, vị trí hoặc thông tin nhạy cảm trong nền; bỏ EXIF không làm mờ các chi tiết nhìn thấy. Chỉ gửi ảnh có quyền, crop/blur nền khi cần và không dùng ảnh khách hàng ở pilot đầu.

## App controls và gaps

- Secret server-side qua environment/config; không đưa API key vào browser. Production yêu cầu HTTPS, adapter chặn redirect, timeout cấu hình, cap request 8 MiB / response 512,000 bytes và input upload max 5 MiB ở route.
- Vision gọi qua adapter OpenAI-compatible hiện hữu. Test egress guard chặn mọi external host trong `APP_ENV=test`; chỉ literal loopback khi bật cờ test rõ ràng. Mọi browser mock bind `127.0.0.1`.
- Runtime hiện chưa có provider hostname allowlist, egress firewall, per-provider credential vault/rotation, cumulative USD budget guard hoặc global spending kill switch. `AI_API_BASE_URL` là operator configuration nhưng khi được bật có thể trỏ tới host HTTPS tùy chọn. Production trước egress cần network allowlist và DNS/IP review.
- Một retry tối đa có thể làm thêm request. Phase 5.3B nên đặt `AI_VISION_MAX_RETRIES=0`; retries chỉ bật khi quota/budget tính retry rõ.
- Chưa có structured provider `response_format`/JSON schema enforcement. App parse/validate sau response; parser reject/strip trường không hợp lệ. Đây là quality/egress cost risk, không phải bằng chứng provider sẽ tuân thủ schema.

## Provider retention và data terms

Tài liệu truy cập ngày 2026-11-10:

- **OpenAI API:** API data mặc định không dùng để train trừ khi opt-in; abuse monitoring có thể giữ prompt/response tới 30 ngày. Chat Completions `store` mặc định là `false`, nhưng đây không tắt abuse monitoring. Image/file inputs có ngoại lệ hiếm nếu classifier flag nội dung CSAM; ZDR/MAM có điều kiện, phải được duyệt và không loại bỏ mọi giới hạn. Adapter hiện không truyền `store` tường minh; trước provider thật cần xác nhận endpoint/account semantics và cấu hình tương thích. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) · [Chat Completions `store`](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- **Anthropic API:** retention phụ thuộc endpoint/feature, ZDR và account configuration; không suy rộng chính sách giữa Claude API, Bedrock, Google Cloud hoặc Messages features. Xem feature eligibility và điều khoản hiện hành. [Anthropic API retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)
- **Gemini API:** abuse monitoring có cửa sổ retention tối đa mặc định 55 ngày theo policy; Interactions lưu đối tượng mặc định, còn GenerateContent mặc định không lưu request. Paid/free tier có data-use khác nhau; dùng request-level `store=false` và project logging setting được xác nhận. [Gemini usage policy](https://ai.google.dev/gemini-api/docs/usage-policies) · [Gemini logging](https://ai.google.dev/gemini-api/docs/logs-datasets) · [Interactions storage](https://ai.google.dev/gemini-api/docs/interactions-overview)

Chính sách vendor thay đổi; đây không phải privacy clearance. Trước khi gửi bất cứ ảnh nào, xác minh DPA, region/subprocessor, abuse logging, retention/deletion, model training/use, escalation/legal holds, image-specific exceptions và quyền áp dụng ZDR cho đúng endpoint/model.

## Cost model

Cost/token cần provider trả actual usage; không thể suy ra từ bytes hoặc một hình minh họa. Dùng công thức:

`USD/request ≈ input_tokens × input_USD_per_MTok / 1,000,000 + output_tokens × output_USD_per_MTok / 1,000,000`

Ảnh, prompt, output, cached input, batch/service tier, long-context và region có thể đổi đơn giá. GPT-6 Luna hiện niêm yết standard short-context $0.10/MTok input, $0.50/MTok output; image tokenization phụ thuộc resolution/model. Xem [OpenAI pricing](https://developers.openai.com/api/docs/pricing) và [image cost calculator](https://developers.openai.com/api/docs/guides/image-cost-calculator). Chi phí mock hiện tại: **không có estimate** vì telemetry null.

Trước Phase 5.3B: đặt cap cứng ≤ USD 1.00 ở provider project/billing layer, hard quota tối đa 50 provider attempts, retry 0; xác minh request count và spend sau mỗi batch. App hiện không thực thi cumulative dollar cap—nếu provider project không có hard quota/budget control phù hợp thì không bắt đầu egress.

## Approval gates

Owner dữ liệu xác nhận consent/license; Security duyệt provider/endpoint/region/egress/secrets; Product duyệt field labels/abstention/UX; cost owner thiết lập hard budget. Chỉ synthetic/approved, đã giảm PII media trong isolated staging. Provider off mặc định; rollback tắt `AI_VISION_ENABLED`, thu hồi credential theo secret-store process và xác nhận không phát sinh request mới. Chi tiết protocol: [Phase 5.3B approval](PHASE53B_PROVIDER_APPROVAL.md).
