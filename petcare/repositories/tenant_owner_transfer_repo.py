"""Tenant-scoped persistence for confirmed owner handoffs."""

from petcare.repositories.base import execute, fetch_all, fetch_one


def membership_role(connection, tenant_id, user_id):
    return fetch_one(
        connection,
        "SELECT role, active FROM tenant_users WHERE tenant_id = %s AND user_id = %s",
        (tenant_id, user_id),
    )


def list_candidates(connection, tenant_id, excluded_user_id):
    return fetch_all(
        connection,
        "SELECT u.id, u.username, u.full_name FROM tenant_users tu "
        "JOIN users u ON u.id = tu.user_id "
        "WHERE tu.tenant_id = %s AND tu.user_id <> %s AND tu.role = 'admin' "
        "AND tu.active = 1 AND u.active = 1 "
        "ORDER BY u.full_name, u.id",
        (tenant_id, excluded_user_id),
    )


def open_for_tenant(connection, tenant_id):
    return fetch_one(
        connection,
        "SELECT tr.id, tr.tenant_id, tr.requested_by, tr.target_user_id, "
        "tr.email_outbox_id, tr.created_at, tr.expires_at, "
        "requester.full_name requester_name, requester.username requester_username, "
        "target.full_name target_name, target.username target_username, "
        "outbox.status email_status "
        "FROM tenant_owner_transfers tr "
        "JOIN users requester ON requester.id = tr.requested_by "
        "JOIN users target ON target.id = tr.target_user_id "
        "LEFT JOIN email_outbox outbox ON outbox.id = tr.email_outbox_id "
        "WHERE tr.tenant_id = %s AND tr.accepted_at IS NULL AND tr.cancelled_at IS NULL "
        "AND tr.expires_at > CURRENT_TIMESTAMP ORDER BY tr.id DESC LIMIT 1",
        (tenant_id,),
    )


def open_for_tenant_for_update(connection, tenant_id):
    """Read the current open request after locking the tenant row.

    The tenant row serializes handoffs. This locking read is also important
    under MySQL REPEATABLE READ: earlier authorization checks may already
    have established a snapshot that cannot see a handoff committed while
    this transaction waited for the tenant lock.
    """
    return fetch_one(
        connection,
        "SELECT id FROM tenant_owner_transfers WHERE tenant_id = %s "
        "AND accepted_at IS NULL AND cancelled_at IS NULL "
        "AND expires_at > CURRENT_TIMESTAMP ORDER BY id DESC LIMIT 1 FOR UPDATE",
        (tenant_id,),
    )


def open_for_update(connection, tenant_id, transfer_id):
    return fetch_one(
        connection,
        "SELECT id, tenant_id, requested_by, target_user_id, email_outbox_id, expires_at "
        "FROM tenant_owner_transfers WHERE tenant_id = %s AND id = %s "
        "AND accepted_at IS NULL AND cancelled_at IS NULL "
        "AND expires_at > CURRENT_TIMESTAMP FOR UPDATE",
        (tenant_id, transfer_id),
    )


def create(connection, tenant_id, requester_id, target_user_id):
    transfer_id = execute(
        connection,
        "INSERT INTO tenant_owner_transfers "
        "(tenant_id, requested_by, target_user_id, expires_at) "
        "VALUES (%s, %s, %s, DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 72 HOUR))",
        (tenant_id, requester_id, target_user_id),
    )[0]
    return fetch_one(
        connection,
        "SELECT id, expires_at FROM tenant_owner_transfers WHERE id = %s",
        (transfer_id,),
    )


def attach_outbox(connection, transfer_id, outbox_id):
    return execute(
        connection,
        "UPDATE tenant_owner_transfers SET email_outbox_id = %s WHERE id = %s",
        (outbox_id, transfer_id),
    )[1]


def cancel(connection, tenant_id, transfer_id, requester_id):
    changed = execute(
        connection,
        "UPDATE tenant_owner_transfers SET cancelled_at = CURRENT_TIMESTAMP "
        "WHERE tenant_id = %s AND id = %s AND requested_by = %s "
        "AND accepted_at IS NULL AND cancelled_at IS NULL "
        "AND expires_at > CURRENT_TIMESTAMP",
        (tenant_id, transfer_id, requester_id),
    )[1]
    if changed:
        cancel_delivery(connection, transfer_id)
    return changed


def cancel_delivery(connection, transfer_id):
    return execute(
        connection,
        "UPDATE email_outbox o JOIN tenant_owner_transfers tr ON tr.email_outbox_id = o.id "
        "SET o.status = 'failed', o.locked_until = NULL, o.last_error_code = 'owner_transfer_cancelled' "
        "WHERE tr.id = %s AND o.status IN ('pending', 'processing')",
        (transfer_id,),
    )[1]


def accept(connection, tenant_id, transfer_id, target_user_id):
    return execute(
        connection,
        "UPDATE tenant_owner_transfers SET accepted_at = CURRENT_TIMESTAMP "
        "WHERE tenant_id = %s AND id = %s AND target_user_id = %s "
        "AND accepted_at IS NULL AND cancelled_at IS NULL "
        "AND expires_at > CURRENT_TIMESTAMP",
        (tenant_id, transfer_id, target_user_id),
    )[1]


def set_membership_role(connection, tenant_id, user_id, role):
    return execute(
        connection,
        "UPDATE tenant_users SET role = %s WHERE tenant_id = %s AND user_id = %s AND active = 1",
        (role, tenant_id, user_id),
    )[1]
