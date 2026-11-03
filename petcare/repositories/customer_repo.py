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


def count_customer_invoices(connection, customer_id):
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM invoices "
        "WHERE tenant_id = @petcare_tenant_id AND customer_id = %s",
        (customer_id,),
    )["total"]


def summarize_customer_invoices(connection, customer_id):
    return fetch_all(
        connection,
        "SELECT i.currency_code, COUNT(*) invoice_count, "
        "SUM(i.status = 'paid') paid_invoice_count, "
        "SUM(i.status = 'unpaid') unpaid_invoice_count, "
        "COALESCE(SUM(CASE WHEN i.status = 'paid' THEN "
        "totals.invoice_total - COALESCE(refunds.refund_total, 0) ELSE 0 END), 0) paid_total, "
        "COALESCE(SUM(CASE WHEN i.status = 'unpaid' THEN totals.invoice_total ELSE 0 END), 0) unpaid_total "
        "FROM invoices i LEFT JOIN ("
        "SELECT ii.tenant_id, ii.invoice_id, SUM(ii.line_total) invoice_total "
        "FROM invoice_items ii JOIN invoices scoped_i "
        "ON scoped_i.id = ii.invoice_id AND scoped_i.tenant_id = ii.tenant_id "
        "WHERE ii.tenant_id = @petcare_tenant_id AND scoped_i.customer_id = %s "
        "GROUP BY ii.tenant_id, ii.invoice_id"
        ") totals ON totals.invoice_id = i.id AND totals.tenant_id = i.tenant_id "
        "LEFT JOIN (SELECT tenant_id, invoice_id, SUM(refund_total) refund_total "
        "FROM invoice_refunds WHERE tenant_id = @petcare_tenant_id GROUP BY tenant_id, invoice_id) refunds "
        "ON refunds.invoice_id = i.id AND refunds.tenant_id = i.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND i.customer_id = %s "
        "GROUP BY i.currency_code ORDER BY i.currency_code",
        (customer_id, customer_id),
    )


def list_customer_invoices_page(connection, customer_id, limit=25, offset=0):
    return fetch_all(
        connection,
        "SELECT i.id, i.created_at, i.status, i.currency_code, i.paid_at, "
        "COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii "
        "WHERE ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id), 0) total_amount, "
        "COALESCE((SELECT SUM(ir.refund_total) FROM invoice_refunds ir "
        "WHERE ir.invoice_id = i.id AND ir.tenant_id = i.tenant_id), 0) refunded_amount, "
        "(SELECT COUNT(*) FROM invoice_items ii "
        "WHERE ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id) item_count "
        "FROM invoices i WHERE i.tenant_id = @petcare_tenant_id AND i.customer_id = %s "
        "ORDER BY i.created_at DESC, i.id DESC LIMIT %s OFFSET %s",
        (customer_id, limit, offset),
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
