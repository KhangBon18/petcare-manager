# Sprint 4.3 — Operations / tenant export UX

## Thay đổi

Trang /users/export/jobs/<id> có metadata thời điểm tạo, số lần thử và expiry khi phù hợp; trạng thái khởi tạo cung cấp aria-busy. Ba error code hiện hành — requester_access_revoked, passphrase_unavailable, export_job_expired — có hướng dẫn riêng. Polling/status/download API không đổi.

## Browser verification

Admin gửi export bằng passphrase QA ngẫu nhiên trên isolated schema. Browser assert pending và nút download ẩn; worker CLI của ứng dụng chạy one-shot với job id fixture; DB xác nhận ready, artifact_size dương, expiry có giá trị, passphrase ciphertext đã được xóa. Trang polling cập nhật, browser tải .pcarexport và đối chiếu kích thước file với DB. Cleanup xóa đúng fixture/artifact QA.

Pending và ready được mở tại 320/390/768/820/1024/1440 px và assert document width bằng viewport. Ảnh đại diện: [pending 320](assets/phase43/after/operations-export-pending-320.png), [pending 1440](assets/phase43/after/operations-export-pending-1440.png), [ready 320](assets/phase43/after/operations-export-ready-320.png), [ready 1440](assets/phase43/after/operations-export-ready-1440.png).

## Ranh giới kiểm thử

Chỉ local isolated storage và worker one-shot; SMTP/S3/daemon không được gọi. File mã hóa được tải nhưng không giải mã trong sprint. Shopify/Square public docs dùng làm tham khảo về trạng thái hàng hóa và nhận hàng; không có tuyên bố đã truy cập dashboard private.

- [Shopify: receiving inventory](https://help.shopify.com/en/manual/inventory-and-locations/purchase-orders/receiving-inventory)
- [Square: manage inventory](https://squareup.com/help/us/en/article/6110-manage-inventory-with-the-retail-pos-app)
