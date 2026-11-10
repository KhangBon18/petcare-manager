# Phase 5.2 — Rà soát an toàn Vision

## Kiểm soát đã kiểm chứng

- **Authentication/role:** endpoint yêu cầu admin; browser test staff nhận 403 HTML theo handler chung. Unit/web tests kiểm anonymous/CSRF/error behavior.
- **Tenant isolation:** actor và tenant lấy từ session/service context; integration test gửi tenant override giả nhưng route tiếp tục truyền tenant của phiên.
- **Input validation:** giới hạn upload 5 MiB, Pillow content sniff cho JPEG/PNG/WebP, pixel limit 20M, EXIF orientation và re-encode thumbnail tối đa 1600 px. MIME, extension và client filename không điều khiển format hoặc path.
- **Metadata/storage:** bytes suggestion chuẩn hóa trong bộ nhớ và không lưu. Browser mock xác nhận JPEG output không còn EXIF. Không dùng ảnh thật hoặc shared storage.
- **Provider output:** JSON object; field allowlist dạng string được normalize/cap; field lạ, confidence, URL, HTML và action bị loại. Không có auto-save.
- **Rate/concurrency:** route có account/IP throttle và bounded image-processing semaphore; busy trả 429 + Retry-After. Browser test gửi hai request đồng thời, xác nhận một request bị giới hạn.
- **Frontend:** textContent, key allowlist, stale-response protection, cancel/retry và apply ô trống. Không render HTML từ provider.
- **Logs/errors:** route không ghi ảnh, body, provider message hoặc credentials; unexpected exception log chỉ loại exception và trả thông điệp chung.
- **Provider boundary:** AI_VISION_ENABLED=0 mặc định. Browser QA trỏ về loopback mock; mock server chỉ bind 127.0.0.1. Không gửi request trả phí/live.

## Kết quả scanner

- Bandit đúng command source-security trong .github/workflows/ci.yml: exit 0. B608 nosec warnings cho statements trong baseline hiện hành không làm CI gate fail. Không thêm blanket exclusion hoặc suppression cho Phase 5.2.
- pip-audit requirements.lock và requirements-browser.lock: “No known vulnerabilities found”.
- pip check, compileall, git diff --check, Compose config và local Docker build: PASS.
- Trivy CLI không có trong môi trường local; secret-scan job của GitHub Actions và hosted workflow chưa chạy trong lượt này.

## Rủi ro chưa được giải quyết

- Provider thật chưa được chọn/duyệt; chưa đánh giá egress, vùng xử lý, điều khoản lưu/training, retention, chi phí, quota hoặc credential rotation.
- Chưa có dữ liệu động vật được cấp phép để đo sai lệch, precision/recall hoặc ngưỡng abstain.
- Chưa có screen-reader audit hoặc axe scan mới cho form Vision; đã kiểm label, aria-live, keyboard Enter và responsive bằng Chromium nhưng đây không phải xác nhận WCAG.
- Docker image được build, chưa deploy hoặc kiểm tra với production secret/services.

Không có phát hiện P0/P1 mới trong workflow mock đã kiểm. Điều đó không xác nhận tính an toàn/độ chính xác của provider thật.
