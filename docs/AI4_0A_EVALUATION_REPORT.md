# Báo cáo Đánh giá Định lượng Đối sánh Ảnh Thú cưng — `AI-4.0a`

- **Bộ kiểm chuẩn**: `petcare-ai4-0a-matching-benchmark` `v1.0.0`
- **Nguyên tắc phân tách**: Chia tách cứng theo `pet_code` giữa `calibration` và `acceptance_holdout` (`0` cá thể trùng lặp giữa hai tập).
- **Gọi API bên ngoài**: `0` (chạy cục bộ 100% bằng Python + Pillow).

## 1. Kiểm kê Bộ Dữ liệu & Nguồn gốc (`Dataset Provenance`)

- **Tổng số ảnh thú cưng có nhãn xác thực**: `68` (`35` mèo gồm `11` mèo cam/vàng/tam thể; `33` chó gồm `13` chó lông vàng/cam/kem).
- **Phân bổ kho cửa hàng kiểm thử**: `56` cá thể đăng ký trong kho (`enrolled`) + `12` cá thể giữ ngoài kho (`absent_from_db`: `6` calibration, `6` acceptance_holdout).
- **Mẫu âm tính phi động vật (`non_animal`)**: `16` ảnh (`8` calibration, `8` acceptance_holdout) từ ảnh chụp giao diện thực và trình sinh thủ tục tất định.

## 2. So sánh Trực tiếp: Baseline Cũ (`AI-3.4`) vs Bản Cải tiến (`AI-4.0a`)

| Chỉ số đo lường | Baseline `AI-3.4` (Holdout) | Baseline `AI-3.4` (Toàn bộ) | Mới `AI-4.0a` (Calibration) | **Mới `AI-4.0a` (Acceptance Holdout)** | Mới `AI-4.0a` (Toàn bộ) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Exact-Image Rank-1 (`EIRA@1`, ảnh gốc)** | `88.2%` (`30/34`) | `86.8%` (`59/68`) | `100.0%` (`34/34`) | **`100.0%` (`34/34`)** | `100.0%` (`68/68`) |
| **Exact Re-encoded JPEG Rank-1** | `85.7%` | `85.7%` | `100.0%` | **`100.0%`** | `100.0%` |
| **Near-Duplicate Precision (`near_duplicate_image`)** | — | — | `100.0%` (`FP=0`) | **`100.0%` (`FP=0`)** | `100.0%` (`FP=0`) |
| **Near-Duplicate Recall — Resize `480px` + JPEG `q=70`** | — | — | `100.0%` | **`100.0%`** | `100.0%` |
| **Near-Duplicate Recall — Crop `4%` + Lệch sáng `+6%`** | — | — | `0.0%` | **`0.0%`** | `0.0%` |
| **Lỗi chéo loài Mèo <-> Chó (`CSER` không lọc tay)** | `100.0%` (`34/34`) | `100.0%` (`68/68`) | `0.0%` (`0/34`) | **`0.0%` (`0/34`)** | `0.0%` (`0/68`) |
| **Dương tính giả trên ảnh phi động vật (mặc định)** | `100.0%` | `100.0%` | `0.0%` | **`0.0%`** | `0.0%` |
| **Từ chối ảnh phi động vật kể cả khi ép lọc `Loài=Mèo`** | `0.0%` | `0.0%` | `100.0%` | **`100.0%`** | `100.0%` |
| **Tỷ lệ từ chối an toàn khi ảnh ngoài kho chưa rõ loài** | `0.0%` | `0.0%` | `100.0%` | **`100.0%`** | `100.0%` |
| **Nhận vơ `exact`/`near_dup` trên thú cưng ngoài kho** | — | — | `0` | **`0`** | `0` |
| **Precision màu lông tương đồng cho Mèo cam (`sP@5`)** | `36.7%` (lẫn chó `6/6`) | `34.5%` (lẫn chó `10/11`) | `100.0%` (lẫn chó `0/5`) | **`100.0%` (lẫn chó `0/6`)** | `100.0%` |
| **Độ trễ tìm kiếm `p50 / p95` (ms)** | — | — | `21.15 / 47.543 ms` | **`21.386 / 27.298 ms`** | `21.373 / 46.405 ms` |

## 3. Các Khả năng Chưa Đánh giá / Chưa Hỗ trợ ở `AI-4.0a` (`Unevaluated Capabilities`)

- **`same_pet_multi_view_reidentification` — `NOT_EVALUATED`**: Repository contains at most 1 synthetic image per pet record; resized/cropped variants only measure near-duplicate image invariance, never cross-pose individual recognition.
- **`automatic_unfiltered_species_classification_on_novel_photos` — `NOT_SUPPORTED_IN_AI4_0A`**: No trained cat/dog classifier is bundled in AI-4.0a; novel photos without an exact/near-duplicate store photo match safely abstain unless the user selects an explicit species filter.
- **`natural_textured_non_animal_scenes_and_multi_pet_frames` — `NOT_EVALUATED_AWAITING_OBJECT_DETECTOR`**: Flat/UI/document/graphic negatives are rejected via calibrated texture gating, but complex natural non-animal photos (e.g. fur-like rugs/foliage with manual species selected) and multi-pet frames require a trained local object detector in AI-4.0b/c.
- **`crop_shifted_near_duplicate_alignment` — `CONSERVATIVELY_ABSTAINED_IN_AI4_0A`**: Global 8x8 perceptual hashes shift under >=4% spatial cropping and overlap with distinct centered studio cat portraits; AI-4.0a enforces a 100%-precision near-duplicate gate (0 false positives) and defers crop-invariant alignment to foreground embeddings in AI-4.0b/c.

## 4. Đánh giá Lộ trình Tiếp theo (`AI-4.0b / AI-4.0c`) & Khoảng trống Dữ liệu

1. **Bộ phân loại loài Mèo/Chó đáng tin cậy (`Reliable Cat/Dog Classification`)**:
   - Không được giả định một mạng xương sống `ImageNet-1K` tổng quát là bộ phân loại Mèo/Chó đã hiệu chỉnh sẵn (vì xác suất softmax trên 1.000 lớp bị phân mảnh theo giống và chưa hiệu chỉnh với ảnh ngoài phân phối).
   - Cần đầu phân loại chuyên biệt `4` lớp (`cat`, `dog`, `other_pet`, `non_animal`) huấn luyện/tinh chỉnh có hiệu chỉnh nhiệt độ (`Temperature Scaling`) và cổng từ chối `margin` trên tập `calibration` trước khi gỡ bỏ yêu cầu chọn `Loài` thủ công cho ảnh mới ngoài kho.
2. **Phát hiện ảnh phi động vật tự nhiên (`Natural Non-Animal Detection`)**:
   - Ngưỡng `flat_pixel_ratio > 0.68` ở `AI-4.0a` loại bỏ `100%` ảnh chụp màn hình UI, hóa đơn, tài liệu, mã vạch và đồ họa phẳng, nhưng **không thể** loại bỏ ảnh tự nhiên giàu chi tiết phi động vật (thảm lông nhân tạo, thú nhồi bông, tán cây, ghế sofa) nếu người dùng chủ động ép bộ lọc `Loài=Mèo`. Cần cổng Object Detector (`SSDLite320-MobileNetV3` / `YOLOv8n` INT8 ONNX) xác nhận sự hiện diện của động vật thật.
3. **Phát hiện khung hình nhiều con vật (`Multiple-Animal Detection`)**:
   - Histogram toàn khung hoặc cắt tâm `56%` sẽ trộn màu lông khi có `>= 2` thú cưng (ví dụ 1 mèo cam + 1 chó trắng). Cần bộ phát hiện hộp giới hạn (`bounding box` + `NMS`) để đếm số lượng chủ thể và yêu cầu chọn vùng cắt hoặc cảnh báo.
4. **Vector nhúng nhận thức tiền cảnh (`Foreground-Aware Visual Embeddings`)**:
   - Cắt vùng hộp giới hạn con vật từ Detector trước khi đưa qua mạng nhúng nhẹ cục bộ (`MobileNetV3` / `DINOv2-Small` INT8 ONNX) để bất biến với cắt viền (`crop >= 4%`), góc chụp nghiêng và nền phòng phức tạp.
5. **Độ tương đồng màu lông cam (`Orange Coat Similarity`)**:
   - Hồ sơ `subject_coat_profile` khử màu viền nền ở `AI-4.0a` đã đạt `100%` `sP@5` trên ảnh chân dung nền studio hiện có, nhưng với ảnh chụp dưới đèn vàng ấm (`warm indoor tungsten`) mèo trắng/kem có thể bị dịch sắc độ sang cam. `AI-4.0b/c` cần cân bằng trắng (`Gray-World / Shades-of-Gray`) kết hợp phân đoạn tiền cảnh trong không gian `CIE-Lab`.
6. **Nhận diện lại cùng một cá thể (`Same-Pet Re-Identification`)**:
   - Vẫn giữ trạng thái **`NOT_EVALUATED`** và **tuyệt đối không tuyên bố nhận diện danh tính cá thể** từ ảnh đơn lẻ. Muốn đánh giá khả năng gợi ý cùng cá thể qua nhiều góc chụp cần tối thiểu `>= 30` cá thể thật (`15` mèo, `15` chó) x `3–5` ảnh độc lập khác góc/khác nền cho mỗi cá thể.
7. **Khoảng trống dữ liệu có nhãn cần bổ sung (`Exact Labeled Data Gaps`)**:
   - `>= 120` ảnh chụp điện thoại thực tế của mèo & chó trong bối cảnh phòng/lồng/sân (không phải ảnh cắt contact sheet nền trơn) để hiệu chỉnh ngưỡng Classifier/Detector.
   - `>= 40` ảnh âm tính tự nhiên giàu kết cấu (`hard natural negatives`: thú bông, chăn lông, quần áo, đồ nội thất gỗ/vàng cam, cây cảnh).
   - `>= 25` ảnh khung hình chứa `2+` con vật (cùng loài và khác loài Mèo + Chó).
   - `>= 15` ảnh Thỏ & Hamster thực tế (hiện `seed.py` có `1` Thỏ và `1` Hamster nhưng `0` tệp ảnh).
   - Bộ ảnh đa góc chụp (`multi-view`) có xác thực cùng cá thể nếu muốn nghiên cứu Re-ID ở `AI-4.0c`.
