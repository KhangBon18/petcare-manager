"""Repository xử lý dữ liệu bảng users (Tài khoản người dùng)."""

from datetime import datetime
import sqlite3
from typing import Any


class UserRepository:
    """Truy vấn SQL có tham số cho tài khoản. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_username(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(
        conn: sqlite3.Connection,
        username: str,
        password_hash: str,
        salt: str,
        role: str,
        full_name: str,
    ) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, full_name, active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (username.strip(), password_hash, salt, role, full_name.strip(), now_str),
        )
        return cursor.lastrowid

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        user_id: int,
        full_name: str,
        role: str,
        active: int = 1,
    ) -> bool:
        cursor = conn.execute(
            """
            UPDATE users
            SET full_name = ?, role = ?, active = ?
            WHERE id = ?
            """,
            (full_name.strip(), role, active, user_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def update_password(
        conn: sqlite3.Connection,
        user_id: int,
        password_hash: str,
        salt: str,
    ) -> bool:
        cursor = conn.execute(
            """
            UPDATE users
            SET password_hash = ?, salt = ?
            WHERE id = ?
            """,
            (password_hash, salt, user_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def list_all(conn: sqlite3.Connection, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT id, username, role, full_name, active, created_at FROM users"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY id ASC"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def count_active_admins(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE role = 'admin' AND active = 1"
        ).fetchone()
        return row["cnt"] if row else 0
