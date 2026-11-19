"""Persistence helpers for immutable invoice refunds and returned items."""

from petcare.repositories.base import execute, fetch_all, fetch_one


def get_refund_by_request_key(connection, request_key):
    return fetch_one(
        connection,
        "SELECT id, invoice_id FROM invoice_refunds "
        "WHERE tenant_id = @petcare_tenant_id AND request_key = %s FOR UPDATE",
        (request_key,),
    )


def refunded_quantities(connection, invoice_id):
    rows = fetch_all(
        connection,
        "SELECT iri.invoice_item_id, SUM(iri.quantity) refunded_quantity "
        "FROM invoice_refund_items iri JOIN invoice_refunds ir "
        "ON ir.tenant_id = iri.tenant_id AND ir.invoice_id = iri.invoice_id "
        "AND ir.id = iri.refund_id "
        "WHERE iri.tenant_id = @petcare_tenant_id AND iri.invoice_id = %s "
        "GROUP BY iri.invoice_item_id",
        (invoice_id,),
    )
    return {row["invoice_item_id"]: int(row["refunded_quantity"]) for row in rows}


def list_invoice_refunds(connection, invoice_id):
    return fetch_all(
        connection,
        "SELECT ir.*, u.full_name creator_name "
        "FROM invoice_refunds ir JOIN users u ON u.id = ir.created_by "
        "WHERE ir.tenant_id = @petcare_tenant_id AND ir.invoice_id = %s "
        "ORDER BY ir.created_at DESC, ir.id DESC",
        (invoice_id,),
    )


def list_invoice_refund_items(connection, invoice_id):
    return fetch_all(
        connection,
        "SELECT iri.*, ir.created_at refund_created_at "
        "FROM invoice_refund_items iri JOIN invoice_refunds ir "
        "ON ir.tenant_id = iri.tenant_id AND ir.invoice_id = iri.invoice_id "
        "AND ir.id = iri.refund_id "
        "WHERE iri.tenant_id = @petcare_tenant_id AND iri.invoice_id = %s "
        "ORDER BY ir.created_at DESC, ir.id DESC, iri.id",
        (invoice_id,),
    )


def create_refund(connection, invoice_id, actor_id, request_key, method, note, currency_code, total):
    return execute(
        connection,
        "INSERT INTO invoice_refunds "
        "(tenant_id, invoice_id, created_by, request_key, method, note, currency_code, refund_total) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s)",
        (invoice_id, actor_id, request_key, method, note, currency_code, total),
    )[0]


def create_refund_item(connection, invoice_id, refund_id, item, quantity, amount, disposition):
    return execute(
        connection,
        "INSERT INTO invoice_refund_items "
        "(tenant_id, invoice_id, refund_id, invoice_item_id, item_type_snapshot, "
        "item_code_snapshot, item_name_snapshot, quantity, unit_price, refund_amount, disposition) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            invoice_id, refund_id, item["id"], item["item_type"],
            item["item_code_snapshot"], item["name_snapshot"], quantity,
            item["unit_price"], amount, disposition,
        ),
    )[0]
