# Kiểm toán tích hợp AI và AI Vision

Ngày 2026-11-09. Phân biệt rõ implementation, local execution và provider thật.

## Thành phần hiện có

| Thành phần | Thực hiện | Trạng thái Phase 2 |
|---|---|---|
| Shop assistant | `petcare/services/assistant_service.py`, `assistant_local.py`, `catalog_intent.py`, route `POST /assistant/chat`. Có local intent cho doanh thu, stock, products, pets, image-search help; truy vấn catalog chính xác đi qua MySQL. | **VERIFIED local** trên browser: low-stock query trả catalog item, mode `local`; panel nói rõ generative AI chưa nối. |
| Optional chat model | `petcare/ai/client.py`; OpenAI-compatible Chat Completions qua stdlib `urllib`, không có SDK/provider lock-in. | **NOT TESTED provider thật**; URL/model/key ở môi trường test để trống. |
| Image similarity | `petcare/services/pet_image_service.py`, descriptor local, candidate index, color/structure/metadata ranking, top 12 results. | **VERIFIED local** bằng ảnh tổng hợp; ảnh mới đứng đầu, điểm hiển thị là ranking score, không phải confidence/probability. |
| Optional AI Vision | Cùng HTTP client nhưng gửi image bytes chỉ khi `AI_VISION_ENABLED` và endpoint/model được cấu hình. Đầu ra JSON được giới hạn allowlist fields. | **NOT TESTED provider thật**; cờ tắt, không gửi ảnh ra ngoài. |
| Attribute suggestions | `/pets/suggest-attributes`, admin-only; nếu Vision tắt thì local dominant-color descriptor chỉ gợi ý `coat_color`. | **VERIFIED local**; ảnh demo đưa ra màu, không tự đoán giống/loài/mắt. |

## Luồng dữ liệu và bảo vệ

- Assistant kiểm actor/tenant trước khi lấy context; date window theo timezone tenant; `catalog_intent` định tuyến sang catalog lookup.
- `_provider_context()` chỉ đưa dữ liệu cần cho câu hỏi: revenue intent đưa đúng một period; pet/product intent gửi preview giới hạn; customer intent chỉ gửi số lượng, không gửi danh sách khách; checkout intent có thể đánh dấu `store_data_included=false`.
- System prompt yêu cầu không bịa số liệu/không lộ PII; coi history, ảnh và shop data là untrusted; phân biệt số tổng hợp với preview bị cắt. History giữ tối đa 8 mục, mỗi nội dung 800 ký tự.
- AI client từ chối URL sai scheme/credentials/query/fragment; production yêu cầu HTTPS trừ ngoại lệ endpoint nội bộ rõ cấu hình; không follow redirect; timeout mặc định 15 giây; response cap 512 KB; output content cap 4.000 ký tự; max tokens 700.
- Khi provider lỗi, assistant trả local fallback với `mode=local`; Vision lỗi/JSON hỏng rơi về descriptor local và warning. Không thấy retry/backoff tự động; mỗi request có thể giữ web worker tối đa khoảng timeout cấu hình.
- Image suggestion cần admin, kiểm membership trước khi gửi model; ảnh chuẩn hóa, analysis fields allowlist `species/breed/coat_color/coat_pattern/coat_length/eye_color/size/shape`, mỗi field được truncate. Local suggestion cho biết color có thể gồm cả background.
- Assistant chat có throttle theo account/IP; route JSON xác thực object/message type, ServiceError thành 400. CSRF nằm trong Flask-WTF.

## Đánh giá thực tế

- Local assistant đã trả catalog result và UI hiển thị nguồn là MySQL hiện tại.
- Tìm ảnh đã dùng ảnh local, descriptor màu/bố cục; không có request Vision. UI không gọi provider nếu cờ/config tắt.
- Unit/MySQL tests cover intent, exact count/preview, fallback, output validation/quota, prompt context minimization, ảnh JSON sai định dạng và giới hạn request. Đây là simulated tests, không phải chất lượng model ngoài đời.
- Không đo token/cost, latency provider, hallucination rate, jailbreak resistance với model thật, retention policy, tenant data egress hoặc accuracy trên bộ ảnh đã gán nhãn.

## Rủi ro và đề xuất

1. **P2 — Latency/cost khi bật provider:** HTTP call đồng bộ có thể chiếm worker đến timeout. Trước khi bật, chốt concurrency/rate limit, per-request cost budget, structured metrics (không ghi prompt/PII) và breaker/timeout UX.
2. **P2 — Hợp đồng dữ liệu:** không có provider allowlist ở hostname; endpoint do operator cấu hình. Thêm kiểm soát deployment để chỉ chấp nhận endpoint đã duyệt, tắt `AI_ALLOW_HTTP_ENDPOINT` ngoài môi trường nội bộ.
3. **P2 — Độ tin cậy Vision:** structured JSON có validation/allowlist nhưng không có đánh giá độ chính xác thực tế. Tạo bộ ảnh synthetic/được cấp quyền có nhãn trước khi dùng suggestions cho quyết định kinh doanh; luôn yêu cầu người dùng xem lại.
4. **P3 — Observability:** lưu provider mode, latency, fallback/error category và token estimate tổng hợp; không ghi raw prompt, ảnh, API key hay customer data.
5. **P3 — UX local-first:** giữ thông báo phân biệt local ranking với semantic model, giữ score là ranking chứ không phải xác suất.

Không bật provider, không gửi ảnh/câu hỏi ra ngoài và không phát sinh phí trong Phase 2. Xem [MASTER_UPGRADE_ROADMAP.md](MASTER_UPGRADE_ROADMAP.md) để biết acceptance criteria.
