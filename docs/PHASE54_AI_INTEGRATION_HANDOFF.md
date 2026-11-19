# Handoff Phase 5.4 — AI integration

Ngày: 2026-11-10. Phase 5.3B kết thúc ở tiền kiểm; không có live provider integration hoặc benchmark thật. **Provider vẫn tắt.** Handoff này không cho phép gửi ảnh.

## Ứng dụng và workflow hiện có

- Flask/Jinja/MySQL, route và service suggestion ở `petcare/services/pet_image_service.py`; client provider-neutral OpenAI-compatible ở `petcare/ai/client.py`.
- Vision workflow trong pet form xử lý upload JPEG/PNG/WebP, chuẩn hóa local, đề xuất `species`, `breed`, `coat_color`, `eye_color`, `appearance_tags`; các thuộc tính pattern/length/size/shape có thể ánh xạ về appearance description.
- Admin review từng suggestion; có thể bỏ qua hoặc apply vào ô trống. Không auto-save, auto-submit, chẩn đoán sức khỏe, suy đoán tuổi/danh tính hay quyết định tự động.
- `AI_VISION_ENABLED=0` mặc định; test environment blocks external provider egress; explicit loopback mock được kiểm thử.

## Quyết định Phase 5.4

Phase 5.4 đã thêm hai capability deterministic, read-only: ưu tiên tồn kho và trạng thái đơn nhập. Việc này dùng service ứng dụng hiện có, không gọi generative AI/Vision provider và không gửi ảnh. Xem [implementation](PHASE54_IMPLEMENTATION.md), [capabilities](PHASE54_AI_CAPABILITIES.md) và [security review](PHASE54_AI_SECURITY.md).

## Cổng còn lại trước mọi live provider pilot

1. Data owner cung cấp ≤50 ảnh có rights/consent egress ghi nhận được và independent annotation/rubric, hoặc có lựa chọn synthetic public benchmark rõ license. Hiện dataset mechanics có 2 synthetic images / 4 labels nhưng **0 ảnh authorized for provider egress**.
2. Product/Data/Security/Privacy/Cost duyệt chính xác model, endpoint, region, retention/DPA, dataset/hash/count, fields, allowed data, budget/tolerance, max attempts, credential path, abort owner.
3. Tạo isolated staging DB/storage/test tenant; scoped key/project; provider hostname allowlist; `AI_VISION_ENABLED=0` mặc định.
4. Implement and offline-test fail-closed per-run 50-attempt counter, zero retries, concurrency=1, local cost reservation/ledger and request/usage redaction. Provider spend cap alone may be delayed/overrun (OpenAI slight overage; Gemini about 10 minutes). No local cumulative guard exists now.
5. Verify exact request contract for the chosen model. Current candidate GPT-6 Luna supports Chat Completions/image/structured output per docs, but current app's `temperature`, token-limit parameter and absence of `response_format` are unverified for that model. Do not claim compatibility until local request-schema checks and then approved minimal live integration test.
6. Keep provider pilot separate/opt-in from normal user route. No bulk processing; one request per explicit, approved image; manual review/no auto-save remains.

## Test boundaries

Baseline from Phase 5.3A: Python 405/405, JavaScript 36/36, Playwright 16/16; all offline/mock. Re-run after any adapter changes on disposable MySQL test schema. Keep provider live tests in a separate manually invoked suite, never part of CI. Do not include credential-bearing environment dumps or request bodies in test artifacts.

Pilot dataset requirements/protocol: [PHASE53B_PROVIDER_PILOT.md](PHASE53B_PROVIDER_PILOT.md). Model desk review: [PHASE53B_MODEL_EVALUATION.md](PHASE53B_MODEL_EVALUATION.md). Cost and privacy blockers: [PHASE53B_COST_AND_LATENCY.md](PHASE53B_COST_AND_LATENCY.md), [PHASE53B_SECURITY_REVIEW.md](PHASE53B_SECURITY_REVIEW.md).
