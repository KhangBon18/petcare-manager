# Checklist nộp đồ án — Petcare Manager

Ngày rà soát: 2026-11-11
Source baseline được rà soát: `solo/khang-petcare` / `691c5275556a038abe315f977ecb803a39e6b4c3`

## Trạng thái tổng quan

- [x] Tại thời điểm bắt đầu phát hành tài liệu Phase 6.4, nhánh là `solo/khang-petcare`; source baseline `691c5275556a038abe315f977ecb803a39e6b4c3` đồng bộ với `origin/solo/khang-petcare` (`0/0`). Commit cuối sau khi publish các tài liệu sẽ khác SHA này.
- [x] Không có thay đổi source đang chờ. Các mục local tooling có sẵn (`.agents/`, `docs/skills.md`, `skills-lock.json`) được giữ nguyên; không đưa vào gói nộp nếu giảng viên không yêu cầu.
- [x] `scripts/demo/classroom.sh --target qa` khởi động được trên MySQL QA tmpfs; `/healthz`, `/readyz`, `/workersz` đều trả HTTP 200. `r` reset lại dữ liệu QA và `q` dừng/dọn đúng môi trường tạm.
- [x] GitHub Actions run #13 cho đúng commit này hoàn tất thành công, đủ 6/6 jobs: Python 3.11/3.12/3.13, source-security, container, browser-smoke. [Xem CI run #13](https://github.com/KhangBon18/petcare-manager/actions/runs/43008051380).
- [x] Bằng chứng đã ghi nhận ở baseline hiện tại: Python 428/428, JavaScript 41/41, Playwright 18/18; cross-browser Playwright 3/3 engine.
- [ ] Không có rubric/đề cương chính thức của môn học trong các tệp repository đã tìm. Sinh viên cần đối chiếu yêu cầu do giảng viên cung cấp bên ngoài repository; tài liệu này không suy đoán yêu cầu chấm điểm.
- [ ] Chưa xác minh native browser zoom 200%, VoiceOver/screen reader, hay contrast bằng thiết bị đo. Không tuyên bố WCAG conformance.

## Hồ sơ học thuật nên có trong gói nộp

### Mã nguồn và cách chạy

- `README.md` — cài dependencies, chạy demo, cấu hình local và các giới hạn bảo mật.
- `requirements.txt`, `requirements.lock`, `requirements-browser.lock` — dependency declarations/constraints.
- `Dockerfile`, `docker-compose.yml`, `compose.qa-test.yml` — image và môi trường database/QA.
- `run.py`, `wsgi.py`, `main.py` — entry points.
- `petcare/` — Flask application, routes, services, repositories, migrations, templates, static assets, workers và AI/Vision code.
- `scripts/` — safe classroom launcher, test utilities, backup/restore utilities.
- `tests/` — unit, web, MySQL integration, JavaScript, browser/a11y tests và synthetic fixtures.
- `.github/workflows/ci.yml` — automated quality/security gates.

### Báo cáo và giải thích học thuật

- `docs/ACADEMIC_PROJECT_OVERVIEW.md`
- `docs/ACADEMIC_ARCHITECTURE.md`
- `docs/ACADEMIC_DATABASE_ERD.md`
- `docs/ACADEMIC_DEMO_SCRIPT.md`
- `docs/ACADEMIC_DEFENSE_QA.md`
- `docs/API_CONTRACT.md`
- `docs/MODULE_INVENTORY.md`, `docs/TEST_MATRIX.md`
- `docs/PHASE62_IMPLEMENTATION_REPORT.md`, `docs/PHASE62_CROSS_BROWSER_REPORT.md`, `docs/PHASE62_FINAL_ACCESSIBILITY.md`
- `docs/FINAL_DEMO_OPERATOR_GUIDE.md`, `docs/FINAL_DEFENSE_PREPARATION.md`, `docs/FINAL_ACADEMIC_RELEASE_STATUS.md`, tài liệu checklist này.

`docs/archive/` là tài liệu/mã desktop lịch sử, không mô tả kiến trúc Flask hiện hành. Chỉ đưa phần archive vào báo cáo nộp nếu muốn nêu tiến trình lịch sử; không dùng nó thay tài liệu web hiện tại.

## Không đưa vào gói nộp

- Bí mật thật: `.env`, mật khẩu, API key, token, private key, cookie/session, MySQL dump có dữ liệu cá nhân.
- `.venv/`, `node_modules/`, cache Playwright/browser, `__pycache__/`, log và tệp database runtime.
- Tệp ảnh/tài liệu người dùng thật hoặc export được tạo trong lúc demo.
- QA password, private QA log, QA storage, dữ liệu database được launcher tạo.
- Local agent/tooling đã có sẵn: `.agents/`, `docs/skills.md`, `skills-lock.json`; giữ nguyên tại máy nhưng không đưa vào submission thông thường.
- Không gửi database schema/data của `petcare_shop_dev` hoặc môi trường production.

`.env.example` là mẫu cấu hình, không phải `.env` thật. Đã kiểm tra danh sách tracked paths; chỉ `.env.example` là tracked trong nhóm tệp `.env`.

## Trước khi tạo ZIP hoặc nộp repository

- [ ] Mở lại [README](../README.md) từ checkout sạch và chạy chính xác các lệnh trong [hướng dẫn operator](FINAL_DEMO_OPERATOR_GUIDE.md).
- [x] Bốn tài liệu `FINAL_*` là một phần của gói submission và được publish cùng documentation release commit.
- [ ] Chạy qua rubric chính thức của môn học khi có rubric; bổ sung đúng deliverable mà rubric yêu cầu.
- [ ] Kiểm tra thư mục gói nộp không chứa `.env`, credential, QA data, virtualenv hoặc local tooling riêng.
- [ ] Thực hiện bước demo thủ công ở checklist cuối của [operator guide](FINAL_DEMO_OPERATOR_GUIDE.md), đặc biệt đăng nhập, project trên máy trình chiếu, zoom và accessibility nếu được yêu cầu.
- [x] Không stage/publish local tooling hoặc runtime artifacts; chỉ đưa bốn tài liệu academic đã rà soát vào documentation release commit.

## Kết luận

Có thể chuẩn bị gói nộp học thuật từ source và tài liệu hiện có, gồm bốn tài liệu Phase 6.4, sau khi sinh viên so khớp với rubric chính thức (nếu được cung cấp). Live demo là **CONDITIONAL GO** theo điều kiện operator guide. Đây không phải xác nhận production readiness hoặc WCAG compliance.
