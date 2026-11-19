# Preflight và phê duyệt migration `petcare_shop_dev`

Ngày kiểm tra: 2026-11-09. Quyết định hiện tại: **NO-GO — KHÔNG chạy migration**.

## Lý do quyết định

Schema và dữ liệu được kiểm tra lại chỉ bằng SELECT/metadata query; không chạy initializer, seed, DDL, DML, restore hoặc thao tác ghi vào `petcare_shop_dev`. Dev vẫn không đạt readiness. Không tìm thấy backup DB dev mới trong thư mục `backups/` của repository và không có đường dẫn/biên nhận backup đã restore thử được cung cấp. Việc không thấy file trong repository **không chứng minh** không có bản backup ở nơi khác; hiện chưa có bằng chứng đủ để xác nhận backup gần đây và khôi phục được.

Chuỗi migration đã được diễn tập trên clone của dev ở Phase 3. Điều đó không thay thế một backup snapshot gần đây của chính dev cùng một lượt restore thử có thể đối chiếu. Vì thiếu điều kiện đó và chưa được chủ dự án ủy quyền DDL, migration không được thực hiện.

## Preflight đọc-only hiện tại

Kết nối runtime đọc `petcare_shop_dev` trên MySQL 8.4.11:

| Hạng mục | Trạng thái quan sát |
|---|---|
| Base tables / columns | 20 bảng / 184 cột; source contract hiện hành yêu cầu 26 bảng. |
| Migration markers | Chỉ `datetime_storage_utc_v1`; thiếu `purchasing_orders_v1`, `invoice_refunds_v1`, `purchase_receipt_idempotency_v1`. |
| Bảng thiếu | `suppliers`, `purchase_orders`, `purchase_order_items`, `purchase_order_receipt_requests`, `invoice_refunds`, `invoice_refund_items`. |
| Cột thiếu trên `stock_movements` | `purchase_order_id`, `purchase_order_item_id`, `refund_id`, `refund_item_id`. |
| Index thiếu | `uq_invoice_items_tenant_invoice_id`, `idx_stock_purchase_order`, `idx_stock_purchase_order_item`, `idx_stock_refund`. |
| FK thiếu trong readiness contract | `fk_suppliers_tenant`; `fk_purchase_orders_tenant`, `fk_purchase_orders_supplier`, `fk_purchase_orders_creator`; ba FK `purchase_order_items`; hai FK `purchase_order_receipt_requests`; hai FK purchasing trên `stock_movements`; ba FK `invoice_refunds`; bốn FK `invoice_refund_items` — tổng cộng 18 named FKs. |
| FK đang có | 26/44 named FKs của readiness contract hiện tại đã tồn tại; so sánh actual ordered columns, referenced table/columns và `ON DELETE` với inline definitions trong `schema.sql` cho **0 mismatch**. |
| Money checks | Ba constraint có tên đang tồn tại nhưng biểu thức còn kiểm `unit_price_vnd`, `sale_price_vnd`, `line_total_vnd`; schema hiện hành cần kiểm `unit_price`, `sale_price`, `line_total`. |
| Data invariants đọc được | Số hàng vi phạm `products.unit_price >= 0`, `pets.sale_price >= 0` và `invoice_items.line_total = unit_price * quantity` đều bằng 0; số `tenant_id IS NULL` trên bảy bảng nghiệp vụ hiện có đều bằng 0. |
| Readiness | `schema_contract_is_ready=False`; Flask `GET /readyz` trả **503**. |
| Aggregate count tham chiếu | users 3, tenants 1, customers 14, products 22, pets 74, invoices 8, invoice_items 15, stock_movements 37. Đây là counts, không xuất dữ liệu cá nhân. |

Các số liệu hiện tại phù hợp drift đã biết trong [DB_READINESS_REMEDIATION.md](DB_READINESS_REMEDIATION.md): purchasing/refund/idempotency migrations chưa được áp dụng và các check cũ chưa được thay. Không phát hiện tenant NULL hay money rows vi phạm ở các kiểm tra read-only đã nêu. Điều đó chưa thay thế full backup/restore, kiểm tra mọi constraint hoặc xác nhận dữ liệu trước/sau migration.

Ngoài 18 FK trong readiness contract, initializer cũng thêm `fk_stock_tenant_refund_item` để ràng buộc refund stock movement với refund item; constraint này không nằm trong `REQUIRED_TENANT_FOREIGN_KEYS` nhưng là một phần DDL cần có trên schema hoàn chỉnh.

Điều kiện của `/readyz` là đủ cột trong `REQUIRED_COLUMNS`, đủ named tenant/global foreign keys và đủ cả bốn marker. Probe không kiểm tên index hay biểu thức CHECK; do đó readiness cần đi cùng so sánh DDL/index/data.

### Non-destructive validation

Các truy vấn dưới đây chỉ đọc metadata hoặc aggregate counts. Chạy bằng connection đã xác nhận đúng target; không chạy `initialize`, `seed`, `ALTER`, `UPDATE`, `INSERT` hoặc `DELETE` trong preflight:

```sql
SELECT DATABASE(), VERSION();
SELECT COUNT(*) FROM information_schema.tables
 WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE';
SELECT version FROM schema_migrations ORDER BY version;
SELECT COUNT(*) FROM products WHERE unit_price < 0;
SELECT COUNT(*) FROM pets WHERE sale_price < 0;
SELECT COUNT(*) FROM invoice_items
 WHERE line_total <> unit_price * quantity;
SELECT COUNT(*) FROM stock_movements WHERE tenant_id IS NULL;
```

So sánh table/column/index/FK/check names với `REQUIRED_COLUMNS`, `REQUIRED_TENANT_FOREIGN_KEYS`, `REQUIRED_GLOBAL_FOREIGN_KEYS`, `schema.sql`, `purchasing.sql` và `refunds.sql`; kiểm `/readyz` để quan sát kết quả contract. Cần lặp lại snapshot counts và invariants ngay trước migration sau khi backup được restore-test.

## Migration sequence và thay đổi dự kiến

Source sequence trong `initialize_database()` đã chạy trên clone ở Phase 3. Dev hiện có UTC marker nên migration sẽ bỏ qua chuyển đổi timestamp một lần đó. Chuỗi dự kiến, nếu được duyệt:

1. `schema.sql`: bảo đảm bảng nền; backfill Decimal money fields tương thích từ cột legacy `_vnd` khi cần.
2. Money checks: kiểm số dòng vi phạm trước bất kỳ `ALTER`; nếu hợp lệ, thay đúng ba named CHECK để bảo vệ cột Decimal hiện tại.
3. UTC marker: thấy `datetime_storage_utc_v1` hiện hữu nên không trừ thêm bảy giờ trên `DATETIME`.
4. Tenancy migration: chạy additive/idempotent backfill, kiểm `tenant_id` và membership theo source; hiện không có `tenant_id` NULL trong bảy bảng nghiệp vụ.
5. `purchasing.sql`: tạo suppliers/orders/items/receipt request ledger; thêm purchasing columns/indexes/FKs/check cho stock ledger; ghi `purchasing_orders_v1`.
6. Refund migration: thêm unique invoice-line index; tạo refund ledger/items; thêm refund stock columns/index/FK/check; ghi `invoice_refunds_v1`.
7. Ghi `purchase_receipt_idempotency_v1` sau khi request ledger tồn tại.

> **Phương thức đề xuất duy nhất sau khi được duyệt:** `python -m petcare.database.initialize`. Không chạy SQL thủ công thay initializer, không chạy `seed`, không drop database/table. Named CHECK thay đổi tương ứng là `ALTER TABLE ... DROP CHECK` + `ADD CONSTRAINT ... CHECK` trên ba bảng tiền; initializer chỉ thay khi biểu thức legacy khác canonical và dữ liệu vượt qua pre-check. Index/FK/table mới là additive.

## Backup/restore cần hoàn tất trước khi xin duyệt

Chỉ chạy từ host vận hành đã xác định đúng cấu hình dev. Lệnh xác nhận target không in user/password:

```sh
python -c 'from petcare.config import Config; print(Config.DB_NAME)'
# Tiếp tục chỉ khi output đúng: petcare_shop_dev
umask 077
mkdir -m 700 -p /secure/backups
python scripts/petcare_backup.py create \
  --output /secure/backups/petcare_shop_dev-before-phase35.pcarebackup \
  --media-source host
python scripts/petcare_backup.py verify \
  /secure/backups/petcare_shop_dev-before-phase35.pcarebackup
shasum -a 256 /secure/backups/petcare_shop_dev-before-phase35.pcarebackup
```

Backup tool yêu cầu passphrase qua prompt, bundle mã hóa, và backup cả database cùng local media. Lưu passphrase riêng khỏi bundle. Nếu media đang dùng S3, công cụ local backup dừng; cần backup DB và bucket theo provider, bao gồm versioning/encryption/access controls. Không đặt password/passphrase vào command line, log hoặc tài liệu.

Sau verify, giải mã/stage và restore vào **schema recovery mới** cùng media directory trống; không import đè dev. So sánh row counts/invariants, thử ứng dụng khôi phục và ghi lại timestamp, checksum, restore result. Theo [backup_restore.md](backup_restore.md), app backup tool không tự tạo database đích và không import dữ liệu. Bundle audit-host cũ `petcare_shop_test` (2026-10-18) không phải backup gần đây của dev và không thỏa điều kiện này.

## Permissions

- Read-only preflight cần quyền `SELECT` trên target và quyền đọc MySQL `information_schema`. Kết nối hiện tại có thể truy vấn metadata và các bảng nêu trên.
- User `petcare_app` hiện được cấp `ALL PRIVILEGES` trên `petcare_shop_dev`; **không có migration account riêng** trong cấu hình hiện tại (`MIGRATION_DB_USER` chưa cấu hình). Development initializer vì thế fallback về runtime connection. Trước khi thực hiện nên dùng account một lần, giới hạn vào đúng `petcare_shop_dev`.
- Quyền tối thiểu cho initializer theo SQL hiện hành: `SELECT`, `INSERT`, `UPDATE`, `CREATE`, `ALTER`, `INDEX`, `REFERENCES` trên đúng schema. Không cần `DROP DATABASE`; mọi `DROP CHECK`/legacy index là thao tác `ALTER TABLE`. Không cấp quyền trên production hoặc schema khác.
- Backup/read-only restore operator cần quyền đọc toàn bộ database. Với `mysqldump` fallback tham khảo, xác minh `SELECT`, `SHOW VIEW`, `TRIGGER`, `EVENT`, và `LOCK TABLES` nếu engine/options yêu cầu; không dùng quyền migration làm backup credential.

## Recovery và rủi ro

- MySQL DDL auto-commit; rollback helper không hoàn tác `CREATE`/`ALTER` đã commit. Nếu command dừng giữa chuỗi, dừng ghi nghiệp vụ, giữ nguyên trạng thái và chạy read-only schema/data diff để quyết định bước tiếp theo.
- Không có migration ngược bằng cách drop tables/columns. Recovery là restore bundle vào schema mới, đối chiếu dữ liệu và khởi chạy instance riêng; không restore đè lên `petcare_shop_dev`.
- UTC marker đã có là chốt an toàn để tránh dịch thời gian lần hai. Nếu marker mất/khác với dự kiến, dừng migration và xác minh nguồn gốc timestamp.
- FK/index/unique/check addition sẽ fail nếu có orphan/duplicate/invalid money data; clone rehearsal và counts hiện tại không xóa rủi ro drift sau thời điểm snapshot.

## Ranh giới phê duyệt

Trạng thái là **NO-GO** cho đến khi có đủ: (1) backup dev mới và checksum, (2) verify pass, (3) restore thử vào schema/media riêng và row counts/invariants khớp, (4) thời gian maintenance và dừng ghi xác nhận, (5) người sở hữu dự án xác nhận rõ cho phép chạy initializer trên `petcare_shop_dev`.

Khi các điều kiện đó đã được review, thao tác được xin duyệt sẽ chỉ là `python -m petcare.database.initialize` nhắm đúng database `petcare_shop_dev`, tiếp đó read-only kiểm 26 bảng, 4 marker, columns/indexes/FKs/checks và `/readyz=200`. Lượt này chưa nhận xác nhận đó và không thực hiện thao tác schema.
