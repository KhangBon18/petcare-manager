# Kế hoạch khắc phục DB readiness

Ngày: 2026-11-09
Trạng thái: **VERIFIED trên clone cô lập / `petcare_shop_dev` giữ nguyên và vẫn chờ phê duyệt trước DDL**

## Kết luận

`petcare_shop_dev` đang ở schema cũ hơn source hiện hành. Kết luận dựa trên migration markers, bảng/cột/index/FK/check constraints và kiểm tra dữ liệu tổng hợp; chênh lệch 20 bảng so với 26 bảng chỉ là một dấu hiệu phụ. `/readyz` của dev vẫn trả `503`. Phase 3 đã dump read-only nguồn vào schema `petcare_phase3_dev_clone` trên MySQL test cô lập, chạy initializer tại đó và xác minh readiness. Không chạy initializer, seed, DDL, DML, `DROP`, restore hay thao tác ghi nào trên `petcare_shop_dev`.

## Bằng chứng schema

- Kết nối read-only xác nhận MySQL 8.4.11, 20 bảng nền và marker duy nhất `datetime_storage_utc_v1`.
- Source hiện hành yêu cầu 26 bảng. Dev thiếu: `suppliers`, `purchase_orders`, `purchase_order_items`, `purchase_order_receipt_requests`, `invoice_refunds`, `invoice_refund_items`.
- `stock_movements` thiếu `purchase_order_id`, `purchase_order_item_id`, `refund_id`, `refund_item_id`. `invoice_items` thiếu unique index `uq_invoice_items_tenant_invoice_id`.
- Index migration thiếu trên `stock_movements`: `idx_stock_purchase_order`, `idx_stock_purchase_order_item`, `idx_stock_refund`. Các bảng chưa tồn tại nên toàn bộ index khai báo trong `purchasing.sql`/`refunds.sql` cũng chưa có.
- FK migration còn thiếu: `fk_suppliers_tenant`; `fk_purchase_orders_tenant`, `fk_purchase_orders_supplier`, `fk_purchase_orders_creator`; `fk_purchase_order_items_tenant`, `fk_purchase_order_items_order`, `fk_purchase_order_items_product`; `fk_stock_tenant_purchase_order`, `fk_stock_tenant_purchase_order_item`; `fk_invoice_refunds_tenant`, `fk_invoice_refunds_invoice`, `fk_invoice_refunds_creator`; `fk_invoice_refund_items_tenant`, `fk_invoice_refund_items_refund`, `fk_invoice_refund_items_invoice`, `fk_invoice_refund_items_invoice_line`; `fk_purchase_receipt_requests_tenant`, `fk_purchase_receipt_requests_order`.
- Marker `purchasing_orders_v1` và `invoice_refunds_v1` chưa có. `purchase_receipt_idempotency_v1` được bổ sung trong Phase 1.5 và hiện chưa có trong dev. Marker ngày giờ UTC đã có, nên initializer không được chạy lại phép trừ 7 giờ.
- Có 0 nhóm trùng theo `(tenant_id, invoice_id, id)`; 0 stock movements vi phạm invariant cũ; các phép đếm orphan tenant/customer/product/pet/invoice/item/actor đều bằng 0. Đây là kiểm tra tổng hợp, không đọc/ghi thông tin cá nhân.
- Rehearsal clone: trước migration có 20 bảng, 729 dòng tổng cộng và marker UTC duy nhất. Sau migration có 26 bảng, đủ bốn marker readiness; các dòng nghiệp vụ hiện có giữ nguyên, chỉ `schema_migrations` tăng từ 1 lên 4; sáu bảng mới rỗng. Các cột, FK và table constraints khớp schema mới. Hai khác biệt tên index hỗ trợ FK tự sinh của MySQL vẫn tồn tại nhưng không làm thay đổi cột khóa; ghi nhận để kiểm tra riêng khi triển khai.
- Clone ban đầu còn ba named CHECK constraint cùng tên nhưng biểu thức cũ tham chiếu cột `_vnd`, trong khi schema hiện hành phải bảo vệ `products.unit_price`, `pets.sale_price` và `invoice_items.line_total`. Trước khi thay constraint, số hàng vi phạm ba luật Decimal lần lượt là 0, 0, 0. Sau khi chạy initializer phiên bản hiện tại, biểu thức check khớp schema mới; thử ghi giá âm/tổng dòng sai bị MySQL từ chối.

## Điều kiện chính xác của `/readyz`

`schema_contract_is_ready()` trong `petcare/database/readiness.py` yêu cầu:

1. Có toàn bộ cột trong `REQUIRED_COLUMNS` trên 26 bảng.
2. Có mọi cặp `(table_name, constraint_name)` trong `REQUIRED_TENANT_FOREIGN_KEYS` và `REQUIRED_GLOBAL_FOREIGN_KEYS`.
3. Có đủ bốn marker: `datetime_storage_utc_v1`, `purchasing_orders_v1`, `invoice_refunds_v1`, `purchase_receipt_idempotency_v1`.

Probe kiểm tên FK, không đối chiếu cấu hình cột hay hành động `ON DELETE`; cũng không kiểm tên index. Vì vậy readiness cần được kết hợp với đối chiếu DDL/index và kiểm tra dữ liệu trước/sau migration.

## Nguyên nhân và chuỗi migration kỳ vọng

Nguyên nhân có thể xác minh: migration purchasing/refund chưa có trên DB dev. Clone còn giữ check tiền cũ vì `CREATE TABLE IF NOT EXISTS` không thay đổi constraint đã tồn tại; đây là drift bổ sung đã được sửa trong initializer. Lý do vận hành khiến migration trước chưa chạy không thể suy ra từ schema. Trình tự trong `initialize_database()` hiện tại (đã chạy lặp lại thành công trên clone):

1. `schema.sql` bảo đảm bảng nền tồn tại.
2. Thêm/backfill các cột tiền Decimal tương thích với dữ liệu legacy `_vnd`.
3. `_migrate_money_check_constraints()` đọc biểu thức từ `information_schema`, kiểm tra toàn bộ hàng hiện có trước mọi `ALTER`, rồi thay đúng ba constraint cũ nếu biểu thức chưa bảo vệ cột Decimal hiện tại. Hàm không dùng identifier từ request và không thay constraint đã canonical.
4. `migrate_datetime_storage_to_utc()` bỏ qua chuyển đổi khi marker `datetime_storage_utc_v1` đã hiện diện.
5. `migrate_tenancy()` chạy phần backfill/additive theo thiết kế idempotent.
6. `purchasing.sql` tạo supplier/order/items và request ledger; `_migrate_purchasing_stock_links()` bổ sung cột, index, FK và check trên stock movements; ghi `purchasing_orders_v1`.
7. `_migrate_invoice_refunds()` tạo refund ledger, unique index invoice item, cột/index/FK/check stock refund; ghi `invoice_refunds_v1`.
8. Ghi `purchase_receipt_idempotency_v1` sau khi bảng receipt request đã được tạo.

Phase 3 rehearsal dùng `mysqldump --single-transaction --routines --events --triggers --hex-blob --no-tablespaces --set-gtid-purged=OFF` và pipe trực tiếp vào database clone riêng, không ghi dump ra repository. Clone trước/sau migration được kiểm tra row counts, marker, schema contract và chạy initializer lần hai để xác nhận idempotency. Test hồi quy MySQL mô phỏng ba CHECK constraint `_vnd` cũ và xác nhận initializer thay chúng sau khi kiểm tra dữ liệu. Không dùng `petcare_shop_test` làm nơi diễn tập; không sửa `petcare_shop_dev`.

## Backup và xác nhận trước khi chạy

Chạy từ một máy vận hành đã được cấp quyền backup; `-p` yêu cầu nhập mật khẩu ẩn, không đặt mật khẩu vào command line hoặc tài liệu:

```sh
umask 077
mysqldump --host=127.0.0.1 --port=3306 --user=<backup_user> -p \
  --single-transaction --routines --triggers --events --hex-blob \
  --databases petcare_shop_dev \
  > /secure/backups/petcare_shop_dev-before-phase3.sql
shasum -a 256 /secure/backups/petcare_shop_dev-before-phase3.sql
```

Lưu bản sao đã mã hóa ở nơi tách biệt, xác minh checksum và diễn tập restore vào một schema recovery riêng trước khi chạm DB gốc. Trước khi chạy migration, xác nhận target chỉ in tên database (không in config/secret):

```sh
python -c 'from petcare.config import Config; print(Config.DB_NAME)'
```

Đảm bảo output là đúng `petcare_shop_dev`; dừng ghi nghiệp vụ trong thời gian DDL. Ghi snapshot counts của các bảng nền và các marker nêu trên trước khi chạy.

## Các bước áp dụng đề xuất — CHƯA THỰC HIỆN

Sau khi nhận **ủy quyền tường minh** cho DB dev và xác minh backup/recovery:

```sh
python -m petcare.database.initialize
```

Không chạy `seed`, không xóa/reset bảng, không chạy SQL thủ công thay cho initializer. Sau đó đọc lại bảng/cột/index/FK/check/markers, kiểm tra count và invariants, rồi xác nhận `/readyz` trả 200. So sánh số dòng dữ liệu nghiệp vụ trước/sau; bảng mới có thể có 0 dòng nếu chưa dùng tính năng.

SQL tham chiếu cho ba constraint mà initializer tự quản lý (không chạy thủ công thay migration):

```sql
ALTER TABLE products DROP CHECK chk_products_price;
ALTER TABLE products ADD CONSTRAINT chk_products_price CHECK (unit_price >= 0);
ALTER TABLE pets DROP CHECK chk_pets_price;
ALTER TABLE pets ADD CONSTRAINT chk_pets_price CHECK (sale_price >= 0);
ALTER TABLE invoice_items DROP CHECK chk_invoice_item_total;
ALTER TABLE invoice_items ADD CONSTRAINT chk_invoice_item_total
  CHECK (line_total = unit_price * quantity);
```

Initializer chỉ drop constraint cùng tên khi biểu thức khác chuẩn. Nó chạy đủ ba truy vấn kiểm tra dữ liệu trước ALTER đầu tiên; nếu dữ liệu vi phạm, migration dừng mà không bắt đầu thay check.

## Rủi ro và phục hồi

- MySQL DDL auto-commit; rollback của transaction helper không hoàn tác các `CREATE`/`ALTER` đã hoàn tất.
- Migration UTC sẽ thay đổi mọi giá trị `DATETIME` cũ nếu marker thiếu. Marker hiện có nên ngăn lần chuyển đổi thứ hai; phải dừng nếu marker hoặc nguồn gốc timestamp không khớp.
- Thêm FK/check/unique có thể dừng nếu dữ liệu vi phạm. Kiểm tra tổng hợp hiện không thấy orphan hoặc duplicate nhóm đã nêu, nhưng đây không thay thế snapshot và kiểm thử.
- `migrate_tenancy()` có đường backfill membership và thay đổi `tenant_id` NULL; cần rà lại số dòng NULL và membership trước khi chạy.
- Không chạy migration ngược bằng cách drop bảng/cột. Nếu trạng thái sau migration không đạt, dừng ghi; restore backup vào schema recovery mới, đối chiếu dữ liệu và chỉ chuyển ứng dụng sau quyết định vận hành. Không restore đè lên DB dev.

## Ranh giới phê duyệt

**Chưa được phép áp dụng kế hoạch lên `petcare_shop_dev` trong lượt này.** Clone rehearsal chứng minh chuỗi migration chạy được trên snapshot hiện tại, nhưng không thay thế backup/restore đã xác minh và không phải là phê duyệt DDL dev. Cần chủ dự án xác nhận rõ việc chạy `python -m petcare.database.initialize` trên `petcare_shop_dev` sau khi backup/restore được xác minh. Tới khi có xác nhận, DB dev giữ nguyên và `/readyz` tiếp tục trả `503`.
