"""Reauthenticated, target-accepted ownership handoff for one store."""

from flask import current_app, url_for

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, tenant_owner_transfer_repo, tenant_repo, user_repo
from petcare.security import verify_password
from petcare.services import mail_service, request_throttle_service
from petcare.services.common import require_actor
from petcare.services.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def _lock_admin_memberships(connection, tenant_id):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT user_id, role FROM tenant_users WHERE tenant_id = %s "
            "AND role IN ('owner', 'admin') AND active = 1 "
            "ORDER BY user_id FOR UPDATE",
            (tenant_id,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()


def _locked_accounts(connection, user_ids):
    accounts = {}
    for user_id in sorted(set(user_ids)):
        accounts[user_id] = user_repo.get_account_by_id_for_update(connection, user_id)
    return accounts


def _verify_password(account, password):
    if (
        not account
        or not account["active"]
        or not isinstance(password, str)
        or not 1 <= len(password) <= 1024
        or not verify_password(password, account["password_hash"])
    ):
        raise ValidationError("Mật khẩu hiện tại không chính xác.")


def _require_active_tenant(connection, tenant_id):
    tenant = tenant_repo.get_for_update(connection, tenant_id)
    if not tenant or tenant["status"] != "active":
        raise ForbiddenError("Cửa hàng không còn hoạt động.")
    return tenant


def get_page_context(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        membership = tenant_owner_transfer_repo.membership_role(
            connection, actor["tenant_id"], actor_id
        )
        if not membership or not membership["active"]:
            raise ForbiddenError("Tài khoản không còn quyền trong cửa hàng này.")
        transfer = tenant_owner_transfer_repo.open_for_tenant(connection, actor["tenant_id"])
        if transfer and membership["role"] != "owner" and actor_id not in {
            transfer["requested_by"], transfer["target_user_id"]
        }:
            transfer = None
        candidates = (
            tenant_owner_transfer_repo.list_candidates(connection, actor["tenant_id"], actor_id)
            if membership["role"] == "owner"
            else []
        )
        return {
            "membership_role": membership["role"],
            "candidates": candidates,
            "transfer": transfer,
            "can_accept": bool(transfer and transfer["target_user_id"] == actor_id),
            "can_cancel": bool(
                transfer
                and transfer["requested_by"] == actor_id
                and membership["role"] == "owner"
            ),
        }


def initiate_transfer(actor_id, target_user_id, current_password):
    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Chọn quản trị viên sẽ nhận bàn giao.") from exc
    if target_user_id <= 0:
        raise ValidationError("Chọn quản trị viên sẽ nhận bàn giao.")

    allowed, retry_after = request_throttle_service.consume(actor_id, "tenant_owner_transfer")
    if not allowed:
        raise RateLimitError("Bạn đã thử bàn giao quá nhiều lần. Vui lòng thử lại sau.", retry_after)

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        tenant = _require_active_tenant(connection, actor["tenant_id"])
        roles = _lock_admin_memberships(connection, tenant["id"])
        if roles.get(actor_id) != "owner":
            raise ForbiddenError("Chỉ chủ cửa hàng hiện tại mới có thể khởi tạo bàn giao.")
        if roles.get(target_user_id) != "admin":
            raise ValidationError("Người nhận phải là quản trị viên đang hoạt động của cửa hàng này.")
        if tenant_owner_transfer_repo.open_for_tenant_for_update(connection, tenant["id"]):
            raise ConflictError("Cửa hàng đã có yêu cầu bàn giao đang chờ xử lý.")

        accounts = _locked_accounts(connection, (actor_id, target_user_id))
        _verify_password(accounts[actor_id], current_password)
        target = accounts[target_user_id]
        if not target or not target["active"]:
            raise ValidationError("Tài khoản người nhận không còn hoạt động.")

        transfer = tenant_owner_transfer_repo.create(
            connection, tenant["id"], actor_id, target_user_id
        )
        email_queued = bool(
            mail_service.is_configured()
            and target["email"]
            and target["email_verified_at"]
        )
        if email_queued:
            link = current_app.config["PUBLIC_BASE_URL"] + url_for("users.ownership")
            body = (
                f"Chủ cửa hàng {tenant['name']} đã đề nghị bàn giao quyền owner cho tài khoản "
                f"{target['username']}. Đăng nhập bằng tài khoản đó, mở trang thành viên và "
                f"xác nhận bằng mật khẩu hiện tại trước {transfer['expires_at']} tại:\n{link}\n\n"
                "Email này chỉ thông báo; không chứa liên kết xác nhận dùng thay cho đăng nhập."
            )
            try:
                outbox_id = mail_service.enqueue_text_email(
                    target["email"],
                    f"Yêu cầu bàn giao chủ cửa hàng {tenant['name']}",
                    body,
                    expires_at=transfer["expires_at"],
                    connection=connection,
                )
            except mail_service.MailDeliveryError as exc:
                raise ValidationError(
                    "Chưa thể gửi thông báo bàn giao. Kiểm tra cấu hình email rồi thử lại."
                ) from exc
            tenant_owner_transfer_repo.attach_outbox(connection, transfer["id"], outbox_id)

        audit_repo.add_event(
            connection,
            actor_id,
            "membership.owner_transfer_requested",
            "owner_transfer",
            transfer["id"],
            f"Đề nghị bàn giao quyền chủ cửa hàng cho tài khoản #{target_user_id}",
            {"target_user_id": target_user_id, "email_delivery": "queued" if email_queued else "manual"},
        )
    return {"id": transfer["id"], "expires_at": transfer["expires_at"], "email_queued": email_queued}


def cancel_transfer(actor_id, transfer_id, current_password):
    allowed, retry_after = request_throttle_service.consume(actor_id, "tenant_owner_transfer")
    if not allowed:
        raise RateLimitError("Bạn đã thử bàn giao quá nhiều lần. Vui lòng thử lại sau.", retry_after)

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        tenant = _require_active_tenant(connection, actor["tenant_id"])
        roles = _lock_admin_memberships(connection, tenant["id"])
        if roles.get(actor_id) != "owner":
            raise ForbiddenError("Chỉ chủ cửa hàng mới có thể thu hồi yêu cầu bàn giao.")
        transfer = tenant_owner_transfer_repo.open_for_update(
            connection, tenant["id"], transfer_id
        )
        if not transfer:
            raise NotFoundError("Yêu cầu bàn giao không còn hiệu lực.")
        if transfer["requested_by"] != actor_id:
            raise ForbiddenError("Chỉ người đã khởi tạo yêu cầu mới có thể thu hồi.")
        account = user_repo.get_account_by_id_for_update(connection, actor_id)
        _verify_password(account, current_password)
        if not tenant_owner_transfer_repo.cancel(
            connection, tenant["id"], transfer_id, actor_id
        ):
            raise ConflictError("Yêu cầu bàn giao vừa được xử lý. Hãy tải lại trang.")
        audit_repo.add_event(
            connection,
            actor_id,
            "membership.owner_transfer_cancelled",
            "owner_transfer",
            transfer_id,
            f"Thu hồi yêu cầu bàn giao chủ cửa hàng #{transfer_id}",
            {},
        )


def accept_transfer(actor_id, transfer_id, current_password):
    allowed, retry_after = request_throttle_service.consume(actor_id, "tenant_owner_transfer")
    if not allowed:
        raise RateLimitError("Bạn đã thử bàn giao quá nhiều lần. Vui lòng thử lại sau.", retry_after)

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        tenant = _require_active_tenant(connection, actor["tenant_id"])
        roles = _lock_admin_memberships(connection, tenant["id"])
        transfer = tenant_owner_transfer_repo.open_for_update(
            connection, tenant["id"], transfer_id
        )
        if not transfer or transfer["target_user_id"] != actor_id:
            raise NotFoundError("Yêu cầu bàn giao không còn hiệu lực.")
        if roles.get(transfer["requested_by"]) != "owner":
            raise ConflictError("Chủ cửa hàng đã thay đổi; yêu cầu bàn giao này không còn hợp lệ.")
        if roles.get(actor_id) != "admin":
            raise ConflictError("Bạn cần còn là quản trị viên đang hoạt động để nhận bàn giao.")

        account = user_repo.get_account_by_id_for_update(connection, actor_id)
        _verify_password(account, current_password)
        tenant_owner_transfer_repo.set_membership_role(
            connection, tenant["id"], transfer["requested_by"], "admin"
        )
        tenant_owner_transfer_repo.set_membership_role(
            connection, tenant["id"], actor_id, "owner"
        )
        if not tenant_owner_transfer_repo.accept(
            connection, tenant["id"], transfer_id, actor_id
        ):
            raise ConflictError("Yêu cầu bàn giao vừa hết hạn hoặc đã được xử lý.")
        tenant_owner_transfer_repo.cancel_delivery(connection, transfer_id)
        audit_repo.add_event(
            connection,
            actor_id,
            "membership.owner_transferred",
            "owner_transfer",
            transfer_id,
            f"Nhận bàn giao quyền chủ cửa hàng từ tài khoản #{transfer['requested_by']}",
            {"previous_owner_user_id": transfer["requested_by"]},
        )
