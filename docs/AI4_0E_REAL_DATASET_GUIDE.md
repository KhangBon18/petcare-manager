# Hướng dẫn Tiếp nhận, Kiểm định & Đánh giá Bộ Dữ liệu Cá thể Thực tế — `AI-4.0e`

## 1. Mục đích & Trạng thái Hiện hành

Tài liệu này hướng dẫn quy trình tiếp nhận (`intake`), kiểm định chống giả mạo và chạy đánh giá tự động cho bộ dữ liệu định danh cá thể thú cưng nhiều góc chụp thực tế thông qua:
- Tệp kê khai: `tests/fixtures/vision_ai4/real_identities_v4/manifest_v4_identities.json`
- Bộ kiểm định & chấm điểm: `petcare/vision/ai4e_validation.py`
- Lệnh CLI: `python scripts/evaluate_ai4e_release_readiness.py`

> **Trạng thái kho dữ liệu hiện tại**:
> - `enrolled_multi_view_identities`: **`0 / 24` cá thể** -> Chỉ số `same_pet_independent_photo_reidentification` (`Recall@1`, `Recall@5`, `mAP`) được gắn cờ cứng **`MULTI_VIEW_IDENTITY_NOT_EVALUATED`**.
> - `absent_open_set_identities`: **`16` ảnh chụp độc lập thực tế** từ Wikimedia Commons (`8` mèo, `8` chó).
> - `real_negative_photographs`: **`18` ảnh chụp thực tế** (`10` phi động vật/thú bông, `4` khung hình đa động vật, `4` loài khác).

---

## 2. Yêu cầu Bắt buộc Trước Khi Tuyên bố Nhận diện Cá thể Đa Góc Chụp

Hệ thống **không được phép** quảng bá hoặc bật tuyên bố nhận diện cùng một cá thể (`Confirmed Same-Pet Recognition`) cho đến khi tập `enrolled_multi_view_identities` trong `manifest_v4_identities.json` đạt đủ các tiêu chuẩn sau:

1. **Quy mô tối thiểu (`Target Dataset`)**:
   - Ít nhất **`24` cá thể thú cưng thật đã xác minh** (`12` cá thể Mèo + `12` cá thể Chó).
   - Mỗi cá thể có ít nhất **`3` bức ảnh chụp độc lập** (`independent_capture = true`):
     - `1` ảnh `gallery_primary` (chính diện rõ mặt/ngực),
     - `1–4` ảnh `gallery_secondary` (góc nghiêng `45°–90°`, tư thế khác),
     - Ít nhất **`1` ảnh `query` KHÔNG đăng ký vào kho ảnh** (chụp ở phông nền hoặc điều kiện ánh sáng khác để làm truy vấn kiểm thử thực).
   - Ít nhất **`8` thú cưng thật không nằm trong kho** (`absent_open_set_identities`) và **`16` ảnh âm tính khó** (`real_negative_photographs`).
   - Nếu số lượng cá thể thật nằm trong khoảng `1..23`, bộ công cụ vẫn chấp nhận chạy thử nghiệm nhưng tự động gắn cờ **`PILOT_SAMPLE_SIZE_LIMITED`** kèm khoảng tin cậy `Wilson 95% CI` để cảnh báo cỡ mẫu nhỏ.

2. **Các hành vi bị bộ kiểm định `validate_real_identity_manifest` tự động chặn (`HARD FAIL`)**:
   - Chia ảnh của cùng một `identity_id` sang cả `calibration_identities` lẫn `acceptance_identities` (**rò rỉ cá thể**).
   - Thiếu ảnh truy vấn độc lập (`assignment = "query"`) chưa đăng ký trong kho.
   - Dùng lại cùng một tệp ảnh, ảnh lưu lại JPEG, ảnh đổi kích thước hoặc ảnh cắt cúp nhẹ từ 1 tấm gốc để giả làm góc chụp thứ 2–3 (bị chặn tự động bởi kiểm tra `raw_sha256`, `normalized_sha256` và khoảng cách Hamming `dHash <= 6 & pHash <= 8`).
   - Thiếu xác nhận quyền sử dụng / sự đồng ý của chủ nuôi (`owner_consent_or_open_license = true`).

---

## 3. Quy trình Từng Bước Bổ sung Ảnh Thực địa Mới

### Bước 1 — Chuẩn hóa riêng tư & loại bỏ EXIF/GPS
Đặt ảnh chụp thực địa (không chứa mặt người, biển số, số điện thoại, địa chỉ riêng tư) vào:
```text
tests/fixtures/vision_ai4/real_identities_v4/enrolled/<identity_id>/
```
Mọi thao tác xử lý chạy 100% cục bộ bằng Python/Pillow; **tuyệt đối không tải ảnh người dùng lên dịch vụ AI bên ngoài**.

### Bước 2 — Khai báo vào `manifest_v4_identities.json`
 Chia `50%` số cá thể vào `"calibration_identities"` (chỉ dùng để chọn ngưỡng) và `50%` số cá thể còn lại vào `"acceptance_identities"` (giữ nguyên để đo kiểm độc lập cuối cùng):

```json
{
  "identity_id": "vn_shop_cat_01",
  "display_name": "Miu Cam 01",
  "species": "cat",
  "breed": "Mèo ta lông ngắn",
  "coat_color": "vàng cam",
  "appearance_tags": "mướp cam, ngực trắng",
  "evaluation_split": "acceptance_identities",
  "photos": [
    {
      "photo_id": "vn_shop_cat_01_p1",
      "image_relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/vn_shop_cat_01/p1_front.jpg",
      "assignment": "gallery_primary",
      "source_and_usage_rights": {
        "source_kind": "student_field_capture",
        "license": "Academic-Evaluation-Consent",
        "owner_consent_or_open_license": true
      },
      "capture_session": {
        "session_id": "2026-11-20-morning-cage",
        "independent_capture": true
      }
    },
    {
      "photo_id": "vn_shop_cat_01_p2",
      "image_relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/vn_shop_cat_01/p2_side.jpg",
      "assignment": "gallery_secondary",
      "source_and_usage_rights": {
        "source_kind": "student_field_capture",
        "license": "Academic-Evaluation-Consent",
        "owner_consent_or_open_license": true
      },
      "capture_session": {
        "session_id": "2026-11-20-morning-table",
        "independent_capture": true
      }
    },
    {
      "photo_id": "vn_shop_cat_01_p3",
      "image_relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/vn_shop_cat_01/p3_query_evening.jpg",
      "assignment": "query",
      "source_and_usage_rights": {
        "source_kind": "student_field_capture",
        "license": "Academic-Evaluation-Consent",
        "owner_consent_or_open_license": true
      },
      "capture_session": {
        "session_id": "2026-11-20-evening-warm-lamp",
        "independent_capture": true
      }
    }
  ]
}
```

### Bước 3 — Chạy kiểm định tính hợp lệ & chống trùng lặp
```sh
.venv/bin/python scripts/evaluate_ai4e_release_readiness.py --validate-only
```
Lệnh trả mã thoát `0` khi không có lỗi rò rỉ tập dữ liệu, không thiếu tệp và không có ảnh cắt cúp giả mạo.

### Bước 4 — Chạy đánh giá toàn diện `CASE A` – `CASE J` & xuất báo cáo
```sh
env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u AI_API_KEY \
  .venv/bin/python scripts/evaluate_ai4e_release_readiness.py
```
Lệnh tự động cập nhật `docs/assets/vision-ai4/ai4_0e_final_evaluation.json` và `docs/AI4_0E_FINAL_VISION_QA.md` mà không cần sửa mã nguồn ứng dụng.
