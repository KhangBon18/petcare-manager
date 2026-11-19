# Sprint 4.3 — Ưu tiên tiếp theo

Ngày đề xuất: 2026-11-10. Bảo toàn mô hình retail và các quyền/contract hiện tại; không mở rộng sang clinic, appointment hoặc thay framework.

| Thứ tự | Ưu tiên | Việc tiếp theo | Tiêu chí hoàn tất | Rủi ro |
|---:|---|---|---|---|
| 1 | P1 · Accessibility verification | Review tay 13 axe `incomplete` items; chạy screen reader/keyboard pass cho menu/nav mobile, remove-line, cart shortcut, error focus và forms. Thực hiện browser zoom 200% thật và kiểm ở 320 CSS px. | Kết quả theo WCAG criterion, browser/version, hành động keyboard và ảnh; không đánh đồng axe 0 violations với chứng nhận WCAG. | Thấp-vừa |
| 2 | P2 · Inventory responsiveness | Chạy stock adjustment/detail/history ở 320/390/768/820/1024/1440 và keyboard/touch. Rà soát long reason, history rỗng và lỗi delta âm/giới hạn số. | Giữ transaction/permission/tenant/stock ledger; browser QA MySQL assertions và không overflow. | Vừa |
| 3 | P2 · POS recovery | Throttle lookup để quan sát loading; kiểm network failure → retry, quick-customer preservation, refresh/back, duplicate HTTP submit/replay, empty cart và item hết tồn. | Cart và server total nhất quán sau mỗi lỗi; không duplicate invoice/movement; error message/action rõ. | Vừa-cao do giao dịch |
| 4 | P2 · Catalog scale | Dùng catalog synthetic dài, tìm kiếm theo mã/tên/danh mục, pagination, ảnh lớn/thiếu và tên dài; đo request/latency. | Server paging/filter semantics không đổi, không query unbounded, mobile action vẫn dễ tìm. | Vừa |
| 5 | P2 · CI/release evidence | Quan sát GitHub hosted workflow, dependency audit và browser-smoke artifacts; xác minh trên matrix Python được CI cấu hình. | Hosted result xanh và artifacts giữ theo policy; ghi version/dependencies. | Thấp |
| 6 | P3 · AI/optional | Chỉ benchmark local assistant/vision với bộ dữ liệu synthetic/được phép; không bật provider thật mặc định. | Accuracy/fallback/privacy/latency/cost có số liệu trước khi thêm UX hoặc provider. | Vừa |

Dev database readiness `/readyz=503` còn là blocker vận hành riêng. Không chạy migration vào `petcare_shop_dev` cho tới khi có backup mới đã restore-test, kế hoạch rollback và approval theo [DB readiness remediation](DB_READINESS_REMEDIATION.md) và [DB development approval gate](DB_DEV_MIGRATION_APPROVAL.md).
