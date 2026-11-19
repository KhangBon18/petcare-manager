# Hướng dẫn sử dụng PetCare Manager

Ứng dụng dành cho quản trị và nhân viên cửa hàng thú cưng. Cần khởi động MySQL trước rồi chạy Flask theo [README](../README.md). Mở `http://127.0.0.1:<APP_PORT>` trong trình duyệt (mặc định port 5055). Không dùng python main.py để mở cửa sổ desktop.

Khi đăng nhập, nhập **mã cửa hàng** cùng username/password. Tài khoản chỉ thấy dữ liệu và quyền của store đang chọn. Nếu được mời vào nhiều cửa hàng, dùng menu **Chuyển cửa hàng** ở sidebar; role có thể khác nhau giữa các store. Database cũ sau migration giữ dữ liệu trong mã cửa hàng `main`.

Database mới được seed có mã cửa hàng `main` và tài khoản demo `admin` (quản trị) cùng `staff1` (nhân viên). Chỉ dùng các tài khoản này trong database demo cô lập; đổi thông tin xác thực trước khi chia sẻ môi trường và không tái sử dụng tài khoản demo trên môi trường công khai. Giá trị mật khẩu không được ghi trong tài liệu.

## Thành viên và lời mời cửa hàng

Admin vào **Tài khoản**, chọn vai trò rồi bấm **Tạo liên kết mời**. Liên kết chỉ dùng một lần và hết hạn sau 7 ngày; có thể thu hồi khi còn chờ. Gửi liên kết riêng cho người nhận, không đăng lên nơi công khai. Người nhận có thể dùng tài khoản đã xác minh đúng email để tham gia cửa hàng, hoặc tạo tài khoản mới bằng username, tên hiển thị và mật khẩu. Khi SMTP đã cấu hình, link được gửi qua email nền; nếu chạy local không có SMTP, admin gửi link thủ công tới đúng người nhận.

## Export dữ liệu cửa hàng

Quản trị viên cửa hàng vào **Tài khoản → Xuất dữ liệu cửa hàng**, nhập lại mật khẩu hiện tại và tạo passphrase mới tối thiểu 12 ký tự hai lần. Tải xuống là bundle mã hóa riêng của cửa hàng đang chọn; thao tác được ghi audit và giới hạn tần suất. Lưu passphrase ở nơi an toàn, tách khỏi bundle; không thể khôi phục dữ liệu nếu quên. Bundle gồm CSV, metadata và ảnh; không có password hash hoặc invite token hash. Text CSV bắt đầu bằng dấu có thể chạy công thức sẽ được thêm dấu nháy đơn để bảng tính mở an toàn. CSV dùng header ổn định, timestamp UTC ISO và số thập phân dấu chấm, không phụ thuộc ngôn ngữ giao diện; báo cáo Excel dành cho người đọc được bản địa hóa theo locale. Gói tải xuống vẫn chứa dữ liệu cá nhân sau khi được giải mã, nên chỉ chia sẻ với người được ủy quyền. Export không xóa dữ liệu trên hệ thống.

Operator có quyền database vẫn dùng `python -m petcare.database.export_tenant export <slug> <đường-dẫn.pcarexport>` để tạo bundle cho quy trình vận hành. Chạy `verify` để xác thực mã hóa và checksum mà không trích xuất. Khi cần bàn giao ZIP cho quy trình khác, chạy `decrypt <bundle.pcarexport> <đường-dẫn-zip-mới>`; ZIP mới quyền `0600` chỉ được tạo sau khi xác thực thành công. ZIP sau giải mã chứa dữ liệu khách hàng và ảnh; giới hạn quyền truy cập và xóa theo chính sách lưu trữ. Export không xóa dữ liệu trên hệ thống.

ZIP export từ phiên bản cũ là plaintext và không được lệnh `verify` mới chấp nhận. Dùng `encrypt <zip-cũ> <bundle.pcarexport-mới>` để xác minh manifest/checksum và chuyển đổi; giữ ZIP gốc riêng tư cho tới khi bundle mới đã verify và sao lưu an toàn.

## Khách hàng

Vào **Khách hàng** để tìm kiếm và xem danh sách. Chọn tên hoặc số hóa đơn để mở hồ sơ, xem thông tin liên hệ, trạng thái và lịch sử giao dịch theo trang. Tổng số hóa đơn được chia theo trạng thái; số tiền đã thu và chưa thu hiển thị riêng theo từng mã tiền tệ, không tự quy đổi.

Chọn **Lập hóa đơn** trong hồ sơ khách đang hoạt động để mở hóa đơn mới với khách đã chọn sẵn. Chọn **Sửa thông tin** để cập nhật hồ sơ. Từ danh sách hoặc trang chi tiết hóa đơn, chọn tên khách để quay lại hồ sơ.

Để tạo khách mới, chọn **Thêm khách hàng**, nhập tên và số điện thoại hợp lệ, sau đó lưu. Địa chỉ và thông tin liên hệ có thể để trống nếu form cho phép.

## Sản phẩm và tồn kho

Vào **Sản phẩm** để tìm mặt hàng, giá bán, tồn kho, mức cảnh báo, mô tả và ảnh. Admin có thể thêm/cập nhật sản phẩm, tải ảnh JPEG/PNG/WebP tối đa 5 MB, đặt ngưỡng bổ sung và điều chỉnh tồn; mỗi lần thay đổi tồn cần nhập số lượng cùng lý do. Staff có thể tra cứu mặt hàng nhưng không được dùng thao tác chỉ dành cho Admin. Ảnh được chuẩn hóa và chỉ thành viên cửa hàng được xem. Backend local mặc định lưu ở `instance/product-images/`; khi dùng S3, hãy duy trì backup/versioning cho bucket cùng database.

### Nhà cung cấp và nhập hàng

Admin mở **Quản trị → Nhập hàng** để theo dõi đơn đặt. Thêm nhà cung cấp trước nếu cửa hàng chưa có; hồ sơ có tên, người liên hệ, điện thoại, email và địa chỉ. Có thể ngừng sử dụng nhà cung cấp mà không xóa các đơn cũ.

Chọn **Lập đơn nhập**, tìm sản phẩm theo tên hoặc mã, thêm từng mặt hàng, nhập số lượng đặt và giá nhập theo tiền tệ của cửa hàng. Giá và tên/mã mặt hàng được chụp vào đơn tại thời điểm tạo. Tạo đơn chưa làm thay đổi tồn kho.

Khi hàng về, mở đơn và nhập **số lượng nhận thêm** cho từng mặt hàng. Có thể xác nhận nhiều đợt; mỗi lần nhận sẽ cộng đúng số xác nhận vào tồn, ghi người thực hiện và liên kết về đơn nhập trong lịch sử tồn kho. Đơn chuyển sang nhận đủ khi mọi dòng đã đủ số lượng. Nếu nhà cung cấp giao thiếu hoặc hủy phần còn lại, chọn **Đóng phần còn lại**; hàng đã nhận vẫn giữ trong kho và đơn đã đóng không thể nhận tiếp. Không sửa/xóa đơn lịch sử.

Mỗi đơn có tối đa 100 mặt hàng; không thể nhận vượt số lượng còn lại hoặc làm tồn vượt giới hạn hệ thống. Đơn nhập chỉ áp dụng cho sản phẩm còn hoạt động khi lập đơn; nếu sản phẩm được ngừng bán sau đó, cửa hàng vẫn có thể ghi nhận hàng đã đặt.

## Thú cưng bán lẻ

Vào **Thú cưng** để quản lý từng cá thể đang bán. Mỗi cá thể có mã riêng, thông tin loài/giống, giá, màu lông, màu mắt, đặc điểm ngoại hình và ảnh hồ sơ. Ảnh hồ sơ tối đa 5 MB, định dạng JPEG/PNG/WebP; hệ thống chuẩn hóa ảnh và lưu riêng tư theo backend đã cấu hình. Chỉ hóa đơn đã thanh toán mới đánh dấu đã bán và gắn khách mua; cá thể đã bán không được bán lần nữa hoặc sửa lịch sử bán.

Khi chọn ảnh ở form thêm/sửa thú cưng, gợi ý thuộc tính hiện tự động. Bấm **Điền vào trường đang trống** để áp dụng; dữ liệu đã nhập được giữ nguyên. Local chỉ gợi ý tông màu, có thể gồm nền ảnh; Vision khi được cấu hình mới gợi ý loài/mắt/ngoại hình. Gợi ý cần được kiểm tra trước khi lưu.

### Tìm thú cưng tương tự bằng ảnh

1. Admin thêm ảnh hồ sơ và mô tả màu lông/mắt/đặc điểm cho những cá thể đang bán.
2. Chọn **Tìm bằng ảnh**. Có thể tải ảnh lên, nhấn **Bật camera máy tính** để xem trực tiếp rồi **Chụp ảnh & tìm**, hoặc dùng camera sau điện thoại qua trình chọn ảnh.
3. Có thể lọc loài và trạng thái (đang bán/đã bán/ngừng bán/tất cả). Kết quả có điểm màu, cấu trúc, thuộc tính và lý do tương đồng; mở hồ sơ để đối chiếu. Chế độ cục bộ so sánh màu vùng trung tâm, màu toàn ảnh và bố cục ảnh đã lưu, đồng thời dùng thuộc tính hồ sơ khi có. Điểm là thứ tự gợi ý, không phải xác suất nhận dạng; ảnh hồ sơ tạo kết quả hữu ích hơn. Bộ seed demo mới có 68 ảnh tổng hợp (32 chó, 32 mèo và 4 ảnh mẫu cũ).
4. Khi AI Vision tắt, ảnh truy vấn vẫn được gửi tới máy chủ ứng dụng để xử lý nhưng không gửi tới endpoint AI và không lưu thành hồ sơ. Nếu cần AI Vision, cấu hình endpoint tương thích OpenAI có hỗ trợ ảnh, rồi đặt `AI_VISION_ENABLED=1` trong `.env`; ảnh truy vấn khi đó được gửi tới endpoint để gợi ý loài, giống khi đủ căn cứ, màu/hoa văn/độ dài lông, màu mắt, kích cỡ và dáng. Đây là gợi ý để xếp hạng, không phải kết quả nhận diện.

Descriptor từ ảnh đã lưu trước bản nâng cấp vẫn dùng được. Operator có thể kiểm tra trước số ảnh cần cập nhật bằng `.venv/bin/python -m petcare.vision.reindex_pet_descriptors`; thêm `--apply` để ghi lại theo batch. Lệnh hỗ trợ backend ảnh local và S3.

Để mở trang trên điện thoại cùng Wi‑Fi bằng QR, bật `LAN_ACCESS_ENABLED=1`, đặt `LAN_ACCESS_BASE_URL` thành `http://<IP-laptop>:<APP_PORT>` trong `.env`, rồi khởi động lại. Xem hướng dẫn lấy IP và lưu ý mạng riêng trong [README](../README.md). Điện thoại cần đăng nhập; kết quả tìm sẽ hiển thị trên điện thoại. LAN mặc định tắt.

### Trợ lý cửa hàng

Chọn **Hỏi trợ lý** ở góc màn hình. Có thể hỏi tổng quan, doanh thu hôm nay/tuần/tháng, sản phẩm tồn thấp, tìm sản phẩm, hoặc lọc thú cưng theo loài, giống, màu lông/mắt, giới tính, mức giá. Trợ lý cũng hướng dẫn lập hóa đơn và tìm ảnh. Ví dụ: “Có mèo lông trắng dưới 5 triệu không?”, “Tìm chó Golden Retriever”, “Tìm sản phẩm thức ăn cho mèo”. Kết quả tra cứu có card ảnh/giá/trạng thái và nút mở hồ sơ; số đếm tính trên toàn danh mục đang bán, tối đa 12 card mỗi câu trả lời. Khi trả lời, nhãn dưới câu trả lời cho biết đang dùng dữ liệu MySQL local hay endpoint AI. Bấm **Xóa cuộc trò chuyện** để xóa lịch sử trong trang hiện tại và dừng chờ kết quả trên trình duyệt. Khi không cấu hình AI, trợ lý tra cứu MySQL và không gọi nhà cung cấp AI; request từ trình duyệt SaaS vẫn tới máy chủ ứng dụng. Để bật trả lời tạo sinh, thêm `AI_API_BASE_URL`, `AI_MODEL` và tùy chọn `AI_API_KEY` vào `.env`; khi cấu hình, câu hỏi cùng dữ liệu cửa hàng liên quan được gửi tới endpoint đó. Thông tin cá nhân khách hàng không nằm trong ngữ cảnh gửi.

Hồ sơ và ảnh trong seed là dữ liệu tổng hợp cho demo/báo cáo; chúng không đại diện thú cưng thật. Dùng `scripts/demo/classroom.sh --target qa` để tạo dữ liệu demo cô lập. Seed thủ công chỉ hợp lệ trên database `_dev`/`_test` khớp `APP_ENV`, yêu cầu `PETCARE_DEMO_MODE=1` và mật khẩu demo riêng từ operator; không dùng trên dữ liệu thật.

## Lập và thanh toán hóa đơn

1. Mở **Hóa đơn** → **Lập hóa đơn mới**.
2. Bên trái tìm mã/tên và bấm thẻ có ảnh, giá, tồn để thêm vào đơn. Bấm lại sản phẩm để tăng số lượng đến mức tồn; mỗi cá thể thú cưng chỉ được chọn một lần với số lượng 1. Bên phải xem giỏ hàng và chọn khách. Nếu khách chưa có, bấm **+ Thêm nhanh**, điền thông tin và lưu; khách được chọn ngay mà không mất mặt hàng. Esc đóng modal và trả focus.
3. Kiểm tra tổng do máy chủ tính và tạo hóa đơn. Hóa đơn có trạng thái unpaid; việc tạo hóa đơn chưa trừ tồn.
4. Khi nhận tiền tại quầy, mở hóa đơn và chọn **Thanh toán**. Trong cùng giao dịch, hệ thống kiểm tra lại tồn, trừ kho, lưu lịch sử xuất hàng và gắn người mua cho thú cưng.
5. Hóa đơn chưa trả có thể hủy. Hóa đơn đã trả không sửa hoặc hủy; admin có thể mở hóa đơn và ghi một giao dịch trả hàng/hoàn tiền riêng. Chọn số lượng từng dòng, phương thức hoàn và tình trạng hàng nhận lại. Hàng sản phẩm chỉ cộng lại kho khi chọn **Nhận lại · có thể bán**; hàng cách ly được ghi nhận nhưng không nhập kho bán. Thú cưng nhận lại được đưa về trạng thái bán hoặc ngừng bán. Chọn **Khách chưa trả hàng** để ghi khoản hỗ trợ mà không đổi tồn/quyền sở hữu. Số tiền được tính từ snapshot hóa đơn và số lượng đã hoàn trước đó; không thể hoàn vượt quá lượng mua.

Việc ghi nhận không tự chuyển tiền qua ngân hàng hoặc cổng thanh toán. Cửa hàng cần chi tiền/chuyển khoản riêng theo quy trình của mình. Mỗi lần hoàn và thao tác kho được lưu cùng transaction, audit và lịch sử hóa đơn; gửi lại cùng yêu cầu sẽ không tạo khoản hoàn trùng. Chức năng dành cho admin.

Mở **Tìm theo tên / số điện thoại** để tìm khách hàng; catalog bên trái có bộ lọc Sản phẩm/Thú cưng và nút **Hiển thị thêm**. Kết quả được tìm ở máy chủ, có trạng thái tải và bỏ qua phản hồi cũ khi đổi từ khóa. Giỏ hàng giữ nguyên qua tìm kiếm; tổng tạm tính chỉ là xem trước, server xác thực giá/tồn khi tạo và thanh toán.

Khung trợ lý gửi bằng Enter, đóng bằng Esc và giữ focus hợp lý; chat, tìm ảnh và export có trạng thái đang xử lý và khóa gửi lặp. Toast thành công tự ẩn, lỗi có nút đóng.

## Báo cáo

Mở **Báo cáo**, chọn khoảng ngày rồi xem doanh thu thuần, số hóa đơn đã thanh toán, hàng bán/hoàn và tồn hiện tại. Tiền bán được tính theo ngày thanh toán; tiền hoàn được trừ theo ngày hoàn nên biểu đồ và Excel phản ánh dòng tiền từng ngày. Số hóa đơn vẫn đếm các hóa đơn đã thu trong kỳ, không đếm lượt hoàn. Dùng kỳ nhanh Hôm nay/7 ngày/30 ngày/Tháng này để so sánh kỳ trước cùng số ngày và xem bản tin tự động. Mở bảng ngày/chi tiết để đối chiếu.

Bấm **Xuất Excel** để tải bốn sheet tổng quan/doanh thu ngày/chi tiết/top sản phẩm, dùng đúng số liệu đang xem kể cả khi có giao dịch mới. Bản xuất có hiệu lực 15 phút; hết hạn thì tải lại báo cáo. Bấm **In / Lưu PDF** và chọn Save as PDF trong trình duyệt; bảng chi tiết tự mở khi in. Tối đa 366 ngày/5.000 dòng hàng mỗi kỳ, không cắt dữ liệu im lặng.

Dashboard và Sản phẩm có **Gợi ý bổ sung tồn kho**. Công thức dùng lượng bán paid 14/30 ngày, cảnh báo dưới 7 ngày tồn hoặc chạm ngưỡng, lập kế hoạch đủ 14 ngày; mặt hàng chưa bán dùng ngưỡng nhập lại. Đây là gợi ý đọc, không tự thay đổi kho. Mở hồ sơ sản phẩm để xem tốc độ và công thức; tồn kho của báo cáo là tại lúc chốt, không phải tồn cuối kỳ.

## Tài khoản và quyền

Người dùng nhấn tên/avatar ở thanh trên cùng để mở cài đặt tài khoản, rồi cập nhật tên hiển thị hoặc email sau khi nhập mật khẩu hiện tại. Tên hiển thị dùng chung ở mọi cửa hàng của tài khoản; quản trị viên cửa hàng không thể đổi tên hoặc mật khẩu toàn cục khi người dùng có nhiều membership, kể cả membership đang tạm khóa. Email mới cần xác minh trong vòng 24 giờ trước khi dùng khôi phục tài khoản. Chỉ email đã xác minh mới nhận liên kết đặt lại mật khẩu (hết hạn sau 30 phút); trang đăng nhập có **Quên mật khẩu?** và không tiết lộ email có khớp tài khoản hay không. Thư được đưa vào outbox; worker cần chạy cùng cấu hình SMTP để giao thư. Admin quản lý thành viên trong cửa hàng đang chọn tại mục **Tài khoản**: nhập email, chọn quyền rồi gửi lời mời. Tài khoản hiện có phải dùng đúng email đã xác minh. Trạng thái membership và role được kiểm tra từ database ở mỗi request; khóa hoặc hạ quyền trong store có hiệu lực ngay ở request tiếp theo.

Chủ cửa hàng và quản trị viên mở **Cài đặt cửa hàng** để cập nhật tên hiển thị và múi giờ của tenant đang chọn. Múi giờ ảnh hưởng cách định dạng thời gian và ngày báo cáo; timestamp đã lưu vẫn theo UTC. Mã cửa hàng giữ ổn định để liên kết đăng nhập không bị hỏng; tiền tệ không thể đổi cho tới khi có quy trình chuyển đổi và quy đổi lịch sử. Vai trò owner được bảo vệ riêng trong danh sách thành viên. Owner mở **Tài khoản → Bàn giao chủ cửa hàng**, chọn một quản trị viên đang hoạt động và nhập lại mật khẩu. Người nhận đăng nhập đúng cửa hàng, mở cùng trang và nhập mật khẩu của họ để chấp nhận trong 72 giờ; khi hoàn tất, owner cũ trở thành admin. Người khởi tạo có thể thu hồi yêu cầu bằng cách xác thực lại trước khi người nhận chấp thuận. Email chỉ được gửi nếu người nhận có email đã xác minh và SMTP được cấu hình; email chỉ thông báo và không thay thế đăng nhập/xác nhận.

Nếu quản trị hệ thống bật `PUBLIC_SIGNUP_ENABLED=1`, trang đăng nhập sẽ có liên kết **Tạo tài khoản cửa hàng**. Người đăng ký chọn tên cửa hàng, mã cửa hàng, tên đăng nhập và email; quyền chủ cửa hàng chỉ hoạt động sau khi xác minh email. Khi chạy local không cấu hình SMTP, trang xác nhận hiển thị link để kiểm thử thủ công. Tính năng mặc định tắt và chưa nên bật cho khách hàng thật cho tới khi có billing/giới hạn gói, điều khoản/chính sách riêng tư và chống lạm dụng ở edge.

Admin xem **Nhật ký hoạt động** để rà soát việc tạo/thu/hủy hóa đơn, điều chỉnh tồn kho và thay đổi hồ sơ khách hàng, sản phẩm, thú cưng, tài khoản. Sự kiện được ghi cùng transaction nghiệp vụ; mật khẩu, token, địa chỉ mạng, giá trị PII, ảnh và ghi chú hóa đơn không được sao chép vào nhật ký.

## Dữ liệu và khắc phục sự cố

- Không chỉnh sửa DB khi ứng dụng đang xử lý hóa đơn. Làm backup theo [hướng dẫn backup/restore](backup_restore.md).
- Nếu trang báo lỗi kết nối, kiểm tra MySQL đang chạy và các biến DB trong .env.
- Nếu không đăng nhập được, kiểm tra user còn active, role và tên database; chỉ chạy seed trên database demo `_dev`/`_test`. Database thật mới cần chạy `initialize` rồi `create_admin`, không dùng tài khoản seed.
