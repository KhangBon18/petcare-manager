# Vision Benchmark Specification

## Mục tiêu và use case

Chấm gợi ý ngoại hình cho hồ sơ thú cưng từ một ảnh JPEG đã được xử lý/chuẩn hóa. Hệ thống chỉ gợi ý quan sát để admin xem xét. Đây không phải phân loại sức khỏe, chẩn đoán, nhận diện cá thể hay quyết định nghiệp vụ tự động.

## Trường và nhãn

| Field | Hành vi hiện có | Đơn vị chấm |
|---|---|---|
| `species` | Gợi ý chuỗi ngắn; tối đa 80 ký tự trên pet form | Exact normalized string; có thể abstain |
| `breed` | Gợi ý chuỗi; tối đa 100 ký tự | Exact normalized string; có thể abstain |
| `coat_color` | Gợi ý chuỗi; tối đa 80 ký tự | Exact normalized string; có thể abstain |
| `eye_color` | Gợi ý chuỗi; tối đa 60 ký tự | Exact normalized string; có thể abstain |
| `appearance_tags` | Mô tả ngoại hình; tối đa 255 ký tự | Exact string khi có nhãn rõ; cần taxonomy/annotation rubric trước benchmark thật |
| `coat_pattern`, `coat_length`, `size`, `shape` | Field adapter có thể chấp nhận; service ánh xạ mô tả vào `appearance_tags` | Chỉ chấm nếu có nhãn độc lập và rule mapping được phê duyệt |

Không hỗ trợ tuổi, sức khỏe, chẩn đoán thú y, tính cách, giá, trạng thái bán, danh tính hay hành động. Không tạo nhãn suy diễn cho các trường không thấy trong ảnh.

## Dataset schema v1

Ví dụ thực tế hiện có: `tests/fixtures/vision/evaluation/manifest.json`. Manifest có `dataset_id`, `version`, `schema_version`, `evaluation_category`, `image_root`, annotation policy, `supported_attribute_fields`, `samples`, coverage requirements và `real_model_accuracy`.

Mỗi sample eligible yêu cầu: duy nhất `sample_id`; đường dẫn ảnh tương đối nằm trong dataset root; `approved_usage_status`; `ground_truth_source` (`verified_construction` hoặc `independent_human_annotation`); ghi chú nguồn nhãn; `split`; `scenario`; `supported_fields`; `ground_truth`; `evaluation_eligible=true`. Path traversal, path thoát khỏi root, ảnh không tồn tại, field lạ, sample ID lặp và nguồn nhãn thiếu đều bị từ chối.

- Giá trị chuỗi: nhãn rõ được ghi từ nguồn độc lập và so khớp exact sau NFKC, whitespace collapse và casefold. Không fuzzy-match synonym.
- `null`: field đã được gán nhãn là unknown/không đủ bằng chứng; kỳ vọng model abstain.
- Field bị bỏ khỏi `ground_truth`: không được annotate và bị loại khỏi mẫu số của field đó.
- Split: `development`, `validation`, `held_out` cho dữ liệu thật; hiện tại `mechanics_only` chỉ để thử harness.
- Media chỉ nhận `synthetic_test_only` hoặc `approved_human_labeled`; quyền sử dụng phải được lưu ngoài model output và review trước mọi egress.

## Prediction contract

JSON có `prediction_source` và đúng một record cho mỗi eligible `sample_id`: `values`, `output_valid`, `initial_error`, `recovered`, cùng telemetry tùy chọn `attempt_count`, `latency_ms`, `input_tokens`, `output_tokens`, `estimated_cost_usd`. ID prediction phải khớp chính xác tập sample; giá trị telemetry phải không âm và hữu hạn. Không có field confidence.

`output_valid` là cờ do evaluation runner ghi sau khi áp đúng provider/application schema; scorer chỉ kiểm tra kiểu boolean và tính tỷ lệ, không tự chạy lại parser của provider. Prediction thật cần lưu parser result/version để metric này audit được.

## Metrics

Cho mỗi field có ground truth:

- `tp`, `fp`, `fn`; precision = TP/(TP+FP), recall = TP/(TP+FN), F1 theo precision/recall.
- Exact match = nhãn đúng / nhãn field đã annotate.
- Abstention = prediction vắng/null / nhãn đã annotate; field coverage = prediction khác null / nhãn đã annotate.
- Incorrect suggestion rate = gợi ý sai / số gợi ý không-null; gợi ý khi ground truth `null` được tính FP và được báo thêm riêng.
- Invalid structured output rate = record `output_valid=false` / toàn bộ record.
- Error recovery rate = số record có initial error và recovered / số initial error; không có lỗi thì metric là `null`, không quy thành 0%.
- Latency p50/p95 dùng nearest-rank trên telemetry có thật; token và chi phí cộng từ record cung cấp. Thiếu telemetry được thể hiện là null/không đầy đủ, không nội suy.

Metric chỉ có ý nghĩa trên tập/nhãn được nêu; không tính CI hoặc significance test hiện tại. Với benchmark thật cần báo sample count và breakdown theo scenario, field, split và annotator agreement.

## Phân biệt bằng chứng

1. **Harness correctness:** metric unit tests xác nhận tính toán, validation, determinism và path safety.
2. **Mock integration mechanics:** mock loopback chứng minh đường đi dữ liệu, parser/response/scoring chạy theo fixture.
3. **Model quality:** cần output provider thật trên bộ dữ liệu được duyệt, nhãn độc lập, protocol versioned và telemetry. Hiện trạng: **NOT MEASURED**.

## Coverage hiện có và còn thiếu

Hai synthetic illustrations chỉ có nhãn `species` và `coat_color`. Clear supported examples được xác minh bằng construction. Ambiguous appearance, poor lighting, occlusion, multiple animals, non-pet, missing visual evidence, conflicting attributes đang là coverage slots chờ media được phép và nhãn độc lập. Unsupported GIF/corrupt/empty/oversized là processing-test cases; không tính là model-quality cases.

Benchmark thật cần chủ sở hữu dữ liệu xác nhận quyền và retention; ít nhất hai annotator độc lập cùng rubric bất đồng/unknown; split giữ tách ảnh/individual phù hợp; holdout không dùng prompt tuning; kiểm tra mất cân bằng trường/loài và duplicate/perceptual duplicate. Kích thước cụ thể để phê duyệt ở `PHASE53B_PROVIDER_APPROVAL.md`.
