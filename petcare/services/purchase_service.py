"""Admin workflows for suppliers, purchase orders and partial stock receipts."""

from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from petcare.database.connection import read_connection, transaction
from petcare.email_address import normalize_email
from petcare.repositories import audit_repo, product_repo, purchase_repo
from petcare.services.common import (
    integer_value,
    money_value,
    page_window,
    phone_value,
    positive_id,
    require_actor,
    text_value,
)
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError


MAX_STOCK_QTY = 2_147_483_647
MAX_ORDER_LINES = 100
MAX_AMOUNT = Decimal("9999999999999999.9999")
ORDER_STATUSES = {"ordered", "partially_received", "received", "cancelled"}


def list_suppliers(actor_id, search="", include_inactive=False, page="1", tenant_id=None):
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        total = purchase_repo.count_suppliers(connection, search, include_inactive)
        _page, offset, pagination = page_window(page, total)
        items = purchase_repo.list_suppliers_page(
            connection, search, include_inactive, pagination["page_size"], offset
        )
    return {"items": items, "pagination": pagination}


def _supplier_data(data):
    values, errors = {}, {}
    validators = {
        "name": lambda raw: text_value(raw, "Tên nhà cung cấp", 160),
        "contact_name": lambda raw: text_value(raw, "Người liên hệ", 160, required=False),
        "address": lambda raw: text_value(raw, "Địa chỉ", 255, required=False),
    }
    for field, validator in validators.items():
        try:
            values[field] = validator(data.get(field))
        except ValidationError as exc:
            errors[field] = str(exc)

    raw_phone = data.get("phone")
    try:
        values["phone"] = phone_value(raw_phone) if raw_phone and raw_phone.strip() else ""
    except (AttributeError, ValidationError):
        errors["phone"] = "Số điện thoại nhà cung cấp không hợp lệ."

    try:
        raw_email = text_value(data.get("email"), "Email", 254, required=False)
        normalized_email = normalize_email(raw_email) if raw_email else ""
        if raw_email and not normalized_email:
            raise ValidationError("Email nhà cung cấp chưa đúng định dạng.")
        values["email"] = normalized_email
    except ValidationError as exc:
        errors["email"] = str(exc)
    if errors:
        raise ValidationError(next(iter(errors.values())), field_errors=errors)
    return values


def create_supplier(actor_id, data, tenant_id=None):
    supplier = _supplier_data(data)
    try:
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            supplier_id = purchase_repo.create_supplier(connection, supplier)
            audit_repo.add_event(
                connection, actor_id, "supplier.created", "supplier", supplier_id,
                f"Thêm nhà cung cấp #{supplier_id}",
            )
            return supplier_id
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Tên nhà cung cấp đã tồn tại trong cửa hàng.") from exc
        raise


def get_supplier(actor_id, supplier_id, tenant_id=None):
    supplier_id = positive_id(supplier_id, "Nhà cung cấp")
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        supplier = purchase_repo.get_supplier(connection, supplier_id)
    if not supplier:
        raise NotFoundError("Không tìm thấy nhà cung cấp.")
    return supplier


def update_supplier(actor_id, supplier_id, data, tenant_id=None):
    supplier_id = positive_id(supplier_id, "Nhà cung cấp")
    supplier = _supplier_data(data)
    try:
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            current = purchase_repo.get_supplier(connection, supplier_id, lock=True)
            if not current:
                raise NotFoundError("Không tìm thấy nhà cung cấp.")
            changed_fields = [
                field for field in ("name", "contact_name", "phone", "email", "address")
                if current[field] != supplier[field]
            ]
            changed = purchase_repo.update_supplier(connection, supplier_id, supplier)
            if changed:
                audit_repo.add_event(
                    connection, actor_id, "supplier.updated", "supplier", supplier_id,
                    f"Cập nhật nhà cung cấp #{supplier_id}",
                    {"changed_fields": changed_fields},
                )
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Tên nhà cung cấp đã được sử dụng.") from exc
        raise


def set_supplier_active(actor_id, supplier_id, active, tenant_id=None):
    supplier_id = positive_id(supplier_id, "Nhà cung cấp")
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        supplier = purchase_repo.get_supplier(connection, supplier_id, lock=True)
        if not supplier:
            raise NotFoundError("Không tìm thấy nhà cung cấp.")
        if bool(supplier["active"]) == bool(active):
            return
        changed = purchase_repo.set_supplier_active(connection, supplier_id, int(bool(active)))
        if not changed:
            raise ConflictError("Nhà cung cấp vừa được thay đổi; hãy tải lại trang.")
        audit_repo.add_event(
            connection, actor_id, "supplier.status_changed", "supplier", supplier_id,
            f"{'Kích hoạt' if active else 'Ngừng sử dụng'} nhà cung cấp #{supplier_id}",
            {"active": bool(active)},
        )


def list_purchase_orders(actor_id, status=None, page="1", tenant_id=None):
    if status and status not in ORDER_STATUSES:
        raise ValidationError("Trạng thái đơn nhập không hợp lệ.")
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        total = purchase_repo.count_purchase_orders(connection, status)
        _page, offset, pagination = page_window(page, total)
        items = purchase_repo.list_purchase_orders_page(
            connection, status, pagination["page_size"], offset
        )
    return {"items": items, "pagination": pagination}


def list_active_suppliers(actor_id, tenant_id=None):
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        return purchase_repo.list_active_suppliers(connection)


def search_active_products(actor_id, search="", tenant_id=None):
    search = text_value(search or "", "Từ khóa", 80, required=False)
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        return product_repo.search_active_products_for_purchase(connection, search, limit=20)


def _parse_order_lines(lines, currency_code):
    if not isinstance(lines, (list, tuple)) or not 1 <= len(lines) <= MAX_ORDER_LINES:
        raise ValidationError(f"Đơn nhập cần từ 1 đến {MAX_ORDER_LINES} dòng sản phẩm.")
    parsed = []
    product_ids = set()
    total = Decimal("0")
    for raw in lines:
        if not isinstance(raw, dict):
            raise ValidationError("Danh sách sản phẩm nhập không hợp lệ.")
        product_id = positive_id(raw.get("product_id"), "Sản phẩm")
        if product_id in product_ids:
            raise ValidationError("Mỗi sản phẩm chỉ được xuất hiện một lần trong đơn nhập.")
        product_ids.add(product_id)
        quantity = integer_value(raw.get("quantity"), "Số lượng đặt", 1, MAX_STOCK_QTY)
        unit_cost = money_value(raw.get("unit_cost"), "Giá nhập", currency_code)
        line_total = unit_cost * quantity
        if line_total > MAX_AMOUNT:
            raise ValidationError("Thành tiền một dòng vượt giới hạn lưu trữ.")
        total += line_total
        parsed.append({
            "product_id": product_id,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "line_total": line_total,
        })
    if total > MAX_AMOUNT:
        raise ValidationError("Tổng đơn nhập vượt giới hạn lưu trữ.")
    return parsed


def create_purchase_order(actor_id, data, lines, tenant_id=None):
    supplier_id = positive_id(data.get("supplier_id"), "Nhà cung cấp")
    note = text_value(data.get("note"), "Ghi chú", 500, required=False)
    try:
        with transaction() as connection:
            actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            parsed = _parse_order_lines(lines, actor["default_currency"])
            supplier = purchase_repo.get_supplier(connection, supplier_id, lock=True)
            if not supplier or not supplier["active"]:
                raise ValidationError("Nhà cung cấp không tồn tại hoặc đã ngừng sử dụng.")
            products = product_repo.get_products_by_ids(
                connection, [line["product_id"] for line in parsed],
                lock=True, active_only=True,
            )
            by_id = {product["id"]: product for product in products}
            if len(by_id) != len(parsed):
                raise ValidationError("Một sản phẩm không tồn tại hoặc đã ngừng bán.")
            for line in parsed:
                product = by_id[line["product_id"]]
                line["code"] = product["code"]
                line["name"] = product["name"]
            total = sum((line["line_total"] for line in parsed), Decimal("0"))
            order_id = purchase_repo.create_purchase_order(
                connection, supplier_id, supplier["name"], actor_id,
                actor["default_currency"], total, note,
            )
            purchase_repo.add_purchase_order_items(connection, order_id, parsed)
            audit_repo.add_event(
                connection, actor_id, "purchase_order.created", "purchase_order", order_id,
                f"Tạo đơn nhập #{order_id}",
                {"supplier_id": supplier_id, "line_count": len(parsed), "total": str(total),
                 "currency_code": actor["default_currency"]},
            )
            return order_id
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Không thể tạo đơn nhập do dòng sản phẩm bị trùng.") from exc
        raise


def get_purchase_order_detail(actor_id, purchase_order_id, tenant_id=None):
    purchase_order_id = positive_id(purchase_order_id, "Đơn nhập")
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        order = purchase_repo.get_purchase_order(connection, purchase_order_id)
        if not order:
            raise NotFoundError("Không tìm thấy đơn nhập.")
        items = purchase_repo.list_purchase_order_items(connection, purchase_order_id)
    order["items"] = items
    order["ordered_units"] = sum(item["quantity_ordered"] for item in items)
    order["received_units"] = sum(item["quantity_received"] for item in items)
    return order


def _parse_receipt_lines(lines):
    if not isinstance(lines, (list, tuple)) or not lines:
        raise ValidationError("Chưa có dòng hàng cần nhận.")
    parsed = []
    seen = set()
    for raw in lines:
        if not isinstance(raw, dict):
            raise ValidationError("Danh sách hàng nhận không hợp lệ.")
        item_id = positive_id(raw.get("item_id"), "Dòng đơn nhập")
        if item_id in seen:
            raise ValidationError("Dòng hàng bị lặp trong yêu cầu nhận.")
        seen.add(item_id)
        quantity = integer_value(raw.get("quantity"), "Số lượng nhận thêm", 0, MAX_STOCK_QTY)
        if quantity:
            parsed.append({"item_id": item_id, "quantity": quantity})
    if not parsed:
        raise ValidationError("Nhập số lượng lớn hơn 0 cho ít nhất một dòng hàng.")
    return parsed


def _receipt_request_key(value):
    if value is None:
        return str(uuid4())
    raw = str(value).strip()
    try:
        normalized = str(UUID(raw))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValidationError("Mã yêu cầu nhận hàng không hợp lệ. Hãy tải lại trang.") from exc
    if normalized != raw.lower():
        raise ValidationError("Mã yêu cầu nhận hàng không hợp lệ. Hãy tải lại trang.")
    return normalized


def _receipt_payload_hash(lines):
    canonical = ",".join(
        f"{line['item_id']}:{line['quantity']}"
        for line in sorted(lines, key=lambda row: row["item_id"])
    )
    return sha256(canonical.encode("ascii")).hexdigest()


def receive_purchase_order(actor_id, purchase_order_id, lines, tenant_id=None, request_key=None):
    purchase_order_id = positive_id(purchase_order_id, "Đơn nhập")
    parsed = _parse_receipt_lines(lines)
    request_key = _receipt_request_key(request_key)
    payload_hash = _receipt_payload_hash(parsed)
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        order = purchase_repo.get_purchase_order(connection, purchase_order_id, lock=True)
        if not order:
            raise NotFoundError("Không tìm thấy đơn nhập.")
        previous_request = purchase_repo.find_receipt_request(connection, request_key)
        if previous_request:
            if (
                previous_request["purchase_order_id"] != purchase_order_id
                or previous_request["payload_hash"] != payload_hash
            ):
                raise ConflictError("Mã yêu cầu nhận hàng đã được dùng cho nội dung khác.")
            return order["status"]
        if order["status"] in {"received", "cancelled"}:
            raise ConflictError("Đơn nhập đã đóng và không thể nhận thêm hàng.")
        order_items = purchase_repo.lock_purchase_order_items(connection, purchase_order_id)
        item_by_id = {item["id"]: item for item in order_items}
        if any(line["item_id"] not in item_by_id for line in parsed):
            raise ValidationError("Một dòng hàng không thuộc đơn nhập này.")
        for line in parsed:
            item = item_by_id[line["item_id"]]
            if line["quantity"] > item["quantity_ordered"] - item["quantity_received"]:
                raise ValidationError(
                    f"Số lượng nhận của {item['product_name_snapshot']} vượt số còn lại."
                )
            line["item"] = item

        products = product_repo.get_products_by_ids(
            connection, [line["item"]["product_id"] for line in parsed], lock=True
        )
        product_by_id = {product["id"]: product for product in products}
        if len(product_by_id) != len({line["item"]["product_id"] for line in parsed}):
            raise ConflictError("Một sản phẩm trong đơn nhập không còn tồn tại.")
        for line in parsed:
            item = line["item"]
            product = product_by_id[item["product_id"]]
            updated_stock = product["stock_qty"] + line["quantity"]
            if updated_stock > MAX_STOCK_QTY:
                raise ValidationError(
                    f"Tồn kho {product['name']} sẽ vượt {MAX_STOCK_QTY:,} đơn vị."
                )
            line["stock_after"] = updated_stock

        try:
            purchase_repo.create_receipt_request(
                connection, purchase_order_id, request_key, payload_hash
            )
        except Exception as exc:
            if getattr(exc, "errno", None) == 1062:
                raise ConflictError("Mã yêu cầu nhận hàng đã được sử dụng.") from exc
            raise

        stock_after = {}
        for line in parsed:
            item = line["item"]
            product = product_by_id[item["product_id"]]
            if not product_repo.adjust_stock(connection, product["id"], line["quantity"]):
                raise ConflictError("Tồn kho vừa thay đổi; hãy tải lại đơn nhập rồi thử lại.")
            if not purchase_repo.add_received_quantity(
                connection, purchase_order_id, item["id"], line["quantity"]
            ):
                raise ConflictError("Số lượng nhận vừa thay đổi; hãy tải lại đơn nhập.")
            product_repo.add_stock_movement(
                connection, product["id"], line["quantity"],
                f"Nhận theo đơn nhập #{purchase_order_id}", actor_id,
                purchase_order_id=purchase_order_id,
                purchase_order_item_id=item["id"],
            )
            stock_after[item["product_id"]] = line["stock_after"]

        all_received = all(
            item["quantity_received"] + next(
                (line["quantity"] for line in parsed if line["item_id"] == item["id"]), 0
            ) >= item["quantity_ordered"]
            for item in order_items
        )
        next_status = "received" if all_received else "partially_received"
        if not purchase_repo.set_purchase_order_status(connection, purchase_order_id, next_status):
            raise ConflictError("Không thể cập nhật trạng thái đơn nhập.")
        audit_repo.add_event(
            connection, actor_id, "purchase_order.received", "purchase_order", purchase_order_id,
            f"Nhận hàng đơn nhập #{purchase_order_id}",
            {"lines": len(parsed), "units": sum(line["quantity"] for line in parsed),
             "status": next_status, "stock_after": stock_after},
        )
        return next_status


def cancel_purchase_order(actor_id, purchase_order_id, tenant_id=None):
    purchase_order_id = positive_id(purchase_order_id, "Đơn nhập")
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        order = purchase_repo.get_purchase_order(connection, purchase_order_id, lock=True)
        if not order:
            raise NotFoundError("Không tìm thấy đơn nhập.")
        if order["status"] in {"received", "cancelled"}:
            raise ConflictError("Đơn nhập đã đóng và không thể hủy.")
        if not purchase_repo.set_purchase_order_status(connection, purchase_order_id, "cancelled"):
            raise ConflictError("Không thể hủy đơn nhập.")
        audit_repo.add_event(
            connection, actor_id, "purchase_order.cancelled", "purchase_order", purchase_order_id,
            f"Hủy phần hàng còn lại của đơn nhập #{purchase_order_id}",
            {"previous_status": order["status"]},
        )
