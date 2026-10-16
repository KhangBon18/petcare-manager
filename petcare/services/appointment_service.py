"""Dịch vụ quản lý lịch hẹn (Appointments)."""

from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.date_utils import normalize_datetime
from petcare.repositories.appointment_repo import AppointmentRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.services.auth_service import AuthService, AuthSession


class AppointmentService:
    """Quy tắc nghiệp vụ lịch hẹn. Đảm bảo lịch hẹn chưa tạo khoản phí."""

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

    def create_appointment(self, session: AuthSession, data: dict[str, Any]) -> int:
        """Tạo lịch hẹn mới; cam kết chưa phát sinh lượt dịch vụ hay phí."""
        pet_id = data.get("pet_id")
        if not pet_id:
            raise ValueError("Vui lòng chọn thú cưng cho lịch hẹn")

        type_ = data.get("type", "")
        if not type_ or not str(type_).strip():
            raise ValueError("Loại lịch hẹn (Khám, Tiêm, Spa,...) không được để trống")

        sched_at_raw = data.get("scheduled_at", "")
        if not sched_at_raw or not str(sched_at_raw).strip():
            raise ValueError("Thời gian hẹn không được để trống")

        # Chuẩn hóa và xác thực ngày giờ thực sự; từ chối chuỗi không hợp lệ
        scheduled_at = normalize_datetime(sched_at_raw, field_name="Thời gian hẹn")

        note = str(data.get("note", "")).strip() or None

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                pet = PetRepository.get_by_id(conn, int(pet_id))
                if not pet:
                    raise ValueError("Thú cưng không tồn tại")
                if not pet["active"]:
                    raise ValueError("Không thể đặt hẹn cho thú cưng đã ngừng theo dõi")

                # Lưu ý: Lịch hẹn chỉ lưu thông tin kế hoạch, chưa tạo bất kỳ khoản phí nào
                return AppointmentRepository.create(
                    conn=conn,
                    pet_id=int(pet_id),
                    type_=str(type_).strip(),
                    scheduled_at=scheduled_at,
                    note=note,
                )
        finally:
            conn.close()

    def update_status(self, session: AuthSession, appt_id: int, status: str) -> bool:
        """Cập nhật trạng thái lịch hẹn: planned / completed / cancelled."""
        if status not in ("planned", "completed", "cancelled"):
            raise ValueError("Trạng thái lịch hẹn phải là 'planned', 'completed' hoặc 'cancelled'")

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                target = AppointmentRepository.get_by_id(conn, appt_id)
                if not target:
                    raise ValueError("Không tìm thấy lịch hẹn")
                return AppointmentRepository.update_status(conn, appt_id, status)
        finally:
            conn.close()

    def get_appointment(self, session: AuthSession, appt_id: int) -> dict[str, Any] | None:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return AppointmentRepository.get_by_id(conn, appt_id)
        finally:
            conn.close()

    def list_appointments(
        self, session: AuthSession, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return AppointmentRepository.list_all(conn, status=status, limit=limit)
        finally:
            conn.close()

    def get_pet_appointments(self, session: AuthSession, pet_id: int) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return AppointmentRepository.list_by_pet(conn, pet_id)
        finally:
            conn.close()
