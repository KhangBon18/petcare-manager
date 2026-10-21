# Nhật ký thay đổi

## Khắc phục CI dependency và tương thích Python — 2026-10-21

- Nâng Pillow tối thiểu lên 13.0.0 để loại bỏ các advisory mới được `pip-audit` và Trivy phát hiện trên bản 12.3.0; chuẩn Python tối thiểu đổi từ 3.10 lên 3.11 theo hỗ trợ của Pillow 13.
- Dùng gzip streaming tường minh cho backup tar để giữ compression level 6 trên Python 3.11–3.13.
- Sau cập nhật: pip-audit sạch; 203/203 test đạt trên Python 3.11 + MySQL 8.4; build container thành công và Trivy không còn finding HIGH/CRITICAL.

## Rà soát hiệu năng và độ tin cậy — 2026-10-20

- Tìm ảnh thêm SimHash 64-bit và chỉ mục LSH gắn composite tenant/pet FK; xếp hạng cuối vẫn dùng descriptor ảnh đầy đủ, còn legacy và bucket quá rộng tự chuyển sang full scan.
- Reindex theo batch đồng bộ descriptor và tám bucket trong transaction; trang kết quả báo rõ tìm kiếm chỉ mục là gần đúng.
- Benchmark MySQL tạm ở 20.000 hồ sơ: median 114.87 ms với 1% candidate; median 1,149.27 ms khi toàn bộ hash va nhau và fallback full scan.
- Toàn suite đạt 203/203 trên MySQL 8.4 tạm; Bandit baseline CI, compileall, Compose config và build web đạt.

## Làm rõ trợ lý, tìm ảnh và dữ liệu demo — 2026-10-20

- Mở rộng seed từ 10 lên 74 hồ sơ thú cưng, gồm 35 chó, 37 mèo, 1 thỏ và 1 hamster; thêm 64 ảnh chó/mèo được tạo tổng hợp bằng AI (68 ảnh kể cả 4 ảnh mẫu đã có).
- Trợ lý local tra cứu danh mục sản phẩm và thú cưng từ MySQL, hỗ trợ lọc theo giống, màu lông/mắt, giới tính, mức giá và doanh thu tuần/tháng; kết quả có ghi nguồn chế độ local/AI.
- Làm rõ bước chụp/tải ảnh, điểm xếp hạng tham khảo và giới hạn nhận diện; đồng bộ bộ icon SVG cho các khu vực chính.
- Ảnh và hồ sơ là dữ liệu hư cấu cho demo. Database cần chạy seed mới để nhận thêm bản ghi; endpoint AI tạo sinh/Vision vẫn cần cấu hình riêng.
- Chưa chạy test hoặc seed database trong lượt cập nhật này.

## Không cache dữ liệu của phiên đăng nhập — 2026-10-19

- Mọi HTML/JSON response của phiên xác thực đều gửi `Cache-Control: private, no-store, max-age=0` và `Pragma: no-cache`, bao gồm trang danh sách, báo cáo, API lookup và trợ lý.
- Thêm regression test cho policy chống cache; toàn suite đạt 197/197 trên MySQL test database tạm, biệt lập rồi được xóa sau chạy.

## Bắt đầu bản địa hóa giao diện Việt–Anh — 2026-10-18

- Thêm language picker có allowlist, giữ lựa chọn trong session, chọn mặc định theo `Accept-Language` và chỉ redirect tới đường dẫn cùng origin.
- Dịch đăng nhập, khung điều hướng, dashboard và lời chào/prompt/trả lời local của trợ lý; định dạng số tiền và ngày theo locale. Tiếng Việt vẫn là mặc định khi trình duyệt không nêu ngôn ngữ hỗ trợ.
- Bổ sung web/unit coverage cho browser locale, session rotation, open-redirect defense, dashboard English và intent/context trợ lý bằng English. Full MySQL test suite hiện đạt 191/191; các module khác vẫn cần dịch trước global launch.

## Bổ sung quét secret toàn source vào CI — 2026-10-18

- GitHub Actions quét toàn bộ source tree bằng Trivy secret scanner, bao gồm file không đi vào Docker image; scan local hiện tại có 0 finding.

## Giảm dữ liệu gửi tới AI theo câu hỏi và làm rõ disclosure — 2026-10-18

- Provider nhận subset phù hợp ý định: doanh thu chỉ có doanh thu/currency; tồn kho chỉ có tên/mã/số lượng; câu hỏi sản phẩm/thú cưng nhận danh sách liên quan; câu hỏi chung không nhận dữ liệu cửa hàng. Lượt local/fallback vẫn giữ context đầy đủ.
- Hộp chat nêu rõ tối đa 8 tin nhắn trước, câu hỏi và dữ liệu danh mục có thể được gửi tới endpoint; hồ sơ khách hàng không tự gửi, nhưng nội dung người dùng nhập vẫn đi theo request.
- Bổ sung unit/web tests; toàn suite MySQL đạt 184/184, compileall và `git diff --check` đạt.

## Mở rộng kiểm thử cô lập tenant trên route — 2026-10-18

- Thử truy cập customer, pet và invoice của `main` bằng ID/từ khóa khi đăng nhập tenant khác; list/detail và API lookup không để lộ hồ sơ. POST ngừng customer chéo tenant không đổi trạng thái nguồn.
- Regression MySQL trên DB `_test` đạt; toàn suite giữ 181/181, compileall và `git diff --check` đạt.

## Quét bảo mật mã nguồn và image trong CI — 2026-10-18

- Ghim GitHub Actions theo commit SHA; thêm Bandit 1.9.4 đối chiếu baseline đã review và Trivy 0.76.0 quét production image tìm HIGH/CRITICAL vulnerability cùng secrets.
- Ghi baseline 38 phát hiện Bandit hiện có (không có High) và bốn suppression SBOM chính xác, có hạn 30 ngày; Trivy local không phát hiện lỗ hổng HIGH/CRITICAL có bản vá hoặc secret. Negative-control image chứa GitHub token giả bị scanner chặn ở CRITICAL. Hosted workflow chưa chạy; cần green run và independent review trước release.

## Quota upload ảnh dùng chung giữa web instances — 2026-10-18

- Thêm quota HMAC theo admin và địa chỉ mạng trong MySQL cho upload ảnh hồ sơ thú cưng/sản phẩm; mặc định 12 lần mỗi tài khoản và 60 lần mỗi mạng trong một phút. Khi vượt ngưỡng, form báo thử lại và gửi `Retry-After`.
- Integration test dùng hai Flask app instance chung MySQL để xác nhận quota mạng được áp dụng xuyên instance; request body vẫn cần edge/WAF giới hạn trước khi tới app. Full suite đạt 181/181; cả ba Docker image build thành công.

## Backpressure khi xử lý ảnh đồng thời — 2026-10-18

- Mỗi web process giới hạn số lần giải mã/chuẩn hóa ảnh đang chạy; mặc định một slot mỗi process, cấu hình 1–4. Request upload khi bận được chuyển lại form với thông báo và `Retry-After: 2`; các form không có ảnh không bị chặn.
- Bổ sung test cấu hình, upload bão hòa và giải phóng slot sau xử lý. Full suite đạt 179/179; ba Docker image build thành công. Semaphore là process-local; cần load test trên cấu hình triển khai thật trước khi tăng giới hạn.

## Giảm cấp phát khi chuẩn hóa ảnh upload — 2026-10-18

- Ảnh RGB được thu nhỏ trước khi các bước xử lý tiếp theo, tránh tạo thêm một bản sao RGB toàn độ phân giải; ảnh palette/grayscale/alpha vẫn chuyển màu trước khi resize để giữ lọc chất lượng.
- Thêm regression kiểm tra đường ảnh RGB và resampling palette; giới hạn 5 MB/20 megapixel vẫn áp dụng. Toàn suite đạt 177/177; ba Docker image build thành công.

## Nhập giá theo đơn vị tiền tệ trên form — 2026-10-18

- Giá `DECIMAL(20,4)` không còn lộ các số 0 thập phân thừa trên form VND; USD/KWD hiển thị đúng precision tiền tệ.
- Native `step` và hướng dẫn nhập theo ISO minor unit giúp tránh nhập giá sẽ bị từ chối khi lưu. Thêm unit/template regression; toàn suite đạt 175/175 và ba Docker image build thành công.

## Tuần tự hóa thay ảnh sản phẩm và thú cưng — 2026-10-18

- Cập nhật ảnh khóa hồ sơ và đọc giá trị mới nhất trước khi thay; hai request đồng thời không còn cùng dựa trên tên ảnh cũ, tránh để sót file đã bị thay.
- Thêm MySQL integration mô phỏng hai lần thay ảnh đồng thời cho sản phẩm và thú cưng; chỉ file đang được hồ sơ tham chiếu còn lại. Toàn suite đạt 173/173; ba Docker image build thành công.

## Giao dịch điều chỉnh kho an toàn khi cạnh tranh — 2026-10-18

- Khóa sản phẩm trước khi đọc tồn và ghi audit, để hai điều chỉnh đồng thời có `stock_before`/`stock_after` tuần tự đúng với stock movement.
- Chặn tồn kho vượt giới hạn MySQL signed `INT` bằng validation rõ ràng; câu UPDATE vẫn có ràng buộc 0–2.147.483.647 ở tầng dữ liệu.
- Thêm hai MySQL regression cho cập nhật đồng thời và vượt ngưỡng. Toàn suite đạt 172/172; ba Docker image build thành công.

## Câu trả lời trợ lý không nhầm preview với tổng số — 2026-10-18

- Thêm truy vấn đếm chính xác số mặt hàng ở ngưỡng tồn thấp; overview không còn suy tổng từ danh sách bị giới hạn 12 dòng.
- Trợ lý local dùng tổng số thật và thông báo khi chỉ hiển thị preview. Context gửi AI kèm giới hạn preview cho tồn thấp (12), sản phẩm (20) và thú cưng (12), cùng hướng dẫn không trình bày danh sách giới hạn như toàn bộ dữ liệu.
- Thêm regression cho cửa hàng có 28 mục tồn thấp, 42 sản phẩm và 34 thú cưng; toàn suite đạt 170/170, ba Docker image build thành công.

## Làm rõ trạng thái AI trên trang tìm ảnh — 2026-10-18

- Nhãn trang tìm ảnh phân biệt so khớp cục bộ, Vision sẵn sàng và lượt tìm đã có mô tả từ AI, tránh tạo cảm giác mọi lượt luôn dùng model.
- Thêm template tests cho trạng thái local và AI. Toàn suite đạt 169/169; Docker web và hai worker build thành công.

## Chuẩn hóa thuộc tính Vision tiếng Anh/Việt — 2026-10-18

- Bổ sung glossary cho loài thú cưng, màu lông/mắt, hoa văn và một số mô tả dáng thường gặp. Kết quả Vision tiếng Anh giờ có thể khớp metadata cửa hàng tiếng Việt.
- Test kiểm tra mẫu `cat/black/blue/striped/short-haired` cho ra điểm metadata đầy đủ trên hồ sơ `Mèo/đen/xanh/sọc/lông ngắn`. Glossary này cải thiện matching, không thay thế dịch toàn bộ UI hay taxonomy được chuyên gia kiểm chứng.
- Toàn suite MySQL/web/unit đạt 168/168; provider model thật vẫn chưa được cấu hình/đánh giá live.

## Bảo vệ liên kết camera điện thoại khi production — 2026-10-18

- Chỉ tạo QR LAN từ một HTTP(S) origin sạch; từ chối credentials, path, query, fragment và port không hợp lệ. Production bắt buộc dùng HTTPS cho URL QR.
- Giữ rõ trải nghiệm thực tế: camera điện thoại qua trình chọn ảnh hoạt động trên LAN HTTP tin cậy; stream `getUserMedia` cần secure context như HTTPS.
- Thêm web regression cho các URL độc hại/sai định dạng và HTTPS bắt buộc ở production; toàn suite đạt 167/167.

## Bàn giao chủ cửa hàng có xác nhận hai phía — 2026-10-18

- Thêm luồng `/users/ownership`: owner xác thực lại để chọn admin đang hoạt động; người nhận đăng nhập và xác thực lại trong tối đa 72 giờ. Chấp thuận đổi membership của hai bên trong cùng transaction; yêu cầu có thể thu hồi và được ghi audit.
- Khóa thao tác theo tenant, rate limit qua MySQL, email chỉ thông báo tới địa chỉ đã xác minh và không chứa bí mật xác nhận. Bổ sung bảng lịch sử bàn giao vào export tenant.
- MySQL integration kiểm sai mật khẩu, người nhận không hợp lệ, hủy, hết hạn, chấp thuận, role cuối, audit và hai POST cạnh tranh dưới cùng một tenant; current locking read ngăn tạo nhiều yêu cầu mở trong MySQL `REPEATABLE READ`. Toàn suite đạt 166/166; `docker compose config --quiet` đạt.
- Đây là mức sẵn sàng sản phẩm nội bộ/pilot, chưa xóa các gate vận hành trước public/global launch trong `docs/launch_readiness.md`.

## Tăng tốc tìm thú cưng tương tự — 2026-10-18

- So khớp trực tiếp các histogram/lưới từ JSON descriptor, bỏ tuple trung gian; vẫn giữ decoder tương thích cho descriptor cũ và giá trị số dạng chuỗi.
- Trên benchmark test MySQL với 20.000 hồ sơ giả lập, median tìm ảnh giảm từ 1,13 giây xuống 0,96 giây (~15%); thêm kiểm tra tương đương score.
- Tại thời điểm tối ưu, suite đạt 165/165. Search vẫn O(n); benchmark tải đồng thời và kiểm thử chất lượng vector retrieval còn mở trước pilot lớn.

## Metrics vận hành có bảo vệ — 2026-10-18

- Thêm `GET /metrics` theo Prometheus text format; endpoint tắt mặc định, yêu cầu bearer token tối thiểu 32 ký tự và trả 404 nếu chưa bật.
- Xuất queue depth/status, tuổi job pending và worker heartbeat theo aggregate toàn nền tảng; không trả tenant ID, account, email, nội dung job hoặc artifact key. Đặt `no-store`, trả 401 token sai và 503 nếu MySQL lỗi.
- Thêm hướng dẫn secret/monitoring; endpoint không tự gửi alert nên queue threshold, alert delivery, WAF và private scrape network vẫn cần cấu hình vận hành.
- Unit/web và MySQL integration bao phủ disable/weak-token/unauthorized/aggregate output; full suite đạt 163/163 trên test DB riêng.

## Cài đặt cửa hàng cho multi-store SaaS — 2026-10-18

- Bổ sung trang admin **Cài đặt cửa hàng** để đổi tên hiển thị và múi giờ của tenant đang chọn; đổi múi giờ không chuyển đổi lại timestamp UTC đã lưu.
- Giữ slug ổn định để bảo vệ luồng đăng nhập/liên kết, và khóa currency cho tới khi có quy trình FX/ledger an toàn.
- Ghi audit event cùng transaction, chỉ lưu danh sách trường thay đổi; route và service đều kiểm quyền admin của đúng cửa hàng.
- Hiển thị role **Chủ cửa hàng** riêng; màn quản trị thành viên không thể hạ quyền hoặc khóa owner. Quy trình bàn giao được bổ sung trong mục changelog mới nhất.
- Chốt trong kế hoạch kiến trúc: nhiều cửa hàng dùng chung SaaS và MySQL, với tenant isolation là ranh giới dữ liệu.
- Xác minh hai luồng mới bằng MySQL integration; toàn suite đạt 161/161 trên DB test riêng. `compileall`, `git diff --check`, `/healthz`, `/readyz`, `/workersz` đều đạt; trang mới mở được và có nhãn truy cập trong browser IAB.

## Quyền kiểm soát hội thoại trợ lý AI — 2026-10-18

- Thêm nút xóa hội thoại trong trợ lý; thao tác xóa lịch sử client-side, dừng chờ kết quả trên trình duyệt và khôi phục câu hỏi gợi ý để không gửi phần chat cũ ở lượt tiếp theo.
- Gắn nhãn truy cập cho nút xóa, kiểm tra template và cú pháp JavaScript.

## Quan sát sức khỏe background worker — 2026-10-18

- Thêm MySQL heartbeat cho email/export worker, mỗi tiến trình dùng instance ID ngẫu nhiên; chỉ lưu mốc thời gian và mã lỗi giới hạn, không lưu exception/PII.
- Export worker tiếp tục heartbeat trong lúc gia hạn lease cho tác vụ dài; `/workersz` chỉ báo ready khi cả hai loại worker có instance khỏe trong 90 giây. `/readyz` vẫn phản ánh riêng web và schema. Email worker dọn heartbeat cũ hơn 30 ngày trong maintenance định kỳ.
- Bổ sung MySQL integration cho heartbeat tươi/lỗi worker và unit tests cho throttle heartbeat, mã lỗi giới hạn và phục hồi.
- Health probe bỏ qua việc nạp user session kể cả khi request mang cookie đăng nhập cũ.
- Bộ kiểm tra đầy đủ đạt 159/159 trên MySQL test riêng; worker error/freshness được kiểm tra qua unit và integration.

## Chất lượng tài khoản, trợ lý offline và giới hạn tải AI — 2026-10-18

- Chuẩn hóa validate tên đăng nhập ở service tạo tài khoản; các luồng tạo, sửa và đặt lại mật khẩu chuyển lỗi chính sách mật khẩu thành thông báo hợp lệ thay vì lỗi 500.
- Đồng bộ pattern/độ dài trong form quản trị với quy tắc backend.
- Trợ lý local trả lời câu hỏi tổng quan bằng số liệu cửa hàng hiện tại; thêm nút gợi ý câu hỏi nhanh để người dùng biết các truy vấn được hỗ trợ khi chưa cấu hình AI endpoint.
- Thêm quota AI chat và quét ảnh theo mạng, kết hợp quota tài khoản trong một transaction MySQL; khóa giới hạn là HMAC nên không lưu IP thô. Kiểm thử admin + staff xác nhận dùng chung quota qua cùng địa chỉ mạng.
- Maintenance worker dọn các quota throttle đã cũ cùng mail đã gửi và signup chưa xác minh; hỗ trợ chạy cleanup ở chế độ worker liên tục lẫn `--once`.
- CSV tenant export trung hòa text có thể bị Excel/Sheets hiểu là công thức; kiểm tra end-to-end trên bundle đã giải mã, giữ nguyên số âm dạng số.
- Toàn suite đạt 155/155 trên MySQL test riêng; JavaScript syntax, Python compileall, Compose config và `git diff --check` đạt.

## Giảm bộ nhớ cho tìm thú cưng bằng ảnh — 2026-10-18

- Image search đọc các trường cần thiết bằng MySQL cursor không buffer, fetch theo lô tối đa 250 hồ sơ thay vì nạp mọi descriptor vào RAM.
- Chỉ giữ 12 kết quả tốt nhất trong heap; giữ nguyên ngưỡng và thứ tự xếp hạng để UI không đổi. Chi phí so sánh vẫn tuyến tính theo số thú cưng đang bán nên inventory lớn vẫn cần benchmark và vector search.
- Regression unit xác nhận quét candidate stream, xếp hạng chính xác và giới hạn top-12.

## Củng cố ranh giới danh tính SaaS nhiều cửa hàng — 2026-10-18

- Store admin không thể đổi tên hiển thị hoặc mật khẩu toàn nền tảng của người có nhiều membership, kể cả membership đang tạm khóa; vai trò và trạng thái vẫn được quản lý riêng theo tenant.
- Thêm **Tài khoản → Cài đặt tài khoản** để chủ tài khoản tự cập nhật tên hiển thị sau khi xác thực lại mật khẩu. Sự kiện được ghi audit trên các cửa hàng đang tham gia, không sao chép tên cá nhân vào log.
- Thêm MySQL integration cho mật khẩu sai/đúng, cập nhật hồ sơ và audit, cùng regression đa cửa hàng với membership inactive.
- Toàn suite đạt 146/146 trên database test MySQL riêng.

## Tìm ảnh ít nhạy với nền và an toàn thông tin hơn — 2026-10-18

- Bổ sung histogram màu vùng trung tâm để giảm nền ảnh lấn át; giữ màu toàn khung và descriptor cũ làm fallback, không cần đổi schema.
- Thêm lệnh `python -m petcare.vision.reindex_pet_descriptors`, mặc định dry-run, đọc/ghi theo batch, cập nhật có điều kiện theo ID + tenant + tên ảnh, hỗ trợ local/S3 và bỏ qua ảnh thiếu/hỏng.
- Sửa thông báo privacy: ảnh tìm kiếm gửi tới app server nhưng không lưu thành hồ sơ; chỉ gửi tới AI endpoint khi AI Vision bật. Trợ lý local không gọi AI provider.
- Thêm regression tests cho ảnh cùng chủ thể khác nền, đọc descriptor cũ, dry-run, cập nhật tenant-scoped và batch limit.
- Toàn suite đạt 145/145; template tìm ảnh render đúng với/no ảnh tham chiếu, thông báo xử lý server và không lưu ảnh query.
- Database phát triển được dry-run, cập nhật 4 descriptor, rồi xác nhận dry-run còn 0; app được restart và `/readyz` vẫn healthy.

## Xác thực TLS cho MySQL production — 2026-10-18

- Production bắt buộc có `DB_SSL_CA`; web, email worker và migration job bật xác thực CA cùng hostname. File CA phải tồn tại và đọc được; CA được đưa vào fingerprint pool để xoay trust bundle không tái dùng pool cũ.
- Compose truyền cấu hình CA đến web/worker; `.env.example`, architecture, privilege setup, README và launch checklist ghi rõ đường dẫn CA cần mount read-only trong container production.
- Thêm kiểm tra config TLS, fail-fast tại app production và pool mới sau khi đổi CA. Toàn suite đạt 139/139; compileall, JS syntax, Compose config và `git diff --check` đều đạt.

## Kết nối MySQL theo pool — 2026-10-18

- Dùng pool thread-safe có giới hạn cho runtime thay vì bắt tay MySQL mới mỗi request; pool được tách theo cấu hình DB và credentials, còn schema migration vẫn dùng kết nối riêng.
- Reset session khi trả kết nối; mỗi lần checkout ghim UTC và xóa `@petcare_tenant_id`, tránh tái sử dụng tenant context giữa request. `DB_POOL_SIZE` mặc định 5 mỗi process, giới hạn 1–32.
- Test MySQL thực giữ đồng thời toàn pool, gắn tenant context rồi checkout lại và xác nhận biến đã reset. Dependency audit: không phát hiện lỗ hổng đã biết.
- Toàn suite sau cập nhật đạt 134/134; Compose config, compileall và `git diff --check` đạt.

## UTC và múi giờ theo cửa hàng — 2026-10-18

- Chuẩn hóa mọi MySQL session về UTC; migration có marker chuyển `DATETIME` legacy từ giờ Việt Nam sang UTC đúng một lần, không đổi date-only fields.
- Tenant chọn IANA timezone hợp lệ khi signup/provision; dashboard, trợ lý và báo cáo dùng ngày địa phương với UTC bounds qua DST; timestamp trong UI hiển thị theo timezone của store.
- Thêm `tzdata` cho nền tảng thiếu cơ sở dữ liệu IANA, readiness kiểm marker migration; test UTC storage, timezone validation, DST 23/25 giờ và report qua ngày đổi giờ.
- `petcare_shop_dev` và `petcare_shop_test` đã migrate; row counts không đổi. Suite sau nâng cấp đạt 130/130.
- CSV/JSON tenant export gắn offset `+00:00` cho mọi timestamp, tránh xuất dữ liệu UTC dạng giờ địa phương không nhãn.

## Tiền tệ per-store chính xác — 2026-10-18

- Chuyển catalog và invoice sang `DECIMAL(20,4)`/Python `Decimal`; kiểm tra giá theo currency minor unit và định dạng currency code rõ ràng.
- Signup và CLI provision cho chọn mã tender hiện hành; hóa đơn lưu currency snapshot. Lookup API/JS, trợ lý AI, dashboard, báo cáo và export dùng số tiền generic.
- Migration additive backfill giá VND cũ, giữ dữ liệu số nguyên và cột compatibility; dev/test đã migrate không đổi số lượng bản ghi, mismatch giữa giá generic và legacy bằng 0.
- Babel/CLDR cung cấp tên currency, current tender list và precision. UI vẫn tiếng Việt; thuế, FX/currency changes và global legal/i18n chưa hoàn tất.
- Thêm test currency, USD invoice minor units, migration VND và signup chọn USD; toàn suite đạt 121/121.

## Độ bền worker onboarding — 2026-10-18

- Sửa thứ tự khóa cleanup signup hết hạn theo luồng xác minh email (account trước, membership sau), tránh deadlock trên account đang xác minh.
- Thêm index tenant signup cleanup và worker retry có backoff khi MySQL/outbox maintenance tạm thời lỗi, để maintenance không dừng luồng gửi email.
- Bổ sung regression checks cho thứ tự khóa, retry worker, migration index và namespace media tenant; full suite MySQL đạt 115/115.

## Namespace ảnh theo cửa hàng — 2026-10-18

- Ảnh upload mới nhận tên UUID có tiền tố tenant; object S3 được lưu dưới `tenants/<id>/<category>/` để một cửa hàng không ghi đè ảnh cửa hàng khác.
- Pet/product photo routes và tenant export từ chối media namespace không khớp; ảnh UUID cũ tiếp tục đọc được để không làm hỏng dữ liệu hiện có.
- Khi thay ảnh cũ, chỉ xóa object sau khi đếm tham chiếu toàn DB và xác nhận không còn bản ghi dùng tới nó.

## Onboarding và lời mời SaaS nhiều cửa hàng — 2026-10-18

- Lời mời thành viên gắn email đích, hạn 7 ngày, queue link mã hóa trong email outbox khi SMTP sẵn sàng; local vẫn có fallback thủ công. Acceptance yêu cầu đúng email đã xác minh cho tài khoản có sẵn; link được bảo vệ no-store/no-referrer, lời mời trùng bị từ chối và revoke hủy thư pending.
- Thêm self-service store signup dạng feature flag, mặc định tắt; tạo tenant, owner, pending membership và token email cùng transaction. Quyền owner chỉ bật sau khi email được xác minh; local không SMTP dùng trang manual verification no-store.
- Email worker dọn các store signup chưa xác minh sau 7 ngày nếu chưa phát sinh dữ liệu; cập nhật migration additive, checklist vận hành và hướng dẫn bật/tắt.
- Sửa migration tenancy để chỉ backfill `main` cho user chưa có membership, ngăn user của store mới bị gán nhầm vào store legacy khi redeploy.
- Full suite unit/web/MySQL integration đạt 109/109 trên DB test riêng; compileall, Compose config/build và `git diff --check` đạt. SMTP provider thật chưa được live-test; signup tiếp tục disabled by default.

## Email tài khoản, khôi phục mật khẩu và outbox — 2026-10-18

- Thêm email toàn nền tảng với xác minh sau khi đặt/thay đổi, xác thực lại mật khẩu khi đổi email và token một lần chỉ lưu SHA-256.
- Thêm khôi phục mật khẩu chỉ dành cho email đã xác minh; response không tiết lộ email có tồn tại hay không, request được giới hạn qua MySQL và reset thu hồi phiên cũ.
- Thêm outbox MySQL mã hóa payload bằng Fernet key riêng, worker lease/claim an toàn giữa workers, backoff retry hữu hạn và retention; Compose có service email-worker.
- SMTP production bắt buộc STARTTLS; adapter và retry đã kiểm thử mock, gửi thật qua provider chưa được kiểm nghiệm.
- Full suite unit/web/MySQL integration đạt 105/105 trên database test riêng; kiểm ciphertext không chứa recipient/body, retry sau lỗi SMTP, bỏ qua email hết hạn và verify/reset token flows.

## Nhật ký xác thực và thu hồi phiên — 2026-10-18

- Lưu sự kiện đăng nhập thành công, đăng xuất và chuyển cửa hàng trong nhật ký tenant; không lưu IP hoặc mật khẩu/token.
- Thêm `users.session_version` và migration cộng thêm; phiên đã ký được kiểm tra version mỗi request, bị thu hồi sau khi đổi mật khẩu hoặc khóa/mở lại membership. Bản triển khai đầu tiên yêu cầu người dùng đăng nhập lại một lần.
- Bổ sung kiểm MySQL cho giao diện activity và phiên cũ sau đổi mật khẩu; full suite đạt 98/98.

## Siết bảo mật lưu ảnh và proxy — 2026-10-18

- Ảnh mới được ghi trong thư mục 0700/tệp 0600 trên POSIX; thêm lệnh siết quyền ảnh cũ theo tên UUID, không đụng tệp khác.
- Bỏ lớp `ProxyFix` thứ hai trong WSGI để không tin `X-Forwarded-Host`/`X-Forwarded-Port`; regression test xác nhận chỉ forwarded IP/protocol được áp dụng.
- Mở rộng `/readyz` để yêu cầu toàn bộ cột runtime và composite foreign key tenant; database migrate thiếu một phần bị đánh dấu chưa sẵn sàng.
- Bỏ predicate `LIKE '%%'` ở danh sách danh mục khi không có từ khóa; ghi lại giới hạn `EXPLAIN` ở dữ liệu demo và nhu cầu benchmark catalog lớn.
- Toàn suite unit/web/MySQL integration đạt 75/75 trên database test riêng.

## Tách tài khoản MySQL runtime và migration — 2026-10-18

- Luồng web/giao dịch tiếp tục dùng `DB_USER`; initializer dùng kết nối riêng `MIGRATION_DB_USER`/`MIGRATION_DB_PASSWORD`.
- Production từ chối migration khi thiếu tài khoản riêng, dùng chung tài khoản runtime hoặc trỏ sang database khác; dev/test vẫn dùng fallback hiện hành.
- Thêm hướng dẫn cấp quyền runtime DML và quyền DDL tối thiểu cho migrator; secret migration chỉ thuộc job một lần.
- Thêm 7 unit tests; full suite mới nhất đạt 82/82. Diễn tập trên MySQL 8.4 dùng container/database riêng: migrator tạo schema được, runtime đọc được, `/readyz` trả 200 và runtime bị từ chối DDL. Đây là kiểm chứng local, chưa phải tài khoản đã provision trên production provider.

## S3-compatible media và cutover ảnh an toàn — 2026-10-18

- Thêm storage adapter private local/S3-compatible cho upload, đọc, xóa và tenant export; S3 không phát public URL/ACL, yêu cầu bucket riêng tư và HTTPS custom endpoint trong production.
- Thêm công cụ dry-run/copy/verify SHA-256 local↔S3, giữ nguyên nguồn để rollback; backup local từ chối S3 mode để không tạo archive thiếu ảnh.
- Tenant export đóng consistent-read snapshot và kết nối MySQL trước khi stream ảnh từ storage; request vẫn đồng bộ, nhưng không giữ DB connection trong lúc chờ object network.
- Sửa cập nhật sản phẩm để không xóa ảnh hiện tại khi người dùng chỉ sửa thông tin; thêm MySQL regression check.
- Thêm 14 test cases; full suite đạt 96/96. Boto3 S3 protocol được kiểm tra bằng Stubber; chưa cấu hình hoặc kiểm tra bucket cloud thật.

## Quyền dữ liệu và tìm ảnh/AI — 2026-10-18

- Thêm admin self-service export cho tenant đang chọn; yêu cầu nhập lại mật khẩu và passphrase mã hóa, ghi audit event, giới hạn tần suất và chỉ giữ tệp tạm riêng đến khi stream tải xuống đóng.
- Tách dữ liệu catalog do người dùng nhập khỏi system prompt trợ lý; JSON AI Vision lỗi/rỗng quay về tìm cục bộ có cảnh báo.
- Đổi huy hiệu kết quả tìm ảnh từ phần trăm tương tự sang thứ tự gợi ý và giải thích giới hạn điểm xếp hạng.
- Suite unit/web/MySQL integration đạt 69/69 tại thời điểm cập nhật; Docker build và kiểm tra trang export trên app local đạt.

## Mã hóa tenant export và backup — 2026-10-18

- Mã hóa bundle export ngay khi ZIP được ghi bằng AES-256-GCM; không tạo ZIP thô trung gian trong thư mục đích.
- Dẫn xuất khóa từ passphrase nhập qua prompt với PBKDF2-HMAC-SHA256, salt và nonce ngẫu nhiên; file export mới có định dạng `.pcarexport` và quyền `0600`.
- Thêm verify có xác thực mã hóa và checksum, cùng lệnh decrypt chỉ tạo ZIP riêng tư sau khi xác thực thành công.
- Mã hóa backup MySQL/ảnh cục bộ thành `.pcarebackup`; thêm verify/decrypt có xác thực và lệnh chuyển backup `.tar.gz` cũ sang định dạng mã hóa.
- Thêm lệnh chuyển tenant-export ZIP cũ sang bundle mã hóa sau khi xác minh manifest/checksum, giữ nguyên file nguồn.
- Cập nhật hướng dẫn, báo cáo, test âm sai passphrase/tamper và chuyển archive cũ; toàn suite trên MySQL 8.4.11 đạt 63/63.

## Dữ liệu và danh mục — 2026-10-17

- Mở rộng seed demo idempotent lên 12 khách, 22 sản phẩm, 10 thú cưng và 7 giao dịch lịch sử tổng hợp; thêm 4 ảnh hồ sơ thú cưng được tạo riêng cho demo.
- Bổ sung mô tả, ảnh tải lên và ngưỡng cảnh báo nhập hàng riêng cho từng sản phẩm; dashboard/trợ lý/báo cáo dùng ngưỡng theo mặt hàng.
- Cập nhật schema petcare_shop_dev bằng migration cộng thêm, không xóa hoặc ghi đè các bản ghi hiện có.
- Thêm lệnh tạo admin ban đầu an toàn cho database dữ liệu thật và cập nhật quy trình backup ảnh sản phẩm/thú cưng.

## Trợ lý và tìm thú cưng bằng ảnh — 2026-10-17

- Thêm khung chat hỗ trợ hỏi dữ liệu doanh thu, tồn kho, sản phẩm, thú cưng và luồng hóa đơn.
- Thêm client endpoint OpenAI-compatible tùy chọn; mặc định chatbot trả lời cục bộ và AI Vision tắt.
- Thêm ảnh hồ sơ cùng metadata màu lông, mắt, đặc điểm và tìm/xếp hạng thú cưng bằng đặc trưng ảnh.
- Lưu ảnh chuẩn hóa tại máy, không lưu PII vào ngữ cảnh trợ lý; bổ sung tài liệu cấu hình, demo và giới hạn.
- Thêm camera trực tiếp trên laptop, chụp khung hình để tìm; thêm camera sau điện thoại và QR LAN tùy chọn, mặc định vẫn chỉ chạy localhost.

## Chuyển hướng sang web/MySQL — 2026-10-17

- Chuyển phạm vi từ quản lý phòng khám sang quản lý cửa hàng thú cưng.
- Thay Tkinter bằng Flask/Jinja HTML và CSS responsive.
- Thay SQLite bằng MySQL/InnoDB; thêm schema cửa hàng, config và seed demo.
- Thay danh mục dịch vụ bằng sản phẩm có tồn kho.
- Thay lượt dịch vụ bằng hóa đơn sản phẩm/thú cưng, snapshot giá và giao dịch trừ kho.
- Thêm thanh toán transaction, sổ điều chỉnh tồn, buyer cho thú cưng, báo cáo doanh thu.
- Giữ tài liệu và source desktop cũ dưới docs/archive; không tự chuyển dữ liệu clinic.
- Bổ sung unit/web tests và MySQL integration tests có DB riêng.
