"""Dịch vụ quản lý danh mục dịch vụ và giá."""

from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.repositories.catalog_repo import CatalogRepository
from petcare.services.auth_service import AuthSession


class CatalogService:
    """Quy tắc nghiệp vụ danh mục dịch vụ. Chỉ Admin có quyền thêm/sửa/đổi giá."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def _validate_data(self, data: dict[str, Any]) -> tuple[str, str, int]:
        name = data.get("name", "")
        if not name or not str(name).strip():
            raise ValueError("Tên dịch vụ không được để trống")

        category = data.get("category", "")
        if not category or not str(category).strip():
            raise ValueError("Loại/Danh mục dịch vụ không được để trống")

        price_raw = data.get("price_vnd")
        if price_raw is None:
            raise ValueError("Giá dịch vụ không được để trống")

        try:
            price_vnd = int(price_raw)
            if price_vnd < 0:
                raise ValueError("Giá dịch vụ không được là số âm")
        except (ValueError, TypeError) as e:
            if "không được là số âm" in str(e):
                raise
            raise ValueError("Giá dịch vụ phải là một số nguyên VND hợp lệ")

        return str(name).strip(), str(category).strip(), price_vnd

    def create_service(self, session: AuthSession, data: dict[str, Any]) -> int:
        """Tạo dịch vụ mới (chỉ Admin)."""
        if not session or not session.is_admin():
            raise PermissionError("Chỉ Quản trị viên (Admin) mới có quyền tạo dịch vụ mới")

        name, category, price_vnd = self._validate_data(data)

        conn = self._get_connection()
        try:
            with transaction(conn):
                existing = CatalogRepository.get_by_name(conn, name)
                if existing:
                    raise ValueError(f"Dịch vụ với tên '{name}' đã tồn tại")
                return CatalogRepository.create(conn, name, category, price_vnd)
        finally:
            conn.close()

    def update_service(
        self, session: AuthSession, service_id: int, data: dict[str, Any]
    ) -> bool:
        """Cập nhật thông tin dịch vụ hoặc giá (chỉ Admin)."""
        if not session or not session.is_admin():
            raise PermissionError("Chỉ Quản trị viên (Admin) mới có quyền thay đổi thông tin/giá dịch vụ")

        name, category, price_vnd = self._validate_data(data)
        active = int(data.get("active", 1))

        conn = self._get_connection()
        try:
            with transaction(conn):
                target = CatalogRepository.get_by_id(conn, service_id)
                if not target:
                    raise ValueError("Không tìm thấy dịch vụ cần cập nhật")

                # Kiểm tra trùng tên với dịch vụ khác
                same_name = CatalogRepository.get_by_name(conn, name)
                if same_name and same_name["id"] != service_id:
                    raise ValueError(f"Dịch vụ với tên '{name}' đã tồn tại")

                return CatalogRepository.update(conn, service_id, name, category, price_vnd, active)
        finally:
            conn.close()

    def deactivate_service(self, session: AuthSession, service_id: int) -> bool:
        """Ngừng kích hoạt dịch vụ (chỉ Admin)."""
        if not session or not session.is_admin():
            raise PermissionError("Chỉ Quản trị viên (Admin) mới có quyền ngừng kích hoạt dịch vụ")

        conn = self._get_connection()
        try:
            with transaction(conn):
                target = CatalogRepository.get_by_id(conn, service_id)
                if not target:
                    raise ValueError("Không tìm thấy dịch vụ")
                return CatalogRepository.deactivate(conn, service_id)
        finally:
            conn.close()

    def get_service(self, session: AuthSession, service_id: int) -> dict[str, Any] | None:
        """Lấy thông tin một dịch vụ (Admin & Nhân viên)."""
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để xem thông tin dịch vụ")

        conn = self._get_connection()
        try:
            return CatalogRepository.get_by_id(conn, service_id)
        finally:
            conn.close()

    def list_services(
        self, session: AuthSession, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Lấy danh sách dịch vụ (Admin & Nhân viên)."""
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để xem danh sách dịch vụ")

        conn = self._get_connection()
        try:
            return CatalogRepository.list_all(conn, active_only=active_only)
        finally:
            conn.close()

    def search_services(
        self,
        session: AuthSession,
        keyword: str = "",
        category: str = "",
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Tìm kiếm dịch vụ theo tên hoặc phân loại."""
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để tìm kiếm dịch vụ")

        conn = self._get_connection()
        try:
            return CatalogRepository.search(
                conn, keyword=keyword, category=category, active_only=active_only
            )
        finally:
            conn.close()
