# Giới hạn đã biết — Phase 6.2

## Production readiness

**NO-GO.** Demo là conditional GO trên isolated local QA. Không có kiểm thử production data, backup/restore được chấp nhận cho schema dev, migration rollout trên dev, hoặc load/concurrency benchmark. Không chạy hosted CI mới trong Phase 6.2; hosted 6/6 từ Phase 6.0 chỉ là baseline cũ.

## Accessibility

- 200% native browser zoom chưa test được trong browser profile an toàn.
- VoiceOver/screen reader chưa test; axe 22 scans có 0 violations nhưng 73 incomplete nodes cần manual review.
- WebKit axe không chạy do axe inline-style instrumentation ảnh hưởng strict CSP audit; cross-engine WCAG completeness chưa chứng minh.

## External integrations / AI

- Real SMTP, S3, payment gateway, real AI/AI Vision và provider accuracy/cost/latency: NOT TESTED.
- Vision mock trả observation cố định; không đánh giá nội dung ảnh, không phải benchmark.
- Assistant insight top-products/operations có dữ liệu thật ở tenant QA; các intent local dùng rule. Provider LLM tùy cấu hình nhưng tắt khỏi launcher.
- Export demo dùng local QA worker/storage, không phải S3 deployment test.

## Environment

- Clean runtime đã cài bằng pinned runtime/browser requirements trên Python 3.13; cross-platform install matrix 3.11/3.12 hosted chưa chạy trong phase.
- Browser cross-test là headless representative run, không bao phủ mọi OS/version/input device.
- Internet không cần trong app runtime sau khi Docker images/dependencies đã cache; first-time package/image acquisition cần mạng.

## Repository/release

- Working tree giữ các thay đổi Phase 6.1 có từ trước; chưa stage/commit/push. Không reset hoặc clean.
- Generated Phase 6.2 screenshots là artifacts được chủ ý thêm trong `docs/assets/phase62/`; raw report/log chứa synthetic ID chỉ ở temp directory.
- Cần review diff và secrets/artifact scan trước khi stage; không tuyên bố automated check là hosted release approval.
