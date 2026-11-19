"""Repository xử lý dữ liệu bảng owners (Chủ nuôi)."""

from datetime import datetime
import sqlite3
from typing import Any


class OwnerRepository:
    """Truy vấn SQL có tham số cho chủ nuôi. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(conn: sqlite3.Connection, full_name: str, phone: str, address: str) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO owners (full_name, phone, address, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (full_name.strip(), phone.strip(), address.strip(), now_str),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, owner_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM owners WHERE id = ?",
            (owner_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        owner_id: int,
        full_name: str,
        phone: str,
        address: str,
        active: int = 1,
    ) -> bool:
        cursor = conn.execute(
            """
            UPDATE owners
            SET full_name = ?, phone = ?, address = ?, active = ?
            WHERE id = ?
            """,
            (full_name.strip(), phone.strip(), address.strip(), active, owner_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def search(
        conn: sqlite3.Connection,
        keyword: str = "",
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM owners WHERE 1=1"
        params: list[Any] = []

        if active_only:
            query += " AND active = 1"

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query += " AND (full_name LIKE ? OR phone LIKE ? OR address LIKE ?)"
            params.extend([kw, kw, kw])

        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, active_only: bool = True) -> list[dict[str, Any]]:
        return OwnerRepository.search(conn, keyword="", active_only=active_only)

    @staticmethod
    def has_invoices(conn: sqlite3.Connection, owner_id: int) -> bool:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
        return (row["cnt"] if row else 0) > 0

    @staticmethod
    def has_pets(conn: sqlite3.Connection, owner_id: int) -> bool:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM pets WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
        return (row["cnt"] if row else 0) > 0

    @staticmethod
    def deactivate(conn: sqlite3.Connection, owner_id: int) -> bool:
        cursor = conn.execute(
            "UPDATE owners SET active = 0 WHERE id = ?",
            (owner_id,),
        )
        return cursor.rowcount > 0

    @staticmethod
    def delete(conn: sqlite3.Connection, owner_id: int) -> bool:
        cursor = conn.execute(
            "DELETE FROM owners WHERE id = ?",
            (owner_id,),
        )
        return cursor.rowcount > 0
