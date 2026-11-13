# Nghiên cứu 3C và thay đổi UI/UX Petcare Manager

Ngày thực hiện: 2026-11-13. Nghiên cứu dựa trên các trang và tài liệu công khai
chính thức; không dùng màn hình sau đăng nhập hoặc tài sản thương hiệu của bên
thứ ba. “Copy” ở đây là học mẫu hình thao tác phổ biến, không sao chép mã hay bố
cục độc quyền.

## Ma trận đối chiếu

| Sản phẩm | Mẫu hình đã xác minh và nguồn | Petcare Manager hiện có | Khoảng trống | Điều chỉnh thực tế | Độ phức tạp | Giá trị |
|---|---|---|---|---|---|---|
| MoeGo | Danh sách khách gắn vật nuôi và hướng dẫn hồ sơ khách/vật nuôi. [Client & Pet List](https://www.moego.pet/help/en/articles/13171141-client-pet-list-overview), [Client Profile](https://www.moego.pet/help/en/articles/12691763-moego-client-profile-new) | Khách hàng và thú cưng đã có bảng/hồ sơ riêng, liên kết qua hóa đơn. | Khó quét nhanh trạng thái, ảnh thú cưng chưa được trình bày trọn vẹn. | Giữ các route riêng; đưa ảnh thú cưng vào vùng `contain`, tăng phân cấp mã/tên/trạng thái và liên kết ảnh tới hồ sơ. | Trung bình | Cao |
| MoeGo | Báo cáo Insights cho phép xem chỉ số, so sánh kỳ và thời điểm cập nhật. [Insights Overview](https://www.moego.pet/help/en/articles/14190547-moego-insights-overview), [How to Use Insights](https://www.moego.pet/help/en/articles/14191461-how-to-use-moego-insights) | Dashboard đã dùng doanh thu thanh toán thực và cảnh báo tồn. | Bộ lọc kỳ và nhãn trục/cập nhật chưa rõ. | Thêm bộ chọn kỳ hợp lệ, thời điểm chụp dữ liệu, đơn vị trục/legend và bảng dữ liệu truy cập được; số liệu vẫn đến từ `report_service`. | Trung bình | Cao |
| Shopify POS | Hồ sơ khách hàng gắn với lịch sử giao dịch trong trải nghiệm bán tại quầy. [Shopify POS customer management](https://help.shopify.com/en/manual/sell-in-person/shopify-pos/customer-management) | POS tạo hóa đơn và hỗ trợ tìm khách/sản phẩm; hồ sơ khách có lịch sử mua. | Trang trông như các form CRUD tách rời khỏi thao tác quầy. | Không đổi API/hành vi checkout; dùng mật độ thông tin gọn, hành động chính nổi bật và tóm tắt giỏ dễ thấy trên màn hình nhỏ. | Trung bình | Cao |
| Square | Dashboard nêu phân tích doanh số, xu hướng và chỉ số cửa hàng. [Square Dashboard Analytics](https://squareup.com/us/en/point-of-sale/features/dashboard/analytics) | Có doanh thu, số hóa đơn và trạng thái tồn thực. | Biểu đồ ít chú giải và không giải thích độ mới của số liệu. | Giữ doanh thu thực, biểu diễn trục/nhãn/legend, kỳ lọc và `captured_at`; không tạo KPI giả. | Thấp–trung bình | Cao |
| Square | Tài liệu Inventory hướng tới theo dõi số lượng và cảnh báo bổ sung. [Inventory with Retail POS](https://squareup.com/help/us/en/article/6110-manage-inventory-with-the-retail-pos-app) | Có tồn, reorder level, lịch sử nhập và restock cũ theo tốc độ ngắn. | Thiếu cửa sổ nhu cầu giải thích được và hàng đang về. | Dùng tám tuần bán thực trừ hoàn trả hàng về kho; trừ số lượng còn lại của PO mở trong đề xuất read-only. Không tạo PO tự động. | Trung bình–cao | Cao |
| Odoo Inventory | Replenishment và reordering rules hiển thị nhu cầu, tồn hiện có và hành động bổ sung. [Replenishment](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment.html), [Reordering Rules](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/product_management/product_replenishment/reordering_rules.html) | Trang restock từng tính từ tốc độ bán 14/30 ngày và reorder level. | Thiếu bằng chứng lịch sử, mức đủ dữ liệu và số PO đang mở; không có lead time nhà cung cấp. | Hiển thị công thức 8 tuần, dữ liệu đủ/ít/thưa, ngày tồn ước tính, PO đang về và cảnh báo rõ chưa có lead time. | Cao | Cao |
| Gingr | Mô hình hồ sơ owners và animals là các hồ sơ liên kết; có customer portal theo tài liệu. [Owners and Animals](https://support.gingrapp.com/hc/en-us/articles/31238139372813-What-Is-Owners-and-Animals), [Customer Portal Overview](https://support.gingrapp.com/hc/en-us/articles/28303758802189-Customer-Portal-Feature-Overview) | Đã có hồ sơ khách/thú cưng nội bộ và tenant access. | Ứng dụng này chưa có portal tự phục vụ khách; không thuộc mục tiêu thay đổi hiện tại. | Cải thiện luồng hồ sơ nhân viên hiện có và không giả lập portal mới. | Thấp | Trung bình |

## Kết quả 3C

- **Copy:** điều hướng có nhóm, hồ sơ khách/thú cưng dễ quét, bộ lọc báo cáo có kỳ
  rõ, tóm tắt POS, dữ liệu tồn và trạng thái cập nhật.
- **Customize:** các mẫu hình được ánh xạ vào Flask/Jinja, MySQL và CSS/JavaScript
  hiện hữu; mọi quyền và số liệu tiếp tục do service hiện tại xác định.
- **Create:** bản sắc riêng dùng nền xanh rừng/trung tính, biểu đồ có trục và chú
  giải, ảnh hồ sơ không cắt, tìm ảnh giải thích điểm, và dự báo tồn kho Python có
  công thức, nguồn dữ liệu cùng cảnh báo giới hạn.

## Thay đổi đã thực hiện

- Dùng tokens CSS và component chung hiện hữu; không thêm framework frontend.
- Chuyển bộ chọn ngôn ngữ sang header, gửi ngay khi đổi VI/EN, không cần nút Apply
  (giữ fallback không JavaScript); route vẫn POST và có CSRF.
- Tạo menu tài khoản gọn hiển thị tên/role, liên kết tới cài đặt tài khoản hiện có,
  và đăng xuất POST có CSRF. Escape đóng menu và trả focus về nút mở. Không tạo
  trang cài đặt không được hỗ trợ.
- Thú cưng dùng `object-fit: contain` trong media box có tỷ lệ xác định; ảnh gốc
  không bị ghi đè/biến dạng. Card và hồ sơ có fallback ảnh lỗi; ảnh mở được hồ sơ.
- Dashboard có kỳ `today`, `7d`, `30d`, `month`, trục số liệu, legend và thời điểm
  chụp dữ liệu. Giá trị tiếp tục đến từ dịch vụ báo cáo hiện có.
- Trang tìm ảnh hiển thị ảnh truy vấn cạnh hồ sơ xếp hạng đầu; phần giải thích
  phân biệt điểm xếp hạng nội bộ với xác suất/nhận diện.
- Restock hiển thị nhu cầu theo tuần, độ đủ lịch sử, tồn hiện có, hàng đang nhập,
  ngày tồn và giới hạn lead time.

## Bằng chứng browser và ảnh trước/sau

Ảnh được chụp từ Chromium chạy ứng dụng Flask và MySQL QA với tài khoản admin,
dữ liệu seed tổng hợp. Bản chụp không đại diện cho dữ liệu cửa hàng thật.

| Màn hình | Trước | Sau |
|---|---|---|
| Dashboard, ngôn ngữ/điều khiển tài khoản | [dashboard trước](assets/python-first-v2/before/dashboard-1440.jpg) | [dashboard sau](assets/python-first-v2/after/dashboard-1440.png) |
| Danh sách thú cưng | [ảnh trước](assets/python-first-v2/before/pets-1440.jpg) | [ảnh sau](assets/python-first-v2/after/pets-1440.png) |
| Tìm thú cưng bằng ảnh | [ảnh trước](assets/python-first-v2/before/image-search-1440.jpg) | [ảnh sau](assets/python-first-v2/after/image-search-1440.png) |
| Bố cục thú cưng ở màn nhỏ | [390 px trước](assets/python-first-v2/before/pets-390.jpg) | [320 px](assets/python-first-v2/after/pets-320.png), [390 px](assets/python-first-v2/after/pets-390.png), [768 px](assets/python-first-v2/after/pets-768.png), [1024 px](assets/python-first-v2/after/pets-1024.png) |
| Kết quả truy vấn mẫu | — | [ảnh chó](assets/python-first-v2/after/image-search-dog-1440.png), [ảnh mèo](assets/python-first-v2/after/image-search-cat-1440.png) |

Luồng browser xác nhận menu tài khoản thao tác bằng bàn phím, locale trực tiếp
VI/EN được giữ qua điều hướng và các ảnh query/candidate tải thành công. Với
ảnh catalog, phép đo DOM từng ghi nhận ảnh cao 335 px trong vùng 205 px; sau khi
đặt ảnh vào media box có kích thước xác định, test kiểm tra phần tử ảnh bằng đúng
kích thước khung và screenshot cho thấy toàn bộ khuôn mặt/mõm trong ảnh mèo/chó.

## Kỹ năng local đã áp dụng

Trong kho có 18 tài liệu `SKILL.md` thuộc 5 skill package cấp cao. Đã đọc và dùng
`frontend-design`, `web-design-guidelines`, `playwright-cli` và `ui-ux-pro-max`
cùng tham chiếu design system tương ứng để giữ Jinja/CSS hiện tại, kiểm tra tên
điều khiển bàn phím, responsive, và xác minh qua browser. `book-to-skill` cùng
slide/banner/brand subskills không áp dụng cho công việc này. Skill chỉ là hướng
dẫn; code, số liệu và kết quả trong báo cáo được kiểm chứng riêng.

## Giới hạn bằng chứng

Nghiên cứu đối thủ chỉ xác minh các mô tả/tài liệu chính thức tại URL đã dẫn, không
đánh giá tài khoản demo, giá gói hay mọi màn hình trả phí. Ảnh trước/sau trong
`docs/assets/python-first-v2/` là dữ liệu tổng hợp cục bộ. Hành vi ở các trình
duyệt không cài được cần được ghi riêng; Chromium không thay thế thử nghiệm Safari
hoặc Firefox.
