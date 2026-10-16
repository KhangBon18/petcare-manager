"""Dịch vụ quản lý chủ nuôi (Owners)."""

from pathlib import Path
import re
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.repositories.owner_repo import OwnerRepository
from petcare.services.auth_service import AuthService, AuthSession


class OwnerService:
    """Quy tắc nghiệp vụ và xác thực dữ liệu cho chủ nuôi."""

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

    def _validate_data(self, full_name: str, phone: str, address: str) -> tuple[str, str, str]:
        name = full_name.strip() if full_name else ""
        if not name or len(name) < 2:
            raise ValueError("Họ và tên chủ nuôi phải có ít nhất 2 ký tự")

        p = phone.strip() if phone else ""
        if not p:
            raise ValueError("Số điện thoại không được để trống")
        # Kiểm tra số điện thoại: cho phép chữ số, khoảng trắng, dấu cộng hoặc dấu gạch nối, độ dài tối thiểu 8 ký tự số
        digits = re.sub(r"\D", "", p)
        if len(digits) < 8 or len(digits) > 15:
            raise ValueError("Số điện thoại không hợp lệ (cần từ 8 đến 15 chữ số)")

        addr = address.strip() if address else ""
        if not addr:
            raise ValueError("Địa chỉ không được để trống")

        return name, p, addr

    def create_owner(self, session: AuthSession, data: dict[str, Any]) -> int:
        """Tạo chủ nuôi mới sau khi kiểm tra dữ liệu hợp lệ."""
        full_name, phone, address = self._validate_data(
            data.get("full_name", ""),
            data.get("phone", ""),
            data.get("address", ""),
        )

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                return OwnerRepository.create(conn, full_name, phone, address)
        finally:
            conn.close()

    def update_owner(self, session: AuthSession, owner_id: int, data: dict[str, Any]) -> bool:
        """Cập nhật thông tin chủ nuôi."""
        full_name, phone, address = self._validate_data(
            data.get("full_name", ""),
            data.get("phone", ""),
            data.get("address", ""),
        )
        active = int(data.get("active", 1))

        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                existing = OwnerRepository.get_by_id(conn, owner_id)
                if not existing:
                    raise ValueError("Không tìm thấy chủ nuôi cần cập nhật")
                return OwnerRepository.update(conn, owner_id, full_name, phone, address, active)
        finally:
            conn.close()

    def get_owner(self, session: AuthSession, owner_id: int) -> dict[str, Any] | None:
        """Lấy thông tin chi tiết một chủ nuôi."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return OwnerRepository.get_by_id(conn, owner_id)
        finally:
            conn.close()

    def search_owners(
        self, session: AuthSession, keyword: str = "", active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Tìm kiếm chủ nuôi theo từ khóa (tên, số điện thoại, địa chỉ)."""
        conn = self._get_connection()
        try:
            self._validate_session(session, conn=conn)
            return OwnerRepository.search(conn, keyword=keyword, active_only=active_only)
        finally:
            conn.close()

    def list_owners(self, session: AuthSession, active_only: bool = True) -> list[dict[str, Any]]:
        """Lấy danh sách tất cả chủ nuôi."""
        return self.search_owners(session, keyword="", active_only=active_only)

    def delete_or_deactivate_owner(self, session: AuthSession, owner_id: int) -> str:
        """Nếu chủ nuôi đã có thú cưng hoặc hóa đơn, chuyển sang ngừng theo dõi; nếu chưa thì xóa."""
        conn = self._get_connection()
        try:
            with transaction(conn):
                self._validate_session(session, conn=conn)
                owner = OwnerRepository.get_by_id(conn, owner_id)
                if not owner:
                    raise ValueError("Không tìm thấy chủ nuôi")

                has_pets = OwnerRepository.has_pets(conn, owner_id)
                has_inv = OwnerRepository.has_invoices(conn, owner_id)

                if has_pets or has_inv:
                    OwnerRepository.deactivate(conn, owner_id)
                    return "deactivated"
                else:
                    OwnerRepository.delete(conn, owner_id)
                    return "deleted"
        finally:
            conn.close()
