# Công việc còn lại sau Phase 3

Ngày: 2026-11-09. Danh sách này tách công việc còn mở khỏi những thay đổi đã triển khai; không coi đề xuất là kết quả đã xác minh.

## Ưu tiên và điều kiện hoàn tất

| Ưu tiên | Hạng mục | Trạng thái hiện tại | Công việc còn lại / tiêu chí hoàn tất |
|---:|---|---|---|
| 1 | Readiness của `petcare_shop_dev` | **BLOCKED tại approval boundary**; clone migration PASS, DB dev vẫn 20 bảng và `/readyz` 503 | Người sở hữu DB cần duyệt rõ việc thay đổi schema dev. Trước đó phải xác minh backup và restore, đối chiếu clone/source schema, xác nhận dừng ứng dụng/worker ghi DB, rồi theo [DB_READINESS_REMEDIATION.md](DB_READINESS_REMEDIATION.md) chạy migration, kiểm row counts/invariants/markers/constraints/readiness và lưu biên bản. Chưa có authorization nên không áp dụng DDL. |
| 2 | Browser refund workflow | Route + MySQL integration **VERIFIED**, browser submit **NOT TESTED** | Dùng browser harness có thể accept/observe confirm dialog, chỉ trên `petcare_phase3_browser_test`; assert validation, flash, invoice/ledger/stock sau partial/full, retry và lỗi. Không kết nối gateway hoặc chuyển tiền. |
| 3 | Browser regression trong CI | **NOT IMPLEMENTED** | Thêm tối thiểu một runner headless dùng DB/storage `_test`, seed riêng, screenshot/artifact không chứa secrets. Bao gồm refund, export, account/RBAC và responsive smoke; không dùng `petcare_shop_dev`. |
| 4 | Account security và onboarding | Partial browser / backend coverage hiện có | Chạy browser flows với mail outbox stub cho password reset/change, email verify, invitation/revoke, owner transfer và hết hạn/replay; kiểm token one-time, role/tenant boundary, audit, session revoke và message an toàn. Không gửi SMTP thật. |
| 5 | Accessibility + request failures | **NOT TESTED đầy đủ** | Keyboard-only/focus, accessible names/labels, screen reader spot checks, contrast, zoom 200%, modal/confirm focus; capture request status/timings bằng browser runner. Sửa lỗi có reproduction và chạy regressions. |
| 6 | Security scan ngoài Bandit | **NOT TESTED** | Chạy Trivy filesystem và image scan, rồi GitHub Actions workflow; phân loại findings dựa trên exact package/image và cập nhật report. Trivy CLI không có trên môi trường vừa chạy. |
| 7 | Favicon request | **OPEN P3** | `/static/favicon.svg` trả 200; browser mặc định `/favicon.ico` trả 404. Chỉ thêm route/alias nếu cần; xác minh request 200 và không ảnh hưởng asset. |
| 8 | SMTP, AI/AI Vision, S3 | **NOT TESTED thật** | Nếu cần nghiệm thu provider, cấp staging endpoint/test bucket/mail sink và synthetic data. Đo timeout/fallback/privacy/cost/retention; không bật production mặc định. |
| 9 | Performance/concurrency/coverage | **NOT TESTED** | Đo baseline và xác định ngưỡng trước khi tối ưu; bổ sung stress/branch coverage có mục tiêu, ưu tiên refund/purchase receiving và export worker. Không tăng hạ tầng nếu chưa có dữ liệu. |

## Rủi ro triển khai DB dev

MySQL DDL có thể implicit-commit. Migration code đã kiểm tra mọi hàng mục tiêu trước khi thay các money check; clone đã có 0 vi phạm, nhưng việc áp dụng lên DB dev vẫn có thể thất bại do backup/permission, khác biệt index hoặc môi trường thực. Giữ bản dump ngoài repo, xác minh restore trên clone, lên lịch maintenance, xác nhận process ghi DB đã dừng và có người duyệt. Nếu bất kỳ precondition nào không đạt, không chạy initializer. Runbook chứa lệnh sao lưu/kiểm tra và recovery.

## Trạng thái hiện tại

- Python: 369/369 PASS; JavaScript 28/28 PASS.
- Bandit CI gate, pip-audit, compileall, pip check, Docker Compose config/build và diff check PASS.
- Browser đã kiểm account display name, RBAC, export ready/download và viewport 390/820/1440; refund POST chưa được browser xác minh.
- Clone migration `/readyz` 200. Dev `/readyz` vẫn 503, không đổi.
- Không có xác minh đầy đủ accessibility, request-level network, Trivy/hosted CI, SMTP, real AI/Vision, S3, load, hoặc production deployment.

## Đề xuất sprint kế tiếp

1. Xin duyệt rõ việc thay đổi schema `petcare_shop_dev`; nếu chưa được duyệt, tiếp tục dùng test/clone và giữ readiness là blocker.
2. Hoàn tất browser refund với confirm handling, rồi thiết lập browser smoke trong CI cho QA schema.
3. Thêm mail stub cho account recovery/invitation flows và kiểm authorization/session behavior.
4. Hoàn tất accessibility/network audit và chạy Trivy/hosted CI.
5. Chỉ sau đó mới nghiệm thu staging integrations; giữ AI/SMTP/S3 thật ngoài phạm vi nếu chưa được cấp sandbox.

Không gọi ứng dụng production-ready cho đến khi các môi trường cần triển khai đã migration có kế hoạch được duyệt, browser/security gates chạy trong CI, và các tích hợp thật được kiểm trong sandbox tương ứng.
