from petcare.repositories.base import fetch_all, fetch_one


def summary(connection, start_date, end_exclusive):
    return fetch_one(
        connection,
        "SELECT COUNT(*) invoice_count, COALESCE(SUM(total_amount), 0) revenue "
        "FROM (SELECT i.id, SUM(ii.line_total) total_amount FROM invoices i "
        "JOIN invoice_items ii ON ii.invoice_id = i.id "
        "WHERE i.tenant_id = @petcare_tenant_id AND ii.tenant_id = i.tenant_id "
        "AND i.status = 'paid' AND i.paid_at >= %s AND i.paid_at < %s "
        "GROUP BY i.id) paid_invoices",
        (start_date, end_exclusive),
    )


def top_products(connection, start_date, end_exclusive):
    return fetch_all(
        connection,
        "SELECT ii.product_id, ii.item_code_snapshot code, ii.name_snapshot name, "
        "SUM(ii.quantity) quantity_sold, SUM(ii.line_total) revenue "
        "FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id AND i.tenant_id = ii.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND ii.tenant_id = @petcare_tenant_id "
        "AND ii.item_type = 'product' AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s "
        "GROUP BY ii.product_id, ii.item_code_snapshot, ii.name_snapshot "
        "ORDER BY quantity_sold DESC, revenue DESC LIMIT 10",
        (start_date, end_exclusive),
    )


def inventory(connection):
    return fetch_one(
        connection,
        "SELECT COUNT(*) product_count, COALESCE(SUM(stock_qty), 0) units_in_stock, "
        "COALESCE(SUM(CASE WHEN stock_qty <= reorder_level AND active = 1 THEN 1 ELSE 0 END), 0) low_stock_count "
        "FROM products WHERE tenant_id = @petcare_tenant_id AND active = 1",
    )


def pets_sold(connection, start_date, end_exclusive):
    return fetch_one(
        connection,
        "SELECT COUNT(*) pets_sold FROM pets "
        "WHERE tenant_id = @petcare_tenant_id AND sale_status = 'sold' "
        "AND sold_at >= %s AND sold_at < %s",
        (start_date, end_exclusive),
    )


def dashboard(connection, day_start_utc, day_end_utc):
    return {
        "customers": fetch_one(
            connection, "SELECT COUNT(*) total FROM customers WHERE tenant_id = @petcare_tenant_id AND active = 1"
        )["total"],
        "products": fetch_one(
            connection, "SELECT COUNT(*) total FROM products WHERE tenant_id = @petcare_tenant_id AND active = 1"
        )["total"],
        "pets_available": fetch_one(
            connection, "SELECT COUNT(*) total FROM pets WHERE tenant_id = @petcare_tenant_id AND sale_status = 'available'"
        )["total"],
        "low_stock": fetch_one(
            connection,
            "SELECT COUNT(*) total FROM products WHERE tenant_id = @petcare_tenant_id "
            "AND active = 1 AND stock_qty <= reorder_level",
        )["total"],
        "today": fetch_one(
            connection,
            "SELECT COALESCE(SUM(ii.line_total), 0) revenue "
            "FROM invoices i JOIN invoice_items ii ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
            "WHERE i.tenant_id = @petcare_tenant_id AND i.status = 'paid' "
            "AND i.paid_at >= %s AND i.paid_at < %s",
            (day_start_utc, day_end_utc),
        )["revenue"],
        "low_stock_items": fetch_all(
            connection,
            "SELECT id, code, name, stock_qty, reorder_level FROM products "
            "WHERE tenant_id = @petcare_tenant_id AND active = 1 AND stock_qty <= reorder_level "
            "ORDER BY stock_qty ASC, name ASC LIMIT 5",
        ),
        "recent_invoices": fetch_all(
            connection,
            "SELECT i.id, i.created_at, i.status, i.currency_code, c.full_name customer_name, "
            "COALESCE(SUM(ii.line_total), 0) total_amount "
            "FROM invoices i JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id "
            "LEFT JOIN invoice_items ii ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
            "WHERE i.tenant_id = @petcare_tenant_id "
            "GROUP BY i.id, i.created_at, i.status, i.currency_code, c.full_name "
            "ORDER BY i.created_at DESC, i.id DESC LIMIT 5",
        ),
    }
