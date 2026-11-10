# Phase 5.3B — So sánh model và lựa chọn pilot có điều kiện

**Ngày tra cứu tài liệu:** 2026-11-10. Đây là desk review tài liệu chính thức; không có provider nào được gọi, không có accuracy/latency/cost thực đo. Model release, pricing, retention và account controls cần kiểm tra lại trước khi dùng.

## Candidate comparison

| Model | Vision / structured output / endpoint | Giá niêm yết liên quan | Privacy / budget controls | Độ khớp với app |
|---|---|---|---|---|
| **OpenAI GPT-6 Luna (`gpt-6-luna`)** | Model docs: image input; Chat Completions và Responses; structured outputs supported. Candidate direct endpoint `/v1/chat/completions`. Chat API chấp nhận multimodal message. | Standard short context: $0.10/MTok input; $0.50/MTok output. Ảnh được tính vào input theo image tokenization; không quy thành giá cố định/ảnh khi chưa có usage. | API data không được dùng train trừ opt-in; abuse monitoring giữ nội dung mặc định tới 30 ngày. Chat Completions có hard spend limit nhưng không instantaneous, có thể hơi vượt. Region/residency và ZDR/MAM eligibility tùy account/endpoint; chưa xác minh. | **Ứng viên pilot số 1 có điều kiện:** adapter đã dùng OpenAI Chat Completions + image data URI. Chưa truyền JSON Schema, chưa verified tham số model-specific. Cần offline contract update, attempt/spend guard, exact account/region review. |
| **Anthropic Claude Haiku 5.5 (`claude-haiku-5-5`)** | Hỗ trợ text + images, Messages API `/v1/messages`, JSON structured outputs qua `output_config.format`; format/API auth/body khác transport hiện tại. | Tới 100k input context: $0.10/MTok input và $0.50/MTok output theo model overview; image token cost phụ thuộc kích thước. | Tài liệu API nói prompt/response không giữ mặc định cho feature không yêu cầu storage; ZDR và ngoại lệ model/feature theo eligibility. Workspace spend caps khả dụng; đạt spend limit trả 400 cho Claude API workspace limits; account config cần xác minh. | Mạnh về classification/extraction theo nhà cung cấp mô tả, nhưng cần adapter + auth/errors/telemetry riêng. Không có benchmark so sánh. |
| **Google Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`)** | Multimodal text/image, structured outputs. Native GenerateContent/Interactions contracts; official OpenAI compatibility có Chat Completions + data URI image example, nhưng compatibility layer beta. | Paid standard: $0.25/MTok input (text/image/video); $1.50/MTok output, gồm thinking tokens. Free tier có “Used to improve our products: Yes”; không xem free tier là phù hợp cho dữ liệu được phép hạn chế. | Paid logging/data-use policy, project settings và region phải review; spend cap project feature experimental, khoảng 10 phút trễ và có thể overrun. | Có thể adapter-compatible cho pilot engineering, nhưng budget cap/compat layer hạn chế khả năng đảm bảo $1 và phải live-contract verify nếu sau này duyệt. |

Giá là thông tin công khai theo tier tiêu chuẩn, không phải quote tài khoản. Long-context, regional, cache, batch/flex/priority và thinking có thể đổi mức giá; đối chiếu trang giá trước mỗi lần phê duyệt. Không dùng nhận định marketing như bằng chứng chất lượng hoặc độ trễ của model.

## Khuyến nghị

Chọn **GPT-6 Luna làm candidate để xây dựng protocol pilot**, không phải “model tốt nhất” đã được chứng minh. Lý do cụ thể: route Chat Completions và dạng ảnh hiện tại gần với client đang có; model page công bố image input và structured outputs; short-context text pricing thấp. Ưu tiên này giảm số phần integration cần đổi để xác minh mechanics.

Các rủi ro còn quyết định: client truyền `temperature=0.2` và lúc không set `AI_REASONING_EFFORT` dùng `max_tokens`; không có `response_format` JSON Schema, không kiểm contract GPT-6 live/offline fixture theo request parameter/model contract. Cần chỉnh/verify request body trước khi pilot theo model docs; không giả định request hiện tại tự động tương thích hoàn toàn.

OpenAI không được chọn vì accuracy/privacy/budget đã thắng các đối thủ. Chỉ một paired, independently labeled evaluation mới cho phép so quality. Provider cap có thể hơi vượt; nếu owner yêu cầu mức tiêu tối đa tuyệt đối USD 1.00 thì current provider control alone chưa đủ và local fail-closed cost guard vẫn phải được thiết kế, kiểm thử và duyệt trước egress.

## Metrics: measured vs not measured

| Metric | GPT-6 Luna | Claude Haiku 5.5 | Gemini 3.1 Flash-Lite |
|---|---|---|---|
| Accuracy / precision / recall / F1 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| Abstention / unsupported output | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| Invalid JSON / schema rate | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| Latency p50/p95 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| Cost/image | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| Request compatibility with this app | Static docs only; NOT LIVE VERIFIED | Adapter differs; NOT IMPLEMENTED | Official compatibility exists but beta; NOT LIVE VERIFIED |

## Official sources

- [GPT-6 Luna model card](https://developers.openai.com/api/docs/models/gpt-6-luna), [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [image cost calculator](https://developers.openai.com/api/docs/guides/image-cost-calculator), [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data), [spend limits](https://developers.openai.com/api/docs/guides/spend-limits).
- [Claude Haiku 5.5 model overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [vision](https://platform.claude.com/docs/en/build-with-claude/vision), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [API data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention), [workspace controls](https://platform.claude.com/docs/en/manage-claude/workspaces), [rate/spend limits](https://platform.claude.com/docs/en/api/rate-limits).
- [Gemini 3.1 Flash-Lite model](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [pricing](https://ai.google.dev/gemini-api/docs/pricing), [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [billing/spend caps](https://ai.google.dev/gemini-api/docs/billing), [data logging and retention](https://ai.google.dev/gemini-api/docs/logs-datasets).
