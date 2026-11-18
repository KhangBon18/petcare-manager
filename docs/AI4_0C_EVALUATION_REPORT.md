# Báo cáo Đánh giá Định lượng Vector Nhúng Tiền cảnh & Tái xếp hạng CIE-Lab — `AI-4.0c`

- **Bộ kiểm chuẩn**: `petcare-ai4-0c-retrieval-benchmark` `v3.0.0` (`manifest_v3.json`)
- **Mô hình nhúng thị giác cục bộ**: `mobilenetv2-12-features.onnx` (`1280` chiều từ tầng áp chót `GlobalAveragePool_97 -> Reshape_103 -> tensor '472'`, chuẩn hóa đơn vị `L2`, mã hóa `float16` base64 `mnv2_op12_fg1280_f16_v1`).
- **Mô tả màu lông tiền cảnh**: `cielab_wb_sog_fg16_v1` (`16` bin cảm nhận `CIE-Lab` + cân bằng trắng `Achromatic-Quantile Shades-of-Gray` + khử nhiễu nền ngoài `bbox`).
- **Dung lượng mô hình đang nạp RAM**: **`16.87 MB`** (`YOLOX-Nano` `3.55 MB` + `MobileNetV2-12-features` `13.32 MB`; tổng thư mục `models/` trên đĩa gồm cả bản gốc bảo toàn: `30.19 MB`).
- **Kích thước JSON descriptor trung bình**: `6106.2 bytes` (`~5.96 KB`/thú cưng) · **Peak RSS**: `262.84 MB`.

## 1. Bảng Đối sánh 4 Phương án (`Ablation Study`) trên Tập Nghiệm thu Độc lập (`Acceptance Holdout`)

| Chỉ số đo lường | `A. AI-4.0b` (Holdout) | `B. Embedding-Only` (`1280-D`) | `C. CIE-Lab Coat-Only` | **`D. AI-4.0c Combined` (Holdout)** | `D. AI-4.0c` (`Calibration`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Same-Species Coat `Precision@5` (`sP@5`)** | `94.7%` | `77.4%` | `90.0%` | **`91.5%`** *(vs `84.3%` cal baseline)* | `86.2%` |
| **1b. Fine-Grained Coat+Morphology `sP@5`** | `64.9%` | `65.8%` | `58.9%` | **`65.2%`** | `62.6%` |
| **2. Top-1 Coat Accuracy** | `94.7%` | `89.5%` | `92.3%` | **`89.5%`** | `89.7%` |
| **2b. Top-1 Fine-Grained (Coat + Coat-Length/Breed)** | `68.4%` | `81.6%` | `66.7%` | **`76.3%`** | `76.9%` |
| **3. Orange-Cat Coat `sP@5` / Fine `sP@5`** | `100.0% / 80.0%` | `87.5% / 72.5%` | `100.0% / 68.3%` | **`100.0% / 75.8%`** | `85.7% / 62.9%` |
| **4. Lỗi Top-1 khác nhóm màu lông (`Wrong-Coat Top-1`)** | `2` | `4` | `3` | **`4`** | `4` |
| **4b. Cặp đối kháng tinh (`Hard-Negative Pairs`)** | `20.0%` (`1/5`) | `80.0%` (`4/5`) | `40.0%` (`2/5`) | **`80.0%` (`4/5`)** | `60.0%` (`3/5`) |
| **5. Lỗi chéo loài Mèo <-> Chó (`CSER`)** | `0.0%` (`0/42`) | `0.0%` | `0.0%` | **`0.0%` (`0/42`)** | `0.0%` |
| **6. FPR trên đồ vật giống lông thú / phi động vật** | `0.0%` | `0.0%` | `0.0%` | **`0.0%`** | `0.0%` |
| **6b. Nhận vơ danh tính (`False Identity Claims`)** | `0` | `0` | `0` | **`0`** | `0` |
| **7. Độ chính xác từ chối không khớp (`No-Match Rejection`)** | `100.0%` (`22/22`) | `90.9%` | `100.0%` | **`100.0%` (`22/22`)** | `100.0%` (`22/22`) |
| **8. Exact-Image Rank-1 (`EIRA@1`)** | `100.0%` (`34/34`) | `100.0%` | `100.0%` | **`100.0%` (`34/34`)** | `100.0%` |
| **9. Near-Duplicate Recall (`480px q=70`) / FP** | `100.0% / FP=0` | `100.0% / FP=0` | `100.0% / FP=0` | **`100.0% / FP=0`** | `100.0% / FP=0` |
| **10. Độ trễ đầu-cuối `p50 / p95` (ms)** | `71.69 / 81.415 ms` | `75.307 / 165.97 ms` | `77.029 / 105.911 ms` | **`71.956 / 77.325 ms`** | `70.1 / 76.882 ms` |
| **12. Độ phủ gợi ý khi đã xác nhận loài (`Coverage`)** | `97.4%` (`38/39`) | `97.4%` | `100.0%` | **`97.4%` (`38/39`)** | `97.5%` (`39/40`) |

## 2. Đánh giá Cân bằng Trắng & Khử Nhiễu Nền `CIE-Lab` (`Acceptance Holdout`)

| Kịch bản Ánh sáng / Phông nền Đối kháng | Không cân bằng trắng (`none`) | `Gray-World` Cổ điển | **`Achromatic Shades-of-Gray` (`AI-4.0c`)** |
| :--- | :---: | :---: | :---: |
| **Mèo cam trên nền cỏ xanh (`green_grass_backdrop`)** | `5/6` | `4/6` | **`5/6`** |
| **Mèo cam dưới đèn vàng ấm `2850K` (`tungsten_2850k`)** | `6/6` | `4/6` | **`5/6`** |
| **Mèo đen/tối trên nền tối sẫm (`dark_charcoal_backdrop`)** | `1/1` | `1/1` | **`1/1`** |
| **Chó trắng dưới ánh sáng ấm/gắt (`white_dog_tungsten`)** | `0/1` | `1/1` | **`1/1`** |
| **Chó lông vàng trên nền màu tương tự (`coat_similar_tan`)** | `7/8` | `2/8` | **`7/8`** |

## 3. Kiểm toán Mô hình ONNX, Lưu trữ Descriptor & Tương thích Ngược

- **Xác minh đồ thị ONNX thực tế (`mobilenetv2-12.onnx` -> `mobilenetv2-12-features.onnx`)**: Đã kiểm tra trực tiếp `ModelProto` (`ir_version=7`, `105` nút): nút `GlobalAveragePool_97` xuất `[batch_size, 1280, 1, 1]` vào `Reshape_103 -> tensor '472'` (`[batch_size, 1280]`) ngay trước `Gemm_104` (`classifier.1.weight [1000, 1280]`). Biến thể `mobilenetv2-12-features.onnx` gắn nút `Identity_embedding_1280 ('472' -> 'embedding_1280')`, bảo toàn tuyệt đối tệp gốc `mobilenetv2-12.onnx` (`SHA-256 = c0c3f76d...`), sai lệch logit so với bản gốc bằng **`0.0`** và sai số tái tạo tuyến tính `< 1e-4`.
- **Chiến lược lưu trữ & backfill an toàn**: Lưu kèm `embedding_version = 'mnv2_op12_fg1280_f16_v1'` (`3.416` ký tự base64 `float16` = `2.560` byte nhị phân) và `fg_lab_version = 'cielab_wb_sog_fg16_v1'` (`16` bin `CIE-Lab` + `7` nhóm màu) ngay trong cột JSON `pets.photo_descriptor`, không cần reset schema, giữ nguyên `raw_sha256`/`normalized_sha256` gốc và bỏ qua dòng đã cập nhật khi chạy lại `python -m petcare.vision.reindex_pet_descriptors --apply`.
- **Cờ quay lui an toàn (`Rollback Flag`)**: `AI_FOREGROUND_EMBEDDING_ENABLED=0` cho phép chuyển tức thời về nhánh xếp hạng `AI-4.0b` mà không cần sửa dữ liệu.

## 4. Giới hạn Dữ liệu Còn lại & Lộ trình `AI-4.0d`

- **`same_pet_multi_view_reidentification` — `NOT_EVALUATED`**: Kho dữ liệu hiện có tối đa `1` ảnh tham chiếu cho mỗi cá thể `PET-*`; điểm tương đồng cosine vector `1280` chiều chỉ phản ánh tương đồng hình thái/kết cấu lông cùng loài (`visually_similar_candidate`, điểm trần `<= 89`), **tuyệt đối không chứng minh hai bức ảnh là cùng một cá thể thú cưng**.
- **Thiên lệch phông nền Studio & Số lượng ảnh thực**: `64/68` ảnh danh mục vẫn là ảnh chân dung cận mặt nền trơn; bộ `real_pack` hiện có `34` ảnh thực tế Wikimedia Commons. Giai đoạn `AI-4.0d` nên mở rộng bảng `pet_photos` (`1:N` nhiều góc chụp cho mỗi hồ sơ thú cưng) và bổ sung bộ ảnh chụp điện thoại đa góc thực tế có xác thực cá thể.
