# Danh mục Kiểm tra Sẵn sàng Phát hành (`Release Readiness Checklist`) — `AI-4.0`

## 1. Phạm vi Sản phẩm Được Phê duyệt Phát hành (`Approved Release Scope`)

- [x] **Được phép phát hành chính thức (`GO`)** dưới dạng tính năng:
  1. **Tự động phát hiện thú cưng đơn lẻ & nhận diện loài Mèo / Chó cục bộ** (`YOLOX-Nano` + `MobileNetV2-12` trên `onnxruntime`, không gửi ảnh ra ngoài).
  2. **Quản lý kho ảnh tham chiếu đã xác minh** tối đa `5` ảnh/cá thể (`pets.photo_filename` + `pet_reference_photos`).
  3. **Đối sánh chính xác ảnh đã lưu kho** (`SHA-256` & `near-duplicate` đã hiệu chỉnh, `Rank-1 = 100.0%`, `FP = 0`).
  4. **Gợi ý xếp hạng thú cưng cùng loài có ngoại hình tương tự** (`1280-D` foreground embedding + biểu đồ màu lông `CIE-Lab` cân bằng trắng) để nhân viên cửa hàng mở hồ sơ đối chiếu.
- [x] **KHÔNG quảng bá nhận diện danh tính cá thể tự động (`NO-GO for Identity Confirmation Claims`)**:
  - Đã kiểm tra `README.md`, `search_image.html`, `detail.html` và tài liệu báo cáo: không có bất kỳ câu chữ nào tuyên bố nhận diện chính xác cùng một con vật từ ảnh mới chưa lưu kho.
  - Mọi ứng viên khác tệp ảnh lưu kho chỉ mang nhãn `visually_similar_pet` hoặc `potential_same_pet_candidate` (`"Potential matching pet — staff verification required"`, điểm trần `<= 89`).
  - Chỉ số `same_pet_multi_view_reidentification` được công bố minh bạch là **`MULTI_VIEW_IDENTITY_NOT_EVALUATED`**.

---

## 2. Kiểm tra Cơ sở Dữ liệu, Di trú & Đa Cửa hàng (`Database & Tenancy Gates`)

- [x] Di trú `pet_reference_photos` cộng thêm (`additive`), chạy lặp lại an toàn (`idempotent`) trên MySQL 8.x, giữ nguyên `27` bảng hợp đồng `/readyz` và không đụng chạm dữ liệu thú cưng `1` ảnh hiện có.
- [x] Khóa ngoại kép `(tenant_id, pet_id) -> pets(tenant_id, id) ON DELETE CASCADE` và `(tenant_id) -> tenants(id) ON DELETE RESTRICT` ngăn rò rỉ dữ liệu chéo cửa hàng ở tầng RDBMS.
- [x] Giao dịch lỗi giữa chừng hoặc ảnh vi phạm kiểm định loài đều tự động xóa tệp vừa ghi (`0` tệp mồ côi trên đĩa).
- [x] Xuất dữ liệu mã hóa cửa hàng (`export_tenant.py`) đóng gói đầy đủ `pet_reference_photos.csv` và tệp ảnh tham chiếu phụ; tác vụ dọn dẹp cửa hàng hết hạn (`tenant_cleanup_repo.py`) kiểm tra đầy đủ bảng mới.
- [x] Không thay đổi cơ sở dữ liệu sản xuất hoặc `petcare_shop_dev`; toàn bộ kiểm thử chạy trên schema dùng một lần `*_test` và dọn sạch sau khi hoàn tất.

---

## 3. Kiểm tra Mô hình ONNX, Hiệu năng & Cờ Quay lui (`Runtime & Rollback Gates`)

- [x] Xác thực khớp tuyệt đối mã băm `SHA-256` của cả 3 tệp mô hình trong `petcare/vision/models/MODEL_MANIFEST.json`:
  - `yolox_nano.onnx` (`3,659,407` bytes · Apache-2.0)
  - `mobilenetv2-12.onnx` (`13,964,571` bytes · Apache-2.0)
  - `mobilenetv2-12-features.onnx` (`13,964,674` bytes · Apache-2.0)
- [x] Bộ nhớ mô hình đang chạy chỉ **`16.87 MB`**, độ trễ tìm kiếm toàn trình trên CPU đạt `p50 ~ 66–81 ms`, `p95 < 130 ms` ngay cả khi kho có `3–5` ảnh/cá thể.
- [x] Cờ cấu hình quay lui tức thời không cần sửa DB:
  - `AI_FOREGROUND_EMBEDDING_ENABLED=0` -> quay lui về xếp hạng histogram + màu lông `AI-4.0b`.
  - `AI_LOCAL_SPECIES_GATE_ENABLED=0` -> quay lui về chế độ yêu cầu lọc loài thủ công `AI-4.0a`.
  - `AI_VISION_ENABLED=0` & `AI_PROVIDER_APPROVED=0` -> mặc định tắt hoàn toàn gọi AI bên ngoài trên môi trường sản xuất.

---

## 4. Kiểm tra Tự động, Giao diện, Khả năng Tiếp cận & Bảo mật (`CI Gates`)

- [x] **Python + MySQL (`unittest discover -s tests`)**: `100%` PASS (unit, web, MySQL integration).
- [x] **JavaScript (`node --test tests/js/*.test.cjs`)**: `100%` PASS.
- [x] **Chromium Playwright E2E (`scripts/browser_smoke/run_smoke.py`)**: `100%` PASS trên cả desktop `1440x960` và di động `390x844` (`scrollWidth == 390`), `0` vi phạm `axe-core` WCAG 2.1 AA nghiêm trọng/tới hạn.
- [x] **Bảo mật phụ thuộc & mã nguồn**: `pip check` sạch, `pip-audit -r requirements.lock` `0` CVE, `bandit` `0` cảnh báo mới, `docker compose config --quiet` hợp lệ, quét secret trên `git diff` `0` phát hiện.
- [x] **Bảo toàn bản phát hành học thuật `AI-3.4`**: Nhánh `solo/khang-petcare` (`7514b472a5d9251fe26f70441cc68e0995cd6ed3`) và tệp `petcare-manager-final-submission.zip` (`SHA-256 = ecc3bf9b...de83e3`) nguyên vẹn tuyệt đối.

---

## 5. Quy trình Đẩy Nhánh & Mở Pull Request (Khi Chủ Dự án Quyết định)

1. Kiểm tra lại trạng thái nhánh sạch: `git status -sb` trên `feature/ai-4.0-pet-image-matching`.
2. Đẩy nhánh tính năng lên GitHub: `git push -u origin feature/ai-4.0-pet-image-matching`.
3. Xác nhận cả 4 luồng công việc trong `.github/workflows/ci.yml` (`verify` Python 3.11–3.13, `browser-smoke`, `source-security`, `container`) đều xanh trên GitHub Actions trước khi mở/gộp Pull Request.
