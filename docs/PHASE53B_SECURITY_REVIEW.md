# Phase 5.3B — Security và privacy review

Ngày: 2026-11-10. Kết luận: **NO EGRESS / LIVE PILOT BLOCKED**. Chưa có provider key được dùng, không có ảnh gửi ra ngoài, không có thay đổi runtime.

## Data flow đã kiểm tra

- Pet image workflow chuẩn hóa định dạng JPEG/PNG/WebP thành JPEG, áp EXIF orientation, resize tối đa 1600×1600, re-encode bỏ metadata và validate trước AI service.
- Khi AI Vision được bật/cấu hình, client đưa JPEG vào `data:image/jpeg;base64,...`, kèm prompt trường appearance. App không chủ ý gửi pet/tenant/user IDs trong prompt.
- Provider content có thể chứa chủ thể/nền nhìn thấy được. Loại EXIF không loại khuôn mặt, địa chỉ, biển số, nội thất hoặc vị trí thể hiện trong ảnh.
- Client dùng server-side bearer key, HTTPS được yêu cầu production trừ trusted internal override, từ chối redirect và giới hạn request 8 MiB/response 512,000 bytes. Route input ảnh có giới hạn 5 MiB.
- App log không lưu raw request, raw image, API key hoặc raw response theo source review; AI result không tự ghi pet record. Admin phải chủ động áp suggestion và submit form hiện có.
- `AI_VISION_ENABLED` mặc định off; `APP_ENV=test` chặn provider host bên ngoài, ngoại trừ loopback được bật rõ cho mock.

## Gaps và risk controls bắt buộc

| Risk/gap | Trạng thái hiện tại | Điều kiện trước live |
|---|---|---|
| Consent/license cho ảnh | Không có evidence; eligible egress = 0 | Data owner evidence theo ảnh và provider/endpoint purpose. |
| Region, DPA, retention, abuse monitoring, training | Chưa review theo project/account | Security/Privacy duyệt processor terms/region; xác nhận ZDR/MAM eligibility và image exception. |
| Provider hostname allowlist/network egress | Chưa có global allowlist | Staging firewall/domain allowlist, DNS/TLS verification, endpoint pinned. |
| Attempt cap / duplicate/replay prevention | Chưa có cumulative 50-call guard | Isolated runner; single concurrency, atomic count reservation, unique sample/attempt ledger. |
| Spend limit | Chưa có app local cumulative dollar guard | Fail-closed pre-request budget reservation; project limit plus documented overrun tolerance; cost owner sign-off. |
| Retries | Client có thể retry transient failures tối đa 1 lần | `AI_VISION_MAX_RETRIES=0`, assert one request per approved sample. |
| Structured response | App parses JSON after response; provider schema not sent | Model contract review; allowlisted schema and offline malformed/invalid/abstention tests. |
| Logs/observability | Source client không log body/secret | Pilot log fields allowlist; test log sink; raw provider body disabled; access + retention bound. |
| Credentials | Environment/config supports `AI_API_KEY`; no pilot key used | Project/key scoped to pilot, secret manager injection, rotation/revoke procedure; no user/chat exposure. |
| Tenant separation | Feature behind authenticated admin route; test coverage exists | Dedicated test tenant/DB/storage; no production/customer records or bulk endpoints. |

## Vendor data-control desk review

- **OpenAI Chat Completions:** API data not used for training absent opt-in; default abuse monitoring may retain prompts/responses up to 30 days. Chat Completions is listed with no application-state retention by default, but this is distinct from abuse monitoring. Approved ZDR/MAM eligibility and image-specific exceptions are account-specific; not verified. The hard project/org spend limit may overshoot slightly while enforcement propagates. [Data controls](https://developers.openai.com/api/docs/guides/your-data), [spend limits](https://developers.openai.com/api/docs/guides/spend-limits).
- **Anthropic:** documented API retention differs by model/feature/organization; ZDR feature eligibility and Covered Model exceptions must be checked for the exact model. Workspace spend caps/API semantics are account settings; not inspected. [Retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention), [workspace](https://platform.claude.com/docs/en/manage-claude/workspaces).
- **Google Gemini:** free vs paid data use differs; project spend cap is experimental and may overrun by roughly 10 minutes; logs/data retention and storage settings need exact project review. No free-tier image request is proposed. [Pricing/data-use](https://ai.google.dev/gemini-api/docs/pricing), [billing](https://ai.google.dev/gemini-api/docs/billing), [logs](https://ai.google.dev/gemini-api/docs/logs-datasets).

These statements summarize public docs, not a legal compliance opinion or confirmation of the project’s account settings.

## Scope and incident response

If a later approved pilot starts: stop worker/request source first; disable `AI_VISION_ENABLED`; close approved egress; revoke scoped key; confirm no new request in local/provider ledger; reconcile attempt and spend; notify data/security owner if unapproved bytes crossed boundary. Do not keep or re-upload raw images for debugging.

No images transmitted; no production/development database or application settings modified; no automatic activation. See [provider pilot gate](PHASE53B_PROVIDER_PILOT.md) for required approvals.
