"""Store-level configuration for tenant administrators."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from petcare.auth import admin_required
from petcare.services import tenant_settings_service
from petcare.services.exceptions import ServiceError
from petcare.timezones import COMMON_TIMEZONES


bp = Blueprint("store", __name__, url_prefix="/store")


def _render_settings_page(policy_form_data=None, policy_errors=None, policy_form_error=None):
    policies = tenant_settings_service.get_public_store_policies(g.tenant_id)
    return render_template(
        "store/settings.html",
        tenant=g.tenant,
        common_timezones=COMMON_TIMEZONES,
        public_policies=policies,
        policy_form_data=policy_form_data if policy_form_data is not None else policies,
        policy_errors=policy_errors or {},
        policy_form_error=policy_form_error,
    )


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        try:
            result = tenant_settings_service.update_store_profile(
                g.user["id"],
                request.form.get("name", ""),
                request.form.get("timezone", ""),
                tenant_id=g.tenant_id,
            )
            if result["status"] == "unchanged":
                flash("Cài đặt cửa hàng chưa thay đổi.", "info")
            else:
                flash("Cài đặt cửa hàng đã được cập nhật.", "success")
        except ServiceError as exc:
            flash(str(exc), "error")
        return redirect(url_for("store.settings"))

    return _render_settings_page()


@bp.post("/settings/public-policies")
@admin_required
def update_public_policies():
    try:
        result = tenant_settings_service.update_public_policies(
            g.user["id"],
            request.form,
            tenant_id=g.tenant_id,
        )
        if result["status"] == "unchanged":
            flash("Thông tin công khai Storefront chưa có thay đổi.", "info")
        else:
            flash("Đã lưu thông tin & chính sách công khai cho Storefront.", "success")
        return redirect(url_for("store.settings"))
    except ServiceError as exc:
        return _render_settings_page(
            policy_form_data=request.form,
            policy_errors=getattr(exc, "field_errors", {}),
            policy_form_error=str(exc),
        )
