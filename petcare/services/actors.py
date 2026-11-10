"""Explicit actor authorization against live user and store membership rows."""

from dataclasses import dataclass

from petcare.database.connection import set_tenant_context
from petcare.repositories import user_repo
from petcare.services.exceptions import ForbiddenError


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    tenant_id: int


def require_actor(connection, actor_id, tenant_id=None, admin=False):
    """Resolve current authority for a user in one active tenant.

    ``tenant_id`` should be supplied by the authenticated request context. The
    single-membership fallback remains for maintenance and legacy call sites.
    User and membership status and role are always read from MySQL.
    """
    if tenant_id is None:
        memberships = user_repo.list_active_tenant_ids(connection, actor_id)
        if len(memberships) != 1:
            raise ForbiddenError("Cần chọn cửa hàng hợp lệ trước khi thao tác.")
        tenant_id = memberships[0]

    actor = user_repo.get_actor_for_tenant(connection, actor_id, tenant_id)
    if not actor or not actor["user_active"] or not actor["membership_active"]:
        raise ForbiddenError("Tài khoản đã bị khóa hoặc không còn tồn tại.")
    if admin and actor["role"] != "admin":
        raise ForbiddenError("Chỉ quản trị viên được thực hiện thao tác này.")

    set_tenant_context(connection, tenant_id)
    return actor
