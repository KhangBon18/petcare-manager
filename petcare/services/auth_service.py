"""Dịch vụ xác thực và quản lý tài khoản người dùng."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.repositories.user_repo import UserRepository
from petcare.security import hash_password, verify_password


@dataclass(frozen=True)
class AuthSession:
    """Phiên đăng nhập hiện tại; không lưu mật khẩu hoặc hash."""
    user_id: int
    username: str
    role: str
    full_name: str

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_staff(self) -> bool:
        return self.role in ("admin", "staff")


class AuthService:
    """Xử lý đăng nhập, phân quyền và quản lý tài khoản."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def login(self, username: str, password: str) -> AuthSession:
        """Xác thực tài khoản và trả về AuthSession."""
        if not username or not password:
            raise ValueError("Tên đăng nhập và mật khẩu không được để trống")

        conn = self._get_connection()
        try:
            user = UserRepository.get_by_username(conn, username.strip())
            if not user:
                raise ValueError("Tên đăng nhập hoặc mật khẩu không chính xác")

            if not user["active"]:
                raise ValueError("Tài khoản này đã bị khóa hoặc ngừng kích hoạt")

            if not verify_password(password, user["password_hash"], user["salt"]):
                raise ValueError("Tên đăng nhập hoặc mật khẩu không chính xác")

            return AuthSession(
                user_id=user["id"],
                username=user["username"],
                role=user["role"],
                full_name=user["full_name"],
            )
        finally:
            conn.close()

    @staticmethod
    def verify_session(
        conn: sqlite3.Connection,
        session: AuthSession,
        required_role: str = "staff",
    ) -> dict[str, Any]:
        """Xác thực phiên trực tiếp từ DB: kiểm tra tài khoản tồn tại, active và quyền mới nhất."""
        if not session or not session.user_id:
            raise PermissionError("Phiên đăng nhập không hợp lệ hoặc đã hết hạn")

        user = UserRepository.get_by_id(conn, session.user_id)
        if not user:
            raise PermissionError("Tài khoản người dùng không còn tồn tại trong hệ thống")

        if not user["active"]:
            raise PermissionError("Tài khoản này đã bị khóa hoặc ngừng kích hoạt")

        actual_role = user["role"]
        if required_role == "admin" and actual_role != "admin":
            raise PermissionError("Chỉ Quản trị viên (Admin) mới có quyền thực hiện thao tác này")
        elif required_role == "staff" and actual_role not in ("admin", "staff"):
            raise PermissionError("Thao tác yêu cầu quyền Nhân viên hoặc Quản trị viên")

        return dict(user)

    def create_user(
        self,
        session: AuthSession,
        username: str,
        password: str,
        role: str,
        full_name: str,
    ) -> int:
        """Tạo tài khoản mới (chỉ Admin)."""
        u_name = username.strip() if username else ""
        if not u_name or len(u_name) < 3:
            raise ValueError("Tên đăng nhập phải có ít nhất 3 ký tự")

        if not password or len(password) < 6:
            raise ValueError("Mật khẩu phải có ít nhất 6 ký tự")

        if role not in ("admin", "staff"):
            raise ValueError("Vai trò người dùng phải là 'admin' hoặc 'staff'")

        f_name = full_name.strip() if full_name else ""
        if not f_name:
            raise ValueError("Họ và tên không được để trống")

        conn = self._get_connection()
        try:
            with transaction(conn):
                self.verify_session(conn, session, required_role="admin")
                existing = UserRepository.get_by_username(conn, u_name)
                if existing:
                    raise ValueError(f"Tên đăng nhập '{u_name}' đã tồn tại")

                pwd_hash, salt = hash_password(password)
                return UserRepository.create(conn, u_name, pwd_hash, salt, role, f_name)
        finally:
            conn.close()

    def update_user(
        self,
        session: AuthSession,
        user_id: int,
        full_name: str,
        role: str,
        active: int,
    ) -> bool:
        """Cập nhật thông tin tài khoản (chỉ Admin)."""
        if role not in ("admin", "staff"):
            raise ValueError("Vai trò người dùng phải là 'admin' hoặc 'staff'")

        if not full_name or not full_name.strip():
            raise ValueError("Họ và tên không được để trống")

        conn = self._get_connection()
        try:
            with transaction(conn):
                self.verify_session(conn, session, required_role="admin")
                target = UserRepository.get_by_id(conn, user_id)
                if not target:
                    raise ValueError("Không tìm thấy tài khoản cần cập nhật")

                # Kiểm tra nếu là admin đang hoạt động mà bị hạ quyền hoặc khóa
                if target["role"] == "admin" and target["active"] == 1:
                    if role != "admin" or active != 1:
                        admin_count = UserRepository.count_active_admins(conn)
                        if admin_count <= 1:
                            raise ValueError("Không thể khóa hoặc hạ quyền Admin hoạt động duy nhất")

                return UserRepository.update(conn, user_id, full_name.strip(), role, active)
        finally:
            conn.close()

    def reset_password(
        self,
        session: AuthSession,
        user_id: int,
        new_password: str,
    ) -> bool:
        """Admin đặt lại mật khẩu cho tài khoản."""
        if not new_password or len(new_password) < 6:
            raise ValueError("Mật khẩu mới phải có ít nhất 6 ký tự")

        conn = self._get_connection()
        try:
            with transaction(conn):
                self.verify_session(conn, session, required_role="admin")
                target = UserRepository.get_by_id(conn, user_id)
                if not target:
                    raise ValueError("Không tìm thấy tài khoản cần đặt lại mật khẩu")

                pwd_hash, salt = hash_password(new_password)
                return UserRepository.update_password(conn, user_id, pwd_hash, salt)
        finally:
            conn.close()

    def list_users(self, session: AuthSession, active_only: bool = False) -> list[dict[str, Any]]:
        """Lấy danh sách tài khoản (chỉ Admin)."""
        conn = self._get_connection()
        try:
            self.verify_session(conn, session, required_role="admin")
            return UserRepository.list_all(conn, active_only=active_only)
        finally:
            conn.close()

