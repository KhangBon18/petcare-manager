# AI-4.0 Pre-Implementation Technical Audit — Pet Image Matching (`docs/AI4_VISION_AUDIT.md`)

- **Dự án**: PetCare Manager (`petcare/vision/`, `petcare/services/pet_image_service.py`, `petcare/routes/pet_routes.py`)
- **Nhánh phát hành được bảo vệ**: `solo/khang-petcare` @ `7514b472a5d9251fe26f70441cc68e0995cd6ed3` (`AI-3.4`)
- **Nhánh phát triển AI-4.0**: `feature/ai-4.0-pet-image-matching` (tách trực tiếp từ `7514b472a5d9251fe26f70441cc68e0995cd6ed3`)
- **Phạm vi tài liệu**: Kiểm toán kỹ thuật trước triển khai (**Pre-Implementation Audit**). Chưa thay đổi bất kỳ hành vi ứng dụng hiện hành nào; `0` lệnh gọi API ngoài; giữ nguyên gói nộp bài `petcare-manager-final-submission.zip`.

---

## 1. Kiến trúc Xử lý Ảnh & Tìm kiếm Hiện hành trong Mã nguồn

Qua kiểm tra trực tiếp toàn bộ mã nguồn thực tế, luồng xử lý ảnh thú cưng hiện tại gồm **6 thành phần** sau:

### 1.1. Tải ảnh lên, Kiểm tra Hợp lệ & Tiền xử lý (`petcare/vision/image_features.py`, `photo_storage.py`)
1. **Giới hạn dung lượng luồng byte (`read_upload`)**: Đọc tối đa `max_bytes + 1` (`Config.PET_IMAGE_MAX_BYTES = 5 * 1024 * 1024` = `5 MiB`) trước khi giải mã ảnh.
2. **Xác thực định dạng nội dung thật & Chống Decompression Bomb (`normalize_image_bytes`, `describe_image`)**:
   - Dùng `PIL.Image.open()` kiểm tra `source.format in {"JPEG", "PNG", "WEBP"}` (không tin `Content-Type` hay đuôi tên tệp do trình duyệt gửi lên).
   - Chặn ảnh vượt quá `MAX_PIXELS = 20_000_000` (`20 MP`).
   - Áp dụng `ImageOps.exif_transpose(source)`, chuyển về `RGB`, thu nhỏ tối đa `1600 x 1600` bằng `Image.Resampling.LANCZOS`, và mã hóa lại thành `JPEG` (`quality=88, optimize=True`) nhằm gỡ bỏ toàn bộ metadata EXIF/GPS.
3. **Lưu trữ tệp riêng tư theo Tenant (`photo_storage.py`, `media_storage.py`, `pet_routes.py`)**:
   - Đặt lại tên tệp ngẫu nhiên theo mẫu `t{tenant_id}-{uuid4().hex}.jpg` (quyền thư mục `0700`, quyền tệp `0600` trên POSIX).
   - Phục vụ ảnh qua route có xác thực `GET /pets/photo/<filename>`: gọi `pet_service.owns_photo()` kiểm tra đồng thời tiền tố `t{tenant_id}-`, quyền thành viên cửa hàng và sự tồn tại của `photo_filename` trong bảng `pets`, trả header `Cache-Control: private, no-store`.

### 1.2. Trích xuất Đặc trưng Thị giác Cục bộ (`ImageDescriptor` trong `image_features.py`)
> **Khẳng định trung thực**: Hệ thống hiện tại **KHÔNG sử dụng bất kỳ mô hình học sâu (CNN / Vision Transformer / Deep Learning) cục bộ nào**. Toàn bộ so khớp cục bộ chỉ dựa trên thống kê màu sắc và lưới độ sáng bằng thư viện `Pillow`:

- **`color_histogram` (`32` chiều)**: Thu nhỏ toàn ảnh về `96 x 96`, chuyển sang không gian màu `HSV` và lượng tử hóa thành `8 (Hue) x 2 (Saturation >= 48) x 2 (Value >= 128) = 32` bin chuẩn hóa tổng bằng `1.0`.
- **`center_color_histogram` (`32` chiều)**: Cắt vùng trung tâm `60% x 60%` của ảnh và tính cùng histogram HSV `32` bin để giảm một phần nhiễu viền nền.
- **`grayscale_grid` (`256` chiều)**: Thu nhỏ ảnh đa cấp xám (`L`) về lưới `16 x 16 = 256` điểm ảnh (`0..255`).
- **`dominant_colors` (`<= 3` nhãn tiếng Việt)**: Dùng quy tắc ngưỡng cứng `_color_name(R, G, B)` trên vùng trung tâm, giữ tối đa `3` màu chiếm `>= 8%` số điểm ảnh (tập nhãn đầu ra chỉ gồm: `đen`, `trắng`, `xám`, `vàng`, `cam`, `nâu`, `xanh lá`, `xanh dương`, `hồng` — **không có nhãn `"kem"`**).
- **Hàm độ tương đồng (`compare_images`)**:
  $$
  S_{\text{vis}}(A, B) = 0.78 \cdot \left(\frac{1}{2}\sum_{i=1}^{32}\min(h^{\text{glob}}_{A,i}, h^{\text{glob}}_{B,i}) + \frac{1}{2}\sum_{i=1}^{32}\min(h^{\text{center}}_{A,i}, h^{\text{center}}_{B,i})\right) + 0.22 \cdot \left(1 - \frac{\sum_{j=1}^{256}|g_{A,j} - g_{B,j}|}{255 \times 256}\right)
  $$

### 1.3. Băm SimHash 64-bit & Chỉ mục LSH trong MySQL (`image_features.py`, `pet_repo.py`, `schema.sql`)
- **`visual_hash` (`16` ký tự hex = `64` bit)**: Ghép `color_histogram` (`32`), `center_color_histogram` (`32`, trọng số `0.39`) và `grayscale_grid` đã trừ trung bình (`256`, trọng số `0.22`) thành vector `320` chiều, nhân vô hướng với `64` vector chiếu ngẫu nhiên cố định (`SplitMix64`, seed `0x504554434152455F`).
- **Bảng `pet_photo_lsh` (`schema.sql:293-305`)**: Chia `64` bit thành `8` dải (`band = 0..7`), mỗi dải `1` byte (`bucket_value = 0..255`). Khi truy vấn, `find_available_image_search_candidates()` dò chính xác bucket + `8` láng giềng lệch `1` bit trên mỗi dải (`8 x 9 = 72` probe qua `JSON_TABLE`), đảm bảo tìm thấy mọi ảnh có khoảng cách Hamming `<= 8`.
- **Ngưỡng kích hoạt**: Chỉ mục LSH chỉ bật khi cửa hàng có `> MAX_IMAGE_SEARCH_CANDIDATES` (`5.000`) thú cưng đang bán; dưới `5.000` hồ sơ (như bộ seed `68` ảnh), hệ thống quét tuần tự toàn bộ `pets` đang bán.

### 1.4. Xếp hạng trên `/pets/find-similar` (`petcare/services/pet_image_service.py`)
- Với mỗi cá thể ứng viên, hệ thống tính:
  - `visual_score` $\in [0, 1]$ từ `compare_images_from_json()` (`None` nếu thú cưng không có ảnh).
  - `metadata_score` $\in [0, 1]$ từ `_metadata_score()`: nếu không bật AI Vision ngoài (`analysis = None`), `metadata_score` **chỉ là kiểm tra nhị phân `0.0` hoặc `1.0`** xem `query.dominant_colors` có giao với `pet.coat_color` hay không!
  - Điểm tổng hợp:
    $$
    S_{\text{total}} = \begin{cases} 0.82 \cdot S_{\text{vis}} + 0.18 \cdot S_{\text{meta}} & \text{nếu cá thể có ảnh hồ sơ} \\ 0.35 \cdot S_{\text{meta}} & \text{nếu cá thể không có ảnh hồ sơ} \end{cases}
    $$
- Giữ tối đa `_RESULT_LIMIT = 12` hồ sơ có `S_total >= _RESULT_MIN_SCORE` (`0.12` = `12/100`).

### 1.5. Quan hệ Dữ liệu Hồ sơ Thú cưng & Thông tin Loài/Giống (`schema.sql`, `pet_service.py`)
- Bảng `pets` lưu **tối đa 1 ảnh duy nhất cho mỗi cá thể** qua 2 cột vô hướng `photo_filename VARCHAR(64) NULL` và `photo_descriptor JSON NULL` (chưa có bảng quan hệ `1:N` `pet_photos`).
- Cột `species VARCHAR(80)` và `breed VARCHAR(100)` là **ô nhập chuỗi tự do** (`<input type="text">` trên `pets/form.html`), dẫn tới tồn tại song song tiếng Việt và tiếng Anh trong các luồng khác nhau (`"Mèo"` / `"cat"`, `"Chó"` / `"dog"`, `"Thỏ"`, `"Hamster"`).
- Hàm `iter_filtered_for_image_search()` chỉ lọc theo loài **khi người dùng tự gõ tay vào ô lọc `Loài`** trên giao diện tìm ảnh; nếu để trống mặc định (`species=""`), truy vấn SQL lấy lẫn lộn toàn bộ các loài.

### 1.6. Luồng Gợi ý Thuộc tính `/pets/suggest-attributes` & `scripts/demo/vision_mock.py`
- Khi `AI_VISION_ENABLED = False` (mặc định cấu hình): chỉ trả về ước lượng màu nền/trung tâm cục bộ (`status = "uncertain"`).
- Khi chạy `classroom.sh --target qa`: `scripts/demo/vision_mock.py` lắng nghe trên `127.0.0.1` và **luôn trả về một JSON tĩnh cố định** (`{"species": "cat", "breed": "domestic shorthair", "coat_color": "gray", "eye_color": "green", "appearance_tags": ["synthetic demo image"]}`) cho mọi tệp ảnh hợp lệ mà không hề phân tích nội dung điểm ảnh.
- Adapter gọi provider ngoài (`ai_client.complete_vision`) có tồn tại nhưng mặc định tắt và chưa từng được kiểm định độ chính xác trên dữ liệu thực (`REAL MODEL ACCURACY = NOT MEASURED` trong `docs/VISION_EVALUATION_RESULTS.md`).

---

## 2. Bảng Phân định Rõ: Chức năng Thật vs Giả lập (Mock) vs Chưa Hiện thực

| Hạng mục kỹ thuật | Trạng thái hiện tại | Vị trí mã nguồn | Đánh giá thực chất |
| :--- | :---: | :--- | :--- |
| Kiểm tra định dạng thật (JPEG/PNG/WebP), giới hạn 5 MB & 20 MP, gỡ EXIF | **THẬT (Real)** | `image_features.py`, `photo_storage.py` | An toàn, đầy đủ unit test & browser E2E test. |
| Lưu trữ riêng tư theo tenant (`t{id}-{uuid}.jpg`) & kiểm tra quyền xem ảnh | **THẬT (Real)** | `photo_storage.py`, `pet_service.py` | Cách ly chặt giữa các cửa hàng, không lộ đường dẫn tĩnh. |
| So khớp histogram màu HSV 32-bin + lưới xám 16x16 + chỉ mục SimHash LSH | **THẬT (Real — Classical Heuristic)** | `image_features.py`, `pet_repo.py` | Chạy nhanh (`< 3 ms`), không cần mạng, **nhưng hoàn toàn mù ngữ nghĩa loài và hình thái động vật**. |
| Nhận diện loài tự động (`Mèo` vs `Chó` vs `Không phải thú cưng`) | **CHƯA CÓ (Missing)** | `pet_image_service.py` | Không có bộ phân loại loài cục bộ; tải ảnh mèo vẫn trả về chó. |
| Phát hiện trùng khớp chính xác ảnh hồ sơ (`SHA-256` / `pHash`) | **CHƯA CÓ (Missing)** | `photo_storage.py`, `pet_image_service.py` | Không lưu mã băm ảnh gốc/chuẩn hóa; ảnh trùng hệt vẫn có thể bị tụt hạng. |
| Dịch vụ `vision_mock.py` (`petcare-local-demo-mock`) | **GIẢ LẬP CỐ ĐỊNH (Mock)** | `scripts/demo/vision_mock.py` | Luôn trả nhãn `"cat / gray / green"` cố định để test giao diện form. |
| Kết nối Multimodal Vision API ngoài (`AI_VISION_ENABLED=1`) | **TẮT MẶC ĐỊNH / CHƯA ĐO ĐẠC** | `ai/client.py`, `pet_image_service.py` | Chỉ có khung truyền nhận JSON; chưa kiểm định độ chính xác, chi phí hay quyền riêng tư. |

---

## 3. Bằng chứng Thực nghiệm về Các Lỗi Cốt lõi của Baseline Hiện tại

Kiểm định trực tiếp hàm xếp hạng hiện hành (`0.82 * visual_score + 0.18 * metadata_score`, `_RESULT_MIN_SCORE = 0.12`, `_RESULT_LIMIT = 12`) trên toàn bộ **68 ảnh hồ sơ thú cưng** trong `assets/demo/pets/` cho thấy **4 khuyết tật nghiêm trọng** cần giải quyết ở AI-4.0:

### 3.1. Lỗi Nghiêm trọng 1 — Nhiễm chéo Loài (`Cross-Species Contamination`) ở mức `85.3%` Top-5 và `100%` Top-12
Khi người dùng tải ảnh lên `/pets/find-similar` mà không gõ bộ lọc loài thủ công:
- **Truy vấn bằng `35` ảnh Mèo**: **`29 / 35` truy vấn (`82.9%`)** bị lẫn ít nhất `1` cá thể **Chó** ngay trong Top-5 (trung bình `1.49` chó / 5 kết quả đầu), và **`35 / 35` (`100%`)** lẫn chó trong Top-12.
- **Truy vấn bằng `33` ảnh Chó**: **`29 / 33` truy vấn (`87.9%`)** bị lẫn ít nhất `1` cá thể **Mèo** ngay trong Top-5 (trung bình `1.55` mèo / 5 kết quả đầu), và **`33 / 33` (`100%`)** lẫn mèo trong Top-12.
- **Ví dụ điển hình với mèo cam (`demo-cat-03.png` — `PET-135` Gừng, mèo mướp cam)**:
  - Hạng `#1`: `PET-135` (`Mèo` Gừng — `100` điểm)
  - Hạng `#2`: **`PET-121` (`Chó` Bánh Bao — Pomeranian cam vàng — `92` điểm)**
  - Hạng `#3`: **`PET-114` (`Chó` Kiki — Yorkshire Terrier — `85` điểm)**
  - Hạng `#4`: **`PET-111` (`Chó` Đậu — Pembroke Welsh Corgi — `83` điểm)**
  - Hạng `#5`: **`PET-101` (`Chó` Sunny — Golden Retriever — `83` điểm)**
  -> **4 trên 5 kết quả đầu tiên cho một bức ảnh mèo cam lại là chó lông vàng/cam** vì cả hai đều có lông tông ấm trên nền phông sáng studio.

### 3.2. Lỗi Nghiêm trọng 2 — Nghịch lý Rớt hạng khi Tải lên Đúng Ảnh Gốc của Cửa hàng (`8 / 68` sai Top-1; `3 / 68` biến mất khỏi Top-12!)
- Khi tải lên chính tệp ảnh gốc đang gắn cho hồ sơ trong cửa hàng (`visual_score = 1.00`), có tới **`8 / 68` cá thể (`11.8%`) KHÔNG đứng ở vị trí `#1`**, đặc biệt **`3` cá thể bị đẩy văng hoàn toàn khỏi danh sách 12 kết quả hiển thị**:
  - `PET-001` (`miu-orange-cream.png`, `coat_color="vàng kem"`): chỉ đạt `82` điểm và rơi xuống **Hạng `#13`** (không xuất hiện trên giao diện!), đứng sau cả chó Corgi `PET-131` (`85` điểm) và chó Yorkshire `PET-114` (`83` điểm).
  - `PET-111` (`demo-dog-11.png`, Corgi `"vàng trắng"`): rơi xuống **Hạng `#15`** (`82` điểm).
  - `PET-118` (`demo-dog-18.png`, French Bulldog `"kem"`): rơi xuống **Hạng `#15`** (`82` điểm).
  - Các ca tụt hạng khác: `PET-125` (Hạng `#12`), `PET-156` (Hạng `#6`), `PET-109` (Hạng `#4`), `PET-155` (Hạng `#3`), `PET-142` (Hạng `#2`).
- **Nguyên nhân gốc trong mã nguồn**: Hàm `_color_name()` trong `image_features.py:75-96` không có nhãn `"kem"` và phân loại nhầm vùng lông kem/be ấm (`R > 140, B > 110, |R - B| < 75`) thành `"hồng"` hoặc `"nâu"`. Khi `dominant_colors` không trùng từ khóa với `coat_color`, `metadata_score = 0.0`, kéo tổng điểm của ảnh trùng khớp tuyệt đối xuống trần `0.82 * 1.0 + 0.18 * 0.0 = 0.82`, thấp hơn các ảnh khác loài/khác cá thể có `visual_score = 0.83` nhưng ăn trọn `metadata_score = 1.0` (`0.82 * 0.83 + 0.18 = 0.86`).

### 3.3. Lỗi Nghiêm trọng 3 — Không có Cơ chế Từ chối Ảnh Không phải Thú cưng hoặc Độ tin cậy Thấp
- Ngưỡng cắt `_RESULT_MIN_SCORE = 0.12` (`12/100`) thấp hơn rất nhiều so với mức giao thoa nền ngẫu nhiên của histogram màu (`0.35–0.55`).
- Kiểm nghiệm thực tế: tải ảnh chụp màn hình bảng hóa đơn HTML (`docs/assets/phase62/classroom-invoice.png` — hoàn toàn không có động vật) lên bộ xếp hạng hiện tại vẫn trả về **đủ `12 / 12` thú cưng** với điểm hiển thị lên tới **`54 / 100`**.

### 3.4. Độ phủ Kiểm thử Hiện có & Khoảng trống QA
- **Đã được kiểm thử tốt**: Bảo mật tệp tải lên, giới hạn dung lượng/kích thước, gỡ EXIF, quyền truy cập ảnh theo tenant, tính ổn định của dải LSH (`test_vision_search.py`), hủy/thử lại/không ghi đè form (`pet_attributes.test.cjs`, `test_vision_e2e.py`), và bộ chấm điểm độc lập (`test_vision_evaluation.py`).
- **Chưa có kiểm thử nghiệm thu**: (1) Chặn nhiễm chéo mèo <-> chó; (2) Đảm bảo ảnh trùng khớp tuyệt đối luôn đạt Hạng `#1`; (3) Xếp hạng ưu tiên mèo cam với mèo cam; (4) Từ chối trả kết quả (`0` kết quả) khi ảnh là đồ vật/văn bản, ảnh mờ nặng, đa cá thể hỗn hợp hoặc cá thể không giống bất kỳ hồ sơ nào trong kho; (5) Ràng buộc ngôn từ giao diện không bao giờ khẳng định hai ảnh chụp khác nhau là cùng một cá thể khi chưa xác minh thực tế.

