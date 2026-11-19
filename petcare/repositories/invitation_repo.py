"""Tenant-scoped persistence for short-lived, single-use store invitations."""

from petcare.repositories.base import execute, fetch_all, fetch_one


def create(connection, tenant_id, email, token_hash, role, actor_id):
    invitation_id = execute(
        connection,
        "INSERT INTO tenant_invitations "
        "(tenant_id, email, token_hash, role, created_by, expires_at) "
        "VALUES (%s, %s, %s, %s, %s, DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 7 DAY))",
        (tenant_id, email, token_hash, role, actor_id),
    )[0]
    invitation = fetch_one(
        connection,
        "SELECT id, expires_at FROM tenant_invitations WHERE id = %s",
        (invitation_id,),
    )
    return invitation


def list_for_tenant(connection, tenant_id, limit=25):
    return fetch_all(
        connection,
        "SELECT i.id, i.email, i.role, i.created_at, i.expires_at, i.accepted_at, i.revoked_at, "
        "o.status email_status, "
        "CASE WHEN accepted_at IS NOT NULL THEN 'accepted' "
        "WHEN revoked_at IS NOT NULL THEN 'revoked' "
        "WHEN i.expires_at <= CURRENT_TIMESTAMP THEN 'expired' ELSE 'pending' END status "
        "FROM tenant_invitations i LEFT JOIN email_outbox o ON o.id = i.email_outbox_id "
        "WHERE i.tenant_id = %s "
        "ORDER BY i.id DESC LIMIT %s",
        (tenant_id, limit),
    )


def attach_outbox(connection, invitation_id, outbox_id):
    return execute(
        connection,
        "UPDATE tenant_invitations SET email_outbox_id = %s WHERE id = %s",
        (outbox_id, invitation_id),
    )[1]


def get_open_for_email(connection, tenant_id, email):
    return fetch_one(
        connection,
        "SELECT id FROM tenant_invitations WHERE tenant_id = %s AND email = %s "
        "AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP "
        "ORDER BY id DESC LIMIT 1 FOR UPDATE",
        (tenant_id, email),
    )


def revoke(connection, invitation_id, tenant_id):
    changed = execute(
        connection,
        "UPDATE tenant_invitations SET revoked_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND tenant_id = %s AND accepted_at IS NULL "
        "AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP",
        (invitation_id, tenant_id),
    )[1]
    if changed:
        cancel_delivery(connection, invitation_id, "invitation_revoked")
    return changed


def cancel_delivery(connection, invitation_id, reason):
    return execute(
        connection,
        "UPDATE email_outbox o JOIN tenant_invitations i ON i.email_outbox_id = o.id "
        "SET o.status = 'failed', o.locked_until = NULL, o.last_error_code = %s "
        "WHERE i.id = %s AND o.status IN ('pending', 'processing')",
        (reason[:64], invitation_id),
    )[1]


def get_open_by_hash(connection, token_hash, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    return fetch_one(
        connection,
        "SELECT i.id, i.tenant_id, i.email, i.email_outbox_id, i.role, i.created_by, "
        "t.name tenant_name, o.status email_status, "
        "t.slug tenant_slug, i.expires_at FROM tenant_invitations i "
        "JOIN tenants t ON t.id = i.tenant_id "
        "LEFT JOIN email_outbox o ON o.id = i.email_outbox_id "
        "WHERE i.token_hash = %s AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
        "AND i.expires_at > CURRENT_TIMESTAMP AND t.status = 'active'" + suffix,
        (token_hash,),
    )


def get_user_by_username_for_update(connection, username):
    return fetch_one(
        connection,
        "SELECT id, username, password_hash, full_name, email, email_verified_at, active FROM users "
        "WHERE username = %s FOR UPDATE",
        (username,),
    )


def get_user_by_email_for_update(connection, email):
    return fetch_one(
        connection,
        "SELECT id, username FROM users WHERE email = %s FOR UPDATE",
        (email,),
    )


def create_user(connection, username, password_hash, full_name, role, email, verified):
    legacy_role = "staff" if role == "staff" else "admin"
    return execute(
        connection,
        "INSERT INTO users (username, password_hash, full_name, role, email, email_verified_at) "
        "VALUES (%s, %s, %s, %s, %s, IF(%s, CURRENT_TIMESTAMP, NULL))",
        (username, password_hash, full_name, legacy_role, email, int(verified)),
    )[0]


def get_membership_for_update(connection, tenant_id, user_id):
    return fetch_one(
        connection,
        "SELECT role, active FROM tenant_users WHERE tenant_id = %s AND user_id = %s FOR UPDATE",
        (tenant_id, user_id),
    )


def add_or_reactivate_membership(connection, tenant_id, user_id, role):
    return execute(
        connection,
        "INSERT INTO tenant_users (tenant_id, user_id, role, active) VALUES (%s, %s, %s, 1) "
        "ON DUPLICATE KEY UPDATE role = VALUES(role), active = 1",
        (tenant_id, user_id, role),
    )[1]


def mark_accepted(connection, invitation_id, tenant_id, user_id):
    changed = execute(
        connection,
        "UPDATE tenant_invitations SET accepted_by = %s, accepted_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND tenant_id = %s AND accepted_at IS NULL "
        "AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP",
        (user_id, invitation_id, tenant_id),
    )[1]
    if changed:
        cancel_delivery(connection, invitation_id, "invitation_already_accepted")
    return changed
