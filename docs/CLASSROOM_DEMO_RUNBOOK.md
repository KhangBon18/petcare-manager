# PetCare Manager & PetCare AI — Classroom Demonstration Runbook (`AI-3.3`)

> **Mục đích**: Kịch bản trình diễn lặp lại được (10–15 phút, kèm bản rút gọn 5 phút) trên dữ liệu tổng hợp `*_test` cô lập, bao phủ trọn vẹn nghiệp vụ quản lý cửa hàng thú cưng và cả hai chế độ hoạt động của **PetCare AI** (**Mode A: Offline Python** & **Mode B: Live Google Gemini Free Tier `gemini-3.5-flash-lite`**).

---

## 0. Nguyên tắc An toàn, Xử lý Tài khoản Demo & Khởi động / Tắt hệ thống

### Xử lý thông tin đăng nhập (Credentials Hygiene)
- **Store ID / Slug đăng nhập**: `main`
- **Tài khoản mẫu tổng hợp**: `admin` (quyền quản trị cửa hàng) và `staff1` (quyền nhân viên bán hàng).
- Hệ thống **không lưu mật khẩu mặc định** trong mã nguồn hay fixture; người trình bày tự nhập 2 mật khẩu tạm thời khác nhau (`>= 16` ký tự) cho `admin` và `staff1` tại dấu nhắc ẩn khi khởi chạy.
- `GEMINI_API_KEY` chỉ nạp từ biến môi trường cục bộ của máy thuyết trình (ví dụ `launchctl getenv GEMINI_API_KEY`), tuyệt đối không ghi vào slide, `.env` commit hay khung chat.
- Không bao giờ trỏ demo vào `petcare_shop_dev` hoặc dữ liệu thật; cả hai launcher đều tự động khởi tạo schema và nạp dữ liệu tổng hợp trên database kết thúc bằng `_test`.

### Chế độ 1 — Khởi động Demo Offline toàn phần (Mode A + Workers + Vision Mock)
```bash
cd "/Users/heisenbon/Documents/Workspace Code/NNLTPython/petcare-manager"
.venv/bin/python -c "import flask, mysql.connector, PIL, cryptography"

# Launcher tự tạo container MySQL _test trong tmpfs, nạp seed tổng hợp, mở web + mail/export workers + vision mock:
PYTHON=.venv/bin/python scripts/demo/classroom.sh --target qa
```
- **Kiểm tra sẵn sàng**: `/healthz`, `/readyz` và `/workersz` tại URL loopback `http://127.0.0.1:<port>` đều trả `HTTP 200`.
- **Reset dữ liệu sạch giữa hai lượt trình bày**: gõ `r` + Enter tại dấu nhắc `petcare-demo>`.
- **Tắt và tự dọn sạch container/storage tạm**: gõ `q` + Enter (hoặc `Ctrl-C`).

### Chế độ 2 — Khởi động Máy chủ Web QA bật Live Google Gemini Free Tier (Mode B)
*(Chạy độc lập với `classroom.sh` trên container MySQL QA cô lập `127.0.0.1:33339` để trình diễn gọi công cụ thật với `gemini-3.5-flash-lite`; tái sử dụng an toàn container `petcare-gemini-live-qa` sẵn có mà không cần tạo lại hay xóa dữ liệu)*:
```bash
# 1. Tái sử dụng container MySQL QA cô lập sẵn có trên 127.0.0.1:33339 (hoặc tạo mới nếu chưa có).
#    Lưu ý: container QA tạm thời cục bộ dùng mật khẩu giả lập mặc định là disposable_qa_pw (không dùng mật khẩu thật):
QA_DB_PW="${QA_DB_PW:-disposable_qa_pw}"
docker start petcare-gemini-live-qa 2>/dev/null || \
  docker run -d --name petcare-gemini-live-qa \
    -e MYSQL_ROOT_PASSWORD="$QA_DB_PW" \
    -e MYSQL_DATABASE=petcare_gemini_qa_test \
    -p 127.0.0.1:33339:3306 mysql:8.4 \
    --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_ai_ci

# 2. Nhập 2 mật khẩu tạm thời khác nhau (>= 16 ký tự) cho admin và staff1 trong phiên trình diễn:
read -rsp "Admin QA Password (16+ chars): " _adm && echo
read -rsp "Staff QA Password (16+ chars): " _stf && echo

# 3. Khởi chạy máy chủ Web QA bật Gemini Free Tier (chỉ bind 127.0.0.1:5095).
#    Cờ --sync-demo-passwords cập nhật hash mật khẩu tạm thời vừa nhập ngay cả khi tái sử dụng DB petcare_gemini_qa_test cũ:
GEMINI_API_KEY="$(launchctl getenv GEMINI_API_KEY)" \
DB_HOST=127.0.0.1 \
DB_PORT=33339 \
DB_NAME=petcare_gemini_qa_test \
DB_USER=root \
DB_PASSWORD="$QA_DB_PW" \
PETCARE_DEMO_ADMIN_PASSWORD="$_adm" \
PETCARE_DEMO_STAFF_PASSWORD="$_stf" \
.venv/bin/python scripts/run_gemini_qa_web.py --port 5095 --sync-demo-passwords

unset _adm _stf QA_DB_PW
```
- **Tắt và dọn dẹp sau buổi trình bày**:
  ```bash
  # Nhấn Ctrl-C tại cửa sổ chạy run_gemini_qa_web.py.
  # Tạm dừng container QA (giữ nguyên schema/dữ liệu mẫu cho lần chạy thử tiếp theo):
  docker stop petcare-gemini-live-qa

  # Hoặc chỉ xóa hẳn container QA tạm thời sau khi đã hoàn tất bảo vệ đồ án:
  docker rm -f petcare-gemini-live-qa
  ```

---

## 1. Kịch bản Trình diễn Lớp học 8 Bước & Kết quả Kỳ vọng

### Bước 1 — Thiết lập & Đăng nhập phân quyền (1 phút)
- **Thao tác**: Mở trang `/login`, thử nhập sai mật khẩu để chỉ ra thông báo lỗi tiếng Việt an toàn, chuyển thử ngôn ngữ `Tiếng Việt <-> English`, sau đó đăng nhập cửa hàng `main` bằng `admin`.
- **Kết quả kỳ vọng**: Chuyển hướng vào `/dashboard`; tiêu đề cửa hàng, tiền tệ `VND` và điều hướng đầy đủ theo quyền quản trị (`Sản phẩm`, `Thú cưng`, `Khách hàng`, `Nhập hàng`, `Hóa đơn / POS`, `Báo cáo`, `Trợ lý AI`, `Nhân sự & Xuất dữ liệu`).

### Bước 2 — Luồng Quản trị Cửa hàng cốt lõi (1 phút)
- **Thao tác**: Quan sát các thẻ KPI trên `/dashboard` (doanh thu, sản phẩm sắp hết, thú cưng đang mở bán) và mở nhanh khung **Hỏi trợ lý** góc dưới phải -> bấm gợi ý *"Bán chạy tuần này"*.
- **Kết quả kỳ vọng**: Trợ lý trả về bảng xếp hạng sản phẩm bán chạy trích xuất trực tiếp từ bảng hóa đơn MySQL của cửa hàng `main` kèm liên kết nội bộ an toàn.

### Bước 3 — Quản lý Khách hàng & Hồ sơ Thú cưng + Tìm kiếm ảnh (2 phút)
- **Thao tác**:
  1. Vào `/customers/new` tạo khách hàng giả lập (`Khách Demo QA`, SĐT giả `0900000099`).
  2. Vào `/pets/new` nhập sẵn một trường thủ công (ví dụ màu lông), tải ảnh mẫu `tests/fixtures/vision/synthetic-cat-black.png` -> xem gợi ý thuộc tính từ dịch vụ **Vision mock cục bộ** (`petcare-local-demo-mock`, chỉ dùng kiểm chứng luồng duyệt gợi ý trên giao diện, không phải mô hình AI Vision thật; chỉ điền vào ô còn trống, không tự lưu) -> lưu hồ sơ thú cưng mới ở trạng thái `Đang bán` (`available`).
  3. Mở `/pets/find-similar` tải ảnh mèo mẫu để chạy thuật toán tìm kiếm tương đồng cục bộ bằng Python (histogram màu vùng trung tâm + bố cục + chỉ mục SimHash LSH, không nhận diện giống bằng deep learning).
- **Kết quả kỳ vọng**: Khách hàng và thú cưng mới được lưu vào MySQL; gợi ý ảnh không ghi đè dữ liệu người dùng đã gõ; trang tìm ảnh hiển thị danh sách hồ sơ thú cưng tương đồng có giải thích độ khớp.

### Bước 4 — Quản lý Tồn kho, Đơn nhập hàng, Bán hàng POS & Hoàn trả một phần (3 phút)
- **Thao tác**:
  1. Tạo sản phẩm mới tồn đầu `0` (`/products/new`) và nhà cung cấp (`/purchasing/suppliers/new`).
  2. Lập đơn nhập `8` đơn vị (`/purchasing/new`) -> chỉ ra trạng thái `ordered` chưa làm tăng tồn kho -> nhận từng phần `3` đơn vị (`partially_received`, tồn = `3`) -> bấm *Điền số còn lại* nhận nốt `5` đơn vị (`received`, tồn = `8`, ghi `2` dòng biến động kho).
  3. Mở `/invoices/new` (POS), lọc chọn `2` túi sản phẩm vừa nhập + `1` bé thú cưng mới tạo cho `Khách Demo QA` -> lập hóa đơn -> bấm *Xác nhận thanh toán* (mô phỏng nội bộ).
  4. Ngay tại chi tiết hóa đơn, hoàn trả `1` đơn vị sản phẩm theo hình thức *Nhận lại, có thể bán (`resell`)*, sau đó mở `/reports/?period=month` và tải file báo cáo `.xlsx`.
- **Kết quả kỳ vọng**: Sau thanh toán, tồn kho giảm từ `8 -> 6`, thú cưng chuyển sang `sold` và gắn `buyer_id`; sau hoàn `1` đơn vị, tồn kho tăng lại `6 -> 7`, sổ cái hoàn tiền ghi nhận riêng và báo cáo tháng khớp chính xác doanh thu thuần.

### Bước 5 — Tư vấn Trợ lý AI Chế độ Offline (Mode A trên `/assistant/chat`, 1.5 phút)
- **Thao tác**: Trên phiên `classroom.sh` (Mode A), mở **Trợ lý AI** (`/assistant/chat`), chuyển sang phạm vi **Xem thử khách mua (QA)** (`shopper_preview`) và gửi:
  - Câu 1: *"Mình nuôi mèo trưởng thành ở căn hộ, bé dị ứng thịt gà, ngân sách dưới 400k, gợi ý hạt giúp mình"*
  - Câu 2: *"So sánh FOOD-001 và FOOD-004"*
  - Câu 3: *"Cho xem doanh thu hôm nay và đơn nhập hàng"*
- **Kết quả kỳ vọng**:
  - Huy hiệu header hiển thị **`Chế độ Offline Python · Dữ liệu MySQL xác thực`**.
  - Câu 1 trả về `5` thẻ thức ăn còn hàng `<= 400.000 VND`, loại bỏ hoàn toàn các mã chứa thịt gà (`FOOD-002`, `FOOD-005`), kèm đơn giá quy đổi theo kg/100g.
  - Câu 2 hiển thị bảng ma trận so sánh trực quan.
  - Câu 3 bị chặn ngay bởi ranh giới `shopper_preview` (bảo vệ doanh thu và đơn nhập nội bộ).

### Bước 6 — Tư vấn Trợ lý AI Thực tế với Google Gemini Free Tier (Mode B trên `:5095`, 2 phút)
- **Thao tác**: Mở phiên web Gemini QA (`http://127.0.0.1:5095/assistant/chat?scope=shopper_preview`):
  - Quan sát huy hiệu ban đầu: **`Đã cấu hình LLM ngoài (chờ xác nhận phản hồi trực tiếp) · Kiểm chứng MySQL`**.
  - Lượt 1: *"Mình đang nuôi bé mèo trưởng thành ở căn hộ chung cư, bé bị dị ứng thịt gà. Gợi ý giúp mình thức ăn dưới 400k đang còn hàng nhé."*
  - Lượt 2 (kiểm tra trí nhớ hội thoại nhiều lượt — không nhắc lại loài/căn hộ/dị ứng gà): *"Giảm ngân sách xuống dưới 150k thì còn những món nào phù hợp cho bé?"*
- **Kết quả kỳ vọng**:
  - Huy hiệu header tự động chuyển sang **`Đã xác nhận kết nối Real LLM · Có kiểm chứng MySQL`** (`data-engine-state="real_llm_confirmed"`).
  - Thanh ngữ cảnh ghim đủ thẻ chip (`Mèo`, `Căn hộ`, `Trưởng thành`, `Tránh: chicken`, `≤ 400.000 VND` rồi cập nhật sang `≤ 150.000 VND`).
  - Lượt 2 tự động loại `FOOD-004` (`210.000 VND`) và chỉ giữ các món `<= 150.000 VND` không chứa thịt gà; chân trang câu trả lời hiển thị rõ `AI tạo sinh phê duyệt + MySQL xác thực`, tên công cụ `recommend_products` và tổng token thực tế.

### Bước 7 — Giải thích Kiến trúc Gọi Công cụ Python, Đối chiếu MySQL & Cổng An toàn Thú y (1.5 phút)
- **Thao tác**: Ngay trên phiên Gemini Mode B, nhập tình huống cấp cứu thú y:
  - *"Tự nhiên bé nhai phải lá hoa ly rồi há miệng thở gấp quá!"*
- **Kết quả kỳ vọng & Điểm nhấn thuyết trình**:
  - Tầng phân loại an toàn thú y phía server (`evaluate_veterinary_safety`) chặn **trước khi gọi Gemini** (`0` API request tiêu thụ), hiển thị ngay hộp cảnh báo khẩn cấp màu đỏ (`.ai-safety-banner--emergency`) kèm các bước sơ cứu an toàn và hướng dẫn đưa đi thú y ngay lập tức.
  - Giải thích luồng 2 bước của PetCare AI: (1) Gemini chỉ chọn tên hàm + tham số từ `8/13` công cụ chỉ-đọc được cấp quyền -> (2) Python kiểm tra schema/RBAC, truy vấn MySQL vào `TurnGroundingLedger` -> (3) Gemini tổng hợp tiếng Việt từ `VERIFIED_PYTHON_TOOL_RESULTS_JSON` (không kèm mảng `tools`) -> (4) `verify_llm_answer_consistency` hậu kiểm mọi mã SKU và giá tiền trước khi trả về giao diện.

### Bước 8 — Minh họa Hạ cấp An toàn (Safe Fallback) & Phân quyền Nhân viên (1 phút)
- **Thao tác**:
  1. Minh họa fallback: nếu chạm giới hạn tần suất Free Tier (`10 RPM`) hoặc bật `AI_PILOT_KILL_SWITCH=1`, huy hiệu chuyển sang **`Đang dùng dự phòng Offline Python · Dữ liệu MySQL xác thực`** (`offline_fallback_active`) và người dùng vẫn nhận được thẻ sản phẩm/bảng so sánh chính xác từ MySQL thay vì lỗi trang trắng.
  2. Đăng nhập tài khoản `staff1`: mở `/customers/` (`HTTP 200`), sau đó thử truy cập `/users/` hoặc `/purchasing/` (`HTTP 403 Forbidden`).

---

## 2. Phân bổ Thời lượng Chuẩn 10 Phút (10-Minute Timed Presentation Plan)

| Khung giờ | Thời lượng | Phần trình bày | Trọng tâm minh họa trên màn hình |
| :---: | :---: | :--- | :--- |
| `00:00 – 01:00` | `1.0 phút` | **Mở đầu & Đăng nhập** | Đăng nhập cửa hàng `main` (`admin`), chuyển nhanh `VI/EN`, giới thiệu kiến trúc Flask + MySQL + PetCare AI. |
| `01:00 – 02:30` | `1.5 phút` | **Khách hàng, Thú cưng & Tìm ảnh** | Tạo nhanh khách giả, xem gợi ý thuộc tính ảnh không tự lưu (`/pets/new`) và tìm ảnh tương đồng (`/pets/find-similar`). |
| `02:30 – 05:00` | `2.5 phút` | **Nhập kho, POS & Hoàn trả** | Nhận đơn nhập `3 + 5 = 8`, bán POS (`8 -> 6` + thú cưng chuyển `sold`), hoàn `1` đơn vị (`6 -> 7`), đối chiếu báo cáo tháng. |
| `05:00 – 06:30` | `1.5 phút` | **PetCare AI — Mode A Offline** | Tư vấn hạt cho mèo căn hộ dị ứng gà `< 400k` (`5` thẻ quy đổi đơn giá), so sánh SKU và chặn câu hỏi nội bộ ở `shopper_preview`. |
| `06:30 – 08:30` | `2.0 phút` | **PetCare AI — Mode B Live Gemini** | Gọi thật `gemini-3.5-flash-lite` 2 lượt liên tiếp (`< 400k` -> `< 150k`), chỉ rõ huy hiệu `real_llm_confirmed`, ngữ cảnh nhớ đa lượt và số liệu khớp MySQL. |
| `08:30 – 10:00` | `1.5 phút` | **An toàn Thú y, Fallback & RBAC** | Chặn tình huống nhai hoa ly thở gấp trước LLM (`0` API call), minh họa fallback an toàn & thử quyền `staff1` bị chặn `403` tại `/users/`. |

---

## 3. Quy trình Dự phòng khi Mất mạng hoặc Chạm Quota API (Fallback Procedures)

1. **Mất kết nối Internet tại phòng bảo vệ / Google AI Studio phản hồi chậm**:
   - Toàn bộ phần Bán lẻ, Tìm ảnh Python và **Mode A (`classroom.sh --target qa`)** chạy 100% cục bộ trên `127.0.0.1` không cần mạng.
   - Ngay trên phiên Mode B (`:5095`), nếu mất mạng hoặc quá timeout, hệ thống tự động bắt lỗi `network_error` / `timeout`, bật huy hiệu **`Đang dùng dự phòng Offline Python · Dữ liệu MySQL xác thực`** (`offline_fallback_active`) và vẫn hiển thị đầy đủ danh sách sản phẩm xác thực từ `TurnGroundingLedger` / Mode A — người trình bày tận dụng ngay tình huống này để chứng minh thiết kế chịu lỗi (fault-tolerant).
2. **Chạm giới hạn `HTTP 429` (`10 RPM` nội bộ / `15 RPM` Google Free Tier)**:
   - Không bấm gửi lặp liên tục; hệ thống tự hạ cấp an toàn về kết quả Python nội bộ mà không chuyển sang bất kỳ model trả phí nào. Đợi `15–20 giây` cửa sổ trượt làm mới hoặc tiếp tục phần còn lại trên phiên Mode A.
3. **Cần ngắt khẩn cấp gọi API ngoài**:
   - Chạy lại với `AI_PILOT_KILL_SWITCH=1` (hoặc chuyển sang tab Mode A) để khóa cứng toàn bộ kết nối ra ngoài ngay lập tức.

---

## 4. Các Giới hạn Đã biết cần Nêu Minh bạch khi Bảo vệ (Known Limitations)

1. **Môi trường học thuật / QA**: Thanh toán hóa đơn và hoàn tiền là bút toán sổ cái nội bộ (không nối cổng thanh toán thật); chưa triển khai cho môi trường bệnh viện thú y lâm sàng hay production thương mại.
2. **Hạn ngạch Google AI Studio Free Tier**: Giới hạn toàn project khoảng `~15 RPM / 250.000 TPM / 500 RPD` (ứng dụng chủ động kẹp an toàn ở `10 RPM / 180.000 TPM / 450 RPD` và giãn cách `1.2s`); độ trễ phản hồi 2 bước dao động `4–16 giây` tùy tải máy chủ Google.
3. **Độ lệch nhãn bộ kiểm thử Hold-out AI-2.2 (`39 / 40`, `97.5%`)**: Ca `FG-MUL-01` trong tệp hold-out bất biến kỳ vọng mã `'KB-NUT-001'` trong khi mã tài liệu chuẩn trong kho tri thức là `'KB-NUTR-001'` (hệ thống trả đúng `'KB-NUTR-001'`, toàn bộ `15/15` ca an toàn thú y đạt `100%` recall & precision; giữ nguyên tệp đề kiểm thử không sửa nhãn).
4. **Phạm vi loài được kiểm duyệt**: Kho sản phẩm và tri thức chăm sóc chỉ hỗ trợ **chó và mèo**; các loài thú ngoại lai (thỏ, hamster, bò sát, chim...) được từ chối minh bạch thay vì tự suy đoán.
