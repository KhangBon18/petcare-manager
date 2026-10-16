"""Repository xử lý các truy vấn thống kê, doanh thu và báo cáo."""

import sqlite3
from typing import Any


class ReportRepository:
    """Truy vấn dữ liệu tổng hợp phục vụ màn hình báo cáo thống kê."""

    @staticmethod
    def get_revenue_summary(
        conn: sqlite3.Connection, start_datetime: str, end_datetime: str
    ) -> dict[str, int]:
        """Tính tổng doanh thu và số hóa đơn đã thanh toán trong khoảng thời gian."""
        row = conn.execute(
            """
            SELECT COALESCE(SUM(ii.amount_vnd), 0) AS total_revenue,
                   COUNT(DISTINCT inv.id) AS paid_invoices_count
            FROM invoices inv
            JOIN invoice_items ii ON inv.id = ii.invoice_id
            WHERE inv.status = 'paid'
              AND inv.paid_at >= ? AND inv.paid_at < ?
            """,
            (start_datetime, end_datetime),
        ).fetchone()

        return {
            "total_revenue_vnd": int(row["total_revenue"]) if row else 0,
            "paid_invoices_count": int(row["paid_invoices_count"]) if row else 0,
        }

    @staticmethod
    def get_medical_summary(
        conn: sqlite3.Connection, start_date: str, end_date: str
    ) -> dict[str, int]:
        """Đếm số lượt khám và số lượng thú cưng duy nhất đã được tiêm phòng."""
        # 1. Số lượt khám bệnh
        exam_row = conn.execute(
            """
            SELECT COUNT(*) AS exam_count
            FROM examinations
            WHERE exam_date >= ? AND exam_date <= ?
            """,
            (start_date, end_date),
        ).fetchone()

        # 2. Số thú cưng đã tiêm (COUNT DISTINCT pet_id)
        vac_row = conn.execute(
            """
            SELECT COUNT(DISTINCT pet_id) AS vaccinated_pets_count
            FROM vaccinations
            WHERE injection_date >= ? AND injection_date <= ?
            """,
            (start_date, end_date),
        ).fetchone()

        return {
            "exam_count": int(exam_row["exam_count"]) if exam_row else 0,
            "vaccinated_pets_count": int(vac_row["vaccinated_pets_count"]) if vac_row else 0,
        }

    @staticmethod
    def get_species_distribution(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Phân bố số lượng thú cưng theo từng loài."""
        rows = conn.execute(
            """
            SELECT species, COUNT(*) AS count
            FROM pets
            WHERE active = 1
            GROUP BY species
            ORDER BY count DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_popular_services(
        conn: sqlite3.Connection, start_datetime: str, end_datetime: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Lấy danh sách các dịch vụ được sử dụng nhiều nhất trong các hóa đơn đã thanh toán."""
        rows = conn.execute(
            """
            SELECT ii.service_name_snapshot AS service_name,
                   COUNT(ii.id) AS usage_count,
                   SUM(ii.amount_vnd) AS total_revenue
            FROM invoice_items ii
            JOIN invoices inv ON ii.invoice_id = inv.id
            WHERE inv.status = 'paid'
              AND inv.paid_at >= ? AND inv.paid_at < ?
            GROUP BY ii.service_name_snapshot
            ORDER BY usage_count DESC, total_revenue DESC
            LIMIT ?
            """,
            (start_datetime, end_datetime, limit),
        ).fetchall()
        return [dict(r) for r in rows]
