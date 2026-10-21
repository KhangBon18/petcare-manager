"""Remove only untouched, expired public-signup reservations."""

from petcare.repositories.base import fetch_all


_EMPTY_TENANT_TABLES = (
    "tenant_invitations",
    "customers",
    "products",
    "pets",
    "invoices",
    "invoice_items",
    "stock_movements",
)


def cleanup_expired_public_signups(connection, limit=100):
    """Delete unverified signups after a grace period, preserving any used tenant."""
    candidates = fetch_all(
        connection,
        "SELECT tenant_id, user_id FROM tenant_users "
        "WHERE active = 0 AND email_activation_pending = 1 "
        "AND created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY) "
        "ORDER BY created_at, tenant_id LIMIT %s",
        (max(1, min(int(limit), 1000)),),
    )
    cursor = connection.cursor()
    removed = 0
    try:
        for membership in candidates:
            tenant_id = membership["tenant_id"]
            user_id = membership["user_id"]
            # Match verification's lock order (account, then membership). Locking
            # the membership in the candidate scan first can deadlock against a
            # verification request that already holds the account row.
            cursor.execute(
                "SELECT email_verified_at FROM users WHERE id = %s FOR UPDATE",
                (user_id,),
            )
            account = cursor.fetchone()
            if not account or account[0] is not None:
                continue
            cursor.execute(
                "SELECT tenant_id FROM tenant_users WHERE tenant_id = %s AND user_id = %s "
                "AND active = 0 AND email_activation_pending = 1 "
                "AND created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY) FOR UPDATE",
                (tenant_id, user_id),
            )
            if not cursor.fetchone():
                continue
            cursor.execute(
                "SELECT COUNT(*) FROM tenant_users WHERE tenant_id = %s",
                (tenant_id,),
            )
            if cursor.fetchone()[0] != 1:
                continue
            cursor.execute(
                "SELECT COUNT(*) FROM audit_events WHERE tenant_id = %s "
                "AND event_type <> 'tenant.signup_started'",
                (tenant_id,),
            )
            if cursor.fetchone()[0]:
                continue
            for table in _EMPTY_TENANT_TABLES:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = %s", (tenant_id,))
                if cursor.fetchone()[0]:
                    break
            else:
                cursor.execute(
                    "DELETE FROM audit_events WHERE tenant_id = %s AND event_type = 'tenant.signup_started'",
                    (tenant_id,),
                )
                cursor.execute(
                    "DELETE FROM tenant_users WHERE tenant_id = %s AND user_id = %s "
                    "AND active = 0 AND email_activation_pending = 1",
                    (tenant_id, user_id),
                )
                if cursor.rowcount != 1:
                    continue
                cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                if cursor.rowcount != 1:
                    continue
                cursor.execute(
                    "SELECT COUNT(*) FROM tenant_users WHERE user_id = %s",
                    (user_id,),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (user_id,))
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                removed += 1
    finally:
        cursor.close()
    return removed
