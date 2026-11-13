# Đánh giá hai thuật toán Python

Kết quả dưới đây được tạo bằng script repo, dữ liệu synthetic và phép đo cục bộ
ngày 2026-11-13. Đây không phải độ chính xác trên cửa hàng thật.

## 1. Tìm ảnh tương đồng

Lệnh: `.venv/bin/python scripts/evaluate_demo_pet_image_retrieval.py`

| Chỉ số | Kết quả |
|---|---:|
| Ảnh nguồn tổng hợp | 68 (32 mèo, 32 chó; bộ demo còn có ảnh synthetic khác) |
| Query | 204 (JPEG resize, tăng sáng nhẹ, crop giữa trên mỗi ảnh nguồn) |
| Precision@1 | 0.995098 |
| Precision@5 | 0.200000 |
| Recall@5 | 1.000000 |
| MRR | 0.997549 |
| Xếp hạng descriptor trên 68 ứng viên, p50 / p95 | 1.159 / 1.297 ms |
| Chuẩn hóa query p50 | 10.466 ms |
| Lỗi trong tập đánh giá | 0 |

Mỗi query được gán đúng một nhãn liên quan: ảnh nguồn gốc của chính biến thể đó.
Vì chỉ có một kết quả đúng trong top 5, Precision@5 bằng 1/5 ngay cả khi Recall@5
bằng 1; không diễn giải nó như tỷ lệ nhận diện. Bộ test đo xếp hạng exhaustive của
descriptor trên ảnh synthetic gần trùng. Nó **không** đo recall của LSH, truy vấn
MySQL/HTTP, ảnh khách hàng, danh tính vật nuôi, giống hay loài. Thời gian xếp hạng
không gồm database, disk, HTTP hoặc tải đồng thời. Do đó không tuyên bố độ chính
xác nhận dạng.

Chi tiết có thể tái lập: [`image-retrieval-evaluation.json`](assets/python-first-v2/image-retrieval-evaluation.json)
và mã [`evaluate_demo_pet_image_retrieval.py`](../scripts/evaluate_demo_pet_image_retrieval.py).

## 2. Dự báo nhu cầu tồn kho

Lệnh: `.venv/bin/python scripts/evaluate_synthetic_demand_forecast.py`

| Phương pháp | MAE đơn vị trên cửa sổ 14 ngày |
|---|---:|
| Weighted moving average, 8 tuần gần nhất | 38.647287 |
| Baseline simple moving average, 8 tuần | 47.441860 |

Holdout theo thứ tự thời gian có 12 product series × 52 tuần, bốn pattern (ổn định,
tăng, giảm, gián đoạn), và 516 forecast origin. Tại mỗi origin, chỉ dùng 8 tuần
trước đó; hai tuần tiếp theo là holdout. Trọng số tuần là 1…8. Kết quả theo nhóm:

| Pattern | Số origin | WMA MAE | SMA MAE |
|---|---:|---:|---:|
| Declining | 129 | 107.666667 | 140.000000 |
| Growing | 129 | 14.961240 | 19.976744 |
| Intermittent | 129 | 31.961240 | 29.790698 |
| Stable | 129 | 0.000000 | 0.000000 |

Trên các pattern tổng hợp đã chọn, WMA có tổng MAE thấp hơn SMA; riêng pattern
intermittent, baseline tốt hơn. Đây chỉ là so sánh cơ chế trên chuỗi được tạo bởi
công thức xác định, không phải backtest dữ liệu bán thật. Chưa có đánh giá theo
tenant, khuyến mại, mùa vụ, stockout, lead time, supplier hay nhu cầu bị kiểm duyệt
do hết hàng. Không có khoảng tin cậy và không khẳng định forecast chất lượng thật.

Chi tiết: [`demand-forecast-evaluation.json`](assets/python-first-v2/demand-forecast-evaluation.json)
và [`evaluate_synthetic_demand_forecast.py`](../scripts/evaluate_synthetic_demand_forecast.py).

## 3. Kiểm thử và an toàn

- Unit kiểm tra công thức, trọng số tuần mới, ngày tồn tại thực tế của sản phẩm,
  không bán hàng, hoàn vượt bán, giá trị sai, giới hạn tài nguyên và đề xuất có PO
  còn mở.
- Browser workflow dùng ảnh demo synthetic mèo/chó; xem query cạnh candidate và
  điểm thành phần. Vision mock bị tắt trong browser này; không gửi ảnh tới API ngoài.
- Truy vấn lịch sử dùng bind parameters và tenant session context; test MySQL chạy
  trên schema mới trong container QA, volume DB ở tmpfs.
- Các thao tác tính recommendation chỉ đọc. Không tự thay tồn hoặc tạo purchase
  order. Không có schema migration mới.

Các rủi ro còn lại là độ đại diện của lịch sử thật và tính gần đúng của LSH. Trước
khi dùng dự báo ra quyết định vận hành, cần so với dữ liệu sales đã gắn nhãn theo
tenant, tính cả ngày hết hàng, và xác minh lead time bằng dữ liệu supplier thực.
