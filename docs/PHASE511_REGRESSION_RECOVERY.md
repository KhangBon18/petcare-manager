# Phase 5.1.1 — Khôi phục regression baseline

Ngày: 2026-11-10. Phạm vi là ổn định test harness sau Phase 5.1; không thay business logic của ứng dụng và chưa triển khai Vision.

## Bảo vệ repository và dữ liệu

- Trước khi sửa, branch `solo/khang-petcare` ở HEAD `8634300f4b5ad4700d6702a048220d6597c4e200`; working tree đã có 104 file tracked thay đổi và 993 đường dẫn untracked. Không có staged changes.
- Checkpoint Phase 5.1 cũ được kiểm tra checksum PASS. Trước khi sửa, tạo checkpoint mới tại `/Users/heisenbon/Documents/Codex/petcare-phase511-checkpoint-20261110`; HEAD, branch, status, tracked/staged diff, danh sách/tar untracked đều có SHA-256 xác minh PASS.
- Không reset, clean, stash, stage hoặc commit. Test chạy trong bản sao repo ở `/tmp` và MySQL 8.4 test service riêng trên tmpfs. Không sửa `petcare_shop_dev`, production hoặc schema QA dùng chung.

## Chẩn đoán lần regression trước

Run trước Phase 5.1.1 đã ghi nhận 380 test với 2 failures và 15 errors trên schema QA có dữ liệu tồn lưu. Full trace cũ không còn trong repository hoặc thư mục artifact; vì vậy bảng dưới ghi test name và root cause được xác nhận qua fixture/code path, không giả lập lại nguyên văn exception.

| Kiểm tra trước đó | Phân loại | Nguyên nhân được xác định | Thay đổi |
|---|---|---|---|
| `test_cli_prepares_real_mysql_with_live_readiness_under_five_seconds_and_no_repayment` | B/C — fixture thiếu tenant context | Test tạo invoice trực tiếp bằng `admin_id` mà không truyền tenant. Trên schema QA cũ, admin có nhiều membership; `require_actor()` từ chối fallback mơ hồ. | Truyền tenant `main` tường minh khi tạo và thanh toán invoice. |
| 10 test trong `MySQLSalesIntegrationTests` | B/C — fixture thiếu tenant context | `setUp()` tạo customer bằng service trực tiếp mà không truyền tenant nên toàn bộ test có thể dừng trước thân test khi admin có nhiều membership. Các helper/service calls khác cũng bỏ tenant. | Lấy `tenant_id` một lần, truyền rõ qua helper và mọi service call trực tiếp. |
| `test_invoice_detail_and_payment_route_work`, `test_stock_adjustment_is_recorded_atomically`, `test_phase_three_paid_restock_and_frozen_report_export_reconcile`, `test_phase_three_image_filters_explanations_and_upload_suggestions_without_api` | B/C — fixture thiếu tenant context | Các test gọi service trực tiếp bên ngoài request đã xác thực; không có tenant trong request context để chọn store. | Chọn customer/product theo tenant và truyền `tenant_id` trực tiếp. |
| `test_assistant_returns_current_shop_context_for_authenticated_user` | E — expectation cứng không bền vững | Test yêu cầu `catalog.total == 22`; dữ liệu QA cũ có 23 sản phẩm active trong tenant. Đây là sai khác giữa fixture count và dữ liệu thật, không phải bằng chứng assistant trả sai. | So sánh với số active product được query trong cùng tenant tại thời điểm test. |
| `test_phase_two_seed_refreshes_only_demo_dates_and_repairs_missing_photos` | C — truy vấn fixture không cô lập | Query lấy invoice demo không lọc `tenant_id`, có thể chọn bản ghi cũ/tenant khác rồi kiểm tra ngày mà seed `main` không sở hữu. | Query theo tenant `main`, thêm thứ tự và giới hạn để chọn record ổn định. |
| Full browser run trước đó: 11 test, 6 failures, 1 error | C/D/F — data/storage và harness | Báo cáo Phase 5.1 nêu ảnh được tham chiếu trong DB không có trong storage sạch, actor fixture đa tenant, export job pending và selector mới quá rộng. Trace per-test không còn để xác nhận chính xác từng lỗi; không kết luận app defect từ lần chạy đó. | Chạy toàn bộ browser suite với DB + media/export storage đều mới; selector top-products đã sửa từ Phase 5.1 và được chạy lại trong cả suite. |

Root cause chung của 15 error được corroborate bằng test code và guard `require_actor()`: các test dùng user seed `admin` ngoài request không cung cấp tenant, trong khi QA dùng chung đã có membership phụ. Ngoại lệ xử lý rõ là các test cross-tenant vốn cần truyền tenant để kiểm tra quyền. Không có bằng chứng cho lỗi trong business logic ứng dụng.

## Test-isolation defects được sửa

- MySQL integration fixtures truyền tenant cụ thể vào các service call trực tiếp; route tests vẫn kiểm tra tenant lấy từ session.
- Catalog assertion tính expected count từ dữ liệu active hiện có trong tenant thay vì hằng số `22`.
- Seed-date test chỉ chọn invoice thuộc tenant `main`.
- Sales `tearDown` xóa đúng audit events của invoice/refund/product/pet/customer do test tạo.
- Product stock-adjustment và pet photo integration cleanup xóa audit events/index rows trước khi xóa record test-owned.
- Hậu kiểm sau suite xác nhận 0 orphan audit events cho customer/product/pet/invoice/refund và 0 record còn lại ở các prefix sales/browser đã kiểm.
- Thêm `compose.qa-test.yml`: MySQL 8.4, chỉ bind vào loopback, schema riêng, dữ liệu trong tmpfs; app user chỉ được khởi tạo trong schema test. Không dùng volume của Compose development.

Không sửa code sản phẩm hoặc API contract trong Phase 5.1.1.

## Kết quả tái lập

Trên schema MySQL tạm mới, sau các thay đổi trên:

- `python -m unittest discover -s tests -v`: **380/380 PASS**, không failure/error/skip; chạy lặp lại hai lần (**43.662s**, **39.691s**).
- Unit: **228/228 PASS**; web: **86/86 PASS**; MySQL integration: **66/66 PASS**.
- Bộ AI sales insight: **8 passed, 13 subtests passed**.
- JavaScript: **31/31 PASS**.
- Full Playwright: **11/11 PASS** hai lần. `/readyz=200`; mỗi lượt không có page exception, failed request hay HTTP error ngoài các status dự kiến. Console có một thông báo 403 dự kiến trong test staff bị chặn `/users/`; không phải JavaScript exception.

Lệnh, thời lượng, artifact path và quality gates được ghi trong [kết quả cuối](PHASE511_FINAL_TEST_RESULTS.md). Hướng dẫn dựng môi trường nằm ở [QA_TEST_ISOLATION.md](QA_TEST_ISOLATION.md).

## Giới hạn

Kết quả xanh chứng minh suite chạy ổn trên schema và storage dùng một lần, không chứng minh schema phát triển đã sẵn sàng. `petcare_shop_dev` readiness còn 503, không được kết nối hoặc sửa trong sprint. GitHub-hosted CI chưa được quan sát.
