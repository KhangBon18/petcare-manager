# Phase 5.3B — Gói pilot provider thật và approval gate

Ngày: 2026-11-10. Trạng thái: **BLOCKED — chưa có ảnh đủ quyền gửi và chưa được user duyệt request thật.** Không có API request nào được gửi.

## Kết quả kiểm tra data

| Thuộc tính | Bằng chứng hiện có | Ý nghĩa cho pilot |
|---|---|---|
| Dataset ID | `petcare-vision-synthetic-mechanics`, v1.0.0 | Chỉ dành cho mechanics, không phải benchmark nhận dạng. |
| Hình eligible trong harness | 2 synthetic illustrations | Có thể chạy offline harness; không được coi là ảnh đã được phép gửi provider. |
| Hình có quyền egress được chứng minh | **0** | Không có consent/license/owner approval cụ thể trong manifest hoặc hồ sơ này. |
| Nhãn | 4 giá trị: `species` và `coat_color` ở mỗi hình | Nhãn xác minh theo construction; không có độc lập hai annotator hay rubric disagreement. |
| Unknown/abstention | Không có mẫu `null` đã annotate | Chưa đo abstention/false suggestion. |
| Split/independence | `mechanics_only` | Không có held-out real-image split; không độc lập với mục đích fixtures. |
| Scenario | Hai case clear synthetic; edge cases chờ ảnh/nhãn | Ambiguous, lighting, occlusion, multiple pets, non-pet, missing evidence và conflicting attributes chưa covered bởi model evaluation. |

`unsupported.gif`, `corrupted.png`, `empty.bin` và `oversized.png` là processing tests, không phải mẫu gửi model. Không tự gán nhãn cho media. Không dùng profile, ảnh, prompt, hoặc record từ tenant thật.

## Điều kiện để chuẩn bị một dataset pilot

1. Data owner cung cấp/định danh tối đa 50 ảnh riêng, quyền sở hữu và văn bản cho phép chuyển nội dung tới đúng provider/endpoint/region; xác nhận không chứa người/địa chỉ/nội dung nhạy cảm hoặc cho phép xử lý sau crop/blur.
2. Giữ labels độc lập từ annotator, provenance, rubric cho từng field, unknown/abstain, bất đồng/adjudication, split và kiểm tra duplicate/perceptual duplicate. Chỉ ghi các field hỗ trợ trong form: `species`, `breed`, `coat_color`, `eye_color`, `appearance_tags`.
3. 50 request là pilot vận hành tối đa, không phải bằng chứng độ chính xác tổng quát. Protocol hiện tại đề xuất 400 ảnh và hai annotator để xem xét quality gate rộng hơn; đây cũng chưa phải yêu cầu thống kê đã được chứng minh và cần Product/Data chốt.
4. Đóng gói manifest có sample IDs bất khả danh, file hashes, scenario, rights status, source labels, holdout marker, prompt/version, preprocessing version và approval reference. Không đưa tên, email, pet/customer ID vào request hoặc report.

## Candidate cụ thể — chưa được phê duyệt

- Provider/model: OpenAI `gpt-6-luna`.
- Candidate endpoint: `https://api.openai.com/v1/chat/completions` (global endpoint; region/account terms chưa được chọn hoặc xác nhận).
- Credential: server-side secret manager injection qua `AI_API_KEY`; tuyệt đối không gửi key qua chat, commit, screenshot hay report.
- Tài liệu model xác nhận image input, Chat Completions và structured outputs; request model-specific chưa live-verified. App hiện chưa bật `response_format` schema và có thể cần narrow adapter adjustment trước khi gửi.
- Staging cần isolated `_test` DB/storage, `AI_VISION_ENABLED=0` mặc định, `AI_VISION_MAX_RETRIES=0`, concurrency=1, tổng attempt counter=50 và request ledger không chứa body/image/key. Chưa có global attempt counter/spend guard trong app hiện tại.

## Dữ liệu có thể đi qua endpoint nếu được duyệt

Ứng dụng chuẩn hóa media thành JPEG (EXIF orientation, resize tối đa 1600×1600, re-encode không giữ metadata) rồi gửi ảnh dạng base64 data URI với system/user prompt chỉ yêu cầu mô tả ngoại hình. Prompt có thể là tiếng Việt hoặc tiếng Anh theo locale. Không gửi pet/customer/tenant ID trong message. Provider vẫn nhận bytes ảnh, prompt, request metadata, IP/runtime metadata và output; ảnh nhìn thấy có thể chứa nội dung nền dù EXIF đã bỏ.

App không log request body, raw image, API key hoặc provider response theo review hiện tại; kết quả model không tự lưu pet record. Dữ liệu vẫn chịu retention/abuse monitoring theo provider/account/region. Đây không phải privacy clearance.

## Approval package — chưa sẵn sàng để chấp thuận live run

| Mục bắt buộc | Giá trị đang đề xuất / chưa biết |
|---|---|
| 1. Provider + model ID | OpenAI `gpt-6-luna`, candidate; chưa duyệt. |
| 2. Endpoint | `https://api.openai.com/v1/chat/completions`; global routing candidate, chưa duyệt. |
| 3. Dataset + số ảnh được duyệt | Manifest `petcare-vision-synthetic-mechanics` có 2 hình; số ảnh được phép gửi provider hiện **0**. Không có run-able dataset. |
| 4. Quyền/consent | Chưa có owner/license/consent egress evidence. BẮT BUỘC bổ sung theo từng sample. |
| 5. Dữ liệu gửi | JPEG tối đa 1600 px sau bỏ metadata + prompt mô tả appearance + request headers; không có record IDs. |
| 6. Region/retention | Endpoint candidate global, region chưa được chốt. OpenAI nói abuse logs mặc định có thể giữ content tới 30 ngày; API không training trừ opt-in. Account ZDR/MAM, DPA, region/data residency và ngoại lệ ảnh chưa được xác minh. |
| 7. Expected cost / maximum | Tổng expected cost chưa biết trước vì chưa có image token usage; output-only upper bound ở 50 × 700 tokens là khoảng USD 0.0175 theo giá standard ngắn hiện hành, chưa gồm input image, prompt hoặc uplift. Budget đề xuất USD 1.00 chưa được chấp thuận. Hard spend limit của OpenAI có thể vượt nhẹ do enforcement delay. |
| 8. Attempts | Đề xuất tối đa 50; automatic retries 0; concurrency 1. Chưa cấu hình/được duyệt. |
| 9. Credential config | Secret manager/runtime injection, env key `AI_API_KEY`; project/key riêng. Không có credential được kiểm tra hay in ra. |
| 10. Abort/disable | Dừng runner, đóng route egress, `AI_VISION_ENABLED=0`, restart process, thu hồi key trong secret manager, reconcile provider usage/request ledger và giữ aggregate-only approved artifacts. Chưa diễn tập trên provider thật. |

### Trạng thái gate

Không gửi request. Để mở lại bước review, cần trước tiên có (a) dataset pilot đã cấp quyền và manifest/rubric, (b) vùng/retention/privacy decision của provider project, (c) verified staging hostname/credential provisioning, (d) local attempt-and-spend guard cùng test offline, và (e) product/security/cost approval cho đúng gói trên. Sau khi các giá trị cụ thể đủ, phải xin phê duyệt tường minh cho **provider + model + endpoint + dataset/hash/count + consent + data flow + region/retention + budget + attempt count + credential injection + abort**. “Tiếp tục Phase 5.3B” không phải chấp thuận gửi dữ liệu.
