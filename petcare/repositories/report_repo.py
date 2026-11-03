from petcare.repositories.base import fetch_all, fetch_one


def summary(connection, start_date, end_exclusive):
    return fetch_one(
        connection,
        "SELECT COUNT(DISTINCT CASE WHEN activity_type = 'sale' THEN invoice_id END) invoice_count, "
        "COALESCE(SUM(amount), 0) revenue FROM ("
        "SELECT i.id invoice_id, 'sale' activity_type, SUM(ii.line_total) amount "
        "FROM invoices i JOIN invoice_items ii ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s GROUP BY i.id "
        "UNION ALL "
        "SELECT ir.invoice_id, 'refund' activity_type, -ir.refund_total amount "
        "FROM invoice_refunds ir WHERE ir.tenant_id = @petcare_tenant_id "
        "AND ir.created_at >= %s AND ir.created_at < %s) activity",
        (start_date, end_exclusive, start_date, end_exclusive),
    )


def top_products(connection, start_date, end_exclusive):
    return fetch_all(
        connection,
        "SELECT product_id, code, name, SUM(quantity_delta) quantity_sold, SUM(revenue_delta) revenue "
        "FROM ("
        "SELECT ii.product_id, ii.item_code_snapshot code, ii.name_snapshot name, "
        "ii.quantity quantity_delta, ii.line_total revenue_delta "
        "FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id AND i.tenant_id = ii.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND ii.item_type = 'product' AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s "
        "UNION ALL "
        "SELECT source.product_id, iri.item_code_snapshot, iri.item_name_snapshot, "
        "CASE WHEN iri.disposition = 'not_returned' THEN 0 ELSE -iri.quantity END, -iri.refund_amount "
        "FROM invoice_refund_items iri JOIN invoice_refunds ir "
        "ON ir.tenant_id = iri.tenant_id AND ir.invoice_id = iri.invoice_id AND ir.id = iri.refund_id "
        "JOIN invoice_items source ON source.tenant_id = iri.tenant_id "
        "AND source.invoice_id = iri.invoice_id AND source.id = iri.invoice_item_id "
        "WHERE iri.tenant_id = @petcare_tenant_id AND iri.item_type_snapshot = 'product' "
        "AND ir.created_at >= %s AND ir.created_at < %s) activity "
        "GROUP BY product_id, code, name "
        "ORDER BY quantity_sold DESC, revenue DESC LIMIT 10",
        (start_date, end_exclusive, start_date, end_exclusive),
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
            "SELECT COALESCE(SUM(amount), 0) revenue FROM ("
            "SELECT ii.line_total amount FROM invoices i JOIN invoice_items ii "
            "ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
            "WHERE i.tenant_id = @petcare_tenant_id AND i.status = 'paid' "
            "AND i.paid_at >= %s AND i.paid_at < %s UNION ALL "
            "SELECT -ir.refund_total amount FROM invoice_refunds ir "
            "WHERE ir.tenant_id = @petcare_tenant_id AND ir.created_at >= %s AND ir.created_at < %s) activity",
            (day_start_utc, day_end_utc, day_start_utc, day_end_utc),
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


def paid_lines(connection, start_at, end_at):
    return fetch_all(connection,
        "SELECT * FROM ("
        "SELECT i.id invoice_id, i.paid_at, 'sale' entry_type, ii.item_type, "
        "ii.item_code_snapshot code, ii.name_snapshot name, ii.quantity, ii.unit_price, ii.line_total "
        "FROM invoices i JOIN invoice_items ii ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s UNION ALL "
        "SELECT ir.invoice_id, ir.created_at, 'refund', iri.item_type_snapshot, "
        "iri.item_code_snapshot, iri.item_name_snapshot, -iri.quantity, iri.unit_price, -iri.refund_amount "
        "FROM invoice_refunds ir JOIN invoice_refund_items iri "
        "ON iri.tenant_id = ir.tenant_id AND iri.invoice_id = ir.invoice_id AND iri.refund_id = ir.id "
        "WHERE ir.tenant_id = @petcare_tenant_id AND ir.created_at >= %s AND ir.created_at < %s) activity "
        "ORDER BY paid_at, invoice_id, entry_type LIMIT 5001",
        (start_at, end_at, start_at, end_at))
