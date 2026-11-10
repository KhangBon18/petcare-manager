# Phase 5.1 — Rà soát an toàn AI/data

## Kiểm soát được xác minh

- **Authentication/CSRF/rate limit:** dùng đúng `POST /assistant/chat` hiện hành; anonymous POST với token CSRF hợp lệ bị chuyển tới đăng nhập. Throttle account/IP không đổi.
- **Role/tenant:** assistant gọi report service với actor và tenant lấy từ phiên server-side. Report service gọi `require_actor`; DB connection nhận tenant context từ membership thật. Staff được phép xem báo cáo theo quyền hiện có, không có admin bypass.
- **SQL:** chỉ period enum cố định (`today`, `7d`, `week`, `last_week`, `month`, `last_month`); ngày tenant-local được đổi thành UTC bounds. `report_repo.top_products` giữ SQL literal, date values bind qua `%s`, tenant predicate dùng `@petcare_tenant_id`, giới hạn `LIMIT 10`; service giới hạn API còn 5 hàng. Không ghép prompt vào SQL.
- **Data minimization:** nhánh này chỉ trả snapshot sản phẩm, số lượng/doanh thu và product ID. Không lấy hoặc gửi tên khách, số điện thoại, địa chỉ hay hồ sơ thú cưng.
- **Prompt injection:** insight được tạo trước provider branch và không gọi `ai_client.complete`. Integration test gửi chỉ dẫn tiết lộ prompt/credentials và tenant ID khác trong body; dữ liệu vẫn khớp tenant đăng nhập.
- **HTML/URL:** frontend dùng `textContent` cho tên/code/metrics; chỉ render href khớp `/products/\d+`. Không dùng `innerHTML` hoặc URL do LLM tạo.
- **Writes/secrets:** tính năng chỉ đọc; không tạo invoice, đổi stock, chạy SQL tùy ý hoặc ghi prompt/secret vào log. Không gọi provider ngoài.

## Kết luận

Không phát hiện P0/P1 mới trong lát cắt này. Các kiểm soát dựa trên test và code path cụ thể, không phải bằng chứng toàn assistant miễn nhiễm prompt injection. Bandit đúng command trong `.github/workflows/ci.yml` exit 0; còn warning `nosec encountered (B608)` đã có trong baseline và không làm gate fail. Không thêm suppression hoặc thay baseline.

## Rủi ro còn lại

- Provider thật chưa được kiểm tra egress/retention/region, credential rotation, timeout/cost hoặc output abuse; các tính năng khác của assistant vẫn có thể gửi context khi provider bật.
- SQL xếp hạng kế thừa semantics của report hiện tại (hoàn trả trừ theo ngày ghi nhận hoàn). Người dùng cần hiểu đó là số lượng bán ròng, không phải tổng đơn tạo.
- Full test suite chưa xanh trên trạng thái QA hiện có; không xóa dữ liệu hoặc mở quyền DB chỉ để đạt kết quả xanh.
- Trivy/hosted GitHub Actions không chạy trong lượt này. `pip-audit` hai lockfiles và source Bandit đã chạy local.

Không bật AI/Vision provider bằng thay đổi Phase 5.1.
