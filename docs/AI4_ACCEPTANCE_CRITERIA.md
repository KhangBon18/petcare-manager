# Kế hoạch Đánh giá, Hiệu chỉnh Ngưỡng & Tiêu chí Nghiệm thu AI-4.0 (`docs/AI4_ACCEPTANCE_CRITERIA.md`)

Tài liệu này quy định phương pháp đánh giá thực nghiệm, định nghĩa toán học cho 7 chỉ số đo lường, quy trình hiệu chỉnh ngưỡng khách quan (**không bịa đặt hằng số ngưỡng khi chưa có dữ liệu hiệu chỉnh**) và các cổng nghiệm thu bắt buộc (**Release Gates**) trước khi cho phép hợp nhất tính năng **AI-4.0 — High-Precision Pet Image Matching**.

---

## 1. Ma trận 11 Kịch bản Kiểm thử Bắt buộc (Mandatory Evaluation Scenarios)

Mọi bản dựng ứng viên của AI-4.0 phải được chạy tự động qua đầy đủ **11 kịch bản thực tế** dưới đây trên tập `acceptance_holdout` đã khóa `SHA-256`:

| STT | Kịch bản kiểm thử | Đầu vào truy vấn (`Query`) | Hành vi đầu ra bắt buộc (`Expected System Behavior`) | Yêu cầu đối ứng |
| :---: | :--- | :--- | :--- | :---: |
| **S01** | **Trùng khớp hệt tệp ảnh (`Same image duplicate`)** | Tệp ảnh gốc hoặc ảnh tải về từ chính hồ sơ đang bán trong cửa hàng (bao gồm cả 8 ca lỗi `PET-001`, `PET-111`, `PET-118`... của baseline cũ). | Trả về đúng hồ sơ đó ở **Hạng `#1`** với `match_tier = "exact_image_match"`; toàn bộ kết quả phụ (nếu bật gợi ý tương tự) bắt buộc cùng loài. | Req A, B, C |
| **S02** | **Biến thể gần trùng của cùng bức ảnh (`Near-duplicate transform`)** | Ảnh gốc của cửa hàng bị nén lại qua ứng dụng nhắn tin (`JPEG quality 60–85`), thu phóng, cắt viền nhẹ `<= 8%`, hoặc lệch sáng nhẹ. | Nhận diện đúng hồ sơ gốc ở **Hạng `#1`** với `match_tier = "near_duplicate_image"` khi vượt ngưỡng hiệu chỉnh $\tau_{\text{near\_dup}}$. | Req C, D |
| **S03** | **Cùng một cá thể thật, ảnh chụp khác góc/nền (`Same pet, different image`)** | Ảnh khác tư thế/ánh sáng của cùng một cá thể xác thực từ **Pack D1**. | Chỉ trả về các cá thể cùng loài; nếu cá thể đó lọt Top-K thì gắn nhãn **`visually_similar_candidate`** — **tuyệt đối không tự khẳng định `exact` hay "cùng một cá thể xác nhận"** khi không có đăng ký sinh trắc đa góc chụp. | Req A, B, E, I |
| **S04** | **Khác cá thể nhưng cùng màu lông (`Different pet, same color`)** | Ảnh mèo đen / mèo trắng / chó vàng không phải cá thể cụ thể đang xét. | Không được báo `exact_image_match` hay `near_duplicate_image`; nếu vượt $\tau_{\text{similar}}$ chỉ được hiển thị ở nhóm `visually_similar_candidate` cùng loài. | Req E, F, I |
| **S05** | **Khác cá thể nhưng cùng giống (`Different pet, same breed`)** | Ảnh một bé Corgi hoặc British Shorthair khác với cá thể đang bán trong kho (ví dụ `PET-111` vs `PET-131`). | Không nhầm thành ảnh trùng lặp của cá thể kia; hiển thị trung thực là ứng viên cùng loài có ngoại hình tương tự nếu đạt ngưỡng. | Req E, F, I |
| **S06** | **Mèo cam đối chiếu kho thú cưng (`Orange cat vs orange cats`)** | Ảnh mèo cam/vàng kem (`miu-orange-cream`, `Gừng`, và các ảnh mèo cam ngoài kho thuộc **Pack D2**). | **100% kết quả trả về là mèo** (`0` chó vàng Corgi/Golden/Pomeranian); các hồ sơ mèo cam/vàng kem tương đồng xếp trên mèo xám/đen/trắng, và không chèn mèo khác màu dưới ngưỡng $\tau_{\text{similar}}$ để lấp đầy danh sách. | Req A, G, J |
| **S07** | **Đối kháng chéo Mèo vs Chó (`Cat versus dog`)** | Toàn bộ ảnh mèo truy vấn trên kho có chó cùng màu lông và ngược lại (chó mặt tròn lông xù như Pomeranian/Pug/Maltese so với mèo Ba Tư/Anh lông dài). | **`0` trường hợp mèo trả về chó và `0` trường hợp chó trả về mèo** trên tập nghiệm thu chuẩn. | Req A, B |
| **S08** | **Ảnh mờ nhòe hoặc bị che khuất nặng (`Blurry / occluded`)** | Ảnh rung tay mất nét nặng, tối đen/cháy sáng, hoặc thú cưng bị che khuất `> 60%` cơ thể/khuôn mặt (**Pack D5**). | Cổng chất lượng hoặc cổng độ tin cậy loài kích hoạt cơ chế **từ chối an toàn (`results = []`)** kèm thông báo yêu cầu ảnh rõ nét hơn. | Req H, J |
| **S09** | **Ảnh không phải động vật & Thú ngoại lai (`Non-animal / unsupported species`)** | Ảnh hóa đơn, bao hạt, đồ chơi, ghế sofa, con người, hoặc ảnh thỏ/hamster/chim (**Pack D4**). | Trả về **`0` kết quả (`results = []`)** với lý do `no_pet_detected` hoặc `unsupported_species` (khắc phục lỗi trả 12 thú cưng trên ảnh hóa đơn của baseline cũ). | Req H, J |
| **S10** | **Cá thể không tồn tại trong cơ sở dữ liệu (`Pet absent from DB`)** | Ảnh rõ nét của một con chó/mèo ngoài đời không nằm trong kho cửa hàng (**Pack D3**). | `0` kết quả mang nhãn `exact_image_match` / `near_duplicate_image`; nếu tắt gợi ý tương tự hoặc không có cá thể cùng loài nào đạt $\tau_{\text{similar}}$ thì trả `results = []`. | Req F, H, I, J |
| **S11** | **Nhiều thú cưng trong một ảnh & Phân loại loài độ tin cậy thấp (`Multi-pet & Low-confidence species`)** | Ảnh chụp chung `mèo + chó` hoặc `2+` cá thể sát nhau; ảnh góc khuất khiến xác suất `cat` vs `dog` sát nhau ($|p_{\text{cat}} - p_{\text{dog}}| < \delta_{\text{margin}}$). | Phát hiện đa chủ thể (`multiple_pets_detected`) hoặc từ chối phân loại (`species_uncertain`), trả `results = []` và hướng dẫn người dùng chụp/cắt riêng từng con vật. | Req A, B, H, J |

---

## 2. Định nghĩa Toán học cho 7 Chỉ số Đánh giá Chính (Core Metrics)

Ưu tiên thiết kế xuyên suốt của AI-4.0 là **Độ chính xác dương tính (Precision) quan trọng hơn Độ phủ (Recall)**: thà trả về ít kết quả đúng hoặc trả rỗng minh bạch còn hơn trả về nhầm loài hoặc nhầm cá thể.

1. **Tỷ lệ Lỗi Chéo Loài (`Cross-Species Error Rate — CSER`)**:
   Với tập truy vấn có nhãn loài chuẩn $Q_{\text{pet}} = \{q \mid y_{\text{species}}(q) \in \{\text{cat}, \text{dog}\}\}$ và tập kết quả trả về $R(q)$:
   $$
   \text{CSER} = \frac{\sum_{q \in Q_{\text{pet}}} \mathbb{I}\!\left(\exists\, c \in R(q) : \text{species}(c) \ne y_{\text{species}}(q)\right)}{|Q_{\text{pet}}|}
   $$
   *(Đếm bất kỳ truy vấn nào để lọt dù chỉ 1 cá thể sai loài ở bất kỳ thứ hạng nào trong $R(q)$).*

2. **Độ chính xác Truy xuất Ảnh Trùng khớp Tuyệt đối ở Hạng 1 (`Exact-Image Retrieval Accuracy — EIRA@1`)**:
   Trên tập truy vấn ảnh gốc/chuẩn hóa đã lưu trong kho $Q_{\text{exact}}$:
   $$
   \text{EIRA}@1 = \frac{1}{|Q_{\text{exact}}|} \sum_{q \in Q_{\text{exact}}} \mathbb{I}\!\left(|R(q)| \ge 1 \;\land\; \text{id}(R(q)_1) = \text{id}^*(q) \;\land\; \text{tier}(R(q)_1) = \text{exact\_image\_match}\right)
   $$

3. **Precision & Recall Bảo thủ trên Biến thể Gần trùng / Cùng Cá thể (`Near-Duplicate Precision & Recall` + Kiểm tra Không Khẳng định Quá mức)**:
   - Trên tập biến thể ảnh gần trùng $Q_{\text{ndup}}$ và tập ảnh không trùng $Q_{\text{non\_dup}}$:
     $$
     \text{Precision}_{\text{ndup}} = \frac{\text{TP}_{\text{ndup}}}{\text{TP}_{\text{ndup}} + \text{FP}_{\text{ndup}}}, \qquad \text{Recall}_{\text{ndup}} = \frac{\text{TP}_{\text{ndup}}}{|Q_{\text{ndup}}|}
     $$
   - Trên tập `same-pet / different-photo` ($Q_{\text{diff\_pose}}$ từ **Pack D1**): đo đồng thời (a) tỷ lệ không gán nhãn sai `exact`/`confirmed_identity` (**bắt buộc đạt `100%`**) và (b) `Recall@K` tham khảo ở nhánh `visually_similar_candidate` để hiểu giới hạn thực tế của mô hình mà không thổi phồng thành nhận diện sinh trắc học.

4. **Độ chính xác Ngoại hình Tương đồng tại Top-K Động (`Similar-Pet Precision@K — sP@K`)**:
   Với truy vấn thú cưng $q$ trả về $m = |R_{\text{sim}}(q)|$ ứng viên tương tự ($1 \le m \le K$, không tính các truy vấn trả rỗng hợp lệ), một ứng viên $c$ được tính là phù hợp ngoại hình ($\text{rel}_{\text{vis}}(q, c) = 1$) khi **cùng loài chuẩn** VÀ **khớp nhóm màu lông/hoa văn chính đã gán nhãn độc lập** (ví dụ mèo cam khớp nhóm `orange / cream / ginger tabby`):
   $$
   \text{sP}@K(q) = \frac{1}{\min(m, K)} \sum_{r=1}^{\min(m, K)} \text{rel}_{\text{vis}}\!\left(q, R_{\text{sim}}(q)_r\right)
   $$

5. **Tỷ lệ Dương tính Giả trên Truy vấn Âm tính (`Negative-Query False Positive Rate — FPR_neg`)**:
   Trên tập truy vấn âm tính $Q_{\text{neg}}$ (gồm ảnh không phải động vật, thú ngoại lai, ảnh mờ đặc, ảnh đa loài):
   $$
   \text{FPR}_{\text{neg}} = \frac{1}{|Q_{\text{neg}}|} \sum_{q \in Q_{\text{neg}}} \mathbb{I}\!\left(|R(q)| > 0\right)
   $$

6. **Độ chính xác Từ chối Không khớp (`No-Match Rejection Accuracy / Specificity — TNR`)**:
   Trên hợp của $Q_{\text{neg}}$ và các truy vấn thú cưng lạ không có cá thể tương đồng màu/hình thái trong kho ($Q_{\text{unmatched}}$):
   $$
   \text{TNR}_{\text{reject}} = 1 - \frac{1}{|Q_{\text{neg}} \cup Q_{\text{unmatched}}|} \sum_{q \in Q_{\text{neg}} \cup Q_{\text{unmatched}}} \mathbb{I}\!\left(|R(q)| > 0\right)
   $$

7. **Độ trễ Tìm kiếm Đầu-Cuối (`Search Latency — p50 & p95`)**:
   Đo thời gian thực thi toàn trình (giải mã ảnh -> phát hiện khung bao -> phân loại loài -> nhúng đặc trưng -> truy vấn/xếp hạng trên kho ứng viên -> hậu xử lý kết quả) bằng mili-giây (`ms`), tách riêng môi trường **Apple Silicon cục bộ (`M1 Pro`)** và **GitHub Actions Linux 2-vCPU**.

---

## 3. Quy trình Hiệu chỉnh Ngưỡng Khách quan (Calibration Protocol — Không Dùng Hằng số Cảm tính)

Trong giai đoạn tiền kiểm toán này, **không một con số ngưỡng tùy ý nào (như `0.75` hay `0.85`) được ấn định trước khi có dữ liệu thực nghiệm**. Khi bước sang giai đoạn hiện thực hóa AI-4.0, toàn bộ các tham số ngưỡng $(\tau_{\text{det}}, T, \tau_{\text{species}}, \delta_{\text{margin}}, k_{\text{cal}}, \tau_{\text{near\_dup}}, \tau_{\text{similar}})$ bắt buộc phải được xác định bằng quy trình 4 bước trên tập **`calibration` (`dev_cal`)**:

1. **Bước C1 — Hiệu chỉnh Nhiệt độ Xác suất (`Temperature Scaling`)**:
   Tìm hệ số nhiệt độ $T > 0$ cực tiểu hóa hàm Negative Log-Likelihood (NLL) và Expected Calibration Error (ECE) của đầu phân loại 4 lớp (`cat`, `dog`, `other_animal`, `non_animal`) trên tập `calibration`.
2. **Bước C2 — Khóa Ngưỡng Cổng Loài & Từ chối Chủ thể ($\tau_{\text{species}}, \delta_{\text{margin}}$)**:
   Quét lưới $(\tau_{\text{species}}, \delta_{\text{margin}})$ trên đường cong Risk–Coverage của tập `calibration` sao cho:
   - Tỷ lệ nhầm lẫn `cat <-> dog` trên `calibration` bằng **`0.0%`** (kèm biên an toàn tối thiểu trên phân phối điểm logit), VÀ
   - Tỷ lệ lọt ảnh không phải chó/mèo (`FPR_neg` ở tầng cổng loài) đạt cực tiểu ($\le 2\%$), ưu tiên đẩy các ca nhập nhằng sang trạng thái `abstain`.
3. **Bước C3 — Khóa Ngưỡng Gần trùng ($k_{\text{cal}}, \tau_{\text{near\_dup}}$)**:
   Tối ưu trên cặp ảnh biến đổi nén/crop (`positive`) đối đầu với các cặp cá thể khác nhau cùng giống & cùng màu lông (`hard negative` trong **Pack D1 & D2**), chọn ngưỡng nhỏ nhất đảm bảo **$\text{Precision}_{\text{ndup, cal}} = 100\%$** (`0` ca cá thể khác nhau bị gắn nhầm là `near_duplicate_image`).
4. **Bước C4 — Khóa Ngưỡng Gợi ý Tương đồng Ngoại hình ($\tau_{\text{similar}}$)**:
   Tối đa hóa điểm $F_{0.5}$ (trọng số Precision gấp đôi Recall) trên nhãn tương đồng màu lông/hình thái cùng loài, với ràng buộc không giữ lại các ứng viên khác nhóm màu cơ bản (ví dụ truy vấn mèo cam không giữ mèo đen/xám trắng).
5. **Bước C5 — Đóng băng Cấu hình & Chấm một lần trên `acceptance_holdout`**:
   Lưu bộ tham số đã hiệu chỉnh vào tệp cấu hình có phiên bản (`vision_calibration_v1.json`), sau đó chạy duy nhất quy trình đánh giá trên tập `acceptance_holdout` đã khóa `SHA-256`.

---

## 4. Cổng Nghiệm thu Phát hành Bắt buộc (AI-4.0 Go / No-Go Release Gates)

Bản triển khai AI-4.0 chỉ được nghiệm thu khi đạt đồng thời **tất cả** các tiêu chí định lượng sau trên tập kiểm thử nghiệm thu (`acceptance_holdout`):

| Hạng mục Nghiệm thu | Chỉ số | Mức Baseline Hiện tại (Đã đo) | Ngưỡng Đạt Bắt buộc của AI-4.0 |
| :--- | :--- | :---: | :---: |
| **Chặn nhầm loài Mèo <-> Chó** | `CSER` trên tập nghiệm thu | `85.3%` sai ở Top-5 (`100%` ở Top-12) | **`0.0%` (`0 / N` truy vấn sai loài)** |
| **Tìm đúng ảnh hồ sơ gốc của cửa hàng** | `EIRA@1` | `88.2%` (`60/68`; `3` ảnh văng khỏi Top-12) | **`100.0%` (`68 / 68` và `100%` tập mở rộng)** |
| **Không nhận vơ cá thể khác là ảnh trùng** | `Precision_ndup` | Không phân biệt mức độ trùng | **`>= 99.0%` (`0` lỗi trên hard negatives cùng giống)** |
| **Không tuyên bố xác nhận danh tính trên ảnh khác góc chụp** | Tuân thủ nhãn `visually_similar_candidate` | Không có kiểm soát nhãn | **`100.0%` tuân thủ (`0` nhãn khẳng định cá thể sai)** |
| **Độ chính xác màu/ngoại hình (Mèo cam -> Mèo cam)** | `sP@5` (trên Top-K động) | Lẫn 4 chó vàng trong Top-5 | **`>= 85.0%`** cùng nhóm sắc lông/ngoại hình trong cùng loài |
| **Từ chối ảnh đồ vật / văn bản / thú ngoại lai** | `TNR_reject` trên `Pack D4` | `0.0%` (trả 12 thú cưng cho ảnh hóa đơn) | **`>= 95.0%`** (`FPR_neg <= 5.0%`) |
| **Xử lý ảnh đa thú cưng (`mèo + chó`) & ảnh mờ đặc** | Tỷ lệ abstain / cảnh báo đúng trên `Pack D5` | `0.0%` | **`>= 90.0%`** từ chối hoặc cảnh báo đa chủ thể an toàn |
| **Độ trễ tìm kiếm toàn trình (`<= 500` hồ sơ)** | `p95 Latency` | `~5 ms` (histogram thuần) | **`<= 250 ms`** trên Mac M1 Pro; **`<= 500 ms`** trên CI CPU |
| **Bảo mật & Quyền riêng tư** | Số lượt gửi ảnh ra API ngoài mặc định | `0` | **`0` tuyệt đối** (`AI_VISION_ENABLED = False`) |

---

## 5. Ghi nhận Minh bạch Rủi ro Thực tế Còn lại (Residual Real-World Risks)

Ngay cả khi đạt **`0.0%` lỗi chéo loài trên bộ kiểm thử nghiệm thu chuẩn**, tài liệu kỹ thuật và giao diện người dùng của AI-4.0 vẫn phải công bố trung thực các rủi ro biên ngoài đời thực:

1. **Giống loài có hình thái giao thoa cực đoan dưới góc chụp khuất**: Thú non rất nhỏ (mèo con sơ sinh vs chó Chihuahua/Pomeranian sơ sinh chụp từ phía sau lưng), hoặc giống không lông (`Mèo Sphynx` vs `Chó Xoloitzcuintli` / `Chinese Crested`) dưới ánh sáng yếu có thể rơi vào vùng biên phân loại. Thiết kế của AI-4.0 giảm thiểu rủi ro này bằng cách **mở rộng vùng từ chối (`abstain`)** để trả `0` kết quả thay vì đoán bừa, nhưng xác suất sai khác `0` ngoài đời thực vẫn tồn tại về mặt lý thuyết thống kê.
2. **Thay đổi ngoại hình theo thời gian tăng trưởng**: Thú cưng lớn lên từ 2 tháng tuổi lên 10 tháng tuổi hoặc vừa cắt tỉa lông (grooming) có thể thay đổi đáng kể hình dáng và sắc độ lông.
3. **Biến thiên cân bằng trắng (White Balance) của camera điện thoại**: Đèn sợi đốt vàng đậm có thể biến bộ lông mèo trắng thành tông vàng kem trên cảm biến ảnh; do đó kết quả luôn được trình bày như **công cụ hỗ trợ tra cứu cho nhân viên/khách hàng**, không thay thế mã định danh hồ sơ (`PET-xxx`) hay kiểm tra thực tế tại cửa hàng.

