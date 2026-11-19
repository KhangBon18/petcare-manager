# Phase 5.1 — Đánh giá trợ lý và grounding

## Bộ đánh giá và tiêu chí

Dùng dữ liệu demo/synthetic trong schema QA `_test`; không dùng production data hoặc gửi nội dung tới provider. Kết quả kỳ vọng được lấy từ report service/repository hiện hành.

Một câu trả lời đạt grounding khi đồng thời: (1) `mode=local`, (2) `insight.kind=top_products`, (3) period và ngày khớp kỳ tenant-local, (4) product ID và số lượng khớp report service, (5) URL là hồ sơ product nội bộ. Điểm task success = số case đạt / tổng case. Không dùng đánh giá chủ quan của LLM.

## Kết quả trước/sau

| Case | Baseline | Sau thay đổi | Bằng chứng |
|---|---:|---:|---|
| Vietnamese: sản phẩm bán chạy tuần này | 0/1 | 1/1 | Baseline trả catalog preview, không có insight/số lượng bán. Sau: browser Chromium click suggestion, card tên/số lượng/link đối chiếu MySQL report. |
| English: “Which products sold the most this week?” kèm prompt injection và tenant override | 0/1 | 1/1 | Baseline không có insight. Sau: POST route trả đúng tenant đang đăng nhập, report facts bằng MySQL; provider mock `complete` không được gọi. |
| **Grounding score** | **0/2 (0%)** | **2/2 (100%)** | Hai workflow trên, một browser thật và một MySQL route integration. Mẫu nhỏ, chỉ kết luận cho use case này. |

Baseline được chạy trước sửa bằng context/catalog giả lập QA: cả VI và EN có `insight_field=false`, không có evidence quantity bán và `catalog_fallback=true`. Sau thay đổi, case EN so sánh API với kết quả report service trên MySQL; case VI so sánh trình bày browser với cùng service. Không suy rộng score sang AI tổng quát.

## Ma trận case

| Case | Kết quả | Kiểm tra |
|---|---|---|
| Câu hỏi VI/EN, period week và default 7d | PASS | Intent/period unit cases; MySQL test xác nhận kỳ tuần. |
| Empty sales result | PASS | Không phát minh tên/số; trả thông báo không có bán ròng. |
| Câu mơ hồ/doanh thu | PASS | “Doanh thu bán hàng tuần này” không bị nhận nhầm thành xếp hạng sản phẩm. |
| Explicit period chưa hỗ trợ | PASS | “Yesterday” và “last 30 days” nhận hướng dẫn chọn kỳ; không query 7 ngày rồi trả như thể đúng period. |
| Period đầu vào không allowlist / chuỗi giống SQL | PASS | ValidationError trước repository; không đưa chuỗi vào SQL. |
| Prompt injection và tenant override trong request | PASS | Integration MySQL: kết quả vẫn current tenant; provider không được gọi; không phản hồi system prompt/credentials. |
| Người dùng chưa đăng nhập | PASS | Request có CSRF token hợp lệ bị redirect khỏi route assistant. |
| Truy cập tenant khác qua service | PASS | `require_actor` từ chối user không phải member của tenant đó. |
| Provider timeout, malformed output, 429, fallback mạng | NOT TESTED ở provider thật | Nhánh insight bỏ qua provider; các trường hợp provider khác không thuộc bài benchmark này. |
| Latency, token usage, chi phí | NOT MEASURED | Không có provider call; không ước tính chi phí giả định. |

## Ràng buộc mẫu và môi trường

MySQL user QA không có quyền tạo schema mới. Vì vậy test dùng schema `_test` có sẵn; schema chứa dữ liệu fixture từ các lượt trước. Không xóa fixture để tránh phá dữ liệu QA. Full Python regression có 380 tests: 2 failures, 15 errors, 0 skip. Các nguyên nhân quan sát được gồm actor/fixture cần một tenant duy nhất nhưng admin có nhiều membership, catalog count 23 khác expectation 22 và seed-date assertion không khớp dữ liệu cũ. Full browser run có 11 tests: 6 failures, 1 error; nguyên nhân quan sát gồm ảnh DB không có trong storage mới, fixture actor không có tenant context tường minh và tenant export pending. Bài insight Playwright đã được chạy độc lập sau khi sửa selector và PASS.

Không chạy screen reader, Firefox/Safari, provider thật, Vision, SMTP hay S3. Xem [ma trận test](TEST_MATRIX.md) và [UX review](PHASE51_AI_UX.md).
