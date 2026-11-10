# Phase 5.3B — Quy trình xin phép đánh giá provider thật

## Trạng thái

**NO-GO hiện tại.** Không có provider thật được gọi, không có ảnh egress, không có quality/cost metric thực. Tài liệu này là protocol chờ Product/Data owner/Security/Cost owner phê duyệt; không tự bật provider.

## Candidate và use case

- Ứng viên để đánh giá trước: **OpenAI GPT-6 Luna (`gpt-6-luna`) qua Chat Completions**, vì model công bố image input/Chat Completions và adapter hiện có dùng OpenAI-compatible Chat Completions. Chưa xác minh live request/parameter/structured output; đây không phải lựa chọn được phê duyệt.
- Use case duy nhất: gợi ý `species`, `breed`, `coat_color`, `eye_color` và mô tả ngoại hình nhìn thấy (`appearance_tags`) cho admin review. Không chẩn đoán, không suy đoán tuổi/danh tính, không tự ghi.
- Mọi model khác cần adapter request/response + security review riêng. Không đổi endpoint/model giữa một dataset run.

## Trước khi bật bất kỳ egress nào

1. Product/Data owner ký xác nhận quyền sử dụng từng ảnh và cách lưu nhãn; loại ảnh khách hàng/nhân viên, metadata, mặt/ngôi nhà/vị trí không cần thiết.
2. Security kiểm DPA, retention/deletion, training, region/subprocessors, account/project settings, TLS, credential secret store, host/IP egress allowlist, abuse logs, incident handling và log policy. Adapter phải yêu cầu chế độ không lưu khi provider hỗ trợ; xác nhận riêng setting đó không ngăn abuse monitoring/retention khác.
3. Cost owner cấu hình hard cap ở provider project: tổng tối đa **USD 1.00**, tối đa **50 provider attempts**, retries=0, quota riêng; cảnh báo không thay hard cap. Nếu provider không enforce mức chi này thì NO-GO.
4. Operator chuẩn bị staging cô lập với `AI_VISION_ENABLED=0` mặc định, DB/storage test, admin test account và app request counter. Không dùng dev/prod DB. Khóa domain/egress network chỉ tới endpoint được duyệt.
5. Reviewer duyệt rubric nhãn independent, dataset split/hash, metric definitions, acceptance thresholds và abort owner.

## Dataset và thiết kế đánh giá

Trước quyết định go/no-go về chất lượng: tối thiểu **400 ảnh được cấp quyền**, trong đó ít nhất 50 ảnh cho mỗi hard scenario: ambiguous, poor lighting, occlusion, multiple pets, non-pet, missing evidence, conflicting attributes; ít nhất 50 clear cases. Có thể tăng sau khi analysis power/balance được review. Hai annotator độc lập label từng field, third-party adjudication cho disagreement; ghi inter-annotator agreement, `unknown`/abstain rule, source license, split, duplicate/near-duplicate check. Holdout labels không được dùng để prompt tuning. Dataset sample count/threshold là proposal cần Product/Data approval, không phải bằng chứng thống kê đã chứng minh.

Vì Phase 5.3B hard cap 50 attempts, đợt đầu chỉ là **pilot vận hành tối đa 50 case**, không thể dùng một mình để kết luận quality acceptance cho 400 ảnh. Full-quality go/no-go cần một đợt đánh giá riêng có budget/authorization mới và giới hạn tương ứng được duyệt trước; không tự tăng cap.

## Proposed thresholds — cần phê duyệt

Đề xuất để Product/Security chốt trước khi xem output: precision ≥0.95 cho `species` và `coat_color` trên ảnh có trường được annotate; precision ≥0.90 cho field khác trước khi dùng; unknown false-suggestion rate ≤0.05; invalid output ≤0.01; zero output diagnosis/identity/unsupported claims; p95 response ≤8 giây; cost nằm trong hard cap. Report 95% confidence intervals and subgroup breakdown; threshold applies to lower confidence bound only if Product approves that statistical policy. Thresholds là target đề xuất, không phải kết quả đo.

Trong pilot 50 case: abort nếu bất kỳ ảnh không được duyệt đi ra, provider host/region lệch, một output tạo health/identity claim, auth/tenant bypass, invalid output liên tiếp ≥2, request count vượt kế hoạch, cumulative usage > USD 0.50 cảnh báo hoặc tới USD 1.00 cap, timeout/5xx rate >10%, unexpected retention/logging, hay không đối soát được số request. Product có thể siết thêm trước run.

## Execution checklist

1. Pin provider/model/API version/region; lưu approval ID, dataset ID/hash, harness commit SHA và endpoint hostname (không lưu secret).
2. Tạo key/project riêng; kiểm cap $1/50 attempts, quota và alert. Secret inject qua runtime; xác nhận log scrub.
3. Chạy offline CLI trên deterministic fixtures trước; lưu baseline results.
4. Với từng approved pilot image, operator đọc lại outbound bytes and size, request counter; giữ prompt/version cố định. `AI_VISION_MAX_RETRIES=0`; không bật AI Assistant hoặc feature khác.
5. Lưu aggregate prediction JSON không chứa ảnh/API key/PII, token/cost/latency, provider error class, attempt count và exact sample IDs. Giới hạn read access và retention.
6. So scorer độc lập, review false positives/abstentions per field/scenario; không đổi prompt trong cùng run.
7. Không quyết định bật production từ pilot 50. Product/Data/Security/Cost owner sign-off riêng trên đủ dataset và thresholds.

## Rollback / disable

Tắt `AI_VISION_ENABLED`; process restart/redeploy, verify no provider requests while local fallback works; revoke project key; remove approved egress route; stop pilot worker; preserve only approved minimal aggregate evidence under agreed retention. No DB migration/schema rollback is needed. Browser UI remains manual review / no auto-save.
