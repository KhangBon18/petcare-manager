from decimal import Decimal, InvalidOperation

from flask import current_app

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, pet_repo
from petcare.services.common import date_value, money_value, page_window, positive_id, require_actor, text_value
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError
from petcare.timezones import tenant_today
from petcare.vision.photo_storage import remove_pet_photo, store_pet_photo
from petcare.vision.media_storage import get_media_storage, media_tenant_id


def list_pets(actor_id, search="", status="", page=None):
    if status not in ("", "available", "sold", "inactive"):
        status = ""
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id)
        if page is not None:
            total = pet_repo.count_pets(connection, search, status)
            _current_page, offset, pagination = page_window(page, total)
            return {
                "items": pet_repo.list_pets_page(
                    connection, search, status, pagination["page_size"], offset
                ),
                "pagination": pagination,
            }
        return pet_repo.list_pets(connection, search, status)


def get_pet(actor_id, pet_id):
    pet_id = positive_id(pet_id, "Thú cưng")
    with read_connection() as connection:
        require_actor(connection, actor_id)
        pet = pet_repo.get_pet(connection, pet_id)
    if not pet:
        raise NotFoundError("Không tìm thấy thú cưng.")
    return pet


def owns_photo(actor_id, filename):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        try:
            scoped_tenant_id = media_tenant_id(filename)
        except ValueError:
            return False
        return (
            (scoped_tenant_id is None or scoped_tenant_id == actor["tenant_id"])
            and pet_repo.has_photo(connection, filename)
        )


def _pet_data(data, currency_code, timezone_name):
    birth_date = date_value(data.get("birth_date"), "Ngày sinh")
    if birth_date and birth_date > tenant_today(timezone_name):
        raise ValidationError("Ngày sinh không được ở tương lai.")
    raw_weight = (data.get("weight_kg") or "").strip()
    try:
        weight = Decimal(raw_weight) if raw_weight else None
    except InvalidOperation:
        raise ValidationError("Cân nặng không hợp lệ.")
    if weight is not None and (weight <= 0 or weight > Decimal("9999.99")):
        raise ValidationError("Cân nặng phải lớn hơn 0 và không vượt quá 9999.99 kg.")
    sex = data.get("sex", "unknown")
    if sex not in ("male", "female", "unknown"):
        raise ValidationError("Giới tính không hợp lệ.")
    return {
        "code": text_value(data.get("code"), "Mã thú cưng", 48).upper(),
        "name": text_value(data.get("name"), "Tên thú cưng", 120),
        "species": text_value(data.get("species"), "Loài", 80),
        "breed": text_value(data.get("breed"), "Giống", 100, required=False),
        "sex": sex,
        "birth_date": birth_date,
        "weight_kg": weight,
        "coat_color": text_value(data.get("coat_color"), "Màu lông", 80, required=False),
        "eye_color": text_value(data.get("eye_color"), "Màu mắt", 60, required=False),
        "appearance_tags": text_value(
            data.get("appearance_tags"), "Đặc điểm ngoại hình", 255, required=False
        ),
        "sale_price": money_value(data.get("sale_price"), "Giá bán", currency_code),
        "legacy_sale_price_vnd": 0,
    }


def _store_upload(actor_id, image_upload):
    if not image_upload or not getattr(image_upload, "filename", ""):
        return None
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    tenant_id = actor["tenant_id"]
    return store_pet_photo(
        image_upload,
        get_media_storage(current_app.config, "pets"),
        current_app.config["PET_IMAGE_MAX_BYTES"],
        tenant_id=tenant_id,
    )


def create_pet(actor_id, data, image_upload=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    pet = _pet_data(data, actor["default_currency"], actor["timezone"])
    pet["legacy_sale_price_vnd"] = (
        int(pet["sale_price"]) if actor["default_currency"] == "VND" else 0
    )
    stored = None
    try:
        stored = _store_upload(actor_id, image_upload)
        if stored:
            pet["photo_filename"] = stored.filename
            pet["photo_descriptor"] = stored.descriptor_json
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True)
            pet_id = pet_repo.create_pet(connection, pet)
            audit_repo.add_event(
                connection, actor_id, "pet.created", "pet", pet_id,
                f"Tạo hồ sơ thú cưng {pet['code']}",
                {"photo_attached": bool(stored)},
            )
            return pet_id
    except Exception as exc:
        if stored:
            remove_pet_photo(stored.filename, get_media_storage(current_app.config, "pets"))
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Mã thú cưng đã tồn tại.") from exc
        raise


def update_pet(actor_id, pet_id, data, image_upload=None):
    pet_id = positive_id(pet_id, "Thú cưng")
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
    pet = _pet_data(data, actor["default_currency"], actor["timezone"])
    pet["legacy_sale_price_vnd"] = (
        int(pet["sale_price"]) if actor["default_currency"] == "VND" else 0
    )
    stored = None
    current = None
    try:
        stored = _store_upload(actor_id, image_upload)
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True)
            current = pet_repo.get_pet(connection, pet_id, lock=True)
            if not current:
                raise NotFoundError("Không tìm thấy thú cưng.")
            if current["sale_status"] == "sold":
                raise ValidationError("Không thể sửa thú cưng đã bán.")
            pet["photo_filename"] = stored.filename if stored else current["photo_filename"]
            pet["photo_descriptor"] = (
                stored.descriptor_json if stored else current["photo_descriptor"]
            )
            changed = pet_repo.update_pet(connection, pet_id, pet)
            if not changed:
                raise ValidationError("Không thể cập nhật thú cưng này.")
            changed_fields = [
                field for field in (
                    "code", "name", "species", "breed", "sex", "birth_date",
                    "weight_kg", "coat_color", "eye_color", "appearance_tags",
                    "sale_price",
                ) if current[field] != pet[field]
            ]
            if stored:
                changed_fields.append("photo")
            audit_repo.add_event(
                connection, actor_id, "pet.updated", "pet", pet_id,
                f"Cập nhật hồ sơ thú cưng #{pet_id}",
                {"changed_fields": changed_fields},
            )
    except Exception as exc:
        if stored:
            remove_pet_photo(stored.filename, get_media_storage(current_app.config, "pets"))
        if getattr(exc, "errno", None) == 1062:
            raise ConflictError("Mã thú cưng đã được sử dụng.") from exc
        raise
    if stored and current and current["photo_filename"]:
        try:
            with read_connection() as connection:
                references = pet_repo.count_photo_references(
                    connection, current["photo_filename"]
                )
            if references == 0:
                remove_pet_photo(
                    current["photo_filename"], get_media_storage(current_app.config, "pets")
                )
        except Exception:
            current_app.logger.exception("Could not clean up an unreferenced pet image")


def set_inactive(actor_id, pet_id, inactive):
    pet_id = positive_id(pet_id, "Thú cưng")
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True)
        pet = pet_repo.get_pet(connection, pet_id)
        if not pet:
            raise NotFoundError("Không tìm thấy thú cưng.")
        if pet["sale_status"] == "sold":
            raise ValidationError("Thú cưng đã bán không thể thay đổi trạng thái.")
        target_status = "inactive" if inactive else "available"
        if pet["sale_status"] == target_status:
            return
        if not pet_repo.set_inactive(connection, pet_id, inactive):
            raise ValidationError("Không thể cập nhật trạng thái thú cưng.")
        audit_repo.add_event(
            connection, actor_id, "pet.status_changed", "pet", pet_id,
            f"{'Ngừng bán' if inactive else 'Đưa thú cưng trở lại bán'} #{pet_id}",
            {"sale_status": target_status},
        )
