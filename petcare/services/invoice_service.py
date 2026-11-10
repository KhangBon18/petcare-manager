from collections import defaultdict
from decimal import Decimal

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, customer_repo, invoice_repo, pet_repo, product_repo, refund_repo
from petcare.services.common import (
    integer_value,
    page_window,
    positive_id,
    require_actor,
    text_value,
)
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError


def list_invoices(actor_id, search="", status="", page=None, tenant_id=None):
    if status not in ("", "unpaid", "paid", "cancelled"):
        status = ""
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        if page is not None:
            total = invoice_repo.count_invoices(connection, search, status)
            _current_page, offset, pagination = page_window(page, total)
            return {
                "items": invoice_repo.list_invoices_page(
                    connection, search, status, pagination["page_size"], offset
                ),
                "pagination": pagination,
            }
        return invoice_repo.list_invoices(connection, search, status)


def get_invoice(actor_id, invoice_id, tenant_id=None):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        invoice = invoice_repo.get_invoice(connection, invoice_id)
        items = invoice_repo.list_items(connection, invoice_id) if invoice else []
        refunds = refund_repo.list_invoice_refunds(connection, invoice_id) if invoice and invoice["status"] == "paid" else []
        refund_items = refund_repo.list_invoice_refund_items(connection, invoice_id) if refunds else []
        refunded_quantities = refund_repo.refunded_quantities(connection, invoice_id) if invoice and invoice["status"] == "paid" else {}
    if not invoice:
        raise NotFoundError("Không tìm thấy hóa đơn.")
    invoice["items"] = items
    invoice["total_amount"] = sum((item["line_total"] for item in items), Decimal("0"))
    for item in items:
        item["refunded_quantity"] = refunded_quantities.get(item["id"], 0)
        item["refundable_quantity"] = max(0, item["quantity"] - item["refunded_quantity"])
    refund_items_by_refund = defaultdict(list)
    for item in refund_items:
        refund_items_by_refund[item["refund_id"]].append(item)
    for refund in refunds:
        refund["items"] = refund_items_by_refund[refund["id"]]
    invoice["refunds"] = refunds
    invoice["total_refunded"] = sum((refund["refund_total"] for refund in refunds), Decimal("0"))
    invoice["net_paid"] = invoice["total_amount"] - invoice["total_refunded"]
    invoice["refund_complete"] = bool(items) and all(
        item["refundable_quantity"] == 0 for item in items
    )
    return invoice


def _normalize_items(raw_items):
    if not raw_items:
        raise ValidationError("Hóa đơn cần ít nhất một mặt hàng.")
    products = defaultdict(int)
    pets = set()
    errors = {}
    for index, raw in enumerate(raw_items):
        item_type = (raw.get("item_type") or "").strip()
        field = f"item_{index}"
        try:
            item_id = positive_id(raw.get("item_id"), "Mặt hàng")
            if item_type not in {"product", "pet"}:
                raise ValidationError("Loại mặt hàng không hợp lệ.")
            if item_type == "pet" and item_id in pets:
                raise ValidationError("Một thú cưng chỉ được thêm một lần vào hóa đơn.")
            field = f"quantity_{index}"
            quantity = integer_value(
                raw.get("quantity", "1"), "Số lượng", 1,
                1 if item_type == "pet" else 2_000_000_000,
            )
            if item_type == "product":
                products[item_id] += quantity
            else:
                pets.add(item_id)
        except ValidationError as exc:
            errors[field] = str(exc)
    if errors:
        raise ValidationError(next(iter(errors.values())), field_errors=errors)
    return products, sorted(pets)


def create_invoice(actor_id, data, raw_items, tenant_id=None):
    errors = {}
    try:
        customer_id = positive_id(data.get("customer_id"), "Khách hàng")
    except ValidationError as exc:
        errors["customer_id"] = str(exc)
    try:
        note = text_value(data.get("note"), "Ghi chú", 500, required=False)
    except ValidationError as exc:
        errors["note"] = str(exc)
    try:
        product_quantities, pet_ids = _normalize_items(raw_items)
    except ValidationError as exc:
        errors.update(exc.field_errors or {"item_0": str(exc)})
    if errors:
        raise ValidationError(next(iter(errors.values())), field_errors=errors)

    def line_field(kind, item_id, field="item"):
        return next(
            f"{field}_{index}" for index, raw in enumerate(raw_items)
            if raw["item_type"] == kind and int(raw["item_id"]) == item_id
        )

    with transaction() as connection:
        actor = require_actor(connection, actor_id, tenant_id=tenant_id)
        customer = customer_repo.get_customer(connection, customer_id)
        if not customer or not customer["active"]:
            raise ValidationError("Khách hàng không tồn tại hoặc đã ngừng sử dụng.", field="customer_id")
        lines = []
        total = Decimal("0")
        for product_id, quantity in sorted(product_quantities.items()):
            product = product_repo.get_product(connection, product_id)
            if not product or not product["active"]:
                raise ValidationError("Sản phẩm không còn được bán.", field=line_field("product", product_id))
            if product["stock_qty"] < quantity:
                raise ValidationError(
                    f"Tồn hiện tại của {product['name']} không đủ; hóa đơn chưa giữ hàng.",
                    field=line_field("product", product_id, "quantity"),
                )
            unit_price = Decimal(product["unit_price"])
            line_total = unit_price * quantity
            lines.append({
                "item_type": "product", "product_id": product_id, "pet_id": None,
                "code": product["code"], "name": product["name"],
                "unit_price": unit_price,
                "quantity": quantity, "line_total": line_total,
            })
            total += line_total
        for pet_id in pet_ids:
            pet = pet_repo.get_pet(connection, pet_id)
            if not pet or pet["sale_status"] != "available":
                raise ValidationError("Thú cưng đã chọn không còn sẵn sàng để bán.", field=line_field("pet", pet_id))
            line_total = Decimal(pet["sale_price"])
            lines.append({
                "item_type": "pet", "product_id": None, "pet_id": pet_id,
                "code": pet["code"], "name": pet["name"],
                "unit_price": line_total, "quantity": 1,
                "line_total": line_total,
            })
            total += line_total
        if not lines:
            raise ValidationError("Hóa đơn cần ít nhất một mặt hàng.")
        if total > Decimal("9999999999999999.9999"):
            raise ValidationError("Tổng hóa đơn vượt giới hạn.")
        invoice_id = invoice_repo.create_invoice(
            connection, customer_id, actor_id, note, actor["default_currency"]
        )
        for line in lines:
            invoice_repo.add_item(
                connection, invoice_id, line, actor["default_currency"]
            )
        audit_repo.add_event(
            connection, actor_id, "invoice.created", "invoice", invoice_id,
            f"Tạo hóa đơn #{invoice_id}",
            {"customer_id": customer_id, "line_count": len(lines), "total_amount": str(total),
             "currency_code": actor["default_currency"]},
        )
        return invoice_id


def pay_invoice(actor_id, invoice_id, tenant_id=None):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with transaction() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        invoice = invoice_repo.get_invoice(connection, invoice_id, lock=True)
        if not invoice:
            raise NotFoundError("Không tìm thấy hóa đơn.")
        if invoice["status"] == "paid":
            return "already_paid"
        if invoice["status"] != "unpaid":
            raise ConflictError("Hóa đơn đã hủy và không thể thanh toán.")
        items = invoice_repo.get_items_for_update(connection, invoice_id)
        if not items:
            raise ConflictError("Hóa đơn không có mặt hàng.")
        quantities = defaultdict(int)
        pet_ids = []
        for item in items:
            if item["item_type"] == "product":
                quantities[item["product_id"]] += item["quantity"]
            else:
                pet_ids.append(item["pet_id"])
        if quantities:
            products = product_repo.get_products_by_ids(
                connection, quantities, lock=True
            )
            by_id = {product["id"]: product for product in products}
            for product_id, quantity in sorted(quantities.items()):
                product = by_id.get(product_id)
                if not product or not product["active"]:
                    raise ConflictError("Một sản phẩm trên hóa đơn đã ngừng bán.")
                if product["stock_qty"] < quantity:
                    raise ConflictError(
                        f"Tồn kho {product['name']} đã thay đổi; chưa thu tiền."
                    )
            for product_id, quantity in sorted(quantities.items()):
                if product_repo.reserve_stock_for_sale(connection, product_id, quantity) != 1:
                    raise ConflictError("Tồn kho vừa thay đổi; vui lòng tải lại hóa đơn.")
                product_repo.add_stock_movement(
                    connection,
                    product_id,
                    -quantity,
                    f"Bán theo hóa đơn #{invoice_id}",
                    actor_id,
                    invoice_id,
                )
        if pet_ids:
            pets = pet_repo.get_pets_by_ids(connection, pet_ids, lock=True)
            by_id = {pet["id"]: pet for pet in pets}
            if any(by_id.get(pet_id, {}).get("sale_status") != "available" for pet_id in pet_ids):
                raise ConflictError("Một cá thể thú cưng đã được bán.")
            for pet_id in sorted(pet_ids):
                if pet_repo.mark_sold(connection, pet_id, invoice["customer_id"]) != 1:
                    raise ConflictError("Thú cưng vừa được bán ở giao dịch khác.")
        if invoice_repo.update_paid(connection, invoice_id) != 1:
            raise ConflictError("Không thể cập nhật trạng thái thanh toán.")
        audit_repo.add_event(
            connection, actor_id, "invoice.paid", "invoice", invoice_id,
            f"Thu tiền hóa đơn #{invoice_id}",
            {
                "customer_id": invoice["customer_id"],
                "line_count": len(items),
                "total_amount": str(sum((Decimal(item["line_total"]) for item in items), Decimal("0"))),
                "currency_code": invoice["currency_code"],
            },
        )
    return "paid"


def cancel_invoice(actor_id, invoice_id, tenant_id=None):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with transaction() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        invoice = invoice_repo.get_invoice(connection, invoice_id, lock=True)
        if not invoice:
            raise NotFoundError("Không tìm thấy hóa đơn.")
        if invoice["status"] == "paid":
            raise ConflictError("Hóa đơn đã thanh toán không thể hủy.")
        if invoice["status"] == "cancelled":
            return "already_cancelled"
        if invoice_repo.update_cancelled(connection, invoice_id) != 1:
            raise ConflictError("Không thể hủy hóa đơn.")
        audit_repo.add_event(
            connection, actor_id, "invoice.cancelled", "invoice", invoice_id,
            f"Hủy hóa đơn #{invoice_id}", {"customer_id": invoice["customer_id"]},
        )
    return "cancelled"
