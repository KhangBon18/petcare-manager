# Phase 6.1 — ma trận nghiệm thu

`PASS` chỉ áp dụng cho workflow có bằng chứng thực thi. `PARTIAL` nghĩa là backend/service được test nhưng không đi hết bằng browser. Mọi test data là tổng hợp trong schema QA `_test` trên tmpfs.

| ID | Module / luồng | Kết quả mong đợi | Kết quả quan sát và bằng chứng | Trạng thái | Tác động demo |
|---|---|---|---|---|---|
| ACC-AUTH-01 | Admin login/dashboard | Phiên hợp lệ vào dashboard | Full Playwright 18/18; login trên store `main` | PASS | Có thể demo |
| ACC-AUTH-02 | Staff và route admin | Chỉ mở route được role cho phép | `test_staff_role_restriction_and_allowed_customer_access`; 403 `/users/` mong đợi | PASS | Có thể demo |
| ACC-CUST-01 | Tạo/sửa customer và validation | Dữ liệu lưu, lỗi form rõ | `test_customer_pet_workflow_and_responsive_navigation`; MySQL workflow/persistence | PASS | Có thể demo |
| ACC-PET-01 | Pet profile và customer/buyer link | Quan hệ profile chính xác | Browser workflow + MySQL; customer detail và pet detail link qua lại | PASS | Có thể demo |
| ACC-PROD-01 | Product create/edit/search | UI khớp MySQL | `test_product_inventory_to_pos_checkout_workflow` | PASS | Có thể demo |
| ACC-INV-01 | Stock adjustment/ledger/invalid negative | Không âm tồn; ledger khớp | Browser thử -3 bị từ chối và tồn không đổi; +1 được ghi; MySQL atomic tests | PASS | Có thể demo |
| ACC-PO-01 | Tạo PO, nhận một phần/toàn phần, hủy | State và stock nhất quán | `test_purchase_order_create_partial_full_receive_and_close`; nhận 2/5 rồi 3/5, stock 2→4→7 | PASS | Có thể demo |
| ACC-PO-02 | Duplicate/replay, sai transition, rollback | Từ chối trạng thái sai, không nhận hai lần | `tests/integration/test_mysql_purchasing.py`: replay idempotency, invalid transitions, duplicate after close, rollback | PASS (MySQL integration) | Replay chưa chạy bằng browser riêng |
| ACC-POS-01 | Product lookup, cart/qty/estimate, payment | Server xác nhận giá; trừ stock một lần | `test_product_inventory_to_pos_checkout_workflow`; payment MySQL integration | PASS | Có thể demo |
| ACC-POS-02 | Catalog HTTP 503/retry | Giữ cart và phục hồi | `test_pos_catalog_503_shows_retry_and_preserves_cart` | PASS | Có thể demo |
| ACC-REF-01 | Refund confirmation, zero/over, partial/full, retry | Dismiss không POST; ledger/stock nhất quán | `test_browser_refund_confirmation_validation_idempotency_and_persistence`; MySQL route/rollback tests | PASS | Chỉ ghi nhận hoàn; không gọi provider |
| ACC-REP-01 | Report period, doanh thu, top products, responsive | UI khớp service | `test_reports_real_filters_values_export_and_responsive_products`; joined journey | PASS | Có thể demo |
| ACC-REP-02 | XLSX snapshot | File khớp snapshot và content type | Browser report export + Python/web tests | PASS | Có thể demo |
| ACC-EXP-01 | Tenant export worker/status/download | Artifact local riêng tư; trạng thái đúng | `test_tenant_export_job_runs_and_downloads_in_isolated_storage` | PASS | Cần local key/storage và worker |
| ACC-AI-01 | Top-selling products | Fact từ report service/tenant hiện hành | `test_assistant_top_products_renders_live_report_facts_on_mobile` | PASS | Có thể demo local |
| ACC-AI-02 | Restock và purchase status | Tồn/ngưỡng/PO status chính xác, role admin | Assistant browser + `test_assistant_inventory_and_purchase_status_use_real_tenant_services` | PASS | Có thể demo local |
| ACC-AI-03 | Operations overview | Card/link từ business services | `test_assistant_operations_overview_uses_live_services_and_reduces_interactions` | PASS | Có thể demo local |
| ACC-AI-04 | Ambiguous/out-of-scope/data failure/tenant spoof | Không bịa hoặc vượt tenant | Unit/MySQL/browser retry; provider không gọi | PASS theo test; live model NOT TESTED | Chỉ demo local |
| ACC-VIS-01 | Upload/suggestion/blank-only apply | Admin review, không tự save/ghi đè | Vision browser E2E, ảnh synthetic, mock loopback | PASS — MOCKED | Phải nói rõ là mock |
| ACC-VIS-02 | Invalid image/provider error/retry/staff denial | Lỗi có thể phục hồi; staff bị chặn | `test_provider_unavailable_malformed_ambiguous_and_manual_retry_states`, upload validation, staff restriction | PASS — MOCKED | Có thể demo mock |
| ACC-OPS-01 | `/healthz`, `/readyz`, DB unavailable | Health còn sống, readiness báo DB | QA 200/200; cổng DB không lắng nghe cho 200/503, Flask sống | PASS | Có thể demo QA |
| ACC-OPS-02 | `/workersz` unavailable → recovery | 503 khi thiếu heartbeat, 200 đủ worker | QA markers xóa riêng: 503; chạy 2 worker: 200 | PASS | Cần chạy worker |
| ACC-USER-01 | Team/invite/ownership/store settings/audit | Role/scope/audit đúng | Backend/web/MySQL suites trong 421 tests; không đi hết các workflow bằng browser | PARTIAL | Không demo thay đổi owner/invite nếu chưa luyện |
| ACC-MEDIA-01 | Media/pet photo/S3 | Media đúng tenant/storage | Preflight kiểm 68 ảnh local; Vision upload browser; mọi CRUD media và S3 chưa đi hết | PARTIAL | Chỉ synthetic/local |
| ACC-METRIC-01 | Metrics endpoint | Metric không lộ dữ liệu tenant | Service/route test; không mở bằng browser | PARTIAL | Không dùng làm demo feature |
| ACC-EXT-01 | SMTP, live AI/Vision, S3, payment | Tích hợp thật hoạt động an toàn | Không bật/call; chỉ mock/local | NOT TESTED | Không tuyên bố đã tích hợp thật |
| ACC-A11Y-01 | axe + keyboard/focus | Không violation ở scan; thao tác chính keyboard được | 31 scans + 5 Vision states, 0 violation; incomplete được liệt kê riêng | PASS có giới hạn | Không phải WCAG sign-off |
| ACC-A11Y-02 | Screen reader + zoom thật 200% | Dùng được cùng AT/zoom | Không chạy screen reader; 720px chỉ mô phỏng viewport | NOT TESTED | Hạn chế đã biết |
| ACC-XBR-01 | Firefox/WebKit route smoke | Login, route và responsive cơ bản | Hai engine: 6 route chính trả 200 ở 390px, không overflow; WebKit CSP warnings | PASS có giới hạn | Safari effect cần follow-up |
| ACC-DEPLOY-01 | Production deployment/config/DB | Production-safe readiness và rollback | Không kết nối production; image build không phải deployment | NOT TESTED | NO-GO production |

## Tổng hợp phạm vi

- Automation: Python **421/421**, JavaScript **40/40**, Chromium Playwright **18/18**.
- Browser thật: journeys trên Flask/MySQL QA; Firefox/WebKit chỉ smoke route/viewport.
- Manual: screenshot dashboard/POS/report đã xem; incomplete axe được đọc lý do. Screen reader, zoom thật, contrast meter chưa chạy.
- External integrations: **NOT TESTED**, trừ Vision mock và export/email worker chạy local với SMTP tắt.
