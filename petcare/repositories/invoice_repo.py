from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one


def list_invoices(connection, search="", status=""):
    search_sql, search_params = contains_filter(
        search, "c.full_name", "CAST(i.id AS CHAR)"
    )
    status_sql = "AND i.status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    return fetch_all(
        connection,
        "SELECT i.*, c.full_name customer_name, u.full_name created_by_name, "
        "COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii "
        "WHERE ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id), 0) total_amount "
        "FROM invoices i JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id "
        "JOIN users u ON u.id = i.created_by "
        "WHERE i.tenant_id = @petcare_tenant_id "
        + search_sql + " " + status_sql + " ORDER BY i.created_at DESC, i.id DESC",
        tuple(params),
    )


def count_invoices(connection, search="", status=""):
    search_sql, search_params = contains_filter(
        search, "c.full_name", "CAST(i.id AS CHAR)"
    )
    status_sql = "AND i.status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM invoices i "
        "JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id "
        + search_sql + " " + status_sql,
        tuple(params),
    )["total"]


def list_invoices_page(connection, search="", status="", limit=25, offset=0):
    search_sql, search_params = contains_filter(
        search, "c.full_name", "CAST(i.id AS CHAR)"
    )
    status_sql = "AND i.status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    params.extend((limit, offset))
    return fetch_all(
        connection,
        "SELECT i.*, c.full_name customer_name, u.full_name created_by_name, "
        "COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii "
        "WHERE ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id), 0) total_amount "
        "FROM invoices i JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id "
        "JOIN users u ON u.id = i.created_by "
        "WHERE i.tenant_id = @petcare_tenant_id "
        + search_sql + " " + status_sql
        + " ORDER BY i.created_at DESC, i.id DESC LIMIT %s OFFSET %s",
        tuple(params),
    )


def get_invoice(connection, invoice_id, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT i.*, c.full_name customer_name, c.phone customer_phone, "
        "u.full_name created_by_name FROM invoices i "
        "JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id "
        "JOIN users u ON u.id = i.created_by "
        "WHERE i.id = %s AND i.tenant_id = @petcare_tenant_id" + suffix,
        (invoice_id,),
    )


def list_items(connection, invoice_id):
    return fetch_all(
        connection,
        "SELECT * FROM invoice_items WHERE invoice_id = %s "
        "AND tenant_id = @petcare_tenant_id ORDER BY id",
        (invoice_id,),
    )


def get_items_for_update(connection, invoice_id):
    return fetch_all(
        connection,
        "SELECT * FROM invoice_items WHERE invoice_id = %s "
        "AND tenant_id = @petcare_tenant_id "
        "ORDER BY item_type, product_id, pet_id FOR UPDATE",
        (invoice_id,),
    )


def create_invoice(connection, customer_id, actor_id, note, currency_code):
    return execute(
        connection,
        "INSERT INTO invoices (tenant_id, customer_id, created_by, note, currency_code) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s)",
        (customer_id, actor_id, note, currency_code),
    )[0]


def add_item(connection, invoice_id, item, currency_code):
    legacy_unit_price = int(item["unit_price"]) if currency_code == "VND" else 0
    legacy_line_total = int(item["line_total"]) if currency_code == "VND" else 0
    execute(
        connection,
        "INSERT INTO invoice_items "
        "(tenant_id, invoice_id, item_type, product_id, pet_id, item_code_snapshot, name_snapshot, "
        "unit_price, unit_price_vnd, quantity, line_total, line_total_vnd) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            invoice_id, item["item_type"], item["product_id"], item["pet_id"],
            item["code"], item["name"], item["unit_price"], legacy_unit_price,
            item["quantity"], item["line_total"], legacy_line_total,
        ),
    )


def update_paid(connection, invoice_id):
    return execute(
        connection,
        "UPDATE invoices SET status = 'paid', paid_at = NOW() "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id AND status = 'unpaid'",
        (invoice_id,),
    )[1]


def update_cancelled(connection, invoice_id):
    return execute(
        connection,
        "UPDATE invoices SET status = 'cancelled' "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id AND status = 'unpaid'",
        (invoice_id,),
    )[1]
