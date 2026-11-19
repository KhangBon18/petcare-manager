"""Tenant-scoped supplier and purchase-order queries."""

from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one


def count_suppliers(connection, search="", include_inactive=False):
    # B608 reviewed: the search columns and active predicate are code-owned;
    # user-entered search text remains in the parameter tuple.
    search_sql, params = contains_filter(search, "name", "contact_name", "phone", "email")
    active_sql = "" if include_inactive else "AND active = 1"
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM suppliers WHERE tenant_id = @petcare_tenant_id "  # nosec B608
        + search_sql + " " + active_sql,
        params,
    )["total"]


def list_suppliers_page(connection, search="", include_inactive=False, limit=25, offset=0):
    # B608 reviewed: identifier/filter fragments are fixed by this repository;
    # search values and pagination values are bound separately.
    search_sql, params = contains_filter(search, "s.name", "s.contact_name", "s.phone", "s.email")
    active_sql = "" if include_inactive else "AND s.active = 1"
    return fetch_all(
        connection,
        "SELECT s.*, (SELECT COUNT(*) FROM purchase_orders po "  # nosec B608
        "WHERE po.tenant_id = s.tenant_id AND po.supplier_id = s.id) purchase_order_count "
        "FROM suppliers s WHERE s.tenant_id = @petcare_tenant_id "
        + search_sql + " " + active_sql
        + " ORDER BY s.active DESC, s.name, s.id LIMIT %s OFFSET %s",
        params + (limit, offset),
    )


def list_active_suppliers(connection):
    return fetch_all(
        connection,
        "SELECT id, name FROM suppliers WHERE tenant_id = @petcare_tenant_id "
        "AND active = 1 ORDER BY name, id",
    )


def get_supplier(connection, supplier_id, lock=False):
    # B608 reviewed: suffix is either the literal FOR UPDATE clause or empty;
    # the only caller value is a separately bound supplier id.
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT * FROM suppliers WHERE id = %s AND tenant_id = @petcare_tenant_id" + suffix,  # nosec B608
        (supplier_id,),
    )


def create_supplier(connection, data):
    return execute(
        connection,
        "INSERT INTO suppliers (tenant_id, name, contact_name, phone, email, address) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s)",
        (data["name"], data["contact_name"], data["phone"], data["email"], data["address"]),
    )[0]


def update_supplier(connection, supplier_id, data):
    return execute(
        connection,
        "UPDATE suppliers SET name = %s, contact_name = %s, phone = %s, email = %s, address = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (data["name"], data["contact_name"], data["phone"], data["email"], data["address"], supplier_id),
    )[1]


def set_supplier_active(connection, supplier_id, active):
    return execute(
        connection,
        "UPDATE suppliers SET active = %s WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (active, supplier_id),
    )[1]


def count_purchase_orders(connection, status=None):
    # B608 reviewed: status_sql is a fixed predicate; status itself is bound.
    status_sql = "AND status = %s" if status else ""
    params = (status,) if status else ()
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM purchase_orders WHERE tenant_id = @petcare_tenant_id "  # nosec B608
        + status_sql,
        params,
    )["total"]


def list_purchase_orders_page(connection, status=None, limit=25, offset=0):
    # B608 reviewed: optional status clause is a code-owned literal; all values
    # are parameterized.
    status_sql = "AND po.status = %s" if status else ""
    params = (status,) if status else ()
    return fetch_all(
        connection,
        "SELECT po.*, COUNT(poi.id) item_count, "  # nosec B608
        "COALESCE(SUM(poi.quantity_ordered), 0) ordered_units, "
        "COALESCE(SUM(poi.quantity_received), 0) received_units "
        "FROM purchase_orders po LEFT JOIN purchase_order_items poi "
        "ON poi.tenant_id = po.tenant_id AND poi.purchase_order_id = po.id "
        "WHERE po.tenant_id = @petcare_tenant_id " + status_sql + " "
        "GROUP BY po.id ORDER BY po.created_at DESC, po.id DESC LIMIT %s OFFSET %s",
        params + (limit, offset),
    )


def get_purchase_order(connection, purchase_order_id, lock=False):
    if lock:
        return fetch_one(
            connection,
            "SELECT * FROM purchase_orders "
            "WHERE id = %s AND tenant_id = @petcare_tenant_id FOR UPDATE",
            (purchase_order_id,),
        )
    return fetch_one(
        connection,
        "SELECT po.*, u.full_name creator_name FROM purchase_orders po "
        "JOIN users u ON u.id = po.created_by "
        "WHERE po.id = %s AND po.tenant_id = @petcare_tenant_id",
        (purchase_order_id,),
    )


def list_purchase_order_items(connection, purchase_order_id):
    return fetch_all(
        connection,
        "SELECT poi.*, p.stock_qty current_stock, p.active product_active "
        "FROM purchase_order_items poi JOIN products p "
        "ON p.id = poi.product_id AND p.tenant_id = poi.tenant_id "
        "WHERE poi.tenant_id = @petcare_tenant_id AND poi.purchase_order_id = %s "
        "ORDER BY poi.id",
        (purchase_order_id,),
    )


def lock_purchase_order_items(connection, purchase_order_id):
    return fetch_all(
        connection,
        "SELECT * FROM purchase_order_items "
        "WHERE tenant_id = @petcare_tenant_id AND purchase_order_id = %s "
        "ORDER BY product_id, id FOR UPDATE",
        (purchase_order_id,),
    )


def create_purchase_order(connection, supplier_id, supplier_name, actor_id, currency_code, total, note):
    return execute(
        connection,
        "INSERT INTO purchase_orders "
        "(tenant_id, supplier_id, supplier_name_snapshot, created_by, status, currency_code, total_amount, note) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, 'ordered', %s, %s, %s)",
        (supplier_id, supplier_name, actor_id, currency_code, total, note),
    )[0]


def add_purchase_order_items(connection, purchase_order_id, items):
    cursor = connection.cursor()
    try:
        cursor.executemany(
            "INSERT INTO purchase_order_items "
            "(tenant_id, purchase_order_id, product_id, product_code_snapshot, "
            "product_name_snapshot, unit_cost, quantity_ordered, line_total) "
            "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    purchase_order_id, item["product_id"], item["code"], item["name"],
                    item["unit_cost"], item["quantity"], item["line_total"],
                )
                for item in items
            ],
        )
    finally:
        cursor.close()


def add_received_quantity(connection, purchase_order_id, item_id, quantity):
    return execute(
        connection,
        "UPDATE purchase_order_items SET quantity_received = quantity_received + %s "
        "WHERE tenant_id = @petcare_tenant_id AND purchase_order_id = %s AND id = %s "
        "AND quantity_received + %s <= quantity_ordered",
        (quantity, purchase_order_id, item_id, quantity),
    )[1]


def find_receipt_request(connection, request_key):
    return fetch_one(
        connection,
        "SELECT purchase_order_id, payload_hash FROM purchase_order_receipt_requests "
        "WHERE tenant_id = @petcare_tenant_id AND request_key = %s FOR UPDATE",
        (request_key,),
    )


def create_receipt_request(connection, purchase_order_id, request_key, payload_hash):
    return execute(
        connection,
        "INSERT INTO purchase_order_receipt_requests "
        "(tenant_id, purchase_order_id, request_key, payload_hash) "
        "VALUES (@petcare_tenant_id, %s, %s, %s)",
        (purchase_order_id, request_key, payload_hash),
    )[0]


def set_purchase_order_status(connection, purchase_order_id, status):
    return execute(
        connection,
        "UPDATE purchase_orders SET status = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (status, purchase_order_id),
    )[1]
