# PetCare Manager — hướng dẫn kiến trúc và phát triển

PetCare Manager là ứng dụng web quản lý nhiều cửa hàng trên cùng nền tảng. Stack hiện hành là Python 3.11+, Flask, Jinja2, HTML/CSS/Vanilla JS và MySQL 8.0.16+ (InnoDB, utf8mb4). Dữ liệu nghiệp vụ được phân vùng theo `tenant_id`; role thuộc membership của từng cửa hàng. Không dùng Tkinter hoặc SQLite cho ứng dụng hiện hành.

## Phạm vi nghiệp vụ

- Khách hàng, hồ sơ từng cá thể thú cưng, sản phẩm có tồn kho, POS/hóa đơn, nhập hàng, hoàn tiền và báo cáo.
- Tìm thú cưng bằng ảnh và trợ lý cửa hàng có chế độ trả lời cục bộ; AI tạo sinh/Vision chỉ chạy khi endpoint được cấu hình.
- Không bao gồm khám bệnh, tiêm phòng, lịch hẹn chăm sóc, dịch vụ spa hoặc lượt dịch vụ. Đặc tả desktop cũ nằm trong `docs/archive/`.

## Cấu trúc và ranh giới module

- `petcare/app_factory.py`: composition root, tạo Flask app và đăng ký blueprint. `petcare/__init__.py` và `petcare/app.py` giữ export tương thích.
- `petcare/app_configuration.py`: kiểm tra cấu hình runtime/production và thiết lập giới hạn tiến trình.
- `petcare/app_hooks.py`: CSRF, tải phiên, locale, giới hạn xử lý ảnh, security headers, error handlers và Jinja helpers.
- `petcare/routes/`: xử lý HTTP, CSRF, render/redirect và gọi service; không đặt truy vấn nghiệp vụ trực tiếp trong route.
- `petcare/services/`: xác thực, quyền, quy tắc nghiệp vụ và transaction. Các service nhận tenant context rõ ràng; `services/actors.py` tải lại membership/role từ MySQL.
- `petcare/repositories/`: câu lệnh MySQL có tham số; repository không commit transaction.
- `petcare/database/`: kết nối/pool MySQL, schema, migration cộng thêm, preflight schema readiness, seed và công cụ vận hành.
- `petcare/templates/`: HTML/Jinja; `petcare/static/`: CSS và JavaScript thuần. Design tokens ở `static/css/tokens.css`; component/layout ở `app.css`; motion ở `motion.css`.
- `catalog_intent.py` và `assistant_local.py` tách nhận diện truy vấn/lọc danh mục khỏi renderer câu trả lời. `assistant_service.py` điều phối context và endpoint AI, đồng thời giữ các import facade tương thích.
- `tests/`: unit, web, JavaScript và integration test cần MySQL test database riêng.

## Luồng request và phân quyền

Route nhận request và bảo vệ thao tác ghi bằng POST + CSRF. Service xác thực actor và membership, áp dụng quy tắc nghiệp vụ rồi điều phối transaction. Repository chỉ thực hiện SQL đã tham số hóa; tenant scope không được lấy từ client làm căn cứ quyền. Authentication tải lại role/membership từ MySQL cho request hiện tại.

Các invariant cần giữ:

- Mọi đọc/ghi nghiệp vụ giới hạn đúng tenant; composite foreign keys cũng ngăn tham chiếu chéo tenant.
- Giá và tổng hóa đơn được xác nhận phía server bằng `Decimal`; hóa đơn giữ snapshot tiền tệ/tên/giá.
- Hóa đơn chưa thanh toán không trừ tồn. Thanh toán khóa dữ liệu, cập nhật tồn, movement và trạng thái thú cưng trong cùng transaction.
- Hoàn tiền ghi sổ điều chỉnh riêng và cập nhật kho/trạng thái theo disposition trong cùng transaction. Lỗi giữa luồng phải rollback toàn bộ.
- Repository không gọi `commit()`; service là nơi sở hữu commit/rollback.
- Không reset/xóa database đang dùng để phát triển. Migration thay đổi schema chỉ chạy chủ động sau khi sao lưu; test MySQL phải trỏ đến database riêng có hậu tố `_test`.

## Chạy local

1. Tạo virtual environment, cài `requirements.txt` cùng constraints `requirements.lock`, sao chép `.env.example` thành `.env` và đặt secret riêng.
2. Tạo database MySQL phát triển riêng, ví dụ `petcare_shop_dev`, với user ứng dụng có quyền đúng database.
3. Khởi tạo schema: `python -m petcare.database.initialize`.
4. Tạo dữ liệu demo tùy chọn: `python -m petcare.database.seed` (chỉ `_dev`/`_test`). Không dùng seed demo với dữ liệu thật.
5. Chạy web: `python run.py`; mở `http://127.0.0.1:5055`.
6. Chạy worker cần dùng trong terminal riêng: `python -m petcare.services.tenant_export_worker_cli`; thêm `python -m petcare.services.mail_worker` nếu cấu hình SMTP.

Thành viên mới nên làm theo hướng dẫn đầy đủ theo hệ điều hành, Docker, MySQL, backup/restore và biến môi trường trong `README.md`. Không đưa `.env`, credential, DB dump hoặc dữ liệu khách thật vào Git.

## Kiểm tra

```sh
python -m compileall -q run.py main.py petcare tests
python -m unittest discover -s tests -v
node --test tests/js/*.test.cjs
```

Kiểm thử tích hợp MySQL chỉ được tính khi cấu hình database `_test` cô lập và MySQL hoạt động. Không thay MySQL bằng SQLite/mock rồi kết luận đã nghiệm thu tích hợp thật.

## Skills và UI

Skills đã pin và hướng dẫn cách dùng nằm trong `.agents/skills/`, `skills-lock.json` và `docs/skills.md`. Skills là tài liệu hướng dẫn, không phải dependency chạy ứng dụng. Giữ Flask/Jinja/Vanilla JS/MySQL; không chép ví dụ đòi React, Tailwind hoặc SQLite vào runtime.

Design System ở `design-system/petcare-manager/MASTER.md`. Duy trì một bộ token ngữ nghĩa, dùng icon SVG hiện có, bảo đảm responsive/accessibility, không phụ thuộc CDN, và tôn trọng `prefers-reduced-motion`.
