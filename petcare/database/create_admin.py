"""Create the first administrator for an empty PetCare database."""

import getpass
import re
import sys

from petcare.config import Config
from petcare.database.connection import transaction
from petcare.repositories import user_repo
from petcare.security import hash_password


def create_first_admin(username, full_name, password):
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        raise ValueError("Tên đăng nhập cần 3–80 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
    if not full_name or len(full_name) > 160:
        raise ValueError("Họ tên cần từ 1 đến 160 ký tự.")
    password_hash = hash_password(password)

    with transaction() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT GET_LOCK('petcare_first_admin_bootstrap', 10)")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Không lấy được khóa khởi tạo quản trị viên; thử lại sau.")
            cursor.execute("SELECT id FROM users LIMIT 1")
            if cursor.fetchone():
                raise RuntimeError(
                    "Database đã có tài khoản. Không thể chạy khởi tạo admin lần đầu."
                )
            cursor.execute("SELECT id FROM tenants WHERE slug = 'main' AND status = 'active'")
            tenant_id = cursor.fetchone()
            if not tenant_id:
                raise RuntimeError("Chưa khởi tạo schema/store mặc định; hãy chạy initialize trước.")
            return user_repo.create_user(
                connection, username, password_hash, full_name, "owner", tenant_id[0]
            )
        finally:
            try:
                cursor.execute("SELECT RELEASE_LOCK('petcare_first_admin_bootstrap')")
            finally:
                cursor.close()


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Lệnh này cần chạy tương tác trong terminal để nhập mật khẩu an toàn.")
    print(f"Tạo admin đầu tiên trong database: {Config.DB_NAME}")
    confirmation = input("Nhập đúng tên database để tiếp tục: ").strip()
    if confirmation != Config.DB_NAME:
        raise SystemExit("Tên database không khớp; đã dừng mà không thay đổi dữ liệu.")
    username = input("Tên đăng nhập (3–80 ký tự): ").strip()
    full_name = input("Họ tên hiển thị: ").strip()
    password = getpass.getpass("Mật khẩu (ít nhất 8 ký tự): ")
    if password != getpass.getpass("Nhập lại mật khẩu: "):
        raise SystemExit("Mật khẩu không khớp; đã dừng.")
    user_id = create_first_admin(username, full_name, password)
    print(f"Đã tạo quản trị viên đầu tiên (id={user_id}).")


if __name__ == "__main__":
    main()
