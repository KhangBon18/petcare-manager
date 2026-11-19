# Checklist Nộp Đồ án & Bảo vệ Cuối kỳ — PetCare Manager & PetCare AI

- **Ngày cập nhật rà soát**: `2026-11-17`
- **Nhánh được ủy quyền**: `solo/khang-petcare`
- **Mốc mã nguồn đã xác thực CI (`AI-3.3`)**: `fe2f54facf7aab477ec919d54c9b570ff4703d1c`
- **Bằng chứng GitHub Actions CI**: [Run #44051734253 (`6 / 6` jobs `success`)](https://github.com/KhangBon18/petcare-manager/actions/runs/44051734253)

---

## 1. Kiểm tra Kho Mã nguồn & Cấu hình Môi trường (Repository, Setup & Environment)

- [x] Nhánh hiện tại là `solo/khang-petcare`, đồng bộ sạch với `origin/solo/khang-petcare` tại baseline ứng dụng `fe2f54facf7aab477ec919d54c9b570ff4703d1c` (không tác động nhánh `main`, không force-push).
- [x] Cài đặt phụ thuộc được khóa phiên bản rõ ràng qua `requirements.txt`, `requirements.lock` và `requirements-browser.lock` trên Python `3.11+` (`3.11`, `3.12`, `3.13` đều xanh trên CI).
- [x] Cấu hình mẫu `.env.example` đầy đủ, không chứa khóa thật; các cờ AI bên ngoài mặc định tắt an toàn trong `petcare/config.py`:
  - `AI_PROVIDER_APPROVED = False` (`0`)
  - `AI_TOOL_CALLING_ENABLED = False` (`0`)
  - `AI_VISION_ENABLED = False` (`0`)
- [x] Đã quét xác minh **không có** tệp `.env`, khóa `GEMINI_API_KEY` / `AI_API_KEY`, mật khẩu thật, session/cookie hay dữ liệu cá nhân trong lịch sử commit phát hành.
- [x] Các tệp công cụ cục bộ ngoài phạm vi đồ án (`.agents/`, `docs/skills.md`, `skills-lock.json`, ảnh chụp rời trên máy) được giữ nguyên tại máy phát triển nhưng **không đưa vào commit hay gói ZIP nộp bài**.

---

## 2. Dữ liệu Mẫu, Môi trường QA & Lệnh Khởi động Demo (Demo Data & Runbook)

- [x] Bộ dữ liệu mẫu trong `petcare/database/seed.py` hoàn toàn là dữ liệu tổng hợp học thuật gắn với cửa hàng `main`:
  - `2` tài khoản vai trò mẫu: `admin` (`owner`) và `staff1` (`staff`) — mật khẩu do người trình bày tự nhập lúc khởi chạy (`>= 16` ký tự, không trùng nhau, không lưu mật khẩu mặc định).
  - `12` hồ sơ khách hàng giả lập (đầu số điện thoại `00000000..`), `22` mặt hàng có mã SKU/tồn kho/ngưỡng đặt lại, `74` cá thể thú cưng (`35` chó, `37` mèo, `1` thỏ, `1` hamster; `68` ảnh tổng hợp) và `7` hóa đơn mẫu đã thanh toán.
- [x] **Chế độ 1 — Demo Offline Toàn phần (`Mode A`)** đã xác minh khởi chạy thành công bằng lệnh:
  ```bash
  PYTHON=.venv/bin/python scripts/demo/classroom.sh --target qa
  ```
  - Tự tạo MySQL 8.4 cô lập trong `tmpfs` (hậu tố `_test`, `26` bảng), khởi chạy Flask web + `mail_worker` + `tenant_export_worker` + `vision_mock` cục bộ; `/healthz`, `/readyz`, `/workersz` đều trả `HTTP 200`; lệnh `r` reset sạch dữ liệu và `q` tắt/dọn dẹp toàn bộ container tạm.
  - Lưu ý vận hành: mở từ cửa sổ terminal sạch không mang sẵn biến `DB_HOST`/`DB_NAME`/`DB_PASSWORD` kế thừa (script chủ động từ chối biến DB kế thừa để bảo vệ dữ liệu khác).
- [x] **Chế độ 2 — Demo Web QA bật Google Gemini Free Tier (`Mode B`)** trong [CLASSROOM_DEMO_RUNBOOK.md](CLASSROOM_DEMO_RUNBOOK.md) đã được đồng bộ nhất quán với container QA thực tế trên máy (`petcare-gemini-live-qa`, cổng `127.0.0.1:33339`, database `petcare_gemini_qa_test`, mật khẩu container QA tạm thời cục bộ `disposable_qa_pw` và cờ `--sync-demo-passwords`), tái sử dụng an toàn mà không cần xóa hay tạo lại database.

---

## 3. Bằng chứng Kiểm thử Tự động & CI/CD (Tests, Screenshots & CI Evidence)

- [x] **Python + MySQL 8.4 Integration Suite**: **`510 / 510 PASS`** (`0` lỗi, `0` bỏ qua).
- [x] **JavaScript Frontend Unit/DOM Suite (`node --test`)**: **`47 / 47 PASS`**.
- [x] **Playwright Browser Smoke & PetCare AI E2E Suite**: **`26 / 26 PASS`** (bao gồm giao diện di động `390x844` không tràn ngang và quét `axe-core` WCAG 2.1 AA `0` vi phạm mức `serious`/`critical`).
- [x] **Diễn tập Chuỗi Nghiệp vụ Lớp học (`scripts/demo/classroom_rehearsal.py`)**: **`14 / 14 PASS`** (đối chiếu khớp sổ cái nhập kho `3 + 5 = 8`, bán POS `8 -> 6`, hoàn trả `6 -> 7`, xuất `.pcarexport` và chặn quyền `staff1` `HTTP 403`).
- [x] **Diễn tập Tự động Giao diện 8 Bước trên `classroom.sh` (Playwright Headless)**: **`8 / 8 PASS`** (`15.52 giây` tổng thời gian phản hồi giao diện máy tính, chứng minh độ trễ hệ thống đủ gọn cho khung trình bày **10 phút**; *không thay thế lượt sinh viên tự tập nói thành tiếng*).
- [x] **Các Bộ Đánh giá Độc lập PetCare AI (giữ nguyên SHA-256 bất biến)**:
  - Core Benchmark (`petcare/ai/evaluation.py`): **`84 / 84`** (`100%`)
  - Independent OOD (`petcare/ai/independent_evaluation.py`): **`44 / 44`** (`100%`)
  - AI-2.1 Held-out Safety (`petcare/ai/heldout_safety_evaluation.py`): **`34 / 34`** (`100%`)
  - AI-2.2 Final Safety & Generalization Hold-out (`petcare/ai/final_safety_generalization_eval.py`): **`39 / 40`** (`97.5%`; đạt trọn vẹn `15 / 15` ca an toàn thú y)
- [x] **Ảnh chụp minh chứng giao diện**: Lưu sẵn tại `docs/assets/phase62/` và `docs/assets/petcare-ai/` (gồm dashboard, đơn nhập, hóa đơn POS, hoàn trả, báo cáo, không gian chat AI và giao diện mobile `390px`).
- [x] **GitHub Actions CI**: Run [`44051734253`](https://github.com/KhangBon18/petcare-manager/actions/runs/44051734253) hoàn tất **`success`** trên cả `6 / 6` jobs (`verify (3.11)`, `verify (3.12)`, `verify (3.13)`, `browser-smoke`, `source-security`, `container`).

---

## 4. Hồ sơ Tài liệu Học thuật & Trình bày trong `docs/`

- [x] [README.md](../README.md) — Hướng dẫn cài đặt, cấu trúc dự án, bảo mật và lệnh khởi chạy.
- [x] [FINAL_PROJECT_OVERVIEW.md](FINAL_PROJECT_OVERVIEW.md) — Tổng quan mục tiêu, công nghệ, kiến trúc phân tầng, chức năng và giới hạn đồ án.
- [x] [AI_ARCHITECTURE_EXPLAINED.md](AI_ARCHITECTURE_EXPLAINED.md) — Giải thích chi tiết NLU, thuật toán chấm điểm gợi ý, đối chứng MySQL, gọi hàm Gemini 2 bước, Okapi BM25 RAG, bộ nhớ đa lượt, RBAC, fallback và sơ đồ Mermaid.
- [x] [CLASSROOM_DEMO_RUNBOOK.md](CLASSROOM_DEMO_RUNBOOK.md) — Sổ tay khởi động demo Offline & Gemini QA, quy trình dự phòng mất mạng/hết quota và dọn dẹp an toàn.
- [x] [TEN_MINUTE_PRESENTATION_SCRIPT.md](TEN_MINUTE_PRESENTATION_SCRIPT.md) — Kịch bản lời thoại tiếng Việt 10 phút bấm giờ từng bước kèm thao tác cụ thể.
- [x] [PROJECT_DEFENSE_QA.md](PROJECT_DEFENSE_QA.md) — `18` câu hỏi và trả lời vấn đáp chuyên sâu trước giảng viên.
- [x] [ACADEMIC_DATABASE_ERD.md](ACADEMIC_DATABASE_ERD.md) & [API_CONTRACT.md](API_CONTRACT.md) — Lược đồ thực thể kết hợp MySQL và đặc tả API nội bộ.
- [x] *(Lưu ý)*: Thư mục `docs/archive/` chỉ lưu tư liệu bản desktop cũ mang tính lịch sử; không dùng thay cho tài liệu kiến trúc web Flask hiện hành.

---

## 5. Các Mục Tuyệt đối KHÔNG Đưa vào Gói Nộp Bài

- [ ] Không nộp `.env`, `GEMINI_API_KEY`, mật khẩu tạm thời lúc chạy demo, token hay cookie phiên đăng nhập.
- [ ] Không nộp `.venv/`, `node_modules/`, `__pycache__/`, bộ nhớ đệm trình duyệt Playwright hoặc thư mục `/tmp/petcare-*`.
- [ ] Không nộp bản dump của database phát triển `petcare_shop_dev` hoặc các gói `.pcarexport` / `.pcarebackup` sinh ra khi chạy thử.
- [ ] Không nộp các tệp công cụ cá nhân ngoài phạm vi bài tập: `.agents/`, `docs/skills.md`, `skills-lock.json` và tệp ảnh chụp rời ở thư mục cha.

---

## 6. Rà soát Tính Trung thực Học thuật & Các Bước Cuối của Sinh viên

- [x] Mọi khẳng định kỹ thuật đều có mã nguồn và bài kiểm thử đối chứng; **không** tuyên bố hệ thống đã sẵn sàng cho production thương mại hay phòng khám lâm sàng.
- [x] Phân biệt rõ **Mode A (Offline Python)**, **Mode B (Google Gemini Free Tier `gemini-3.5-flash-lite`)**, **tìm ảnh cục bộ bằng histogram/SimHash** và **dịch vụ Vision mock cục bộ (`vision_mock.py`)**.
- [x] Nêu minh bạch giới hạn hạn ngạch/độ trễ của Google AI Studio Free Tier và lý do lệch 1 mã nhãn `'KB-NUT-001'` vs `'KB-NUTR-001'` ở bộ hold-out AI-2.2 (`39 / 40`).
- [ ] **Việc sinh viên tự thực hiện cuối cùng trước giờ nộp & bảo vệ**:
  1. **Tự tập nói thành tiếng bấm giờ 10 phút** (chưa thực hiện thay sinh viên): mở [TEN_MINUTE_PRESENTATION_SCRIPT.md](TEN_MINUTE_PRESENTATION_SCRIPT.md) và tự chạy thử trên đúng máy tính sẽ mang lên lớp.
  2. Đối chiếu danh sách tệp nộp với đề cương/rubric chính thức của giảng viên (bổ sung báo cáo PDF/slide nếu môn học yêu cầu nộp kèm trên LMS).
  3. Kiểm tra lần cuối gói nén sạch `petcare-manager-final-submission.zip` (xuất từ `git archive HEAD`) và tự tải lên hệ thống nộp bài của trường.
