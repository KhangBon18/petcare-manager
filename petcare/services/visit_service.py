"""Dịch vụ quản lý các lượt sử dụng dịch vụ (Service Visits)."""

from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.date_utils import normalize_date
from petcare.repositories.catalog_repo import CatalogRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.repositories.visit_repo import VisitRepository
from petcare.services.auth_service import AuthService, AuthSession


class VisitService:
    """Quản lý các lượt dịch vụ chung (khám, tiêm, tắm/spa, xét nghiệm)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def _validate_session(
        self,
        session: AuthSession,
        required_role: str = "staff",
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        if conn is not None:
            return AuthService.verify_session(conn, session, required_role=required_role)
        temp_conn = self._get_connection()
        try:
            return AuthService.verify_session(temp_conn, session, required_role=required_role)
        finally:
            temp_conn.close()

    def record_service_usage(
        self,
        session: AuthSession,
        pet_id: int,
        service_id: int,
        performed_at: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Ghi nhận trực tiếp một lượt sử dụng dịch vụ chăm sóc/xét nghiệm (không qua hồ sơ khám/tiêm)."""
        if not pet_id:
            raise ValueError("Vui lòng chọn thú cưng")
        if not service_id:
            raise ValueError("Vui lòng chọn dịch vụ")

        # Chuẩn hóa ngày thực hiện thành ISO YYYY-MM-DD
        performed_at_str = normalize_date(performed_at, field_name="Ngày thực hiện", default_today=True)

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                pet = PetRepository.get_by_id(conn, int(pet_id))
                if not pet:
                    raise ValueError("Thú cưng không tồn tại")
                if not pet["active"]:
                    raise ValueError("Không thể ghi nhận dịch vụ cho thú cưng đã ngừng theo dõi")

                service = CatalogRepository.get_by_id(conn, int(service_id))
                if not service:
                    raise ValueError("Dịch vụ không tồn tại")
                if not service["active"]:
                    raise ValueError("Dịch vụ đã ngừng cung cấp")

                unit_price = int(service["price_vnd"])
                return VisitRepository.create_visit(
                    conn=conn,
                    pet_id=int(pet_id),
                    service_id=int(service_id),
                    performed_at=performed_at_str,
                    unit_price_vnd=unit_price,
                    notes=str(notes).strip() if notes else None,
                )
        finally:
            conn.close()

    def get_unbilled_visits_by_owner(
        self, session: AuthSession, owner_id: int
    ) -> list[dict[str, Any]]:
        """Lấy danh sách các lượt dịch vụ chưa được tính tiền của một chủ nuôi."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VisitRepository.get_unbilled_by_owner(conn, owner_id)
        finally:
            conn.close()

    def get_pet_visits(self, session: AuthSession, pet_id: int) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VisitRepository.get_by_pet_id(conn, pet_id)
        finally:
            conn.close()

    def list_all_visits(
        self, session: AuthSession, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VisitRepository.list_all(conn, limit=limit)
        finally:
            conn.close()
