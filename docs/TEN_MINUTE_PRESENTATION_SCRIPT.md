# Kịch bản Thuyết trình 10 Phút — PetCare Manager & PetCare AI

> **Mục tiêu**: Kịch bản lời thoại tiếng Việt tự nhiên, bấm giờ sát thực tế (**9 phút 05 giây** thao tác & thuyết minh 8 bước + **55 giây** kết luận & dự phòng = **10 phút 00 giây**), kèm chỉ dẫn thao tác chuột/bàn phím cụ thể trên giao diện để sinh viên tự tập dượt trước buổi bảo vệ.

---

## Chuẩn bị Trước Giờ Lên Lớp 5 Phút (Không tính vào 10 phút trình bày)

1. **Khởi động môi trường QA cô lập**:
   - Mở Terminal 1 chạy bản **Mode A Offline đầy đủ** (`PYTHON=.venv/bin/python scripts/demo/classroom.sh --target qa`), nhập 2 mật khẩu tạm thời (`>= 16` ký tự) cho `admin` và `staff1`, kiểm tra thông báo `QA demo ready at http://127.0.0.1:<port>`.
   - *(Tùy chọn nếu có mạng ổn định và muốn minh họa trực tiếp Mode B)*: Mở Terminal 2 khởi động `scripts/run_gemini_qa_web.py --port 5095 --sync-demo-passwords` trên container `petcare-gemini-live-qa` (`disposable_qa_pw`) theo đúng lệnh trong [CLASSROOM_DEMO_RUNBOOK.md](CLASSROOM_DEMO_RUNBOOK.md).
2. **Chuẩn bị trình duyệt**:
   - Đặt tỷ lệ hiển thị trình duyệt `110%` để giảng viên ngồi cuối phòng nhìn rõ số liệu.
   - Mở sẵn tệp ghi chú tạm chứa **3 câu hỏi tiếng Việt mẫu** để dán nhanh (`Cmd+V`) khi demo AI, tiết kiệm ~45 giây gõ phím trực tiếp:
     - Câu 1: `Mình nuôi mèo trưởng thành ở căn hộ, bé dị ứng thịt gà, ngân sách dưới 400k, gợi ý hạt giúp mình`
     - Câu 2: `Giảm ngân sách xuống dưới 150k thì còn những món nào phù hợp cho bé?`
     - Câu 3: `Mèo nhà mình nhai lá hoa ly và đang há miệng thở gấp!`

---

## Bảng Tổng hợp Phân bổ Thời lượng (10 Phút)

| Mốc thời gian | Thời lượng | Bước trình bày | Màn hình chính |
| :---: | :---: | :--- | :--- |
| `00:00 – 01:00` | `60 giây` | **Bước 1**: Mở đầu, Đăng nhập & Tổng quan Cửa hàng | `/login` -> `/dashboard` |
| `01:00 – 02:20` | `80 giây` | **Bước 2**: Quản lý Sản phẩm, Thú cưng & Tìm ảnh cục bộ | `/products/`, `/pets/new`, `/pets/find-similar` |
| `02:20 – 04:10` | `110 giây` | **Bước 3**: Đơn nhập hàng nhiều đợt, POS & Hoàn trả một phần | `/purchasing/`, `/invoices/new`, `/invoices/<id>` |
| `04:10 – 05:00` | `50 giây` | **Bước 4**: Báo cáo Doanh thu thuần, Xuất Excel & Xuất Tenant mã hóa | `/reports/?period=month`, `/users/export` |
| `05:00 – 05:55` | `55 giây` | **Bước 5**: Kiến trúc PetCare AI & Phân tích Vận hành Cửa hàng | `/assistant/chat` (`workspace`) |
| `05:55 – 07:35` | `100 giây` | **Bước 6**: Gợi ý Sản phẩm chuẩn đơn giá, Nhớ đa lượt & So sánh *(Offline hoặc Gemini)* | `/assistant/chat` (`shopper_preview`) |
| `07:35 – 08:20` | `45 giây` | **Bước 7**: Tra cứu Tri thức BM25 & Chốt chặn Cấp cứu Thú y | `/assistant/chat` (`shopper_preview`) |
| `08:20 – 09:05` | `45 giây` | **Bước 8**: Cách ly Quyền Nhân viên (`RBAC`) & Cơ chế Hạ cấp An toàn | `/customers/`, `/users/` (`403`) |
| `09:05 – 10:00` | `55 giây` | **Kết luận**: Tổng kết Kiểm thử, CI/CD & Nêu Minh bạch Giới hạn | Slide / `README.md` |

---

## Kịch bản Chi tiết Từng Phút (Lời thoại & Thao tác Giao diện)

### Bước 1 (`00:00 – 01:00`) — Mở đầu, Đăng nhập & Tổng quan Cửa hàng

- **Thao tác trên màn hình**:
  1. Đứng tại trang `/login`, bấm nút chuyển đổi ngôn ngữ `EN <-> VI` ở góc trên để minh họa song ngữ.
  2. Nhập `Store slug`: `main`, `Username`: `admin`, nhập mật khẩu tạm thời -> nhấn **Đăng nhập**.
  3. Tại `/dashboard`, di chuột qua 4 thẻ thống kê (`Doanh thu hôm nay`, `Khách hàng`, `Sản phẩm`, `Thú cưng đang bán`) và bảng cảnh báo nhập hàng.
- **Lời thoại gợi ý**:
  > *"Em chào thầy/cô. Hôm nay em xin trình bày đồ án **PetCare Manager tích hợp trợ lý PetCare AI** — ứng dụng quản trị cửa hàng thú cưng đa chi nhánh viết bằng Python, Flask và MySQL 8.4. Toàn bộ dữ liệu em trình diễn hôm nay đều chạy trên cơ sở dữ liệu QA tổng hợp cô lập hậu tố `_test`, không dùng mật khẩu mặc định và không chạm dữ liệu thật.*
  > *Sau khi đăng nhập vào cửa hàng `main` với quyền quản trị viên, trang Tổng quan hiển thị ngay doanh thu thuần trong ngày, số lượng khách hàng, tồn kho sắp chạm ngưỡng đặt lại và số thú cưng đang mở bán."*

---

### Bước 2 (`01:00 – 02:20`) — Quản lý Sản phẩm, Thú cưng & Tìm kiếm Ảnh Cục bộ

- **Thao tác trên màn hình**:
  1. Nhấn menu **Sản phẩm** (`/products/`) chỉ nhanh danh mục `22` sản phẩm mẫu có mã SKU, giá bán và ngưỡng cảnh báo tồn.
  2. Nhấn menu **Thú cưng** -> **Thêm thú cưng** (`/pets/new`), gõ thử từ `"vàng kem"` vào ô **Màu lông**, chọn tệp ảnh mẫu `tests/fixtures/vision/synthetic-cat-black.png` -> khi khung gợi ý hiện ra, nhấn **Áp dụng gợi ý** để chỉ rõ ô `Loài` trống được điền nhưng ô `Màu lông` đã gõ tay được giữ nguyên, và biểu mẫu **không tự động lưu**.
  3. Nhấn **Tìm bằng ảnh** (`/pets/find-similar`), chọn ảnh `assets/demo/pets/miu-orange-cream.png` -> nhấn **Tìm hồ sơ tương tự** -> cuộn qua danh sách kết quả có thanh điểm `Màu sắc / Cấu trúc / Thuộc tính`.
- **Lời thoại gợi ý**:
  > *"Ở phân hệ Danh mục, hệ thống quản lý riêng hàng hóa tính theo số lượng tồn và từng cá thể thú cưng có hồ sơ độc lập. Khi thêm thú cưng mới, giao diện hỗ trợ luồng duyệt gợi ý thuộc tính từ ảnh — trong môi trường QA lớp học này hệ thống dùng dịch vụ Vision mock cục bộ để kiểm thử cơ chế an toàn: chỉ điền vào ô đang trống, không ghi đè dữ liệu nhân viên đã nhập và không tự lưu.*
  > *Còn tại màn hình **Tìm bằng ảnh**, thuật toán Python nội sinh trích xuất histogram màu ưu tiên vùng trung tâm kết hợp bố cục sáng tối và chỉ mục SimHash LSH để xếp hạng các hồ sơ tương đồng kèm giải thích điểm minh bạch, không phụ thuộc API bên ngoài."*

---

### Bước 3 (`02:20 – 04:10`) — Nhập hàng Nhiều đợt, Bán hàng POS & Hoàn trả Một phần

- **Thao tác trên màn hình**:
  1. Mở **Nhập hàng** (`/purchasing/`), mở một đơn đặt hàng mẫu (hoặc tạo nhanh đơn `8` túi cho sản phẩm mới): nhập nhận đợt 1 là `3` -> nhấn **Ghi nhận hàng về** (trạng thái chuyển sang `Đã nhận một phần`, tồn kho `+3`) -> nhấn **Điền số còn lại** (`5`) -> nhấn **Ghi nhận hàng về** (trạng thái `Đã nhận đủ`, tồn kho `= 8`).
  2. Nhấn **Lập hóa đơn** (`/invoices/new`), chọn khách hàng mẫu, gõ tìm sản phẩm thêm số lượng `2` và chuyển tab **Thú cưng** chọn `1` bé mèo đang bán -> nhấn **Tạo hóa đơn**.
  3. Tại trang chi tiết hóa đơn (`/invoices/<id>`), chỉ rõ trạng thái `Chưa thanh toán` chưa làm giảm tồn kho -> nhấn **Xác nhận thanh toán** -> hộp thoại xác nhận -> thông báo xanh hiện lên.
  4. Kéo xuống khung **Hoàn trả hàng**, nhập số lượng `1` với phân loại **Nhận lại, có thể bán (`resell`)** -> nhấn **Ghi nhận hoàn trả**.
- **Lời thoại gợi ý**:
  > *"Điểm cốt lõi ở tầng dữ liệu là mọi thay đổi tồn kho đều nằm trong transaction MySQL có khóa dòng và sổ cái biến động `stock_movements`. Khi tạo đơn nhập `8` túi, tồn kho chưa tăng ngay mà cộng chính xác theo hai đợt nhận `3` và `5`, đồng thời có khóa chống gửi trùng request.*
  > *Tương tự tại quầy POS, lập hóa đơn nháp chưa trừ kho; chỉ khi xác nhận thanh toán, transaction mới trừ `2` đơn vị hàng từ `8` xuống `6` và chuyển cá thể thú cưng sang trạng thái `Đã bán` gắn với người mua. Khi khách trả lại `1` túi còn nguyên vẹn ở chế độ `resell`, hệ thống ghi vào sổ cái hoàn trả bất biến `invoice_refunds` và hoàn tồn kho lên `7`."*

---

### Bước 4 (`04:10 – 05:00`) — Báo cáo Doanh thu Thuần, Xuất Excel & Xuất Dữ liệu Mã hóa

- **Thao tác trên màn hình**:
  1. Mở menu **Báo cáo** (`/reports/?period=month`), chỉ vào số doanh thu thuần đã tự động trừ khoản hoàn trả vừa thực hiện -> nhấn nút **Xuất Excel** để tải tệp `.xlsx` về máy.
  2. Mở menu **Tài khoản** -> **Xuất dữ liệu cửa hàng** (`/users/export`), chỉ vào biểu mẫu xác nhận lại mật khẩu và passphrase mã hóa `AES-256-GCM` do worker nền xử lý thành gói `.pcarexport`.
- **Lời thoại gợi ý**:
  > *"Mọi giao dịch bán và hoàn trả vừa rồi được đối chiếu tức thời trên trang Báo cáo tháng. Nút **Xuất Excel** sử dụng snapshot dữ liệu có chữ ký số phía server để đảm bảo file tải về khớp đúng số liệu đang xem trên màn hình. Ngoài ra, quản trị viên có thể yêu cầu worker nền đóng gói dữ liệu riêng của cửa hàng thành tệp `.pcarexport` mã hóa chuẩn `AES-256-GCM`."*

---

### Bước 5 (`05:00 – 05:55`) — Kiến trúc PetCare AI & Phân tích Vận hành Cửa hàng

- **Thao tác trên màn hình**:
  1. Nhấn mục **Trợ lý AI** (`/assistant/chat`) trên thanh điều hướng trái.
  2. Chỉ vào **Huy hiệu trạng thái Engine** ở đầu trang và thanh chuyển đổi phạm vi **`Không gian cửa hàng`** vs **`Xem thử khách mua (QA)`**.
  3. Đang ở `Không gian cửa hàng`, bấm thẻ gợi ý sẵn **"Sản phẩm bán chạy tuần này"** (hoặc **"Tổng quan vận hành cửa hàng"**) -> chỉ vào thẻ phân tích vận hành vừa hiện ra.
- **Lời thoại gợi ý**:
  > *"Tiếp theo là trọng tâm **PetCare AI**. Hệ thống được thiết kế theo nguyên tắc Python làm chủ dữ liệu và nghiệp vụ: AI chỉ được gọi vào `13` công cụ Python chỉ-đọc, tuyệt đối không tự sinh câu lệnh SQL và không tự ý sửa dữ liệu.*
  > *Khi đứng ở phạm vi **Không gian cửa hàng**, quản trị viên có thể tra cứu nhanh mặt hàng bán chạy hoặc dự báo nhu cầu tồn kho 8 tuần trực tiếp từ dữ liệu MySQL của chi nhánh hiện tại."*

---

### Bước 6 (`05:55 – 07:35`) — Tư vấn Sản phẩm Chuẩn Đơn giá, Trí nhớ Đa lượt & So sánh

- **Thao tác trên màn hình**:
  1. Nhấn nút chuyển sang **`Xem thử khách mua (QA)`** (`shopper_preview`) — chỉ ra các gợi ý nội bộ của cửa hàng lập tức được ẩn đi. *(Nếu mở song song tab Gemini QA `:5095`, thực hiện bước này trên tab `:5095` để giảng viên thấy huy hiệu chuyển sang `Đã xác nhận kết nối Real LLM`; nếu chạy hoàn toàn offline, thực hiện ngay trên tab hiện tại)*.
  2. **Lượt 1**: Dán câu `Mình nuôi mèo trưởng thành ở căn hộ, bé dị ứng thịt gà, ngân sách dưới 400k, gợi ý hạt giúp mình` -> nhấn **Gửi**.
     - Chỉ vào dải chip ngữ cảnh (`Mèo`, `Căn hộ`, `Trưởng thành`, `Tránh: chicken`, `≤ 400.000 VND`) và `5` thẻ sản phẩm (`FOOD-001` `100.000 VND/kg`, `FOOD-004` `140.000 VND/kg`...), hoàn toàn không có sản phẩm chứa gà (`FOOD-002`, `FOOD-005`).
  3. **Lượt 2 (kiểm tra nhớ đa lượt)**: Dán câu `Giảm ngân sách xuống dưới 150k thì còn những món nào phù hợp cho bé?` -> nhấn **Gửi**.
     - Chỉ ra người dùng không cần nhắc lại loài mèo hay dị ứng gà: hệ thống vẫn giữ nguyên bộ lọc dị ứng, cập nhật chip ngân sách thành `≤ 150.000 VND` và tự động loại gói `FOOD-004` (`210.000 VND`).
  4. **Lượt 3**: Gõ `So sánh FOOD-001 và FOOD-003` -> nhấn **Gửi** -> chỉ vào bảng đối chiếu đơn giá quy đổi `100.000 VND/kg` so với `17.647 VND/100g`.
- **Lời thoại gợi ý**:
  > *"Khi chuyển sang chế độ **Xem thử khách mua**, trợ lý hỗ trợ hai chế độ: **Mode A chạy Offline 100% bằng Python** và **Mode B kết nối Google Gemini Free Tier (`gemini-3.5-flash-lite`)** qua giao thức gọi hàm 2 bước.*
  > *Ở lượt đầu tiên, hệ thống trích xuất đầy đủ điều kiện mèo trưởng thành, ở căn hộ, dị ứng thịt gà và trần giá 400 nghìn, loại bỏ cứng toàn bộ sản phẩm có gà và quy đổi đơn giá bằng kiểu `Decimal` chính xác tới từng đồng trên mỗi kg. Sang lượt thứ hai, dù em chỉ nói giảm ngân sách xuống dưới 150 nghìn, bộ nhớ phiên vẫn giữ nguyên ràng buộc dị ứng gà và tự lọc bỏ gói 210 nghìn. Kể cả khi dùng Gemini ở Mode B, mọi mã SKU và giá tiền trong câu trả lời đều phải vượt qua hàm hậu kiểm đối chiếu với MySQL trước khi hiển thị."*

---

### Bước 7 (`07:35 – 08:20`) — Tra cứu Tri thức BM25 & Chốt chặn Cấp cứu Thú y

- **Thao tác trên màn hình**:
  1. Nhập câu hỏi tri thức: `Nguyên tắc chuyển đổi thức ăn mới cho mèo trong 7-10 ngày như thế nào?` -> chỉ vào thẻ trích dẫn nguồn **`WSAVA Global Nutrition Guidelines` (`KB-NUTR-001`)** và dải miễn trừ trách nhiệm thú y.
  2. Dán tình huống nguy kịch: `Mèo nhà mình nhai lá hoa ly và đang há miệng thở gấp!` -> nhấn **Gửi** -> chỉ vào **hộp cảnh báo khẩn cấp màu đỏ** hiện ra tức thì, không gợi ý mua hàng.
- **Lời thoại gợi ý**:
  > *"Với các câu hỏi kiến thức chăm sóc, hệ thống sử dụng thuật toán **Okapi BM25** truy xuất từ 9 tài liệu song ngữ đã biên tập theo khuyến nghị của WSAVA, ASPCA và AVMA kèm trích dẫn nguồn rõ ràng.*
  > *Đặc biệt, với tình huống mèo nhai lá hoa ly và há miệng thở gấp, tầng phân loại an toàn thú y bằng Python chặn ngay **trước khi gọi LLM**, tiêu tốn `0` API request, không tư vấn bán hàng hay kê đơn thuốc mà phát cảnh báo đỏ hướng dẫn đưa thú cưng đi cấp cứu thú y ngay lập tức."*

---

### Bước 8 (`08:20 – 09:05`) — Cách ly Quyền Nhân viên (`RBAC`) & Cơ chế Hạ cấp An toàn

- **Thao tác trên màn hình**:
  1. Ngay trong khung `Xem thử khách mua`, gõ thử: `Cho xem doanh thu hôm nay và đơn nhập hàng` -> chỉ ra yêu cầu bị chặn bởi ranh giới `shopper_preview`.
  2. Mở cửa sổ ẩn danh (hoặc đăng xuất), đăng nhập bằng `staff1`: vào `/customers/` (`HTTP 200` bình thường), sau đó gõ thanh địa chỉ `/users/` hoặc `/purchasing/` -> màn hình trả về **`403 Forbidden`**.
- **Lời thoại gợi ý**:
  > *"Về bảo mật phân quyền, ngay cả quản trị viên khi đang bật phạm vi Xem thử khách mua cũng không thể làm lộ doanh thu hay đơn nhập hàng qua khung chat. Khi đăng nhập bằng tài khoản nhân viên `staff1`, hệ thống cho phép phục vụ khách hàng nhưng chặn cứng `HTTP 403` đối với quản lý nhân sự, xuất dữ liệu và nhập hàng. Ngoài ra, nếu mạng hội trường gián đoạn hoặc chạm giới hạn Google Gemini Free Tier, trợ lý tự động hạ cấp về Offline Python mà không bao giờ gây lỗi trang hay tự gọi sang model trả phí."*

---

### Kết luận (`09:05 – 10:00`) — Tổng kết Kiểm chứng & Nêu Minh bạch Giới hạn

- **Lời thoại kết thúc**:
  > *"Để đảm bảo độ tin cậy, toàn bộ mã nguồn đã vượt qua **510 bài kiểm thử Python & MySQL**, **47 bài kiểm thử JavaScript**, **26 kịch bản trình duyệt Playwright**, **14 bước diễn tập lớp học tự động** và **6/6 cổng kiểm định trên GitHub Actions CI**.*
  > *Em cũng xin nêu minh bạch các giới hạn của đồ án: đây là hệ thống học thuật chạy trên dữ liệu tổng hợp, thanh toán là bút toán nội bộ chưa nối cổng ngân hàng thật; tính năng gợi ý ảnh trong launcher lớp học dùng dịch vụ mock cục bộ; gói Gemini Free Tier có giới hạn tần suất chia sẻ; và trên bộ kiểm thử độc lập AI-2.2 bất biến, hệ thống đạt `39/40` (`97.5%`, trong đó đủ `15/15` ca an toàn thú y) do một ca trong đề kiểm thử gốc ghi nhãn `'KB-NUT-001'` thay vì mã chuẩn `'KB-NUTR-001'`. Em xin cảm ơn thầy/cô đã lắng nghe và rất mong nhận được câu hỏi từ thầy/cô ạ!"*
