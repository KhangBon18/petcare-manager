"""Business rules for the selected store's editable profile."""

from petcare.database.connection import transaction
from petcare.repositories import audit_repo, tenant_repo
from petcare.services.common import require_actor, text_value
from petcare.services.exceptions import ForbiddenError, ValidationError
from petcare.timezones import TimezoneError, normalize_timezone_name


def update_store_profile(actor_id, name, timezone_name):
    name = text_value(name, "Tên cửa hàng", 160)
    try:
        timezone_name = normalize_timezone_name(timezone_name)
    except TimezoneError as exc:
        raise ValidationError(str(exc)) from exc

    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        tenant = tenant_repo.get_for_update(connection, actor["tenant_id"])
        if not tenant or tenant["status"] != "active":
            raise ForbiddenError("Cửa hàng không còn hoạt động.")

        changed_fields = []
        if tenant["name"] != name:
            changed_fields.append("name")
        if tenant["timezone"] != timezone_name:
            changed_fields.append("timezone")
        if not changed_fields:
            return {"status": "unchanged"}

        tenant_repo.update_profile(
            connection, tenant["id"], name, timezone_name
        )
        audit_repo.add_event(
            connection,
            actor_id,
            "tenant.settings_updated",
            "tenant",
            tenant["id"],
            "Cập nhật cài đặt cửa hàng",
            {"changed_fields": changed_fields},
        )
    return {"status": "updated"}
