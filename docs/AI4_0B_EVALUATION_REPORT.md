# Báo cáo Đánh giá Định lượng Tự động Phát hiện Thú cưng & Nhận diện Loài — `AI-4.0b`

- **Bộ kiểm chuẩn**: `petcare-ai4-0b-vision-benchmark` `v2.0.0` (`manifest_v2.json`)
- **Mô hình cục bộ**: `YOLOX-Nano` (`3.55 MB`, Apache-2.0) + `MobileNetV2-12` (`13.32 MB`, Apache-2.0) = **`16.87 MB`** trên `onnxruntime` (`CPUExecutionProvider`, `0` gọi mạng, `0` cần PyTorch).
- **Đỉnh bộ nhớ tiến trình (`Peak RSS`)**: `261.05 MB`.

## 1. Ma trận Nhầm lẫn Mèo / Chó trên Tập Nghiệm thu Độc lập (`Acceptance Holdout` — Ảnh Mới Ngoài Kho)

### 1.1. Toàn bộ ảnh mới ngoài kho trên `Acceptance Holdout` (`8` ảnh nhiếp ảnh thực + `6` chân dung ngoài kho = `14` cá thể)

| Nhãn Thực tế \ Dự đoán Tự động | Dự đoán `Mèo` (`one_cat`) | Dự đoán `Chó` (`one_dog`) | Từ chối an toàn (`Abstained`) |
| :--- | :---: | :---: | :---: |
| **Thực tế là `Mèo` (`7`)** | **`7`** | **`0`** | `0` |
| **Thực tế là `Chó` (`7`)** | **`0`** | **`5`** | `2` |

### 1.2. Riêng nhóm Ảnh Nhiếp ảnh Thực tế Độc lập (`Real Photographs Only` trên `Acceptance Holdout` — `8` ảnh)

| Nhãn Thực tế \ Dự đoán Tự động | Dự đoán `Mèo` (`one_cat`) | Dự đoán `Chó` (`one_dog`) | Từ chối an toàn (`Abstained`) |
| :--- | :---: | :---: | :---: |
| **Ảnh thật `Mèo` (`4`)** | **`4`** | **`0`** | `0` |
| **Ảnh thật `Chó` (`4`)** | **`0`** | **`2`** | `2` |

## 2. So sánh Trực tiếp `AI-4.0a` vs `AI-4.0b` (Độ chính xác, Độ phủ & Từ chối An toàn)

| Chỉ số đo lường | `AI-4.0a` (Không lọc tay) | `AI-4.0b` (`Calibration`) | **`AI-4.0b` (`Acceptance Holdout`)** | `AI-4.0b` (Toàn bộ) |
| :--- | :---: | :---: | :---: | :---: |
| **Độ phủ tự động trên ảnh thú cưng mới (`Coverage`)** | `0.0%` (luôn đòi chọn tay) | `85.7%` | **`85.7%`** | `85.7%` |
| **Độ phủ tự động riêng trên Ảnh Thật (`Real Photos`)** | `0.0%` | `75.0%` | **`75.0%`** | `75.0%` |
| **Tỷ lệ từ chối phân loại loài (`Species Abstention`)** | `100.0%` | `14.3%` | **`14.3%`** | `14.3%` |
| **Precision loài `Mèo` / `Chó` (khi đã xác nhận)** | — | `100.0% / 100.0%` | **`100.0% / 100.0%`** | `100.0% / 100.0%` |
| **Recall đầu-cuối loài `Mèo` / `Chó`** | `0.0% / 0.0%` | `85.7% / 85.7%` | **`100.0% / 71.4%`** | `92.9% / 78.6%` |
| **Lỗi truy xuất chéo loài Mèo <-> Chó (`CSER`)** | `0.0%` (do từ chối 100%) | `0.0%` (`0/14`) | **`0.0%` (`0/14`)** | `0.0%` (`0/28`) |
| **Lỗi chéo loài Mèo Cam vs Chó Lông Vàng** | — | `0/6` | **`0/8`** | `0/14` |
| **Precision màu lông Mèo Cam tự động (`sP@5`)** | — | `100.0%` | **`100.0%`** | `100.0%` |
| **Exact-Image Rank-1 (`EIRA@1`)** | `100.0%` | `100.0%` (`34/34`) | **`100.0%` (`34/34`)** | `100.0%` (`68/68`) |
| **FPR trên Ảnh Thật Phi Động vật & Thú Bông** | *(không chặn nếu ép loài)* | `0.0%` | **`0.0%`** | `0.0%` |
| **FPR trên Ảnh Chụp Giao diện / Đồ họa** | `0.0%` | `0.0%` | **`0.0%`** | `0.0%` |
| **Độ chính xác từ chối Ảnh Đa Động vật (`2+` con)** | `0.0%` (nếu ép loài) | `100.0%` (`3/3`) | **`100.0%` (`3/3`)** | `100.0%` (`6/6`) |
| **Độ chính xác từ chối Không khớp Tổng hợp** | — | `100.0%` (`22/22`) | **`100.0%` (`22/22`)** | `100.0%` (`44/44`) |
| **Độ trễ tìm kiếm toàn trình `p50 / p95` (ms)** | `21.4 / 27.3 ms` | `61.01 / 67.895 ms` | **`61.402 / 68.661 ms`** | `61.435 / 71.508 ms` |
