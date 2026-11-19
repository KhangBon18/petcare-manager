# Tổng quan Đồ án Cuối kỳ — PetCare Manager & PetCare AI

- **Tên đề tài**: Quản lý Cửa hàng Thú cưng Đa Chi nhánh tích hợp Trợ lý Tư vấn Thông minh (**PetCare Manager & PetCare AI — Intelligent Pet Shopping & Care Assistant**)
- **Nhánh phát hành đã xác thực**: `solo/khang-petcare` (Release baseline `fe2f54facf7aab477ec919d54c9b570ff4703d1c`)
- **Phạm vi triển khai**: Đồ án học thuật môn Ngôn ngữ Lập trình Python & Kiểm thử QA cô lập (**không phải** hệ thống thương mại hay bệnh viện thú y lâm sàng đang vận hành production).

---

## 1. Mục tiêu Đồ án (Project Goals)

1. **Xây dựng nền tảng quản lý bán lẻ cửa hàng thú cưng chuẩn kiến trúc phân tầng bằng Python**:
   - Đáp ứng trọn vẹn chu trình nghiệp vụ của cửa hàng thú cưng thực tế: quản lý khách hàng, hồ sơ thú cưng có ảnh, danh mục sản phẩm, đơn nhập hàng nhiều đợt từ nhà cung cấp, bán hàng tại quầy (POS), hoàn trả một phần theo phân loại hàng trả, báo cáo doanh thu thuần và xuất dữ liệu mã hóa.
   - Thiết kế đa cửa hàng (**multi-tenant**) với cách ly dữ liệu nghiêm ngặt theo `tenant_id` và phân quyền theo vai trò (`owner`/`admin` và `staff`).
2. **Tích hợp Trợ lý AI có kiểm chứng dữ liệu thực tế (`PetCare AI`)**:
   - Biến dữ liệu MySQL của cửa hàng thành nguồn sự thật duy nhất (**Single Source of Truth**) cho tư vấn chọn thú cưng, gợi ý sản phẩm quy đổi đơn giá chuẩn (`Decimal`), so sánh trực quan và tra cứu tri thức chăm sóc chó mèo có trích dẫn nguồn uy tín (`WSAVA`, `ASPCA`, `AVMA`, `AAFP/ISFM`, `Cornell`).
   - Vận hành song song hai chế độ rõ ràng:
     - **Mode A — Offline Deterministic Python Engine (mặc định)**: chạy 100% bằng thuật toán Python + MySQL + Okapi BM25 cục bộ, không gọi mạng ngoài, độ trễ vài chục mili-giây.
     - **Mode B — Approved Real LLM Tool-Calling (`Google Gemini Free Tier` / `OpenAI-compatible`)**: chỉ bật có kiểm soát trong phiên QA được phê duyệt (`AI_PROVIDER_APPROVED=1`, `AI_TOOL_CALLING_ENABLED=1`), nơi mô hình `gemini-3.5-flash-lite` điều phối `13` công cụ chỉ-đọc của Python và diễn đạt câu trả lời tự nhiên nhưng **không bao giờ tự sinh SQL, không tự tính giá và không vượt qua chốt chặn an toàn thú y**.
3. **Đảm bảo chất lượng phần mềm bằng hệ thống kiểm thử tự động đa tầng**:
   - Kiểm chứng toàn diện qua Unit, Flask Web, MySQL 8.4 Integration (`510` ca), JavaScript DOM (`47` ca), Playwright Chromium E2E + `axe-core` (`26` ca), kịch bản diễn tập lớp học nối liền (`14` bước) và `4` bộ benchmark đánh giá AI độc lập.

---

## 2. Công nghệ Sử dụng (Technology Stack)

| Tầng thành phần | Công nghệ / Thư viện | Vai trò thực tế trong mã nguồn |
| :--- | :--- | :--- |
| **Ngôn ngữ cốt lõi** | Python `3.11+` (`3.11`, `3.12`, `3.13` trên CI) | Toàn bộ backend, thuật toán xếp hạng, NLU, BM25, dự báo nhu cầu, xử lý ảnh và điều phối LLM. |
| **Web Framework** | Flask, Jinja2, Gunicorn (`wsgi:app`) | Định tuyến Blueprint (`petcare/routes/`), render giao diện SSR đa ngôn ngữ (`vi`/`en`), bảo vệ CSRF & CSP. |
| **Cơ sở dữ liệu** | MySQL `8.4` (`InnoDB`, `utf8mb4`) | Lưu trữ quan hệ `26` bảng hiện hành, khóa dòng giao dịch (`FOR UPDATE`), khóa ngoại kép theo `tenant_id`. |
| **Frontend** | HTML5, CSS3 (`tokens.css`, `app.css`), Vanilla JS, GSAP `3.15.0` local | Không phụ thuộc bước build/bundler; tuân thủ CSP chặt (`script-src 'self'; style-src 'self'`), hỗ trợ giao diện di động `390x844`. |
| **Thuật toán Python nội sinh** | `decimal.Decimal`, Okapi BM25 + Bigram, Histogram màu + SimHash LSH (`pet_photo_lsh`), Dự báo tuyến tính gia quyền 8 tuần | Chuẩn hóa đơn giá `VND/kg`/`VND/L`, truy xuất tri thức `petcare/ai/knowledge_base.py`, tìm ảnh tương đồng `petcare/vision/`, dự báo tồn kho `petcare/analytics/demand_forecast.py`. |
| **Nhà cung cấp LLM (Tùy chọn QA)** | Google Gemini API Free Tier (`gemini-3.5-flash-lite`) & OpenAI-compatible HTTP client (`urllib.request` + `ssl`/`certifi`) | Gọi công cụ có kiểm soát qua `/v1beta/openai/chat/completions` (`petcare/ai/client.py`, `petcare/ai/llm_tool_agent.py`), không dùng SDK nặng bên thứ ba. |
| **Bảo mật & Mã hóa** | `PBKDF2-HMAC-SHA256`, `AES-256-GCM`, `Fernet` (`cryptography`), `XlsxWriter`, `Pillow` | Băm mật khẩu, mã hóa gói xuất dữ liệu cửa hàng `.pcarexport`, mã hóa hàng đợi email outbox, chuẩn hóa và gỡ EXIF ảnh tải lên. |
| **Kiểm thử & CI/CD** | `unittest`, Node `--test`, Playwright, `axe-core`, Bandit, `pip-audit`, Trivy, Docker Compose, GitHub Actions | `6/6` cổng kiểm định tự động trong `.github/workflows/ci.yml`. |

---

## 3. Kiến trúc Phân tầng Hệ thống (System Architecture)

Mã nguồn trong gói `petcare/` tuân thủ nguyên tắc tách biệt trách nhiệm nghiêm ngặt:

1. **Tầng Giao tiếp HTTP (`petcare/routes/`, `petcare/app_factory.py`, `petcare/app_hooks.py`)**:
   - Xác thực phiên đăng nhập (session chỉ giữ `user_id`; quyền và trạng thái hoạt động được nạp lại từ MySQL ở mỗi request), kiểm tra CSRF token, giới hạn tần suất (rate limit), gắn header bảo mật và định dạng dữ liệu trả về HTML/JSON.
2. **Tầng Nghiệp vụ & Giao dịch (`petcare/services/`)**:
   - Thực thi quy tắc kinh doanh, kiểm tra phân quyền vai trò (`admin` vs `staff`), quản lý ranh giới giao dịch nguyên tử (`with transaction() as connection:`) cho thanh toán hóa đơn, nhận hàng nhập kho, hoàn trả hàng và ghi nhật ký kiểm toán (`audit_events`).
3. **Tầng Trí tuệ Nhân tạo & Phân tích (`petcare/ai/`, `petcare/vision/`, `petcare/analytics/`)**:
   - Điều phối hội thoại nhiều lượt (`orchestrator.py`), phân loại an toàn thú y (`safety_triage.py`), hiểu ngôn ngữ tự nhiên Việt–Anh (`nlu.py`), chấm điểm gợi ý thú cưng/sản phẩm (`recommender_pets.py`, `recommender_products.py`), truy xuất tri thức BM25 (`knowledge_base.py`), thực thi `13` công cụ chỉ-đọc (`tools.py`) và kết nối LLM an toàn (`provider.py`, `client.py`, `llm_tool_agent.py`).
4. **Tầng Truy cập Dữ liệu (`petcare/repositories/`, `petcare/database/`)**:
   - Chỉ chứa truy vấn SQL tham số hóa (`%s`), không tự ý `commit`, luôn gắn ngữ cảnh `@petcare_tenant_id` và điều kiện `tenant_id = %s`.
   - Quản lý kết nối pool, kiểm tra sẵn sàng (`/healthz`, `/readyz`, `/workersz`), hệ thống migration cộng dồn `26` bảng (`initialize.py`) và bộ tạo dữ liệu mẫu cô lập (`seed.py`).
5. **Tiến trình Nền (`mail_worker.py`, `tenant_export_worker_cli.py`)**:
   - Xử lý hàng đợi gửi email xác thực/khôi phục mật khẩu và đóng gói dữ liệu cửa hàng mã hóa `.pcarexport` độc lập với tiến trình web, có cơ chế báo nhịp tim (`worker_heartbeats`).

---

## 4. Các Nhóm Chức năng Đã Hoàn thiện & Kiểm chứng (Verified Features)

### 4.1. Quản trị Bán lẻ Đa Cửa hàng (`PetCare Manager`)
- **Xác thực, Đa ngôn ngữ (`VI`/`EN`) & Phân quyền**: Đăng nhập theo `store_slug` (`main`), chống vét cạn mật khẩu (`login_throttle`), chuyển đổi song ngữ Việt–Anh xuyên suốt giao diện và file báo cáo, phân quyền chặt giữa Quản trị viên (`owner`/`admin`) và Nhân viên (`staff`).
- **Khách hàng & Hồ sơ Thú cưng**: Quản lý thông tin khách mua, lịch sử hóa đơn và thú cưng đã mua; quản lý hồ sơ thú cưng (`available`, `sold`, `inactive`), lưu trữ ảnh riêng tư đã loại bỏ metadata EXIF.
- **Tìm kiếm Thú cưng Tương đồng bằng Ảnh (`/pets/find-similar`)**: So khớp cục bộ bằng đặc trưng màu vùng trung tâm, cấu trúc sáng/tối, chỉ mục SimHash LSH (`pet_photo_lsh`) và thuộc tính ghi nhận, kèm giải thích điểm thành phần minh bạch. Trên form thêm thú cưng (`/pets/new`), luồng duyệt gợi ý thuộc tính chỉ điền vào trường đang trống và không tự động lưu.
- **Tồn kho & Đơn nhập hàng Nhiều đợt (`/products/`, `/purchasing/`)**: Tạo đơn đặt hàng nhà cung cấp (`ordered` chưa cộng tồn), nhận hàng từng phần (`partially_received` -> `received`), chống gửi trùng phiếu nhận bằng khóa `purchase_order_receipt_requests` và ghi sổ biến động `stock_movements`.
- **Bán hàng POS, Thanh toán & Hoàn trả Một phần (`/invoices/`)**: Lập hóa đơn kết hợp sản phẩm và thú cưng; chỉ khi xác nhận thanh toán mới khóa bản ghi, trừ tồn kho và chuyển thú cưng sang `sold` gắn `buyer_id`; hỗ trợ hoàn trả từng phần với 3 hướng xử lý (`resell` nhập lại kho bán tiếp, `quarantine` cách ly, `not_returned` không thu hồi hàng) trên sổ cái bất biến `invoice_refunds`.
- **Báo cáo Doanh thu, Dự báo Tồn kho & Xuất Dữ liệu Mã hóa (`/reports/`, `/users/export`)**: Báo cáo doanh thu thuần đối chiếu kỳ trước, gợi ý nhập hàng và dự báo nhu cầu 8 tuần; xuất Excel `.xlsx` từ snapshot có chữ ký số (hiệu lực 15 phút); xuất toàn bộ dữ liệu tenant ra gói `.pcarexport` mã hóa `AES-256-GCM`.

### 4.2. Trợ lý Mua sắm & Chăm sóc Thông minh (`PetCare AI`)
- **Không gian Hội thoại Chuyên biệt (`/assistant/chat`) & Khung Trợ lý Nổi (`#assistant-panel`)**: Tách bạch rõ `Không gian cửa hàng` (`workspace`, mở thêm `5` công cụ vận hành nội bộ) và `Xem thử khách mua` (`shopper_preview`, khóa chặt dữ liệu doanh thu/đơn nhập).
- **Ghép đôi Thú cưng Có Giải thích (`0–100` điểm)** và **Gợi ý & So sánh Sản phẩm Quy đổi Đơn giá (`Decimal`)**: Loại trừ cứng các thành phần dị ứng đã khai báo trong phiên (ví dụ dị ứng thịt gà), tự động gợi ý sản phẩm thay thế khi hết hàng và lập bảng so sánh `2–4` mã SKU.
- **Bộ nhớ Hội thoại Đa lượt (`PreferenceSlots`)**: Ghi nhớ loài, môi trường sống, độ tuổi, ngân sách, dị ứng qua nhiều lượt hỏi và hỗ trợ câu lệnh gỡ bỏ ràng buộc tự nhiên (*"bỏ giới hạn giá"*, *"bé hết dị ứng gà rồi"*).
- **Tra cứu Tri thức Chăm sóc (`9` tài liệu chuẩn) & Chốt chặn An toàn Thú y 3 Tầng**: Phát hiện triệu chứng cấp cứu hoặc ngộ độc (nhai hoa ly, sô-cô-la, xylitol, khó thở, bí tiểu...) ngay tại Python trước khi gọi LLM, từ chối kê đơn/tính liều thuốc `mg/kg` và luôn đính kèm trích dẫn nguồn cùng miễn trừ trách nhiệm thú y.
- **Tích hợp Google Gemini Free Tier (`gemini-3.5-flash-lite`) có Kiểm chứng**: Đã kiểm chứng thực tế luồng gọi công cụ 2 bước và hạ cấp an toàn về Offline Python khi gặp lỗi mạng, timeout hoặc chạm hạn ngạch Free Tier.

*(Lưu ý lịch sử dự án: Các tính năng khám bệnh lâm sàng, lịch hẹn tiêm chủng và dịch vụ spa thuộc phiên bản ứng dụng desktop cũ lưu trong `docs/archive/`, không thuộc phạm vi ứng dụng web bán lẻ hiện hành).*

---

## 5. Các Giới hạn Đã biết & Ranh giới Học thuật (Known Limitations)

1. **Chưa phải bản triển khai thương mại (Non-Production Academic System)**:
   - Thanh toán hóa đơn và hoàn tiền là bút toán sổ cái nội bộ để mô phỏng nghiệp vụ; ứng dụng **không** tích hợp cổng thanh toán ngân hàng/ví điện tử thật.
   - Chưa thực hiện kiểm thử chịu tải đồng thời quy mô lớn (load/soak testing), chưa kiểm chứng gửi SMTP/S3 thương mại trực tiếp trên hạ tầng đám mây và chưa đánh giá bằng phần mềm đọc màn hình thực tế (VoiceOver/NVDA) hay zoom trình duyệt gốc 200% (dù `axe-core` tự động đạt `0` lỗi nghiêm trọng theo tiêu chuẩn WCAG 2.1 AA).
2. **Phân biệt rõ Thị giác Máy tính Cục bộ, Mock Vision và AI Vision**:
   - Tìm ảnh tương đồng cục bộ dựa trên phân bố màu sắc và bố cục sáng/tối, **không phải** mô hình học sâu nhận diện giống loài.
   - Trong launcher lớp học (`scripts/demo/classroom.sh --target qa`), dịch vụ gợi ý ảnh chạy bằng **`scripts/demo/vision_mock.py` (`petcare-local-demo-mock`)** trả nhãn giả lập cố định trên loopback để kiểm thử giao diện duyệt gợi ý; tuyệt đối không trình bày đây là độ chính xác của mô hình AI Vision thật (`AI_VISION_ENABLED` mặc định `False`).
3. **Giới hạn của Google Gemini Free Tier trong Môi trường QA**:
   - Mặc định cấu hình ứng dụng tắt gọi AI ngoài (`AI_PROVIDER_APPROVED=False`, `AI_TOOL_CALLING_ENABLED=False`).
   - Khi bật trong phiên QA (`scripts/run_gemini_qa_web.py`), gói miễn phí Google AI Studio dùng chung hạn ngạch khoảng `~15 RPM / 250.000 TPM / 500 RPD` (được ứng dụng kẹp bảo vệ ở `10 RPM / 180.000 TPM / 450 RPD` và giãn cách `1.2s`), độ trễ phản hồi 2 bước dao động `4–16 giây` tùy tải máy chủ Google.
4. **Độ lệch Nhãn Đề Kiểm thử Bất biến AI-2.2 (`39 / 40`, `97.5%`)**:
   - Trong tệp kiểm thử độc lập `petcare/ai/final_safety_generalization_eval.py`, ca `FG-MUL-01` kỳ vọng nhãn gõ nhầm `'KB-NUT-001'` trong khi mã tài liệu chuẩn trong kho tri thức là `'KB-NUTR-001'` (hệ thống trả đúng `'KB-NUTR-001'` và đạt `15/15` ca an toàn thú y với `100%` recall & precision). Giữ nguyên tệp kiểm thử hold-out không sửa đáp án để bảo toàn tính trung thực thực nghiệm.
5. **Phạm vi Loài trong Kho Tri thức**:
   - Tư vấn dinh dưỡng và chăm sóc của `PetCare AI` chỉ hỗ trợ **chó và mèo**; các câu hỏi về thú ngoại lai (thỏ, hamster, chim, bò sát...) được hệ thống từ chối minh bạch thay vì suy đoán ngoài dữ liệu đã kiểm duyệt.

---

## 6. Bộ Tài liệu Tham khảo Chính trong `docs/`

- [AI_ARCHITECTURE_EXPLAINED.md](AI_ARCHITECTURE_EXPLAINED.md) — Giải thích chuyên sâu kiến trúc Python AI, công thức chấm điểm, gọi hàm Gemini 2 bước, RAG BM25, RBAC và cơ chế fallback.
- [CLASSROOM_DEMO_RUNBOOK.md](CLASSROOM_DEMO_RUNBOOK.md) — Sổ tay khởi động, vận hành và xử lý sự cố demo lớp học.
- [TEN_MINUTE_PRESENTATION_SCRIPT.md](TEN_MINUTE_PRESENTATION_SCRIPT.md) — Kịch bản lời thoại tiếng Việt chi tiết theo từng phút kèm thao tác giao diện.
- [PROJECT_DEFENSE_QA.md](PROJECT_DEFENSE_QA.md) — Bộ câu hỏi và trả lời vấn đáp bảo vệ đồ án trước giảng viên.
- [FINAL_SUBMISSION_CHECKLIST.md](FINAL_SUBMISSION_CHECKLIST.md) — Danh mục kiểm tra toàn diện trước khi nộp đồ án.
