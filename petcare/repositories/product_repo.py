from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one


def list_products(connection, search="", include_inactive=False):
    search_sql, search_params = contains_filter(search, "code", "name", "category")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_all(
        connection,
        "SELECT * FROM products WHERE tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql + " ORDER BY active DESC, name, id",
        search_params,
    )


def count_products(connection, search="", include_inactive=False):
    search_sql, search_params = contains_filter(search, "code", "name", "category")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM products "
        "WHERE tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql,
        search_params,
    )["total"]


def list_products_page(connection, search="", include_inactive=False, limit=25, offset=0):
    search_sql, search_params = contains_filter(search, "code", "name", "category")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_all(
        connection,
        "SELECT * FROM products WHERE tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql
        + " ORDER BY active DESC, name, id LIMIT %s OFFSET %s",
        search_params + (limit, offset),
    )


def get_product(connection, product_id, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT * FROM products WHERE id = %s AND tenant_id = @petcare_tenant_id" + suffix,
        (product_id,),
    )


def has_photo(connection, filename):
    return fetch_one(
        connection,
        "SELECT 1 found FROM products WHERE tenant_id = @petcare_tenant_id "
        "AND photo_filename = %s LIMIT 1",
        (filename,),
    ) is not None


def count_photo_references(connection, filename):
    """Count all tenant references before removing a shared legacy object."""
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM products WHERE photo_filename = %s",
        (filename,),
    )["total"]


def create_product(connection, code, name, category, description, price, legacy_vnd_price, stock, reorder_level, photo_filename):
    return execute(
        connection,
        "INSERT INTO products (tenant_id, code, name, category, description, unit_price, unit_price_vnd, "
        "stock_qty, reorder_level, photo_filename) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (code, name, category, description, price, legacy_vnd_price, stock, reorder_level, photo_filename),
    )[0]


def update_product(connection, product_id, code, name, category, description, price, legacy_vnd_price, reorder_level, photo_filename):
    return execute(
        connection,
        "UPDATE products SET code = %s, name = %s, category = %s, description = %s, "
        "unit_price = %s, unit_price_vnd = %s, reorder_level = %s, "
        "photo_filename = COALESCE(%s, photo_filename) "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (code, name, category, description, price, legacy_vnd_price, reorder_level, photo_filename, product_id),
    )[1]


def set_active(connection, product_id, active):
    return execute(
        connection,
        "UPDATE products SET active = %s WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (active, product_id),
    )[1]


def adjust_stock(connection, product_id, delta):
    return execute(
        connection,
        "UPDATE products SET stock_qty = stock_qty + %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
        "AND stock_qty + %s BETWEEN 0 AND 2147483647",
        (delta, product_id, delta),
    )[1]


def add_stock_movement(connection, product_id, delta, reason, actor_id, invoice_id=None):
    execute(
        connection,
        "INSERT INTO stock_movements "
        "(tenant_id, product_id, quantity_delta, reason, created_by, invoice_id) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s)",
        (product_id, delta, reason, actor_id, invoice_id),
    )


def stock_history(connection, product_id):
    return fetch_all(
        connection,
        "SELECT sm.*, u.full_name actor_name, i.id invoice_number "
        "FROM stock_movements sm JOIN users u ON u.id = sm.created_by "
        "LEFT JOIN invoices i ON i.id = sm.invoice_id AND i.tenant_id = sm.tenant_id "
        "WHERE sm.product_id = %s AND sm.tenant_id = @petcare_tenant_id "
        "ORDER BY sm.created_at DESC, sm.id DESC LIMIT 100",
        (product_id,),
    )
