# Dàn ý slide tổng kết — PetCare Manager

## Slide 1 — PetCare Manager

- Web quản lý cửa hàng thú cưng.
- Khách hàng · sản phẩm · thú cưng · hóa đơn · báo cáo.
- Phiên bản nội bộ chạy local.

## Slide 2 — Yêu cầu điều chỉnh

- Giao diện chuyển từ desktop Tkinter sang web HTML/CSS.
- Database chuyển sang MySQL.
- Thay nghiệp vụ dịch vụ phòng khám bằng bán sản phẩm và thú cưng.
- Giữ mã và tài liệu clinic cũ trong docs/archive/.

## Slide 3 — Công nghệ và kiến trúc

- Python + Flask + Jinja2.
- HTML, CSS và JavaScript thuần.
- MySQL 8.4 / InnoDB / utf8mb4.
- Route → service → repository → database.

## Slide 4 — Nghiệp vụ chính

- Khách hàng và thông tin người mua.
- Sản phẩm có giá và tồn kho.
- Thú cưng là từng cá thể có mã, giá và trạng thái bán.
- Hóa đơn bán sản phẩm, thú cưng hoặc kết hợp.
- Báo cáo doanh thu đã thu và hàng bán.
- Trợ lý local theo dữ liệu MySQL: doanh thu ngày/tuần/tháng, sản phẩm/tồn thấp và tìm thú cưng theo giống, màu, giới tính, ngân sách; endpoint AI tạo sinh bật tùy chọn.
- Xếp hạng thú cưng tương tự theo ảnh và thuộc tính ngoại hình.

## Slide 5 — Thanh toán và toàn vẹn dữ liệu

- Hóa đơn tạo ở trạng thái unpaid, chưa giữ hoặc trừ tồn.
- Khi thanh toán, server khóa hóa đơn và hàng liên quan trong transaction.
- Kiểm tra tồn, trừ kho, lưu stock movement, gắn người mua và hoàn tất invoice cùng lúc.
- Chống thanh toán lặp, tồn âm và bán trùng thú cưng.

## Slide 6 — Phân quyền và bảo mật

- Mật khẩu băm, CSRF protection, session user/tenant/version đã ký; phiên cũ bị thu hồi khi mật khẩu hoặc trạng thái membership đổi.
- Quyền owner/admin/staff được gắn riêng theo cửa hàng.
- Trạng thái tài khoản/role được kiểm tra lại trong database theo từng request.
- Tenant-scoped query và composite FK ngăn tham chiếu khách/hàng/nhân viên chéo store.
- Lời mời một lần, hết hạn 7 ngày; token chỉ lưu dạng hash, link domain lấy từ cấu hình tin cậy.
- Nhật ký hoạt động admin cho giao dịch hóa đơn, điều chỉnh tồn kho và cập nhật tài khoản.
- Secrets nằm trong .env, không commit.

## Slide 7 — Kiểm thử

- MySQL Server 8.4.11 trên môi trường phát triển.
- Lần kiểm đầy đủ mới nhất (2026-10-25): 283/283 Python tests (171 unit, 55 web, 57 MySQL integration) và 19/19 JavaScript tests đạt trên database MySQL tạm, biệt lập và được xóa sau kiểm thử; kiểm currency/minor-unit, UTC migration và tenant timezone/DST, pool session isolation, tenant isolation, email/outbox/onboarding, tenant media, backup/export mã hóa, AI boundary/fallback, audit/localization, authenticated no-store policy và giao dịch cạnh tranh. SMTP và bucket cloud thật chưa được nghiệm thu.
- Hai tenant dùng chung mã hàng nhưng không đọc dữ liệu/ảnh/hóa đơn của nhau; kiểm tra switching store và role membership.
- Seed demo trong source hiện có 22 sản phẩm, 12 khách mẫu, 74 hồ sơ thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster), 68 ảnh tổng hợp và lịch sử bán hàng. Dev đã nạp ngày 2026-10-25; chạy seed lại trước demo để làm mới mốc ngày mà không trừ kho lặp. Schema có 20 bảng.
- Kiểm tra thanh toán cạnh tranh ở đơn vị tồn cuối.
- Đăng nhập Chrome và xem dashboard với dữ liệu demo.

## Slide 8 — Giới hạn và bước tiếp

- Multi-store foundation đã có; chưa public-launch-ready hoặc triển khai Internet/HTTPS.
- Đã có email invitation, email verify/recovery và public signup feature-flag mặc định tắt; admin self-service tenant export mã hóa có checksum. Giá/invoice hỗ trợ currency tenant, còn i18n, tax/FX, đổi currency, billing/plan limits, tenant deletion/retention, SMTP live validation và bucket production còn thiếu.
- Windows setup và kiểm tải chưa kiểm chứng.
- Hoàn tiền, trả hàng, PDF, biểu đồ và thanh toán online là nâng cấp sau nghiệm thu.
- Trước khi nộp: tác giả cập nhật phần đóng góp cá nhân và ảnh giao diện.
- Hồ sơ và ảnh minh họa là dữ liệu AI tổng hợp, không phải thú cưng có thật; chat/vision tạo sinh cần endpoint riêng.
- POS có catalog ảnh/giá/tồn, giỏ hàng và modal thêm nhanh khách hàng. Dev hiện có 14 khách (giữ dữ liệu cũ), 22 sản phẩm, 74 thú cưng, 68 ảnh, 7 hóa đơn demo; Chrome đã kiểm tra desktop/tablet/mobile.
- Tạo sinh AI/Vision cần endpoint tương thích được cấu hình; mặc định trợ lý dùng dữ liệu local và AI Vision tắt. Bộ tìm cục bộ dùng màu/bố cục, không phải mô hình nhận dạng động vật.


## Bổ sung Phase 3 — điểm nhấn trình bày

- Trợ lý local/LLM trả card hồ sơ từ SQL toàn danh mục, đếm chính xác; API lỗi vẫn có kết quả local.
- Nhập hàng có giải thích: paid 14/30 ngày → tốc độ/ngày tồn → kế hoạch 14 ngày; hàng mới dùng reorder_level.
- Biểu đồ, kỳ so sánh và bản tin Python. Excel bốn sheet và PDF khớp bản số liệu đã chốt; in tự mở chi tiết.
- Tìm ảnh theo loài/trạng thái, có điểm thành phần/lý do; upload gợi ý thuộc tính để người dùng duyệt, giữ dữ liệu nhập tay.
- Offline/local đã kiểm thực tế; LLM/Vision có regression mô phỏng thành công/mất mạng. Không tuyên bố đã kiểm provider trực tuyến khi chưa cấu hình.

## Bổ sung Phase 4 — tổng duyệt trước bảo vệ

- Giữ web chạy, gọi `python run.py prepare-demo`: MySQL/schema/quyền/tồn/ảnh/web đúng database, làm mới ngày mẫu; 0,76 / 0,67 giây trên máy nghiệm thu, lỗi trả exit 1.
- 283 Python + 19 JavaScript tests đạt; tranh chấp tồn cuối và thanh toán lặp chạy trên MySQL thật.
- Kịch bản 8 phút trong `DEMO_SCRIPT.md`: Dashboard → POS kết hợp/thêm khách → thanh toán → nhập kho → trợ lý → ảnh → Excel/PDF.
