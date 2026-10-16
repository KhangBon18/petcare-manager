# Sơ đồ Thực thể Quan hệ (ERD - erd.md)

Tài liệu này mô tả cấu trúc 10 bảng cơ sở dữ liệu và các mối quan hệ khóa ngoại trong hệ thống PetCare Manager.

---

## 1. Sơ đồ Quan hệ Thực thể (Mermaid Diagram)

```mermaid
erDiagram
    users {
        INTEGER id PK
        TEXT username UK
        TEXT password_hash
        TEXT salt
        TEXT role
        TEXT full_name
        INTEGER active
        TEXT created_at
    }

    owners {
        INTEGER id PK
        TEXT full_name
        TEXT phone
        TEXT address
        INTEGER active
        TEXT created_at
    }

    pets {
        INTEGER id PK
        INTEGER owner_id FK
        TEXT name
        TEXT species
        TEXT breed
        TEXT sex
        TEXT birth_date
        REAL weight_kg
        TEXT coat_color
        INTEGER active
        TEXT created_at
    }

    services {
        INTEGER id PK
        TEXT name UK
        TEXT category
        INTEGER price_vnd
        INTEGER active
        TEXT created_at
    }

    service_visits {
        INTEGER id PK
        INTEGER pet_id FK
        INTEGER service_id FK
        TEXT performed_at
        INTEGER unit_price_vnd
        TEXT notes
    }

    examinations {
        INTEGER id PK
        INTEGER pet_id FK
        INTEGER visit_id UK,FK
        TEXT exam_date
        TEXT symptoms
        TEXT diagnosis
        TEXT medicines
    }

    vaccinations {
        INTEGER id PK
        INTEGER pet_id FK
        INTEGER visit_id UK,FK
        TEXT vaccine_name
        TEXT injection_date
        TEXT next_due_date
        INTEGER reminder_resolved
    }

    appointments {
        INTEGER id PK
        INTEGER pet_id FK
        TEXT type
        TEXT scheduled_at
        TEXT status
        TEXT note
        TEXT created_at
    }

    invoices {
        INTEGER id PK
        INTEGER owner_id FK
        TEXT created_at
        TEXT status
        TEXT paid_at
        TEXT note
    }

    invoice_items {
        INTEGER id PK
        INTEGER invoice_id FK
        INTEGER visit_id UK,FK
        TEXT service_name_snapshot
        TEXT pet_name_snapshot
        INTEGER amount_vnd
    }

    owners ||--o{ pets : "sở hữu (1-N)"
    owners ||--o{ invoices : "thanh toán (1-N)"
    pets ||--o{ service_visits : "sử dụng (1-N)"
    pets ||--o{ examinations : "khám bệnh (1-N)"
    pets ||--o{ vaccinations : "tiêm phòng (1-N)"
    pets ||--o{ appointments : "lên lịch hẹn (1-N)"
    services ||--o{ service_visits : "định giá (1-N)"
    service_visits ||--o| examinations : "liên kết (1-1)"
    service_visits ||--o| vaccinations : "liên kết (1-1)"
    service_visits ||--o| invoice_items : "thuộc hóa đơn (1-1)"
    invoices ||--|{ invoice_items : "chứa chi tiết (1-N)"
```

---

## 2. Chi tiết các Ràng buộc Toàn vẹn (Constraints)

1. **Khóa ngoại và Bật Pragma**:
   - Mọi kết nối SQLite đều thực thi `PRAGMA foreign_keys = ON;`.
   - Các bảng `pets`, `service_visits`, `examinations`, `vaccinations`, `appointments`, `invoices`, `invoice_items` đều có ràng buộc `REFERENCES` tới bảng cha tương ứng.
2. **Ràng buộc Tính phí Một lần (`visit_id UNIQUE`)**:
   - `invoice_items.visit_id` được đặt ràng buộc `UNIQUE`.
   - Bất kỳ lượt dịch vụ nào đã tồn tại trong `invoice_items` sẽ bị SQLite từ chối nếu cố tình chèn thêm vào một hóa đơn khác.
3. **Ràng buộc Liên kết Khám & Tiêm**:
   - `examinations.visit_id UNIQUE` và `vaccinations.visit_id UNIQUE` bảo đảm mỗi hồ sơ y tế chỉ gắn liền với một lượt dịch vụ duy nhất.
4. **Bảo toàn Giá lịch sử (Snapshotting)**:
   - Khi dịch vụ thay đổi giá trong `services.price_vnd`, các bản ghi `service_visits.unit_price_vnd` và `invoice_items.amount_vnd` đã lưu trong quá khứ không bị cập nhật theo, giữ đúng nguyên giá trị tại thời điểm thực hiện.
