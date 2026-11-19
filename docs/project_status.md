# Trạng thái PetCare Manager

Cập nhật: 2026-11-03. Nhánh làm việc `solo/khang-petcare` đã push đầy đủ thay đổi P1.1–P2.4, UI và tài liệu tới commit `c9b8621`; nhánh local khớp origin. GitHub Actions run #5 xanh trên Python 3.11–3.13, source-security và container. Run #4 từng fail do checksum GSAP bị thay đổi khi trim whitespace; đã khôi phục nguyên file phân phối và kiểm tra full suite local. Tag `v1.0-demo-ready` vẫn chỉ ở local; chưa merge hoặc tạo PR.

## P1.1 — hồ sơ khách hàng — 2026-11-02

- Trang hồ sơ hiển thị liên hệ, trạng thái, số hóa đơn theo trạng thái, tổng paid/unpaid theo từng currency và lịch sử hóa đơn phân trang.
- Từ hồ sơ có thể lập hóa đơn với khách đã chọn; danh sách và chi tiết hóa đơn liên kết ngược về hồ sơ.
- 17 focused Python web/unit tests đạt; Jinja/Python compile và `git diff --check` đạt. Playwright xác nhận desktop 1280 px và mobile 360 px không tràn ngang; nút trợ lý mobile không che số liệu.
- Không chạy migration, không ghi dữ liệu hay thay đổi schema MySQL trong lượt này.

## P1.2 — nhà cung cấp và nhập hàng từng phần — 2026-11-02

- Admin quản lý nhà cung cấp và tạo đơn nhập với snapshot nhà cung cấp, mã/tên sản phẩm, giá nhập, số lượng và tiền tệ tại thời điểm đặt; tạo đơn chưa cộng tồn.
- Có thể nhận hàng qua nhiều đợt. Mỗi đợt khóa đơn, dòng hàng và sản phẩm; kiểm tra số còn lại/giới hạn tồn; cập nhật tồn, số đã nhận, stock movement và audit trong cùng transaction. Đơn hoàn tất hoặc đóng phần còn lại không thể nhận tiếp.
- Thêm migration MySQL cộng dồn cho `suppliers`, `purchase_orders`, `purchase_order_items` và nguồn đơn nhập trong sổ tồn. Readiness và tenant export đã nhận schema mới. DB phát triển hiện tại chưa chạy migration, vẫn giữ 20 bảng và toàn bộ dữ liệu.
- 54 focused Python web/unit tests đạt; sau lượt chỉnh UI, toàn bộ unit 183/183 và web 70/70 tiếp tục đạt, compileall, cú pháp JavaScript và `git diff --check` đạt. MySQL 8.4 container riêng xác nhận migration trên DB trống, luồng đặt/nhận từng phần/nhận đủ, rollback khi tồn vượt giới hạn, `/readyz` schema contract và 13 truy vấn CSV tenant export; container đã xóa. Không kết nối hoặc ghi vào `petcare_shop_dev`.
- Playwright đã kiểm tra danh sách đơn, nhà cung cấp, form lập đơn và chi tiết nhận hàng trên desktop 1440 px, mobile 390 px và màn hẹp 320 px. Trang tạo đơn không tràn ngang, các trường nhận số lượng/giá không bị nút trợ lý hoặc thanh điều hướng che; trợ lý mở từ nút đặt trong form. Console sạch sau khi thay thanh tiến độ inline bằng phần tử native tương thích CSP.

## P1.3 — trả hàng và hoàn tiền — 2026-11-02

- Admin ghi nhận hoàn một phần/toàn phần bằng một sổ mới; hóa đơn đã thanh toán giữ nguyên trạng thái, dòng và snapshot. Idempotency key chặn gửi trùng; lượng hoàn cộng dồn không thể vượt lượng bán.
- Sản phẩm nhận lại chỉ cộng kho khi có thể bán lại; hàng cách ly không cộng kho. Thú cưng nhận lại được đưa về available hoặc inactive, còn goodwill refund không thay đổi tồn/quyền sở hữu. Header, dòng hoàn, tồn/trạng thái, stock movement và audit cùng một transaction.
- Migration cộng dồn thêm hai bảng hoàn tiền và liên kết nguồn vào sổ tồn. Readiness, export tenant, cleanup và báo cáo đã cập nhật; báo cáo/assistant tính doanh thu thuần theo ngày hoàn, gợi ý nhập kho chỉ trừ hàng thực nhận lại. DB phát triển vẫn giữ 20 bảng, chưa chạy migration.
- Thao tác hoàn chỉ ghi nhận và đối soát; không kết nối/chuyển tiền thực tế. UI giới hạn cho admin và nêu rõ cần chi tiền/chuyển khoản riêng.
- Nghiệm thu: **321/321 Python tests** trên Python 3.13 gồm 189 unit, 73 web và 59 MySQL integration trên container MySQL 8.4 riêng; **26/26 JavaScript**. Migration được kiểm tra cùng luồng hoàn thực; test data và container đã dọn. `pip-audit`, Bandit theo baseline, Compose config, Docker build, source secret scan, `compileall`, `node --check` và `git diff --check` đạt.
- Playwright: 1440×1000 và 390×844 không tràn ngang; trợ lý mở/đóng bằng Esc và trả focus đúng. Nút nổi được thay bằng nút ngữ cảnh trong hóa đơn; tại cuối form mobile, các trường và nút gửi vẫn nằm phía trên thanh điều hướng. Console không có lỗi/cảnh báo. Không gửi khoản hoàn từ trình duyệt.
- Không migrate hoặc ghi vào `petcare_shop_dev`; DB phát triển giữ nguyên 20 bảng và dữ liệu.

## P2.1 — local CI và release gates — 2026-11-02

- Chạy trọn suite theo lệnh CI trên Python 3.13: 321/321 Python tests, gồm 59 MySQL integration trên MySQL 8.4 tạm; 26/26 JavaScript tests. `pip-audit`, Bandit theo baseline, `docker compose config --quiet`, Docker image build và Trivy source secret scan đạt.
- Trivy image scan đạt 0 HIGH/CRITICAL sau khi dùng `.trivyignore.yaml`; Trivy source secret scan không phát hiện secret. Thêm một suppression có ngày hết hạn 2026-11-18 cho `msgpack 1.1.2` bị gán nhầm từ SBOM; đã kiểm tra package không được cài trong image. GitHub Actions run #3 trên commit `479e0f3` đã xanh cả ba job; cần chạy lại trên release candidate chứa thay đổi hiện tại trước khi phát hành.
- `petcare_shop_dev` không được kết nối hoặc thay đổi. MySQL test container, server Playwright và artifact kiểm thử đã dọn.

## P2.2 — hoàn thiện locale cho email và báo cáo — 2026-11-02

- Email xác minh/khôi phục tài khoản, lời mời thành viên và thông báo bàn giao owner được dựng bằng tiếng Việt hoặc English tại thời điểm enqueue; email bàn giao theo locale đã lưu của tài khoản đích. Nội dung vẫn giữ one-time link và hạn 24 giờ/30 phút/7 ngày/72 giờ tương ứng.
- API lỗi của trợ lý, gợi ý ảnh, tìm sản phẩm nhập hàng và lỗi kỳ báo cáo trả bản dịch theo locale; trang lỗi báo cáo cũng dịch validation message.
- Nhật ký audit của giao dịch hoàn tiền hiển thị số tiền, currency và mã hóa đơn bằng tiếng Anh khi dùng locale English; phần mô tả audit lịch sử khác vẫn còn nội dung cần rà soát.
- Excel báo cáo dùng locale giao diện lúc tải: sheet, tiêu đề, cột, nội dung tóm tắt và định dạng ngày/giờ được bản địa hóa. Dữ liệu số, currency và tên riêng giữ nguyên giá trị.
- Xác minh đầy đủ: **330/330 Python tests** gồm 195 unit, 76 web và 59 MySQL integration trên MySQL 8.4 container cô lập; **26/26 JavaScript tests**. `pip-audit`, Bandit theo baseline, `compileall` và `git diff --check` cũng đạt sau thay đổi. Container/database test đã xóa; database phát triển vẫn chạy riêng và không bị thay đổi.
- Email provider thật, bounce/complaint, nội dung audit lịch sử và một số thông báo server vẫn cần nghiệm thu trước public launch. Ngày/giờ/số trên các màn hình nghiệp vụ chính đã định dạng theo ngôn ngữ và múi giờ cửa hàng; CSV giữ header ổn định, timestamp UTC ISO và số thập phân dấu chấm để tương thích trao đổi dữ liệu.

## P2.3 — định dạng ngày giờ và số theo locale — 2026-11-03

- Bổ sung helper định dạng ngày, giờ và số theo `vi`/`en`; timestamp được hiển thị theo múi giờ cửa hàng. Cập nhật các màn hình dashboard, khách hàng, thú cưng, hóa đơn, nhập hàng, sản phẩm và báo cáo; số trong bảng dùng chữ số tabular.
- Trang báo cáo và các tổng quan hiển thị cùng một khoảng ngày theo locale đã chọn; định dạng tiền tệ giữ quy tắc currency hiện hành. File CSV tiếp tục dùng contract trung tính locale: header ổn định, ngày giờ UTC ISO và số thập phân dấu chấm.
- Nghiệm thu: **334/334 Python tests** gồm 198 unit, 77 web và 59 MySQL integration trên MySQL 8.4 container cô lập; **26/26 JavaScript tests**. `pip-audit` không tìm thấy lỗ hổng đã biết; Bandit baseline, `compileall`, cú pháp JavaScript, `docker compose config --quiet`, production Docker build và `git diff --check` đạt.
- Playwright đã kiểm tra trang báo cáo ở desktop 1280×720 và mobile 360 px, xác nhận hiển thị VI/EN và không tràn ngang trên mobile. Không migrate hoặc ghi vào `petcare_shop_dev`; database MySQL và media tạm đã được dọn sau kiểm tra.
- Còn mở trước public launch: rà soát đầy đủ thông báo/validation ở mọi route, bản dịch nội dung audit lịch sử, nghiệm thu SMTP/bounce/complaint và hosted CI trên release candidate.

## P2.4 — thông báo workflow và nhật ký audit VI/EN — 2026-11-03

- Bổ sung bản dịch cho các lỗi nhập hàng, báo cáo/export, giới hạn tốc độ, tìm ảnh và xác thực vai trò còn thiếu; chuỗi flash/lỗi tĩnh trong route/service được kiểm tra tự động để tránh thêm nội dung English chưa dịch.
- Hoàn thiện nhãn sự kiện và đối tượng audit cho hoàn tiền, đơn nhập, nhà cung cấp, bàn giao owner, cập nhật tài khoản và đăng ký cửa hàng; bổ sung bản dịch cho summary tài khoản/đăng ký đã được ghi trong nhật ký cũ.
- Nghiệm thu: **338/338 Python tests** (201 unit, 78 web, 59 MySQL integration trên MySQL 8.4 cô lập), **26/26 JavaScript tests**. `pip-audit`, Bandit theo baseline, Compose config, production Docker build và `git diff --check` đạt.
- Playwright: trang audit English trên desktop hiển thị đúng nhãn/summary hoàn tiền và lịch sử; mobile 360 px không tràn ngang, bảng cuộn trong khung riêng. Đã xóa 68 ảnh chỉ được DB test tham chiếu; toàn bộ file mà `petcare_shop_dev` tham chiếu được giữ nguyên. CI DB tạm đã dọn; database phát triển không bị ghi hoặc migrate.
- Các summary phát sinh từ ứng dụng và event/entity đã biết được dịch. Audit nhập từ hệ thống khác hoặc summary tự do không khớp mẫu vẫn hiển thị nguyên văn nguồn. Hosted CI run #5 xanh trên commit `c9b8621` cho cả ba phiên bản Python cùng source-security/container.

## Nghiệm thu Phase 4 — 2026-10-25

- **283/283 Python tests**, không fail/error/skip: **171 unit, 55 web, 57 MySQL integration**, 32,014 giây; **19/19 JavaScript tests** đạt.
- Tổng duyệt Chrome/MySQL: Admin/Staff, validation giữ dữ liệu/focus, quick customer, đơn sản phẩm + cá thể, trạng thái trước/sau thu, báo cáo, trợ lý Việt và upload ảnh local. Thanh toán lặp/tranh chấp đơn vị cuối được kiểm bằng transaction MySQL thật.
- Excel tải bằng Chrome sau đơn 2.250.000 VND: tổng 7 ngày **2.583.000 VND**, 3 đơn, 1 pet, tồn 499 khớp màn hình và workbook 4 sheet. Đây là số QA, không phải dữ liệu dev.
- `python run.py prepare-demo [--json]` đo ngoài process **0,760 / 0,671 giây**; MySQL không kết nối báo exit 1/mã 2003 trong 0,754 giây. Preflight có ngân sách 4,7 giây và kiểm đúng server/database, làm mới timestamp marker paid, không thu/trừ kho lặp.
- AST/Jinja/JS, Compose, pip check, dependency audit, git diff check và Bandit baseline đạt. Giữ nguyên i18n từng byte. Dev giữ 20 bảng, 14/22/74/68 và tổng tồn 501; /readyz 5055 trả 200. Hai DB test/scoped grant và tab QA đã dọn.
- Ma trận, công thức kiểm chứng và giới hạn: [nghiệm thu Phase 4](phase4_acceptance.md). Kịch bản bảo vệ: [DEMO_SCRIPT.md](../DEMO_SCRIPT.md).

## Nghiệm thu Phase 3 — 2026-10-25

- Đã hoàn tất 3.1–3.4: tra cứu SQL toàn danh mục với card hồ sơ; gợi ý nhập kho có công thức từ paid 14/30 ngày; biểu đồ/kỳ so sánh/bản tin Python, Excel snapshot và in/PDF; tìm ảnh có bộ lọc/giải thích và gợi ý thuộc tính có duyệt.
- 271/271 Python (162 unit, 53 web, 56 MySQL integration) và 19/19 JavaScript tests đạt. Provider LLM/Vision được mô phỏng cả thành công/lỗi; local đã chạy thực tế trên trình duyệt.
- Excel đã render kiểm tra 4 sheet, PDF 2 trang được xuất bằng Chrome và render kiểm tra; số liệu khớp. Báo cáo mobile 390×844 không tràn ngang.
- Giữ schema 20 bảng, dữ liệu dev 14/22/74/68 và tổng tồn 501; không seed/migrate/reset dev. i18n giữ nguyên từng byte. App local 5055 `/readyz` 200; DB test tạm và tab/viewport đã dọn.
- Chi tiết công thức, snapshot 15 phút và giới hạn 366 ngày/5.000 dòng ở [Phase 3](phase3_ai_automation.md). Đây là snapshot Phase 3; xem mục Phase 4 phía trên cho kết quả mới nhất.

## Nghiệm thu Phase 2 — 2026-10-25

- Chuẩn hóa CSS/breakpoint, system font, màu `#287A62`, badge, toast, empty state và reduced motion.
- POS hai vùng với catalog ảnh/giá/tồn, tìm kiếm/phân trang, giỏ hàng và thêm nhanh khách hàng ngay trong modal. Sản phẩm tăng đến tồn; thú cưng là cá thể, số lượng 1. Server vẫn xác thực và tính tiền.
- Loading và khóa gửi lặp cho lookup/chat/tìm ảnh/export; modal và trợ lý hỗ trợ Esc/focus. Pool MySQL chờ tối đa 3 giây khi cạn slot để phục vụ burst ảnh mà không tăng giới hạn kết nối.
- Đã seed dev sau backup mã hóa: 14 khách hàng, 22 sản phẩm, 74 thú cưng, 68 ảnh và 7 hóa đơn demo; tổng tồn sản phẩm giữ 501 trước/sau lần làm mới. Ngày demo tương đối được cập nhật khi chạy lại seed; ảnh thiếu được bổ sung. Các snapshot 10 thú cưng/4 ảnh bên dưới là lịch sử.
- 236/236 Python tests (139 unit, 44 web, 53 MySQL integration) và 15/15 JavaScript tests đạt. MySQL dùng database `_test` riêng. Chrome: POS 1280×800, 768×1024, 390×844 không tràn ngang; giỏ hàng giữ nguyên qua tìm kiếm và modal.
- Module `petcare.i18n` giữ nguyên từng byte so với trước Phase 1; Phase 3 chưa thực hiện.

## Phạm vi hiện hành

- Nền tảng web multi-store SaaS dùng chung database: Flask + Jinja HTML, CSS và JavaScript thuần; hiện mới là baseline phát triển, chưa public-launch-ready.
- MySQL/InnoDB; database phát triển riêng petcare_shop_dev.
- Quản lý tài khoản, khách hàng, thú cưng bán lẻ, sản phẩm/tồn kho, hóa đơn và báo cáo.
- Trợ lý hỏi đáp theo dữ liệu cửa hàng, có endpoint AI tạo sinh tùy chọn; context không chứa PII khách hàng.
- Ảnh hồ sơ thú cưng với thuộc tính ngoại hình; tìm ảnh đọc candidate theo lô, chỉ giữ top-12 trong RAM, xếp hạng màu trung tâm/toàn ảnh, cấu trúc và AI Vision opt-in. So sánh vẫn tuyến tính theo inventory; có lệnh dry-run/reindex descriptor cũ theo batch.
- Camera laptop chụp một khung hình để tìm; điện thoại có camera gốc và QR link qua LAN opt-in.
- Khám, tiêm, lịch hẹn và dịch vụ spa không thuộc phạm vi app mới; mã/tài liệu clinic cũ được lưu ở docs/archive/.

## Đã hoàn thiện

- App factory, blueprint, đăng nhập/đăng xuất, CSRF, session có user/tenant/version đã ký, thu hồi phiên sau đổi mật khẩu hoặc đổi trạng thái membership; membership/role được tải lại ở mỗi request.
- Schema code hiện hành có 25 bảng sau migration P1.2/P1.3 gồm nhà cung cấp/đơn nhập và trả hàng/hoàn tiền; database phát triển đang dùng chưa chạy các migration này nên vẫn có 20 bảng. Business data tenant-scoped, composite foreign keys chống ghép chéo; migration cộng thêm backfill DB cũ vào `main`, không DROP.
- Cửa hàng mới có thể được provision qua `python -m petcare.database.create_store`; user nhiều membership chọn/đổi cửa hàng, role khác nhau theo từng store.
- Tên hiển thị/mật khẩu là thuộc tính toàn nền tảng; admin không sửa hồ sơ toàn cục của user nhiều membership, còn người dùng đổi tên ở cài đặt tài khoản sau re-auth.
- Admin tạo/thu hồi liên kết mời dùng một lần, 7 ngày; với SMTP cấu hình, lời mời gửi qua encrypted outbox; môi trường local chưa có SMTP dùng link thủ công. Người nhận gắn tài khoản đã xác minh đúng email hoặc tạo tài khoản mới. Email tài khoản có thể xác minh; khôi phục mật khẩu dùng token một lần. SMTP provider thật chưa được kiểm tra.
- Operator có CLI export; store-admin gửi yêu cầu nền vào MySQL queue, worker snapshot tenant và tạo bundle AES-GCM gồm CSV, ảnh và manifest checksum. Passphrase được mã hóa tạm bằng Fernet, worker lease/retry, recheck role, audit hoàn tất, phân quyền status/download theo requester + tenant và tự dọn artifact theo retention; password/token hashes không được xuất.
- CRUD khách hàng, sản phẩm (mô tả, ảnh, ngưỡng nhập lại riêng), thú cưng và nhà cung cấp; điều chỉnh tồn kho có lý do; đơn nhập ghi tăng tồn theo các lần nhận thực tế.
- Hóa đơn snapshot; thanh toán transaction, khóa hàng, trừ kho và ghi người mua; unpaid hủy được, paid bất biến. Hoàn tiền lưu sổ điều chỉnh riêng, không sửa invoice gốc.
- Dashboard, báo cáo doanh thu/hàng bán/tồn; layout responsive tiếng Việt.
- Timestamp lưu UTC; mỗi tenant chọn múi giờ IANA hợp lệ, ngày báo cáo theo lịch địa phương qua DST, timestamp hiển thị theo giờ cửa hàng. Migration +07 chỉ chạy một lần và readiness kiểm marker.
- Runtime dùng MySQL connection pool giới hạn theo process; session reset khi trả pool và UTC/tenant context được đặt lại trên mỗi checkout. Production xác thực TLS MySQL qua `DB_SSL_CA`, CA và hostname đều được kiểm tra.
- Chủ/admin có trang cài đặt tenant để đổi tên và múi giờ; slug và currency giữ nguyên. Owner được hiển thị riêng, không thể bị admin thường khóa/hạ quyền; bàn giao cho admin khác cần re-auth hai phía, chấp thuận 72 giờ, có thể thu hồi và ghi audit.
- `/metrics` tùy chọn, bearer-protected, cho Prometheus xem queue depth/age và worker up mà không xuất tenant/job PII; để trống `OPS_METRICS_TOKEN` thì endpoint 404.
- Hướng dẫn setup, sử dụng, tìm ảnh, trợ lý và báo cáo tổng kết được cập nhật cho phạm vi cửa hàng.
- Composer hóa đơn có tìm kiếm/phân trang server-side cho khách hàng, sản phẩm, thú cưng; trang admin có nhật ký transaction cho hóa đơn, tồn kho, và thay đổi hồ sơ khách hàng/sản phẩm/thú cưng/tài khoản.

## Bằng chứng chạy trên máy hiện tại

- Python 3.13.3; Flask 3.1.3; Flask-WTF 1.3.0; mysql-connector-python 9.7.0; MySQL Server 8.4.11.
- .venv/bin/python -m compileall -q run.py main.py petcare tests — đạt.
- Toàn bộ suite unit/web/MySQL trên database `petcare_codex_<random>_test` mới tạo, cấp quyền scoped rồi xóa sau kiểm thử — đạt 197/197 vào 2026-10-19. Bao gồm locale persistence, nhãn audit VI/EN, thông báo validation, response no-store cho phiên đăng nhập, tenant isolation, camera/AI, export, account, inventory, timezone, image processing, quota và worker. Lượt xác minh mới nhất chạy compileall, cú pháp JavaScript, `git diff --check`, Bandit 1.9.4 theo baseline (không phát hiện mới) và `pip-audit` (không phát hiện CVE đã biết); Trivy gần nhất có bằng chứng ngày 2026-10-18, không chạy lại vì binary không có trong môi trường hiện tại.
- `petcare_shop_dev` đã initialize additive; `/readyz` và `/workersz` đều trả HTTP 200 `ready` sau khi web, email worker và export worker khởi động lại.
- `docker compose config --quiet`, `docker compose build web email-worker export-worker`, `node --check` và `git diff --check` đạt; sau migrate dev, app local `/healthz`, `/readyz`, `/workersz`, `/login` đều 200. Email/export workers đang chạy với heartbeat mới.
- Sau khi bổ sung danh mục demo, petcare_shop_dev đã initialize và seed hai lần: 2 users, 13 customers (12 hồ sơ demo mới, giữ nguyên dữ liệu có sẵn), 22 products, 10 pets, 4 ảnh thú cưng demo và 7 hóa đơn demo đã thanh toán. Lịch sử tồn có 36 dòng. Không có ảnh sản phẩm seed sẵn; ảnh mặt hàng được tải lên từ form admin.
- `petcare_shop_dev` đã chạy additive initialize cho account tokens và encrypted email outbox/expiry; không chạy seed trong lần migrate này. Các hàng hiện có được giữ lại; `/readyz` trả 200.
- Flask client: login/CSS trả 200; trang cần đăng nhập redirect 302 khi chưa có session.
- Trình duyệt đăng nhập admin thành công; dashboard, form bán và trang chi tiết hóa đơn hoạt động. Luồng bán qua giao diện tạo và thanh toán hóa đơn 2.250.000 ₫ gồm hai sản phẩm và Miu; tồn kho, doanh thu và trạng thái thú cưng được cập nhật. Dữ liệu walkthrough được dọn khỏi DB test và tồn kho khôi phục.
- Trang `/store/settings` được mở trên browser IAB sau khi restart app; menu quản trị xuất hiện và form đọc được bằng accessibility tree. Browser chỉ đọc; kiểm tra POST, audit và validation chạy trên MySQL test DB riêng.
- Web integration xác nhận form tạo khách hàng/sản phẩm/thú cưng, trang chi tiết và route thanh toán có CSRF; DB test được khôi phục sau kiểm thử.
- Trang đăng nhập đã được xem ở khung 628 × 627; sửa lỗi minh họa đè lên chữ và kiểm tra lại sau khi khởi động lại Flask.
- Trang tìm ảnh được mở trực tiếp; trợ lý trên DB phát triển trả danh sách sản phẩm và tồn thấp. Migration cộng thêm các cột ảnh/ngoại hình, mô tả và ngưỡng nhập hàng; giữ dữ liệu hiện có.
- UI tìm ảnh sau nâng cấp hiển thị nút camera laptop, lựa chọn camera điện thoại và cảnh báo xin quyền; MySQL integration xác nhận QR chỉ sinh khi bật LAN. Không cấp quyền hoặc bật camera trong lúc nghiệm thu.
- Docker container riêng petcare-manager-mysql khỏe mạnh, MySQL 8.4.11; port chỉ bind vào 127.0.0.1:3306.

## Cập nhật source cho demo — 2026-10-20

- Seed hiện định nghĩa 74 hồ sơ thú cưng (35 chó, 37 mèo, 1 thỏ, 1 hamster) và 68 ảnh. 64 ảnh chó/mèo mới được tạo tổng hợp bằng AI; hồ sơ/ảnh đều hư cấu để demo.
- Trợ lý local được mở rộng để tra cứu doanh thu ngày/tuần/tháng, sản phẩm và thú cưng theo các thuộc tính có trong hồ sơ. Giao diện tìm ảnh và icon ở luồng thú cưng được làm rõ hơn; giới hạn của xếp hạng local được ghi trực tiếp trên trang.
- Các con số vận hành/kiểm thử phía trên là bằng chứng lịch sử cho bộ seed 10 thú cưng/4 ảnh. Lượt này chưa chạy seed lên MySQL, chưa chạy test và chưa bật lại ứng dụng; cần nạp seed trên database `_dev` trước buổi demo.

## Chạy cục bộ

- URL hiện tại khi server đang chạy: http://127.0.0.1:5055.
- Tài khoản demo `admin` và `staff1` chỉ dùng với database demo local. Đổi thông tin xác thực trước khi chia sẻ môi trường; giá trị mật khẩu không được ghi trong tài liệu.
- Bí mật được lưu trong .env đã gitignore; .env.example chỉ chứa placeholder.
- Database trống dùng dữ liệu thật có thể khởi tạo admin đầu tiên bằng `python -m petcare.database.create_admin`; xác nhận tên database và nhập mật khẩu ẩn qua terminal.

## Giới hạn còn lại

- Chưa kiểm setup sạch trên Windows.
- App chưa triển khai Internet/HTTPS, kiểm thử tải hoặc nghiệm thu hệ thống sao lưu ngoài máy. SaaS có invitation email qua outbox, public signup route mặc định tắt, email verify/recovery và self-service export mã hóa; còn thiếu billing, deletion/retention workflow, cấu hình bucket production, kiểm live SMTP và review độc lập về bảo mật cô lập.
- Giá, hóa đơn, hoàn tiền và báo cáo dùng Decimal/DECIMAL theo currency tenant; tenant mới chọn currency ISO và IANA timezone khi onboarding, hóa đơn snapshot mã tiền, timestamp lưu UTC rồi hiển thị theo giờ cửa hàng. Locale UI hỗ trợ vi/en; chưa có thuế đa vùng, FX/đổi currency hoặc cổng thanh toán tự động.
- Camera laptop trực tiếp cần localhost/HTTPS; trên điện thoại truy cập LAN dùng trình chụp ảnh gốc thay cho video trực tiếp do giới hạn secure-context của trình duyệt. LAN access mặc định tắt.
- Tìm ảnh local dùng histogram màu vùng trung tâm/toàn ảnh và cấu trúc toàn ảnh; nền/framing vẫn có thể ảnh hưởng, đây chưa phải object detector/embedding đã huấn luyện. Ảnh truy vấn được gửi tới app server, không lưu; chỉ gửi AI endpoint nếu AI Vision bật. Tạo sinh chat và AI Vision cần endpoint tương thích cấu hình; AI Vision mặc định tắt.
- Báo cáo tổng kết chính được cập nhật; các trang báo cáo/slide ghi tên từng thành viên vẫn là ghi chép của phiên bản clinic và cần tác giả rà soát trước khi nộp.
