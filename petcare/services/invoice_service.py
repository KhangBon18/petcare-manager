from collections import defaultdict
from decimal import Decimal

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, customer_repo, invoice_repo
from petcare.repositories.base import fetch_all, fetch_one
from petcare.repositories.product_repo import add_stock_movement
from petcare.services.common import (
    integer_value,
    page_window,
    positive_id,
    require_actor,
    text_value,
)
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError


def list_invoices(actor_id, search="", status="", page=None):
    if status not in ("", "unpaid", "paid", "cancelled"):
        status = ""
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id)
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


def get_invoice(actor_id, invoice_id):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with read_connection() as connection:
        require_actor(connection, actor_id)
        invoice = invoice_repo.get_invoice(connection, invoice_id)
        items = invoice_repo.list_items(connection, invoice_id) if invoice else []
    if not invoice:
        raise NotFoundError("Không tìm thấy hóa đơn.")
    invoice["items"] = items
    invoice["total_amount"] = sum((item["line_total"] for item in items), Decimal("0"))
    return invoice


def _normalize_items(raw_items):
    if not raw_items:
        raise ValidationError("Hóa đơn cần ít nhất một mặt hàng.")
    products = defaultdict(int)
    pets = set()
    for raw in raw_items:
        item_type = (raw.get("item_type") or "").strip()
        item_id = positive_id(raw.get("item_id"), "Mặt hàng")
        if item_type == "product":
            quantity = integer_value(raw.get("quantity"), "Số lượng", 1, 2_000_000_000)
            products[item_id] += quantity
        elif item_type == "pet":
            quantity = integer_value(raw.get("quantity", "1"), "Số lượng", 1, 1)
            if item_id in pets:
                raise ValidationError("Một thú cưng chỉ được thêm một lần vào hóa đơn.")
            pets.add(item_id)
        else:
            raise ValidationError("Loại mặt hàng không hợp lệ.")
    return products, sorted(pets)


def create_invoice(actor_id, data, raw_items):
    customer_id = positive_id(data.get("customer_id"), "Khách hàng")
    note = text_value(data.get("note"), "Ghi chú", 500, required=False)
    product_quantities, pet_ids = _normalize_items(raw_items)
    with transaction() as connection:
        actor = require_actor(connection, actor_id)
        customer = customer_repo.get_customer(connection, customer_id)
        if not customer or not customer["active"]:
            raise ValidationError("Khách hàng không tồn tại hoặc đã ngừng sử dụng.")
        lines = []
        total = Decimal("0")
        for product_id, quantity in sorted(product_quantities.items()):
            product = fetch_one(
                connection,
                "SELECT id, code, name, unit_price, stock_qty, active "
                "FROM products WHERE id = %s AND tenant_id = @petcare_tenant_id",
                (product_id,),
            )
            if not product or not product["active"]:
                raise ValidationError("Sản phẩm không còn được bán.")
            if product["stock_qty"] < quantity:
                raise ValidationError(
                    f"Tồn hiện tại của {product['name']} không đủ; hóa đơn chưa giữ hàng."
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
            pet = fetch_one(
                connection,
                "SELECT id, code, name, sale_price, sale_status FROM pets "
                "WHERE id = %s AND tenant_id = @petcare_tenant_id",
                (pet_id,),
            )
            if not pet or pet["sale_status"] != "available":
                raise ValidationError("Thú cưng đã chọn không còn sẵn sàng để bán.")
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


def pay_invoice(actor_id, invoice_id):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with transaction() as connection:
        require_actor(connection, actor_id)
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
            placeholders = ",".join(["%s"] * len(quantities))
            products = fetch_all(
                connection,
                "SELECT id, name, stock_qty, active FROM products "
                f"WHERE tenant_id = @petcare_tenant_id AND id IN ({placeholders}) ORDER BY id FOR UPDATE",
                tuple(sorted(quantities)),
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
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE products SET stock_qty = stock_qty - %s "
                        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
                        "AND active = 1 AND stock_qty >= %s",
                        (quantity, product_id, quantity),
                    )
                    if cursor.rowcount != 1:
                        raise ConflictError("Tồn kho vừa thay đổi; vui lòng tải lại hóa đơn.")
                finally:
                    cursor.close()
                add_stock_movement(
                    connection,
                    product_id,
                    -quantity,
                    f"Bán theo hóa đơn #{invoice_id}",
                    actor_id,
                    invoice_id,
                )
        if pet_ids:
            placeholders = ",".join(["%s"] * len(pet_ids))
            pets = fetch_all(
                connection,
                "SELECT id, sale_status FROM pets WHERE tenant_id = @petcare_tenant_id AND id IN "
                f"({placeholders}) ORDER BY id FOR UPDATE",
                tuple(sorted(pet_ids)),
            )
            by_id = {pet["id"]: pet for pet in pets}
            if any(by_id.get(pet_id, {}).get("sale_status") != "available" for pet_id in pet_ids):
                raise ConflictError("Một cá thể thú cưng đã được bán.")
            for pet_id in sorted(pet_ids):
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE pets SET sale_status = 'sold', buyer_id = %s, sold_at = NOW() "
                        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
                        "AND sale_status = 'available'",
                        (invoice["customer_id"], pet_id),
                    )
                    if cursor.rowcount != 1:
                        raise ConflictError("Thú cưng vừa được bán ở giao dịch khác.")
                finally:
                    cursor.close()
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


def cancel_invoice(actor_id, invoice_id):
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    with transaction() as connection:
        require_actor(connection, actor_id)
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
