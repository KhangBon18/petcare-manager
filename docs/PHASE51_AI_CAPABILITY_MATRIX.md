# Phase 5.1 — Ma trận năng lực AI

| Năng lực | Trạng thái | Bằng chứng và giới hạn |
|---|---|---|
| Local assistant: doanh thu, tồn kho, sản phẩm, thú cưng, hướng dẫn | VERIFIED | Code `assistant_service.py`, `assistant_local.py`, `catalog_intent.py`; unit/MySQL/browser coverage cũ. Không rà lại mọi intent trong sprint này. |
| Insight sản phẩm bán chạy theo kỳ | VERIFIED | Local deterministic path dùng report service/repository thật; staff và admin; kỳ today/7d/week/last_week/month/last_month; tối đa 5 link sản phẩm. Kỳ explicit chưa hỗ trợ được giải thích thay vì tự dùng 7d. Unit, MySQL route và Chromium 390 px đều chạy. |
| Độ chính xác số liệu bán | VERIFIED theo QA scope | API response được so sánh product ID/số lượng với `report_service.top_products_for_period`; xử lý không có kết quả và period không hợp lệ có unit tests. |
| Tenant và role enforcement | VERIFIED theo QA scope | `require_actor` đọc membership từ MySQL; test staff ở tenant hiện tại; payload cố override tenant bị bỏ qua; tenant khác bị từ chối khi gọi service trực tiếp. |
| LLM provider OpenAI-compatible | IMPLEMENTED / NOT TESTED thật | Client và fallback có sẵn; test tắt external egress. Intent bán chạy không gọi `complete`, kể cả khi mocked provider-configured. Chưa xác minh model, latency, token/cost hoặc provider errors trên mạng thật. |
| AI Vision pet attributes | IMPLEMENTED cục bộ / NOT TESTED provider | Local descriptor/color suggestion và image similarity tồn tại; Vision thật không chạy. Chi tiết ở [AI integration audit](AI_INTEGRATION_AUDIT.md). |
| SQL/tool execution từ prompt | NOT PROVIDED | Intent là allowlist cố định; người dùng không gửi SQL/date range/tenant quyền; không có AI tool có quyền ghi. |
| UI insight và record navigation | VERIFIED | Suggestion mới, trạng thái source, top product cards, số lượng/doanh thu và link same-origin. XSS payload dạng tên sản phẩm được render bằng text. |
| Retry/fallback mới | NOT APPLICABLE | Nhánh số liệu không gọi provider; DB/API failure theo lỗi route hiện hữu. Không thêm retry DB để tránh lặp request không cần thiết. |

Trạng thái “VERIFIED” chỉ áp dụng cho phạm vi và evidence ghi ở hàng tương ứng; không chứng minh toàn bộ assistant hoặc provider đã sẵn sàng production.
