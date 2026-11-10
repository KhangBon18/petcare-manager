# Phase 5.3 — Điều kiện sẵn sàng cho provider Vision

## Quyết định

**NO-GO cho provider thật ở thời điểm này.** Phase 5.2 hoàn tất integration kỹ thuật bằng mock loopback và ảnh synthetic; chưa có bằng chứng model accuracy, privacy terms, provider retention, region, egress hoặc chi phí thực tế.

## Điều kiện cần được duyệt trước khi gửi ảnh ra ngoài

1. Provider/model và endpoint allowlist; owner vận hành, timeout, quota, budget cap và kill switch.
2. Data-processing terms: region, retention, training/reuse policy, deletion, logs, incident handling và credential rotation.
3. Danh mục ảnh được cấp quyền và xác nhận không chứa dữ liệu khách hàng/nhân viên không cần thiết.
4. Bộ đánh giá có nhãn độc lập, protocol per-field precision/recall/abstain, failure taxonomy và ngưỡng chấp nhận.
5. Human-review flow, wording uncertainty, retention/log policy và quy trình disable/rollback.
6. Security review endpoint/network, secrets handling, request/response limits, timeouts, rate limits và cost monitoring.
7. Approval tường minh cho môi trường/staging được chỉ định. Không dùng petcare_shop_dev hoặc production để thử nghiệm.

## Lộ trình sau khi được duyệt

1. Chạy offline evaluation trên dataset được phép, không network egress.
2. Review false-positive/ambiguous cases với người nghiệp vụ; chốt abstain threshold cho từng field.
3. Chạy smoke staging có quota thấp, ảnh đã duyệt, synthetic identifiers và provider logs tối thiểu.
4. Xác minh retention/deletion, aggregate latency/cost, timeout/429/5xx fallback và kill switch.
5. Mở giới hạn theo tenant nhỏ sau approval; giữ opt-in, admin review, no auto-save và default off nếu config thiếu.
6. Theo dõi drift/feedback an toàn; quay về local-only khi vượt error/cost/privacy budget.

## Rollback và tiêu chí đóng gate

Tắt AI_VISION_ENABLED để quay về local-only; suggestion không persistence. Gỡ credential khỏi deployment secret store theo quy trình vận hành, không ghi credential vào repository/log. Không cần migration rollback vì Phase 5.2 không đổi schema.

Không bật provider cho dữ liệu thật trước khi approval records, dataset rights, evaluation thresholds, budget, endpoint, retention and operational rollback được xác nhận và test lại trên staging cô lập. Phase 5.2 chưa đáp ứng điều kiện này.
