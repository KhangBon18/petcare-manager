from flask import current_app

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, product_repo
from petcare.repositories.base import fetch_one
from petcare.services.common import (
    integer_value,
    money_value,
    page_window,
    positive_id,
    require_actor,
    text_value,
)
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError
from petcare.vision.photo_storage import remove_pet_photo, store_product_photo
from petcare.vision.media_storage import get_media_storage, media_tenant_id

MAX_STOCK_QTY = 2_147_483_647


def list_products(actor_id, search="", include_inactive=False, page=None):
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id)
        if page is not None:
            total = product_repo.count_products(connection, search, include_inactive)
            _current_page, offset, pagination = page_window(page, total)
            return {
                "items": product_repo.list_products_page(
                    connection, search, include_inactive, pagination["page_size"], offset
                ),
                "pagination": pagination,
            }
        return product_repo.list_products(
            connection, search, include_inactive
        )


def get_product(actor_id, product_id):
    product_id = positive_id(product_id, "Sản phẩm")
    with read_connection() as connection:
        require_actor(connection, actor_id)
        product = product_repo.get_product(connection, product_id)
        history = product_repo.stock_history(connection, product_id) if product else []
    if not product:
        raise NotFoundError("Không tìm thấy sản phẩm.")
    product["stock_history"] = history
    return product


def owns_photo(actor_id, filename):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        try:
            scoped_tenant_id = media_tenant_id(filename)
        except ValueError:
            return False
        return (
            (scoped_tenant_id is None or scoped_tenant_id == actor["tenant_id"])
            and product_repo.has_photo(connection, filename)
        )


def _catalog_data(data, currency_code):
    return {
        "code": text_value(data.get("code"), "Mã sản phẩm", 48).upper(),
        "name": text_value(data.get("name"), "Tên sản phẩm", 160),
        "category": text_value(data.get("category"), "Danh mục", 100),
        "description": text_value(data.get("description"), "Mô tả", 500, required=False),
        "unit_price": money_value(data.get("unit_price"), "Giá bán", currency_code),
        "legacy_unit_price_vnd": 0,
        "reorder_level": integer_value(
            data.get("reorder_level", "5"), "Ngưỡng cảnh báo tồn", 0, 2_000_000_000
        ),
    }


def _store_photo(actor_id, image_upload):
    if not image_upload or not getattr(image_upload, "filename", ""):
        return None
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    tenant_id = actor["tenant_id"]
    return store_product_photo(
        image_upload,
        get_media_storage(current_app.config, "products"),
        current_app.config["PRODUCT_IMAGE_MAX_BYTES"],
        tenant_id=tenant_id,
    )


def create_product(actor_id, data, image_upload=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    product = _catalog_data(data, actor["default_currency"])
    product["legacy_unit_price_vnd"] = (
        int(product["unit_price"]) if actor["default_currency"] == "VND" else 0
    )
    stock = integer_value(data.get("stock_qty", "0"), "Tồn đầu", 0, 2_000_000_000)
    stored = None
    try:
        stored = _store_photo(actor_id, image_upload)
        product["photo_filename"] = stored.filename if stored else None
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True)
            product_id = product_repo.create_product(
                connection,
                product["code"], product["name"], product["category"],
                product["description"], product["unit_price"],
                product["legacy_unit_price_vnd"], stock,
                product["reorder_level"], product["photo_filename"],
            )
            if stock:
                product_repo.add_stock_movement(
                    connection, product_id, stock, "Tồn đầu khi tạo sản phẩm", actor_id
                )
            audit_repo.add_event(
                connection, actor_id, "product.created", "product", product_id,
                f"Tạo sản phẩm {product['code']}",
                {"opening_stock": stock, "photo_attached": bool(stored)},
            )
            return product_id
    except Exception as exc:
        if stored:
            remove_pet_photo(stored.filename, get_media_storage(current_app.config, "products"))
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Mã sản phẩm đã tồn tại.") from exc
        raise


def update_product(actor_id, product_id, data, image_upload=None):
    product_id = positive_id(product_id, "Sản phẩm")
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    product = _catalog_data(data, actor["default_currency"])
    product["legacy_unit_price_vnd"] = (
        int(product["unit_price"]) if actor["default_currency"] == "VND" else 0
    )
    stored = None
    current = None
    try:
        stored = _store_photo(actor_id, image_upload)
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True)
            current = product_repo.get_product(connection, product_id, lock=True)
            if not current:
                raise NotFoundError("Không tìm thấy sản phẩm.")
            product["photo_filename"] = (
                stored.filename if stored else current["photo_filename"]
            )
            changed_fields = [
                field for field in (
                    "code", "name", "category", "description",
                    "unit_price", "reorder_level",
                ) if current[field] != product[field]
            ]
            if stored:
                changed_fields.append("photo")
            changed = product_repo.update_product(
                connection,
                product_id, product["code"], product["name"], product["category"],
                product["description"], product["unit_price"],
                product["legacy_unit_price_vnd"],
                product["reorder_level"], product["photo_filename"],
            )
            if changed:
                audit_repo.add_event(
                    connection, actor_id, "product.updated", "product", product_id,
                    f"Cập nhật sản phẩm #{product_id}",
                    {"changed_fields": changed_fields},
                )
    except Exception as exc:
        if stored:
            remove_pet_photo(stored.filename, get_media_storage(current_app.config, "products"))
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Mã sản phẩm đã được sử dụng.") from exc
        raise
    if stored and current and current["photo_filename"]:
        try:
            with read_connection() as connection:
                references = product_repo.count_photo_references(
                    connection, current["photo_filename"]
                )
            if references == 0:
                remove_pet_photo(
                    current["photo_filename"], get_media_storage(current_app.config, "products")
                )
        except Exception:
            current_app.logger.exception("Could not clean up an unreferenced product image")


def set_active(actor_id, product_id, active):
    product_id = positive_id(product_id, "Sản phẩm")
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True)
        product = product_repo.get_product(connection, product_id, lock=True)
        if not product:
            raise NotFoundError("Không tìm thấy sản phẩm.")
        if bool(product["active"]) == bool(active):
            return
        changed = product_repo.set_active(connection, product_id, int(bool(active)))
        if not changed:
            raise NotFoundError("Không tìm thấy sản phẩm.")
        audit_repo.add_event(
            connection, actor_id, "product.status_changed", "product", product_id,
            f"{'Kích hoạt' if active else 'Ngừng bán'} sản phẩm #{product_id}",
            {"active": bool(active)},
        )


def adjust_stock(actor_id, product_id, data):
    product_id = positive_id(product_id, "Sản phẩm")
    delta = integer_value(data.get("quantity_delta"), "Số lượng điều chỉnh", -2_000_000_000, 2_000_000_000)
    if delta == 0:
        raise ValidationError("Số lượng điều chỉnh không được bằng 0.")
    reason = text_value(data.get("reason"), "Lý do", 255)
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True)
        product = product_repo.get_product(connection, product_id, lock=True)
        if not product:
            raise NotFoundError("Không tìm thấy sản phẩm.")
        updated_stock = product["stock_qty"] + delta
        if updated_stock < 0:
            raise ValidationError("Điều chỉnh này làm tồn kho âm.")
        if updated_stock > MAX_STOCK_QTY:
            raise ValidationError(
                f"Tồn kho không thể vượt {MAX_STOCK_QTY:,} đơn vị."
            )
        changed = product_repo.adjust_stock(connection, product_id, delta)
        if not changed:
            raise ConflictError("Tồn kho vừa thay đổi; hãy tải lại rồi thử lại.")
        product_repo.add_stock_movement(
            connection, product_id, delta, reason, actor_id
        )
        audit_repo.add_event(
            connection, actor_id, "stock.adjusted", "product", product_id,
            f"Điều chỉnh tồn {product['code']}: {delta:+d} đơn vị",
            {"quantity_delta": delta, "stock_before": product["stock_qty"],
             "stock_after": product["stock_qty"] + delta},
        )
