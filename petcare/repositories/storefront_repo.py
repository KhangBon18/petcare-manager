"""Tenant-scoped SQL queries for Customer Storefront MVP 1.0."""

from __future__ import annotations

from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one


_ACTIVE_ORDER_STATES_SQL = "('pending', 'confirmed', 'preparing')"

_PUBLIC_PET_COLUMNS = (
    "p.id, p.code, p.name, p.species, p.breed, p.sex, p.birth_date, p.weight_kg, "
    "p.coat_color, p.eye_color, p.appearance_tags, p.photo_filename, p.sale_price, p.sale_status, "
    "EXISTS(SELECT 1 FROM customer_order_pet_locks pl WHERE pl.tenant_id = p.tenant_id AND pl.pet_id = p.id) AS is_reserved"
)

_PUBLIC_PRODUCT_COLUMNS = (
    "p.id, p.code, p.name, p.category, p.description, p.unit_price, p.stock_qty, p.photo_filename, p.active, "
    "GREATEST(0, CAST(p.stock_qty AS SIGNED) - COALESCE(("
    "SELECT SUM(oi.quantity) FROM customer_order_items oi "
    "JOIN customer_orders o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id "
    "WHERE oi.tenant_id = p.tenant_id AND oi.product_id = p.id "
    "AND o.order_status IN " + _ACTIVE_ORDER_STATES_SQL +
    "), 0)) AS available_online_qty"
)


def get_active_store_by_slug(connection, slug: str):
    return fetch_one(
        connection,
        "SELECT id, name, slug, status, default_currency, timezone "
        "FROM tenants WHERE slug = %s AND status = 'active'",
        (slug,),
    )


def list_public_categories(connection):
    rows = fetch_all(
        connection,
        "SELECT DISTINCT category FROM products "
        "WHERE tenant_id = @petcare_tenant_id AND active = 1 "
        "ORDER BY category",
    )
    return [row["category"] for row in rows if row.get("category")]


def _product_filters_sql(search: str = "", category: str = "", in_stock_only: bool = False):
    clauses = ["p.tenant_id = @petcare_tenant_id", "p.active = 1"]
    params = []
    search_sql, search_params = contains_filter(search, "p.code", "p.name", "p.category", "p.description")
    if search_sql:
        clauses.append(search_sql.lstrip(" AND "))
        params.extend(search_params)
    if category:
        clauses.append("p.category = %s")
        params.append(category)
    if in_stock_only:
        clauses.append("p.stock_qty > 0")
    return " AND ".join(clauses), tuple(params)


def count_public_products(connection, search: str = "", category: str = "", in_stock_only: bool = False) -> int:
    where_sql, params = _product_filters_sql(search, category, in_stock_only)
    sql = "SELECT COUNT(*) total FROM products p WHERE " + where_sql  # nosec B608
    return int(fetch_one(connection, sql, params)["total"])


def list_public_products_page(
    connection,
    search: str = "",
    category: str = "",
    in_stock_only: bool = False,
    sort: str = "featured",
    limit: int = 24,
    offset: int = 0,
):
    where_sql, params = _product_filters_sql(search, category, in_stock_only)
    order_by = {
        "price_asc": "p.unit_price ASC, p.name ASC, p.id ASC",
        "price_desc": "p.unit_price DESC, p.name ASC, p.id ASC",
        "name": "p.name ASC, p.id ASC",
    }.get(sort, "CASE WHEN p.stock_qty > 0 THEN 0 ELSE 1 END ASC, p.id ASC")
    sql = (
        f"SELECT {_PUBLIC_PRODUCT_COLUMNS} FROM products p WHERE {where_sql} "
        f"ORDER BY {order_by} LIMIT %s OFFSET %s"
    )  # nosec B608
    return fetch_all(connection, sql, (*params, limit, offset))


def get_public_product(connection, product_id: int):
    return fetch_one(
        connection,
        f"SELECT {_PUBLIC_PRODUCT_COLUMNS} FROM products p "
        "WHERE p.id = %s AND p.tenant_id = @petcare_tenant_id AND p.active = 1",  # nosec B608
        (product_id,),
    )


def has_active_public_product_photo(connection, filename: str) -> bool:
    return fetch_one(
        connection,
        "SELECT 1 found FROM products WHERE tenant_id = @petcare_tenant_id "
        "AND active = 1 AND photo_filename = %s LIMIT 1",
        (filename,),
    ) is not None


def _pet_filters_sql(search: str = "", species: str = ""):
    clauses = ["p.tenant_id = @petcare_tenant_id", "p.sale_status = 'available'"]
    params = []
    search_sql, search_params = contains_filter(
        search, "p.code", "p.name", "p.species", "p.breed", "p.coat_color", "p.appearance_tags"
    )
    if search_sql:
        clauses.append(search_sql.lstrip(" AND "))
        params.extend(search_params)
    sp = (species or "").strip().lower()
    if sp in {"cat", "mèo"}:
        clauses.append("(LOWER(p.species) LIKE %s OR LOWER(p.species) LIKE %s)")
        params.extend(("%mèo%", "%cat%"))
    elif sp in {"dog", "chó"}:
        clauses.append("(LOWER(p.species) LIKE %s OR LOWER(p.species) LIKE %s)")
        params.extend(("%chó%", "%dog%"))
    elif sp in {"other", "khác"}:
        clauses.append(
            "LOWER(p.species) NOT LIKE %s AND LOWER(p.species) NOT LIKE %s "
            "AND LOWER(p.species) NOT LIKE %s AND LOWER(p.species) NOT LIKE %s"
        )
        params.extend(("%mèo%", "%cat%", "%chó%", "%dog%"))
    return " AND ".join(clauses), tuple(params)


def count_public_pets(connection, search: str = "", species: str = "") -> int:
    where_sql, params = _pet_filters_sql(search, species)
    sql = "SELECT COUNT(*) total FROM pets p WHERE " + where_sql  # nosec B608
    return int(fetch_one(connection, sql, params)["total"])


def list_public_pets_page(
    connection,
    search: str = "",
    species: str = "",
    sort: str = "featured",
    limit: int = 24,
    offset: int = 0,
):
    where_sql, params = _pet_filters_sql(search, species)
    order_by = {
        "price_asc": "p.sale_price ASC, p.name ASC, p.id ASC",
        "price_desc": "p.sale_price DESC, p.name ASC, p.id ASC",
        "name": "p.name ASC, p.id ASC",
    }.get(sort, "CASE WHEN p.photo_filename IS NOT NULL THEN 0 ELSE 1 END ASC, p.id ASC")
    sql = (
        f"SELECT {_PUBLIC_PET_COLUMNS} FROM pets p WHERE {where_sql} "
        f"ORDER BY {order_by} LIMIT %s OFFSET %s"
    )  # nosec B608
    return fetch_all(connection, sql, (*params, limit, offset))


def get_public_pet(connection, pet_id: int):
    return fetch_one(
        connection,
        f"SELECT {_PUBLIC_PET_COLUMNS} FROM pets p "
        "WHERE p.id = %s AND p.tenant_id = @petcare_tenant_id AND p.sale_status = 'available'",  # nosec B608
        (pet_id,),
    )


def list_public_pet_reference_photos(connection, pet_id: int):
    return fetch_all(
        connection,
        "SELECT id, photo_filename, image_role, sort_order FROM pet_reference_photos "
        "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s "
        "ORDER BY sort_order ASC, id ASC",
        (pet_id,),
    )


def has_available_public_pet_photo(connection, filename: str) -> bool:
    return fetch_one(
        connection,
        "SELECT 1 found FROM pets WHERE tenant_id = @petcare_tenant_id "
        "AND sale_status = 'available' AND photo_filename = %s "
        "UNION ALL "
        "SELECT 1 found FROM pet_reference_photos rp "
        "JOIN pets p ON p.id = rp.pet_id AND p.tenant_id = rp.tenant_id "
        "WHERE rp.tenant_id = @petcare_tenant_id AND p.sale_status = 'available' "
        "AND rp.photo_filename = %s LIMIT 1",
        (filename, filename),
    ) is not None


def reserved_product_quantities(
    connection, product_ids, exclude_order_id: int | None = None, lock: bool = False
) -> dict[int, int]:
    ids = sorted({int(pid) for pid in product_ids})
    if not ids:
        return {}
    placeholders = ", ".join(["%s"] * len(ids))
    excl_sql = "AND o.id <> %s " if exclude_order_id is not None else ""
    params = list(ids)
    if exclude_order_id is not None:
        params.append(exclude_order_id)
    suffix = " FOR UPDATE" if lock else ""
    rows = fetch_all(
        connection,
        "SELECT oi.product_id, oi.quantity "
        "FROM customer_order_items oi "
        "JOIN customer_orders o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id "
        f"WHERE oi.tenant_id = @petcare_tenant_id AND oi.product_id IN ({placeholders}) "
        f"AND o.order_status IN {_ACTIVE_ORDER_STATES_SQL} {excl_sql}"
        "ORDER BY oi.id" + suffix,  # nosec B608
        tuple(params),
    )
    totals: dict[int, int] = {}
    for row in rows:
        pid = int(row["product_id"])
        totals[pid] = totals.get(pid, 0) + int(row["quantity"])
    return totals


def get_pets_for_order_lock(connection, pet_ids):
    ids = sorted({int(pid) for pid in pet_ids})
    if not ids:
        return []
    placeholders = ", ".join(["%s"] * len(ids))
    return fetch_all(
        connection,
        "SELECT id, code, name, sale_price, sale_status FROM pets "
        f"WHERE tenant_id = @petcare_tenant_id AND id IN ({placeholders}) "
        "ORDER BY id FOR UPDATE",  # nosec B608
        tuple(ids),
    )


def locked_pet_ids(
    connection, pet_ids, exclude_order_id: int | None = None, lock: bool = False
) -> set[int]:
    ids = sorted({int(pid) for pid in pet_ids})
    if not ids:
        return set()
    placeholders = ", ".join(["%s"] * len(ids))
    excl_sql = "AND order_id <> %s " if exclude_order_id is not None else ""
    params = list(ids)
    if exclude_order_id is not None:
        params.append(exclude_order_id)
    suffix = " FOR UPDATE" if lock else ""
    rows = fetch_all(
        connection,
        "SELECT pet_id FROM customer_order_pet_locks "
        f"WHERE tenant_id = @petcare_tenant_id AND pet_id IN ({placeholders}) {excl_sql}"
        "ORDER BY pet_id" + suffix,  # nosec B608
        tuple(params),
    )
    return {int(row["pet_id"]) for row in rows}


def lock_pet_for_order(connection, pet_id: int, order_id: int):
    execute(
        connection,
        "INSERT INTO customer_order_pet_locks (tenant_id, pet_id, order_id) "
        "VALUES (@petcare_tenant_id, %s, %s)",
        (pet_id, order_id),
    )


def release_pet_locks_for_order(connection, order_id: int):
    execute(
        connection,
        "DELETE FROM customer_order_pet_locks "
        "WHERE tenant_id = @petcare_tenant_id AND order_id = %s",
        (order_id,),
    )


# ---------- Customer accounts ----------
def get_account_by_email(connection, email: str):
    return fetch_one(
        connection,
        "SELECT * FROM customer_accounts WHERE tenant_id = @petcare_tenant_id AND email = %s",
        (email,),
    )


def get_account_by_id(connection, account_id: int):
    return fetch_one(
        connection,
        "SELECT * FROM customer_accounts WHERE tenant_id = @petcare_tenant_id AND id = %s",
        (account_id,),
    )


def create_account(connection, email: str, password_hash: str, full_name: str, phone: str, default_address: str):
    return execute(
        connection,
        "INSERT INTO customer_accounts (tenant_id, email, password_hash, full_name, phone, default_address) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s)",
        (email, password_hash, full_name, phone, default_address),
    )[0]


def update_account_profile(connection, account_id: int, full_name: str, phone: str, default_address: str):
    return execute(
        connection,
        "UPDATE customer_accounts SET full_name = %s, phone = %s, default_address = %s "
        "WHERE tenant_id = @petcare_tenant_id AND id = %s",
        (full_name, phone, default_address, account_id),
    )[1]


# ---------- Customer orders ----------
def get_order_by_request_key(connection, request_key: str):
    return fetch_one(
        connection,
        "SELECT * FROM customer_orders WHERE tenant_id = @petcare_tenant_id AND request_key = %s",
        (request_key,),
    )


def get_order_by_code(connection, order_code: str):
    return fetch_one(
        connection,
        "SELECT * FROM customer_orders WHERE tenant_id = @petcare_tenant_id AND order_code = %s",
        (order_code,),
    )


def get_order_by_id(connection, order_id: int, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT o.*, u.full_name AS processed_by_name "
        "FROM customer_orders o "
        "LEFT JOIN users u ON u.id = o.processed_by "
        "WHERE o.tenant_id = @petcare_tenant_id AND o.id = %s" + suffix,
        (order_id,),
    )


def create_order(
    connection,
    order_code: str,
    request_key: str,
    customer_account_id: int | None,
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    delivery_address: str,
    fulfillment_method: str,
    payment_method: str,
    currency_code: str,
    total_amount,
    customer_note: str,
):
    return execute(
        connection,
        "INSERT INTO customer_orders "
        "(tenant_id, order_code, request_key, customer_account_id, customer_name, customer_phone, "
        "customer_email, delivery_address, fulfillment_method, payment_method, currency_code, "
        "total_amount, customer_note) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            order_code, request_key, customer_account_id, customer_name, customer_phone,
            customer_email, delivery_address, fulfillment_method, payment_method, currency_code,
            total_amount, customer_note,
        ),
    )[0]


def add_order_item(connection, order_id: int, line: dict):
    execute(
        connection,
        "INSERT INTO customer_order_items "
        "(tenant_id, order_id, item_type, product_id, pet_id, item_code_snapshot, "
        "name_snapshot, unit_price, quantity, line_total) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            order_id, line["item_type"], line["product_id"], line["pet_id"],
            line["code"], line["name"], line["unit_price"], line["quantity"], line["line_total"],
        ),
    )


def list_order_items(connection, order_id: int, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_all(
        connection,
        "SELECT oi.*, p.photo_filename AS product_photo_filename, pt.photo_filename AS pet_photo_filename, "
        "p.category AS product_category, pt.species AS pet_species "
        "FROM customer_order_items oi "
        "LEFT JOIN products p ON p.id = oi.product_id AND p.tenant_id = oi.tenant_id "
        "LEFT JOIN pets pt ON pt.id = oi.pet_id AND pt.tenant_id = oi.tenant_id "
        "WHERE oi.tenant_id = @petcare_tenant_id AND oi.order_id = %s "
        "ORDER BY oi.id" + suffix,
        (order_id,),
    )


def list_orders_for_account(connection, account_id: int, limit: int = 30, offset: int = 0):
    return fetch_all(
        connection,
        "SELECT o.*, (SELECT COUNT(*) FROM customer_order_items oi WHERE oi.tenant_id = o.tenant_id AND oi.order_id = o.id) AS item_count "
        "FROM customer_orders o WHERE o.tenant_id = @petcare_tenant_id AND o.customer_account_id = %s "
        "ORDER BY o.created_at DESC, o.id DESC LIMIT %s OFFSET %s",
        (account_id, limit, offset),
    )


def count_orders_for_staff(connection, search: str = "", status: str = "") -> int:
    clauses = ["o.tenant_id = @petcare_tenant_id"]
    params = []
    search_sql, search_params = contains_filter(search, "o.order_code", "o.customer_name", "o.customer_phone")
    if search_sql:
        clauses.append(search_sql.lstrip(" AND "))
        params.extend(search_params)
    if status:
        clauses.append("o.order_status = %s")
        params.append(status)
    sql = "SELECT COUNT(*) total FROM customer_orders o WHERE " + " AND ".join(clauses)  # nosec B608
    return int(fetch_one(connection, sql, tuple(params))["total"])


def list_orders_for_staff_page(connection, search: str = "", status: str = "", limit: int = 25, offset: int = 0):
    clauses = ["o.tenant_id = @petcare_tenant_id"]
    params = []
    search_sql, search_params = contains_filter(search, "o.order_code", "o.customer_name", "o.customer_phone")
    if search_sql:
        clauses.append(search_sql.lstrip(" AND "))
        params.extend(search_params)
    if status:
        clauses.append("o.order_status = %s")
        params.append(status)
    sql = (
        "SELECT o.*, (SELECT COUNT(*) FROM customer_order_items oi WHERE oi.tenant_id = o.tenant_id AND oi.order_id = o.id) AS item_count, "
        "u.full_name AS processed_by_name "
        "FROM customer_orders o "
        "LEFT JOIN users u ON u.id = o.processed_by "
        "WHERE " + " AND ".join(clauses) + " ORDER BY FIELD(o.order_status, 'pending', 'confirmed', 'preparing', 'ready_completed', 'rejected', 'cancelled'), o.created_at DESC, o.id DESC LIMIT %s OFFSET %s"
    )  # nosec B608
    return fetch_all(connection, sql, (*params, limit, offset))


def find_active_crm_customer_by_phone(connection, phone: str):
    return fetch_one(
        connection,
        "SELECT * FROM customers WHERE tenant_id = @petcare_tenant_id AND phone = %s AND active = 1 ORDER BY id LIMIT 1",
        (phone,),
    )


def update_order_state(
    connection,
    order_id: int,
    *,
    order_status: str,
    payment_status: str | None = None,
    processed_by: int | None = None,
    staff_note: str | None = None,
    customer_id: int | None = None,
    invoice_id: int | None = None,
    set_confirmed_at: bool = False,
    set_completed_at: bool = False,
    set_cancelled_at: bool = False,
):
    sets = ["order_status = %s"]
    params = [order_status]
    if payment_status is not None:
        sets.append("payment_status = %s")
        params.append(payment_status)
    if processed_by is not None:
        sets.append("processed_by = %s")
        params.append(processed_by)
    if staff_note is not None:
        sets.append("staff_note = %s")
        params.append(staff_note)
    if customer_id is not None:
        sets.append("customer_id = %s")
        params.append(customer_id)
    if invoice_id is not None:
        sets.append("invoice_id = %s")
        params.append(invoice_id)
    if set_confirmed_at:
        sets.append("confirmed_at = COALESCE(confirmed_at, NOW())")
    if set_completed_at:
        sets.append("completed_at = COALESCE(completed_at, NOW())")
    if set_cancelled_at:
        sets.append("cancelled_at = COALESCE(cancelled_at, NOW())")
    params.append(order_id)
    sql = (
        "UPDATE customer_orders SET " + ", ".join(sets)
        + " WHERE tenant_id = @petcare_tenant_id AND id = %s"
    )  # nosec B608
    return execute(connection, sql, tuple(params))[1]

