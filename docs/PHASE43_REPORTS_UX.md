# Sprint 4.3 — Reports UX

## Thay đổi

- Product report table giữ cho desktop; đến breakpoint mobile, cards hiện tên sản phẩm, quantity sold và revenue từ report result thật.
- Quick period đang chọn có style riêng và aria-current.
- Không đổi report query, date semantics, signed snapshot, currency hoặc POST /reports/export.xlsx.

## Browser verification

Chromium admin browser chạy thật trên app và MySQL QA. Tại 320/390/768/820/1024/1440 px document không overflow; browser xác nhận 7-day quick period, revenue/invoice count trùng report_service, sản phẩm/số lượng hiển thị đúng ở mobile card và card/table breakpoint chính xác. Custom date range được submit rồi kiểm tra lại URL/form. XLSX download có extension .xlsx và ZIP/OpenXML signature PK.

Ảnh: [trước 320](assets/phase43/before/reports-320.png), [sau 320](assets/phase43/after/reports-320.png), [sau desktop](assets/phase43/after/reports-1440.png).

## Tham khảo 3C

Shopify tách report PO khỏi màn xem/nhận hàng; Square gắn receiving với cập nhật inventory. Sprint áp dụng nguyên tắc làm số liệu/đơn vị dễ quét và trạng thái lọc rõ, với UI riêng cho Petcare Manager; không sao chép source hoặc asset.

- [Shopify: purchase order report](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/custom-reports/purchase-orders)
- [Shopify: view purchase orders](https://help.shopify.com/en/manual/inventory-and-locations/purchase-orders/viewing-purchase-orders)
- [Square: create purchase orders](https://squareup.com/help/us/en/article/8258-create-purchase-orders-with-square-for-retail)

PDF/print dialog, workbook cell contents beyond signature and large-catalog performance chưa được browser assert.
