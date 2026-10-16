"""Dịch vụ quản lý thông tin thú cưng (Pets)."""

from datetime import date
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.date_utils import normalize_date, parse_date
from petcare.repositories.owner_repo import OwnerRepository
from petcare.repositories.pet_repo import PetRepository
from petcare.services.auth_service import AuthService, AuthSession


class PetService:
    """Quy tắc nghiệp vụ và xác thực dữ liệu cho thú cưng."""

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

    def _validate_data(self, data: dict[str, Any]) -> dict[str, Any]:
        name = data.get("name", "")
        if not name or not str(name).strip():
            raise ValueError("Tên thú cưng không được để trống")

        species = data.get("species", "")
        if not species or not str(species).strip():
            raise ValueError("Loài thú cưng (Chó, Mèo,...) không được để trống")

        sex = data.get("sex", "unknown")
        if sex not in ("male", "female", "unknown"):
            raise ValueError("Giới tính phải là 'male' (Đực), 'female' (Cái) hoặc 'unknown' (Chưa rõ)")

        weight_raw = data.get("weight_kg")
        weight_kg = None
        if weight_raw is not None and str(weight_raw).strip() != "":
            try:
                weight_kg = float(weight_raw)
                if weight_kg < 0:
                    raise ValueError("Cân nặng không được là số âm")
            except (TypeError, ValueError) as e:
                if "không được là số âm" in str(e):
                    raise
                raise ValueError("Cân nặng phải là một số hợp lệ")

        birth_date = data.get("birth_date")
        if birth_date and str(birth_date).strip():
            try:
                b_date = parse_date(birth_date, field_name="Ngày sinh")
                if b_date > date.today():
                    raise ValueError("Ngày sinh không được lớn hơn ngày hiện tại")
                b_str = b_date.isoformat()
            except ValueError as e:
                if "không được lớn hơn" in str(e):
                    raise
                raise ValueError("Ngày sinh không đúng định dạng chuẩn YYYY-MM-DD")
        else:
            b_str = None

        return {
            "name": str(name).strip(),
            "species": str(species).strip(),
            "breed": str(data.get("breed", "")).strip() or None,
            "sex": sex,
            "birth_date": b_str,
            "weight_kg": weight_kg,
            "coat_color": str(data.get("coat_color", "")).strip() or None,
        }

    def create_pet(self, session: AuthSession, data: dict[str, Any]) -> int:
        """Tạo thú cưng mới; chủ nuôi phải tồn tại và đang hoạt động."""
        owner_id = data.get("owner_id")
        if not owner_id:
            raise ValueError("Vui lòng chọn chủ nuôi cho thú cưng")

        validated = self._validate_data(data)

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                owner = OwnerRepository.get_by_id(conn, int(owner_id))
                if not owner:
                    raise ValueError("Chủ nuôi không tồn tại trong hệ thống")
                if not owner["active"]:
                    raise ValueError("Không thể thêm thú cưng cho chủ nuôi đã ngừng theo dõi")

                return PetRepository.create(
                    conn=conn,
                    owner_id=int(owner_id),
                    name=validated["name"],
                    species=validated["species"],
                    breed=validated["breed"],
                    sex=validated["sex"],
                    birth_date=validated["birth_date"],
                    weight_kg=validated["weight_kg"],
                    coat_color=validated["coat_color"],
                )
        finally:
            conn.close()

    def update_pet(self, session: AuthSession, pet_id: int, data: dict[str, Any]) -> bool:
        """Cập nhật thông tin thú cưng; chặn đổi chủ nếu thú cưng đã có hóa đơn."""
        validated = self._validate_data(data)
        active = int(data.get("active", 1))

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                existing = PetRepository.get_by_id(conn, pet_id)
                if not existing:
                    raise ValueError("Không tìm thấy thú cưng cần cập nhật")

                new_owner_id = data.get("owner_id")
                target_owner_id = None
                if new_owner_id is not None and int(new_owner_id) != existing["owner_id"]:
                    # Kiểm tra xem có hóa đơn chưa
                    if PetRepository.has_invoices(conn, pet_id):
                        raise ValueError("Không thể đổi chủ nuôi cho thú cưng đã có hóa đơn trong hệ thống")
                    new_owner = OwnerRepository.get_by_id(conn, int(new_owner_id))
                    if not new_owner or not new_owner["active"]:
                        raise ValueError("Chủ nuôi mới không hợp lệ hoặc đã ngừng hoạt động")
                    target_owner_id = int(new_owner_id)

                return PetRepository.update(
                    conn=conn,
                    pet_id=pet_id,
                    name=validated["name"],
                    species=validated["species"],
                    breed=validated["breed"],
                    sex=validated["sex"],
                    birth_date=validated["birth_date"],
                    weight_kg=validated["weight_kg"],
                    coat_color=validated["coat_color"],
                    active=active,
                    owner_id=target_owner_id,
                )
        finally:
            conn.close()

    def get_pet(self, session: AuthSession, pet_id: int) -> dict[str, Any] | None:
        """Lấy thông tin chi tiết một thú cưng kèm thông tin chủ nuôi."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return PetRepository.get_by_id(conn, pet_id)
        finally:
            conn.close()

    def get_pets_by_owner(
        self, session: AuthSession, owner_id: int, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Lấy danh sách thú cưng của một chủ nuôi."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return PetRepository.get_by_owner_id(conn, owner_id, active_only=active_only)
        finally:
            conn.close()

    def search_pets(
        self,
        session: AuthSession,
        keyword: str = "",
        species: str = "",
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Tìm kiếm thú cưng theo tên, giống loài, hoặc tên chủ nuôi."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return PetRepository.search(
                conn, keyword=keyword, species=species, active_only=active_only
            )
        finally:
            conn.close()

    def list_pets(self, session: AuthSession, active_only: bool = True) -> list[dict[str, Any]]:
        """Lấy danh sách toàn bộ thú cưng."""
        return self.search_pets(session, keyword="", species="", active_only=active_only)

    def delete_or_deactivate_pet(self, session: AuthSession, pet_id: int) -> str:
        """Nếu thú cưng đã có lịch sử y tế/hóa đơn, chuyển sang ngừng theo dõi; nếu chưa thì xóa."""
        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                pet = PetRepository.get_by_id(conn, pet_id)
                if not pet:
                    raise ValueError("Không tìm thấy thú cưng")

                has_hist = PetRepository.has_history(conn, pet_id)
                has_inv = PetRepository.has_invoices(conn, pet_id)

                if has_hist or has_inv:
                    PetRepository.deactivate(conn, pet_id)
                    return "deactivated"
                else:
                    PetRepository.delete(conn, pet_id)
                    return "deleted"
        finally:
            conn.close()
