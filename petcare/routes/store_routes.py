"""Store-level configuration for tenant administrators."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from petcare.auth import admin_required
from petcare.services import tenant_settings_service
from petcare.services.exceptions import ServiceError
from petcare.timezones import COMMON_TIMEZONES


bp = Blueprint("store", __name__, url_prefix="/store")


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        try:
            result = tenant_settings_service.update_store_profile(
                g.user["id"],
                request.form.get("name", ""),
                request.form.get("timezone", ""),
            )
            if result["status"] == "unchanged":
                flash("Cài đặt cửa hàng chưa thay đổi.", "info")
            else:
                flash("Cài đặt cửa hàng đã được cập nhật.", "success")
        except ServiceError as exc:
            flash(str(exc), "error")
        return redirect(url_for("store.settings"))

    return render_template(
        "store/settings.html",
        tenant=g.tenant,
        common_timezones=COMMON_TIMEZONES,
    )
