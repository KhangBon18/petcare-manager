"""Khởi tạo cấu trúc cơ sở dữ liệu SQLite theo schema.sql mà không xoá dữ liệu cũ."""

from datetime import datetime
from pathlib import Path
import sys

from petcare.database.connection import get_connection
from petcare.security import hash_password


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def initialize_database(database_path: Path | str | None = None) -> None:
    """Tạo các bảng và chỉ mục nếu chưa tồn tại (CREATE TABLE IF NOT EXISTS).
    
    Đồng thời chuẩn hóa an toàn các bản ghi ngày tháng cũ và đảm bảo tài khoản cơ sở.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file schema tại {SCHEMA_PATH}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(database_path)
    try:
        conn.executescript(schema_sql)

        # 1. Bảo toàn dữ liệu cũ: Chuẩn hóa các trường ngày cũ dạng YYYYMMDD (8 ký tự) sang YYYY-MM-DD
        conn.execute(
            """
            UPDATE examinations
            SET exam_date = substr(exam_date, 1, 4) || '-' || substr(exam_date, 5, 2) || '-' || substr(exam_date, 7, 2)
            WHERE length(exam_date) = 8 AND exam_date NOT LIKE '%-%'
            """
        )
        conn.execute(
            """
            UPDATE vaccinations
            SET injection_date = substr(injection_date, 1, 4) || '-' || substr(injection_date, 5, 2) || '-' || substr(injection_date, 7, 2)
            WHERE length(injection_date) = 8 AND injection_date NOT LIKE '%-%'
            """
        )
        conn.execute(
            """
            UPDATE vaccinations
            SET next_due_date = substr(next_due_date, 1, 4) || '-' || substr(next_due_date, 5, 2) || '-' || substr(next_due_date, 7, 2)
            WHERE next_due_date IS NOT NULL AND length(next_due_date) = 8 AND next_due_date NOT LIKE '%-%'
            """
        )
        conn.execute(
            """
            UPDATE pets
            SET birth_date = substr(birth_date, 1, 4) || '-' || substr(birth_date, 5, 2) || '-' || substr(birth_date, 7, 2)
            WHERE birth_date IS NOT NULL AND length(birth_date) = 8 AND birth_date NOT LIKE '%-%'
            """
        )
        conn.execute(
            """
            UPDATE service_visits
            SET performed_at = substr(performed_at, 1, 4) || '-' || substr(performed_at, 5, 2) || '-' || substr(performed_at, 7, 2)
            WHERE length(performed_at) = 8 AND performed_at NOT LIKE '%-%'
            """
        )

        # 2. Đảm bảo tài khoản cơ sở ban đầu nếu bảng users đang rỗng
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM users")
        if cursor.fetchone()["cnt"] == 0:
            now_str = datetime.now().isoformat()
            admin_hash, admin_salt = hash_password("Admin@123")
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, salt, role, full_name, active, created_at)
                VALUES (1, 'admin', ?, ?, 'admin', 'Quản Trị Viên', 1, ?)
                """,
                (admin_hash, admin_salt, now_str),
            )
            staff_hash, staff_salt = hash_password("Staff@123")
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, salt, role, full_name, active, created_at)
                VALUES (2, 'staff', ?, ?, 'staff', 'Nhân viên mặc định', 1, ?)
                """,
                (staff_hash, staff_salt, now_str),
            )

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    print("Bắt đầu khởi tạo cơ sở dữ liệu...")
    initialize_database()
    print("Khởi tạo cơ sở dữ liệu thành công! (Dữ liệu cũ được bảo toàn)")


if __name__ == "__main__":
    main()
