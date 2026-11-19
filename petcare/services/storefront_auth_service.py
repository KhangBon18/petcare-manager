"""Customer account registration, authentication, and session isolation."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from flask import current_app
from mysql.connector import IntegrityError

from petcare.database.connection import read_connection, set_tenant_context, transaction
from petcare.email_address import normalize_email
from petcare.repositories import login_throttle_repo, storefront_repo
from petcare.security import hash_password, verify_password
from petcare.services.common import text_value
from petcare.services.exceptions import ConflictError, ValidationError


_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))
_PHONE_RE = re.compile(r"^[0-9]{8,15}$")


def normalize_phone(value: str) -> str:
    digits = re.sub(r"[\s().-]+", "", (value or "").strip())
    if digits.startswith("+84") and len(digits) > 3:
        digits = "0" + digits[3:]
    elif digits.startswith("+"):
        digits = digits[1:]
    if not _PHONE_RE.fullmatch(digits):
        raise ValidationError("Số điện thoại cần 8 đến 15 chữ số hợp lệ.")
    return digits


def _throttle_keys(tenant_id: int, email: str, remote_addr: str):
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    identities = []
    if email:
        identities.append(("customer_account", f"{tenant_id}:{email.casefold()[:200]}"))
    identities.append(("customer_address", f"{tenant_id}:{(remote_addr or 'unknown')[:80]}"))
    return sorted(
        (
            scope,
            hmac.new(secret, f"cust_login:{scope}:{val}".encode("utf-8"), hashlib.sha256).hexdigest(),
        )
        for scope, val in identities
    )


def customer_login_blocked(tenant_id: int, email: str, remote_addr: str) -> bool:
    keys = [key for _, key in _throttle_keys(tenant_id, email, remote_addr)]
    with read_connection() as connection:
        return login_throttle_repo.is_blocked(connection, keys)


def record_customer_login_failure(tenant_id: int, email: str, remote_addr: str) -> bool:
    keys = _throttle_keys(tenant_id, email, remote_addr)
    with transaction() as connection:
        blocked = False
        for scope, key in keys:
            threshold = 10 if scope == "customer_account" else 40
            blocked = login_throttle_repo.record_failure(connection, key, threshold) or blocked
        login_throttle_repo.prune_old(connection)
    return blocked


def clear_customer_login_failures(tenant_id: int, email: str, remote_addr: str) -> None:
    keys = [key for scope, key in _throttle_keys(tenant_id, email, remote_addr) if scope == "customer_account"]
    with transaction() as connection:
        login_throttle_repo.clear(connection, keys)


def register_customer(tenant_id: int, data: dict) -> dict:
    try:
        email = normalize_email(data.get("email", ""))
    except ValueError as exc:
        raise ValidationError(str(exc), field="email") from exc
    full_name = text_value(data.get("full_name"), "Họ tên", 160)
    phone = normalize_phone(data.get("phone", ""))
    address = text_value(data.get("default_address"), "Địa chỉ", 255, required=False)
    password = data.get("password") or ""
    if not isinstance(password, str) or len(password) < 8 or len(password) > 1024:
        raise ValidationError("Mật khẩu cần từ 8 đến 1024 ký tự.", field="password")
    password_hash = hash_password(password)

    with transaction() as connection:
        set_tenant_context(connection, tenant_id)
        try:
            account_id = storefront_repo.create_account(
                connection, email, password_hash, full_name, phone, address
            )
        except IntegrityError as exc:
            raise ConflictError("Email này đã được đăng ký tài khoản mua hàng.") from exc
        account = storefront_repo.get_account_by_id(connection, account_id)
    return _safe_account(account)


def authenticate_customer(tenant_id: int, raw_email: str, raw_password: str) -> dict | None:
    try:
        email = normalize_email(raw_email) if isinstance(raw_email, str) and raw_email.strip() else ""
    except ValueError:
        email = ""
    password = raw_password if isinstance(raw_password, str) else ""
    valid_password = 1 <= len(password) <= 1024
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        account = storefront_repo.get_account_by_email(connection, email) if email else None
    matched = verify_password(
        password if valid_password else "",
        account["password_hash"] if account else _DUMMY_PASSWORD_HASH,
    )
    if not email or not valid_password or not account or not account["active"] or not matched:
        return None
    return _safe_account(account)


def load_active_customer(account_id: int, tenant_id: int, session_version: int | None) -> dict | None:
    if not account_id or not tenant_id:
        return None
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        account = storefront_repo.get_account_by_id(connection, account_id)
    if not account or not account["active"]:
        return None
    if account["session_version"] != session_version:
        return None
    return _safe_account(account)


def update_customer_profile(tenant_id: int, account_id: int, data: dict) -> dict:
    full_name = text_value(data.get("full_name"), "Họ tên", 160)
    phone = normalize_phone(data.get("phone", ""))
    address = text_value(data.get("default_address"), "Địa chỉ", 255, required=False)
    with transaction() as connection:
        set_tenant_context(connection, tenant_id)
        storefront_repo.update_account_profile(connection, account_id, full_name, phone, address)
        account = storefront_repo.get_account_by_id(connection, account_id)
    return _safe_account(account)


def _safe_account(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "tenant_id": int(row["tenant_id"]),
        "email": row["email"],
        "full_name": row["full_name"],
        "phone": row["phone"],
        "default_address": row["default_address"],
        "session_version": int(row["session_version"]),
    }

