# PetCare AI & Petcare Manager — Tổng quan dự án

## Định hướng sản phẩm (Product Pivot)

**Đề tài trọng tâm**: *"Xây dựng trợ lý AI tư vấn và gợi ý sản phẩm thông minh cho cửa hàng thú cưng bằng Python"*
**Tên tiếng Anh**: **PetCare AI — Intelligent Pet Shopping & Care Assistant**

Ứng dụng kết hợp **PetCare AI** làm **trải nghiệm sản phẩm trung tâm** (`GET /assistant/chat`) trên nền tảng dữ liệu và vận hành bán lẻ đa cửa hàng (**Petcare Manager** — Flask / Jinja2 / MySQL 8.4):
- Mọi gợi ý thú cưng, gợi ý sản phẩm, bảng so sánh đối chiếu đơn giá quy đổi và phân tích vận hành đều truy xuất trực tiếp từ dữ liệu MySQL xác thực theo đúng `tenant_id`, vai trò (`admin` / `staff`) và phạm vi (`workspace` / `shopper_preview`).
- Giữ nguyên toàn bộ nền tảng nghiệp vụ bán lẻ (POS, nhập hàng nhiều đợt, hoàn tiền, báo cáo, tìm kiếm ảnh cục bộ và dự báo nhu cầu 8 tuần) làm nguồn sự thật (Source of Truth) đáng tin cậy.

## Mục tiêu kỹ thuật & học thuật

- Thiết kế kiến trúc **Python AI Core** phân tầng rõ ràng (`petcare/ai/`): NLU song ngữ Việt–Anh, bộ nhớ hội thoại nhiều lượt theo phiên (`PreferenceSlots`), registry 13 công cụ Python chỉ đọc (allowlisted read-only tools), công cụ gợi ý có giải thích điểm số, truy xuất tri thức Okapi BM25 có trích dẫn nguồn, và hàng rào an toàn thú y/bảo mật.
- Tách biệt xử lý HTTP (`routes/`), điều phối AI & nghiệp vụ (`ai/`, `services/`), và truy vấn lưu trữ tham số hóa (`repositories/`).
- Đảm bảo an toàn đa tenant, RBAC, CSP nghiêm ngặt (`script-src 'self'; style-src 'self'`), không sinh SQL từ mô hình và không tự động ghi/tạo giao dịch khi chưa có xác nhận của con người.
- Đánh giá định lượng bằng bộ benchmark tự động 84 kịch bản (`scripts/evaluate_petcare_ai.py`) cùng kiểm thử Unit, Web, MySQL Integration, JavaScript DOM và Playwright Chromium E2E + `axe-core`.

## Chức năng cốt lõi

### 1. Không gian Trợ lý AI trung tâm (`PetCare AI`)
- **Không gian hội thoại toàn trang (`/assistant/chat`)** tích hợp nổi bật trên thanh điều hướng chính (`Trợ lý AI` / `AI Assistant`), kèm nút tắt nổi tùy chọn trên các trang nghiệp vụ khác.
- **Hội thoại nhiều lượt & nhớ ngữ cảnh (`PreferenceSlots`)**: Phát hiện thông tin còn thiếu, đặt câu hỏi làm rõ, cập nhật ngân sách/loài/tính cách theo lượt hỏi tiếp theo và cho phép xóa ngữ cảnh an toàn.
- **Ghép đôi thú cưng 2 giai đoạn có giải thích (`0–100` điểm)**: Lọc cứng theo loài, trạng thái `available` và trần ngân sách; chấm điểm minh bạch dựa trên dữ liệu xác minh; tuyệt đối không suy đoán tính cách hay độ hợp căn hộ từ tên giống (`unknown` = `0` điểm thưởng kèm cảnh báo rõ ràng).
- **Gợi ý & so sánh sản phẩm chuẩn hóa đơn giá (`Decimal`)**: Quy đổi chính xác `VND/kg`, `VND/100g`, `VND/L`, `VND/tờ`; lọc theo loài, độ tuổi, cân nặng, dị ứng khai báo trong phiên; xử lý hàng hết tồn kho kèm gợi ý thay thế và bảng so sánh đối chiếu 2–4 sản phẩm.
- **Kho tri thức chăm sóc chó mèo đáng tin cậy (`Okapi BM25`)**: Truy xuất tài liệu biên tập từ nguồn uy tín (`WSAVA`, `AVMA`, `AAFP/ISFM`, `ASPCA`, `Cornell`) kèm trích dẫn nguồn, miễn trừ trách nhiệm bác sĩ thú y, từ chối kê đơn/liều thuốc và cảnh báo cấp cứu thú y tức thời.
- **Chế độ Xem thử khách mua (`Shopper Preview QA`)**: Cho phép kiểm thử trải nghiệm người mua hàng an toàn ngay trong môi trường QA có xác thực mà không làm lộ doanh thu, đơn nhập hàng hay cảnh báo tồn kho nội bộ.

### 2. Nền tảng vận hành bán lẻ & thuật toán Python-first (`Petcare Manager`)
- Quản lý khách hàng, hồ sơ thú cưng, tìm kiếm thú cưng tương tự bằng đặc trưng thị giác cục bộ (`petcare/vision/`).
- Quản lý sản phẩm, sổ cái xuất nhập tồn, đơn mua hàng nhà cung cấp nhận nhiều đợt, hóa đơn POS, hoàn tiền theo phân loại xử lý hàng trả và dự báo nhu cầu tồn kho gia quyền 8 tuần (`petcare/analytics/demand_forecast.py`).
- Xuất báo cáo XLSX và sao lưu tenant mã hóa chạy nền qua worker.

## Công nghệ

Python 3.11+, Flask, Jinja2, Vanilla JavaScript (CSP-safe), MySQL 8.4/InnoDB, Okapi BM25 & `Decimal` ranking engines, Playwright, Node test runner, `unittest`, Bandit, `pip-audit` và Docker Compose. Mặc định vận hành ở **Mode A (Offline Deterministic Python Engine)** không gọi API trả phí; hỗ trợ sẵn cổng chuyển đổi **Mode B (`AI_PROVIDER_APPROVED=1`)** cho OpenAI-compatible LLM.

## Tài liệu liên quan

- [Tầm nhìn sản phẩm & phân tích 3C PetCare AI](PETCARE_AI_PRODUCT_VISION.md)
- [Kiến trúc hệ thống Python AI Core](PETCARE_AI_ARCHITECTURE.md)
- [Thuật toán gợi ý thú cưng, sản phẩm & so sánh đơn giá](PETCARE_AI_RECOMMENDATION_ENGINE.md)
- [Kho tri thức BM25 & an toàn thú y](PETCARE_AI_KNOWLEDGE_BASE.md)
- [Báo cáo đánh giá thực nghiệm 84 kịch bản](PETCARE_AI_EVALUATION.md)
- [Sẵn sàng tích hợp nhà cung cấp LLM ngoài](PETCARE_AI_PROVIDER_READINESS.md)
- [Kiến trúc nền tảng](ACADEMIC_ARCHITECTURE.md) · [Database ERD](ACADEMIC_DATABASE_ERD.md)
