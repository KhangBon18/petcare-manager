"""Email verification and password recovery for global user identities."""

import hashlib
import re
import secrets

from flask import current_app, url_for

from petcare.database.connection import read_connection, transaction
from petcare.email_address import normalize_email
from petcare.money import CurrencyError, normalize_currency_code
from petcare.repositories import account_token_repo, audit_repo, user_repo
from petcare.security import hash_password, verify_password
from petcare.services import request_throttle_service
from petcare.services.common import password_hash_value, require_actor, text_value
from petcare.services.exceptions import ForbiddenError, RateLimitError, ValidationError
from petcare.services.mail_service import MailDeliveryError, is_configured, enqueue_text_email
from petcare.timezones import DEFAULT_TIMEZONE, TimezoneError, normalize_timezone_name


_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_EMAIL_VERIFY = "email_verification"
_PASSWORD_RESET = "password_reset"


def _token_hash(token):
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_token(connection, user_id, purpose, ttl_minutes):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    account_token_repo.prune_expired(connection)
    account_token_repo.revoke_open(connection, user_id, purpose)
    expires_at = account_token_repo.create(connection, user_id, purpose, token_hash, ttl_minutes)
    return token, expires_at


def _audit_account_event(connection, user_id, event_type, summary, tenant_ids=None):
    tenant_ids = tenant_ids if tenant_ids is not None else user_repo.active_membership_tenant_ids(connection, user_id)
    for tenant_id in tenant_ids:
        cursor = connection.cursor()
        try:
            cursor.execute("SET @petcare_tenant_id = %s", (tenant_id,))
        finally:
            cursor.close()
        audit_repo.add_event(
            connection, user_id, event_type, "user", user_id, summary, None
        )


def _queue_token_email(email, purpose, token, expires_at, connection=None, required=False):
    if not is_configured():
        return False
    if purpose == _EMAIL_VERIFY:
        endpoint = "account.verify_email"
        subject = "Xác minh email PetCare Manager"
        explanation = "Xác minh địa chỉ email để bảo vệ tài khoản của bạn."
    else:
        endpoint = "account.reset_password"
        subject = "Đặt lại mật khẩu PetCare Manager"
        explanation = "Yêu cầu đặt lại mật khẩu cho tài khoản PetCare Manager."
    link = current_app.config["PUBLIC_BASE_URL"] + url_for(endpoint, token=token)
    body = (
        f"{explanation}\n\nMở liên kết này để tiếp tục (liên kết hết hạn sau thời gian ngắn):\n"
        f"{link}\n\nNếu bạn không yêu cầu thao tác này, hãy bỏ qua email."
    )
    try:
        enqueue_text_email(
            email, subject, body, expires_at=expires_at, connection=connection
        )
        return True
    except MailDeliveryError:
        # Do not include the recipient, token or provider response in application logs.
        current_app.logger.warning("Account email could not be queued (purpose=%s)", purpose)
        if required:
            raise ValidationError("Chưa thể xếp thư xác minh. Kiểm tra cấu hình email rồi thử lại.")
        return False


def _check_limit(identity, scope, message):
    allowed, retry_after = request_throttle_service.consume(identity, scope)
    if not allowed:
        raise RateLimitError(message, retry_after)


def create_public_store(
    owner_name, username, raw_email, password, store_name, slug, remote_addr,
    currency_code="VND", timezone_name=DEFAULT_TIMEZONE,
):
    """Create a new store behind a verifiable owner email and gated public signup."""
    owner_name = (owner_name or "").strip()
    username = (username or "").strip()
    store_name = (store_name or "").strip()
    slug = (slug or "").strip().lower()
    email = normalize_email(raw_email)
    try:
        currency_code = normalize_currency_code(currency_code)
    except CurrencyError as exc:
        raise ValidationError(str(exc)) from exc
    try:
        timezone_name = normalize_timezone_name(timezone_name)
    except TimezoneError as exc:
        raise ValidationError(str(exc)) from exc
    if not 1 <= len(owner_name) <= 160:
        raise ValidationError("Tên chủ cửa hàng cần từ 1 đến 160 ký tự.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        raise ValidationError("Tên đăng nhập cần 3–80 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
    if not email:
        raise ValidationError("Nhập địa chỉ email hợp lệ.")
    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
        raise ValidationError("Mật khẩu cần từ 8 đến 1024 ký tự.")
    if not 1 <= len(store_name) <= 160:
        raise ValidationError("Tên cửa hàng cần từ 1 đến 160 ký tự.")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])", slug):
        raise ValidationError("Mã cửa hàng cần 3–80 ký tự: chữ thường, số và dấu gạch ngang.")

    _check_limit(email, "public_signup_email", "Email này vừa gửi quá nhiều yêu cầu đăng ký.")
    _check_limit(remote_addr or "unknown", "public_signup_ip", "Đã có quá nhiều yêu cầu từ mạng này.")
    password_hash = password_hash_value(password)
    user_id = tenant_id = None
    token = None
    email_queued = False
    try:
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tenants (name, slug, status, default_currency, timezone) "
                    "VALUES (%s, %s, 'active', %s, %s)",
                    (store_name, slug, currency_code, timezone_name),
                )
                tenant_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, full_name, role) "
                    "VALUES (%s, %s, %s, %s, 'admin')",
                    (username, email, password_hash, owner_name),
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO tenant_users "
                    "(tenant_id, user_id, role, active, email_activation_pending) "
                    "VALUES (%s, %s, 'owner', 0, 1)",
                    (tenant_id, user_id),
                )
                cursor.execute("SET @petcare_tenant_id = %s", (tenant_id,))
                audit_repo.add_event(
                    connection,
                    user_id,
                    "tenant.signup_started",
                    "tenant",
                    tenant_id,
                    "Bắt đầu đăng ký cửa hàng tự phục vụ",
                    None,
                )
                token, token_expires_at = _new_token(connection, user_id, _EMAIL_VERIFY, 24 * 60)
                email_queued = _queue_token_email(
                    email,
                    _EMAIL_VERIFY,
                    token,
                    token_expires_at,
                    connection=connection,
                    required=True,
                )
            finally:
                cursor.close()
    except Exception as exc:
        if getattr(exc, "errno", None) in {1062, 1205, 1213}:
            raise ValidationError(
                "Không thể tạo cửa hàng bằng thông tin này. Kiểm tra mã cửa hàng, email và tên đăng nhập rồi thử lại."
            ) from exc
        raise
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "tenant_slug": slug,
        "tenant_name": store_name,
        "email": email,
        "email_queued": email_queued,
        "verification_token": None if email_queued else token,
    }


def set_account_email(actor_id, tenant_id, current_password, raw_email):
    email = normalize_email(raw_email) if raw_email else None
    if raw_email and not email:
        raise ValidationError("Email chưa đúng định dạng. Hãy kiểm tra lại địa chỉ.")
    _check_limit(actor_id, "email_verification", "Bạn thao tác quá nhanh. Vui lòng thử lại sau.")
    token = None
    with transaction() as connection:
        require_actor(connection, actor_id)
        user = user_repo.get_account_by_id_for_update(connection, actor_id)
        if not user or not verify_password(current_password or "", user["password_hash"]):
            raise ForbiddenError("Mật khẩu hiện tại chưa đúng.")
        if user["email"] == email and (not email or user["email_verified_at"]):
            return {"status": "unchanged", "session_version": user["session_version"], "email_sent": False}

        if user["email"] != email:
            if email:
                try:
                    user_repo.update_account_email(connection, actor_id, email)
                except Exception as exc:
                    if getattr(exc, "errno", None) == 1062:
                        raise ValidationError("Email này đã được dùng cho một tài khoản khác.") from exc
                    raise
                event_type, summary = "account.email_changed", "Cập nhật email tài khoản"
            else:
                user_repo.remove_account_email(connection, actor_id)
                event_type, summary = "account.email_removed", "Gỡ email tài khoản"
            account_token_repo.revoke_open(connection, actor_id, _EMAIL_VERIFY)
            account_token_repo.revoke_open(connection, actor_id, _PASSWORD_RESET)
            _audit_account_event(connection, actor_id, event_type, summary, [tenant_id])
        if email:
            token, token_expires_at = _new_token(connection, actor_id, _EMAIL_VERIFY, 24 * 60)
        else:
            token_expires_at = None
        new_version = int(user["session_version"]) + (1 if user["email"] != email else 0)

    return {
        "status": "verification_pending" if email else "removed",
        "session_version": new_version,
        "email_sent": _queue_token_email(email, _EMAIL_VERIFY, token, token_expires_at) if token else False,
    }


def update_account_profile(actor_id, current_password, raw_full_name):
    full_name = text_value(raw_full_name, "Tên hiển thị", 160)
    with transaction() as connection:
        require_actor(connection, actor_id)
        user = user_repo.get_account_by_id_for_update(connection, actor_id)
        if (
            not user
            or not user["active"]
            or not verify_password(current_password or "", user["password_hash"])
        ):
            raise ForbiddenError("Mật khẩu hiện tại chưa đúng.")
        if user["full_name"] == full_name:
            return {"status": "unchanged"}
        user_repo.update_account_profile(connection, actor_id, full_name)
        _audit_account_event(
            connection, actor_id, "account.profile_updated", "Cập nhật tên hiển thị tài khoản"
        )
    return {"status": "updated"}


def resend_email_verification(actor_id):
    _check_limit(actor_id, "email_verification", "Bạn đã yêu cầu xác minh gần đây. Vui lòng thử lại sau.")
    with transaction() as connection:
        user = user_repo.get_account_by_id_for_update(connection, actor_id)
        if not user or not user["active"] or not user["email"] or user["email_verified_at"]:
            return {"status": "not_pending", "email_sent": False}
        token, token_expires_at = _new_token(connection, actor_id, _EMAIL_VERIFY, 24 * 60)
        email = user["email"]
    return {
        "status": "verification_pending",
        "email_sent": _queue_token_email(email, _EMAIL_VERIFY, token, token_expires_at),
    }


def preview_email_verification(token):
    token_hash = _token_hash(token)
    if not token_hash:
        return False
    with read_connection() as connection:
        return account_token_repo.user_id_for_hash(connection, token_hash, _EMAIL_VERIFY) is not None


def verify_account_email(token):
    token_hash = _token_hash(token)
    if not token_hash:
        return False
    with read_connection() as connection:
        user_id = account_token_repo.user_id_for_hash(connection, token_hash, _EMAIL_VERIFY)
    if not user_id:
        return False
    with transaction() as connection:
        user = user_repo.get_account_by_id_for_update(connection, user_id)
        token_row = account_token_repo.get_open_for_update(
            connection, token_hash, _EMAIL_VERIFY, user_id
        )
        if not user or not user["active"] or not user["email"] or not token_row:
            return False
        if user["email_verified_at"]:
            account_token_repo.consume(connection, token_row["id"])
            return True
        if not user_repo.mark_email_verified(connection, user_id):
            return False
        user_repo.activate_email_pending_memberships(connection, user_id)
        account_token_repo.consume_open_for_user(connection, user_id, _EMAIL_VERIFY)
        _audit_account_event(
            connection, user_id, "account.email_verified", "Xác minh email tài khoản"
        )
    return True


def request_password_reset(raw_email, remote_addr):
    email = normalize_email(raw_email)
    limit_identity = email or "invalid-email"
    _check_limit(limit_identity, "password_reset", "Vui lòng đợi trước khi yêu cầu hướng dẫn khác.")
    _check_limit(
        remote_addr or "unknown",
        "password_reset_ip",
        "Vui lòng đợi trước khi thử lại.",
    )
    if not email or not is_configured():
        return {"email_sent": False}

    with transaction() as connection:
        user = user_repo.get_verified_account_by_email_for_update(connection, email)
        if not user:
            return {"email_sent": False}
        token, token_expires_at = _new_token(connection, user["id"], _PASSWORD_RESET, 30)
        user_id = user["id"]

    return {
        "email_sent": _queue_token_email(email, _PASSWORD_RESET, token, token_expires_at),
        "user_id": user_id,
    }


def preview_password_reset(token):
    token_hash = _token_hash(token)
    if not token_hash:
        return False
    with read_connection() as connection:
        return account_token_repo.user_id_for_hash(connection, token_hash, _PASSWORD_RESET) is not None


def reset_password(token, password, confirmation):
    token_hash = _token_hash(token)
    if not token_hash:
        return False
    if not isinstance(password, str) or password != confirmation:
        raise ValidationError("Hai lần nhập mật khẩu chưa khớp.")
    password_hash = password_hash_value(password)
    with read_connection() as connection:
        user_id = account_token_repo.user_id_for_hash(connection, token_hash, _PASSWORD_RESET)
    if not user_id:
        return False
    with transaction() as connection:
        user = user_repo.get_account_by_id_for_update(connection, user_id)
        token_row = account_token_repo.get_open_for_update(
            connection, token_hash, _PASSWORD_RESET, user_id
        )
        if (
            not user or not user["active"] or not user["email_verified_at"]
            or not token_row
        ):
            return False
        if not user_repo.update_password_from_reset(connection, user_id, password_hash):
            return False
        account_token_repo.consume_open_for_user(connection, user_id, _PASSWORD_RESET)
        _audit_account_event(
            connection, user_id, "account.password_reset", "Đặt lại mật khẩu qua email"
        )
    return True
