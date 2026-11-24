"""Storefront catalog, MySQL-backed cart pricing, checkout, and order fulfillment services."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re
import secrets

from flask import current_app
from mysql.connector import IntegrityError

from petcare.database.connection import read_connection, set_tenant_context, transaction
from petcare.email_address import normalize_email
from petcare.repositories import (
    audit_repo,
    customer_repo,
    invoice_repo,
    pet_repo,
    product_repo,
    storefront_repo,
)
from petcare.services.common import integer_value, page_window, positive_id, require_actor, text_value
from petcare.services.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from petcare.services.storefront_auth_service import normalize_phone
from petcare.timezones import tenant_today
from petcare.vision.media_storage import media_tenant_id


MAX_CART_LINES = 25
MAX_ITEM_QTY = 99
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

ORDER_STATUS_LABELS_VI = {
    "pending": "Chờ xác nhận",
    "confirmed": "Đã xác nhận",
    "preparing": "Đang chuẩn bị",
    "fulfilled": "Đã giao · Chờ thu tiền",
    "ready_completed": "Hoàn tất",
    "rejected": "Từ chối",
    "cancelled": "Đã hủy",
}

ORDER_STATUS_LABELS_EN = {
    "pending": "Pending confirmation",
    "confirmed": "Confirmed",
    "preparing": "Preparing",
    "fulfilled": "Fulfilled · Awaiting payment",
    "ready_completed": "Completed",
    "rejected": "Rejected",
    "cancelled": "Cancelled",
}


def resolve_public_store(slug: str | None = None) -> dict:
    target_slug = (slug or current_app.config.get("PUBLIC_STORE_SLUG") or "main").strip().lower()
    with read_connection() as connection:
        store = storefront_repo.get_active_store_by_slug(connection, target_slug)
    if not store:
        raise NotFoundError("Cửa hàng không tồn tại hoặc đang tạm ngưng hoạt động.")
    return store


def get_storefront_home_data(tenant_id: int) -> dict:
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        categories = storefront_repo.list_public_categories(connection)
        pets = storefront_repo.list_public_pets_page(connection, limit=6, offset=0)
        products = storefront_repo.list_public_products_page(connection, limit=8, offset=0)
        total_pets = storefront_repo.count_public_pets(connection)
        total_products = storefront_repo.count_public_products(connection)
    return {
        "categories": categories,
        "featured_pets": pets,
        "featured_products": products,
        "total_pets": total_pets,
        "total_products": total_products,
    }


def list_public_products(
    tenant_id: int,
    *,
    search: str = "",
    category: str = "",
    in_stock_only: bool = False,
    sort: str = "featured",
    page=1,
) -> dict:
    search = (search or "").strip()[:120]
    category = (category or "").strip()[:100]
    if sort not in {"featured", "price_asc", "price_desc", "name"}:
        sort = "featured"
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        categories = storefront_repo.list_public_categories(connection)
        total = storefront_repo.count_public_products(connection, search, category, in_stock_only)
        _curr, offset, pagination = page_window(page, total, page_size=12)
        items = storefront_repo.list_public_products_page(
            connection,
            search=search,
            category=category,
            in_stock_only=in_stock_only,
            sort=sort,
            limit=pagination["page_size"],
            offset=offset,
        )
    return {"items": items, "pagination": pagination, "categories": categories}


def get_public_product(tenant_id: int, product_id) -> dict:
    pid = positive_id(product_id, "Sản phẩm")
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        product = storefront_repo.get_public_product(connection, pid)
    if not product:
        raise NotFoundError("Sản phẩm không tồn tại hoặc đã ngừng bán.")
    return product


def list_public_pets(
    tenant_id: int,
    *,
    search: str = "",
    species: str = "",
    sort: str = "featured",
    page=1,
) -> dict:
    search = (search or "").strip()[:120]
    species = (species or "").strip().lower()[:40]
    if species not in {"", "cat", "dog", "other", "mèo", "chó", "khác"}:
        species = ""
    if sort not in {"featured", "price_asc", "price_desc", "name"}:
        sort = "featured"
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        total = storefront_repo.count_public_pets(connection, search, species)
        _curr, offset, pagination = page_window(page, total, page_size=12)
        items = storefront_repo.list_public_pets_page(
            connection,
            search=search,
            species=species,
            sort=sort,
            limit=pagination["page_size"],
            offset=offset,
        )
    return {"items": items, "pagination": pagination}


def get_public_pet(tenant_id: int, pet_id) -> dict:
    pid = positive_id(pet_id, "Thú cưng")
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        pet = storefront_repo.get_public_pet(connection, pid)
        refs = storefront_repo.list_public_pet_reference_photos(connection, pid) if pet else []
    if not pet:
        raise NotFoundError("Thú cưng không tồn tại hoặc không còn mở bán.")
    pet["reference_photos"] = refs
    return pet


def public_owns_product_photo(tenant_id: int, filename: str) -> bool:
    try:
        scoped = media_tenant_id(filename)
    except ValueError:
        return False
    if scoped is not None and scoped != tenant_id:
        return False
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        return storefront_repo.has_active_public_product_photo(connection, filename)


def public_owns_pet_photo(tenant_id: int, filename: str) -> bool:
    try:
        scoped = media_tenant_id(filename)
    except ValueError:
        return False
    if scoped is not None and scoped != tenant_id:
        return False
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        return storefront_repo.has_available_public_pet_photo(connection, filename)


def sanitize_cart(raw_cart) -> list[dict]:
    """Normalize session cart items safely."""
    if not isinstance(raw_cart, list):
        return []
    merged_products: dict[int, int] = defaultdict(int)
    pet_ids: list[int] = []
    seen_pets: set[int] = set()
    for entry in raw_cart[:MAX_CART_LINES * 2]:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("item_type")
        try:
            item_id = int(entry.get("item_id"))
        except (TypeError, ValueError):
            continue
        if item_id <= 0:
            continue
        if kind == "product":
            try:
                qty = int(entry.get("quantity", 1))
            except (TypeError, ValueError):
                qty = 1
            if qty > 0:
                merged_products[item_id] = min(MAX_ITEM_QTY, merged_products[item_id] + qty)
        elif kind == "pet" and item_id not in seen_pets:
            seen_pets.add(item_id)
            pet_ids.append(item_id)
    items = [
        {"item_type": "product", "item_id": pid, "quantity": qty}
        for pid, qty in merged_products.items()
    ] + [{"item_type": "pet", "item_id": pid, "quantity": 1} for pid in pet_ids]
    return items[:MAX_CART_LINES]


def add_item_to_cart(tenant_id: int, raw_cart, item_type: str, raw_item_id, raw_qty=1) -> list[dict]:
    if item_type not in {"product", "pet"}:
        raise ValidationError("Loại mặt hàng không hợp lệ.")
    item_id = positive_id(raw_item_id, "Mặt hàng")
    qty = 1 if item_type == "pet" else integer_value(raw_qty, "Số lượng", 1, MAX_ITEM_QTY)
    cart = sanitize_cart(raw_cart)
    if len(cart) >= MAX_CART_LINES and not any(
        c["item_type"] == item_type and c["item_id"] == item_id for c in cart
    ):
        raise ValidationError("Giỏ hàng đã đạt giới hạn tối đa.")

    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        if item_type == "product":
            product = storefront_repo.get_public_product(connection, item_id)
            if not product:
                raise NotFoundError("Sản phẩm không còn kinh doanh.")
            existing_qty = next(
                (c["quantity"] for c in cart if c["item_type"] == "product" and c["item_id"] == item_id),
                0,
            )
            desired_qty = existing_qty + qty
            available = int(product["available_online_qty"])
            if available <= 0:
                raise ValidationError(f"{product['name']} hiện đã tạm hết hàng trực tuyến.")
            if desired_qty > available:
                raise ValidationError(
                    f"{product['name']} chỉ còn tối đa {available} sản phẩm khả dụng."
                )
            updated = False
            for c in cart:
                if c["item_type"] == "product" and c["item_id"] == item_id:
                    c["quantity"] = desired_qty
                    updated = True
            if not updated:
                cart.append({"item_type": "product", "item_id": item_id, "quantity": qty})
        else:
            pet = storefront_repo.get_public_pet(connection, item_id)
            if not pet:
                raise NotFoundError("Thú cưng hiện không còn mở bán.")
            if pet.get("is_reserved"):
                raise ValidationError("Cá thể thú cưng này đang được giữ cho đơn hàng khác.")
            if not any(c["item_type"] == "pet" and c["item_id"] == item_id for c in cart):
                cart.append({"item_type": "pet", "item_id": item_id, "quantity": 1})
    return cart


def update_cart_item(tenant_id: int, raw_cart, item_type: str, raw_item_id, raw_qty) -> list[dict]:
    if item_type not in {"product", "pet"}:
        raise ValidationError("Loại mặt hàng không hợp lệ.")
    item_id = positive_id(raw_item_id, "Mặt hàng")
    qty = integer_value(raw_qty, "Số lượng", 0, MAX_ITEM_QTY)
    cart = sanitize_cart(raw_cart)
    if qty == 0:
        return [c for c in cart if not (c["item_type"] == item_type and c["item_id"] == item_id)]
    if item_type == "pet":
        return cart
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        product = storefront_repo.get_public_product(connection, item_id)
        if not product:
            return [c for c in cart if not (c["item_type"] == "product" and c["item_id"] == item_id)]
        available = int(product["available_online_qty"])
        if qty > available:
            raise ValidationError(
                f"{product['name']} chỉ còn tối đa {available} sản phẩm khả dụng."
            )
    for c in cart:
        if c["item_type"] == "product" and c["item_id"] == item_id:
            c["quantity"] = qty
    return cart


def price_cart_snapshot(tenant_id: int, raw_cart) -> dict:
    """Recompute every line total strictly from live MySQL catalog tables."""
    cart = sanitize_cart(raw_cart)
    if not cart:
        return {"items": [], "subtotal": Decimal("0"), "total_units": 0, "has_unavailable": False, "warnings": []}

    lines = []
    warnings = []
    subtotal = Decimal("0")
    total_units = 0
    has_unavailable = False

    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        for entry in cart:
            if entry["item_type"] == "product":
                row = storefront_repo.get_public_product(connection, entry["item_id"])
                if not row:
                    has_unavailable = True
                    warnings.append("Một sản phẩm trong giỏ đã ngừng bán.")
                    continue
                available = int(row["available_online_qty"])
                qty = entry["quantity"]
                item_available = available >= qty and available > 0
                if not item_available:
                    has_unavailable = True
                    warnings.append(
                        f"{row['name']} hiện còn {available} khả dụng (bạn chọn {qty})."
                    )
                unit_price = Decimal(row["unit_price"])
                line_total = unit_price * qty
                lines.append({
                    "item_type": "product",
                    "item_id": int(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "category": row["category"],
                    "photo_filename": row.get("photo_filename"),
                    "unit_price": unit_price,
                    "quantity": qty,
                    "available_qty": available,
                    "line_total": line_total,
                    "is_available": item_available,
                })
                subtotal += line_total
                total_units += qty
            else:
                row = storefront_repo.get_public_pet(connection, entry["item_id"])
                if not row:
                    has_unavailable = True
                    warnings.append("Một thú cưng trong giỏ hiện không còn mở bán.")
                    continue
                item_available = not bool(row.get("is_reserved"))
                if not item_available:
                    has_unavailable = True
                    warnings.append(f"Thú cưng {row['name']} hiện đang tạm giữ cho đơn hàng khác.")
                unit_price = Decimal(row["sale_price"])
                lines.append({
                    "item_type": "pet",
                    "item_id": int(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "species": row["species"],
                    "breed": row["breed"],
                    "photo_filename": row.get("photo_filename"),
                    "unit_price": unit_price,
                    "quantity": 1,
                    "available_qty": 1 if item_available else 0,
                    "line_total": unit_price,
                    "is_available": item_available,
                })
                subtotal += unit_price
                total_units += 1

    return {
        "items": lines,
        "subtotal": subtotal,
        "total_units": total_units,
        "has_unavailable": has_unavailable,
        "warnings": warnings,
    }


def sign_guest_order_token(tenant_id: int, order_code: str) -> str:
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    return hmac.new(
        secret,
        f"guest-order:{tenant_id}:{order_code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_guest_order_token(tenant_id: int, order_code: str, token: str | None) -> bool:
    if not token or not isinstance(token, str):
        return False
    expected = sign_guest_order_token(tenant_id, order_code)
    return hmac.compare_digest(expected, token)


def _generate_order_code(timezone_name: str) -> str:
    stamp = tenant_today(timezone_name).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"ORD-{stamp}-{suffix}"


def place_order(
    tenant_id: int,
    currency_code: str,
    timezone_name: str,
    raw_cart,
    form_data: dict,
    *,
    customer_account_id: int | None = None,
) -> dict:
    """Validate live MySQL prices/availability inside a transaction and persist a pending order."""
    cart = sanitize_cart(raw_cart)
    if not cart:
        raise ValidationError("Giỏ hàng đang trống.")

    request_key = str(form_data.get("request_key") or "").strip().lower()
    if not _UUID_RE.fullmatch(request_key):
        raise ValidationError("Phiên đặt hàng không hợp lệ. Vui lòng tải lại trang thanh toán.")

    try:
        customer_name = text_value(form_data.get("customer_name"), "Họ tên người nhận", 160)
    except ValidationError as exc:
        raise ValidationError(str(exc), field="customer_name") from exc

    try:
        customer_phone = normalize_phone(form_data.get("customer_phone", ""))
    except ValidationError as exc:
        raise ValidationError(str(exc), field="customer_phone") from exc

    raw_email = (form_data.get("customer_email") or "").strip()
    customer_email = ""
    if raw_email:
        try:
            customer_email = normalize_email(raw_email)
        except ValueError as exc:
            raise ValidationError(str(exc), field="customer_email") from exc

    fulfillment_method = (form_data.get("fulfillment_method") or "pickup").strip()
    if fulfillment_method not in {"pickup", "cod_delivery"}:
        raise ValidationError("Hình thức nhận hàng không hợp lệ.", field="fulfillment_method")

    try:
        delivery_address = text_value(
            form_data.get("delivery_address"),
            "Địa chỉ giao hàng",
            255,
            required=(fulfillment_method == "cod_delivery"),
        )
    except ValidationError as exc:
        raise ValidationError(str(exc), field="delivery_address") from exc

    payment_method = "cod" if fulfillment_method == "cod_delivery" else "pay_at_store"
    try:
        customer_note = text_value(form_data.get("customer_note"), "Ghi chú", 500, required=False)
    except ValidationError as exc:
        raise ValidationError(str(exc), field="customer_note") from exc

    product_quantities: dict[int, int] = defaultdict(int)
    pet_ids: list[int] = []
    for entry in cart:
        if entry["item_type"] == "product":
            product_quantities[entry["item_id"]] += entry["quantity"]
        elif entry["item_id"] not in pet_ids:
            pet_ids.append(entry["item_id"])

    with transaction() as connection:
        set_tenant_context(connection, tenant_id)
        existing = storefront_repo.get_order_by_request_key(connection, request_key)
        if existing:
            return {"status": "already_created", "order": _hydrate_order(connection, existing)}

        lines = []
        total = Decimal("0")

        if product_quantities:
            locked_products = product_repo.get_products_by_ids(connection, product_quantities, lock=True)
            by_pid = {int(p["id"]): p for p in locked_products}
            reserved_map = storefront_repo.reserved_product_quantities(
                connection, product_quantities.keys(), lock=True
            )
            for product_id, qty in sorted(product_quantities.items()):
                product = by_pid.get(product_id)
                if not product or not product["active"]:
                    raise ConflictError("Một sản phẩm trong giỏ đã ngừng bán.")
                available = max(0, int(product["stock_qty"]) - int(reserved_map.get(product_id, 0)))
                if available < qty:
                    raise ConflictError(
                        f"Số lượng khả dụng của {product['name']} không đủ (còn {available})."
                    )
                unit_price = Decimal(product["unit_price"])
                line_total = unit_price * qty
                lines.append({
                    "item_type": "product",
                    "product_id": product_id,
                    "pet_id": None,
                    "code": product["code"],
                    "name": product["name"],
                    "unit_price": unit_price,
                    "quantity": qty,
                    "line_total": line_total,
                })
                total += line_total

        if pet_ids:
            locked_pets = storefront_repo.get_pets_for_order_lock(connection, pet_ids)
            by_pet_id = {int(p["id"]): p for p in locked_pets}
            reserved_pets = storefront_repo.locked_pet_ids(connection, pet_ids, lock=True)
            for pet_id in sorted(pet_ids):
                pet = by_pet_id.get(pet_id)
                if not pet or pet["sale_status"] != "available":
                    raise ConflictError("Thú cưng bạn chọn hiện không còn mở bán.")
                if pet_id in reserved_pets:
                    raise ConflictError(f"Thú cưng {pet['name']} hiện đã được giữ cho đơn hàng khác.")
                price = Decimal(pet["sale_price"])
                lines.append({
                    "item_type": "pet",
                    "product_id": None,
                    "pet_id": pet_id,
                    "code": pet["code"],
                    "name": pet["name"],
                    "unit_price": price,
                    "quantity": 1,
                    "line_total": price,
                })
                total += price

        if not lines:
            raise ValidationError("Giỏ hàng không có mặt hàng hợp lệ.")

        if customer_account_id is not None:
            account = storefront_repo.get_account_by_id(connection, customer_account_id)
            if not account or not account["active"]:
                customer_account_id = None

        order_id = None
        for _ in range(5):
            order_code = _generate_order_code(timezone_name)
            try:
                order_id = storefront_repo.create_order(
                    connection,
                    order_code,
                    request_key,
                    customer_account_id,
                    customer_name,
                    customer_phone,
                    customer_email,
                    delivery_address,
                    fulfillment_method,
                    payment_method,
                    currency_code,
                    total,
                    customer_note,
                )
                break
            except IntegrityError:
                again = storefront_repo.get_order_by_request_key(connection, request_key)
                if again:
                    return {"status": "already_created", "order": _hydrate_order(connection, again)}
        if order_id is None:
            raise ConflictError("Không thể tạo mã đơn hàng duy nhất; vui lòng thử lại.")

        for line in lines:
            storefront_repo.add_order_item(connection, order_id, line)
        order = storefront_repo.get_order_by_id(connection, order_id)
        return {"status": "created", "order": _hydrate_order(connection, order)}


def _hydrate_order(connection, order: dict) -> dict:
    hydrated = dict(order)
    hydrated["items"] = storefront_repo.list_order_items(connection, int(order["id"]))
    return hydrated


def get_customer_order(
    tenant_id: int,
    order_code: str,
    *,
    customer_account_id: int | None = None,
    guest_tokens: dict | None = None,
) -> dict:
    clean_code = (order_code or "").strip().upper()
    if not clean_code or len(clean_code) > 32:
        raise NotFoundError("Không tìm thấy đơn hàng.")
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        order = storefront_repo.get_order_by_code(connection, clean_code)
        if not order:
            raise NotFoundError("Không tìm thấy đơn hàng.")
        allowed = False
        if customer_account_id is not None and order.get("customer_account_id") == customer_account_id:
            allowed = True
        elif isinstance(guest_tokens, dict):
            token = guest_tokens.get(clean_code)
            allowed = verify_guest_order_token(tenant_id, clean_code, token)
        if not allowed:
            raise ForbiddenError("Bạn không có quyền xem đơn hàng này.")
        return _hydrate_order(connection, order)


def lookup_guest_order(tenant_id: int, raw_order_code: str, raw_phone: str) -> dict:
    clean_code = (raw_order_code or "").strip().upper()
    if not clean_code or len(clean_code) > 32:
        raise ValidationError("Mã đơn hàng không hợp lệ.")
    phone = normalize_phone(raw_phone)
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        order = storefront_repo.get_order_by_code(connection, clean_code)
        if not order or order["customer_phone"] != phone:
            raise NotFoundError("Không tìm thấy đơn hàng khớp mã đơn và số điện thoại.")
        return _hydrate_order(connection, order)


def list_customer_orders(tenant_id: int, account_id: int) -> list[dict]:
    with read_connection() as connection:
        set_tenant_context(connection, tenant_id)
        return storefront_repo.list_orders_for_account(connection, account_id)


def cancel_customer_pending_order(
    tenant_id: int,
    order_code: str,
    *,
    customer_account_id: int | None = None,
    guest_tokens: dict | None = None,
) -> dict:
    clean_code = (order_code or "").strip().upper()
    with transaction() as connection:
        set_tenant_context(connection, tenant_id)
        row = storefront_repo.get_order_by_code(connection, clean_code)
        if not row:
            raise NotFoundError("Không tìm thấy đơn hàng.")
        order = storefront_repo.get_order_by_id(connection, int(row["id"]), lock=True)
        allowed = False
        if customer_account_id is not None and order.get("customer_account_id") == customer_account_id:
            allowed = True
        elif isinstance(guest_tokens, dict):
            allowed = verify_guest_order_token(tenant_id, clean_code, guest_tokens.get(clean_code))
        if not allowed:
            raise ForbiddenError("Bạn không có quyền hủy đơn hàng này.")
        if order["order_status"] == "cancelled":
            return _hydrate_order(connection, order)
        if order["order_status"] != "pending":
            raise ConflictError("Chỉ có thể hủy đơn khi đơn đang ở trạng thái chờ xác nhận.")
        storefront_repo.update_order_state(
            connection, int(order["id"]), order_status="cancelled", set_cancelled_at=True
        )
        updated = storefront_repo.get_order_by_id(connection, int(order["id"]))
        return _hydrate_order(connection, updated)


# ---------- Staff / Admin Storefront Order Processing ----------
def list_staff_orders(actor_id: int, search: str = "", status: str = "", page=1, tenant_id=None) -> dict:
    if status not in ("", "pending", "confirmed", "preparing", "fulfilled", "ready_completed", "rejected", "cancelled"):
        status = ""
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        total = storefront_repo.count_orders_for_staff(connection, search, status)
        _curr, offset, pagination = page_window(page, total)
        items = storefront_repo.list_orders_for_staff_page(
            connection, search, status, pagination["page_size"], offset
        )
    return {"items": items, "pagination": pagination}


def get_staff_order(actor_id: int, order_id, tenant_id=None) -> dict:
    oid = positive_id(order_id, "Đơn hàng")
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        order = storefront_repo.get_order_by_id(connection, oid)
        if not order:
            raise NotFoundError("Không tìm thấy đơn hàng khách đặt.")
        return _hydrate_order(connection, order)


def process_staff_order(
    actor_id: int,
    order_id,
    action: str,
    staff_note: str = "",
    tenant_id=None,
    *,
    payment_confirmed: bool = False,
    collected_amount=None,
) -> dict:
    oid = positive_id(order_id, "Đơn hàng")
    action = (action or "").strip()
    if action not in {"confirm", "prepare", "fulfill", "complete_payment", "reject", "cancel"}:
        raise ValidationError("Thao tác xử lý đơn hàng không hợp lệ.")
    clean_note = text_value(staff_note, "Ghi chú xử lý", 500, required=False)

    with transaction() as connection:
        actor = require_actor(connection, actor_id, tenant_id=tenant_id)
        order = storefront_repo.get_order_by_id(connection, oid, lock=True)
        if not order:
            raise NotFoundError("Không tìm thấy đơn hàng khách đặt.")
        items = storefront_repo.list_order_items(connection, oid, lock=True)
        current_status = order["order_status"]

        if action == "confirm":
            if current_status == "confirmed":
                return {"status": "unchanged", "order": _hydrate_order(connection, order)}
            if current_status != "pending":
                raise ConflictError("Chỉ có thể xác nhận đơn hàng đang chờ xác nhận.")
            _reserve_items_for_confirmation(connection, oid, items)
            storefront_repo.update_order_state(
                connection,
                oid,
                order_status="confirmed",
                processed_by=actor_id,
                staff_note=clean_note or order["staff_note"],
                set_confirmed_at=True,
            )
            audit_repo.add_event(
                connection, actor_id, "storefront_order.confirmed", "customer_order", oid,
                f"Xác nhận đơn online {order['order_code']}",
                {"order_code": order["order_code"], "total_amount": str(order["total_amount"])},
            )
        elif action == "prepare":
            if current_status == "preparing":
                return {"status": "unchanged", "order": _hydrate_order(connection, order)}
            if current_status != "confirmed":
                raise ConflictError("Đơn hàng cần được xác nhận trước khi chuyển sang chuẩn bị.")
            storefront_repo.update_order_state(
                connection,
                oid,
                order_status="preparing",
                processed_by=actor_id,
                staff_note=clean_note or order["staff_note"],
            )
            audit_repo.add_event(
                connection, actor_id, "storefront_order.preparing", "customer_order", oid,
                f"Chuẩn bị đơn online {order['order_code']}",
                {"order_code": order["order_code"]},
            )
        elif action == "fulfill":
            if current_status == "fulfilled":
                return {"status": "unchanged", "order": _hydrate_order(connection, order)}
            if current_status not in {"confirmed", "preparing"}:
                raise ConflictError("Đơn hàng cần được xác nhận trước khi bàn giao hoặc giao hàng.")
            storefront_repo.update_order_state(
                connection,
                oid,
                order_status="fulfilled",
                payment_status="unpaid",
                processed_by=actor_id,
                staff_note=clean_note or order["staff_note"],
                set_fulfilled_at=True,
            )
            audit_repo.add_event(
                connection, actor_id, "storefront_order.fulfilled", "customer_order", oid,
                f"Đã giao / sẵn sàng bàn giao đơn {order['order_code']} (chờ thu tiền)",
                {"order_code": order["order_code"], "payment_status": "unpaid"},
            )
        elif action in {"reject", "cancel"}:
            if current_status in {"rejected", "cancelled"}:
                return {"status": "unchanged", "order": _hydrate_order(connection, order)}
            if current_status == "ready_completed" or order["payment_status"] == "paid":
                raise ConflictError("Đơn đã hoàn tất thanh toán; không thể từ chối hoặc hủy.")
            target_status = "rejected" if action == "reject" else "cancelled"
            storefront_repo.release_pet_locks_for_order(connection, oid)
            storefront_repo.update_order_state(
                connection,
                oid,
                order_status=target_status,
                processed_by=actor_id,
                staff_note=clean_note or order["staff_note"],
                set_cancelled_at=True,
            )
            audit_repo.add_event(
                connection, actor_id, f"storefront_order.{target_status}", "customer_order", oid,
                f"{'Từ chối' if action == 'reject' else 'Hủy'} đơn online {order['order_code']}",
                {"order_code": order["order_code"]},
            )
        elif action == "complete_payment":
            if current_status == "ready_completed" and order["payment_status"] == "paid":
                return {"status": "already_completed", "order": _hydrate_order(connection, order)}
            if current_status not in {"confirmed", "preparing", "fulfilled"}:
                raise ConflictError("Cần xác nhận đơn hàng trước khi hoàn tất và thu tiền.")
            if not payment_confirmed:
                raise ValidationError(
                    "Cần xác nhận đã thu đủ tiền thực tế trước khi hoàn tất thanh toán."
                )
            if collected_amount is not None and str(collected_amount).strip() != "":
                raw_amt = str(collected_amount).strip().replace(",", "")
                try:
                    parsed_amt = Decimal(raw_amt)
                except InvalidOperation as exc:
                    raise ValidationError("Số tiền thực thu không hợp lệ.") from exc
                if parsed_amt != Decimal(order["total_amount"]):
                    raise ValidationError("Số tiền thực thu phải khớp đúng tổng giá trị đơn hàng.")
            _complete_order_to_paid_invoice(connection, actor_id, actor, order, items, clean_note)

        updated = storefront_repo.get_order_by_id(connection, oid)
        return {"status": "updated", "order": _hydrate_order(connection, updated)}


def _reserve_items_for_confirmation(connection, order_id: int, items: list[dict]) -> None:
    product_quantities: dict[int, int] = defaultdict(int)
    pet_ids: list[int] = []
    for item in items:
        if item["item_type"] == "product":
            product_quantities[int(item["product_id"])] += int(item["quantity"])
        else:
            pet_ids.append(int(item["pet_id"]))

    if product_quantities:
        locked_products = product_repo.get_products_by_ids(connection, product_quantities, lock=True)
        by_pid = {int(p["id"]): p for p in locked_products}
        other_reserved = storefront_repo.reserved_product_quantities(
            connection, product_quantities.keys(), exclude_order_id=order_id, lock=True
        )
        for product_id, qty in sorted(product_quantities.items()):
            product = by_pid.get(product_id)
            if not product or not product["active"]:
                raise ConflictError("Một sản phẩm trong đơn đã ngừng bán.")
            available = max(0, int(product["stock_qty"]) - int(other_reserved.get(product_id, 0)))
            if available < qty:
                raise ConflictError(
                    f"Tồn kho của {product['name']} không đủ để xác nhận đơn."
                )

    if pet_ids:
        locked_pets = storefront_repo.get_pets_for_order_lock(connection, pet_ids)
        by_pet = {int(p["id"]): p for p in locked_pets}
        for pet_id in sorted(pet_ids):
            pet = by_pet.get(pet_id)
            if not pet or pet["sale_status"] != "available":
                raise ConflictError("Thú cưng trong đơn không còn sẵn sàng để bán.")
            try:
                storefront_repo.lock_pet_for_order(connection, pet_id, order_id)
            except IntegrityError as exc:
                raise ConflictError(
                    f"Thú cưng {pet['name']} đã được giữ cho một đơn hàng xác nhận khác."
                ) from exc


def _complete_order_to_paid_invoice(
    connection,
    actor_id: int,
    actor: dict,
    order: dict,
    items: list[dict],
    clean_note: str,
) -> None:
    order_id = int(order["id"])
    product_quantities: dict[int, int] = defaultdict(int)
    pet_ids: list[int] = []
    for item in items:
        if item["item_type"] == "product":
            product_quantities[int(item["product_id"])] += int(item["quantity"])
        else:
            pet_ids.append(int(item["pet_id"]))

    if product_quantities:
        products = product_repo.get_products_by_ids(connection, product_quantities, lock=True)
        by_pid = {int(p["id"]): p for p in products}
        for product_id, qty in sorted(product_quantities.items()):
            product = by_pid.get(product_id)
            if not product or not product["active"]:
                raise ConflictError("Một sản phẩm trên đơn đã ngừng bán.")
            if int(product["stock_qty"]) < qty:
                raise ConflictError(f"Tồn kho {product['name']} không đủ để xuất bán.")

    if pet_ids:
        pets = pet_repo.get_pets_by_ids(connection, pet_ids, lock=True)
        by_pet = {int(p["id"]): p for p in pets}
        other_locks = storefront_repo.locked_pet_ids(connection, pet_ids, exclude_order_id=order_id)
        if other_locks:
            raise ConflictError("Một thú cưng đang được giữ cho đơn hàng khác.")
        for pet_id in sorted(pet_ids):
            pet = by_pet.get(pet_id)
            if not pet or pet["sale_status"] != "available":
                raise ConflictError("Một thú cưng trên đơn đã được bán.")

    crm_customer = storefront_repo.find_active_crm_customer_by_phone(connection, order["customer_phone"])
    if crm_customer:
        crm_customer_id = int(crm_customer["id"])
    else:
        crm_customer_id = customer_repo.create_customer(
            connection,
            order["customer_name"],
            order["customer_phone"],
            order["delivery_address"] or "Khách đặt online",
        )

    invoice_note = f"Đơn online {order['order_code']} ({order['payment_method']})"
    invoice_id = invoice_repo.create_invoice(
        connection, crm_customer_id, actor_id, invoice_note, actor["default_currency"]
    )
    for item in items:
        invoice_repo.add_item(
            connection,
            invoice_id,
            {
                "item_type": item["item_type"],
                "product_id": item["product_id"],
                "pet_id": item["pet_id"],
                "code": item["item_code_snapshot"],
                "name": item["name_snapshot"],
                "unit_price": Decimal(item["unit_price"]),
                "quantity": int(item["quantity"]),
                "line_total": Decimal(item["line_total"]),
            },
            actor["default_currency"],
        )

    for product_id, qty in sorted(product_quantities.items()):
        if product_repo.reserve_stock_for_sale(connection, product_id, qty) != 1:
            raise ConflictError("Tồn kho vừa thay đổi; không thể hoàn tất đơn hàng.")
        product_repo.add_stock_movement(
            connection,
            product_id,
            -qty,
            f"Bán từ đơn online {order['order_code']} (HĐ #{invoice_id})",
            actor_id,
            invoice_id,
        )

    for pet_id in sorted(pet_ids):
        if pet_repo.mark_sold(connection, pet_id, crm_customer_id) != 1:
            raise ConflictError("Thú cưng vừa được bán ở giao dịch khác.")

    storefront_repo.release_pet_locks_for_order(connection, order_id)
    if invoice_repo.update_paid(connection, invoice_id) != 1:
        raise ConflictError("Không thể hoàn tất trạng thái thanh toán hóa đơn.")

    storefront_repo.update_order_state(
        connection,
        order_id,
        order_status="ready_completed",
        payment_status="paid",
        processed_by=actor_id,
        staff_note=clean_note or order["staff_note"],
        customer_id=crm_customer_id,
        invoice_id=invoice_id,
        set_completed_at=True,
    )
    audit_repo.add_event(
        connection,
        actor_id,
        "storefront_order.completed",
        "customer_order",
        order_id,
        f"Hoàn tất & thu tiền đơn online {order['order_code']} (HĐ #{invoice_id})",
        {
            "order_code": order["order_code"],
            "invoice_id": invoice_id,
            "customer_id": crm_customer_id,
            "total_amount": str(order["total_amount"]),
        },
    )

