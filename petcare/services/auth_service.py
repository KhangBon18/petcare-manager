import hashlib
import hmac
import secrets

from flask import current_app

from petcare.database.connection import read_connection, transaction
from petcare.i18n import SUPPORTED_LOCALES
from petcare.repositories import account_token_repo, audit_repo, login_throttle_repo, user_repo
from petcare.security import hash_password, verify_password
from petcare.services.common import password_hash_value, require_actor, username_value, text_value
from petcare.services.exceptions import ConflictError, ForbiddenError, ValidationError


_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def _login_throttle_keys(username, remote_addr):
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    identities = []
    normalized_username = (username or "").strip().casefold()[:80]
    if normalized_username:
        identities.append(("account", normalized_username))
    identities.append(("address", (remote_addr or "unknown")[:80]))
    return sorted(
        (
            scope,
            hmac.new(
                secret, f"login:{scope}:{value}".encode("utf-8"), hashlib.sha256
            ).hexdigest(),
        )
        for scope, value in identities
    )


def login_blocked(username, remote_addr):
    keys = [key for _, key in _login_throttle_keys(username, remote_addr)]
    with read_connection() as connection:
        return login_throttle_repo.is_blocked(connection, keys)


def record_login_failure(username, remote_addr):
    keys = _login_throttle_keys(username, remote_addr)
    with transaction() as connection:
        # Stable order keeps simultaneous requests from deadlocking on shared keys.
        blocked = False
        for scope, key in keys:
            threshold = 10 if scope == "account" else 40
            blocked = login_throttle_repo.record_failure(connection, key, threshold) or blocked
        login_throttle_repo.prune_old(connection)
    return blocked


def clear_login_failures(username, remote_addr):
    # Clear the account-specific counter after a valid login. Keep the shared
    # address counter so another valid account cannot erase its abuse history.
    keys = [key for scope, key in _login_throttle_keys(username, remote_addr) if scope == "account"]
    with transaction() as connection:
        login_throttle_repo.clear(connection, keys)


def authenticate(username, password, tenant_slug="main"):
    username = username.strip() if isinstance(username, str) else ""
    tenant_slug = tenant_slug.strip().lower() if isinstance(tenant_slug, str) else ""
    password = password if isinstance(password, str) else ""
    valid_username = 1 <= len(username) <= 80
    valid_password = len(password) <= 1024
    with read_connection() as connection:
        user = user_repo.get_by_username(connection, username) if valid_username else None
    password_matches = verify_password(
        password if valid_password else "" ,
        user["password_hash"] if user else _DUMMY_PASSWORD_HASH,
    )
    if not valid_username or not valid_password or not user or not user["active"] or not password_matches:
        return None
    with read_connection() as connection:
        membership = user_repo.get_membership_by_slug(connection, user["id"], tenant_slug)
    if not membership or not membership["active"]:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "email_verified_at": user["email_verified_at"],
        "full_name": user["full_name"],
        "preferred_locale": user["preferred_locale"],
        "session_version": user["session_version"],
        "role": "staff" if membership["role"] == "staff" else "admin",
        "tenant_id": membership["tenant_id"],
        "tenant_name": membership["tenant_name"],
        "tenant_slug": membership["tenant_slug"],
        "default_currency": membership["default_currency"],
        "timezone": membership["timezone"],
    }


def record_auth_event(user_id, tenant_id, event_type, summary):
    """Append a tenant-scoped authentication event without storing request PII."""
    allowed_events = {
        "auth.login_succeeded",
        "auth.logout",
        "auth.store_switched",
    }
    if event_type not in allowed_events:
        raise ValueError("Unsupported authentication audit event.")

    with transaction() as connection:
        membership = user_repo.get_active_membership(connection, user_id, tenant_id)
        if not membership:
            return False
        cursor = connection.cursor()
        try:
            cursor.execute("SET @petcare_tenant_id = %s", (tenant_id,))
        finally:
            cursor.close()
        audit_repo.add_event(
            connection,
            user_id,
            event_type,
            "session",
            None,
            summary,
            {"authentication_method": "password"} if event_type == "auth.login_succeeded" else None,
        )
    return True


def load_active_user(user_id, tenant_id=None, session_version=None):
    if session_version is None:
        return None
    with read_connection() as connection:
        memberships = user_repo.list_memberships(connection, user_id)
        if tenant_id is None:
            membership = memberships[0] if len(memberships) == 1 else None
            tenant_id = membership["tenant_id"] if membership else None
        user = user_repo.get_by_id(connection, user_id, tenant_id) if tenant_id else None
    if (
        not user
        or not user["active"]
        or int(user["session_version"]) != int(session_version)
    ):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "email_verified_at": user["email_verified_at"],
        "full_name": user["full_name"],
        "preferred_locale": user["preferred_locale"],
        "role": user["role"],
        "store_memberships": memberships,
        "tenant": {
            "id": user["tenant_id"],
            "name": user["tenant_name"],
            "slug": user["tenant_slug"],
            "default_currency": user["default_currency"],
            "timezone": user["timezone"],
        },
    }


def update_preferred_locale(user_id, locale):
    if locale not in SUPPORTED_LOCALES:
        raise ValidationError("Ngôn ngữ không được hỗ trợ.")
    with transaction() as connection:
        user_repo.update_preferred_locale(connection, user_id, locale)


def store_membership(user_id, slug):
    with read_connection() as connection:
        membership = user_repo.get_membership_by_slug(connection, user_id, slug)
    return membership if membership and membership["active"] else None


def list_users(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        return user_repo.list_users(connection, actor["tenant_id"])


def create_user(actor_id, data):
    username = username_value(data.get("username"))
    full_name = text_value(data.get("full_name"), "Họ tên", 160)
    role = data.get("role", "staff")
    if role not in ("admin", "staff"):
        raise ValidationError("Vai trò không hợp lệ.")
    password_hash = password_hash_value(data.get("password", ""))
    try:
        with transaction() as connection:
            actor = require_actor(connection, actor_id, admin=True)
            user_id = user_repo.create_user(
                connection, username, password_hash, full_name, role, actor["tenant_id"]
            )
            audit_repo.add_event(
                connection, actor_id, "user.created", "user", user_id,
                f"Tạo tài khoản #{user_id} ({role})", {"role": role},
            )
            return user_id
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Tên đăng nhập đã được sử dụng.") from exc
        raise


def update_user(actor_id, user_id, data):
    full_name = text_value(data.get("full_name"), "Họ tên", 160)
    role = data.get("role", "staff")
    active = data.get("active") == "1"
    if role not in ("admin", "staff"):
        raise ValidationError("Vai trò không hợp lệ.")
    password = data.get("password") or ""
    password_hash = password_hash_value(password) if password else None
    try:
        with transaction() as connection:
            actor = require_actor(connection, actor_id, admin=True)
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT user_id FROM tenant_users WHERE tenant_id = %s "
                    "AND role IN ('owner', 'admin') AND active = 1 "
                    "ORDER BY user_id FOR UPDATE",
                    (actor["tenant_id"],),
                )
                active_admin_ids = {row[0] for row in cursor.fetchall()}
            finally:
                cursor.close()
            user = user_repo.get_by_id_for_update(connection, user_id, actor["tenant_id"])
            if not user:
                raise ValidationError("Không tìm thấy tài khoản.")
            if user["membership_role"] == "owner":
                raise ForbiddenError(
                    "Không thể đổi vai trò hoặc khóa chủ cửa hàng tại đây. "
                    "Tên và email được quản lý trong Cài đặt tài khoản; "
                    "mật khẩu dùng luồng Quên mật khẩu."
                )
            if password_hash or full_name != user["full_name"]:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM tenant_users WHERE user_id = %s",
                        (user_id,),
                    )
                    membership_count = cursor.fetchone()[0]
                finally:
                    cursor.close()
                if password_hash and membership_count > 1:
                    raise ForbiddenError(
                        "Tài khoản đang dùng ở nhiều cửa hàng; không thể đổi mật khẩu từ một cửa hàng riêng lẻ."
                    )
                if full_name != user["full_name"] and membership_count > 1:
                    raise ForbiddenError(
                        "Tài khoản đang dùng ở nhiều cửa hàng; người dùng cần đổi tên hiển thị trong cài đặt tài khoản."
                    )
            if user["id"] == actor["id"] and (not active or role != "admin"):
                raise ForbiddenError("Không thể tự khóa hoặc tự hạ quyền quản trị của mình.")
            if user["id"] in active_admin_ids and (
                not active or role != "admin"
            ):
                if len(active_admin_ids) <= 1:
                    raise ForbiddenError("Không thể khóa hoặc hạ quyền quản trị viên cuối cùng.")
            changed = user_repo.update_user(
                connection, user_id, actor["tenant_id"], full_name, role,
                int(active), password_hash,
                invalidate_sessions=bool(user["active"]) != bool(active),
            )
            if changed:
                if password_hash:
                    account_token_repo.consume_open_for_user(
                        connection, user_id, "email_verification"
                    )
                    account_token_repo.consume_open_for_user(
                        connection, user_id, "password_reset"
                    )
                audit_repo.add_event(
                    connection, actor_id, "user.updated", "user", user_id,
                    f"Cập nhật tài khoản #{user_id}",
                    {"role": role, "active": bool(active), "password_changed": bool(password_hash)},
                )
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Không thể cập nhật tài khoản.") from exc
        raise
