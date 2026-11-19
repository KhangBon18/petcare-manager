# Yêu cầu Dữ liệu Định danh Cá thể Đa góc Chụp Thực tế — `AI-4.0d` / `AI-4.0e`

## 1. Kết quả Kiểm toán Dữ liệu Hiện có trong Kho Mã nguồn (`Phase 7 Audit`)

Trước khi đánh giá `AI-4.0d`, toàn bộ ảnh hiện có trong kho mã nguồn PetCare Manager đã được kiểm toán nguồn gốc cá thể:

| Nguồn dữ liệu trong repo | Số lượng tệp | Số ảnh độc lập / cá thể | Có xác minh nhiều góc chụp của cùng 1 cá thể thật? | Kết luận sử dụng |
| :--- | :---: | :---: | :---: | :--- |
| `seed_demo_store_data` (`PET-101` .. `PET-168`) | `68` ảnh | `1` ảnh/hồ sơ | **Không** (`1` ảnh chân dung duy nhất/cá thể) | Chỉ dùng đánh giá truy vấn `1` ảnh gốc, `Leave-One-Out` cùng loài, kiểm thử kỹ thuật lưu trữ kho ảnh |
| `tests/fixtures/vision_ai4/real_pack` (`Wikimedia Commons`) | `34` ảnh (`16` thú cưng đơn, `10` phi động vật, `4` đa thú, `4` loài khác) | `1` ảnh/tác giả độc lập | **Không** (không có bằng chứng 2 tệp Wikimedia chụp cùng 1 cá thể) | Chỉ dùng đánh giá nhận diện loài tự động, xếp hạng tương đồng ngoại hình cùng loài và từ chối ngoại lai |
| Biến thể cắt cúp / đổi độ sáng / nén JPEG (`make_near_duplicate_variant`) | Sinh tự động khi test | Biến đổi số học từ `1` ảnh gốc | **Không** (chỉ là biến thể biên tập của cùng 1 bức ảnh) | Chỉ dùng đo độ bền `Near-Duplicate` (`crop`/`resize`/`JPEG`), **tuyệt đối không tính là đa góc chụp cá thể** |

> **Trạng thái bắt buộc báo cáo trong `AI-4.0d`**:
> `same_pet_multi_view_reidentification = NOT_EVALUATED`
>
> Hệ thống kỹ thuật (`pet_reference_photos` tối đa `5` ảnh/cá thể + xếp hạng cấp hồ sơ thú cưng `calibrated_gallery_hybrid` + nhãn cảnh báo `"Potential matching pet — staff verification required"`) đã được triển khai đầy đủ, nhưng **không tuyên bố độ chính xác nhận diện cá thể thực tế (`Re-ID accuracy`)** cho đến khi thu thập xong bộ dữ liệu đa góc chụp có xác minh dưới đây.

---

## 2. Quy mô Mục tiêu của Bộ Dữ liệu Định danh Thực tế (`AI-4.0e Real Identity Pack`)

Để mở khóa phép đo `same_pet_multi_view_reidentification` hợp lệ về mặt khoa học mà không rò rỉ dữ liệu hiệu chỉnh/nghiệm thu:

| Nhóm mẫu bắt buộc | Số lượng tối thiểu | Số ảnh chụp độc lập / cá thể | Tổng số ảnh tối thiểu | Phân chia `calibration` / `acceptance_holdout` |
| :--- | :---: | :---: | :---: | :--- |
| **1. Cá thể Mèo có mặt trong kho (`Enrolled Cats`)** | `>= 12` cá thể thật | `3 – 5` ảnh độc lập | `>= 36` ảnh | `6` cá thể (`cal`) / `6` cá thể (`holdout`) |
| **2. Cá thể Chó có mặt trong kho (`Enrolled Dogs`)** | `>= 12` cá thể thật | `3 – 5` ảnh độc lập | `>= 36` ảnh | `6` cá thể (`cal`) / `6` cá thể (`holdout`) |
| **3. Thú cưng KHÔNG có trong kho (`Absent Open-Set Pets`)** | `>= 8` cá thể thật (`4` mèo, `4` chó) | `>= 2` ảnh độc lập | `>= 16` ảnh | `4` cá thể (`cal`) / `4` cá thể (`holdout`) |
| **4. Ảnh âm tính phi động vật & đa động vật (`Negatives`)** | `>= 16` cảnh chụp | `1` ảnh/cảnh | `>= 16` ảnh | `8` ảnh (`cal`) / `8` ảnh (`holdout`) |
| **Tổng cộng tối thiểu** | **`>= 32` cá thể thật + `16` âm tính** | — | **`>= 104` ảnh chụp thật** | Chia tách **100% theo `identity_id`** (không bao giờ chia ảnh của cùng 1 con sang cả 2 tập) |

### Các cặp đối kháng (`Hard-Negative Identities`) bắt buộc phải có trong `24` cá thể đăng ký
1. **Ít nhất `2` cá thể mèo lông cam/vàng khác nhau** (`cat_orange_id_A` và `cat_orange_id_B`) chụp trong bối cảnh ánh sáng trong nhà tương tự để kiểm chứng hệ thống không khẳng định nhầm danh tính chỉ vì trùng màu lông cam.
2. **Ít nhất `2` cá thể chó cùng giống** (ví dụ `2` Poodle nâu đỏ, `2` Corgi vàng trắng, hoặc `2` Golden Retriever khác chủ) để kiểm chứng ranh giới giữa tương đồng giống loài và cá thể.
3. **Ít nhất `2` cá thể lông trắng khác độ dài lông** (ví dụ lông ngắn sát vs lông xù dài) dưới cả ánh đèn vàng ấm trong nhà và ánh sáng tự nhiên gần cửa sổ.
4. **Ít nhất `4` cá thể có mảng lông đặc trưng bất đối xứng** (tam thể, nhị thể, đốm tai/mõm) chụp từ cả góc trái và góc phải.

---

## 3. Quy trình Chụp ảnh Thực địa cho Sinh viên (`Capture Protocol`)

Mỗi cá thể (`identity_id`) phải có ít nhất **`3` lần bấm máy độc lập** (khác thời điểm/góc máy thật, **cấm** dùng công cụ cắt ảnh từ 1 tấm gốc để giả làm ảnh thứ 2–3):

1. **Ảnh `#1` — `front_view` (Ảnh đại diện chính trong kho)**:
   - Góc chính diện mặt + ngực (`0° – 15°`), thú cưng nhìn về phía ống kính, khoảng cách `0.6m – 1.5m`, ánh sáng rõ.
2. **Ảnh `#2` — `side_view` (Ảnh tham chiếu phụ trong kho)**:
   - Góc nghiêng thân/đầu (`45° – 90°`) hoặc tư thế ngồi/đứng toàn thân để lộ tỷ lệ cơ thể và hoa văn lưng/sườn.
3. **Ảnh `#3` — `lighting_or_bg_query` (Ảnh truy vấn kiểm thử độc lập)**:
   - Chụp ở **phông nền khác** (ví dụ chuyển từ sàn gạch trắng sang thảm/ghế gỗ/sân cây) hoặc **nguồn sáng khác** (đèn phòng buổi tối vs ánh sáng ban ngày). Trong kịch bản đánh giá `2-photo gallery -> 1-photo query`, Ảnh `#1` và `#2` nạp vào `pet_reference_photos`, còn Ảnh `#3` đóng vai trò ảnh khách hàng tải lên `/pets/find-similar`.
4. **Ảnh `#4 – #5` *(khuyến khích)* — `coat_detail` / `lighting_variant`**:
   - Góc chụp từ trên xuống nhẹ hoặc cận cảnh vùng đầu–vai để kiểm thử hiệu quả khi kho ảnh tăng từ `2` lên `4` ảnh tham chiếu.

---

## 4. Quy ước Đặt tên Thư mục, Tệp ảnh & Lược đồ `manifest_v4_identities.json`

### Cấu trúc thư mục chuẩn
```text
tests/fixtures/vision_ai4/real_identities_v4/
├── manifest_v4_identities.json
├── enrolled/
│   ├── id_cat_01/
│   │   ├── p1_front_daylight.jpg
│   │   ├── p2_side_indoor.jpg
│   │   └── p3_query_warm_sofa.jpg
│   ├── id_cat_02/
│   └── id_dog_01/
├── absent_queries/
│   ├── id_absent_cat_01/
│   │   ├── q1_front.jpg
│   │   └── q2_side.jpg
│   └── id_absent_dog_01/
└── negatives/
    ├── neg_01_plush_toy.jpg
    └── neg_02_two_cats_frame.jpg
```

### Lược đồ JSON bắt buộc cho mỗi bản ghi ảnh trong `manifest_v4_identities.json`
```json
{
  "schema_version": 4,
  "identity_id": "id_cat_01",
  "species": "cat",
  "breed_or_type": "Mèo ta lông ngắn mướp cam",
  "coat_color": "vàng cam",
  "split": "acceptance_holdout",
  "catalog_enrollment": "enrolled",
  "verified_identity_source": "owner_confirmed_single_animal_session",
  "owner_consent_recorded": true,
  "photos": [
    {
      "photo_id": "id_cat_01_p1",
      "relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/id_cat_01/p1_front_daylight.jpg",
      "benchmark_role": "gallery_primary",
      "image_role": "front_view",
      "lighting": "natural_window",
      "background": "tile_floor",
      "independent_capture": true
    },
    {
      "photo_id": "id_cat_01_p2",
      "relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/id_cat_01/p2_side_indoor.jpg",
      "benchmark_role": "gallery_reference",
      "image_role": "side_view",
      "lighting": "white_led",
      "background": "wood_chair",
      "independent_capture": true
    },
    {
      "photo_id": "id_cat_01_p3",
      "relpath": "tests/fixtures/vision_ai4/real_identities_v4/enrolled/id_cat_01/p3_query_warm_sofa.jpg",
      "benchmark_role": "heldout_view_query",
      "image_role": "lighting_variant",
      "lighting": "warm_lamp",
      "background": "fabric_sofa",
      "independent_capture": true
    }
  ]
}
```

---

## 5. Quy tắc Bảo mật Riêng tư, Đạo đức & Chống Rò rỉ Nghiệm thu

1. **Quyền riêng tư & Xóa EXIF**: Chỉ chụp thú cưng tại cửa hàng thực tập, gia đình hoặc bạn bè khi đã được chủ nuôi đồng ý. Không để lọt khuôn mặt người, biển số xe, địa chỉ nhà, số điện thoại hoặc mã QR cá nhân vào khung hình. Chạy chuẩn hóa `normalize_image_bytes(...)` để loại bỏ hoàn toàn tọa độ GPS và siêu dữ liệu EXIF trước khi đưa vào Git (`<= 800px` cạnh dài, JPEG `q=85` để tổng dung lượng gói `< 12 MB`).
2. **Không tải ảnh lên đám mây bên ngoài**: Toàn bộ kiểm định loài, trích xuất embedding `1280-D` và đánh giá chạy **100% cục bộ bằng ONNX Runtime**.
3. **Luật chống rò rỉ dữ liệu (`Zero Identity Leakage`)**:
   - Mọi tham số trọng số hoặc ngưỡng gợi ý xác minh nhân viên chỉ được tinh chỉnh trên các `identity_id` thuộc `split = "calibration"`.
   - Tập `split = "acceptance_holdout"` chỉ được chạy đo kiểm đúng 1 lần để báo cáo kết quả độc lập.
   - Kể cả khi đạt `Top-1` cao trên tập `Real Identity Pack`, giao diện sản phẩm vẫn phải giữ nguyên nhãn **`"Potential matching pet — staff verification required"`** đối với mọi ảnh chụp mới chưa trùng khớp mã băm kho ảnh, vì ngoại hình tương đồng qua ảnh 2D không bao giờ thay thế bước đối chiếu trực tiếp của nhân viên cửa hàng.
