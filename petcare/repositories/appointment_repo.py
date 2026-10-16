"""Repository xử lý dữ liệu bảng appointments (Lịch hẹn khám/chăm sóc)."""

from datetime import datetime
import sqlite3
from typing import Any


class AppointmentRepository:
    """Truy vấn SQL có tham số cho lịch hẹn. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(
        conn: sqlite3.Connection,
        pet_id: int,
        type_: str,
        scheduled_at: str,
        note: str | None = None,
    ) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO appointments (pet_id, type, scheduled_at, status, note, created_at)
            VALUES (?, ?, ?, 'planned', ?, ?)
            """,
            (pet_id, type_.strip(), scheduled_at.strip(), note.strip() if note else None, now_str),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, appt_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT a.*, p.name AS pet_name, p.species, o.full_name AS owner_name, o.phone AS owner_phone
            FROM appointments a
            JOIN pets p ON a.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE a.id = ?
            """,
            (appt_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update_status(conn: sqlite3.Connection, appt_id: int, status: str) -> bool:
        cursor = conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appt_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        appt_id: int,
        type_: str,
        scheduled_at: str,
        status: str,
        note: str | None = None,
    ) -> bool:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET type = ?, scheduled_at = ?, status = ?, note = ?
            WHERE id = ?
            """,
            (type_.strip(), scheduled_at.strip(), status, note.strip() if note else None, appt_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def list_by_pet(conn: sqlite3.Connection, pet_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM appointments
            WHERE pet_id = ?
            ORDER BY scheduled_at ASC, id DESC
            """,
            (pet_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(
        conn: sqlite3.Connection, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        query = """
            SELECT a.*, p.name AS pet_name, p.species, o.full_name AS owner_name, o.phone AS owner_phone
            FROM appointments a
            JOIN pets p ON a.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE 1=1
        """
        params: list[Any] = []
        if status and status.strip():
            query += " AND a.status = ?"
            params.append(status.strip())

        query += " ORDER BY a.scheduled_at ASC, a.id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
