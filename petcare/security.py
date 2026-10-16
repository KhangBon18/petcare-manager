"""Bảo mật mật khẩu sử dụng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên."""

import hashlib
import hmac
import secrets


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Băm mật khẩu sử dụng PBKDF2-HMAC-SHA256 với 100,000 vòng lặp.

    Trả về tuple: (password_hash, salt) dưới dạng chuỗi hex.
    """
    if not password:
        raise ValueError("Mật khẩu không được để trống")
    if salt is None:
        salt = secrets.token_hex(16)
    
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return key.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """So sánh an toàn mật khẩu nhập vào với mật khẩu đã băm."""
    if not password or not password_hash or not salt:
        return False
    computed_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, password_hash)
