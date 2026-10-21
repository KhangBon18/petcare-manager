"""Dịch vụ quản lý hồ sơ khám bệnh."""

from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.date_utils import normalize_date
from petcare.repositories.catalog_repo import CatalogRepository
from petcare.repositories.exam_repo import ExamRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.repositories.visit_repo import VisitRepository
from petcare.services.auth_service import AuthService, AuthSession


class ExamService:
    """Quy tắc nghiệp vụ khám bệnh. Lưu ca khám và lượt dịch vụ trong cùng một transaction."""

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

    def record_exam(self, session: AuthSession, data: dict[str, Any]) -> tuple[int, int]:
        """Ghi nhận ca khám bệnh và tạo lượt dịch vụ tương ứng trong cùng giao dịch."""
        pet_id = data.get("pet_id")
        if not pet_id:
            raise ValueError("Vui lòng chọn thú cưng để ghi nhận khám bệnh")

        service_id = data.get("service_id")
        if not service_id:
            raise ValueError("Vui lòng chọn gói dịch vụ khám bệnh")

        symptoms = data.get("symptoms", "")
        if not symptoms or not str(symptoms).strip():
            raise ValueError("Triệu chứng không được để trống")

        diagnosis = data.get("diagnosis", "")
        if not diagnosis or not str(diagnosis).strip():
            raise ValueError("Chẩn đoán không được để trống")

        exam_date_raw = data.get("exam_date") or data.get("date")
        # Chuẩn hóa ngày khám thành ISO YYYY-MM-DD thống nhất, xử lý cả định dạng YYYYMMDD
        exam_date = normalize_date(exam_date_raw, field_name="Ngày khám", default_today=True)

        medicines = str(data.get("medicines", "")).strip() or None

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                pet = PetRepository.get_by_id(conn, int(pet_id))
                if not pet:
                    raise ValueError("Thú cưng không tồn tại")
                if not pet["active"]:
                    raise ValueError("Không thể tạo hồ sơ khám cho thú cưng đã ngừng theo dõi")

                service = CatalogRepository.get_by_id(conn, int(service_id))
                if not service:
                    raise ValueError("Dịch vụ không tồn tại trong danh mục")
                if not service["active"]:
                    raise ValueError("Dịch vụ đã ngừng cung cấp")

                # Snapshot giá hiện tại của dịch vụ
                unit_price = int(service["price_vnd"])

                # 1. Tạo lượt dịch vụ với ngày đã chuẩn hóa
                visit_id = VisitRepository.create_visit(
                    conn=conn,
                    pet_id=int(pet_id),
                    service_id=int(service_id),
                    performed_at=exam_date,
                    unit_price_vnd=unit_price,
                    notes=f"Khám: {str(diagnosis).strip()}",
                )

                # 2. Tạo hồ sơ khám liên kết với visit_id
                exam_id = ExamRepository.create(
                    conn=conn,
                    pet_id=int(pet_id),
                    visit_id=visit_id,
                    exam_date=exam_date,
                    symptoms=str(symptoms).strip(),
                    diagnosis=str(diagnosis).strip(),
                    medicines=medicines,
                )

                return exam_id, visit_id
        finally:
            conn.close()

    def get_exam(self, session: AuthSession, exam_id: int) -> dict[str, Any] | None:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return ExamRepository.get_by_id(conn, exam_id)
        finally:
            conn.close()

    def get_pet_exams(self, session: AuthSession, pet_id: int) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return ExamRepository.get_by_pet_id(conn, pet_id)
        finally:
            conn.close()

    def list_exams(self, session: AuthSession, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return ExamRepository.list_all(conn, limit=limit)
        finally:
            conn.close()
