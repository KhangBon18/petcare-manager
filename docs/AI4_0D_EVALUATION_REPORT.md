# Báo cáo Đánh giá Kho Ảnh Đa góc Chụp, Khớp Bền Cắt Cúp & Trung thực Định danh — `AI-4.0d`

- **Bộ kiểm chuẩn**: `petcare-ai4-0d-gallery-and-crop-benchmark` `v4.0.0` (trên tập phân chia đóng băng `calibration` / `acceptance_holdout` của `manifest_v3.json`, **0 rò rỉ cá thể**).
- **Kiến trúc lưu trữ kho ảnh**: `pets.photo_filename` (Ảnh `#1` đại diện chính) + bảng `pet_reference_photos` (tối đa `4` ảnh tham chiếu phụ `#2..#5`, tổng tối đa **`5` ảnh đã xác minh / cá thể**, **`0` byte ảnh trùng lặp**).
- **Mô hình ONNX cục bộ tái sử dụng**: `YOLOX-Nano` + `MobileNetV2-12-features` (`16.87 MB` nạp RAM, `0` mô hình tải mới, `0` lệnh gọi API bên ngoài).
- **Trạng thái định danh đa góc chụp thực tế**: **`same_pet_multi_view_reidentification = NOT_EVALUATED`** *(xem chi tiết tại `docs/AI4_0D_DATASET_REQUIREMENTS.md`)*.

## 1. Phân tích Trung thực Đánh đổi `AI-4.0b` vs `AI-4.0c` vs `Embedding-Only` (`Phase 0 Review`)

| Điểm vận hành (`Acceptance Holdout` đóng băng) | `Top-1 Fine-Grained` | `Same-Species Coat P@5` | `No-Match Rejection` | Nhận xét kỹ thuật trung thực |
| :--- | :---: | :---: | :---: | :--- |
| **`AI-4.0b` (Histogram + RGB Coat Gate)** | `68.4%` | **`94.7%`** | **`100.0%`** | Lọc thô nhóm màu RGB chặt nên `Coat P@5` cao nhất (`94.7%`), nhưng thiếu đặc trưng hình thái/độ dài lông (`Top-1 Fine` chỉ `68.4%`). |
| **`AI-4.0c Combined` (`0.58 Emb + 0.34 Lab + 0.08 Struct`)** | `76.3%` | `91.5%` | **`100.0%`** | Điểm cân bằng Pareto: tăng `+7.9` điểm % `Top-1 Fine` so với `AI-4.0b` và giữ `100.0%` `No-Match`, nhưng đánh đổi `-3.2` điểm % `Coat P@5` trên các ca biên kem/vàng nhạt. |
| **`Embedding-Only` (`1280-D` Cosine)** | **`81.6%`** | `77.4%` | `90.9%` | Mạnh nhất về hình thái (`81.6%`), nhưng rơi xuống `90.9%` `No-Match` (không tự từ chối khi kho thiếu thú cưng cùng màu lông). |

> **Nguyên tắc không gian lận kiểm chuẩn**: Không có thuật toán 1 ảnh nào thống trị tuyệt đối mọi trục đo. Bộ tham số `AI-4.0c` không được chỉnh lại theo `acceptance_holdout`; thay vào đó, `AI-4.0d` giải quyết bài toán biến thiên góc khung hình và ánh sáng ở tầng kiến trúc bằng **kho ảnh tham chiếu đa góc đã xác minh (`1..5` ảnh/cá thể)** và **hợp nhất cấp hồ sơ cá thể (`calibrated_gallery_hybrid`)**.

## 2. Đối sánh 4 Phương pháp Hợp nhất Kho Ảnh (`Acceptance Holdout`, `3` ảnh/hồ sơ)

| Chỉ số đo lường (kèm kích thước mẫu thật) | `A. Primary-Only` (`AI-4.0c`) | `B. Max-Photo` | `C. Mean-Gallery` | **`D. Calibrated Hybrid` (`AI-4.0d`)** | `D. AI-4.0d` (`Calibration`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Exact Primary Photo Rank-1 (`34/34` hold / `34/34` cal)** | `100.0%` (`34/34`) | `100.0%` | `100.0%` | **`100.0%` (`34/34`)** | `100.0%` (`34/34`) |
| **2. Exact Secondary Photo `#2/#3` Rank-1 (`n=56` hold / `56` cal)** | `0.0%` (`0/56`) | `100.0%` | `100.0%` | **`100.0%` (`56/56`)** | `100.0%` (`56/56`) |
| **3a. Near-Duplicate `Resize 480 q=70` Recall (`n=28` enrolled/split)** | `100.0%` (`28/28`) | `100.0%` | `100.0%` | **`100.0%` (`28/28`)** | `100.0%` (`28/28`) |
| **3b. Crop-Robust Near-Duplicate `Crop 4% + Bright +6%` (`n=28`)** | `0.0%` (`0/28`) | `96.4%` | `96.4%` | **`96.4%` (`27/28`)** | `92.9%` (`26/28`) |
| **3c. Tổng Near-Duplicate Precision / Recall (`n=56` biến thể/split)** | `100.0% / 50.0% (FP=0)` | `100.0% / 98.2%` | `100.0% / 98.2%` | **`100.0% / 98.2% (FP=0)`** | `100.0% / 96.4% (FP=0)` |
| **4. Same-Species Coat `Precision@5`** | `91.5%` | `92.8%` | `92.5%` | **`92.8%`** | `86.8%` |
| **4b. Top-1 Fine-Grained (Coat + Coat-Length/Breed)** | `76.3%` | `76.3%` | `79.0%` | **`76.3%`** | `74.4%` |
| **5. Orange-Cat Coat `sP@5` / Fine `sP@5`** | `100.0% / 75.8%` | `100.0% / 78.3%` | `100.0% / 78.3%` | **`100.0% / 78.3%`** | `85.7% / 65.7%` |
| **6. Hard-Negative Pairwise Ranking (`n=5` hold / `5` cal)** | `80.0%` (`4/5`) | `100.0%` (`5/5`) | `80.0%` (`4/5`) | **`100.0%` (`5/5`)** | `60.0%` (`3/5`) |
| **7. Lỗi chéo loài Mèo <-> Chó (`CSER`)** | `0.0%` (`0/42`) | `0.0%` | `0.0%` | **`0.0%` (`0/42`)** | `0.0%` |
| **8. No-Match Rejection (`n=22` hold / `22` cal)** | `100.0%` (`22/22`) | `100.0%` | `100.0%` | **`100.0%` (`22/22`)** | `100.0%` (`22/22`) |
| **9. Tỷ lệ trùng lặp thẻ cùng 1 thú cưng (`Duplicate Pet Rate`)** | `0.0%` (`0/215`) | `0.0%` | `0.0%` | **`0.0%` (`0/215`)** | `0.0%` (`0/215`) |
| **10. Nhận vơ danh tính (`False Identity Claims`)** | `0` | `0` | `0` | **`0`** | `0` |

## 3. Hiệu ứng Kích thước Kho Ảnh (`1` vs `3` vs `5` ảnh/cá thể & Kho Bất đối xứng)

| Cấu hình Kho ảnh (`Acceptance Holdout`) | `Coat P@5` | `Top-1 Fine` | `No-Match Rejection` | `Duplicate Pet Rate` | Độ trễ toàn trình `p50 / p95` | Riêng tầng xếp hạng kho ảnh `p50 / p95` | Dung lượng JSON Descriptor / cá thể |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`1` ảnh / cá thể (Tương thích ngược)** | `91.5%` | `76.3%` | `100.0%` | `0.0%` | `65.748 / 80.373 ms` | `7.513 / 13.346 ms` | `5.96 KB` |
| **`3` ảnh / cá thể** | `92.8%` | `76.3%` | `100.0%` | `0.0%` | `80.829 / 91.258 ms` | `20.149 / 20.619 ms` | `17.89 KB` |
| **`5` ảnh / cá thể (Giới hạn tối đa)** | `93.8%` | `76.3%` | `100.0%` | `0.0%` | `96.013 / 127.409 ms` | `33.982 / 34.377 ms` | `29.82 KB` |
| **Bất đối xứng (`50%` 5 ảnh vs `50%` 1 ảnh)** | `92.3%` | `76.3%` | `100.0%` | `0.0%` | — | — | Hỗn hợp (`5.96 – 29.82 KB`) |

## 4. Tách biệt Rõ ràng giữa `Near-Duplicate Photo` và `Potential Same-Pet Verification`

- **Cổng `near_duplicate_image` bền cắt cúp nhẹ (`Phase 6`)**: Chỉ kích hoạt khi đồng thời thỏa `dHash + pHash <= 24`, `embedding_cosine >= 0.955`, `lab_coat_similarity >= 0.86` và `visual_similarity >= 0.90` (hiệu chỉnh thuần trên `calibration`, nơi cặp cá thể khác nhau gần nhất đạt tối đa `emb_sim = 0.9335`, cách ngưỡng `0.955` một biên an toàn `+0.0215`). Nhờ đó Recall trên ảnh cắt cúp `4% + sáng +6% + JPEG q=82` tăng từ **`0.0%` (`0/28`) lên `96.4%` (`27/28`)** trên `Acceptance Holdout` với **`FP = 0`** (`Precision = 100.0%`).
- **Nhãn bắt buộc cho ứng viên ngoại hình rất giống nhưng không phải ảnh trùng kho**: Mọi ứng viên đạt tương đồng cao (`emb >= 0.80`, `lab >= 0.78`, `combined >= 0.78`) nhưng không qua cổng mã băm/cắt cúp đều giữ ở tầng `visually_similar_candidate` (`score <= 89`) và gắn nhãn cảnh báo rõ ràng: **`"Potential matching pet — staff verification required"`** (`"Có thể cùng thú cưng — cần nhân viên kiểm tra xác minh"`). Hệ thống **không bao giờ tự động xác nhận danh tính cá thể**.

## 5. Giới hạn Dữ liệu Hiện tại & Bước Kế tiếp `AI-4.0e`

- **`same_pet_multi_view_reidentification = NOT_EVALUATED`**: Các biến thể góc cắt/ánh sáng trong mục 2–3 chỉ kiểm chứng tính đúng đắn của cơ chế kho ảnh (`Exact Secondary Photo Rank-1 = 100%`, `Duplicate Pet Card Rate = 0%`, không thưởng điểm ảo cho cá thể nhiều ảnh, độ trễ `< 35 ms`), **tuyệt đối không được diễn giải là độ chính xác nhận diện cá thể qua nhiều góc chụp thực tế**.
- **Bước tiếp theo cho `AI-4.0e`**: Thực hiện thu thập bộ dữ liệu thực địa `>= 24` cá thể thật (`12` mèo + `12` chó) x `>= 3` lần chụp độc lập theo đúng quy trình và lược đồ `manifest_v4_identities.json` trong `docs/AI4_0D_DATASET_REQUIREMENTS.md`, sau đó chạy đánh giá mở khóa chỉ số `same_pet_multi_view_reidentification`.
