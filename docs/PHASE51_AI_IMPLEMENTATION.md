# Phase 5.1 — Trợ lý AI và insight bán hàng

Ngày thực hiện: 2026-11-10. Đây là một lát cắt bổ sung cho Flask/Jinja/MySQL hiện hữu; không thay framework, migration, schema hay workflow bán hàng.

## Kết quả

Trợ lý nhận câu hỏi tiếng Việt/Anh về sản phẩm bán chạy theo kỳ, lấy dữ liệu bằng report service hiện có, trả thứ hạng và liên kết hồ sơ sản phẩm. Đây là câu trả lời xác định từ MySQL, không phải câu trả lời do LLM tạo. Các câu hỏi được nhận diện không đi tới provider, kể cả khi provider được cấu hình.

Kỳ được phép: hôm nay, 7 ngày gần nhất (mặc định), tuần hiện tại, tuần trước, tháng hiện tại và tháng trước. Kỳ rõ ràng chưa hỗ trợ (ví dụ hôm qua hoặc 30 ngày) nhận câu hỏi hướng dẫn; không âm thầm trả về kỳ mặc định. Kết quả chỉ giữ tối đa 5 sản phẩm có số lượng bán ròng dương. Cách xếp hạng tuân theo `report_repo.top_products`: số lượng ròng giảm dần, doanh thu ròng giảm dần làm tiêu chí phụ; hoàn/đổi được trừ theo semantics của báo cáo hiện hành.

## Kiến trúc đã kiểm tra

- `POST /assistant/chat` yêu cầu phiên đăng nhập, CSRF và giới hạn request account/IP.
- `assistant_routes.py` chuyển actor/tenant từ request context sang `assistant_service.answer()`.
- `assistant_service.py` nhận diện intent bán chạy trước khi tạo context chung hoặc gọi provider.
- `report_service.top_products_for_period()` xác thực actor bằng `require_actor`, đổi ngày theo timezone tenant và gọi `report_repo.top_products()` với cửa sổ thời gian có bind parameters.
- Repository dùng `@petcare_tenant_id`, trả tối đa 10 hàng; service lọc hàng không có bán ròng dương và giới hạn API ở 5.
- Route tạo URL `/products/<id>` và chuỗi tiền đã định dạng. Frontend tạo node DOM, dùng `textContent`, chỉ chấp nhận URL nội bộ `/products/<số>`.

Không có thay đổi schema/database migration. API chỉ thêm field tùy chọn `insight`; `reply`, `mode` và `catalog` hiện có vẫn giữ nguyên.

```json
{
  "reply": "Sản phẩm bán chạy tuần này ...",
  "mode": "local",
  "insight": {
    "kind": "top_products",
    "period": "week",
    "start_date": "2026-11-09",
    "end_date": "2026-11-10",
    "currency_code": "VND",
    "items": [
      {"product_id": 23, "code": "QA-1", "name": "QA product",
       "quantity_sold": 3, "revenue": "30000.0000",
       "url": "/products/23", "revenue_label": "30.000 VND"}
    ]
  }
}
```

## Baseline, checkpoint và commit strategy

Trước thay đổi Phase 5.1, branch `solo/khang-petcare` ở HEAD `8634300f4b5ad4700d6702a048220d6597c4e200` đã có 103 tracked file thay đổi và 985 đường dẫn untracked từ các sprint trước. Không stage, reset, stash, clean hay commit các thay đổi đó.

Checkpoint ngoài repository: `/Users/heisenbon/Documents/Codex/petcare-phase51-checkpoint-20261110`. Có HEAD, branch, status, binary diff, danh sách/tar untracked và `SHA256SUMS`; toàn bộ checksum được kiểm tra PASS trước khi sửa mã. Checkpoint không được xem là commit.

Đề xuất khi tạo commit sau này: review rồi stage theo danh sách file Phase 5.1 (service, route, template/i18n/JS, test mới/sửa và tài liệu Phase 5.1); giữ nguyên mọi thay đổi có trước. Chưa tạo commit hoặc stage file trong lượt này.

Schema QA đang dùng có hậu tố `_test`, được xác nhận khớp guard `PETCARE_TEST_DB_NAME`; `/readyz` trả 200 khi browser runner khởi động Flask. Tài khoản DB QA không có quyền tạo schema mới; không xóa hay dọn dữ liệu QA hiện có. Không truy cập hoặc sửa `petcare_shop_dev`/production.

## Kiểm chứng thực tế

- Baseline 2 câu hỏi bán chạy (VI/EN) trả fallback catalog, không có field insight và không có số lượng bán: **0/2** theo tiêu chí grounding.
- Sau thay đổi: một request API/MySQL cho staff được đối chiếu trực tiếp với report service, và một workflow Chromium dùng suggestion trên viewport 390 px được đối chiếu tên/số lượng/link: **2/2** theo cùng tiêu chí.
- Pytest cho 7 unit mới + 1 MySQL route integration: **8 passed**, 13 subtests.
- Unit + web bằng pytest: **314 passed**, 422 subtests.
- JavaScript: **31/31 PASS**.
- Browser test mới chạy riêng trên Flask thật: **1/1 PASS**; `/readyz=200` trước khi test.
- Full Python `unittest discover`: **380 tests; 2 failures, 15 errors, 0 skip** trên QA schema hiện hữu. Nhiều fixture cũ cần tenant duy nhất/tường minh; một test còn mong đợi 22 sản phẩm trong khi schema có 23 và seed-date assertion không khớp dữ liệu cũ. Đây không phải run PASS.
- Full browser suite: run **11 tests, FAILED** (6 failures, 1 error). Có lỗi storage ảnh fixture, actor không chọn tenant tường minh và tenant export còn pending. Bài test insight ban đầu chọn selector quá rộng; đã sửa và chạy riêng PASS. Không chạy lại cả suite sau khi phát hiện các fixture QA cũ không ổn định.
- Bandit đúng lệnh CI exit 0; `pip-audit` cho cả hai lockfile không phát hiện advisory; `pip check`, `compileall`, `git diff --check`, `docker compose config --quiet` và Docker build PASS.

Pytest 9.2.0 được cài tạm trong `.venv` để đáp ứng bước QA; không thêm pytest vào requirements/lockfiles. Không gọi AI provider trả phí, SMTP, S3 hoặc Vision thật.

## Phạm vi còn lại

Provider thật, timeout/malformed response/cost/latency của provider chưa được đo. Full integration/browser regression chưa sạch do trạng thái test database/media fixture có sẵn; xem [đánh giá](PHASE51_AI_EVALUATION.md) và [ma trận test](TEST_MATRIX.md). Không khẳng định production readiness.

## Tài liệu Phase 5.1

- [Capability matrix](PHASE51_AI_CAPABILITY_MATRIX.md)
- [Evaluation](PHASE51_AI_EVALUATION.md)
- [Security review](PHASE51_AI_SECURITY.md)
- [UX review](PHASE51_AI_UX.md)
- [Handoff Phase 5.2 Vision](PHASE52_VISION_HANDOFF.md)
