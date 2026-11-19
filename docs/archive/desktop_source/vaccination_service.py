"""Dịch vụ quản lý tiêm phòng (Vaccinations)."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.date_utils import normalize_date, parse_date
from petcare.repositories.catalog_repo import CatalogRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.repositories.vaccination_repo import VaccinationRepository
from petcare.repositories.visit_repo import VisitRepository
from petcare.services.auth_service import AuthService, AuthSession


class VaccinationService:
    """Quy tắc nghiệp vụ tiêm phòng và lịch nhắc vaccine."""

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

    def record_vaccination(
        self, session: AuthSession, data: dict[str, Any]
    ) -> tuple[int, int]:
        """Ghi nhận ca tiêm phòng và tạo lượt dịch vụ tương ứng trong cùng giao dịch."""
        pet_id = data.get("pet_id")
        if not pet_id:
            raise ValueError("Vui lòng chọn thú cưng để ghi nhận tiêm phòng")

        service_id = data.get("service_id")
        if not service_id:
            raise ValueError("Vui lòng chọn dịch vụ tiêm phòng")

        vaccine_name = data.get("vaccine_name", "")
        if not vaccine_name or not str(vaccine_name).strip():
            raise ValueError("Tên vaccine không được để trống")

        inj_date_raw = data.get("injection_date") or data.get("date")
        if not inj_date_raw or not str(inj_date_raw).strip():
            inj_date_str = date.today().isoformat()
            inj_date_obj = date.today()
        else:
            try:
                inj_date_obj = parse_date(inj_date_raw, field_name="Ngày tiêm")
                if inj_date_obj > date.today():
                    raise ValueError("Ngày tiêm không được lớn hơn ngày hiện tại")
                inj_date_str = inj_date_obj.isoformat()
            except ValueError as e:
                if "không được lớn hơn" in str(e):
                    raise
                raise ValueError("Ngày tiêm không đúng định dạng YYYY-MM-DD")

        next_due_raw = data.get("next_due_date")
        if next_due_raw and str(next_due_raw).strip():
            try:
                next_due_obj = parse_date(next_due_raw, field_name="Ngày tiêm nhắc lại")
                if next_due_obj <= inj_date_obj:
                    raise ValueError("Ngày hẹn tiêm nhắc lại phải sau ngày tiêm")
                next_due_str = next_due_obj.isoformat()
            except ValueError as e:
                if "phải sau ngày tiêm" in str(e):
                    raise
                raise ValueError("Ngày tiêm nhắc lại không đúng định dạng YYYY-MM-DD")
        else:
            next_due_str = None

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                pet = PetRepository.get_by_id(conn, int(pet_id))
                if not pet:
                    raise ValueError("Thú cưng không tồn tại")
                if not pet["active"]:
                    raise ValueError("Không thể tiêm cho thú cưng đã ngừng theo dõi")

                service = CatalogRepository.get_by_id(conn, int(service_id))
                if not service:
                    raise ValueError("Dịch vụ tiêm không tồn tại trong danh mục")
                if not service["active"]:
                    raise ValueError("Dịch vụ tiêm này đã ngừng cung cấp")

                unit_price = int(service["price_vnd"])

                # 1. Tạo lượt dịch vụ với ngày tiêm chuẩn hóa
                visit_id = VisitRepository.create_visit(
                    conn=conn,
                    pet_id=int(pet_id),
                    service_id=int(service_id),
                    performed_at=inj_date_str,
                    unit_price_vnd=unit_price,
                    notes=f"Tiêm vaccine: {str(vaccine_name).strip()}",
                )

                # 2. Tạo hồ sơ tiêm chủng liên kết với visit_id
                vaccination_id = VaccinationRepository.create(
                    conn=conn,
                    pet_id=int(pet_id),
                    visit_id=visit_id,
                    vaccine_name=str(vaccine_name).strip(),
                    injection_date=inj_date_str,
                    next_due_date=next_due_str,
                )

                return vaccination_id, visit_id
        finally:
            conn.close()

    def get_vaccination(
        self, session: AuthSession, vaccination_id: int
    ) -> dict[str, Any] | None:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VaccinationRepository.get_by_id(conn, vaccination_id)
        finally:
            conn.close()

    def get_pet_vaccinations(
        self, session: AuthSession, pet_id: int
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VaccinationRepository.get_by_pet_id(conn, pet_id)
        finally:
            conn.close()

    def list_vaccinations(
        self, session: AuthSession, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VaccinationRepository.list_all(conn, limit=limit)
        finally:
            conn.close()

    def get_upcoming_reminders(
        self, session: AuthSession, days_ahead: int = 30
    ) -> list[dict[str, Any]]:
        """Lấy danh sách các mũi tiêm cần nhắc trong khoảng số ngày tới."""
        target_date = (date.today() + timedelta(days=days_ahead)).isoformat()
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return VaccinationRepository.get_upcoming_reminders(conn, target_date)
        finally:
            conn.close()

    def resolve_reminder(self, session: AuthSession, vaccination_id: int) -> bool:
        """Đánh dấu đã hoàn thành hoặc hủy nhắc nhở cho mũi tiêm."""
        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                return VaccinationRepository.resolve_reminder(conn, vaccination_id)
        finally:
            conn.close()
