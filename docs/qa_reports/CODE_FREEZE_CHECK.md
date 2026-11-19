# Rà soát trước code freeze — 25/10/2026

## Trạng thái Git

- Repo: `petcare-manager`, nhánh `solo/khang-petcare`.
- Working tree còn các sửa đổi/chương trình/tài liệu mới của cả 4 Phase và tài liệu bàn giao cuối; chúng chưa commit nên status chưa sạch. Đây không phải dấu hiệu xung đột.
- Index không có file unmerged; không có nội dung staged tại thời điểm rà soát. Tag `v1.0-demo-ready` chưa tồn tại.
- Lượt cuối chỉ tạo/sửa **tài liệu và bộ bằng chứng QA**, không thay logic trong `petcare/`, `run.py`, dependency hoặc tests; không thay trạng thái MySQL. Không stage, commit, tag hoặc push.
- Thư mục gốc repo không có file `phase*-report.md` hay Excel/PDF QA rơi vãi. Các bản bàn giao nằm ngoài repo; đã tạo archive 27 file tại thư mục này, khoảng 1,95 MB. Bản gốc ngoài repo được giữ để liên kết cũ không hỏng.
- `.env`, backup và ảnh upload vẫn bị gitignore. Không kèm `work/`, key/SQL backup hoặc venv vào QA. Manifest checksum kiểm đủ 27 file; Markdown đổi link cho portable, binary giữ byte gốc.

## petcare.i18n

- Diff với Git chỉ có comment `# pyrefly: ignore[missing-import]` trước `from flask import g, session`.
- Byte-for-byte trùng snapshot trước Phase 1; SHA-256: `c934f5b9b201200616c28b0b03e1b7c7772f5590f9b4213711a51cdfb7c1132f`.
- Comment không thay hành vi runtime; không có xung đột với bốn Phase. Module mới dùng `ui_text()`/copy VI–EN tại chỗ để giữ phần việc i18n có sẵn.
- Rà literal `t()` trên toàn template có **4 nhãn chưa được dịch English**:

| Nhãn fallback VI | Vị trí |
|---|---|
| Tồn kho | `petcare/templates/products/detail.html` |
| Gợi ý | `petcare/templates/pets/search_image.html` |
| Ngày | `petcare/templates/partials/business_chart.html` |
| Thêm | `petcare/templates/partials/pos_card.html` |

Đây là thiếu sót copy UI khi chọn English, không phải exception hoặc lỗi nghiệp vụ. Không thay i18n trong lần đóng băng này. Rà literal không đồng nghĩa kiểm đủ mọi chuỗi động/email hoặc chứng nhận English hoàn toàn.

## Kiểm chứng cuối

- Chạy lại **171/171 unit** (3,629 giây) và **55/55 web** (1,228 giây): đạt, không fail/error/skip; có regression locale/translation và form/POS/AI/report.
- Không chạy lại MySQL integration vào database dev. Bằng chứng toàn bộ Phase 4 vẫn là **283/283 Python** (171 unit, 55 web, 57 MySQL integration trên `_test` riêng) và **19/19 JavaScript** ở [ma trận chính thức](../phase4_acceptance.md).
- `git diff --check`, kiểm index conflict, checksum archive và các liên kết trong tài liệu mới/archive: đạt.
- Cẩm nang có đúng **10** câu hỏi, bản đồ file/function của đủ **5** điểm nhấn. Đã nêu giới hạn signed snapshot không mã hóa, LSH là gần đúng, nhánh ảnh có lọc dùng batch, restock là heuristic và provider chưa live-test.

Để commit và tạo tag, nhóm tự làm theo [CODE_FREEZE_GIT_GUIDE.md](../../CODE_FREEZE_GIT_GUIDE.md). Chỉ đặt tag khi commit thành công và status sạch; tag chỉ chứa dữ liệu Git đã commit, không thay thế backup MySQL/ảnh/.env.
