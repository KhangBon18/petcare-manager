"""Tenant profile persistence."""

from petcare.repositories.base import execute, fetch_one


def get_for_update(connection, tenant_id):
    return fetch_one(
        connection,
        "SELECT id, name, slug, status, default_currency, timezone "
        "FROM tenants WHERE id = %s FOR UPDATE",
        (tenant_id,),
    )


def update_profile(connection, tenant_id, name, timezone_name):
    return execute(
        connection,
        "UPDATE tenants SET name = %s, timezone = %s "
        "WHERE id = %s AND status = 'active'",
        (name, timezone_name, tenant_id),
    )[1]
