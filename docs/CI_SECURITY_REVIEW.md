# Rà soát CI và cảnh báo Bandit

Ngày: 2026-11-09

Trạng thái: **VERIFIED — đúng lệnh Bandit của CI exit 0**

## Kết quả

Gate được chạy đúng như `.github/workflows/ci.yml`:

```sh
bandit -q -r petcare scripts main.py run.py wsgi.py \
  -x petcare/templates,petcare/static \
  -b .security/bandit-baseline.json
```

Bandit 1.9.4 exit `0`. Các cảnh báo B608 mới được giới hạn bằng `# nosec B608` ở đúng câu SQL đã rà soát; không sửa baseline và không tắt rule toàn cục. Bandit vẫn in các cảnh báo thông tin cho suppression B608 đã có trong repository.

## Đánh giá từng vị trí

| Vị trí | Cấu trúc SQL | Nguồn identifier | Giá trị | Đánh giá |
|---|---|---|---|---|
| `petcare/database/readiness.py` — truy vấn `information_schema.columns` | Số lượng `%s` được dựng từ số phần tử của `REQUIRED_COLUMNS` | Tên bảng/cột lấy từ mapping hằng số trong module | Tên bảng gửi qua bind parameters | False positive B608; không thấy input người dùng ảnh hưởng SQL structure. |
| `petcare/database/readiness.py` — truy vấn `information_schema.table_constraints` | Số lượng `%s` được dựng từ số phần tử của hợp hai set FK hằng số | Tên constraint lấy từ các set hằng số | Tên constraint gửi qua bind parameters | False positive B608; không thấy input người dùng ảnh hưởng SQL structure. |
| `petcare/repositories/tenant_cleanup_repo.py` — đếm bản ghi trống theo tenant | Table name được đặt trong identifier quote | Chỉ lấy từ `_EMPTY_TENANT_TABLES`, tuple literal nằm trong module | `tenant_id` truyền riêng bằng `%s` | False positive B608; table list đóng và không nhận request/config/database input. |

Các chỗ trên không dùng placeholder cho identifier vì MySQL bind parameters chỉ áp dụng cho value. Validation đúng ranh giới là đóng nguồn identifier trong literal/set hằng số; dữ liệu tenant tiếp tục là bind parameter. Suppression hẹp ghi cạnh câu lệnh, kèm lý do ngay phía trên. Không thêm blanket exclusion.

`# nosec B608` không thay kiểm tra source: review xác nhận tuple/mapping không được mutate từ input và code chỉ tạo placeholder count. Nếu sau này nguồn tên bảng/constraint được mở rộng ra cấu hình hoặc request, phải bỏ suppression và thiết kế lại query.

## Dependency gate

`requirements.lock` chứa bộ runtime exact-version. `pip-audit -r requirements.lock` trả `No known vulnerabilities found` trong lần kiểm tra hiện tại. Đây là kết quả theo advisory database tại thời điểm chạy, không bảo đảm cho bản nâng cấp tương lai.

## Giới hạn CI

Lệnh Bandit cục bộ là gate cụ thể đã được yêu cầu và đã pass. `docker build --tag petcare-manager-web:phase15 .` cũng thành công trên Docker Desktop (linux/arm64, base Python 3.12). Không chạy toàn GitHub Actions workflow; Trivy CLI/action không có trong môi trường nên filesystem/image/secret scan của CI chưa được xác minh. Xem `docs/TEST_MATRIX.md` cho trạng thái từng bước.
