"""Provision a store and its first owner in an existing SaaS database."""

import getpass
import re
import sys

from petcare.config import Config
from petcare.database.connection import transaction
from petcare.money import CurrencyError, normalize_currency_code
from petcare.timezones import DEFAULT_TIMEZONE, TimezoneError, normalize_timezone_name
from petcare.security import hash_password, verify_password


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,80}$")


def create_store(
    slug, store_name, username, full_name, password, currency_code="VND",
    timezone_name=DEFAULT_TIMEZONE,
):
    slug = (slug or "").strip().lower()
    store_name = (store_name or "").strip()
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    try:
        currency_code = normalize_currency_code(currency_code)
    except CurrencyError as exc:
        raise ValueError(str(exc)) from exc
    try:
        timezone_name = normalize_timezone_name(timezone_name)
    except TimezoneError as exc:
        raise ValueError(str(exc)) from exc
    if not SLUG_RE.fullmatch(slug):
        raise ValueError("Mã cửa hàng cần 3–80 ký tự: chữ thường, số và dấu gạch ngang.")
    if not 1 <= len(store_name) <= 160:
        raise ValueError("Tên cửa hàng cần từ 1 đến 160 ký tự.")
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Tên đăng nhập cần 3–80 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
    if not 1 <= len(full_name) <= 160:
        raise ValueError("Tên chủ cửa hàng cần từ 1 đến 160 ký tự.")
    password_hash = hash_password(password)

    with transaction() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT GET_LOCK('petcare_store_provisioning', 10)")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Không lấy được khóa tạo cửa hàng; thử lại sau.")
            cursor.execute(
                "INSERT INTO tenants (name, slug, status, default_currency, timezone) "
                "VALUES (%s, %s, 'active', %s, %s)",
                (store_name, slug, currency_code, timezone_name),
            )
            tenant_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, password_hash, active FROM users WHERE username = %s FOR UPDATE",
                (username,),
            )
            existing_user = cursor.fetchone()
            if existing_user:
                if not existing_user[2] or not verify_password(password, existing_user[1]):
                    raise ValueError("Tài khoản đã tồn tại; mật khẩu hiện tại không đúng.")
                user_id = existing_user[0]
            else:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) "
                    "VALUES (%s, %s, %s, 'admin')",
                    (username, password_hash, full_name),
                )
                user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO tenant_users (tenant_id, user_id, role, active) "
                "VALUES (%s, %s, 'owner', 1)",
                (tenant_id, user_id),
            )
            return tenant_id, user_id
        except Exception as exc:
            if getattr(exc, "errno", None) == 1062:
                raise ValueError("Mã cửa hàng hoặc tên đăng nhập đã được sử dụng.") from exc
            raise
        finally:
            try:
                cursor.execute("SELECT RELEASE_LOCK('petcare_store_provisioning')")
                cursor.fetchone()
            finally:
                cursor.close()


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Lệnh này cần chạy tương tác trong terminal để nhập mật khẩu an toàn.")
    print(f"Tạo cửa hàng trong database SaaS: {Config.DB_NAME}")
    confirmation = input("Nhập đúng tên database để tiếp tục: ").strip()
    if confirmation != Config.DB_NAME:
        raise SystemExit("Tên database không khớp; đã dừng mà không thay đổi dữ liệu.")
    slug = input("Mã cửa hàng (ví dụ: petcare-hanoi): ").strip()
    store_name = input("Tên cửa hàng: ").strip()
    username = input("Tên đăng nhập chủ cửa hàng: ").strip()
    full_name = input("Tên chủ cửa hàng: ").strip()
    currency_code = input("Mã tiền tệ ISO 4217 (mặc định VND): ").strip().upper() or "VND"
    timezone_name = input("Tên múi giờ IANA (mặc định Asia/Ho_Chi_Minh): ").strip() or DEFAULT_TIMEZONE
    password = getpass.getpass("Mật khẩu (ít nhất 8 ký tự): ")
    if password != getpass.getpass("Nhập lại mật khẩu: "):
        raise SystemExit("Mật khẩu không khớp; đã dừng.")
    tenant_id, user_id = create_store(
        slug, store_name, username, full_name, password, currency_code, timezone_name
    )
    print(f"Đã tạo cửa hàng #{tenant_id} và tài khoản chủ cửa hàng #{user_id}.")
    print(f"Đăng nhập với mã cửa hàng: {slug}")


if __name__ == "__main__":
    main()
