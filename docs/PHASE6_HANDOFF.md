# Phase 6 handoff

Ngày: 2026-11-11. Nền tảng giao: Flask/Jinja/MySQL, Phase 5.5 operations overview.

## Trạng thái sẵn sàng

Một workflow intelligence hữu ích đã được giao và xác minh trên disposable MySQL QA. Full Python 421/421, JavaScript 40/40, Playwright 18/18; targeted overview rerun 1/1. Bandit CI gate, dependency audits, compile, Compose QA config, Docker build và diff check pass.

Đủ cơ sở để Phase 6 tiếp tục kiểm chứng UX/read-only workflow và đo hiệu năng theo quy mô. Chưa đủ bằng chứng để bật AI/Vision provider, khẳng định production readiness hoặc thay đổi schema dev/prod.

## Cách chạy an toàn

1. Đọc [QA_TEST_ISOLATION.md](QA_TEST_ISOLATION.md).
2. Tạo MySQL QA schema mới kết thúc `_test` từ `compose.qa-test.yml` (tmpfs, project name riêng); cấu hình `DB_NAME` và `PETCARE_TEST_DB_NAME` cùng giá trị.
3. Dùng storage riêng dưới `/tmp` cho pet/product/export và browser artifact.
4. Đặt AI URL/key/model trống, `AI_VISION_ENABLED=0`, mail/S3 tắt.
5. Khởi động `.venv/bin/python run.py`; xác nhận `/healthz=200`, `/readyz=200` trên QA rồi mới mở browser.

Không dùng `.env` mặc định nếu nó trỏ vào `petcare_shop_dev`; không chạy migration/seed/test vào dev/prod. Hướng dẫn chính xác về env, Compose và cleanup chỉ trong [QA_TEST_ISOLATION.md](QA_TEST_ISOLATION.md).

## Roles, routes và modules liên quan

- Membership roles: `admin`, `staff`; actor role được nạp lại từ MySQL mỗi request.
- Assistant UI nằm trong `base.html`; API là POST `/assistant/chat` với session, CSRF và rate limit.
- Inventory: `restock_service`; overview và purchase status chỉ admin vì overview cần purchasing data.
- Sales context: `report_service.top_products_for_period(..., "7d")`.
- CTA mở `/products/<id>`, `/purchasing/<id>`, `/purchasing/`, `/reports/?start=...&end=...`.
- Product, inventory, purchase, report và invoice module giữ route/API/business rules hiện có.

## Contract không được phá

- Giữ envelope assistant `reply`, `mode`, các insight Phase 5.1–5.4 và request JSON cũ.
- New `insight.kind="operations_overview"` được mô tả tại [API_CONTRACT.md](API_CONTRACT.md); top-level status mới của overview là `ok`, `partial`, `forbidden` hoặc `unavailable`.
- Tenant luôn lấy từ server session. Không lấy tenant ID, role, SQL/filter structure hoặc link từ user text.
- Purchase service là admin authorization gate. Khi staff bị từ chối, tuyệt đối không trả inventory/sales payload.
- Giữ 5 item/nhóm trong overview, exact count từ service, sales kỳ 7d, cùng-origin URLs và `textContent`.
- Không biến recommendation thành write action. Không tạo PO, nhận/hủy PO hay thay stock/customer data từ assistant.

## Giới hạn hiện tại

- Phrase matching VI/EN, không hỗ trợ câu tùy ý/custom date trong overview.
- Ba source reads không atomic; inventory recommendations duyệt active catalog để có exact total.
- Overview không cung cấp sales total/invoice count; sales section là top-selling context.
- Axe incomplete items/manual screen reader/200% zoom/cross-browser chưa xử lý.
- Real AI, Vision, SMTP, S3, provider privacy/region/retention/cost chưa xác minh; không bật egress trong Phase 6 mặc định.
- `petcare_shop_dev` readiness/schema không được chạm trong Phase 5.5.

## Đề xuất thứ tự Phase 6

1. Hoàn thành keyboard-only, screen reader và browser zoom 200% trên overview; xử lý incomplete nếu có finding thực.
2. Chạy acceptance với admin/staff trên staging/test tenant tổng hợp, hỏi về relevance/clarity của từng nhóm và wording.
3. Benchmark thời gian `restock_service` theo kích thước catalog rồi mới cân nhắc tối ưu; thêm regression giữ công thức/total trước khi sửa query.
4. Thu câu hỏi overview ẩn danh hoặc synthetic để kiểm intent VI/EN và false positives trước khi thêm phrase.
5. Chỉ xem xét AI/provider sau package riêng về dataset rights/consent, privacy/region/retention, cost/attempt guard, evaluation labels và approval.

Files Phase 5.5: [implementation](PHASE55_IMPLEMENTATION.md), [workflow](PHASE55_INTELLIGENCE_WORKFLOW.md), [AI evaluation](PHASE55_AI_EVALUATION.md), [UX verification](PHASE55_UX_VERIFICATION.md).
