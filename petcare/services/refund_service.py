"""Admin-only, transactional returns and refunds for paid invoice snapshots."""

from decimal import Decimal
from uuid import UUID

from petcare.database.connection import transaction
from petcare.repositories import audit_repo, invoice_repo, pet_repo, refund_repo
from petcare.repositories import product_repo
from petcare.services.common import integer_value, positive_id, require_actor, text_value
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError


MAX_STOCK_QTY = 2_147_483_647
REFUND_METHODS = {"cash", "bank_transfer", "card", "other"}
DISPOSITIONS = {"resell", "quarantine", "not_returned"}


def _request_key(value):
    raw = text_value(value, "Mã yêu cầu", 36)
    try:
        parsed = UUID(raw)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Mã yêu cầu hoàn tiền không hợp lệ.") from exc
    if str(parsed) != raw.lower():
        raise ValidationError("Mã yêu cầu hoàn tiền không hợp lệ.")
    return str(parsed)


def _normalize_lines(raw_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValidationError("Hãy chọn ít nhất một mặt hàng cần hoàn.")
    normalized, seen = [], set()
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise ValidationError("Danh sách mặt hàng hoàn không hợp lệ.")
        item_id = positive_id(raw.get("invoice_item_id"), "Dòng hóa đơn")
        if item_id in seen:
            raise ValidationError("Một dòng hóa đơn chỉ được chọn một lần trong mỗi lần hoàn.")
        seen.add(item_id)
        quantity = integer_value(raw.get("quantity", "0"), "Số lượng hoàn", 0, 2_000_000_000)
        if quantity == 0:
            continue
        disposition = raw.get("disposition", "")
        if disposition not in DISPOSITIONS:
            raise ValidationError("Tình trạng hàng nhận lại không hợp lệ.")
        normalized.append({
            "invoice_item_id": item_id,
            "quantity": quantity,
            "disposition": disposition,
        })
    if not normalized:
        raise ValidationError("Số lượng hoàn phải lớn hơn 0.")
    return normalized


def refund_invoice(actor_id, invoice_id, data, raw_lines, tenant_id=None):
    """Record a partial/full return without changing the paid invoice itself.

    ``resell`` returns stock or a pet to the available catalog, ``quarantine``
    records a physical return that cannot be sold again, and ``not_returned``
    records a goodwill refund where the customer keeps the item.
    """
    invoice_id = positive_id(invoice_id, "Hóa đơn")
    request_key = _request_key(data.get("request_key"))
    method = data.get("method", "")
    if method not in REFUND_METHODS:
        raise ValidationError("Phương thức hoàn tiền không hợp lệ.")
    note = text_value(data.get("note"), "Ghi chú hoàn tiền", 300, required=False)
    requested = _normalize_lines(raw_lines)

    try:
        with transaction() as connection:
            actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            invoice = invoice_repo.get_invoice(connection, invoice_id, lock=True)
            if not invoice:
                raise NotFoundError("Không tìm thấy hóa đơn.")
            previous_request = refund_repo.get_refund_by_request_key(connection, request_key)
            if previous_request:
                if previous_request["invoice_id"] != invoice_id:
                    raise ConflictError("Mã yêu cầu này đã được dùng cho hóa đơn khác.")
                return {"status": "already_recorded", "refund_id": previous_request["id"]}
            if invoice["status"] != "paid":
                raise ConflictError("Chỉ hóa đơn đã thanh toán mới được hoàn tiền.")

            items = invoice_repo.get_items_for_update(connection, invoice_id)
            by_id = {item["id"]: item for item in items}
            already_refunded = refund_repo.refunded_quantities(connection, invoice_id)
            prepared, refund_total = [], Decimal("0")
            for row in requested:
                item = by_id.get(row["invoice_item_id"])
                if not item:
                    raise ValidationError("Dòng hàng không thuộc hóa đơn này.")
                remaining = item["quantity"] - already_refunded.get(item["id"], 0)
                if row["quantity"] > remaining:
                    raise ConflictError(
                        f"Số lượng hoàn của {item['name_snapshot']} vượt số còn có thể hoàn ({remaining})."
                    )
                if item["item_type"] == "pet" and row["quantity"] != 1:
                    raise ValidationError("Mỗi thú cưng chỉ có thể hoàn một lần.")
                amount = Decimal(item["unit_price"]) * row["quantity"]
                prepared.append({**row, "item": item, "amount": amount})
                refund_total += amount

            product_ids = sorted({
                line["item"]["product_id"] for line in prepared
                if line["item"]["item_type"] == "product"
                and line["disposition"] == "resell"
            })
            products = product_repo.get_products_by_ids(connection, product_ids, lock=True)
            product_by_id = {product["id"]: product for product in products}
            add_by_product = {}
            for line in prepared:
                item = line["item"]
                if item["item_type"] == "product" and line["disposition"] == "resell":
                    add_by_product[item["product_id"]] = (
                        add_by_product.get(item["product_id"], 0) + line["quantity"]
                    )
            for product_id, quantity in add_by_product.items():
                product = product_by_id.get(product_id)
                if not product:
                    raise ConflictError("Một sản phẩm không còn tồn tại; chưa ghi nhận hoàn tiền.")
                if product["stock_qty"] + quantity > MAX_STOCK_QTY:
                    raise ConflictError(f"Tồn kho {product['name']} vượt giới hạn sau khi nhận trả.")

            pet_ids = sorted({
                line["item"]["pet_id"] for line in prepared
                if line["item"]["item_type"] == "pet"
                and line["disposition"] != "not_returned"
            })
            pets = []
            if pet_ids:
                pets = pet_repo.get_pets_by_ids(connection, pet_ids, lock=True)
            pet_by_id = {pet["id"]: pet for pet in pets}
            for pet_id in pet_ids:
                pet = pet_by_id.get(pet_id)
                if not pet or pet["sale_status"] != "sold" or pet["buyer_id"] != invoice["customer_id"]:
                    raise ConflictError("Tình trạng sở hữu thú cưng đã thay đổi; chưa ghi nhận hoàn tiền.")

            refund_id = refund_repo.create_refund(
                connection, invoice_id, actor_id, request_key, method, note,
                invoice["currency_code"], refund_total,
            )
            stored_lines = []
            for line in prepared:
                refund_item_id = refund_repo.create_refund_item(
                    connection, invoice_id, refund_id, line["item"],
                    line["quantity"], line["amount"], line["disposition"],
                )
                stored_lines.append({**line, "refund_item_id": refund_item_id})

            for product_id, quantity in sorted(add_by_product.items()):
                if product_repo.adjust_stock(connection, product_id, quantity) != 1:
                    raise ConflictError("Tồn kho vừa thay đổi; vui lòng tải lại hóa đơn.")
            for line in stored_lines:
                item = line["item"]
                if item["item_type"] == "product" and line["disposition"] == "resell":
                    product_repo.add_stock_movement(
                        connection, item["product_id"], line["quantity"],
                        f"Nhận trả theo hoàn #{refund_id}", actor_id,
                        invoice_id=invoice_id, refund_id=refund_id,
                        refund_item_id=line["refund_item_id"],
                    )
                elif item["item_type"] == "pet" and line["disposition"] != "not_returned":
                    new_status = "available" if line["disposition"] == "resell" else "inactive"
                    if pet_repo.return_sold_pet(
                        connection, item["pet_id"], invoice["customer_id"], new_status
                    ) != 1:
                        raise ConflictError("Thú cưng vừa được thay đổi; chưa ghi nhận hoàn tiền.")

            audit_repo.add_event(
                connection, actor_id, "invoice.refunded", "invoice_refund", refund_id,
                f"Hoàn {format(refund_total, 'f')} {invoice['currency_code']} cho hóa đơn #{invoice_id}",
                {
                    "invoice_id": invoice_id,
                    "line_count": len(prepared),
                    "refund_total": format(refund_total, "f"),
                    "currency_code": invoice["currency_code"],
                    "method": method,
                },
            )
            return {"status": "refunded", "refund_id": refund_id}
    except Exception as exc:
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Yêu cầu hoàn tiền này đã được ghi nhận trước đó.") from exc
        raise
