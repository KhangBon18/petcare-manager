# Handoff Phase 5 — AI và AI Vision

## Mục tiêu

Đánh giá độ tin cậy, egress/privacy và độ chính xác của AI hiện hữu; không thay kiến trúc hoặc tự bật provider. Sprint 4.3 không gửi câu hỏi, dữ liệu store hay ảnh ra provider.

## Code path

- POST /assistant/chat → petcare/routes/assistant_routes.py → assistant_service.py; yêu cầu login, CSRF, string message, account/IP throttle.
- assistant_local.py, catalog_intent.py, catalog_service.py trả lời local/deterministic trên tenant DB. Provider OpenAI-compatible chỉ được gọi khi cấu hình.
- POST /pets/suggest-attributes và /pets/find-similar → pet_routes.py + pet_image_service.py. Gợi ý attributes admin-only; local fallback chỉ có thể gợi ý màu lông dominant. Tìm tương đồng dùng descriptor local, Vision chỉ khi flag/endpoint bật rõ.
- petcare/ai/client.py dùng HTTP client giới hạn timeout/response/output, không follow redirect.

## Role và dữ liệu

Membership hiện có owner và staff; quyền admin được xác định trên membership phía server. Tenant/actor lấy từ session/backend; client không quyết định tenant quyền. Assistant yêu cầu login; pet attribute suggestions admin-only; pet/catalog access tenant-scoped.

Provider context được giới hạn theo intent. Customer intent chỉ nhận aggregate count; checkout intent có thể không gửi store data; revenue chỉ period summary; pet/product lists có giới hạn preview; history tối đa 8 items, 800 ký tự mỗi item. Ảnh chỉ egress nếu Vision được bật và có endpoint. System prompt coi store data, history và ảnh là dữ liệu không tin cậy, yêu cầu không bịa số liệu/không lộ PII. Đây là guardrails trong code/test, không phải bằng chứng prompt injection không thể xảy ra.

Xem [AI integration audit](AI_INTEGRATION_AUDIT.md), [API contract](API_CONTRACT.md).

## Mức kiểm chứng

- VERIFIED local: local assistant/catalog trên test data; local image descriptor/color suggestions; fallback, payload validation và context minimization có unit/MySQL tests.
- NOT TESTED thật: model quality, token/cost, latency, provider timeout/429 qua endpoint thật, retention/region, hostname egress allowlist, Vision accuracy trên labelled images.
- SMTP, S3 và external AI/Vision không được gọi sprint này.

## Kế hoạch đánh giá

1. Chốt use case, response schema, budget/request, latency target và hostname staging được duyệt. Credentials chỉ qua secret manager.
2. Tạo synthetic Vietnamese/English prompts có expected facts: exact totals, empty result, time windows, truncated preview, role/tenant checks và untrusted instruction injection.
3. Dùng ảnh synthetic/được phép và labels review thủ công; đo precision/recall theo species/breed/coat fields. Mọi output tiếp tục là suggestion người dùng duyệt.
4. Trên staging với synthetic tenant, kiểm timeout, malformed JSON, 429, provider outage/local fallback và latency/cost aggregate. Không log raw prompt, ảnh, PII hay key.
5. Review egress allowlist, quota/concurrency, redaction và privacy trước khi cân nhắc bật production; quyết định dựa trên report, không tự bật.
