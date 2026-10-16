"""Dịch vụ quản lý các lượt sử dụng dịch vụ (Service Visits)."""

from datetime import date
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.repositories.catalog_repo import CatalogRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.repositories.visit_repo import VisitRepository
from petcare.services.auth_service import AuthSession


class VisitService:
    """Quản lý các lượt dịch vụ chung (khám, tiêm, tắm/spa, xét nghiệm)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def _validate_session(self, session: AuthSession) -> None:
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để thao tác lượt dịch vụ")

    def record_service_usage(
        self,
        session: AuthSession,
        pet_id: int,
        service_id: int,
        performed_at: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Ghi nhận trực tiếp một lượt sử dụng dịch vụ chăm sóc/xét nghiệm (không qua hồ sơ khám/tiêm)."""
        self._validate_session(session)

        if not pet_id:
            raise ValueError("Vui lòng chọn thú cưng")
        if not service_id:
            raise ValueError("Vui lòng chọn dịch vụ")

        if not performed_at or not str(performed_at).strip():
            performed_at = date.today().isoformat()
        else:
            performed_at = str(performed_at).strip()
            try:
                date.fromisoformat(performed_at)
            except ValueError:
                raise ValueError("Ngày thực hiện không đúng định dạng YYYY-MM-DD")

        conn = self._get_connection()
        try:
            with transaction(conn):
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
                    performed_at=performed_at,
                    unit_price_vnd=unit_price,
                    notes=str(notes).strip() if notes else None,
                )
        finally:
            conn.close()

    def get_unbilled_visits_by_owner(
        self, session: AuthSession, owner_id: int
    ) -> list[dict[str, Any]]:
        """Lấy danh sách các lượt dịch vụ chưa được tính tiền của một chủ nuôi."""
        self._validate_session(session)
        conn = self._get_connection()
        try:
            return VisitRepository.get_unbilled_by_owner(conn, owner_id)
        finally:
            conn.close()

    def get_pet_visits(self, session: AuthSession, pet_id: int) -> list[dict[str, Any]]:
        self._validate_session(session)
        conn = self._get_connection()
        try:
            return VisitRepository.get_by_pet_id(conn, pet_id)
        finally:
            conn.close()

    def list_all_visits(
        self, session: AuthSession, limit: int = 100
    ) -> list[dict[str, Any]]:
        self._validate_session(session)
        conn = self._get_connection()
        try:
            return VisitRepository.list_all(conn, limit=limit)
        finally:
            conn.close()
