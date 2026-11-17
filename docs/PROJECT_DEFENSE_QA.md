# Bộ Câu hỏi & Trả lời Vấn đáp Bảo vệ Đồ án (`PROJECT_DEFENSE_QA`)

Bộ tài liệu này tổng hợp **18 câu hỏi thực tế** mà giảng viên môn lập trình Python / Công nghệ phần mềm thường đặt ra khi chấm bảo vệ, kèm câu trả lời ngắn gọn, chính xác và bám sát 100% vào mã nguồn `petcare/`.

---

## Nhóm A — Python, Kiến trúc Phần mềm & Flask

### Câu 1: Vì sao nhóm chọn kiến trúc `Routes -> Services -> Repositories` trên Flask thay vì viết thẳng SQL trong hàm xử lý route hoặc dùng ORM tự động?
- **Trả lời**:
  - Việc tách 3 tầng giúp phân tách rõ trách nhiệm: `petcare/routes/` chỉ xử lý giao thức HTTP, session, CSRF và trả HTML/JSON; `petcare/services/` nắm giữ quy tắc nghiệp vụ, phân quyền và quản lý ranh giới transaction (`with transaction() as connection:`); còn `petcare/repositories/` chỉ thực thi các câu lệnh SQL tham số hóa (`%s`) mà không tự ý `commit`.
  - Không dùng ORM ẩn giúp sinh viên kiểm soát tường minh khóa dòng giao dịch (`SELECT ... FOR UPDATE`), khóa ngoại kép theo `tenant_id` và hiệu năng truy vấn trên MySQL 8.4, đồng thời dễ viết unit test độc lập cho tầng service mà không phụ thuộc giao diện web.

### Câu 2: Kiến trúc đa cửa hàng (`Multi-tenant`) được thực thi như thế nào để cửa hàng A không bao giờ đọc hoặc sửa nhầm dữ liệu cửa hàng B?
- **Trả lời**:
  - Ngữ cảnh `tenant_id` không bao giờ lấy từ tham số form hay JSON của client mà được xác định phía server từ bảng hội viên `tenant_users` sau khi đăng nhập theo `store_slug`.
  - Mỗi kết nối/transaction đặt biến phiên `@petcare_tenant_id`, mọi hàm trong `petcare/repositories/` đều bắt buộc lọc `WHERE tenant_id = %s`, và ở tầng MySQL các bảng con (`invoices`, `invoice_items`, `purchase_orders`, `stock_movements`...) dùng **khóa ngoại kép (composite foreign keys)** bao gồm cả `tenant_id`. Ngay cả trong `petcare/ai/tools.py`, hệ thống từ chối mọi đối số `tenant_id` hoặc `actor_id` nếu mô hình LLM cố truyền vào.

### Câu 3: Tại sao toàn bộ tính toán tiền tệ và quy đổi đơn giá trong dự án lại dùng `decimal.Decimal` thay vì kiểu số thực `float`?
- **Trả lời**:
  - Kiểu `float` nhị phân IEEE-754 gây sai số biểu diễn thập phân (ví dụ `0.1 + 0.2 != 0.3`), dẫn tới lệch tổng hóa đơn, lệch hoàn tiền hoặc sai thứ tự xếp hạng khi so sánh sát biên ngân sách.
  - Dự án dùng `DECIMAL(12, 4)` trong MySQL kết hợp `decimal.Decimal` xuyên suốt `invoice_service.py`, `nlu.py` và `recommender_products.py` (ví dụ quy đổi gói `85g` giá `15.000 VND` ra đơn giá chuẩn trên mỗi `100g` và `1kg`), đảm bảo đối chiếu tài chính khớp tuyệt đối tới từng đồng.

---

## Nhóm B — Thiết kế Cơ sở Dữ liệu MySQL & Giao dịch Nghiệp vụ

### Câu 4: Khi hai nhân viên cùng bấm thanh toán cho sản phẩm chỉ còn 1 túi trong kho hoặc cùng bán một cá thể thú cưng, hệ thống chống bán âm kho (race condition) bằng cách nào?
- **Trả lời**:
  - Bước tạo hóa đơn (`status='unpaid'`) chưa trừ kho. Khi xác nhận thanh toán trong `invoice_service.py`, hệ thống mở một transaction InnoDB, khóa bản ghi hóa đơn và các dòng sản phẩm/thú cưng liên quan (`FOR UPDATE`), kiểm tra lại `invoice.status == 'unpaid'`, `product.stock_qty >= quantity` và `pet.sale_status == 'available'`.
  - Chỉ khi toàn bộ điều kiện thỏa mãn, hệ thống mới trừ `stock_qty`, chuyển `sale_status = 'sold'`, gắn `buyer_id`, ghi `stock_movements` và `commit`. Nếu bất kỳ dòng nào thiếu tồn hoặc đã thanh toán trước đó, toàn bộ transaction `rollback` nguyên vẹn.

### Câu 5: Cơ chế nhận hàng đơn nhập nhiều đợt (`partially_received` -> `received`) chống lỗi nhân đôi tồn kho khi mạng chập chờn người dùng bấm gửi lại form như thế nào?
- **Trả lời**:
  - Mỗi biểu mẫu nhận hàng sinh một khóa định danh `request_key` kèm dấu vân tay nội dung (`payload fingerprint`) lưu vào bảng `purchase_order_receipt_requests` có ràng buộc duy nhất theo `(tenant_id, request_key)`.
  - Nếu trình duyệt gửi lặp lại đúng `request_key` và cùng payload, hệ thống nhận diện phiếu đã xử lý và không cộng tồn kho lần thứ hai; nếu dùng lại `request_key` nhưng sửa số lượng khác đi, hệ thống báo lỗi từ chối ngay trong transaction.

### Câu 6: Nghiệp vụ hoàn trả một phần (`Partial Refund`) xử lý tồn kho và doanh thu như thế nào? Ứng dụng có chuyển tiền thật không?
- **Trả lời**:
  - Ứng dụng **không** kết nối cổng thanh toán ngân hàng thật; thanh toán và hoàn tiền là bút toán sổ cái nội bộ.
  - Khi hoàn trả trên hóa đơn đã thanh toán, hóa đơn gốc được giữ nguyên lịch sử, đồng thời hệ thống ghi thêm bản ghi bất biến vào `invoice_refunds` và `invoice_refund_items` (kiểm tra tổng số lượng hoàn tích lũy không vượt số lượng đã mua).
  - Chỉ hướng xử lý `resell` (*nhận lại hàng nguyên vẹn để bán tiếp*) mới cộng trả `stock_qty` và ghi dòng nhập lại trong `stock_movements`; hai hướng `quarantine` (*hàng lỗi cách ly*) và `not_returned` (*không thu hồi vật lý*) chỉ ghi giảm doanh thu thuần mà không cộng lại vào tồn kho đang bán.

---

## Nhóm C — Thuật toán Python, Gợi ý Sản phẩm, RAG & Thị giác Máy tính

### Câu 7: Thuật toán chấm điểm gợi ý thú cưng (`0–100` điểm) giải quyết bài toán thiếu dữ liệu và tránh suy diễn cảm tính theo giống loài ra sao?
- **Trả lời**:
  - `petcare/ai/recommender_pets.py` chạy 2 giai đoạn: Giai đoạn 1 lọc cứng theo `sale_status = 'available'`, loài, giới tính và trần/sàn ngân sách; Giai đoạn 2 chấm điểm tổng `100` gồm `budget_fit (30) + space_size_fit (25) + temperament_care_fit (25) + age_profile_completeness (20)`.
  - Điểm đặc biệt là **chính sách không định kiến giống (Zero-Stereotype Policy)**: hệ thống không tự suy đoán độ hiền hay độ hợp căn hộ chỉ dựa vào tên giống (`breed`), mà chỉ chấm dựa trên `weight_kg` và `appearance_tags` thực tế đã lưu. Nếu hồ sơ thiếu cân nặng hoặc tính cách, tiêu chí đó nhận `0` điểm thưởng (`status="unknown"`) kèm nhãn cảnh báo *"Chưa ghi nhận"* rõ ràng cho khách mua.

### Câu 8: Tại sao kho tri thức chăm sóc thú cưng (`RAG`) dùng thuật toán `Okapi BM25` viết bằng Python thuần thay vì dùng Vector Database và Embedding API bên ngoài?
- **Trả lời**:
  - Kho tri thức của cửa hàng gồm `9` tài liệu song ngữ đã được biên tập kỹ từ `WSAVA`, `ASPCA`, `AVMA`, `AAFP/ISFM` và `Cornell` (`KB-NUTR-001` đến `KB-VET-009`). Với tập tài liệu chuyên ngành cô đọng, `Okapi BM25` kết hợp unigram + bigram chuẩn hóa tiếng Việt không dấu đạt thời gian truy xuất dưới `1 ms`, giải thích chính xác từ khóa nào khớp, chạy offline 100% không tốn phí embedding API và cho kết quả lặp lại tất định trong kiểm thử tự động.
  - Hệ thống đặt ngưỡng tin cậy `MIN_BM25_SCORE = 2.2` và bộ lọc ranh giới từ cho thú ngoại lai (thỏ, hamster, bò sát...) để từ chối trung thực khi câu hỏi nằm ngoài phạm vi chó/mèo.

### Câu 9: Tính năng Tìm thú cưng bằng ảnh (`/pets/find-similar`) và gợi ý thuộc tính ảnh trên `/pets/new` hoạt động thực chất như thế nào? Có dùng mô hình AI nhận diện ảnh thật không?
- **Trả lời**:
  - Cần phân biệt rạch ròi 3 thành phần:
    1. **Tìm ảnh cục bộ (`petcare/vision/image_features.py`)**: hoàn toàn viết bằng Python + Pillow, chuẩn hóa ảnh, trích xuất histogram màu ưu tiên vùng trung tâm, lưới cấu trúc sáng/tối và mã băm SimHash LSH (`pet_photo_lsh`) để xếp hạng các ảnh hồ sơ gần màu/bố cục nhất. Đây **không phải** mô hình deep learning nhận diện giống loài.
    2. **Dịch vụ `vision_mock.py` trong launcher lớp học (`classroom.sh`)**: chỉ là dịch vụ HTTP nội bộ (`127.0.0.1`) trả JSON mẫu cố định để kiểm thử luồng giao diện duyệt gợi ý (chỉ điền vào ô trống, không ghi đè dữ liệu gõ tay, không tự lưu).
    3. **Adapter AI Vision ngoài (`AI_VISION_ENABLED`)**: mặc định tắt (`False`) để bảo vệ quyền riêng tư và không tốn chi phí API; đồ án không tuyên bố kết quả kiểm định độ chính xác Vision AI thật.

---

## Nhóm D — Tích hợp Google Gemini Free Tier, Điều phối Công cụ & An toàn Thú y

### Câu 10: Sự khác biệt cốt lõi giữa Mode A (Offline Python) và Mode B (Google Gemini Free Tier `gemini-3.5-flash-lite`) trong `PetCare AI` là gì?
- **Trả lời**:
  - **Mode A (mặc định)**: `nlu.py` phân tích câu hỏi, gọi trực tiếp các hàm trong `tools.py` và tự dựng câu trả lời xác định từ dữ liệu MySQL/BM25 với `0` kết nối mạng ngoài.
  - **Mode B (chỉ bật khi có `AI_PROVIDER_APPROVED=1` và `AI_TOOL_CALLING_ENABLED=1` trên DB QA `*_test`)**: `gemini-3.5-flash-lite` nhận câu hỏi tự nhiên của người dùng, quyết định chọn hàm nào trong tập công cụ chỉ-đọc được cấp quyền (Bước 1), sau đó Python thực thi hàm trên MySQL và đưa kết quả JSON xác thực cho Gemini diễn đạt câu trả lời tự nhiên (Bước 2). Mọi logic tính giá, lọc dị ứng, kiểm tra quyền và chốt chặn an toàn vẫn nằm 100% ở Python.

### Câu 11: Vì sao trong `llm_tool_agent.py`, bước thứ 2 gửi lên Gemini lại phải loại bỏ hoàn toàn trường `tools` và `tool_choice` thay vì chỉ đặt `tool_choice="none"`?
- **Trả lời**:
  - Qua kiểm thử thực tế với endpoint tương thích OpenAI `https://generativelanguage.googleapis.com/v1beta/openai/` của `gemini-3.5-flash-lite`, khi mảng `tools` vẫn còn hiện diện trong request thứ 2 thì tầng dịch của Gemini đôi khi vẫn sinh tiếp `tool_calls` (ví dụ tự gọi thêm `get_product_details`) bất chấp `tool_choice="none"`.
  - Việc xây dựng hàm `build_gemini_final_synthesis_messages()` chuyển kết quả thành khối dữ liệu `VERIFIED_PYTHON_TOOL_RESULTS_JSON` theo đúng thứ tự vai trò `system -> user -> assistant -> user` và **lược bỏ hoàn toàn `tools` cùng `tool_choice`** giúp bước 2 luôn kết thúc ổn định bằng văn bản tư vấn (`finish_reason="stop"`), gói gọn mỗi lượt chat trong đúng `2` API calls.

### Câu 12: Làm sao đảm bảo Gemini không "ảo giác" (bịa mã sản phẩm, sửa giá tiền khuyến mãi, hoặc kê liều thuốc nguy hiểm cho thú cưng)?
- **Trả lời**:
  - Hệ thống áp dụng **3 lớp bảo vệ**:
    1. **Trước khi gọi LLM (`safety_triage.py`)**: Mọi dấu hiệu cấp cứu thú y (khó thở, bí tiểu, ăn hoa ly/sô-cô-la/bả chuột...) hoặc hỏi liều thuốc `mg/kg` đều bị chặn ngay tại Python (`0` lệnh gọi LLM).
    2. **Trong khi thực thi công cụ (`tools.py` + `TurnGroundingLedger`)**: Chỉ truy xuất sản phẩm thật từ MySQL của đúng `tenant_id`, định dạng sẵn giá nguyên `"100000"` và `"100.000 VND"` qua `_format_price_for_llm()`.
    3. **Sau khi LLM trả lời (`verify_llm_answer_consistency`)**: Đối chiếu mọi mã SKU và con số giá tiền xuất hiện trong văn bản của Gemini với `TurnGroundingLedger`, đồng thời quét lại an toàn thú y trên câu trả lời. Nếu lệch dù chỉ một mã hoặc một mức giá, câu trả lời của LLM bị hủy và thay bằng câu trả lời chuẩn từ sổ cái Python.

### Câu 13: Chuyện gì xảy ra nếu trong lúc thuyết trình mất Wi-Fi hoặc tài khoản Google AI Studio Free Tier chạm giới hạn `HTTP 429` (`15 RPM / 500 RPD`)?
- **Trả lời**:
  - Thứ nhất, ứng dụng có `FreeTierRateLimiter` chủ động kẹp ngưỡng an toàn thấp hơn trần của Google (`10 RPM / 180.000 TPM / 450 RPD`, giãn cách `1.2 giây` giữa 2 request).
  - Thứ hai, nếu gặp lỗi mạng, quá hạn chờ (`timeout`) hoặc `HTTP 429`, hệ thống **không lặp vô hạn và không bao giờ tự chuyển sang model trả phí**; nó lập tức kích hoạt cơ chế hạ cấp an toàn (`fallback_used=True`), dựng câu trả lời từ dữ liệu đã lấy trong `TurnGroundingLedger` hoặc chuyển về **Mode A Offline Python**, đồng thời đổi huy hiệu trên giao diện sang *Dự phòng Offline Python · Dữ liệu MySQL xác thực*.

---

## Nhóm E — Bảo mật, Kiểm thử Tự động & Tính Trung thực Thực nghiệm

### Câu 14: Những biện pháp bảo mật ứng dụng web quan trọng nào đã được hiện thực hóa và kiểm chứng trong dự án?
- **Trả lời**:
  - **Xác thực & Phiên**: Mật khẩu băm `PBKDF2-HMAC-SHA256`; cookie session `HttpOnly`, `SameSite=Lax`; mỗi request nạp lại trạng thái `active` và `role` từ MySQL; có chống vét cạn `login_throttle`.
  - **Chống tấn công Web**: Kiểm tra CSRF token trên mọi request thay đổi trạng thái và API chat; Content-Security-Policy (`CSP`) chặn inline script/style; trung hòa công thức độc hại (CSV formula injection) khi xuất dữ liệu; gỡ bỏ metadata EXIF và đổi tên ngẫu nhiên ảnh tải lên.
  - **Bảo mật kết nối AI ngoài**: Bắt buộc xác minh chứng chỉ TLS (`ssl.CERT_REQUIRED` + `certifi`), chặn SSRF tới dải IP nội bộ/cloud metadata, và tự động lọc sạch mọi chuỗi khóa `AIza...` / `sk-...` / `Bearer` khỏi log và bộ nhớ phiên.

### Câu 15: Quy mô kiểm thử tự động của dự án gồm những tầng nào và làm sao đảm bảo test không làm hỏng cơ sở dữ liệu phát triển `petcare_shop_dev`?
- **Trả lời**:
  - Hệ thống có `510` bài test Python/MySQL (`unittest`), `47` bài test JavaScript (`node --test`), `26` bài test trình duyệt thực Playwright Chromium + `axe-core`, `14` bước diễn tập lớp học nối liền (`classroom_rehearsal.py`) và `6/6` job tự động trên GitHub Actions (Python `3.11`, `3.12`, `3.13`, `browser-smoke`, `source-security` Bandit/Trivy, `container`).
  - Mọi bộ test tích hợp, script khởi tạo seed và máy chủ QA (`classroom.sh`, `run_gemini_qa_web.py`) đều kiểm tra điều kiện cứng (fail-closed): bắt buộc tên database khớp biểu thức `^[A-Za-z0-9_]+_test$` và từ chối ngay nếu phát hiện `_dev`, `production` hoặc kế thừa biến môi trường DB ngoài ý muốn.

### Câu 16: Tại sao trong tài liệu báo cáo, bộ kiểm thử độc lập AI-2.2 lại ghi kết quả `39/40` (`97.5%`) mà nhóm không sửa lại cho tròn `40/40`?
- **Trả lời**:
  - Tệp `petcare/ai/final_safety_generalization_eval.py` là bộ đề kiểm thử độc lập (hold-out benchmark) được khóa checksum SHA-256 để đánh giá khách quan khả năng tổng quát hóa.
  - Ở câu `FG-MUL-01`, đề kiểm thử gốc ghi nhầm mã kỳ vọng là `'KB-NUT-001'`, trong khi mã tài liệu chuẩn của bài hướng dẫn dinh dưỡng WSAVA trong `KNOWLEDGE_CORPUS` là `'KB-NUTR-001'` (hệ thống thực tế đã truy xuất đúng `['KB-ENV-004', 'KB-NUTR-001']`). Toàn bộ `15/15` ca an toàn thú y đều đạt `100%`. Theo nguyên tắc liêm chính học thuật, nhóm giữ nguyên tệp đề kiểm thử không chỉnh sửa đáp án và báo cáo minh bạch nguyên nhân lệch 1 nhãn này.

### Câu 17: Bộ nhớ hội thoại đa lượt (`ConversationMemoryStore`) xử lý ra sao khi khách hàng đổi ý (ví dụ: bỏ trần ngân sách hoặc báo thú cưng không còn dị ứng gà)?
- **Trả lời**:
  - Trong `nlu.py`, hàm `detect_slot_removals()` nhận diện riêng các mệnh đề gỡ bỏ ràng buộc bằng cả tiếng Việt và tiếng Anh (như *"bỏ giới hạn giá"*, *"không cần dưới 200k nữa"*, *"bé không dị ứng thịt gà"*), tách biệt với mệnh đề thêm ràng buộc mới.
  - Sau đó `merge_preference_slots()` xóa đúng thuộc tính `budget_max` hoặc loại `"chicken"` khỏi `PreferenceSlots.allergies` mà vẫn bảo toàn các thông tin khác (như loài mèo, ở căn hộ), đồng thời trong Mode B các công cụ cũng hỗ trợ cờ `clear_budget` và `clear_allergies` tường minh.

### Câu 18: Nếu muốn nâng cấp đồ án này từ bản học thuật lên hệ thống vận hành thực tế tại chuỗi cửa hàng, cần hoàn thiện thêm những hạng mục nào?
- **Trả lời**:
  - Cần thực hiện 5 hạng mục chính: (1) Tích hợp cổng thanh toán và hóa đơn điện tử thực tế thay cho sổ cái thanh toán mô phỏng; (2) Diễn tập migration và sao lưu/khôi phục (`backup/restore`) trên môi trường staging có dữ liệu tương đương thực tế; (3) Cấu hình tài khoản MySQL runtime tối thiểu quyền (tách biệt tài khoản DDL migration), bật TLS/reverse proxy chuẩn và lưu trữ ảnh/export trên S3 riêng tư; (4) Kiểm thử chịu tải đồng thời (load/concurrency testing) và kiểm thử trình đọc màn hình hỗ trợ tiếp cận thực tế; (5) Nếu bật LLM thương mại, ký thỏa thuận xử lý dữ liệu và dùng gói API có SLA thay vì gói Google AI Studio Free Tier.
