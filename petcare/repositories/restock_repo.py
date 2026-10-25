"""Sales velocity from paid invoice snapshots, including zero-sale products."""

from petcare.repositories.base import fetch_all


def sales_inventory(connection, start_30, start_14, end):
    return fetch_all(
        connection,
        "SELECT p.id, p.code, p.name, p.stock_qty, p.reorder_level, p.photo_filename, "
        "COALESCE(s.sold_14, 0) sold_14, COALESCE(s.sold_30, 0) sold_30 "
        "FROM products p LEFT JOIN ("
        "SELECT ii.product_id, SUM(CASE WHEN i.paid_at >= %s THEN ii.quantity ELSE 0 END) sold_14, "
        "SUM(ii.quantity) sold_30 FROM invoice_items ii "
        "JOIN invoices i ON i.id = ii.invoice_id AND i.tenant_id = ii.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND ii.tenant_id = @petcare_tenant_id "
        "AND i.status = 'paid' AND ii.item_type = 'product' "
        "AND i.paid_at >= %s AND i.paid_at < %s GROUP BY ii.product_id) s ON s.product_id = p.id "
        "WHERE p.tenant_id = @petcare_tenant_id AND p.active = 1 ORDER BY p.name, p.id",
        (start_14, start_30, end),
    )
