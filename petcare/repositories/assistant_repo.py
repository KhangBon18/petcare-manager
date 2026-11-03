"""Minimal aggregate shop context for the authenticated assistant."""

from petcare.repositories.base import fetch_all, fetch_one


def _net_revenue(connection, start_at, end_at):
    return fetch_one(
        connection,
        "SELECT COALESCE(SUM(amount), 0) total FROM ("
        "SELECT ii.line_total amount FROM invoices i JOIN invoice_items ii "
        "ON ii.invoice_id = i.id AND ii.tenant_id = i.tenant_id "
        "WHERE i.tenant_id = @petcare_tenant_id AND i.status = 'paid' "
        "AND i.paid_at >= %s AND i.paid_at < %s UNION ALL "
        "SELECT -ir.refund_total amount FROM invoice_refunds ir "
        "WHERE ir.tenant_id = @petcare_tenant_id AND ir.created_at >= %s AND ir.created_at < %s) activity",
        (start_at, end_at, start_at, end_at),
    )["total"]


def shop_context(connection, day_start_utc, day_end_utc, period_windows=None):
    dashboard = {
        "active_customers": fetch_one(
            connection, "SELECT COUNT(*) total FROM customers WHERE tenant_id = @petcare_tenant_id AND active = 1"
        )["total"],
        "active_products": fetch_one(
            connection, "SELECT COUNT(*) total FROM products WHERE tenant_id = @petcare_tenant_id AND active = 1"
        )["total"],
        "available_pets": fetch_one(
            connection, "SELECT COUNT(*) total FROM pets WHERE tenant_id = @petcare_tenant_id AND sale_status = 'available'"
        )["total"],
        "low_stock_count": fetch_one(
            connection,
            "SELECT COUNT(*) total FROM products WHERE tenant_id = @petcare_tenant_id "
            "AND active = 1 AND stock_qty <= reorder_level",
        )["total"],
        "revenue_today": _net_revenue(connection, day_start_utc, day_end_utc),
    }
    if period_windows:
        for key in period_windows:
            if key in {"week", "month"}:
                start_at, end_at = period_windows[key]
                dashboard[f"revenue_{key}"] = _net_revenue(connection, start_at, end_at)
    low_stock = fetch_all(
        connection,
        "SELECT code, name, category, unit_price, stock_qty, reorder_level FROM products "
        "WHERE tenant_id = @petcare_tenant_id AND active = 1 AND stock_qty <= reorder_level "
        "ORDER BY stock_qty, name LIMIT 50",
    )
    products = fetch_all(
        connection,
        "SELECT code, name, category, unit_price, stock_qty, reorder_level FROM products "
        "WHERE tenant_id = @petcare_tenant_id AND active = 1 ORDER BY name LIMIT 100",
    )
    pets = fetch_all(
        connection,
        "SELECT code, name, species, breed, coat_color, eye_color, appearance_tags, sale_price "
        "FROM pets WHERE tenant_id = @petcare_tenant_id "
        "AND sale_status = 'available' ORDER BY name LIMIT 250",
    )
    return {
        "summary": dashboard,
        "low_stock": low_stock,
        "products": products,
        "available_pets": pets,
        "preview_limits": {"low_stock": 12, "products": 20, "available_pets": 12},
        # Keep catalog truncation separate from the assistant's display limit.
        "catalog_preview_truncated": {
            "products": dashboard["active_products"] > len(products),
            "available_pets": dashboard["available_pets"] > len(pets),
        },
    }
