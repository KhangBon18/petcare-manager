# Kiểm kê Dữ liệu Ảnh & Kế hoạch Bộ Dữ liệu Chuẩn cho AI-4.0 (`docs/AI4_IMAGE_DATASET_PLAN.md`)

Tài liệu này kiểm kê chính xác toàn bộ tài nguyên hình ảnh và bản ghi thú cưng hiện có trong kho mã nguồn `petcare-manager`, trả lời định lượng 8 câu hỏi kiểm toán dữ liệu và xác định cấu trúc bộ dữ liệu cần bổ sung trước khi hiệu chỉnh ngưỡng (threshold calibration) và nghiệm thu **AI-4.0**.

---

## 1. Kiểm kê Chi tiết Tài nguyên Ảnh & Hồ sơ Thú cưng Hiện có

### 1.1. Tổng hợp Bản ghi Thú cưng trong `petcare/database/seed.py`

| Nhóm dữ liệu | Tổng số cá thể | Mèo (`Mèo`) | Chó (`Chó`) | Thỏ (`Thỏ`) | Hamster (`Hamster`) | Ghi chú ánh xạ ảnh |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `CORE_PETS` (`PET-001`..`PET-010`) | `10` | `5` | `3` | `1` | `1` | Chỉ `4` bản ghi đầu (`PET-001`..`PET-004`) có ảnh; `6` bản ghi (`PET-005`..`PET-010`) **không có ảnh** (`photo_filename = NULL`). |
| `ADDITIONAL_DEMO_PETS` (`PET-101`..`PET-164`) | `64` | `32` (`PET-133`..`164`) | `32` (`PET-101`..`132`) | `0` | `0` | Toàn bộ `64 / 64` bản ghi có ảnh chân dung tổng hợp `~300 x 300 px`. |
| **Tổng cộng trong Seed Catalog** | **`74`** | **`37`** | **`35`** | **`1`** | **`1`** | **`68` bản ghi có ảnh** (`35` mèo, `33` chó); **`6` bản ghi không có ảnh**. |

### 1.2. Tổng hợp Tệp Ảnh Vật lý trong Kho Mã nguồn

1. **`assets/demo/pets/` (`68` tệp ảnh PNG chân dung tổng hợp, tổng `~17.9 MB`)**:
   - `4` ảnh chân dung bối cảnh phòng độ phân giải cao (`1254 x 1254` khi chuẩn hóa): `miu-orange-cream.png` (`PET-001`), `nori-tabby.png` (`PET-002`), `may-calico.png` (`PET-003`), `bo-mixed-dog.png` (`PET-004`).
   - `32` ảnh chó (`demo-dog-01.png`..`demo-dog-32.png`) và `32` ảnh mèo (`demo-cat-01.png`..`demo-cat-32.png`) cắt từ bảng contact sheet do AI sinh, kích thước khoảng `298–307 x 294–317 px`, phông nền trắng ngà/xám sáng đồng nhất kiểu studio.
   - **Kiểm tra trùng lặp mã băm**: Cả `68 / 68` tệp có mã `SHA-256` gốc hoàn toàn phân biệt và `68 / 68` mã `SHA-256` sau chuẩn hóa JPEG hoàn toàn phân biệt (`0` ảnh trùng lặp giữa các bản ghi).
2. **`tests/fixtures/vision/` (`8` tệp fixture kiểm thử cơ học & bảo mật tệp)**:
   - `synthetic-cat-black.png` (`931 bytes`) và `synthetic-dog-brown.webp` (`1962 bytes`): **hình vẽ minh họa phẳng kiểu hình học pixel-art**, chỉ dùng kiểm tra luồng tích hợp mock, **không thể** dùng để đo độ chính xác nhận diện thị giác thực tế.
   - `extension-mismatch.jpg` (`931 bytes`, nội dung PNG trùng `synthetic-cat-black.png`), `oversized.png` (`69 KB` nén nhưng vượt `20 MP` điểm ảnh để kiểm tra chống bom giải nén), `unsupported.gif`, `corrupted.png`, `empty.bin`.
3. **`docs/assets/` (ảnh chụp màn hình giao diện Playwright)**:
   - Là ảnh chụp trang web (`dashboard`, `POS`, `invoice`, `report`...), chỉ có giá trị tận dụng một phần nhỏ làm mẫu âm tính (non-animal UI screenshot), không phải dữ liệu thú cưng.

---

## 2. Trả lời Trực tiếp 8 Câu hỏi Kiểm toán Dữ liệu (Dataset Audit Findings)

1. **Có bao nhiêu ảnh mèo có nhãn?**
   - Có **`35` ảnh chân dung mèo tổng hợp dạng nhiếp ảnh** trong `assets/demo/pets/` gắn với `35` bản ghi mèo (`PET-001`..`003`, `PET-133`..`164`), cộng thêm `1` hình vẽ hình học `synthetic-cat-black.png` (chỉ phục vụ kiểm thử cơ học). Trong đó nhóm mèo có sắc cam/vàng/tam thể gồm `9` ảnh (`PET-001` vàng kem, `PET-003` tam thể, `PET-135` cam vằn, `PET-137` tam thể, `PET-139` Bengal nâu vàng, `PET-147` đồi mồi đen cam, `PET-152` cam trắng, `PET-157` cam trắng lông dài, `PET-159` Bengal vàng nâu).
2. **Có bao nhiêu ảnh chó có nhãn?**
   - Có **`33` ảnh chân dung chó tổng hợp dạng nhiếp ảnh** trong `assets/demo/pets/` gắn với `33` bản ghi chó (`PET-004`, `PET-101`..`132`), cộng thêm `1` hình vẽ hình học `synthetic-dog-brown.webp`.
3. **Có bao nhiêu định danh cá thể thú cưng (`unique pet identities`)?**
   - Có **`74` mã cá thể giả lập** trong CSDL (`68` mã có ảnh, ánh xạ `1:1` mỗi tệp ảnh vào đúng 1 mã `PET-*`). Vì đây là ảnh AI tổng hợp độc lập (`assets/demo/pets/README.md`), ngay cả hai bản ghi cùng giống (ví dụ `PET-111` và `PET-131` cùng là Pembroke Welsh Corgi) cũng là hai bức tranh sinh độc lập, **tuyệt đối không suy diễn danh tính cá thể thật từ độ giống nhau thị giác**.
4. **Có nhiều ảnh cho cùng một cá thể thú cưng không?**
   - **KHÔNG (`0` cá thể có từ 2 ảnh trở lên)**. Mỗi cá thể hiện chỉ có tối đa `1` ảnh cả trong thư mục `assets/` lẫn trong thiết kế bảng `pets` (`photo_filename` đơn trị).
5. **Nhãn màu lông và giống (`coat_color`, `breed`) có đáng tin cậy không?**
   - **Đáng tin cậy ở mức quan sát con người trên 68 ảnh demo**, nhưng có **3 hạn chế kỹ thuật lớn**:
     - Chuỗi tự do không chuẩn hóa từ vựng (`"vàng kem"`, `"cam vằn"`, `"cam trắng"`, `"xám xanh"`, `"xám bạc"`).
     - `8 / 68` ảnh (`11.8%`) bị lệch hoàn toàn với bộ lượng tử màu `_color_name()` hiện tại do nhiễu phông nền/lưỡi hồng/lông kem sáng.
     - **Thiên lệch phông nền Studio (`Studio Shortcut Bias`)**: `64 / 68` ảnh (`94.1%`) là ảnh chụp chính diện cận mặt trên phông trơn sáng đồng nhất, thiếu hoàn toàn bối cảnh chuồng/sàn gạch/ánh sáng vàng/góc chụp nghiêng thực tế tại cửa hàng.
6. **Có thể nhận diện ảnh trùng khớp chính xác (`exact duplicate`) không?**
   - Với tập dữ liệu hiện tại, mỗi ảnh gốc có `SHA-256` duy nhất nên **hoàn toàn kiểm chứng được 100%** khi bổ sung lưu mã băm ảnh gốc và ảnh chuẩn hóa; tuy nhiên thuật toán hiện hành chưa lưu mã băm nên đang để lọt `8 / 68` ảnh gốc khỏi vị trí `#1`.
7. **Hiện tại có thể đánh giá thực chất bài toán "cùng một con vật nhưng chụp ảnh khác" (`same-pet / different-photo`) không?**
   - **KHÔNG THỂ đánh giá trung thực trên dữ liệu hiện có trong repo**. Kịch bản `scripts/evaluate_demo_pet_image_retrieval.py` hiện chỉ biến đổi hình học nhẹ (`resize`, `brightness +6%`, `crop 4%`) từ **cùng một bức ảnh gốc**, tức là đo **khả năng chống nhiễu ảnh gần trùng (`near-duplicate`)**, hoàn toàn không phải đo tái nhận diện cá thể qua tư thế/góc chụp/ánh sáng khác nhau (`Instance Re-ID`).
8. **Có sẵn bộ mẫu âm tính (`negative examples`) đáng tin cậy không?**
   - **CHƯA CÓ**. Kho mã nguồn hiện có `0` ảnh hợp lệ đã gán nhãn cho nhóm không phải động vật (đồ vật, hóa đơn, bao thức ăn, phòng trống, con người), `0` ảnh thú ngoại lai có nhãn (thỏ, hamster, chim), `0` ảnh chứa nhiều con vật trong cùng khung hình và `0` ảnh cá thể chó/mèo ngoài danh mục cửa hàng được thiết kế riêng cho kiểm thử từ chối.

---

## 3. Kế hoạch Bổ sung Dữ liệu Có Nhãn Minh bạch cho AI-4.0

Tuân thủ nguyên tắc **không bao giờ tự gán nhãn cá thể chỉ dựa trên cảm quan giống nhau**, bộ dữ liệu kiểm chuẩn AI-4.0 (`tests/fixtures/vision_ai4/`) cần được xây dựng theo **5 gói bổ sung nhỏ gọn, có nguồn gốc bản quyền sạch (`CC0` / `CC-BY-4.0` / ảnh tự chụp có xác thực cá thể)**:

| Mã gói | Mục tiêu kiểm thử | Số lượng tối thiểu khuyến nghị | Yêu cầu nguồn gốc & Nhãn chuẩn (`Ground Truth`) |
| :--- | :--- | :---: | :--- |
| **Pack D1 — Multi-PhotoVerified Individuals** | Đánh giá trung thực `same-pet / different-photo` vs `different-pet / same-breed` (Req E, F, I) | `24` cá thể (`12` mèo, `12` chó) x `3` ảnh khác góc chụp/nền = **`72` ảnh** | Bắt buộc có `animal_instance_id` xác thực từ nguồn gốc chụp (ví dụ ảnh chụp thực tế nhiều góc của cùng một cá thể hoặc tập con có metadata cá thể rõ ràng, giấy phép `CC0`/`CC-BY`), **không dùng ảnh AI sinh ngẫu nhiên để giả làm cùng cá thể**. |
| **Pack D2 — Color & Breed Confounders** | Kiểm thử `orange cat -> orange cats`, mèo đen vs chó đen, mèo trắng vs chó trắng, cùng giống khác cá thể (Req A, B, G) | **`40` ảnh** (`12` mèo cam/vàng, `8` mèo màu khác, `12` chó vàng/cam Corgi/Golden/Pomeranian/Shiba, `8` chó đen/trắng) | Nhãn kiểm duyệt độc lập gồm: `species_canonical` (`cat`/`dog`), `primary_coat_color` chuẩn hóa (`orange`, `cream`, `calico`, `black`, `white`, `gray`, `brown_tabby`), `coat_pattern` và `breed_group`. |
| **Pack D3 — Absent-from-Shop Queries** | Thú cưng thật nhưng **không nằm trong kho cửa hàng** (kiểm thử Req F, H, I, J) | **`24` ảnh** (`12` mèo lạ, `12` chó lạ ở bối cảnh đời thực ngoài studio) | Đảm bảo `in_catalog = false`: hệ thống tuyệt đối không được báo `exact_match` hay `near_duplicate`, và chỉ trả `visually_similar` cùng loài nếu vượt ngưỡng hoặc trả rỗng `[]`. |
| **Pack D4 — Non-Animal & Unsupported Species Negatives** | Kiểm thử từ chối trả kết quả sai (Req H, J) | **`36` ảnh** (`24` ảnh đồ vật/hóa đơn/túi hạt/khay cát/ghế/sàn nhà/người + `12` ảnh thỏ/hamster/chim/cá) | `species_canonical = "non_animal"` hoặc `"other_animal"`, kỳ vọng bắt buộc: `results == []` (`0` cá thể chó/mèo được trả về). |
| **Pack D5 — Degraded, Occluded & Multi-Pet Queries** | Kiểm thử cơ chế từ chối/cảnh báo khi ảnh kém chất lượng hoặc có nhiều thú cưng (Phase 6) | **`28` ảnh** (`10` ảnh mờ rung/thiếu sáng nặng, `8` ảnh che khuất `> 60%`, `10` ảnh có `>= 2` con vật gồm cả `mèo + chó` chung khung hình) | Nhãn `quality_flag` (`blurry`, `occluded`, `low_light`, `multi_pet_same_species`, `multi_pet_mixed_species`); kỳ vọng hệ thống abstain an toàn hoặc yêu cầu chụp tách riêng từng con. |

---

## 4. Đặc tả Schema Manifest v2 & Quy tắc Phân tách Tập Hiệu chỉnh / Tập Nghiệm thu

Để tránh gian lận học máy (**threshold overfitting**), toàn bộ ảnh bổ sung và `68` ảnh seed hiện hữu phải được quản lý qua tệp `manifest_v2.json` với quy tắc phân tách cứng:

1. **Phân tách theo Cá thể (`Instance-Disjoint Split`)**:
   - **`calibration` split (`50%` số cá thể của mỗi nhóm)**: Chỉ dùng để tối ưu hóa nhiệt độ xác suất (`Temperature Scaling`) và chọn các ngưỡng quyết định ($\tau_{\text{species}}, \tau_{\text{near\_dup}}, \tau_{\text{similar}}$).
   - **`acceptance_holdout` split (`50%` số cá thể còn lại, khóa checksum `SHA-256`)**: Không bao giờ dùng để tinh chỉnh trọng số hay dò ngưỡng; chỉ chạy để báo cáo kết quả nghiệm thu cuối cùng.
   - Mọi ảnh có chung `animal_instance_id` bắt buộc phải nằm trọn trong cùng một split (`calibration` hoặc `acceptance_holdout`).
2. **Chuẩn hóa từ điển nhãn trong Manifest v2**:
   - `species_canonical`: `"cat" | "dog" | "other_animal" | "non_animal"`
   - `primary_color_canonical`: `"orange" | "cream" | "yellow_gold" | "brown" | "black" | "white" | "gray_silver" | "calico_tortie" | "bicolor" | null`
   - `animal_instance_id`: chuỗi định danh duy nhất khi xác thực được ngoài đời thực, hoặc `null` đối với ảnh đơn lẻ không xác minh đa góc chụp.
   - `subject_count`: số lượng động vật trong ảnh (`0`, `1`, `2+`).
   - `license` & `source_provenance`: bắt buộc ghi rõ cho từng ảnh để đảm bảo tuân thủ bản quyền học thuật và không chứa dữ liệu cá nhân của khách hàng thật.

