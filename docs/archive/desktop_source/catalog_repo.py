"""Repository xử lý dữ liệu bảng services (Danh mục dịch vụ)."""

from datetime import datetime
import sqlite3
from typing import Any


class CatalogRepository:
    """Truy vấn SQL có tham số cho dịch vụ. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(conn: sqlite3.Connection, name: str, category: str, price_vnd: int) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO services (name, category, price_vnd, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (name.strip(), category.strip(), int(price_vnd), now_str),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, service_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM services WHERE id = ?",
            (service_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM services WHERE name = ?",
            (name.strip(),),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        service_id: int,
        name: str,
        category: str,
        price_vnd: int,
        active: int = 1,
    ) -> bool:
        cursor = conn.execute(
            """
            UPDATE services
            SET name = ?, category = ?, price_vnd = ?, active = ?
            WHERE id = ?
            """,
            (name.strip(), category.strip(), int(price_vnd), active, service_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def search(
        conn: sqlite3.Connection,
        keyword: str = "",
        category: str = "",
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM services WHERE 1=1"
        params: list[Any] = []

        if active_only:
            query += " AND active = 1"

        if category and category.strip():
            query += " AND category = ?"
            params.append(category.strip())

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query += " AND (name LIKE ? OR category LIKE ?)"
            params.extend([kw, kw])

        query += " ORDER BY id ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, active_only: bool = True) -> list[dict[str, Any]]:
        return CatalogRepository.search(conn, keyword="", category="", active_only=active_only)

    @staticmethod
    def deactivate(conn: sqlite3.Connection, service_id: int) -> bool:
        cursor = conn.execute(
            "UPDATE services SET active = 0 WHERE id = ?",
            (service_id,),
        )
        return cursor.rowcount > 0
