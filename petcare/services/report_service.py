"""Dịch vụ tổng hợp báo cáo thống kê hoạt động và doanh thu."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection
from petcare.repositories.report_repo import ReportRepository
from petcare.services.auth_service import AuthSession


class ReportService:
    """Quy tắc nghiệp vụ tổng hợp thống kê và phân tích số liệu."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def _validate_session(self, session: AuthSession) -> None:
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để xem báo cáo thống kê")

    def get_summary(
        self,
        session: AuthSession,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Tổng hợp các chỉ số: doanh thu, lượt khám, thú cưng đã tiêm, phân bố loài, dịch vụ phổ biến."""
        self._validate_session(session)

        # Mặc định: từ đầu tháng hiện tại đến hôm nay
        today = date.today()
        if not start_date or not str(start_date).strip():
            start_d = today.replace(day=1)
            start_date_str = start_d.isoformat()
        else:
            start_date_str = str(start_date).strip()
            try:
                start_d = date.fromisoformat(start_date_str)
            except ValueError:
                raise ValueError("Ngày bắt đầu không đúng định dạng YYYY-MM-DD")

        if not end_date or not str(end_date).strip():
            end_d = today
            end_date_str = end_d.isoformat()
        else:
            end_date_str = str(end_date).strip()
            try:
                end_d = date.fromisoformat(end_date_str)
            except ValueError:
                raise ValueError("Ngày kết thúc không đúng định dạng YYYY-MM-DD")

        if start_d > end_d:
            raise ValueError("Ngày bắt đầu không được lớn hơn ngày kết thúc")

        # Ranh giới thời gian cho paid_at: từ 00:00:00 ngày bắt đầu đến trước 00:00:00 của ngày tiếp theo ngày kết thúc
        start_datetime = f"{start_date_str}T00:00:00"
        next_day = end_d + timedelta(days=1)
        end_datetime = f"{next_day.isoformat()}T00:00:00"

        conn = self._get_connection()
        try:
            # 1. Doanh thu và số hóa đơn đã thanh toán
            rev_info = ReportRepository.get_revenue_summary(conn, start_datetime, end_datetime)

            # 2. Lượt khám và thú cưng tiêm phòng
            med_info = ReportRepository.get_medical_summary(conn, start_date_str, end_date_str)

            # 3. Phân bố loài
            species_dist = ReportRepository.get_species_distribution(conn)

            # 4. Top dịch vụ phổ biến
            popular_services = ReportRepository.get_popular_services(conn, start_datetime, end_datetime)

            return {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "total_revenue_vnd": rev_info["total_revenue_vnd"],
                "paid_invoices_count": rev_info["paid_invoices_count"],
                "exam_count": med_info["exam_count"],
                "vaccinated_pets_count": med_info["vaccinated_pets_count"],
                "species_distribution": species_dist,
                "popular_services": popular_services,
            }
        finally:
            conn.close()
