# Báo cáo Nghiệm thu Thị giác Cuối cùng & Đánh giá Trung thực Định danh — `AI-4.0e`

- **Mã kiểm chuẩn**: `petcare-ai4-0e-final-release-readiness` `v4.1.0`
- **Kết luận phạm vi phát hành**: **`SAFE_FOR_RELEASE_AS_SPECIES_AND_VISUAL_SIMILARITY_ONLY`**
- **Cho phép quảng bá nhận diện cá thể chính xác (`Same-Pet Identity Confirmation`)**: **`False`** (`same_pet_multi_view_reidentification = MULTI_VIEW_IDENTITY_NOT_EVALUATED`).
- **Kiểm định toàn vẹn mô hình ONNX cục bộ**: **`PASS`** (`YOLOX-Nano` + `MobileNetV2-12` + `MobileNetV2-12-features`, `CPUExecutionProvider`, `0` gọi API ngoài).
- **Kiểm toán 5 nhãn quyết định định danh an toàn (`ALLOWED_IDENTITY_DECISIONS`)**: `473` truy vấn kiểm tra, **`0`** nhãn ngoài quy ước.

## 1. Kiểm kê Dữ liệu Thực tế vs Lịch sử vs Biến đổi Tổng hợp (`Phase 2 & Phase 3`)

| Phân nhóm dữ liệu trong kho | Số lượng thật | Bản chất độc lập | Vai trò trong `AI-4.0e` | Giới hạn thống kê |
| :--- | :---: | :--- | :--- | :--- |
| **Cá thể thật có `>= 3` ảnh chụp độc lập (`enrolled_multi_view_identities`)** | **`0` / `24` mục tiêu** | Chưa có trong repo | `CASE C` & `Metric I` -> **`MULTI_VIEW_IDENTITY_NOT_EVALUATED`** | Không bao giờ suy diễn từ ảnh cắt/nén hay gán ghép ảnh Wikimedia |
| **Ảnh chụp thực tế độc lập Wikimedia Commons (`absent_open_set_identities`)** | **`16`** (`8` mèo, `8` chó) | `1` lần chụp độc lập / tác giả thật | Nhận diện loài tự động, `CASE D/E/F/I`, kiểm thử open-set | Cỡ mẫu nhỏ (`n=16` ảnh thú thật); khoảng tin cậy Wilson 95% rộng |
| **Ảnh nhiếp ảnh thực âm tính / đa động vật / loài khác (`real_negative_photographs`)** | **`18`** (`10` đồ vật/thú bông, `4` đa thú, `4` loài khác) | Ảnh chụp thực độc lập | `CASE G`, `CASE H`, kiểm thử chống dương tính giả tự nhiên | Cỡ mẫu `n=18` ảnh thực + `16` ảnh UI/tài liệu = `34` mẫu |
| **Danh mục mẫu cửa hàng (`seed_demo_store_data`)** | **`68`** (`56` trong kho + `12` ngoài kho) | `1` chân dung mẫu / cá thể | Chỉ dùng làm **benchmark hồi quy lịch sử** (`AI-4.0a..d`), KHÔNG coi là tập holdout mới chưa chạm | Phông nền studio sạch hơn ảnh điện thoại thực địa |
| **Biến đổi cắt cúp / nén JPEG / đổi sáng có kiểm soát** | `112` biến thể `near-dup` + `112` slot kho ảnh kỹ thuật | **Biến đổi tổng hợp từ 1 ảnh gốc** | Chỉ kiểm thử cơ chế kho ảnh (`CASE B`, `CASE J`) & cổng `near_duplicate_image` (`Metric B`) | **Tuyệt đối không tính là ảnh chụp đa góc của cùng cá thể** |

## 2. Kết quả Ma trận 10 Tình huống Thực chiến (`CASE A` – `CASE J`, `Phase 4`)

| Tình huống (`Scenario`) | Nguồn dữ liệu kiểm chứng | Kết quả thực đo (`Hits / Total`) | Wilson 95% CI | Trạng thái |
| :--- | :--- | :---: | :---: | :---: |
| **`CASE A` — Tải đúng ảnh chính đã lưu -> Rank 1** | `68` ảnh chính lưu kho | **`68/68` (`100.0%`)** | `[94.7%, 100.0%]` | **`PASS`** |
| **`CASE B` — Tải đúng ảnh phụ `#2/#3` trong kho -> Rank 1** | `112` ảnh tham chiếu phụ lưu kho | **`112/112` (`100.0%`)** | `[96.7%, 100.0%]` | **`PASS`** |
| **`CASE C` — Ảnh chụp độc lập khác của thú cưng đã đăng ký** | `enrolled_multi_view_identities` (`n=0` hiện tại) | **`NOT EVALUATED`** (`0` nhận vơ danh tính) | — | **`MULTI_VIEW_IDENTITY_NOT_EVALUATED`** |
| **`CASE D` — Mèo cam khác cá thể có màu lông tương tự** | `4` mèo cam Wikimedia thật + `2` mèo cam ngoài kho | **`6/6` an toàn (`0` nhận vơ, Coat P@5=`83.3%`)** | — | **`PASS`** |
| **`CASE E` — Chó lông vàng/cam giống màu mèo -> chỉ trả về Chó** | `4` chó vàng Wikimedia thật + `13` chó vàng/kem | **`17/17` (`CSER = 0.0%`)** | — | **`PASS`** |
| **`CASE F` — Thú cưng KHÔNG có trong kho -> `0` khẳng định danh tính** | `16` ảnh thú thật Wikimedia + `12` cá thể ngoài kho | **`28/28` (`0` false exact/near-dup)** | `[87.9%, 100.0%]` | **`PASS`** |
| **`CASE G` — Ảnh phi động vật (đồ vật, thú bông, hóa đơn)** | `8` ảnh thật Wikimedia + `16` ảnh UI/tài liệu | **`24/24` từ chối (`100.0%`)** | `[86.2%, 100.0%]` | **`PASS`** |
| **`CASE H` — Ảnh có nhiều động vật (`>= 2` con)** | `6` khung hình đa thú (`4` ảnh thật Wikimedia + `2` ghép đôi) | **`6/6` từ chối (`100.0%`)** | `[61.0%, 100.0%]` | **`PASS`** |
| **`CASE I` — Kho không có ứng viên đủ giống -> trả về rỗng** | `4` mèo cam vs kho mèo đen + `2` chó đen vs kho chó trắng | **`6/6` rỗng (`100.0%`)** | `[61.0%, 100.0%]` | **`PASS`** |
| **`CASE J` — Cá thể có đủ `5` ảnh kho -> chỉ hiện `1` thẻ/cá thể** | `72` truy vấn trên kho `5` ảnh/cá thể | **`0/72` trùng lặp (`0.0%`)** | — | **`PASS`** |

## 3. Bảng Tổng hợp 11 Chỉ số Nghiệm thu Độc lập (`Metrics A` – `K`, `Phase 9`)

| Ký hiệu | Tên chỉ số | Kết quả thực đo & Mẫu số (`Denominator`) | Khoảng tin cậy / Ghi chú giới hạn |
| :---: | :--- | :--- | :--- |
| **`A`** | **Exact-Image Retrieval (`Rank-1`)** | Primary: **`68/68 (100.0%)`** · Secondary: **`112/112 (100.0%)`** (Tổng: `180/180`) | `95% CI`: `[97.9%, 100.0%]` |
| **`B`** | **Near-Duplicate Retrieval *(biến đổi tổng hợp)*** | Resize `480 q=70`: **`56/56` (`100.0%`)** · Crop `4%+Bright`: **`53/56` (`94.6%`)** · Precision: **`100.0%`** (`FP=0`) | `95% CI Recall`: `[92.4%, 99.1%]` · Chỉ đo biến đổi từ 1 ảnh gốc |
| **`C`** | **Species Recognition Accuracy *(khi chấp nhận)*** | Ảnh thật độc lập: **`12/12` (`100.0%`)** · Toàn bộ `84` ảnh lịch sử: **`79/79` (`100.0%`)** | Ảnh thật `95% CI`: `[75.8%, 100.0%]` (`n=12` ảnh thật qua cổng) |
| **`D`** | **Species Recognition Coverage *(tự động không lọc tay)*** | Ảnh thật độc lập: **`12/16` (`75.0%`)** · Toàn bộ `84` ảnh: **`79/84` (`94.0%`)** | `4/16` (`25.0%`) ảnh thật góc khó/ngược sáng chủ động từ chối an toàn thay vì đoán bừa |
| **`E`** | **Cross-Species Retrieval Errors (`CSER`)** | Ảnh thật độc lập: **`0/16` (`0.0%`)** · Toàn bộ `84` truy vấn: **`0/84` (`0.0%`)** | Chặn cứng cả mâu thuẫn bộ lọc loài thủ công |
| **`F`** | **Similarity Ranking Coat `Precision@5`** | Ảnh thật độc lập (`n=12`): **`76.9%`** · Toàn bộ lịch sử (`n=77`): **`89.8%`** | Đo mức khớp nhóm màu lông cùng loài, không khẳng định danh tính |
| **`G`** | **Open-Set Rejection Accuracy** | Mẫu không khớp/phi thú: **`46/46` (`100.0%`)** · Thú ngoài kho không nhận vơ: **`28/28 (100.0%)`** | `95% CI`: `[92.3%, 100.0%]` |
| **`H`** | **Multi-Photo Pet-Level Duplicate Rate** | Kho `3` ảnh: **`0/473`** · Kho `5` ảnh: **`0/72` (`0.0%`)** | Mỗi `pet_id` xuất hiện tối đa `1` lần |
| **`I`** | **Same-Pet Independent-Photo `Recall@1 / Recall@5 / mAP`** | **`MULTI_VIEW_IDENTITY_NOT_EVALUATED`** (`0 / 24` cá thể đa góc có xác minh) | Chỉ kích hoạt khi nạp bộ ảnh thật `>= 3` lần chụp độc lập/cá thể vào `manifest_v4_identities.json` |
| **`J`** | **Search Latency `p50 / p95` *(ảnh thật, kho 3 ảnh)*** | **`86.294 ms` / `92.315 ms`** (`n=16` ảnh thật chưa cache) | Chạy thuần CPU (`CPUExecutionProvider`) |
| **`K`** | **Model Memory & Descriptor Storage Overhead** | RAM mô hình đang chạy: **`16.81 MB`** (đĩa: `30.13 MB`) · Peak RSS: `256.03 MB` · JSON Descriptor: **`5.96 KB`** (`1` ảnh) / **`17.89 KB`** (`3` ảnh) / **`29.82 KB`** (`5` ảnh) | `0` byte nhân bản cho thú cưng `1` ảnh |

## 4. Ranh giới Pháp lý & Sản phẩm của 5 Nhãn Quyết định An toàn (`Phase 5`)

1. **`exact_stored_image_match` (`Khớp chính xác ảnh đã lưu`)**: Chỉ hiển thị khi mã băm `SHA-256` xác nhận cùng một tệp ảnh đã lưu trong `pets` hoặc `pet_reference_photos`.
2. **`near_duplicate_image` (`Ảnh gần trùng khớp với ảnh đã lưu`)**: Chỉ hiển thị khi vượt qua đồng thời cổng mã băm cảm nhận và cổng embedding/CIE-Lab đã hiệu chỉnh (`FP = 0` trên toàn bộ cá thể khác nhau).
3. **`potential_same_pet_candidate` (`Ứng viên có thể cùng cá thể · Cần xác minh`)**: Kèm cảnh báo bắt buộc `"Potential matching pet — staff verification required"`, điểm trần `<= 89`, **không bao giờ tự động xác nhận cùng cá thể**.
4. **`visually_similar_pet` (`Thú cưng ngoại hình tương tự`)**: Hiển thị tách biệt ở **Nhóm 2** bên dưới kết quả khớp ảnh lưu kho, ghi rõ chỉ tương đồng màu lông/hình thái cùng loài.
5. **`no_confident_match` (`Chưa tìm thấy kết quả đủ độ tin cậy`)**: Trả về danh sách rỗng kèm lý do cụ thể cho nhân viên cửa hàng, tuyệt đối không nhồi nhét ứng viên yếu để lấp đầy Top-K.
