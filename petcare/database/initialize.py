"""Khởi tạo cấu trúc cơ sở dữ liệu SQLite theo schema.sql mà không xoá dữ liệu cũ."""

from pathlib import Path
import sys

from petcare.database.connection import get_connection


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def initialize_database(database_path: Path | str | None = None) -> None:
    """Tạo các bảng và chỉ mục nếu chưa tồn tại (CREATE TABLE IF NOT EXISTS)."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file schema tại {SCHEMA_PATH}")
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(database_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    print("Bắt đầu khởi tạo cơ sở dữ liệu...")
    initialize_database()
    print("Khởi tạo cơ sở dữ liệu thành công! (Dữ liệu cũ được bảo toàn)")


if __name__ == "__main__":
    main()
