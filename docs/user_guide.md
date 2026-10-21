# Hướng dẫn sử dụng PetCare Manager

Ứng dụng dành cho quản trị và nhân viên cửa hàng thú cưng. Cần khởi động MySQL trước rồi chạy Flask theo [README](../README.md). Mở `http://127.0.0.1:<APP_PORT>` trong trình duyệt (mặc định port 5000). Không dùng python main.py để mở cửa sổ desktop.

Khi đăng nhập, nhập **mã cửa hàng** cùng username/password. Tài khoản chỉ thấy dữ liệu và quyền của store đang chọn. Nếu được mời vào nhiều cửa hàng, dùng menu **Chuyển cửa hàng** ở sidebar; role có thể khác nhau giữa các store. Database cũ sau migration giữ dữ liệu trong mã cửa hàng `main`.

Database mới được seed có mã cửa hàng `main` và tài khoản demo admin / Admin@123 cùng staff1 / Staff@123. Đổi mật khẩu trước khi dùng dữ liệu thật; không tái sử dụng tài khoản demo trên môi trường công khai.

## Thành viên và lời mời cửa hàng

Admin vào **Tài khoản**, chọn vai trò rồi bấm **Tạo liên kết mời**. Liên kết chỉ dùng một lần và hết hạn sau 7 ngày; có thể thu hồi khi còn chờ. Gửi liên kết riêng cho người nhận, không đăng lên nơi công khai. Người nhận có thể dùng tài khoản đã xác minh đúng email để tham gia cửa hàng, hoặc tạo tài khoản mới bằng username, tên hiển thị và mật khẩu. Khi SMTP đã cấu hình, link được gửi qua email nền; nếu chạy local không có SMTP, admin gửi link thủ công tới đúng người nhận.

## Export dữ liệu cửa hàng

Quản trị viên cửa hàng vào **Tài khoản → Xuất dữ liệu cửa hàng**, nhập lại mật khẩu hiện tại và tạo passphrase mới tối thiểu 12 ký tự hai lần. Tải xuống là bundle mã hóa riêng của cửa hàng đang chọn; thao tác được ghi audit và giới hạn tần suất. Lưu passphrase ở nơi an toàn, tách khỏi bundle; không thể khôi phục dữ liệu nếu quên. Bundle gồm CSV, metadata và ảnh; không có password hash hoặc invite token hash. Text CSV bắt đầu bằng dấu có thể chạy công thức sẽ được thêm dấu nháy đơn để bảng tính mở an toàn; số và ngày vẫn giữ nguyên. Gói tải xuống vẫn chứa dữ liệu cá nhân sau khi được giải mã, nên chỉ chia sẻ với người được ủy quyền. Export không xóa dữ liệu trên hệ thống.

Operator có quyền database vẫn dùng `python -m petcare.database.export_tenant export <slug> <đường-dẫn.pcarexport>` để tạo bundle cho quy trình vận hành. Chạy `verify` để xác thực mã hóa và checksum mà không trích xuất. Khi cần bàn giao ZIP cho quy trình khác, chạy `decrypt <bundle.pcarexport> <đường-dẫn-zip-mới>`; ZIP mới quyền `0600` chỉ được tạo sau khi xác thực thành công. ZIP sau giải mã chứa dữ liệu khách hàng và ảnh; giới hạn quyền truy cập và xóa theo chính sách lưu trữ. Export không xóa dữ liệu trên hệ thống.

ZIP export từ phiên bản cũ là plaintext và không được lệnh `verify` mới chấp nhận. Dùng `encrypt <zip-cũ> <bundle.pcarexport-mới>` để xác minh manifest/checksum và chuyển đổi; giữ ZIP gốc riêng tư cho tới khi bundle mới đã verify và sao lưu an toàn.

## Khách hàng

Vào **Khách hàng** để tìm kiếm và xem danh sách. Chọn **Thêm khách hàng**, nhập tên và số điện thoại hợp lệ, sau đó lưu. Địa chỉ và thông tin liên hệ có thể để trống nếu form cho phép.

## Sản phẩm và tồn kho

Vào **Sản phẩm** để tìm mặt hàng, giá bán, tồn kho, mức cảnh báo, mô tả và ảnh. Admin có thể thêm/cập nhật sản phẩm, tải ảnh JPEG/PNG/WebP tối đa 5 MB, đặt ngưỡng bổ sung và điều chỉnh tồn; mỗi lần thay đổi tồn cần nhập số lượng cùng lý do. Staff có thể tra cứu mặt hàng nhưng không được dùng thao tác chỉ dành cho Admin. Ảnh được chuẩn hóa và chỉ thành viên cửa hàng được xem. Backend local mặc định lưu ở `instance/product-images/`; khi dùng S3, hãy duy trì backup/versioning cho bucket cùng database.

## Thú cưng bán lẻ

Vào **Thú cưng** để quản lý từng cá thể đang bán. Mỗi cá thể có mã riêng, thông tin loài/giống, giá, màu lông, màu mắt, đặc điểm ngoại hình và ảnh hồ sơ. Ảnh hồ sơ tối đa 5 MB, định dạng JPEG/PNG/WebP; hệ thống chuẩn hóa ảnh và lưu riêng tư theo backend đã cấu hình. Chỉ hóa đơn đã thanh toán mới đánh dấu đã bán và gắn khách mua; cá thể đã bán không được bán lần nữa hoặc sửa lịch sử bán.

### Tìm thú cưng tương tự bằng ảnh

1. Admin thêm ảnh hồ sơ và mô tả màu lông/mắt/đặc điểm cho những cá thể đang bán.
2. Chọn **Tìm bằng ảnh**. Có thể tải ảnh lên, nhấn **Bật camera máy tính** để xem trực tiếp rồi **Chụp ảnh & tìm**, hoặc dùng camera sau điện thoại qua trình chọn ảnh.
3. Chế độ cục bộ so sánh màu vùng trung tâm, màu toàn ảnh và bố cục ảnh đã lưu, đồng thời dùng thuộc tính hồ sơ khi có. Điểm là thứ tự gợi ý, không phải xác suất nhận dạng; ảnh hồ sơ tạo kết quả hữu ích hơn. Bộ seed demo mới có 68 ảnh tổng hợp (32 chó, 32 mèo và 4 ảnh mẫu cũ).
4. Khi AI Vision tắt, ảnh truy vấn vẫn được gửi tới máy chủ ứng dụng để xử lý nhưng không gửi tới endpoint AI và không lưu thành hồ sơ. Nếu cần AI Vision, cấu hình endpoint tương thích OpenAI có hỗ trợ ảnh, rồi đặt `AI_VISION_ENABLED=1` trong `.env`; ảnh truy vấn khi đó được gửi tới endpoint để phân tích loài, màu lông, hoa văn, màu mắt và dáng.

Descriptor từ ảnh đã lưu trước bản nâng cấp vẫn dùng được. Operator có thể kiểm tra trước số ảnh cần cập nhật bằng `.venv/bin/python -m petcare.vision.reindex_pet_descriptors`; thêm `--apply` để ghi lại theo batch. Lệnh hỗ trợ backend ảnh local và S3.

Để mở trang trên điện thoại cùng Wi‑Fi bằng QR, bật `LAN_ACCESS_ENABLED=1`, đặt `LAN_ACCESS_BASE_URL` thành `http://<IP-laptop>:<APP_PORT>` trong `.env`, rồi khởi động lại. Xem hướng dẫn lấy IP và lưu ý mạng riêng trong [README](../README.md). Điện thoại cần đăng nhập; kết quả tìm sẽ hiển thị trên điện thoại. LAN mặc định tắt.

### Trợ lý cửa hàng

Chọn **Hỏi trợ lý** ở góc màn hình. Có thể hỏi tổng quan, doanh thu hôm nay/tuần/tháng, sản phẩm tồn thấp, tìm sản phẩm, hoặc lọc thú cưng theo loài, giống, màu lông/mắt, giới tính, mức giá. Trợ lý cũng hướng dẫn lập hóa đơn và tìm ảnh. Ví dụ: “Có mèo lông trắng dưới 5 triệu không?”, “Tìm chó Golden Retriever”, “Tìm sản phẩm thức ăn cho mèo”. Khi trả lời, nhãn dưới câu trả lời cho biết đang dùng dữ liệu MySQL local hay endpoint AI. Bấm **Xóa cuộc trò chuyện** để xóa lịch sử trong trang hiện tại và dừng chờ kết quả trên trình duyệt. Khi không cấu hình AI, trợ lý tra cứu MySQL và không gọi nhà cung cấp AI; request từ trình duyệt SaaS vẫn tới máy chủ ứng dụng. Để bật trả lời tạo sinh, thêm `AI_API_BASE_URL`, `AI_MODEL` và tùy chọn `AI_API_KEY` vào `.env`; khi cấu hình, câu hỏi cùng dữ liệu cửa hàng liên quan được gửi tới endpoint đó. Thông tin cá nhân khách hàng không nằm trong ngữ cảnh gửi.

Hồ sơ chó/mèo mới và ảnh trong seed được tạo tổng hợp bằng AI, là dữ liệu hư cấu dùng cho demo/báo cáo; chúng không thể hiện hàng tồn hoặc thú cưng thật. Trên database demo hiện có, chạy `python -m petcare.database.seed` để nạp bản ghi mới. Chỉ chạy lệnh trên database kết thúc bằng `_dev` hoặc `_test`.

## Lập và thanh toán hóa đơn

1. Mở **Hóa đơn** → **Lập hóa đơn mới**.
2. Chọn khách hàng; thêm một hay nhiều sản phẩm và số lượng, hoặc chọn cá thể thú cưng.
3. Kiểm tra tổng do máy chủ tính và tạo hóa đơn. Hóa đơn có trạng thái unpaid; việc tạo hóa đơn chưa trừ tồn.
4. Khi nhận tiền tại quầy, mở hóa đơn và chọn **Thanh toán**. Trong cùng giao dịch, hệ thống kiểm tra lại tồn, trừ kho, lưu lịch sử xuất hàng và gắn người mua cho thú cưng.
5. Hóa đơn chưa trả có thể hủy. Hóa đơn đã trả là bất biến; chưa hỗ trợ hoàn tiền hoặc trả hàng.

Tìm khách hàng theo tên/số điện thoại và mặt hàng theo mã/tên ngay trên form. Kết quả được tìm ở máy chủ và tải theo trang để không cần nạp toàn bộ danh mục lớn vào trình duyệt.

## Báo cáo

Mở **Báo cáo**, chọn khoảng ngày rồi xem doanh thu thực thu, số hóa đơn đã thanh toán, hàng bán và tồn hiện tại. Doanh thu được tính từ hóa đơn paid theo thời điểm thanh toán.

## Tài khoản và quyền

Người dùng nhấn tên/avatar ở thanh trên cùng để mở cài đặt tài khoản, rồi cập nhật tên hiển thị hoặc email sau khi nhập mật khẩu hiện tại. Tên hiển thị dùng chung ở mọi cửa hàng của tài khoản; quản trị viên cửa hàng không thể đổi tên hoặc mật khẩu toàn cục khi người dùng có nhiều membership, kể cả membership đang tạm khóa. Email mới cần xác minh trong vòng 24 giờ trước khi dùng khôi phục tài khoản. Chỉ email đã xác minh mới nhận liên kết đặt lại mật khẩu (hết hạn sau 30 phút); trang đăng nhập có **Quên mật khẩu?** và không tiết lộ email có khớp tài khoản hay không. Thư được đưa vào outbox; worker cần chạy cùng cấu hình SMTP để giao thư. Admin quản lý thành viên trong cửa hàng đang chọn tại mục **Tài khoản**: nhập email, chọn quyền rồi gửi lời mời. Tài khoản hiện có phải dùng đúng email đã xác minh. Trạng thái membership và role được kiểm tra từ database ở mỗi request; khóa hoặc hạ quyền trong store có hiệu lực ngay ở request tiếp theo.

Chủ cửa hàng và quản trị viên mở **Cài đặt cửa hàng** để cập nhật tên hiển thị và múi giờ của tenant đang chọn. Múi giờ ảnh hưởng cách định dạng thời gian và ngày báo cáo; timestamp đã lưu vẫn theo UTC. Mã cửa hàng giữ ổn định để liên kết đăng nhập không bị hỏng; tiền tệ không thể đổi cho tới khi có quy trình chuyển đổi và quy đổi lịch sử. Vai trò owner được bảo vệ riêng trong danh sách thành viên. Owner mở **Tài khoản → Bàn giao chủ cửa hàng**, chọn một quản trị viên đang hoạt động và nhập lại mật khẩu. Người nhận đăng nhập đúng cửa hàng, mở cùng trang và nhập mật khẩu của họ để chấp nhận trong 72 giờ; khi hoàn tất, owner cũ trở thành admin. Người khởi tạo có thể thu hồi yêu cầu bằng cách xác thực lại trước khi người nhận chấp thuận. Email chỉ được gửi nếu người nhận có email đã xác minh và SMTP được cấu hình; email chỉ thông báo và không thay thế đăng nhập/xác nhận.

Nếu quản trị hệ thống bật `PUBLIC_SIGNUP_ENABLED=1`, trang đăng nhập sẽ có liên kết **Tạo tài khoản cửa hàng**. Người đăng ký chọn tên cửa hàng, mã cửa hàng, tên đăng nhập và email; quyền chủ cửa hàng chỉ hoạt động sau khi xác minh email. Khi chạy local không cấu hình SMTP, trang xác nhận hiển thị link để kiểm thử thủ công. Tính năng mặc định tắt và chưa nên bật cho khách hàng thật cho tới khi có billing/giới hạn gói, điều khoản/chính sách riêng tư và chống lạm dụng ở edge.

Admin xem **Nhật ký hoạt động** để rà soát việc tạo/thu/hủy hóa đơn, điều chỉnh tồn kho và thay đổi hồ sơ khách hàng, sản phẩm, thú cưng, tài khoản. Sự kiện được ghi cùng transaction nghiệp vụ; mật khẩu, token, địa chỉ mạng, giá trị PII, ảnh và ghi chú hóa đơn không được sao chép vào nhật ký.

## Dữ liệu và khắc phục sự cố

- Không chỉnh sửa DB khi ứng dụng đang xử lý hóa đơn. Làm backup theo [hướng dẫn backup/restore](backup_restore.md).
- Nếu trang báo lỗi kết nối, kiểm tra MySQL đang chạy và các biến DB trong .env.
- Nếu không đăng nhập được, kiểm tra user còn active, role và tên database; chỉ chạy seed trên database demo `_dev`/`_test`. Database thật mới cần chạy `initialize` rồi `create_admin`, không dùng tài khoản seed.
