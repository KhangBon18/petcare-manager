from decimal import Decimal, InvalidOperation

from flask import current_app

from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, pet_repo
from petcare.services.common import date_value, money_value, page_window, positive_id, require_actor, text_value
from petcare.services.exceptions import ConflictError, NotFoundError, ValidationError
from petcare.services.ui_text import ui_text
from petcare.timezones import tenant_today
from petcare.vision.image_features import descriptor_from_json
from petcare.vision.local_pet_detector import (
    SUBJECT_MULTIPLE_ANIMALS,
    SUBJECT_NO_RELIABLE_ANIMAL,
    SUBJECT_OTHER_ANIMAL,
    analyze_pet_image,
)
from petcare.vision.photo_storage import remove_pet_photo, store_pet_photo
from petcare.vision.media_storage import get_media_storage, media_tenant_id
from petcare.vision.species_taxonomy import canonicalize_species


def list_pets(actor_id, search="", status="", page=None, tenant_id=None):
    if status not in ("", "available", "sold", "inactive"):
        status = ""
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
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


def get_pet(actor_id, pet_id, tenant_id=None):
    pet_id = positive_id(pet_id, "Thú cưng")
    with read_connection() as connection:
        require_actor(connection, actor_id, tenant_id=tenant_id)
        pet = pet_repo.get_pet(connection, pet_id)
        if pet:
            refs = pet_repo.list_reference_photos(connection, pet_id)
            pet["reference_photos"] = refs
            pet["gallery_photo_count"] = (1 if pet.get("photo_filename") else 0) + len(refs)
            pet["max_gallery_photos"] = pet_repo.MAX_PET_GALLERY_PHOTOS
    if not pet:
        raise NotFoundError("Không tìm thấy thú cưng.")
    return pet


def owns_photo(actor_id, filename, tenant_id=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, tenant_id=tenant_id)
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


def _store_upload(actor_id, image_upload, tenant_id=None):
    if not image_upload or not getattr(image_upload, "filename", ""):
        return None
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
    tenant_id = actor["tenant_id"]
    return store_pet_photo(
        image_upload,
        get_media_storage(current_app.config, "pets"),
        current_app.config["PET_IMAGE_MAX_BYTES"],
        tenant_id=tenant_id,
    )


def create_pet(actor_id, data, image_upload=None, tenant_id=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
    pet = _pet_data(data, actor["default_currency"], actor["timezone"])
    pet["legacy_sale_price_vnd"] = (
        int(pet["sale_price"]) if actor["default_currency"] == "VND" else 0
    )
    stored = None
    try:
        stored = _store_upload(actor_id, image_upload, tenant_id=tenant_id)
        if stored:
            pet["photo_filename"] = stored.filename
            pet["photo_descriptor"] = stored.descriptor_json
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
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


def update_pet(actor_id, pet_id, data, image_upload=None, tenant_id=None):
    pet_id = positive_id(pet_id, "Thú cưng")
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
    pet = _pet_data(data, actor["default_currency"], actor["timezone"])
    pet["legacy_sale_price_vnd"] = (
        int(pet["sale_price"]) if actor["default_currency"] == "VND" else 0
    )
    stored = None
    current = None
    try:
        stored = _store_upload(actor_id, image_upload, tenant_id=tenant_id)
        with transaction() as connection:
            require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            current = pet_repo.get_pet(connection, pet_id, lock=True)
            if not current:
                raise NotFoundError("Không tìm thấy thú cưng.")
            if current["sale_status"] == "sold":
                raise ValidationError("Không thể sửa thú cưng đã bán.")
            existing_refs = pet_repo.list_reference_photos(connection, pet_id)
            if existing_refs and canonicalize_species(pet["species"]) != canonicalize_species(current["species"]):
                raise ValidationError(
                    ui_text(
                        "Không thể đổi loài khi cá thể đang có ảnh tham chiếu phụ đã xác minh theo loài cũ. Hãy xóa các ảnh tham chiếu phụ trước khi sửa loài.",
                        "Cannot change species while verified reference photos exist for the current species. Remove the additional reference photos first.",
                    )
                )
            if stored and existing_refs:
                upload_hashes = {
                    h for h in (stored.descriptor.raw_sha256, stored.descriptor.normalized_sha256) if len(h) == 64
                }
                ref_hashes: set[str] = set()
                for ref in existing_refs:
                    ref_hashes.update(_descriptor_hashes(ref.get("photo_descriptor")))
                if upload_hashes and (upload_hashes & ref_hashes):
                    raise ValidationError(
                        ui_text(
                            "Ảnh này đã có sẵn trong bộ sưu tập của thú cưng.",
                            "This photograph is already stored in this pet's gallery.",
                        )
                    )
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


def set_inactive(actor_id, pet_id, inactive, tenant_id=None):
    pet_id = positive_id(pet_id, "Thú cưng")
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
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


def _descriptor_hashes(raw_descriptor_json):
    desc = descriptor_from_json(raw_descriptor_json)
    if desc is None:
        return set()
    return {h for h in (desc.raw_sha256, desc.normalized_sha256) if len(h) == 64}


def _validate_reference_photo_species_consistency(pet_species, stored_photo, storage):
    """Ensure a verified reference photo does not contradict the pet's species or subject safety."""
    if not current_app.config.get("AI_LOCAL_SPECIES_GATE_ENABLED", True):
        return
    norm_bytes = storage.read(stored_photo.filename)
    gate = analyze_pet_image(norm_bytes, flat_pixel_ratio=stored_photo.descriptor.flat_pixel_ratio)
    if gate.subject_status == SUBJECT_MULTIPLE_ANIMALS:
        raise ValidationError(
            ui_text(
                "Ảnh tham chiếu chứa nhiều động vật; vui lòng chọn ảnh chụp riêng đúng cá thể này.",
                "The reference photo shows multiple animals; please upload a single-pet photo of this individual.",
            )
        )
    if gate.subject_status == SUBJECT_NO_RELIABLE_ANIMAL:
        raise ValidationError(
            ui_text(
                "Không phát hiện thú cưng đáng tin cậy trong ảnh tham chiếu tải lên.",
                "No reliable pet subject was detected in the uploaded reference photo.",
            )
        )
    pet_canon = canonicalize_species(pet_species)
    if pet_canon in ("cat", "dog"):
        if gate.subject_status == SUBJECT_OTHER_ANIMAL:
            raise ValidationError(
                ui_text(
                    "Ảnh tải lên thuộc loài động vật khác với hồ sơ thú cưng này.",
                    "The uploaded photo depicts an animal outside this pet's species.",
                )
            )
        if gate.verified_species is not None and gate.verified_species != pet_canon:
            raise ValidationError(
                ui_text(
                    "Ảnh tải lên mâu thuẫn với loài đã ghi nhận của hồ sơ thú cưng này.",
                    "The uploaded photo contradicts this pet record's species.",
                )
            )


def add_reference_photo(
    actor_id,
    pet_id,
    image_upload,
    *,
    image_role="additional",
    verified_same_pet=False,
    tenant_id=None,
):
    """Add a verified reference photo to a pet's gallery (up to MAX_PET_GALLERY_PHOTOS total)."""
    pet_id = positive_id(pet_id, "Thú cưng")
    if not verified_same_pet:
        raise ValidationError(
            ui_text(
                "Vui lòng xác nhận ảnh tham chiếu chụp đúng cá thể thú cưng trong hồ sơ.",
                "Please confirm that the reference photograph depicts this exact pet.",
            )
        )
    image_role = (image_role or "additional").strip().lower()
    if image_role not in pet_repo.VALID_IMAGE_ROLES:
        raise ValidationError(
            ui_text("Vai trò ảnh tham chiếu không hợp lệ.", "The reference photo role is invalid.")
        )
    if not image_upload or not getattr(image_upload, "filename", ""):
        raise ValidationError(
            ui_text("Vui lòng chọn một ảnh tham chiếu hợp lệ.", "Please choose a valid reference photo.")
        )

    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        existing_pet = pet_repo.get_pet(connection, pet_id)
        if not existing_pet:
            raise NotFoundError("Không tìm thấy thú cưng.")
        if existing_pet["sale_status"] == "sold":
            raise ValidationError("Không thể sửa ảnh của thú cưng đã bán.")
        current_count = (1 if existing_pet.get("photo_filename") else 0) + pet_repo.count_reference_photos(
            connection, pet_id
        )
        if current_count >= pet_repo.MAX_PET_GALLERY_PHOTOS:
            raise ValidationError(
                ui_text(
                    f"Mỗi thú cưng chỉ lưu tối đa {pet_repo.MAX_PET_GALLERY_PHOTOS} ảnh tham chiếu đã xác minh.",
                    f"Each pet can store at most {pet_repo.MAX_PET_GALLERY_PHOTOS} verified reference photos.",
                )
            )

    storage = get_media_storage(current_app.config, "pets")
    stored = None
    try:
        stored = _store_upload(actor_id, image_upload, tenant_id=tenant_id)
        if not stored:
            raise ValidationError(
                ui_text("Vui lòng chọn một ảnh tham chiếu hợp lệ.", "Please choose a valid reference photo.")
            )
        _validate_reference_photo_species_consistency(existing_pet["species"], stored, storage)
        new_hashes = {
            h for h in (stored.descriptor.raw_sha256, stored.descriptor.normalized_sha256) if len(h) == 64
        }

        with transaction() as connection:
            require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
            locked = pet_repo.get_pet(connection, pet_id, lock=True)
            if not locked:
                raise NotFoundError("Không tìm thấy thú cưng.")
            if locked["sale_status"] == "sold":
                raise ValidationError("Không thể sửa ảnh của thú cưng đã bán.")
            refs = pet_repo.list_reference_photos(connection, pet_id)
            total_now = (1 if locked.get("photo_filename") else 0) + len(refs)
            if total_now >= pet_repo.MAX_PET_GALLERY_PHOTOS:
                raise ValidationError(
                    ui_text(
                        f"Mỗi thú cưng chỉ lưu tối đa {pet_repo.MAX_PET_GALLERY_PHOTOS} ảnh tham chiếu đã xác minh.",
                        f"Each pet can store at most {pet_repo.MAX_PET_GALLERY_PHOTOS} verified reference photos.",
                    )
                )

            existing_hashes = set(_descriptor_hashes(locked.get("photo_descriptor")))
            for ref in refs:
                existing_hashes.update(_descriptor_hashes(ref.get("photo_descriptor")))
            if new_hashes and (new_hashes & existing_hashes):
                raise ValidationError(
                    ui_text(
                        "Ảnh này đã có sẵn trong bộ sưu tập của thú cưng.",
                        "This photograph is already stored in this pet's gallery.",
                    )
                )

            if not locked.get("photo_filename"):
                # Promote directly to primary representative photo when pet had 0 photos
                changed_primary = pet_repo.set_primary_photo(
                    connection, pet_id, stored.filename, stored.descriptor_json
                )
                if not changed_primary:
                    raise ValidationError("Không thể cập nhật thú cưng này.")
                ref_id = 0
            else:
                ref_id = pet_repo.add_reference_photo(
                    connection,
                    pet_id,
                    stored.filename,
                    stored.descriptor_json,
                    image_role,
                    len(refs) + 1,
                )
            audit_repo.add_event(
                connection,
                actor_id,
                "pet.photo_added",
                "pet",
                pet_id,
                f"Thêm ảnh tham chiếu cho thú cưng #{pet_id}",
                {"image_role": image_role, "gallery_total": total_now + 1},
            )
            return ref_id
    except Exception:
        if stored:
            remove_pet_photo(stored.filename, storage)
        raise


def remove_reference_photo(actor_id, pet_id, photo_id, tenant_id=None):
    """Remove an additional reference photo and clean up its media file if unreferenced."""
    pet_id = positive_id(pet_id, "Thú cưng")
    photo_id = positive_id(photo_id, "Ảnh tham chiếu")
    removed_filename = None
    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        locked = pet_repo.get_pet(connection, pet_id, lock=True)
        if not locked:
            raise NotFoundError("Không tìm thấy thú cưng.")
        if locked["sale_status"] == "sold":
            raise ValidationError("Không thể sửa ảnh của thú cưng đã bán.")
        ref_row = pet_repo.get_reference_photo(connection, pet_id, photo_id, lock=True)
        if not ref_row:
            raise NotFoundError("Không tìm thấy ảnh tham chiếu.")
        removed_filename = ref_row["photo_filename"]
        if not pet_repo.delete_reference_photo(connection, pet_id, photo_id):
            raise NotFoundError("Không tìm thấy ảnh tham chiếu.")
        audit_repo.add_event(
            connection,
            actor_id,
            "pet.photo_removed",
            "pet",
            pet_id,
            f"Xóa ảnh tham chiếu #{photo_id} của thú cưng #{pet_id}",
            {"photo_id": photo_id},
        )

    if removed_filename:
        try:
            with read_connection() as connection:
                references = pet_repo.count_photo_references(connection, removed_filename)
            if references == 0:
                remove_pet_photo(
                    removed_filename, get_media_storage(current_app.config, "pets")
                )
        except Exception:
            current_app.logger.exception("Could not clean up removed pet reference image")


def reorder_reference_photo(actor_id, pet_id, photo_id, direction, tenant_id=None):
    """Reorder an additional reference photo ('up', 'down', or 'make_primary')."""
    pet_id = positive_id(pet_id, "Thú cưng")
    photo_id = positive_id(photo_id, "Ảnh tham chiếu")
    direction = (direction or "").strip().lower()
    if direction not in ("up", "down", "make_primary"):
        raise ValidationError(
            ui_text("Thao tác sắp xếp ảnh không hợp lệ.", "The gallery reorder action is invalid.")
        )

    with transaction() as connection:
        require_actor(connection, actor_id, admin=True, tenant_id=tenant_id)
        locked = pet_repo.get_pet(connection, pet_id, lock=True)
        if not locked:
            raise NotFoundError("Không tìm thấy thú cưng.")
        if locked["sale_status"] == "sold":
            raise ValidationError("Không thể sửa ảnh của thú cưng đã bán.")
        refs = pet_repo.list_reference_photos(connection, pet_id)
        ids = [int(r["id"]) for r in refs]
        if photo_id not in ids:
            raise NotFoundError("Không tìm thấy ảnh tham chiếu.")

        if direction == "make_primary":
            pet_repo.swap_primary_with_reference_photo(
                connection,
                pet_id,
                photo_id,
                locked.get("photo_filename"),
                locked.get("photo_descriptor"),
            )
        else:
            idx = ids.index(photo_id)
            swap_idx = idx - 1 if direction == "up" else idx + 1
            if 0 <= swap_idx < len(ids):
                ids[idx], ids[swap_idx] = ids[swap_idx], ids[idx]
                pet_repo.resequence_reference_photos(connection, pet_id, ids)

        audit_repo.add_event(
            connection,
            actor_id,
            "pet.photo_reordered",
            "pet",
            pet_id,
            f"Sắp xếp lại kho ảnh thú cưng #{pet_id}",
            {"photo_id": photo_id, "direction": direction},
        )
