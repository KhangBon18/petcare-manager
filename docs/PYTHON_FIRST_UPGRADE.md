# Python-first upgrade: thuật toán và tích hợp

Mục tiêu của Phase Python-first là làm rõ phần tính toán Python bên trong hệ thống
Flask/Jinja hiện có, không thay stack hay quy tắc bán hàng.

## Khả năng Python hiện hữu

| Nhóm | Trạng thái trước phần nâng cấp | Mã nguồn / chức năng | Quyết định |
|---|---|---|---|
| Nghiệp vụ bán hàng | Đã có | `petcare/services/invoice_service.py`, transaction thanh toán, `refund_service.py`, các repository tương ứng | Giữ nguyên; tiếp tục dùng tiền `Decimal`, khoá hàng và rollback. |
| Tenant/role | Đã có | `petcare/auth.py`, `services/actors.py`, SQL có `tenant_id` và MySQL session context | Không nới quyền; truy vấn mới giữ cùng tenant scope. |
| Trợ lý cửa hàng | Đã có một phần | `assistant_local.py`, `assistant_capabilities.py`, service báo cáo/tồn/Purchase | Giữ các câu hỏi dữ liệu cục bộ; làm rõ Vision mock không phải LLM. |
| So sánh ảnh thú cưng | Đã có thuật toán cục bộ | `petcare/vision/image_features.py`, `services/pet_image_service.py`; Pillow, EXIF orientation, histogram màu, lưới grayscale, SimHash/LSH, điểm màu/cấu trúc, top-K | Tái sử dụng; không viết lại thành classifier và không gọi provider thật. |
| Dự báo tồn | Chưa có forecast nhiều tuần | Restock cũ dựa trên cửa sổ bán 14/30 ngày; dịch vụ đọc hóa đơn, hoàn hàng và tồn | Thêm weighted moving average giải thích được, không phụ thuộc ML. |
| Reconciliation ledger | Cơ hội chưa triển khai | `stock_movements`, invoice/refund/purchase ledgers đã có | Chưa mở rộng trong phase này; không tự sửa lịch sử. |
| Test | Đã có | `unittest`, MySQL 8.4 disposable, Playwright, axe-core, Node test | Thêm kiểm thử công thức, metrics retrieval, SQL và UI responsive. |

## Python capability inventory sau thay đổi

- **Đã có và tái sử dụng:** các transaction invoice/refund/purchase; validation
  trạng thái và tồn; truy vấn theo tenant; chart doanh thu từ dịch vụ báo cáo.
- **Đã có và được làm rõ:** trích descriptor màu/cấu trúc, SimHash 64-bit, 8-band
  LSH và heap top-12. Đây là phép xếp hạng tương đồng ảnh, không suy luận danh tính,
  loài hay giống.
- **Được cải thiện:** `petcare/vision/retrieval_evaluation.py` tính Precision@K,
  Recall@K và MRR từ nhãn bên ngoài; `pet_image_service` trả preview đã chuẩn hóa
  trong response hiện tại để người dùng so sánh với ứng viên xếp đầu. Preview không
  được ghi thành ảnh hồ sơ.
- **Mới:** `petcare/analytics/demand_forecast.py` tạo forecast nhu cầu 14 ngày;
  `demand_evaluation.py` làm rolling time-ordered comparison với baseline.
- **Chưa có:** lead time/supplier model, mùa vụ/khuyến mại/stockout correction,
  confidence intervals, auto-PO, đánh giá LSH recall bằng nhãn người độc lập, hoặc
  phân tích từ ảnh khách hàng thật.

## Luồng tìm ảnh V2

`multipart upload → validation/size bound → Pillow decode + EXIF transpose →
normalized descriptor → tenant-scoped candidate lookup → exact descriptor scoring
→ top 12 → score + component reasons + query preview`.

Service dùng candidate retrieval hiện có; nếu danh mục có LSH index đầy đủ, chỉ
những candidate trong bucket được so sánh chính xác. Do LSH là phép truy xuất gần
đúng, nó có thể bỏ sót candidate. Descriptor dựa trên phân bố màu và cấu trúc vùng
ảnh; phần màu nhấn vùng giữa để giảm nền. UI ghi rõ điểm 0–100 là điểm xếp hạng,
không phải xác suất. Query preview là JPEG data URI ngắn hạn trong HTML response;
không lưu ảnh truy vấn vào MySQL hay storage.

Các giới hạn đầu vào hiện có được giữ: tệp kiểm tra theo MIME/nội dung, chỉ định
dạng ảnh được hỗ trợ, `read_upload` giới hạn byte, Pillow normalizer giới hạn điểm
ảnh; ảnh hỏng được chuyển thành lỗi có thể phục hồi. Ứng viên lấy qua actor đã
xác thực, tenant membership và trạng thái/trạng thái lọc hiện có. Bài đánh giá dùng
68 ảnh demo tổng hợp có sẵn, không dùng ảnh khách.

## Luồng dự báo nhập hàng

Repository đọc hóa đơn đã thanh toán, trừ các refund đã trả sản phẩm vào kho, và
lấy số lượng còn lại của PO có trạng thái `ordered` hoặc `partially_received`.
Phạm vi ngày là ngày địa phương của cửa hàng, được đổi sang các khoảng UTC-naive
nửa mở trước khi bind vào SQL. `cancelled` và `received` không được tính là hàng sắp
về. Không thay schema.

Estimator nhận tối đa 8 `DemandBucket` tuần, mỗi bucket có `net_units` và
`days_observed`. Trọng số tuần tăng tuyến tính theo độ mới từ 1 tới 8:

```text
weighted_daily_rate = Σ(max(net_units_i, 0) × i) / Σ(days_observed_i × i)
expected_14d = ceil(weighted_daily_rate × 14)
target_stock = max(reorder_level + 1, expected_14d)
suggested_qty = max(0, target_stock − on_hand − incoming_open_PO)
days_remaining = on_hand / weighted_daily_rate   (khi rate > 0)
```

Mẫu số chỉ tính ngày lịch sử sản phẩm đã tồn tại. Bucket có hoàn vượt số bán được
clip về nhu cầu 0; không dùng giá trị âm như nhu cầu tương lai. Nếu dữ liệu đủ
ngắn, UI gắn cờ `no_history`, `sparse`, `limited`, `sufficient` hoặc `no_sales`.
Không đủ history thì đề xuất vẫn bị chặn bởi `reorder_level + 1`; đây là mức
fallback nghiệp vụ sẵn có, không phải forecast đáng tin cậy. Hệ thống không đặt PO.

Thuật toán Python chạy O(n) thời gian, O(1) bộ nhớ bổ sung cho n bucket; trong UI
n=8. Truy vấn đọc số liệu theo product trong một aggregate MySQL rồi service tính
ngày sản phẩm/tenant timezone và estimate. Không tạo một query mỗi sản phẩm.

## Cách giải thích trong buổi bảo vệ

- Tham số là chuỗi nhu cầu tuần, tồn, reorder level, PO còn mở và ngày sản phẩm
  bắt đầu có mặt. Output là tốc độ trung bình có trọng số, lượng kỳ vọng 14 ngày,
  ngày tồn ước tính và lượng cần cân nhắc nhập.
- Dataclass `DemandBucket` làm rõ một đơn vị dữ liệu; `DemandEstimate` chứa cả
  rate lẫn tử số/mẫu số có trọng số để UI/test truy nguyên công thức.
- Dữ liệu đầu vào sai giới hạn gây `ForecastInputError`, không bỏ qua âm thầm.
  Không có bán hàng không chia cho 0; rate là `None` và không khẳng định có tốc độ
  tiêu thụ.
- Chọn thuật toán nhẹ vì 8 tuần là dữ liệu ngắn, có thể kiểm tra bằng tay và không
  cần training/chi phí inference. Nó không thay thế replenishment planning đầy đủ.

## Skill được dùng

`frontend-design` định hướng hệ thống component/tokens và phân cấp; `web-design-guidelines`
dùng để xem tên control/focus/error/empty states; `playwright-cli` dùng workflow
browser QA; `ui-ux-pro-max` và design-system subskill được tham chiếu cho responsive
layout. Các skill React/Tailwind/SQLite không được áp dụng vì xung đột với kiến trúc
hiện tại. Không cài thêm runtime dependency cho hai thuật toán.
