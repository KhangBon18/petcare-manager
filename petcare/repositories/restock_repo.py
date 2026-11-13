"""Tenant-scoped demand history and open purchase quantities."""

from petcare.repositories.base import fetch_all


# Keep SQL structure fixed. Dates are values bound below; no request or tenant
# data is interpolated into SQL identifiers or expressions.
SALES_INVENTORY_SQL = """
SELECT
    p.id, p.code, p.name, p.stock_qty, p.reorder_level,
    p.photo_filename, p.created_at,
    COALESCE(s.sold_14, 0) sold_14,
    COALESCE(s.sold_30, 0) sold_30,
    COALESCE(po.incoming_qty, 0) incoming_qty,
    COALESCE(s.week_0, 0) week_0,
    COALESCE(s.week_1, 0) week_1,
    COALESCE(s.week_2, 0) week_2,
    COALESCE(s.week_3, 0) week_3,
    COALESCE(s.week_4, 0) week_4,
    COALESCE(s.week_5, 0) week_5,
    COALESCE(s.week_6, 0) week_6,
    COALESCE(s.week_7, 0) week_7
FROM products p
LEFT JOIN (
    SELECT product_id,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s THEN quantity_delta ELSE 0 END)) sold_14,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s THEN quantity_delta ELSE 0 END)) sold_30,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_0,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_1,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_2,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_3,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_4,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_5,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_6,
        GREATEST(0, SUM(CASE WHEN activity_at >= %s AND activity_at < %s THEN quantity_delta ELSE 0 END)) week_7
    FROM (
        SELECT ii.product_id, i.paid_at activity_at, ii.quantity quantity_delta
        FROM invoice_items ii
        JOIN invoices i ON i.id = ii.invoice_id AND i.tenant_id = ii.tenant_id
        WHERE i.tenant_id = @petcare_tenant_id
          AND ii.item_type = 'product' AND i.status = 'paid'
          AND i.paid_at >= %s AND i.paid_at < %s
        UNION ALL
        SELECT source.product_id, ir.created_at, -iri.quantity
        FROM invoice_refund_items iri
        JOIN invoice_refunds ir
          ON ir.tenant_id = iri.tenant_id
         AND ir.invoice_id = iri.invoice_id
         AND ir.id = iri.refund_id
        JOIN invoice_items source
          ON source.tenant_id = iri.tenant_id
         AND source.invoice_id = iri.invoice_id
         AND source.id = iri.invoice_item_id
        WHERE iri.tenant_id = @petcare_tenant_id
          AND iri.item_type_snapshot = 'product'
          AND iri.disposition <> 'not_returned'
          AND ir.created_at >= %s AND ir.created_at < %s
    ) activity
    GROUP BY product_id
) s ON s.product_id = p.id
LEFT JOIN (
    SELECT poi.product_id,
        SUM(poi.quantity_ordered - poi.quantity_received) incoming_qty
    FROM purchase_order_items poi
    JOIN purchase_orders po
      ON po.tenant_id = poi.tenant_id AND po.id = poi.purchase_order_id
    WHERE poi.tenant_id = @petcare_tenant_id
      AND po.status IN ('ordered', 'partially_received')
    GROUP BY poi.product_id
) po ON po.product_id = p.id
WHERE p.tenant_id = @petcare_tenant_id AND p.active = 1
ORDER BY p.name, p.id
"""


def sales_inventory(connection, start_30, start_14, end, history_start=None, weekly_windows=()):
    """Return paid net demand and outstanding order units for the tenant.

    ``weekly_windows`` must contain the eight fixed, UTC-naive half-open
    windows used by the forecast service. Only date values are parameters;
    statement structure and identifiers are constant.
    """
    if len(weekly_windows) != 8:
        raise ValueError("exactly eight weekly windows are required")
    history_start = history_start or start_30
    weekly_parameters = tuple(
        value
        for window in weekly_windows
        for value in window
    )
    parameters = (
        start_14,
        start_30,
        *weekly_parameters,
        history_start,
        end,
        history_start,
        end,
    )
    return fetch_all(connection, SALES_INVENTORY_SQL, parameters)
