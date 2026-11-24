"""Tenant profile and public policy persistence."""

from petcare.repositories.base import execute, fetch_one


PUBLIC_POLICY_COLUMNS = (
    "pickup_address",
    "opening_hours",
    "cod_service_area_fees",
    "order_confirmation_sla",
    "return_refund_policy",
    "cancellation_instructions",
    "pet_handover_policy",
    "support_hotline",
    "support_zalo",
    "support_email",
    "privacy_terms_url",
    "privacy_terms_summary",
)


def create_public_signup(connection, name, slug, currency_code, timezone_name):
    return execute(
        connection,
        "INSERT INTO tenants (name, slug, status, default_currency, timezone) "
        "VALUES (%s, %s, 'active', %s, %s)",
        (name, slug, currency_code, timezone_name),
    )[0]


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


def get_public_policies(connection, tenant_id):
    # Static column list from PUBLIC_POLICY_COLUMNS constant.
    cols = ", ".join(PUBLIC_POLICY_COLUMNS)
    return fetch_one(
        connection,
        f"SELECT tenant_id, {cols}, updated_at FROM tenant_public_policies WHERE tenant_id = %s",  # nosec B608
        (tenant_id,),
    )


def upsert_public_policies(connection, tenant_id, values, updated_by):
    cols = ", ".join(PUBLIC_POLICY_COLUMNS)
    marks = ", ".join(["%s"] * len(PUBLIC_POLICY_COLUMNS))
    updates = ", ".join(f"{col} = VALUES({col})" for col in PUBLIC_POLICY_COLUMNS)
    params = (
        tenant_id,
        *(values[col] for col in PUBLIC_POLICY_COLUMNS),
        updated_by,
    )
    return execute(
        connection,
        f"INSERT INTO tenant_public_policies (tenant_id, {cols}, updated_by) "  # nosec B608
        f"VALUES (%s, {marks}, %s) "
        f"ON DUPLICATE KEY UPDATE {updates}, updated_by = VALUES(updated_by)",
        params,
    )[1]
