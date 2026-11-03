"""Sales velocity from paid invoice snapshots, including zero-sale products."""

from petcare.repositories.base import fetch_all


def sales_inventory(connection, start_30, start_14, end):
    return fetch_all(
        connection,
        "SELECT p.id, p.code, p.name, p.stock_qty, p.reorder_level, p.photo_filename, "
        "COALESCE(s.sold_14, 0) sold_14, COALESCE(s.sold_30, 0) sold_30 "
        "FROM products p LEFT JOIN ("
        "SELECT product_id, SUM(CASE WHEN activity_at >= %s THEN quantity_delta ELSE 0 END) sold_14, "
        "SUM(quantity_delta) sold_30 FROM ("
        "SELECT ii.product_id, i.paid_at activity_at, ii.quantity quantity_delta "
        "FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id AND i.tenant_id = ii.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND ii.item_type = 'product' AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s UNION ALL "
        "SELECT source.product_id, ir.created_at, -iri.quantity "
        "FROM invoice_refund_items iri JOIN invoice_refunds ir "
        "ON ir.tenant_id = iri.tenant_id AND ir.invoice_id = iri.invoice_id AND ir.id = iri.refund_id "
        "JOIN invoice_items source ON source.tenant_id = iri.tenant_id "
        "AND source.invoice_id = iri.invoice_id AND source.id = iri.invoice_item_id "
        "WHERE iri.tenant_id = @petcare_tenant_id AND iri.item_type_snapshot = 'product' "
        "AND iri.disposition <> 'not_returned' "
        "AND ir.created_at >= %s AND ir.created_at < %s) activity GROUP BY product_id) s ON s.product_id = p.id "
        "WHERE p.tenant_id = @petcare_tenant_id AND p.active = 1 ORDER BY p.name, p.id",
        (start_14, start_30, end, start_30, end),
    )
