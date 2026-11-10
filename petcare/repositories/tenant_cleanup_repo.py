"""Persistence for removing expired, untouched public-signup reservations."""

from petcare.repositories.base import fetch_all


_EMPTY_TENANT_TABLES = (
    "tenant_invitations",
    "customers",
    "products",
    "suppliers",
    "pets",
    "invoices",
    "invoice_items",
    "invoice_refunds",
    "invoice_refund_items",
    "purchase_orders",
    "purchase_order_items",
    "stock_movements",
)


def list_expired_public_signup_candidates(connection, limit=100):
    return fetch_all(
        connection,
        "SELECT tenant_id, user_id FROM tenant_users "
        "WHERE active = 0 AND email_activation_pending = 1 "
        "AND created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY) "
        "ORDER BY created_at, tenant_id LIMIT %s",
        (max(1, min(int(limit), 1000)),),
    )


def delete_expired_unclaimed_signup(connection, tenant_id, user_id):
    """Lock account before membership and delete only a still-empty reservation."""
    cursor = connection.cursor()
    try:
        # Verification locks the account before the membership. Keep the same
        # order here so cleanup cannot deadlock with a verification request.
        cursor.execute(
            "SELECT email_verified_at FROM users WHERE id = %s FOR UPDATE",
            (user_id,),
        )
        account = cursor.fetchone()
        if not account or account[0] is not None:
            return False

        cursor.execute(
            "SELECT tenant_id FROM tenant_users WHERE tenant_id = %s AND user_id = %s "
            "AND active = 0 AND email_activation_pending = 1 "
            "AND created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY) FOR UPDATE",
            (tenant_id, user_id),
        )
        if not cursor.fetchone():
            return False

        cursor.execute(
            "SELECT COUNT(*) FROM tenant_users WHERE tenant_id = %s", (tenant_id,)
        )
        if cursor.fetchone()[0] != 1:
            return False

        cursor.execute(
            "SELECT COUNT(*) FROM audit_events WHERE tenant_id = %s "
            "AND event_type <> 'tenant.signup_started'",
            (tenant_id,),
        )
        if cursor.fetchone()[0]:
            return False

        # B608: each table name is selected from the closed module-level tuple
        # above; tenant_id is always passed as a bound value.
        for table in _EMPTY_TENANT_TABLES:
            cursor.execute(
                f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = %s", (tenant_id,)  # nosec B608
            )
            if cursor.fetchone()[0]:
                return False

        cursor.execute(
            "DELETE FROM audit_events WHERE tenant_id = %s "
            "AND event_type = 'tenant.signup_started'",
            (tenant_id,),
        )
        cursor.execute(
            "DELETE FROM tenant_users WHERE tenant_id = %s AND user_id = %s "
            "AND active = 0 AND email_activation_pending = 1",
            (tenant_id, user_id),
        )
        if cursor.rowcount != 1:
            return False

        cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        if cursor.rowcount != 1:
            return False

        cursor.execute(
            "SELECT COUNT(*) FROM tenant_users WHERE user_id = %s", (user_id,)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return True
    finally:
        cursor.close()
