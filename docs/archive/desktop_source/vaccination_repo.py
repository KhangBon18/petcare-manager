"""Repository xử lý dữ liệu bảng vaccinations (Hồ sơ tiêm phòng)."""

import sqlite3
from typing import Any


class VaccinationRepository:
    """Truy vấn SQL có tham số cho tiêm phòng. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(
        conn: sqlite3.Connection,
        pet_id: int,
        visit_id: int,
        vaccine_name: str,
        injection_date: str,
        next_due_date: str | None = None,
        reminder_resolved: int = 0,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO vaccinations (pet_id, visit_id, vaccine_name, injection_date, next_due_date, reminder_resolved)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pet_id,
                visit_id,
                vaccine_name.strip(),
                injection_date.strip(),
                next_due_date.strip() if next_due_date else None,
                reminder_resolved,
            ),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, vaccination_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT v.*, sv.unit_price_vnd, s.name AS service_name,
                   p.name AS pet_name, p.species, o.full_name AS owner_name, o.phone AS owner_phone
            FROM vaccinations v
            JOIN service_visits sv ON v.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON v.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE v.id = ?
            """,
            (vaccination_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_pet_id(conn: sqlite3.Connection, pet_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT v.*, sv.unit_price_vnd, s.name AS service_name
            FROM vaccinations v
            JOIN service_visits sv ON v.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            WHERE v.pet_id = ?
            ORDER BY v.injection_date DESC, v.id DESC
            """,
            (pet_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT v.*, sv.unit_price_vnd, s.name AS service_name,
                   p.name AS pet_name, o.full_name AS owner_name
            FROM vaccinations v
            JOIN service_visits sv ON v.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON v.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            ORDER BY v.injection_date DESC, v.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_upcoming_reminders(
        conn: sqlite3.Connection, target_date: str
    ) -> list[dict[str, Any]]:
        """Lấy danh sách các mũi tiêm cần nhắc (next_due_date <= target_date và reminder_resolved = 0)."""
        rows = conn.execute(
            """
            SELECT v.*, p.name AS pet_name, p.species, o.full_name AS owner_name, o.phone AS owner_phone
            FROM vaccinations v
            JOIN pets p ON v.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE v.next_due_date IS NOT NULL
              AND v.next_due_date <= ?
              AND v.reminder_resolved = 0
            ORDER BY v.next_due_date ASC
            """,
            (target_date,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def resolve_reminder(conn: sqlite3.Connection, vaccination_id: int) -> bool:
        cursor = conn.execute(
            "UPDATE vaccinations SET reminder_resolved = 1 WHERE id = ?",
            (vaccination_id,),
        )
        return cursor.rowcount > 0
