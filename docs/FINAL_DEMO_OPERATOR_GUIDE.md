# Hướng dẫn operator — demo lớp học

Phạm vi: demo local với dữ liệu tổng hợp trong MySQL `_test` tạm thời. Không dùng database dev hoặc production. Launcher bind các dịch vụ web/mocks vào loopback và tự tạo project/credentials nội bộ.

## A. Chuẩn bị trước buổi học

### Yêu cầu máy

- Docker Engine và Docker Compose plugin đã cài, Docker Desktop đang chạy.
- Python 3.11 trở lên; release này đã chạy trên Python 3.13.
- Kết nối Internet khi cài dependencies hoặc kéo image lần đầu. Nếu dự kiến offline, cài packages và cache MySQL image trước.
- Browser hiện đại. Không cần Node hoặc Playwright để mở ứng dụng bằng tay; các gói browser chỉ cần cho automated rehearsal/a11y.
- Có quyền mở port localhost do launcher chọn. Không chạy launcher nhiều lần song song.

### Cài dependencies từ checkout

```sh
python3 -m venv /tmp/petcare-demo-venv
. /tmp/petcare-demo-venv/bin/activate
python -m pip install -r requirements.txt -c requirements.lock -r requirements-browser.lock
```

Nếu chỉ chạy UI thủ công, browser automation không cần khởi cài. Để chạy kiểm thử Playwright/axe, cài thêm browser binaries và npm package đúng lockfile theo README:

```sh
python -m playwright install chromium firefox webkit
npm ci --prefix tests/a11y
```

Nên chạy các lệnh cài đặt trước ngày trình bày để phát hiện mạng chậm, thiếu dung lượng hoặc image chưa có cache.

## B. Khởi động an toàn

1. Đảm bảo Docker Desktop đã hiện trạng thái running.
2. Mở terminal tại root repository; activate virtualenv có dependencies.
3. Chạy:

   ```sh
   scripts/demo/classroom.sh --target qa
   ```

4. Nhập hai mật khẩu riêng, tối thiểu 16 ký tự, tại prompt ẩn. Không chụp màn hình, ghi vào slide, shell history, log hoặc tài liệu. Không dùng mật khẩu tài khoản cá nhân.
5. Chờ launcher báo `QA demo ready at http://127.0.0.1:<port>`. Chỉ mở địa chỉ loopback được launcher in ra.
6. Mở lần lượt các health checks trong browser hoặc terminal. Mỗi endpoint phải trả HTTP 200:

   ```sh
   printf "Port printed by the launcher: "
   read -r DEMO_PORT
   curl -i "http://127.0.0.1:${DEMO_PORT}/healthz"
   curl -i "http://127.0.0.1:${DEMO_PORT}/readyz"
   curl -i "http://127.0.0.1:${DEMO_PORT}/workersz"
   ```

Nhập port thực tế launcher vừa in; port được chọn tự động, không mặc định là 5055. `/healthz` kiểm tra tiến trình web; `/readyz` kiểm tra schema database; `/workersz` kiểm tra heartbeat worker bắt buộc. Không bắt đầu demo nếu `/readyz` hoặc `/workersz` không 200.

### Tài khoản và quyền

- Store ID/slug: `main`.
- Username `admin`: tài khoản demo có membership `owner`; application ánh xạ membership owner thành quyền admin cho các màn hình nghiệp vụ. QA seed không tạo thêm một membership `admin` riêng.
- Username `staff1`: membership `staff`; có thể đọc quy trình cửa hàng được phép, nhưng trang quản trị `/users/` phải từ chối với HTTP 403.
- Hai mật khẩu lấy từ prompt operator vừa nhập; không có mật khẩu mặc định.

## C. Kịch bản trình bày 8–12 phút

Mở [kịch bản chi tiết và câu hỏi](FINAL_DEFENSE_PREPARATION.md) trước buổi demo. Bản tóm tắt thao tác:

1. Dashboard: nêu bài toán, Flask/Jinja/MySQL, tenant và synthetic data.
2. Customers → tạo khách hàng thử nghiệm. Pets → tạo hồ sơ thú cưng, giải thích trạng thái available.
3. Products → tạo SKU và supplier; ban đầu stock bằng 0.
4. Purchasing → tạo purchase order 8 đơn vị. Xác nhận tạo order chưa tăng stock; nhận 3 rồi 5 để thấy partial/full receiving và stock ledger.
5. POS/Invoices → lập hóa đơn với sản phẩm + thú cưng, thanh toán mô phỏng; kiểm tra tồn sản phẩm giảm và thú cưng gắn người mua.
6. Invoice detail → hoàn một đơn vị theo disposition resell; kiểm tra refund ledger và tồn được cộng lại. Không có tiền chuyển qua cổng thanh toán.
7. Reports → đối chiếu doanh thu, refund và inventory.
8. Users → Export data; nhập xác thực/passphrase tạm theo UI, chờ worker, tải bundle mã hóa.
9. Dashboard → Assistant → “Bán chạy tuần này”; nói rõ đây là truy vấn/rule local trên tenant data trong demo.
10. Pets → Vision suggestions; xem và apply gợi ý mock, chỉ lưu khi operator chủ động submit form.
11. Đăng xuất, đăng nhập staff1; mở Customers, sau đó `/users/` để minh họa giới hạn quyền.
12. Kết luận về test evidence và những tích hợp chưa bật.

Các con số 8→3→8, hóa đơn/refund minh họa trong [demo script](ACADEMIC_DEMO_SCRIPT.md) là từ fixture đã nghiệm thu. Nếu operator thay đổi dữ liệu, đối chiếu trạng thái và ledger thực tế thay vì học thuộc số.

## D. Những bước cần người trình bày xác nhận

Tự động hóa không thể đảm bảo điều kiện tại phòng học/máy giảng viên. Operator tự đánh dấu:

- [ ] Docker Desktop đã khởi động trên đúng máy; không có port conflict hoặc thiếu dung lượng.
- [ ] Các password demo được nhập kín và khác nhau; không được hiển thị trong terminal khi gõ.
- [ ] Trang login thực tế mở trên browser/máy chiếu; tài khoản admin vào dashboard.
- [ ] Tạo/nhận hàng/bán/hoàn tiền đều dùng tên và dữ liệu giả; không nhập PII thật.
- [ ] Xem file export được tải đúng vị trí; giữ nó trong vùng tạm, không đưa vào submission nếu chứa dữ liệu phiên demo.
- [ ] Nêu rõ payment không chuyển tiền, AI assistant không phải bằng chứng model quality, Vision hiện là mock.
- [ ] Demo đã được người nói diễn tập có lời dẫn; 17.76 giây ở tài liệu trước là thời gian browser automation, không phải thời lượng thuyết trình 8–12 phút.
- [ ] Nếu accessibility là yêu cầu chấm điểm: dùng browser thật đặt zoom 200%, duyệt luồng trọng yếu bằng keyboard và VoiceOver/NVDA thực, ghi nhận lại. Các bước này chưa được reviewer xác minh ở Phase 6.4.
- [ ] Kiểm tra mạng hoặc xác nhận image/dependencies đã cache trước buổi offline.

## E. Reset và shutdown

- Nhập `r` tại prompt `petcare-demo>` để launcher dừng đúng project QA của phiên này, tạo lại tmpfs schema và nạp lại synthetic seed. Mọi dữ liệu đã nhập trong phiên QA sẽ mất.
- Nhập `q` để dừng workers/web và xóa project Docker + storage tạm được launcher đánh dấu. `Ctrl-C` cũng gọi cleanup.
- Không dùng `docker compose down -v`, SQL DROP, reset script khác hoặc lệnh seed thủ công để “sửa demo”. Launcher đã tự giới hạn cleanup vào project được tạo.
- Sau shutdown có thể xác nhận container/network theo project launcher đã dừng và URL health không còn phản hồi. Không chạy lệnh dọn chung tác động tới những container khác.

### Kết quả xác minh Phase 6.4

Trên checkout/commit ghi ở status report, launcher QA khởi chạy thành công. Trước và sau thao tác `r`, `/healthz=200`, `/readyz=200`, `/workersz=200`. Thao tác `q` kết thúc exit code 0; container, network, app process và thư mục storage của chính phiên QA được launcher tạo đã biến mất. Không truy cập hoặc sửa `petcare_shop_dev` hay production.

## F. Phương án dự phòng

- Nếu Docker/MySQL không healthy: dừng live demo ở đó, không chuyển sang schema dev. Dùng sơ đồ/ảnh trong `docs/assets/phase62/` và giải thích rằng live database bị BLOCKED.
- Nếu `/workersz` không healthy: bỏ phần export; không giả vờ rằng worker đã xử lý xong.
- Nếu Vision mock lỗi: bỏ thao tác, giải thích fixed mock/review-only; không bật provider thật.
- Nếu thời gian ngắn: dùng bản 3–5 phút ở `docs/ACADEMIC_DEMO_SCRIPT.md`; ưu tiên PO → receiving → POS → report → assistant/Vision disclaimer → staff permission.
- Nếu browser automation lỗi nhưng app vẫn mở: có thể tiếp tục UI thủ công; không tuyên bố test tự động vừa chạy.
