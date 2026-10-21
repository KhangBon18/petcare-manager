"""Business rules for manual, short-lived tenant invitations."""

import hashlib
import re
import secrets

from flask import current_app, url_for

from petcare.database.connection import read_connection, transaction
from petcare.email_address import normalize_email
from petcare.repositories import audit_repo, invitation_repo
from petcare.services import mail_service, request_throttle_service
from petcare.services.common import require_actor
from petcare.services.exceptions import ConflictError, NotFoundError, RateLimitError, ValidationError
from petcare.security import hash_password, verify_password


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,80}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _token_hash(token):
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_invitation(actor_id, email, role="staff"):
    if role not in {"staff", "admin"}:
        raise ValidationError("Vai trò lời mời không hợp lệ.")
    email = normalize_email(email)
    if not email:
        raise ValidationError("Nhập địa chỉ email hợp lệ cho thành viên được mời.")
    allowed, retry_after = request_throttle_service.consume(actor_id, "tenant_invitation")
    if not allowed:
        raise RateLimitError("Bạn đã tạo quá nhiều lời mời gần đây. Vui lòng thử lại sau.", retry_after)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    email_queued = mail_service.is_configured()
    try:
        with transaction() as connection:
            actor = require_actor(connection, actor_id, admin=True)
            if invitation_repo.get_open_for_email(connection, actor["tenant_id"], email):
                raise ConflictError("Email này đã có lời mời đang chờ trong cửa hàng.")
            invitation = invitation_repo.create(
                connection, actor["tenant_id"], email, token_hash, role, actor_id
            )
            if email_queued:
                invite_link = (
                    current_app.config["PUBLIC_BASE_URL"]
                    + url_for("users.accept_invitation", token=token)
                )
                body = (
                    f"Bạn được mời tham gia cửa hàng {actor['tenant_name']} với vai trò "
                    f"{'quản trị viên' if role == 'admin' else 'nhân viên'}.\n\n"
                    f"Chấp nhận lời mời trong 7 ngày tại:\n{invite_link}\n\n"
                    "Liên kết chỉ dùng một lần. Nếu bạn không mong đợi lời mời này, hãy bỏ qua email."
                )
                try:
                    outbox_id = mail_service.enqueue_text_email(
                        email,
                        f"Lời mời tham gia {actor['tenant_name']} trên PetCare Manager",
                        body,
                        expires_at=invitation["expires_at"],
                        connection=connection,
                    )
                except mail_service.MailDeliveryError as exc:
                    raise ValidationError(
                        "Chưa thể tạo lời mời email. Kiểm tra cấu hình gửi thư rồi thử lại."
                    ) from exc
                invitation_repo.attach_outbox(connection, invitation["id"], outbox_id)
            audit_repo.add_event(
                connection, actor_id, "membership.invitation_created", "invitation", invitation["id"],
                f"Tạo lời mời tham gia cửa hàng với vai trò {role}",
                {"role": role, "email_delivery": "queued" if email_queued else "manual"},
            )
    except Exception as exc:
        if getattr(exc, "errno", None) in {1062, 1205, 1213}:
            raise ConflictError("Không thể tạo lời mời lúc này hoặc email đã có lời mời mới. Vui lòng tải lại và thử lại.") from exc
        raise
    return {
        "id": invitation["id"],
        "token": None if email_queued else token,
        "role": role,
        "email": email,
        "email_queued": email_queued,
    }


def list_invitations(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        return invitation_repo.list_for_tenant(connection, actor["tenant_id"])


def revoke_invitation(actor_id, invitation_id):
    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        changed = invitation_repo.revoke(connection, invitation_id, actor["tenant_id"])
        if not changed:
            raise NotFoundError("Lời mời không còn hiệu lực hoặc không tồn tại.")
        audit_repo.add_event(
            connection, actor_id, "membership.invitation_revoked", "invitation", invitation_id,
            f"Thu hồi lời mời #{invitation_id}", {},
        )


def preview_invitation(token):
    token_hash = _token_hash(token)
    if not token_hash:
        raise NotFoundError("Lời mời không hợp lệ hoặc đã hết hạn.")
    with read_connection() as connection:
        invitation = invitation_repo.get_open_by_hash(connection, token_hash)
    if not invitation:
        raise NotFoundError("Lời mời không hợp lệ hoặc đã hết hạn.")
    return invitation


def accept_invitation(token, username, password, full_name=""):
    token_hash = _token_hash(token)
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    if not token_hash:
        raise NotFoundError("Lời mời không hợp lệ hoặc đã hết hạn.")
    if not USERNAME_RE.fullmatch(username):
        raise ValidationError("Tên đăng nhập cần 3–80 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
    if len(full_name) > 160:
        raise ValidationError("Tên hiển thị không được dài quá 160 ký tự.")

    password_hash = None
    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
        raise ValidationError("Mật khẩu cần từ 8 đến 1024 ký tự.")
    try:
        with transaction() as connection:
            invitation = invitation_repo.get_open_by_hash(connection, token_hash, for_update=True)
            if not invitation:
                raise NotFoundError("Lời mời không hợp lệ, đã được dùng hoặc đã hết hạn.")
            user = invitation_repo.get_user_by_username_for_update(connection, username)
            if user:
                if not user["active"] or not verify_password(password, user["password_hash"]):
                    raise ValidationError("Thông tin tài khoản không khớp.")
                if invitation["email"] and (
                    user["email"] != invitation["email"] or not user["email_verified_at"]
                ):
                    raise ValidationError(
                        "Tài khoản phải dùng đúng email lời mời và đã xác minh email trước khi tham gia."
                    )
                user_id = user["id"]
            else:
                if not full_name:
                    raise ValidationError("Nhập tên hiển thị để tạo tài khoản mới.")
                email_account = (
                    invitation_repo.get_user_by_email_for_update(connection, invitation["email"])
                    if invitation["email"]
                    else None
                )
                if email_account:
                    raise ValidationError(
                        "Email này đã có tài khoản. Hãy chấp nhận lời mời bằng tên đăng nhập của tài khoản đó."
                    )
                password_hash = hash_password(password)
                user_id = invitation_repo.create_user(
                    connection,
                    username,
                    password_hash,
                    full_name,
                    invitation["role"],
                    invitation["email"],
                    invitation["email_status"] == "sent",
                )

            membership = invitation_repo.get_membership_for_update(
                connection, invitation["tenant_id"], user_id
            )
            if membership and membership["active"]:
                raise ConflictError("Tài khoản này đã là thành viên của cửa hàng.")
            invitation_repo.add_or_reactivate_membership(
                connection, invitation["tenant_id"], user_id, invitation["role"]
            )
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (invitation["tenant_id"],))
            finally:
                cursor.close()
            if not invitation_repo.mark_accepted(
                connection, invitation["id"], invitation["tenant_id"], user_id
            ):
                raise ConflictError("Lời mời vừa được sử dụng hoặc đã hết hạn. Vui lòng thử lại.")
            audit_repo.add_event(
                connection, user_id, "membership.invitation_accepted", "user", user_id,
                f"Tham gia cửa hàng qua lời mời với vai trò {invitation['role']}",
                {"role": invitation["role"]},
            )
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT session_version FROM users WHERE id = %s", (user_id,))
                session_version = cursor.fetchone()[0]
            finally:
                cursor.close()
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Tên đăng nhập đã được sử dụng.") from exc
        raise
    return {
        "id": user_id,
        "username": username,
        "tenant_id": invitation["tenant_id"],
        "tenant_slug": invitation["tenant_slug"],
        "tenant_name": invitation["tenant_name"],
        "role": invitation["role"],
        "session_version": session_version,
    }
