"""Repository xử lý dữ liệu bảng examinations (Hồ sơ khám bệnh)."""

import sqlite3
from typing import Any


class ExamRepository:
    """Truy vấn SQL có tham số cho khám bệnh. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(
        conn: sqlite3.Connection,
        pet_id: int,
        visit_id: int,
        exam_date: str,
        symptoms: str,
        diagnosis: str,
        medicines: str | None = None,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO examinations (pet_id, visit_id, exam_date, symptoms, diagnosis, medicines)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pet_id, visit_id, exam_date.strip(), symptoms.strip(), diagnosis.strip(), medicines.strip() if medicines else None),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, exam_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT e.*, sv.unit_price_vnd, s.name AS service_name,
                   p.name AS pet_name, p.species, o.full_name AS owner_name, o.phone AS owner_phone
            FROM examinations e
            JOIN service_visits sv ON e.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON e.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE e.id = ?
            """,
            (exam_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_pet_id(conn: sqlite3.Connection, pet_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT e.*, sv.unit_price_vnd, s.name AS service_name
            FROM examinations e
            JOIN service_visits sv ON e.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            WHERE e.pet_id = ?
            ORDER BY e.exam_date DESC, e.id DESC
            """,
            (pet_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT e.*, sv.unit_price_vnd, s.name AS service_name,
                   p.name AS pet_name, o.full_name AS owner_name
            FROM examinations e
            JOIN service_visits sv ON e.visit_id = sv.id
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON e.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            ORDER BY e.exam_date DESC, e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
