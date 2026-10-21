from petcare.repositories.base import execute, fetch_all, fetch_one


def get_by_id(connection, user_id, tenant_id):
    return fetch_one(
        connection,
        "SELECT u.id, u.username, u.email, u.email_verified_at, u.password_hash, u.full_name, "
        "u.preferred_locale, "
        "IF(tu.role = 'staff', 'staff', 'admin') role, "
        "(u.active AND tu.active) active, u.session_version, u.created_at, "
        "t.id tenant_id, t.name tenant_name, t.slug tenant_slug, "
        "t.default_currency, t.timezone "
        "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
        "JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE u.id = %s AND tu.tenant_id = %s AND tu.active = 1 AND t.status = 'active'",
        (user_id, tenant_id),
    )


def get_by_id_for_update(connection, user_id, tenant_id):
    return fetch_one(
        connection,
        "SELECT u.id, u.username, u.password_hash, u.full_name, "
        "IF(tu.role = 'staff', 'staff', 'admin') role, tu.role membership_role, "
        "tu.active, u.created_at "
        "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
        "WHERE u.id = %s AND tu.tenant_id = %s FOR UPDATE",
        (user_id, tenant_id),
    )


def get_by_username(connection, username):
    return fetch_one(
        connection,
        "SELECT id, username, email, email_verified_at, password_hash, full_name, role, active, "
        "session_version, preferred_locale, created_at "
        "FROM users WHERE username = %s",
        (username,),
    )


def get_account_by_id_for_update(connection, user_id):
    return fetch_one(
        connection,
        "SELECT id, username, email, email_verified_at, password_hash, full_name, "
        "active, session_version FROM users WHERE id = %s FOR UPDATE",
        (user_id,),
    )


def get_verified_account_by_email_for_update(connection, email):
    return fetch_one(
        connection,
        "SELECT id, username, email, full_name, active, session_version "
        "FROM users WHERE email = %s AND email_verified_at IS NOT NULL "
        "AND active = 1 FOR UPDATE",
        (email,),
    )


def update_account_email(connection, user_id, email):
    return execute(
        connection,
        "UPDATE users SET email = %s, email_verified_at = NULL, "
        "session_version = session_version + 1 WHERE id = %s AND active = 1",
        (email, user_id),
    )[1]


def update_account_profile(connection, user_id, full_name):
    return execute(
        connection,
        "UPDATE users SET full_name = %s WHERE id = %s AND active = 1",
        (full_name, user_id),
    )[1]


def update_preferred_locale(connection, user_id, locale):
    return execute(
        connection,
        "UPDATE users SET preferred_locale = %s WHERE id = %s",
        (locale, user_id),
    )[1]


def remove_account_email(connection, user_id):
    return execute(
        connection,
        "UPDATE users SET email = NULL, email_verified_at = NULL, "
        "session_version = session_version + 1 WHERE id = %s AND active = 1",
        (user_id,),
    )[1]


def update_password_from_reset(connection, user_id, password_hash):
    return execute(
        connection,
        "UPDATE users SET password_hash = %s, session_version = session_version + 1 "
        "WHERE id = %s AND active = 1",
        (password_hash, user_id),
    )[1]


def mark_email_verified(connection, user_id):
    return execute(
        connection,
        "UPDATE users SET email_verified_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND active = 1 AND email IS NOT NULL",
        (user_id,),
    )[1]


def activate_email_pending_memberships(connection, user_id):
    return execute(
        connection,
        "UPDATE tenant_users SET active = 1, email_activation_pending = 0 "
        "WHERE user_id = %s AND email_activation_pending = 1 AND active = 0",
        (user_id,),
    )[1]


def active_membership_tenant_ids(connection, user_id):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT tu.tenant_id FROM tenant_users tu JOIN tenants t ON t.id = tu.tenant_id "
            "WHERE tu.user_id = %s AND tu.active = 1 AND t.status = 'active' ORDER BY tu.tenant_id",
            (user_id,),
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


def get_membership_by_slug(connection, user_id, slug):
    return fetch_one(
        connection,
        "SELECT tu.tenant_id, tu.role, tu.active, t.name tenant_name, t.slug tenant_slug, "
        "t.default_currency, t.timezone FROM tenant_users tu "
        "JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE tu.user_id = %s AND t.slug = %s AND t.status = 'active'",
        (user_id, slug),
    )


def get_active_membership(connection, user_id, tenant_id):
    return fetch_one(
        connection,
        "SELECT tu.tenant_id FROM tenant_users tu "
        "JOIN users u ON u.id = tu.user_id "
        "JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE tu.user_id = %s AND tu.tenant_id = %s AND tu.active = 1 "
        "AND u.active = 1 AND t.status = 'active'",
        (user_id, tenant_id),
    )


def get_only_membership(connection, user_id):
    rows = fetch_all(
        connection,
        "SELECT tu.tenant_id, tu.role, tu.active, t.name tenant_name, t.slug tenant_slug, "
        "t.default_currency, t.timezone FROM tenant_users tu "
        "JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE tu.user_id = %s AND tu.active = 1 AND t.status = 'active' LIMIT 2",
        (user_id,),
    )
    return rows[0] if len(rows) == 1 else None


def list_memberships(connection, user_id):
    return fetch_all(
        connection,
        "SELECT t.id tenant_id, t.name tenant_name, t.slug tenant_slug, tu.role "
        "FROM tenant_users tu JOIN tenants t ON t.id = tu.tenant_id "
        "WHERE tu.user_id = %s AND tu.active = 1 AND t.status = 'active' "
        "ORDER BY t.name, t.id",
        (user_id,),
    )


def list_users(connection, tenant_id):
    return fetch_all(
        connection,
        "SELECT u.id, u.username, u.full_name, "
        "IF(tu.role = 'staff', 'staff', 'admin') role, tu.role membership_role, "
        "tu.active, u.created_at "
        "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
        "WHERE tu.tenant_id = %s ORDER BY u.full_name, u.id",
        (tenant_id,),
    )


def create_user(connection, username, password_hash, full_name, role, tenant_id):
    legacy_role = "staff" if role == "staff" else "admin"
    user_id = execute(
        connection,
        "INSERT INTO users (username, password_hash, full_name, role) "
        "VALUES (%s, %s, %s, %s)",
        (username, password_hash, full_name, legacy_role),
    )[0]
    execute(
        connection,
        "INSERT INTO tenant_users (tenant_id, user_id, role, active) VALUES (%s, %s, %s, 1)",
        (tenant_id, user_id, role, ),
    )
    return user_id


def update_user(
    connection, user_id, tenant_id, full_name, role, active,
    password_hash=None, invalidate_sessions=False,
):
    if password_hash:
        execute(
            connection,
            "UPDATE users SET full_name = %s, password_hash = %s, "
            "session_version = session_version + 1 WHERE id = %s "
            "AND EXISTS (SELECT 1 FROM tenant_users WHERE user_id = %s AND tenant_id = %s)",
            (full_name, password_hash, user_id, user_id, tenant_id),
        )
    elif invalidate_sessions:
        execute(
            connection,
            "UPDATE users SET full_name = %s, session_version = session_version + 1 "
            "WHERE id = %s AND EXISTS "
            "(SELECT 1 FROM tenant_users WHERE user_id = %s AND tenant_id = %s)",
            (full_name, user_id, user_id, tenant_id),
        )
    else:
        execute(
            connection,
            "UPDATE users SET full_name = %s WHERE id = %s "
            "AND EXISTS (SELECT 1 FROM tenant_users WHERE user_id = %s AND tenant_id = %s)",
            (full_name, user_id, user_id, tenant_id),
        )
    return execute(
        connection,
        "UPDATE tenant_users SET role = %s, active = %s WHERE user_id = %s AND tenant_id = %s",
        (role, active, user_id, tenant_id),
    )[1]
