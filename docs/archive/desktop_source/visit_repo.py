"""Repository xử lý dữ liệu bảng service_visits (Lượt sử dụng dịch vụ)."""

import sqlite3
from typing import Any


class VisitRepository:
    """Truy vấn SQL có tham số cho lượt dịch vụ. Nhận kết nối conn của transaction hiện tại, không tự commit."""

    @staticmethod
    def create_visit(
        conn: sqlite3.Connection,
        pet_id: int,
        service_id: int,
        performed_at: str,
        unit_price_vnd: int,
        notes: str | None = None,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO service_visits (pet_id, service_id, performed_at, unit_price_vnd, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pet_id, service_id, performed_at, int(unit_price_vnd), notes),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, visit_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT sv.*, s.name AS service_name, s.category AS service_category,
                   p.name AS pet_name, p.owner_id, o.full_name AS owner_name
            FROM service_visits sv
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON sv.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            WHERE sv.id = ?
            """,
            (visit_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_pet_id(conn: sqlite3.Connection, pet_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT sv.*, s.name AS service_name, s.category AS service_category
            FROM service_visits sv
            JOIN services s ON sv.service_id = s.id
            WHERE sv.pet_id = ?
            ORDER BY sv.performed_at DESC, sv.id DESC
            """,
            (pet_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_unbilled_by_owner(conn: sqlite3.Connection, owner_id: int) -> list[dict[str, Any]]:
        """Lấy danh sách các lượt dịch vụ của chủ nuôi chưa được đưa vào hóa đơn nào."""
        rows = conn.execute(
            """
            SELECT sv.*, s.name AS service_name, s.category AS service_category,
                   p.name AS pet_name
            FROM service_visits sv
            JOIN pets p ON sv.pet_id = p.id
            JOIN services s ON sv.service_id = s.id
            WHERE p.owner_id = ?
              AND sv.id NOT IN (SELECT visit_id FROM invoice_items)
            ORDER BY sv.performed_at ASC, sv.id ASC
            """,
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT sv.*, s.name AS service_name, s.category AS service_category,
                   p.name AS pet_name, o.full_name AS owner_name,
                   CASE WHEN ii.id IS NOT NULL THEN 1 ELSE 0 END AS is_billed,
                   inv.status AS invoice_status
            FROM service_visits sv
            JOIN services s ON sv.service_id = s.id
            JOIN pets p ON sv.pet_id = p.id
            JOIN owners o ON p.owner_id = o.id
            LEFT JOIN invoice_items ii ON sv.id = ii.visit_id
            LEFT JOIN invoices inv ON ii.invoice_id = inv.id
            ORDER BY sv.performed_at DESC, sv.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
