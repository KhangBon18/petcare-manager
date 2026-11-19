# Bằng chứng QA — Phases 1–4

Đóng gói ngày **25/10/2026** trước code freeze. Bộ này gồm **27 file** báo cáo, ảnh kiểm giao diện, Excel/PDF mẫu và log kết quả công khai đã bàn giao; tổng khoảng **1,95 MB** (chưa tính README/manifest). Đây là dữ liệu nghiệm thu lịch sử của đồ án, không phải số liệu cửa hàng đang chạy.

| Giai đoạn | Tài liệu / bằng chứng chính |
|---|---|
| Phase 1 | [Báo cáo](phase1-report.md), [form khách](phase1-customer-validation.png), [validation hóa đơn](phase1-invoice-validation.png) |
| Phase 2 | [Báo cáo](phase2-report.md), [POS desktop](phase2-pos-desktop.png), [POS mobile](phase2-pos-mobile-order.png) |
| Phase 3 | [Báo cáo](phase3-report.md), [Excel mẫu](phase3-demo-report.xlsx), [PDF mẫu](phase3-demo-report.pdf), [card trợ lý](phase3-assistant-cards.png) |
| Phase 4 | [Báo cáo](phase4-report.md), [ma trận](phase4-acceptance.md), [log Python](phase4-python-final.log), [log JavaScript](phase4-js-final.log), [preflight](phase4-preflight-dev.json) |

- [manifest.json](manifest.json) ghi tên, kích thước và SHA-256 của 27 file; Excel/PDF/PNG/log/JSON giữ nguyên byte. Markdown chỉ đổi đường dẫn file bàn giao thành link tương đối để mở được khi clone sang máy khác.
- Bản bàn giao gốc trong thư mục `outputs/` của cuộc trò chuyện nằm **ngoài repo**, được giữ lại để các liên kết cũ còn dùng được. Không có báo cáo QA tạm/Excel/PDF rơi ở thư mục gốc repo.
- Không lấy file từ `work/`: không kèm venv/tooling, SQL backup mã hóa, key giải mã, media test, server log riêng hoặc file `.env`.
- Tài liệu nguồn hiện hành vẫn ở [nghiệm thu Phase 4](../phase4_acceptance.md), [kết quả test](../test_results.md), [kịch bản demo](../../DEMO_SCRIPT.md), [cẩm nang vấn đáp](../../DEFENSE_QA_GUIDE.md). Bản report trong thư mục này là snapshot, không thay thế tài liệu nguồn.
- PDF trình duyệt đã nghiệm thu ở Phase 3. Phase 4 có giao dịch QA mới nên không kỳ vọng workbook/PDF Phase 3 trùng dashboard sau đó. Muốn số mới, xuất lại từ cùng snapshot báo cáo đang xem.

Rà soát cuối về Git/i18n, bốn nhãn English fallback và kiểm tra tài liệu: [CODE_FREEZE_CHECK.md](CODE_FREEZE_CHECK.md).
