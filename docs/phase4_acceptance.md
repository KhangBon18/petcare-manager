# Phase 4 — nghiệm thu tổng thể và đóng gói demo

Ngày nghiệm thu: **2026-10-25**, macOS, Python 3.13.3, Flask 3.1.3, MySQL Docker 8.4.11. Phạm vi: MVP local phục vụ đồ án; không mở rộng hạ tầng.

## Kết quả bộ kiểm

| Bộ kiểm | Kết quả |
|---|---|
| Python unit | **171/171** |
| Flask web | **55/55** |
| MySQL integration | **57/57** trên database `_test` mới, biệt lập |
| Tổng Python | **283/283**, 32,014 giây, không fail/error/skip |
| JavaScript | **19/19**, không bỏ qua |
| Python AST / Jinja / JS syntax | 143 file Python, 44 template, 9 file JS đạt |
| Dependency | `pip check` và `pip-audit -r requirements.txt` đạt, không advisory đã biết trong lần quét |
| Cấu hình / source | Compose config, `git diff --check`, Bandit theo baseline đạt |

Bandit giữ baseline hiện có; không phải scan không có ngoại lệ. Hai suppression mới tại worker subprocess đã review: chỉ chạy `sys.executable` với module/đối số cố định, không shell/không lệnh người dùng. Không thay baseline chung. Cảnh báo scanner về suppression B608 cũ không phải finding mới.

Hai database QA/test do lượt này tạo cùng scoped grant đã được dọn; không reset database có sẵn. Media kiểm thử nằm ngoài thư mục ảnh dev. Test cạnh tranh dùng kết nối/transaction MySQL thật.

## Ma trận kịch bản

| Kịch bản | Kiểm tra thực tế / kết quả | Tự động hóa hỗ trợ |
|---|---|---|
| Admin / Staff | Chrome: Admin mở trang Tài khoản; Staff không có menu và `/users/` hiển thị từ chối quyền. Staff vẫn bán hàng/xem báo cáo. | Web + MySQL auth/tenant/CSRF |
| Validation giữ dữ liệu | Khách: tên/địa chỉ còn, lỗi phone/focus đúng. POS: giả lập tồn thay đổi khi đang chọn 3 dòng; server giữ khách/ghi chú/dòng/số lượng, focus lượng lỗi. Sửa thông báo dài bị bó trong cột quantity. | `tests/web/test_phase1_forms.py`, regression mới kiểm vị trí cả lỗi item/quantity |
| Hóa đơn kết hợp | Chrome: thêm nhanh khách trong POS không mất hàng; 2 FOOD-001 + 1 ACC-001 + Miu = **2.250.000 VND**. Chưa thu vẫn tồn 10/5; thu xong 8/4, Miu sold/buyer đúng, 2 movement sản phẩm. | `test_payment_updates_stock_pet_and_revenue_once`, `test_invoice_detail_and_payment_route_work` |
| Chống thu lặp | Sau thu nút thanh toán biến mất; transaction test gọi thu lần nữa xác nhận kho/doanh thu không đổi. | MySQL payment idempotence |
| Cạnh tranh đơn vị tồn cuối | Hai thread đồng bộ Barrier, hai kết nối MySQL thật: chỉ một đơn thành công, kho không âm. | `test_concurrent_payment_cannot_sell_last_unit_twice`; stock adjustment serialization |
| Báo cáo khớp | Chrome sau đơn hỗn hợp: 7 ngày **2.583.000 VND**, 3 đơn, 1 pet, tồn 499. Dashboard và report khớp. | Paid-only, timezone/DST, ngày trống, kỳ so sánh, snapshot khi DB thay đổi |
| Trợ lý tiếng Việt | “Hôm nay còn mèo nào?” → 36 kết quả (card preview 12); “Tìm mèo lông trắng dưới 3 triệu” → Mây/Mực/Sữa. Miu vừa bán không còn trong nhóm đang bán. Enter gửi/Esc đóng. | SQL toàn danh mục > preview, tenant scope, JSON sai kiểu 400, local/LLM lỗi mạng |
| Gợi ý nhập kho | Dashboard sau thu: ACC-001 tồn 4/ngưỡng 5, bán 1/14 và 1/30 ngày, còn 56 ngày, đề xuất nhập 2, công thức rõ. | Paid-only, fallback hàng mới, ceil phân số, 14/30 ngày |
| Tìm bằng ảnh | Chrome tải `may-calico.png`, lọc Mèo/Đang bán: Mây #1 **100/100**, hiển thị màu/cấu trúc/thuộc tính, progress không vi phạm CSP. | Bộ lọc trước ranking; Vision mất mạng/JSON hỏng về local, giữ thuộc tính nhập tay |
| Xuất Excel | Click thật từ Chrome, nút có loading/khóa rồi trở lại bình thường; file tải xong. Đọc 4 sheet: tổng quan **2.583.000 VND**, 3 đơn, 1 pet, tồn 499 và thời điểm chốt khớp màn hình. | Đối chiếu tổng quan/ngày/chi tiết, signed snapshot 15 phút, CSRF/tenant/actor, formula injection và tiền lớn |

Các số trong bảng là snapshot của **QA**, không phải số phải ép vào database dev. Bộ seed mới là 12 khách, 22 sản phẩm, 74 thú cưng, 68 ảnh, 7 hóa đơn; dữ liệu dev được giữ lại có thể nhiều khách hơn. Kiểm PDF hai trang/render đã có bằng chứng Phase 3; Phase 4 chạy lại regression JavaScript trước/sau in, không xuất thêm PDF bằng trình duyệt.

Chrome không cấp quyền extension đọc file URL; tìm ảnh được thực hiện bằng hộp chọn file native, không đổi quyền extension. Console của tab QA không có lỗi JavaScript trong lượt kiểm cuối. Các tab QA đã đóng, server QA đã dừng.

## Lệnh chuẩn bị nhanh

```sh
# Terminal 1, cùng .env/venv:
python run.py
# Terminal 2:
python run.py prepare-demo
# Tích hợp vào script nếu cần:
python run.py prepare-demo --json
```

Thực hiện:

1. Chặn production/database ngoài `_dev`/`_test`, yêu cầu SECRET_KEY cố định và ảnh local.
2. Kiểm MySQL/schema, tài khoản admin/staff1, tồn đủ cho 2 FOOD-001 + 1 ACC-001 và một pet đang bán có ảnh; in cá thể/tổng thực tế để dùng khi diễn lại.
3. Kiểm file ảnh đã gắn và HTTP `/readyz` 200. Chữ ký HMAC trong header local xác nhận đúng database/cấu hình; body JSON cũ giữ nguyên. Không trả header này cho production hoặc request ngoài loopback.
4. Khóa/kiểm đúng bảy marker seed; chỉ cập nhật created_at/paid_at và ngày stock movement tương ứng trong **một transaction**. Bỏ qua marker đã hủy; nếu marker “hôm nay” bị hủy hoặc marker thiếu/chưa thu thì báo chưa sẵn sàng. Không tự trả thú đã bán vào kho hoặc thanh toán lại.
5. Parent process giới hạn worker trong ngân sách **4,7 giây**, exit 0 khi sẵn sàng, exit 1 khi lỗi/quá hạn. Timeout có thể xảy ra sát commit nên kết quả luôn ghi “chưa xác nhận”; chạy lại an toàn. Không khẳng định rollback nếu process đã commit trước lúc bị dừng.

| Phép đo public CLI | Thời gian ngoài process | Kết quả |
|---|---|---|
| Dev lần 1 | **0,760 s** | Ready, 7 marker, 68 ảnh |
| Dev lần 2 | **0,671 s** | Ready, không trừ kho lặp |
| MySQL không kết nối (cổng sai) | **0,754 s** | Exit 1, thông báo mã 2003, không giả ready |

MySQL integration cũng gọi public CLI hai lần với HTTP server thật, kiểm mỗi lần dưới 5 giây và thử SECRET_KEY khác: báo lỗi, ngày giao dịch không đổi. Unit test xác nhận timeout, rollback khi write thứ hai lỗi, dữ liệu marker không hợp lệ và sanitization output. Đây là phép đo trên máy nghiệm thu; máy quá chậm/hỏng kết nối được báo thất bại thay vì bảo đảm luôn hoàn tất thành công trong 5 giây.

## Bảo toàn dữ liệu và giới hạn

- Dev sau nghiệm thu: **20 bảng, 14 khách, 22 sản phẩm, 74 pet, 68 ảnh, tổng tồn 501**. Không migrate/seed đầy đủ/reset dev trong Phase 4. Preflight chỉ làm mới timestamp giao dịch mẫu như yêu cầu.
- So sánh fingerprint trước/sau hai lần preflight: kho, status/buyer/sold_at của pets, mọi invoice item, ngày/trạng thái hóa đơn ngoài marker demo và password hash giữ nguyên.
- `petcare.i18n` giữ nguyên từng byte so với snapshot trước Phase 1, SHA-256 `c934f5b9b201200616c28b0b03e1b7c7772f5590f9b4213711a51cdfb7c1132f`.
- Web dev được khởi động lại bằng code cuối trên 5055; `/readyz` **HTTP 200**. AI local chạy thật, provider LLM/Vision online vẫn chỉ kiểm thành công/lỗi qua mô phỏng khi không có cấu hình provider.
- Không commit/push/merge/tag trong lượt này. Không triển khai production hay kiểm provider cloud thật.

Kịch bản ngắn để nhóm cầm khi bảo vệ: [DEMO_SCRIPT.md](../DEMO_SCRIPT.md).
