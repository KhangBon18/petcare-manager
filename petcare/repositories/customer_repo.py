from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one


def list_customers(connection, search="", include_inactive=False):
    search_sql, search_params = contains_filter(search, "c.full_name", "c.phone")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_all(
        connection,
        "SELECT c.*, (SELECT COUNT(*) FROM invoices i WHERE i.customer_id = c.id "
        "AND i.tenant_id = c.tenant_id) invoice_count "
        "FROM customers c WHERE c.tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql + " ORDER BY c.full_name, c.id",
        search_params,
    )


def count_customers(connection, search="", include_inactive=False):
    search_sql, search_params = contains_filter(search, "full_name", "phone")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM customers WHERE tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql,
        search_params,
    )["total"]


def list_customers_page(connection, search="", include_inactive=False, limit=25, offset=0):
    search_sql, search_params = contains_filter(search, "c.full_name", "c.phone")
    active_sql = "" if include_inactive else "AND c.active = 1"
    return fetch_all(
        connection,
        "SELECT c.*, (SELECT COUNT(*) FROM invoices i WHERE i.customer_id = c.id "
        "AND i.tenant_id = c.tenant_id) invoice_count "
        "FROM customers c WHERE c.tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql
        + " ORDER BY c.full_name, c.id LIMIT %s OFFSET %s",
        search_params + (limit, offset),
    )


def get_customer(connection, customer_id):
    return fetch_one(
        connection,
        "SELECT * FROM customers WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (customer_id,),
    )


def create_customer(connection, full_name, phone, address):
    return execute(
        connection,
        "INSERT INTO customers (tenant_id, full_name, phone, address) "
        "VALUES (@petcare_tenant_id, %s, %s, %s)",
        (full_name, phone, address),
    )[0]


def update_customer(connection, customer_id, full_name, phone, address):
    return execute(
        connection,
        "UPDATE customers SET full_name = %s, phone = %s, address = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (full_name, phone, address, customer_id),
    )[1]


def set_active(connection, customer_id, active):
    return execute(
        connection,
        "UPDATE customers SET active = %s WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (active, customer_id),
    )[1]
