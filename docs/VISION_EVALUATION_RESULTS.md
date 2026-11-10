# Vision Evaluation Results

Ngày chạy: 2026-11-10. Công cụ cục bộ `scripts/vision_evaluation/evaluate.py`; không thực hiện egress hoặc gọi provider.

## Kết quả mock mechanics

Dataset: `petcare-vision-synthetic-mechanics` v1.0.0, category `mock_integration_mechanics_only`; 2 eligible synthetic illustrations, 4 annotated values. Nhãn construction độc lập với prediction fixture. Prediction source là `deterministic_loopback_mock_fixture`.

| Field | n | TP/FP/FN | Precision | Recall | F1 | Exact match | Abstention | Coverage | Incorrect suggestion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| species | 2 | 2/0/0 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| coat_color | 2 | 2/0/0 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 |

Output-valid records 2/2; invalid-output rate 0.000. No errors/recoveries. Latency, token usage, and estimated cost are null because no such telemetry was supplied. Machine-readable output: [`mock-results.json`](assets/vision-evaluation/mock-results.json).

## Diễn giải đúng phạm vi

Các metric 1.0 mô tả đúng hai dòng prediction fixture so với hai nhãn synthetic đã dựng; chúng chỉ là smoke test cho scoring mechanics. Fixture không được sinh bởi một model, không đại diện ảnh đời thực và không có mẫu ambiguous/abstain. Vì vậy chúng **không phải độ chính xác nhận dạng AI**.

**REAL MODEL ACCURACY = NOT MEASURED.** Không có call provider; không có precision/recall, latency, token hay cost thật.

## Reproducibility

Chạy lại CLI như trong `PHASE53A_IMPLEMENTATION.md`; JSON output sắp xếp field/record và deterministic với input không đổi. Unit suite `tests.unit.test_vision_evaluation` gồm 9 test scoring/validation. Toàn Python regression: 405/405 PASS, 0 skipped. Kết quả này là local evidence, không thay cho hosted CI.

## Phase 5.3B — live pilot readiness

Ngày: 2026-11-10. Desk review model và dữ liệu hoàn tất; **provider calls = 0**, ảnh egress = 0. Manifest vẫn có đúng 2 synthetic mechanics-only samples, 4 nhãn construction, chỉ `species` và `coat_color`. Không có consent/license egress evidence, không có label độc lập hai annotator, held-out real data hoặc sample `null`/abstention. Các hard scenarios chưa có media/labels; fixture corrupt/unsupported chỉ kiểm xử lý.

Vì không có dataset đủ điều kiện và chưa có approval cụ thể, các metric Phase 5.3B sau đều **NOT MEASURED**: model exact-match/precision/recall/F1, abstention, invalid-output, unsupported suggestions, provider errors, latency p50/p95, image token use và cost/request. Mock score phía trên không được cập nhật thành model result. Chi tiết readiness/approval ở [pilot gate](PHASE53B_PROVIDER_PILOT.md) và [model comparison](PHASE53B_MODEL_EVALUATION.md).

Offline CLI được chạy lại trong preflight Phase 5.3B trên cùng mock manifest/predictions và PASS; metrics telemetry vẫn null, đúng như fixture đầu vào. Kết quả này chỉ xác nhận evaluator mechanics/reproducibility.
