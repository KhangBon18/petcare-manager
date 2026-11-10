# Phase 5.2 — Điều kiện bắt đầu

Ngày đánh giá: 2026-11-10.

## Quyết định

**GO có điều kiện cho Phase 5.2 implementation trên môi trường test cô lập, dùng ảnh synthetic hoặc được cấp phép và provider mock/off.** Phase 5.1.1 đã khôi phục full regression trên MySQL/storage dùng một lần: Python 380/380 hai lần, JavaScript 31/31, Playwright 11/11 hai lần, không skip.

**NO-GO cho gọi provider trả phí, ảnh khách hàng/production, hoặc triển khai/migration development/production.** Việc này cần scope riêng, endpoint/credential/retention/budget review và quyền sử dụng dữ liệu rõ ràng. `petcare_shop_dev` vẫn có `/readyz=503`; không được dùng làm QA.

## Bằng chứng sẵn sàng

- Test isolation có Compose MySQL 8.4 schema mới trong tmpfs và media/export path riêng.
- AI Assistant top-products vẫn qua MySQL integration và browser regression trong full suites.
- Tenant context được truyền rõ trong các MySQL service tests; fixture cleanup hậu kiểm không để record test-owned hoặc orphan audit events.
- Bandit, hai lockfile audits, `pip check`, `compileall`, Docker build và Compose checks PASS local.
- Xem [kết quả cuối](PHASE511_FINAL_TEST_RESULTS.md), [recovery](PHASE511_REGRESSION_RECOVERY.md) và [QA isolation](QA_TEST_ISOLATION.md).

## Gate cho Phase 5.2

1. Chọn một hành vi Vision đọc-only, field allowlist và abstain threshold; không tự ghi hồ sơ.
2. Dùng bộ ảnh synthetic/được phép, nhãn độc lập và điểm đo per-field precision/recall/abstain.
3. Giữ endpoint provider tắt mặc định; kiểm tra timeout, 429/5xx, malformed JSON, sai enum và fallback bằng mock.
4. Xác nhận resize/MIME/EXIF, PII, retention, tenant ownership, egress và log redaction trên QA trước khi provider thật.
5. Nếu cần provider thật, xin phê duyệt endpoint, vùng lưu trữ, retention, giới hạn budget và credential handling trước khi chạy; chỉ gửi ảnh test được duyệt.
6. Sau thay đổi, chạy full Python, JavaScript và Playwright trên môi trường QA cô lập. Hosted CI cần quan sát riêng sau push/PR.

Phase 5.2 chưa bắt đầu trong sprint recovery này.
