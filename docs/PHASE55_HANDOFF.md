# Phase 5.5 handoff

Ngày: 2026-11-10. Phase 5.4 hoàn tất hai capability assistant đọc-only. Phase 5.5 nên giữ scope nhỏ và tiếp tục chạy offline.

## Chạy và test an toàn

- Theo hướng dẫn `docs/QA_TEST_ISOLATION.md` để bật Compose MySQL QA schema `*_test` và thư mục storage riêng. Không dùng `.env` mặc định nếu đang trỏ `petcare_shop_dev`; đặt `DB_NAME=PETCARE_TEST_DB_NAME` cùng DB credentials riêng cho test.
- Chạy web trong local QA: `.venv/bin/python run.py`, sau khi đã export DB/port/storage QA. Kiểm tra `/healthz` và `/readyz` trước workflow.
- Giữ `AI_API_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, mail và S3 unset/empty; `AI_VISION_ENABLED=0`. Vision e2e hiện chỉ dùng mock loopback test.
- Test gates: `.venv/bin/python -m unittest discover -s tests -v`, `node --test tests/js/*.test.cjs`, `AXE_CORE_PATH=tests/a11y/node_modules/axe-core/axe.min.js .venv/bin/python scripts/browser_smoke/run_smoke.py`; chạy Bandit và audit commands từ `docs/QA_TEST_ISOLATION.md`.

## Vai trò và routes

- Vai trò ứng dụng là `admin` và `staff` trong membership tenant.
- Assistant: POST `/assistant/chat`, cần session + CSRF, rate-limited.
- Inventory insight: authenticated member trong tenant hiện tại; dùng `restock_service`.
- Purchasing status: admin trong tenant hiện tại; dùng `purchase_service`. Staff nhận phản hồi permission-aware, không có counts/record rows.
- Browser pages liên quan: `/products/`, `/products/<id>`, `/purchasing/`, `/purchasing/<id>`, dashboard và assistant panel toàn cục.

## Contract không được phá

- Giữ `reply` và `mode` (`local|ai`) trong response cũ; catalog và top-products fields hiện có tiếp tục tương thích.
- Mở rộng theo `insight.kind`: `inventory_restock` hoặc `purchase_status`; không đổi names/data semantics được mô tả ở [API contract](API_CONTRACT.md).
- Tenant scope đến từ server session, không từ JSON. Giữ authentication, CSRF, throttle, admin check, query parameterization và output cap.
- Nội dung business data đi vào DOM bằng text nodes; href luôn do server sinh và được allowlist.

## Hướng tiếp theo

1. Chỉ thêm alias/intent theo usage thực tế; bổ sung VI/EN negative/ambiguity cases trước khi mở rộng.
2. Review 40 axe incomplete assistant nodes bằng keyboard-only, screen reader và browser zoom thật.
3. Theo dõi kích thước catalog trước khi tối ưu restock aggregation; đo trước và giữ công thức `restock_service` là nguồn sự thật.
4. Giữ assistant read-only. Tạo/nhận/hủy PO tự động không thuộc Phase 5.5 mặc định.
5. Real AI/Vision pilot vẫn bị block bởi dataset rights/consent, independent labels, provider region/retention/privacy, cost guard và approval package trong `PHASE53B_PROVIDER_PILOT.md`; không bật chỉ để hoàn thiện assistant.

## Evidence Phase 5.4

- Python 415/415, JavaScript 38/38, full Playwright 17/17 và assistant browser rerun 1/1, Bandit CI gate pass, cả hai `pip-audit` không có known vulnerabilities, npm audit 0 vulnerabilities, pip check/compile/Compose/Docker build/diff check pass. Python 415 và assistant browser rerun dùng disposable MySQL test schemas.
- Ảnh: [inventory desktop](assets/phase54/assistant-inventory-desktop.png), [purchasing desktop](assets/phase54/assistant-purchasing-desktop.png), [purchasing mobile](assets/phase54/assistant-purchasing-mobile-390.png).
- Live provider, full screen-reader audit, hosted Actions/Trivy và `petcare_shop_dev` readiness **không được kiểm tra trong Phase 5.4**.
