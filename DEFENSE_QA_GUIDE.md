# Cẩm nang vấn đáp — PetCare Manager v1.0 Demo

Dùng cùng [kịch bản trình bày](DEMO_SCRIPT.md). Khi được hỏi, mở **file → tìm tên hàm/class** trong bảng dưới, giải thích quy tắc rồi chỉ test kiểm chứng. Đường dẫn tính từ thư mục gốc repo; số dòng có thể thay đổi khi format nên ưu tiên tìm symbol.

Phạm vi: Python + Flask/Jinja + MySQL/InnoDB, quản lý cửa hàng bán sản phẩm và từng cá thể thú cưng. Đây là polished MVP local, không có nghiệp vụ khám bệnh hoặc thanh toán ngân hàng thật.

## 1. Transaction, chống bán trùng và âm kho

| Mở file | Hàm/class cần chỉ | Vai trò |
|---|---|---|
| [invoice_service.py](petcare/services/invoice_service.py) | `pay_invoice()` | Khóa hóa đơn, các dòng hàng, sản phẩm và thú cưng; kiểm tra lại trước khi ghi. |
| [connection.py](petcare/database/connection.py) | `transaction()` | Context manager `@contextmanager`: thành công `commit()`, có exception `rollback()`, luôn đóng kết nối trong `finally`. |
| [invoice_repo.py](petcare/repositories/invoice_repo.py) | `get_invoice(lock=True)`, `get_items_for_update()`, `update_paid()` | `SELECT ... FOR UPDATE`; chỉ chuyển `unpaid → paid`. |
| [schema.sql](petcare/database/schema.sql) | Bảng `products`, `pets`, `invoice_items` | InnoDB, CHECK tồn không âm, cá thể pet có quantity = 1, ràng buộc buyer/status. |

**Giải thích 30 giây:** `pay_invoice()` giữ khóa dòng hóa đơn trước. Nếu đã `paid`, trả `already_paid` ngay nên không trừ kho lần nữa. Khóa sản phẩm/pet theo thứ tự ID nhất quán giúp giảm deadlock; không phải cam kết loại bỏ mọi deadlock. Trừ sản phẩm bằng `UPDATE ... stock_qty >= quantity`, bán pet bằng `UPDATE ... sale_status = 'available'`, kiểm `rowcount == 1`. Stock movement, buyer và trạng thái hóa đơn cùng một transaction. Nếu pet đã bán sau lúc lập đơn, mọi phần trừ kho trước đó cũng rollback. Đơn chưa thu không giữ hàng; phải kiểm tra lại khi thu.

**Chỉ test:** `tests/integration/test_mysql_sales.py` → `MySQLSalesIntegrationTests.test_payment_updates_stock_pet_and_revenue_once()` và `test_concurrent_payment_cannot_sell_last_unit_twice()`; test sau dùng hai thread/Barrier và MySQL thật.

## 2. Intent tiếng Việt, thời gian, giá và AI fallback

| Mở file | Hàm/class cần chỉ | Vai trò |
|---|---|---|
| [assistant_service.py](petcare/services/assistant_service.py) | `_normalize()`, `_question_intent()`, `pet_filter_spec()`, `answer()`, `local_answer()` | Unicode NFD/casefold/bỏ dấu, xác định chủ đề, lọc thuộc tính, điều phối local/LLM. |
| [assistant_query.py](petcare/services/assistant_query.py) | `PriceFilter`, `query_period()`, `catalog_filters()` | `@dataclass(frozen=True)` giữ biên giá bằng `Decimal`; tách cụm thời gian/giá khỏi từ khóa. |
| [catalog_service.py](petcare/services/catalog_service.py) | `lookup()` | Bộ lọc xác định → kết quả có cấu trúc/card. |
| [catalog_repo.py](petcare/repositories/catalog_repo.py) | `search()` | SQL tham số hóa, bảng/cột/toán tử trong danh sách cố định; COUNT toàn bộ kết quả rồi LIMIT 12 cho hiển thị. |
| [client.py](petcare/ai/client.py) | `is_configured()`, `complete()`, `AIProviderError` | Gọi provider có timeout; bọc lỗi thành exception kiểm soát được. |
| [assistant_routes.py](petcare/routes/assistant_routes.py) | `chat()` | Kiểm kiểu JSON/message, xác thực và quota; message số/list/object trả HTTP 400. |

**Ví dụ phải nhớ:** “Hôm nay còn mèo nào?” → intent `pet`; “hôm nay” không tự biến thành intent doanh thu. “Tìm mèo lông trắng dưới 3 triệu” → loài/màu + `sale_price < Decimal('3000000')`; cụm giá đã trích xuất không còn bị đem đi tìm LIKE. “Dưới/trên” loại trừ biên; “tối đa/tối thiểu/từ…đến…” gồm biên; “khoảng N” là ±10% theo quy ước ứng dụng. Kỳ tuần/tháng dùng timezone cửa hàng, đổi cửa sổ truy vấn sang UTC.

**Fallback:** không cấu hình provider → trả local ngay. Khi provider ném `AIProviderError`, `answer()` trả local và giữ nguyên card từ MySQL. LLM chỉ hỗ trợ diễn đạt; không sinh SQL để thực thi, không có quyền tự ghi tồn kho/hóa đơn. Tổng số và card được tính ở Python/SQL; văn bản provider vẫn có thể sai nên không tuyên bố LLM không bao giờ hallucinate.

**Chỉ test:** `tests/unit/test_assistant_query.py`; `tests/unit/test_phase3_automation.py` → `CatalogSQLTests`, `AssistantFallbackTests`; `tests/integration/test_mysql_web.py` → `test_phase_three_assistant_searches_beyond_preview_and_keeps_cards_on_api_failure()`.

## 3. Sales velocity và gợi ý nhập kho có giải thích

| Mở file | Hàm/class cần chỉ | Vai trò |
|---|---|---|
| [restock_repo.py](petcare/repositories/restock_repo.py) | `sales_inventory()` | LEFT JOIN danh mục với lượng bán; chỉ `paid`, chỉ product, lọc `paid_at` bằng cửa sổ `[start, end)`. |
| [restock_service.py](petcare/services/restock_service.py) | `estimate()`, `for_connection()`, `recommendations()` | Tính tốc độ/ngày tồn/mục tiêu/khuyến nghị; cửa sổ gồm hôm nay và 13 hoặc 29 ngày trước theo timezone tenant. |
| [restock.html](petcare/templates/partials/restock.html) | Partial gợi ý nhập kho | Trình bày số liệu đầu vào, lý do và công thức trên UI. |

Đặt `S14`, `S30` là **tổng số lượng sản phẩm** trên các hóa đơn đã thu trong từng cửa sổ, `Q` là tồn hiện tại, `R` là `reorder_level`:

```text
v14 = S14 / 14; v30 = S30 / 30
Chọn w = 14 nếu S14 > 0; nếu không, chọn 30 khi S30 > 0
v = Sw / w
Ngày tồn = Q / v                 (chưa có lịch sử → None)
Mục tiêu = max(R + 1, ceil(v × 14))
Gợi ý nhập = max(0, Mục tiêu − Q)
Cảnh báo khi Q ≤ R hoặc Ngày tồn ≤ 7
```

Nếu không có lịch sử cả hai kỳ, mục tiêu dùng `R + 1`, không chia cho 0 và không dựng tốc độ bán giả. Code tính `ceil(Sw × 14 / w)` bằng số nguyên `(Sw * 14 + w - 1) // w` để tránh sai số Decimal lặp làm nhập dư một đơn vị. Ví dụ Q=4, R=5, S14=1 → còn 56 ngày nhưng vẫn chạm ngưỡng, đề xuất nhập 2.

**Giới hạn cần nói đúng:** đây là heuristic theo lượng bán quan sát được; chưa dự báo mùa vụ, lượng cầu bị mất khi hết hàng hoặc lead time. Chỉ gợi ý đọc dữ liệu, không tự đặt mua/tăng tồn.

**Chỉ test:** `tests/unit/test_phase3_automation.py` → `RestockTests` (30 ngày, hàng mới, ceil, không âm); integration → `test_phase_three_paid_restock_and_frozen_report_export_reconcile()`.

## 4. Signed Snapshot: Excel khớp màn hình đang xem

| Mở file | Hàm/class cần chỉ | Vai trò |
|---|---|---|
| [report_service.py](petcare/services/report_service.py) | `report()`, `_report()`, `business_brief()` | Tính một bộ số liệu gồm tổng, chuỗi ngày, chi tiết, kỳ trước và thời điểm chốt; tiền dùng Decimal. |
| [report_export_service.py](petcare/services/report_export_service.py) | `_signer()`, `snapshot()`, `read_snapshot()`, `workbook_bytes()` | `URLSafeTimedSerializer`, salt `petcare-report-v1`, SECRET_KEY; hết hạn sau 900 giây; xuất XlsxWriter vào BytesIO. |
| [report_routes.py](petcare/routes/report_routes.py) | `index()`, `export_xlsx()` | Ký chính report đem render; POST export xác minh rồi xuất **report từ token**, không truy vấn lại số liệu. |
| [reports.js](petcare/static/js/reports.js) | Luồng export/in | Gửi snapshot/CSRF, khóa nút khi xuất và khôi phục; mở bảng chi tiết trước in. |

**Luồng:** `report → render + signed token → POST export → verify signature/time/actor/tenant → workbook_bytes(report)`. Decimal được tuần tự hóa thành chuỗi chính xác; khi xuất mới chuyển dạng phù hợp Excel. Số vượt khả năng 15 chữ số có nghĩa của Excel được ghi text để không âm thầm làm tròn. Tắt tự hiểu chuỗi là công thức/URL khi ghi workbook.

**Nói đúng “100%”:** file khớp số liệu đã chốt trên trang đó, kể cả có giao dịch mới sau khi mở trang. Muốn số mới phải tải lại báo cáo. Chữ ký bảo vệ tính toàn vẹn/xác thực, **không mã hóa** nội dung. Token bị sửa, hết hạn hoặc khác actor/tenant bị từ chối. Snapshot xuất báo cáo cũng khác snapshot tên/giá trong từng dòng hóa đơn.

**Chỉ test:** `tests/unit/test_phase3_automation.py` → `ReportAutomationTests.test_snapshot_scoped_tamper_and_expiry()`, `test_xlsx_reconciles_overview_daily_and_line_details_and_does_not_execute_text()`; integration sửa DB sau render rồi đối chiếu Excel trong `test_phase_three_paid_restock_and_frozen_report_export_reconcile()`.

## 5. Pillow, Descriptor và SimHash/LSH trong tìm ảnh

| Mở file | Hàm/class cần chỉ | Vai trò |
|---|---|---|
| [image_features.py](petcare/vision/image_features.py) | `ImageDescriptor`, `normalize_image_bytes()`, `describe_image()` | Dataclass bất biến/slots; kiểm ảnh, EXIF transpose, RGB/JPEG chuẩn hóa, HSV histogram 32 bins toàn ảnh + vùng giữa 60%, grayscale grid 16×16. |
| Cùng file | `_visual_hash()`, `visual_hash_bands()` | SimHash 64 bit từ projection cố định; chia 8 band × 8 bit để lập bucket LSH. |
| Cùng file | `compare_images()`, `compare_images_from_json()`, `similarity_components()` | Điểm descriptor đầy đủ: 0,78 màu + 0,22 cấu trúc; giải thích thành phần. |
| [pet_repo.py](petcare/repositories/pet_repo.py) | `replace_photo_search_index()`, `replace_photo_search_indexes()`, `find_available_image_search_candidates()` | Lưu/xóa bucket cùng transaction đổi ảnh; dò band bằng bucket đúng và 8 hàng xóm khác một bit. |
| Cùng file | `iter_available_for_image_search()`, `iter_filtered_for_image_search()` | Duyệt dữ liệu theo batch khi full scan hoặc có lọc loài/trạng thái. |
| [pet_image_service.py](petcare/services/pet_image_service.py) | `search_similar()`, `_metadata_score()`, `suggest_attributes()` | Chọn ứng viên, top-k bằng heapq, kết hợp ảnh/metadata, gợi ý thuộc tính có duyệt. |

**Điểm cuối:** khi có descriptor, `0,82 × điểm ảnh + 0,18 × điểm thuộc tính`, rồi đổi sang thang 100. Không có ảnh tham chiếu chỉ gợi ý metadata với trọng số bảo thủ; không tuyên bố đã so ảnh. Descriptor/hash là đặc trưng thủ công xác định, không phải mô hình deep learning đã huấn luyện.

**Phân biệt hai nhánh hiện hành:**

- Không đặt loài, trạng thái mặc định `available`: có thể dùng LSH để lấy ứng viên rồi xếp hạng bằng descriptor đầy đủ. Hash lỗi hoặc tập ứng viên vượt giới hạn thì fallback quét batch; descriptor legacy/thiếu hash được xét theo nhánh tương thích.
- Có loài hoặc trạng thái khác mặc định: quét **toàn bộ tập đã lọc** theo batch rồi xếp hạng, tránh lấy một preview LSH không phù hợp bộ lọc.

LSH là bước tìm gần đúng; không bảo đảm tìm mọi ảnh có điểm descriptor cao nhất. Với cách probe hiện tại, fingerprint Hamming ≤ 8 chắc chắn có ít nhất một band lệch ≤ 1 bit, nhưng độ gần Hamming không đồng nghĩa độ giống ngữ nghĩa. Điểm 100/100 với ảnh mẫu không chứng minh danh tính/giống hoặc xác suất đúng.

**Chỉ test:** `tests/unit/test_vision_search.py` (descriptor/hash/band/legacy); `tests/unit/test_pet_image_service.py`; `tests/unit/test_phase3_automation.py` → `ImageSuggestionTests`; `tests/integration/test_mysql_web.py` → `test_phase_three_image_filters_explanations_and_upload_suggestions_without_api()`. Công cụ reindex sẵn có: `petcare/vision/reindex_pet_descriptors.py::reindex_pet_descriptors()`; không cần chạy lại trong buổi vấn đáp.

## 10 câu hỏi khó và câu trả lời ngắn

1. **Python có GIL rồi, tại sao vẫn cần FOR UPDATE?**

   GIL không đồng bộ nhiều process/máy và không bảo vệ transaction MySQL. InnoDB khóa dòng trong `pay_invoice()` để mỗi người thu kiểm tra trạng thái/tồn mới nhất; UPDATE có điều kiện và kiểm rowcount là lớp bảo vệ bổ sung.

2. **Nếu lỗi sau khi đã trừ kho, hoặc người dùng bấm thanh toán hai lần?**

   Kho, pet, movement và trạng thái cùng transaction; exception làm rollback toàn bộ. Lần gọi thứ hai khóa lại hóa đơn, thấy `paid` và trả `already_paid`, không ghi nhận lần hai. Đây là tính idempotent của nghiệp vụ thu nội bộ, không phải bảo đảm cho cổng thanh toán bên ngoài.

3. **Tại sao dùng Decimal và lưu giá trong invoice_items?**

   `float` biểu diễn nhị phân có sai số; Python `Decimal` và MySQL DECIMAL phù hợp tiền. Dòng hóa đơn giữ snapshot tên/mã/giá nên sửa danh mục sau này không viết lại lịch sử. Tổng được tính phía server, không nhận tổng client làm nguồn tin cậy.

4. **Vì sao “Hôm nay còn mèo nào?” không bị hiểu là hỏi doanh thu?**

   `_question_intent()` phân loại chủ thể độc lập với `query_period()`. Từ doanh thu mới chọn nhánh revenue; pet dùng bộ lọc danh mục. `catalog_filters()` tiêu thụ cụm thời gian/giá trước khi lấy từ khóa, còn biên tiền dùng `PriceFilter`/Decimal.

5. **Không có Internet/API key thì chức năng AI có chết không? LLM có sửa database không?**

   Không có cấu hình thì dùng rule-based và SQL local ngay; lỗi provider được bọc `AIProviderError`, trả local cùng card. Đây là trợ lý tra cứu chỉ đọc; không thực thi SQL do LLM sinh hoặc cho LLM tự thu tiền/đổi tồn. Provider trực tuyến chưa được nghiệm thu thật khi chưa có endpoint; test dùng phản hồi/lỗi mô phỏng.

6. **Tại sao chọn 14 ngày, khi nào dùng 30 ngày? Hàng mới thì sao?**

   Ưu tiên 14 ngày nếu có bán gần đây; nếu không có, dùng 30 ngày khi còn lịch sử. Không có cả hai thì dùng ngưỡng R+1, ngày tồn là None. Đây là heuristic dễ giải thích, chưa tính mùa vụ, lead time hay cầu bị che do stockout; người quản lý quyết định nhập.

7. **Snapshot đã ký có giấu dữ liệu không? DB thay đổi thì Excel “100% khớp” nghĩa là gì?**

   Chữ ký không mã hóa: nó phát hiện sửa nội dung và ràng buộc actor/tenant, hạn 900 giây. Export dùng report đã ký nên khớp trang đã chốt, không phải số DB mới nhất sau đó. Refresh trang để lấy snapshot mới; login/CSRF vẫn kiểm riêng.

8. **Điểm ảnh 100 có phải đúng 100% đây là cùng một con mèo?**

   Không. Đó là điểm xếp hạng kết hợp histogram màu, grayscale grid và metadata; ảnh gần như giống nhau dễ có điểm cao. Thuật toán không nhận diện danh tính hoặc xác nhận trong ảnh có động vật; người dùng mở hồ sơ để đối chiếu.

9. **SimHash/LSH có bỏ sót không, tại sao không luôn so mọi ảnh?**

   LSH giảm số ứng viên ở danh mục lớn rồi dùng descriptor đầy đủ để xếp hạng; có thể bỏ sót ảnh ngoài tập ứng viên dù ảnh giống về ngữ nghĩa. Hash không hợp lệ/tập ứng viên quá rộng thì quét batch; khi có lọc loài/trạng thái code chủ động quét tập đã lọc. Không dùng kết quả benchmark tổng hợp để tuyên bố độ chính xác nhận diện.

10. **Staff sửa ID trên URL/JSON để xem cửa hàng khác thì sao? Bao nhiêu test đã chứng minh điều đó?**

    `require_actor()` xác minh membership và thiết lập tenant context; repository ràng buộc tenant và server kiểm quyền, không tin ID/role client gửi. Bộ nghiệm thu Phase 4 có 283 Python tests, gồm 57 integration trên MySQL riêng, cùng 19 JavaScript tests; có test tenant isolation và giao dịch cạnh tranh. Số test không phải độ bao phủ 100% hay cam kết an toàn production; cloud/SMTP/provider thật vẫn là phạm vi chưa nghiệm thu.

## Nhắc nhanh trước code freeze

- `petcare/i18n.py` hiện chỉ có một thay đổi có sẵn: `# pyrefly: ignore[missing-import]` trước import Flask. Comment cho type checker, không đổi runtime; đã giữ nguyên từng byte qua cả bốn Phase, không có conflict trong index.
- Module mới dùng `petcare/services/ui_text.py::ui_text()` và copy VI/EN tại chỗ để không ghi đè phần i18n đang làm dở. Unit/web locale hiện đạt; điều này không chứng minh mọi chuỗi trên mọi màn hình đã dịch hoàn toàn. Rà literal `t()` trong template còn **4 nhãn chưa có bản dịch English**: `Tồn kho` (`petcare/templates/products/detail.html`), `Gợi ý` (`petcare/templates/pets/search_image.html`), `Ngày` (`petcare/templates/partials/business_chart.html`), `Thêm` (`petcare/templates/partials/pos_card.html`). Chúng fallback về tiếng Việt, không làm lỗi luồng; ghi nhận thiếu sót giao diện, giữ nguyên code/i18n theo phạm vi đóng băng. Kiểm tra literal này không bao phủ toàn bộ chuỗi động.
- Lần rà soát tài liệu cuối chạy lại **171 unit + 55 web**, đều đạt; không sửa logic và không chạy lại integration vào DB dev. Bằng chứng toàn suite Phase 4: [ma trận nghiệm thu](docs/phase4_acceptance.md).
- Báo cáo, ảnh và Excel/PDF mẫu lịch sử nằm trong [docs/qa_reports](docs/qa_reports/README.md). Số liệu file mẫu là thời điểm nghiệm thu, không ép phải trùng dashboard sau khi làm mới ngày/tạo giao dịch.
- Lệnh đóng gói Git để **người dùng tự chạy**: [CODE_FREEZE_GIT_GUIDE.md](CODE_FREEZE_GIT_GUIDE.md). Tag Git bảo toàn code/tài liệu đã commit; không sao lưu MySQL, `.env`, ảnh upload hoặc key backup bị gitignore.
