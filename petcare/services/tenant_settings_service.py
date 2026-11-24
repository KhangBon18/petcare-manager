"""Business rules for the selected store's editable profile and public storefront policies."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

import mysql.connector

from petcare.database.connection import read_connection, transaction
from petcare.email_address import normalize_email
from petcare.repositories import audit_repo, tenant_repo
from petcare.repositories.tenant_repo import PUBLIC_POLICY_COLUMNS
from petcare.services.common import require_actor, text_value
from petcare.services.exceptions import ForbiddenError, ValidationError
from petcare.timezones import TimezoneError, normalize_timezone_name


PUBLIC_POLICY_LIMITS = {
    "pickup_address": ("Địa chỉ nhận hàng tại quầy", 300),
    "opening_hours": ("Giờ mở cửa", 200),
    "cod_service_area_fees": ("Khu vực & phí giao COD", 400),
    "order_confirmation_sla": ("Thời gian xác nhận & giao dự kiến", 200),
    "return_refund_policy": ("Chính sách đổi trả & hoàn tiền", 600),
    "cancellation_instructions": ("Hướng dẫn hủy / liên hệ chỉnh đơn", 400),
    "pet_handover_policy": ("Chính sách bàn giao & sức khỏe thú cưng", 600),
    "support_hotline": ("Hotline hỗ trợ", 60),
    "support_zalo": ("Kênh Zalo hỗ trợ", 160),
    "support_email": ("Email CSKH công khai", 254),
    "privacy_terms_url": ("Liên kết điều khoản / bảo mật", 300),
    "privacy_terms_summary": ("Tóm tắt quyền riêng tư & điều khoản", 400),
}

_HOTLINE_RE = re.compile(r"^[0-9+\-\s().]{6,60}$")
_ZALO_HANDLE_RE = re.compile(r"^[A-Za-z0-9@+._\-\s]{3,160}$")
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HOSTNAME_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_NUMERIC_HOST_LABEL_RE = re.compile(r"^(?:[0-9]+|0[xX][0-9A-Fa-f]+)$")


def _clean_text(value: object, label: str, maximum: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{label} không hợp lệ.")
    cleaned = _CTRL_CHARS_RE.sub("", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if len(cleaned) > maximum:
        raise ValidationError(f"{label} không được vượt quá {maximum} ký tự.")
    return cleaned


def _is_valid_url_hostname(hostname: str, *, bracketed: bool | None = None) -> bool:
    if not hostname or any(ch in hostname for ch in "%\\[]"):
        return False

    is_ipv6_host = bracketed if bracketed is not None else (":" in hostname)
    if is_ipv6_host:
        try:
            ipaddress.IPv6Address(hostname)
            return True
        except ValueError:
            return False

    if ":" in hostname:
        return False

    try:
        ipaddress.IPv4Address(hostname)
        return True
    except ValueError:
        pass

    dns_host = hostname[:-1] if hostname.endswith(".") else hostname
    if (
        not dns_host
        or len(dns_host) > 253
        or dns_host.startswith(".")
        or dns_host.endswith(".")
        or ".." in dns_host
    ):
        return False

    try:
        ascii_host = dns_host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return False

    if not ascii_host or len(ascii_host) > 253:
        return False

    labels = ascii_host.split(".")
    if not all(bool(_HOSTNAME_LABEL_RE.fullmatch(part)) for part in labels):
        return False
    return not _NUMERIC_HOST_LABEL_RE.fullmatch(labels[-1])


def _validated_http_url(raw: str, label: str) -> str:
    if not raw:
        return ""
    if any(ch.isspace() for ch in raw):
        raise ValidationError(f"{label} không được chứa khoảng trắng.")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise ValidationError(f"{label} không hợp lệ.") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValidationError(f"{label} phải là liên kết bắt đầu bằng http:// hoặc https://.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise ValidationError(f"{label} không được chứa thông tin đăng nhập.")
    if "\\" in parts.netloc:
        raise ValidationError(f"{label} không hợp lệ.")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValidationError(f"{label} không hợp lệ.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValidationError(f"{label} không hợp lệ.")
    hostname = (parts.hostname or "").strip()
    if not _is_valid_url_hostname(hostname, bracketed=parts.netloc.startswith("[")):
        raise ValidationError(f"{label} không hợp lệ.")
    return raw


def _is_safe_http_href(raw: str) -> str:
    if not raw:
        return ""
    try:
        return _validated_http_url(raw, "URL")
    except ValidationError:
        return ""


def _enrich_policies(row: dict | None) -> dict:
    data = {col: str((row or {}).get(col) or "") for col in PUBLIC_POLICY_COLUMNS}
    configured_count = sum(1 for col in PUBLIC_POLICY_COLUMNS if bool(data[col]))
    checkout_fields = (
        "pickup_address",
        "opening_hours",
        "cod_service_area_fees",
        "order_confirmation_sla",
        "return_refund_policy",
        "cancellation_instructions",
        "support_hotline",
    )
    has_checkout_policy = any(bool(data[f]) for f in checkout_fields)
    has_contact_info = any(
        bool(data[f]) for f in ("support_hotline", "support_zalo", "support_email", "opening_hours")
    )
    zalo_raw = data["support_zalo"]
    support_zalo_href = (
        _is_safe_http_href(zalo_raw)
        if zalo_raw.lower().startswith(("http://", "https://"))
        else ""
    )
    data.update({
        "configured_count": configured_count,
        "total_fields": len(PUBLIC_POLICY_COLUMNS),
        "has_any_policy": configured_count > 0,
        "has_checkout_policy": has_checkout_policy,
        "has_contact_info": has_contact_info,
        "has_missing_checkout_essentials": not all(
            bool(data[f]) for f in ("pickup_address", "cod_service_area_fees", "support_hotline")
        ),
        "privacy_terms_href": _is_safe_http_href(data["privacy_terms_url"]),
        "support_zalo_href": support_zalo_href,
        "updated_at": (row or {}).get("updated_at"),
    })
    return data


def empty_public_policies() -> dict:
    return _enrich_policies(None)


def get_public_store_policies(tenant_id: int) -> dict:
    with read_connection() as connection:
        row = tenant_repo.get_public_policies(connection, int(tenant_id))
    return _enrich_policies(row)


def get_public_store_policies_safe(tenant_id: int) -> dict:
    try:
        return get_public_store_policies(tenant_id)
    except mysql.connector.Error:
        return empty_public_policies()


def update_store_profile(actor_id, name, timezone_name, tenant_id=None):
    name = text_value(name, "Tên cửa hàng", 160)
    try:
        timezone_name = normalize_timezone_name(timezone_name)
    except TimezoneError as exc:
        raise ValidationError(str(exc)) from exc

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        tenant = tenant_repo.get_for_update(connection, actor["tenant_id"])
        if not tenant or tenant["status"] != "active":
            raise ForbiddenError("Cửa hàng không còn hoạt động.")

        changed_fields = []
        if tenant["name"] != name:
            changed_fields.append("name")
        if tenant["timezone"] != timezone_name:
            changed_fields.append("timezone")
        if not changed_fields:
            return {"status": "unchanged"}

        tenant_repo.update_profile(
            connection, tenant["id"], name, timezone_name
        )
        audit_repo.add_event(
            connection,
            actor_id,
            "tenant.settings_updated",
            "tenant",
            tenant["id"],
            "Cập nhật cài đặt cửa hàng",
            {"changed_fields": changed_fields},
        )
    return {"status": "updated"}


def update_public_policies(actor_id, raw_data, tenant_id=None):
    cleaned: dict[str, str] = {}
    field_errors: dict[str, str] = {}

    for col, (label, maximum) in PUBLIC_POLICY_LIMITS.items():
        try:
            cleaned[col] = _clean_text(raw_data.get(col, ""), label, maximum)
        except ValidationError as exc:
            field_errors[col] = str(exc)
            cleaned[col] = ""

    hotline = cleaned.get("support_hotline", "")
    if hotline and "support_hotline" not in field_errors:
        digits = re.sub(r"\D", "", hotline)
        if not _HOTLINE_RE.fullmatch(hotline) or not 6 <= len(digits) <= 20:
            field_errors["support_hotline"] = "Hotline hỗ trợ chỉ dùng chữ số, khoảng trắng, +, -, ( ) và dài từ 6–20 chữ số."

    zalo = cleaned.get("support_zalo", "")
    if zalo and "support_zalo" not in field_errors:
        if zalo.lower().startswith(("http://", "https://")) or "://" in zalo or ":" in zalo:
            try:
                cleaned["support_zalo"] = _validated_http_url(zalo, "Liên kết Zalo")
            except ValidationError as exc:
                field_errors["support_zalo"] = str(exc)
        elif not _ZALO_HANDLE_RE.fullmatch(zalo):
            field_errors["support_zalo"] = "Kênh Zalo cần là số điện thoại/ID hợp lệ hoặc URL bắt đầu bằng https://."

    email = cleaned.get("support_email", "")
    if email and "support_email" not in field_errors:
        normalized_email = normalize_email(email)
        if not normalized_email:
            field_errors["support_email"] = "Email CSKH công khai không đúng định dạng."
        else:
            cleaned["support_email"] = normalized_email

    terms_url = cleaned.get("privacy_terms_url", "")
    if terms_url and "privacy_terms_url" not in field_errors:
        try:
            cleaned["privacy_terms_url"] = _validated_http_url(terms_url, "Liên kết điều khoản / bảo mật")
        except ValidationError as exc:
            field_errors["privacy_terms_url"] = str(exc)

    if field_errors:
        raise ValidationError(
            "Vui lòng kiểm tra lại thông tin chính sách công khai.",
            field_errors=field_errors,
        )

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        tenant = tenant_repo.get_for_update(connection, actor["tenant_id"])
        if not tenant or tenant["status"] != "active":
            raise ForbiddenError("Cửa hàng không còn hoạt động.")

        existing = tenant_repo.get_public_policies(connection, tenant["id"]) or {}
        changed_fields = [
            col for col in PUBLIC_POLICY_COLUMNS if str(existing.get(col) or "") != cleaned[col]
        ]
        if not changed_fields:
            return {"status": "unchanged"}

        tenant_repo.upsert_public_policies(connection, tenant["id"], cleaned, actor_id)
        audit_repo.add_event(
            connection,
            actor_id,
            "tenant.public_policies_updated",
            "tenant",
            tenant["id"],
            "Cập nhật thông tin & chính sách công khai Storefront",
            {"changed_fields": changed_fields},
        )
    return {"status": "updated", "changed_fields": changed_fields}
