"""Repository xử lý dữ liệu bảng invoices và invoice_items (Hóa đơn và Chi tiết)."""

from datetime import datetime
import sqlite3
from typing import Any


class InvoiceRepository:
    """Truy vấn SQL có tham số cho hóa đơn. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create_invoice(
        conn: sqlite3.Connection,
        owner_id: int,
        note: str | None = None,
    ) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO invoices (owner_id, created_at, status, paid_at, note)
            VALUES (?, ?, 'unpaid', NULL, ?)
            """,
            (owner_id, now_str, note.strip() if note else None),
        )
        return cursor.lastrowid

    @staticmethod
    def add_item(
        conn: sqlite3.Connection,
        invoice_id: int,
        visit_id: int,
        service_name_snapshot: str,
        pet_name_snapshot: str,
        amount_vnd: int,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO invoice_items (invoice_id, visit_id, service_name_snapshot, pet_name_snapshot, amount_vnd)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                visit_id,
                service_name_snapshot.strip(),
                pet_name_snapshot.strip(),
                int(amount_vnd),
            ),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, invoice_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT inv.*, o.full_name AS owner_name, o.phone AS owner_phone, o.address AS owner_address
            FROM invoices inv
            JOIN owners o ON inv.owner_id = o.id
            WHERE inv.id = ?
            """,
            (invoice_id,),
        ).fetchone()
        if not row:
            return None

        inv = dict(row)
        inv["items"] = InvoiceRepository.get_items(conn, invoice_id)
        inv["total_amount_vnd"] = sum(item["amount_vnd"] for item in inv["items"])
        return inv

    @staticmethod
    def get_items(conn: sqlite3.Connection, invoice_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT ii.*, sv.performed_at, sv.pet_id
            FROM invoice_items ii
            JOIN service_visits sv ON ii.visit_id = sv.id
            WHERE ii.invoice_id = ?
            ORDER BY ii.id ASC
            """,
            (invoice_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_total_amount(conn: sqlite3.Connection, invoice_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_vnd), 0) as total FROM invoice_items WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()
        return row["total"] if row else 0

    @staticmethod
    def is_visit_billed(conn: sqlite3.Connection, visit_id: int) -> bool:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoice_items WHERE visit_id = ?",
            (visit_id,),
        ).fetchone()
        return (row["cnt"] if row else 0) > 0

    @staticmethod
    def mark_as_paid(conn: sqlite3.Connection, invoice_id: int, paid_at_str: str) -> bool:
        cursor = conn.execute(
            """
            UPDATE invoices
            SET status = 'paid', paid_at = ?
            WHERE id = ? AND status = 'unpaid'
            """,
            (paid_at_str, invoice_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def cancel_invoice(conn: sqlite3.Connection, invoice_id: int) -> bool:
        """Hủy hóa đơn unpaid: xóa các chi tiết invoice_items để giải phóng visit_id, đổi status = cancelled."""
        # 1. Xóa các dòng chi tiết
        conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        # 2. Cập nhật trạng thái
        cursor = conn.execute(
            "UPDATE invoices SET status = 'cancelled' WHERE id = ? AND status = 'unpaid'",
            (invoice_id,),
        )
        return cursor.rowcount > 0

    @staticmethod
    def list_all(
        conn: sqlite3.Connection,
        status: str | None = None,
        owner_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT inv.*, o.full_name AS owner_name, o.phone AS owner_phone,
                   COALESCE(SUM(ii.amount_vnd), 0) AS total_amount_vnd,
                   COUNT(ii.id) AS item_count
            FROM invoices inv
            JOIN owners o ON inv.owner_id = o.id
            LEFT JOIN invoice_items ii ON inv.id = ii.invoice_id
            WHERE 1=1
        """
        params: list[Any] = []
        if status and status.strip():
            query += " AND inv.status = ?"
            params.append(status.strip())

        if owner_id:
            query += " AND inv.owner_id = ?"
            params.append(int(owner_id))

        query += " GROUP BY inv.id ORDER BY inv.id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
