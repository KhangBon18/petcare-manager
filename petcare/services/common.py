"""Shared validation and live-authorization helpers."""

from datetime import date
import re

from flask import g, has_request_context

from petcare.repositories.base import fetch_one
from petcare.services.exceptions import ForbiddenError, ValidationError
from petcare.money import CurrencyError, parse_money


PAGE_SIZE = 25
USERNAME_PATTERN = r"[A-Za-z0-9_.-]{3,80}"


def require_actor(connection, actor_id, admin=False):
    tenant = getattr(g, "tenant", None) if has_request_context() else None
    tenant_id = tenant.get("id") if tenant else None
    if tenant_id is None:
        memberships = fetch_one(
            connection,
            "SELECT COUNT(*) membership_count FROM tenant_users tu "
            "JOIN tenants t ON t.id = tu.tenant_id "
            "WHERE tu.user_id = %s AND tu.active = 1 AND t.status = 'active'",
            (actor_id,),
        )
        if not memberships or memberships["membership_count"] != 1:
            raise ForbiddenError("Cần chọn cửa hàng hợp lệ trước khi thao tác.")
        selected = fetch_one(
            connection,
            "SELECT tenant_id FROM tenant_users WHERE user_id = %s AND active = 1",
            (actor_id,),
        )
        tenant_id = selected["tenant_id"]
    user = fetch_one(
        connection,
        "SELECT u.id, IF(tu.role = 'staff', 'staff', 'admin') role, t.name tenant_name, "
        "t.default_currency, t.timezone, "
        "u.active user_active, tu.active membership_active, tu.tenant_id tenant_id "
        "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
        "JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE u.id = %s AND tu.tenant_id = %s AND t.status = 'active'",
        (actor_id, tenant_id),
    )
    if not user or not user["user_active"] or not user["membership_active"]:
        raise ForbiddenError("Tài khoản đã bị khóa hoặc không còn tồn tại.")
    cursor = connection.cursor()
    try:
        cursor.execute("SET @petcare_tenant_id = %s", (tenant_id,))
    finally:
        cursor.close()
    if admin and user["role"] != "admin":
        raise ForbiddenError("Chỉ quản trị viên được thực hiện thao tác này.")
    return user


def text_value(value, label, maximum, required=True):
    value = (value or "").strip()
    if required and not value:
        raise ValidationError(f"{label} không được để trống.")
    if len(value) > maximum:
        raise ValidationError(f"{label} không được dài quá {maximum} ký tự.")
    return value


def username_value(value):
    username = text_value(value, "Tên đăng nhập", 80)
    if not re.fullmatch(USERNAME_PATTERN, username):
        raise ValidationError(
            "Tên đăng nhập cần 3–80 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang."
        )
    return username


def password_hash_value(value):
    """Hash a user-supplied password and translate policy failures to 400-safe errors."""
    from petcare.security import hash_password

    try:
        return hash_password(value)
    except ValueError as exc:
        raise ValidationError("Mật khẩu cần từ 8 đến 1024 ký tự.") from exc


def positive_id(value, label="Mã"):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} không hợp lệ.")
    if result <= 0:
        raise ValidationError(f"{label} không hợp lệ.")
    return result


def integer_value(value, label, minimum=0, maximum=2_000_000_000):
    try:
        raw = str(value).strip()
        if not re.fullmatch(r"-?\d+", raw):
            raise ValueError
        result = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} phải là số nguyên.")
    if result < minimum or result > maximum:
        raise ValidationError(f"{label} nằm ngoài giới hạn cho phép.")
    return result


def money_value(value, label="Giá", currency_code="VND"):
    try:
        return parse_money(value, currency_code, label)
    except (CurrencyError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc


def date_value(value, label="Ngày", allow_empty=True):
    raw = (value or "").strip()
    if not raw and allow_empty:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        raise ValidationError(f"{label} không hợp lệ.")
    if parsed.isoformat() != raw:
        raise ValidationError(f"{label} không hợp lệ.")
    return parsed


def phone_value(value):
    phone = text_value(value, "Số điện thoại", 32)
    compact = re.sub(r"[\s().+-]", "", phone)
    if not compact.isdigit() or not 8 <= len(compact) <= 15:
        raise ValidationError("Số điện thoại cần có từ 8 đến 15 chữ số.")
    return phone


def page_window(value, total, page_size=PAGE_SIZE):
    """Return a bounded page window and display metadata for database lists."""
    raw = str(value or "1")
    requested = int(raw) if re.fullmatch(r"\d{1,7}", raw) else 1
    page_count = max(1, (int(total) + page_size - 1) // page_size)
    page = min(max(1, requested), page_count)
    first = (page - 1) * page_size + 1 if total else 0
    last = min(page * page_size, int(total))
    return page, (page - 1) * page_size, {
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "pages": page_count,
        "first": first,
        "last": last,
        "has_previous": page > 1,
        "has_next": page < page_count,
    }
