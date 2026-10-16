"""Nạp dữ liệu mẫu an toàn (Idempotent: chạy nhiều lần không tạo dữ liệu trùng)."""

from datetime import datetime, date
from pathlib import Path

from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.security import hash_password


def seed_database(database_path: Path | str | None = None) -> None:
    """Nạp tài khoản, danh mục dịch vụ, chủ nuôi và thú cưng mẫu."""
    # Đảm bảo bảng đã tồn tại
    initialize_database(database_path)
    
    conn = get_connection(database_path)
    now_str = datetime.now().isoformat()
    today_str = date.today().isoformat()

    try:
        # 1. Nạp người dùng (Admin & Nhân viên)
        users_to_seed = [
            ("admin", "Admin@123", "admin", "Quản Trị Viên"),
            ("staff1", "Staff@123", "staff", "Nguyễn Văn Quản"),
            ("staff2", "Staff@123", "staff", "Trần Thị Nhàn"),
        ]
        for username, plain_pass, role, full_name in users_to_seed:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not existing:
                pwd_hash, salt = hash_password(plain_pass)
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, salt, role, full_name, active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (username, pwd_hash, salt, role, full_name, now_str),
                )

        # 2. Nạp danh mục dịch vụ chuẩn
        services_to_seed = [
            ("Khám bệnh tổng quát", "Khám bệnh", 150000),
            ("Khám chuyên khoa / Tái khám", "Khám bệnh", 100000),
            ("Tiêm vaccine Dại", "Tiêm phòng", 180000),
            ("Tiêm vaccine 7 bệnh cho chó", "Tiêm phòng", 250000),
            ("Tiêm vaccine 4 bệnh cho mèo", "Tiêm phòng", 280000),
            ("Tắm vệ sinh & Cắt tỉa lông", "Chăm sóc", 200000),
            ("Cắt móng & Vệ sinh tai", "Chăm sóc", 80000),
            ("Siêu âm ổ bụng", "Xét nghiệm", 300000),
            ("Tẩy giun định kỳ", "Chăm sóc", 50000),
        ]
        for name, category, price in services_to_seed:
            existing = conn.execute("SELECT id FROM services WHERE name = ?", (name,)).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO services (name, category, price_vnd, active, created_at)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (name, category, price, now_str),
                )

        # 3. Nạp chủ nuôi mẫu
        owners_to_seed = [
            ("Nguyễn Thị Lan", "0901234567", "123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM"),
            ("Trần Văn Minh", "0912345678", "45 Lê Duẩn, Phường Bến Nghé, Quận 1, TP.HCM"),
            ("Lê Thị Mai", "0987654321", "78 Hai Bà Trưng, Phường 6, Quận 3, TP.HCM"),
        ]
        owner_ids = {}
        for full_name, phone, address in owners_to_seed:
            row = conn.execute(
                "SELECT id FROM owners WHERE full_name = ? AND phone = ?",
                (full_name, phone),
            ).fetchone()
            if row:
                owner_ids[full_name] = row["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO owners (full_name, phone, address, active, created_at)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (full_name, phone, address, now_str),
                )
                owner_ids[full_name] = cursor.lastrowid

        # 4. Nạp thú cưng mẫu
        pets_to_seed = [
            (
                "Nguyễn Thị Lan",
                "Miu",
                "Mèo",
                "Mèo Anh lông ngắn",
                "female",
                "2024-03-15",
                3.5,
                "Xám tro",
            ),
            (
                "Trần Văn Minh",
                "Bông",
                "Chó",
                "Samoyed",
                "female",
                "2022-05-10",
                18.0,
                "Trắng",
            ),
            (
                "Lê Thị Mai",
                "Mun",
                "Mèo",
                "Mèo ta",
                "male",
                "2023-11-01",
                3.8,
                "Đen tuyền",
            ),
        ]
        pet_ids = {}
        for owner_name, pet_name, species, breed, sex, birth_date, weight, color in pets_to_seed:
            owner_id = owner_ids.get(owner_name)
            if not owner_id:
                continue
            row = conn.execute(
                "SELECT id FROM pets WHERE owner_id = ? AND name = ?",
                (owner_id, pet_name),
            ).fetchone()
            if row:
                pet_ids[pet_name] = row["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO pets (owner_id, name, species, breed, sex, birth_date, weight_kg, coat_color, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (owner_id, pet_name, species, breed, sex, birth_date, weight, color, now_str),
                )
                pet_ids[pet_name] = cursor.lastrowid

        # 5. Nạp một số dữ liệu lịch sử cho thú cưng Bông (để các báo cáo thống kê có số liệu mẫu ban đầu)
        # Chỉ tạo nếu chưa có hóa đơn nào trong hệ thống
        invoice_count = conn.execute("SELECT COUNT(*) as cnt FROM invoices").fetchone()["cnt"]
        if invoice_count == 0 and "Bông" in pet_ids:
            bong_id = pet_ids["Bông"]
            minh_id = owner_ids["Trần Văn Minh"]
            kham_service = conn.execute("SELECT id, price_vnd FROM services WHERE name = 'Khám bệnh tổng quát'").fetchone()
            tam_service = conn.execute("SELECT id, price_vnd FROM services WHERE name = 'Tắm vệ sinh & Cắt tỉa lông'").fetchone()

            if kham_service and tam_service:
                # Visit 1: Khám bệnh
                cur_v1 = conn.execute(
                    """
                    INSERT INTO service_visits (pet_id, service_id, performed_at, unit_price_vnd, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (bong_id, kham_service["id"], today_str, kham_service["price_vnd"], "Khám định kỳ cho Bông"),
                )
                v1_id = cur_v1.lastrowid
                conn.execute(
                    """
                    INSERT INTO examinations (pet_id, visit_id, exam_date, symptoms, diagnosis, medicines)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (bong_id, v1_id, today_str, "Sức khỏe tốt, ăn uống bình thường", "Bình thường", "Bổ sung vitamin"),
                )

                # Visit 2: Tắm
                cur_v2 = conn.execute(
                    """
                    INSERT INTO service_visits (pet_id, service_id, performed_at, unit_price_vnd, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (bong_id, tam_service["id"], today_str, tam_service["price_vnd"], "Dịch vụ spa tắm chải lông"),
                )
                v2_id = cur_v2.lastrowid

                # Invoice paid cho Minh
                cur_inv = conn.execute(
                    """
                    INSERT INTO invoices (owner_id, created_at, status, paid_at, note)
                    VALUES (?, ?, 'paid', ?, 'Thanh toán trực tiếp tại quầy')
                    """,
                    (minh_id, now_str, now_str),
                )
                inv_id = cur_inv.lastrowid
                conn.execute(
                    """
                    INSERT INTO invoice_items (invoice_id, visit_id, service_name_snapshot, pet_name_snapshot, amount_vnd)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (inv_id, v1_id, "Khám bệnh tổng quát", "Bông", kham_service["price_vnd"]),
                )
                conn.execute(
                    """
                    INSERT INTO invoice_items (invoice_id, visit_id, service_name_snapshot, pet_name_snapshot, amount_vnd)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (inv_id, v2_id, "Tắm vệ sinh & Cắt tỉa lông", "Bông", tam_service["price_vnd"]),
                )

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    print("Bắt đầu nạp dữ liệu mẫu (seed)...")
    seed_database()
    print("Nạp dữ liệu mẫu thành công!")


if __name__ == "__main__":
    main()
