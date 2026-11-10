# Handoff cho frontend/UI agent

## Chạy local an toàn

1. Cài Python 3.11+ bằng bộ versions đã khóa:

   ```sh
   python -m pip install -r requirements.txt -c requirements.lock
   ```

2. Đảm bảo MySQL 8.0.16+ có một schema cô lập kết thúc `_test`, với user chỉ có quyền trên schema đó. Đặt `DB_NAME` và `PETCARE_TEST_DB_NAME` cùng tên; không dùng `petcare_shop_dev` hoặc `petcare_shop_test` cho browser/test data. Cấu hình thư mục ảnh/export vào `/tmp` hoặc volume test riêng.
3. Chỉ trên schema `_test`, chạy `python -m petcare.database.initialize`, sau đó seed demo theo hướng dẫn `REPO_GUIDE.md`/`README.md`.
4. Chạy `python run.py`; app bind localhost port 5055 theo mặc định. Mở `http://127.0.0.1:5055`. Không cần framework frontend build.

Trong checkout hiện tại `.env` trỏ tới `petcare_shop_dev`; cần override `DB_NAME` sang schema `_test` trước khi chạy web. Development database hiện `/readyz=503`; không chạy initializer trên DB đó khi làm frontend audit.

## Roles và quyền

- `owner`: chủ cửa hàng; quyền quản trị theo tenant và các luồng ownership có re-auth.
- `admin`: quản trị viên cửa hàng; quản lý catalog, nhập hàng, thành viên, báo cáo và dữ liệu tenant.
- `staff`: thao tác tác nghiệp được cho phép trong tenant; không vào purchasing/user admin/refund-admin.

Role và membership được tải lại từ MySQL mỗi request; không lấy role từ form/client. Dữ liệu demo có tài khoản seed cho admin/staff, nhưng handoff này không chép mật khẩu/credential.

## Routes/modules để duyệt

- Auth/account: `/login`, `/signup` (tắt mặc định), `/account/settings`, email verify/reset.
- Home: `/dashboard`.
- Khách hàng: `/customers/` và detail/create/edit.
- Catalog: `/products/`, `/pets/`, hồ sơ, ảnh riêng tư và tìm ảnh local.
- POS: `/invoices/new`, lookup customer/product/pet, invoice detail/pay/cancel/refund.
- Nhập hàng (owner/admin): `/purchasing/`, `/purchasing/new`, suppliers, order detail/receive/cancel.
- Reports: `/reports/` và XLSX export.
- Assistant: `/assistant/chat` (local-first; provider ngoài chỉ bật khi cấu hình).
- Tenant/account admin: `/store/settings`, `/users/`, invitations, ownership, export, `/activity/`.
- Probes: `/healthz`, `/readyz`, `/workersz`; metrics `/metrics` tắt nếu không có token.

Blueprint, role access và JSON/form contracts đầy đủ nằm trong [`docs/API_CONTRACT.md`](API_CONTRACT.md). Handoff này ưu tiên visual/browser walkthrough; không đổi endpoint, method, payload, status code, CSRF behavior hoặc hidden purchasing `receipt_request_key`.

## Browser-accessible features và giới hạn hiện tại

App dùng Flask/Jinja, CSS local và vanilla JS. Không có frontend bundler hoặc ORM. Trạng thái form write thường là flash + redirect; API JSON có error status riêng. Ảnh/media mặc định lưu local private storage; có thể cấu hình S3.

Login/locale đã được quan sát trực tiếp trước đây. Authenticated page flows mới chỉ có evidence từ Flask test client và MySQL integration. Chưa có walkthrough browser cho mọi template, viewport phone/tablet, keyboard-only, screen reader, contrast, focus order, console errors hoặc failed network request. External SMTP/AI/AI Vision/S3 chưa được thử thật. Docker image build đã pass; container runtime và Trivy scan chưa được xác minh.

## Hợp đồng không được làm vỡ

- Session authenticated là tenant-scoped; POST cần CSRF; user không được đổi role bằng client input.
- JSON response và routes giữ theo [`docs/API_CONTRACT.md`](API_CONTRACT.md).
- Khi hiển thị purchase receive form, giữ hidden `receipt_request_key` do trang chi tiết sinh và gửi kèm CSRF. Một lần retry phải giữ đúng UUID và payload; lần giao hàng mới phải dùng key mới.
- Không lấy tổng tiền/tồn kho từ DOM làm nguồn chuẩn; server revalidate và transaction cập nhật DB.
- Giữ same-origin static assets; login/authenticated responses dùng `no-store`.

## Technical limitations

Dev schema có 20 bảng và `/readyz=503`; expected source schema sau migration hiện là 26 bảng. Migration run trên dev cần backup và xác nhận. Test data phải dùng `_test` schema; app test config không nên reuse real customer data. Docker image build đã pass; Trivy, container runtime, authenticated browser accessibility, SMTP, remote AI, AI Vision và S3 còn chưa kiểm chứng.
