# Quy tắc Tài chính & Hóa đơn (billing_rules.md)

Tài liệu này xác định các quy tắc nghiệp vụ tài chính, hóa đơn và bảo toàn doanh thu trong PetCare Manager.

---

## 1. Đơn vị Tiền tệ & Định dạng

- **Đơn vị lưu trữ**: Số nguyên (`INTEGER`) theo Việt Nam Đồng (VND).
- Tuyệt đối không dùng kiểu số thực (`REAL` / `FLOAT`) cho giá dịch vụ hoặc tổng tiền hóa đơn nhằm tránh sai số dấu phẩy động trong quá trình tính toán.
- Ràng buộc: `price_vnd >= 0` và `amount_vnd >= 0`.
- Hiển thị trên giao diện: Định dạng phân tách phần nghìn bằng dấu chấm và thêm hậu tố `đ` (ví dụ: `150.000 đ`).

---

## 2. Quy tắc Lượt dịch vụ (Service Visits)

1. **Khám bệnh & Tiêm phòng**:
   - Khi bác sĩ tạo ca khám hoặc ghi nhận mũi tiêm, hệ thống tự động ghi nhận một bản ghi `service_visits` trong cùng một transaction.
   - Giá của lượt dịch vụ được sao chép (snapshot) từ giá hiện tại của dịch vụ trong danh mục.
2. **Lịch hẹn**:
   - Lịch hẹn khám hoặc chăm sóc spa chỉ lưu kế hoạch tiếp đón và **tuyệt đối không tạo lượt dịch vụ hoặc phát sinh chi phí**.
3. **Dịch vụ Chăm sóc / Spa / Xét nghiệm**:
   - Có thể được nhân viên ghi nhận trực tiếp qua chức năng Lượt dịch vụ khi khách hàng đưa thú cưng đến tắm, cắt móng, làm đẹp mà không cần lập hồ sơ bệnh án.
4. **Bảo toàn Giá lịch sử**:
   - Nếu Quản trị viên thay đổi giá dịch vụ trong danh mục (ví dụ từ 150.000 đ lên 200.000 đ), giá của các lượt dịch vụ đã diễn ra trong quá khứ không bị thay đổi.

---

## 3. Quy tắc Lập Hóa đơn (Invoice Creation)

1. **Tính tiền Một lần (Single-Billing Invariant)**:
   - Mỗi lượt dịch vụ chỉ được xuất hiện trên đúng một hóa đơn.
   - Ràng buộc `visit_id UNIQUE` trong bảng `invoice_items` và kiểm tra logic tại `InvoiceService` đảm bảo không bao giờ xảy ra tính tiền trùng lặp.
2. **Quy tắc Cùng Chủ sở hữu**:
   - Một hóa đơn có thể gộp nhiều lượt dịch vụ của nhiều thú cưng khác nhau, nhưng **tất cả thú cưng đó phải thuộc về cùng một chủ nuôi**. Cố tình đưa lượt dịch vụ của chủ khác vào hóa đơn sẽ bị từ chối ngay tại tầng Service.
3. **Ảnh chụp Thông tin (Snapshotting)**:
   - Khi tạo hóa đơn, các thông tin: tên dịch vụ (`service_name_snapshot`), tên thú cưng (`pet_name_snapshot`) và số tiền (`amount_vnd`) được lưu cố định vào `invoice_items`.
   - Tổng tiền hóa đơn được tính động bằng `SUM(amount_vnd)` từ các dòng chi tiết, đảm bảo không có sự mâu thuẫn giữa tổng tiền và chi tiết.

---

## 4. Quy tắc Thanh toán Trực tiếp (Direct Payment)

1. **Tính chất Bất biến của Hóa đơn đã thanh toán**:
   - Hóa đơn sau khi được thanh toán sẽ chuyển trạng thái sang `paid` và lưu thời điểm `paid_at`.
   - Hóa đơn `paid` trở thành bất biến: Không thể chỉnh sửa, không thể thêm bớt dòng chi tiết và không thể hủy.
2. **Thanh toán lặp (Idempotent Payment)**:
   - Nếu gọi thanh toán cho một hóa đơn đã ở trạng thái `paid`, hệ thống trả về kết quả `already_paid` mà không ghi nhận thêm tiền hoặc thay đổi thời điểm thanh toán.
3. **Hóa đơn đã hủy**:
   - Hóa đơn ở trạng thái `cancelled` không thể được thanh toán.

---

## 5. Quy tắc Hủy Hóa đơn (Invoice Cancellation)

1. **Hủy hóa đơn chưa thanh toán (`unpaid`)**:
   - Chỉ cho phép hủy hóa đơn có trạng thái `unpaid`.
   - Khi hủy: Hệ thống xóa toàn bộ các dòng chi tiết trong `invoice_items` để **giải phóng các `visit_id`**, giúp các lượt dịch vụ này có thể được lập vào hóa đơn mới nếu cần.
   - Bản ghi hóa đơn trong `invoices` được cập nhật trạng thái `cancelled` để phục vụ tra cứu và kiểm toán lịch sử.
2. **Cấm hủy hóa đơn đã thanh toán (`paid`)**:
   - Nhằm bảo toàn số liệu kế toán và doanh thu, mọi yêu cầu hủy hóa đơn `paid` đều bị chặn với thông báo lỗi rõ ràng.

---

## 6. Quy tắc Thống kê Doanh thu (Revenue Reporting)

1. **Doanh thu thực thu**:
   - Doanh thu chỉ được ghi nhận từ các hóa đơn có trạng thái `paid`.
   - Hóa đơn `unpaid` (chưa trả tiền) và `cancelled` (đã hủy) tuyệt đối không được cộng vào doanh thu.
2. **Kỳ báo cáo theo `paid_at`**:
   - Doanh thu được phân bổ theo ngày thực tế thanh toán `paid_at`, không tính theo ngày thực hiện dịch vụ hay ngày tạo hóa đơn tạm.
3. **Ranh giới Thời gian Toàn vẹn**:
   - Khi truy vấn doanh thu từ `start_date` đến `end_date`, hệ thống lấy từ `start_dateT00:00:00` đến trước `00:00:00` của ngày tiếp theo ngày kết thúc (tức bao gồm trọn vẹn 23:59:59 của ngày kết thúc).
