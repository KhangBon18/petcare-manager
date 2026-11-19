from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from petcare.auth import login_required
from petcare.services import customer_service
from petcare.services.exceptions import ServiceError

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.get("/")
@login_required
def index():
    listing = customer_service.list_customers(
        g.user["id"], request.args.get("q", ""),
        request.args.get("all") == "1", page=request.args.get("page", "1"),
        tenant_id=g.actor_context.tenant_id,
    )
    return render_template(
        "customers/index.html",
        customers=listing["items"],
        pagination=listing["pagination"],
        search=request.args.get("q", ""),
        include_inactive=request.args.get("all") == "1",
    )


@bp.get("/<int:customer_id>")
@login_required
def detail(customer_id):
    try:
        profile = customer_service.get_customer_profile(
            g.user["id"], customer_id,
            page=request.args.get("page", "1"),
            pet_page=request.args.get("pet_page", "1"),
            tenant_id=g.actor_context.tenant_id,
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("customers.index"))
    return render_template("customers/detail.html", **profile)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    errors = {}
    form_error = None
    if request.method == "POST":
        try:
            customer_service.create_customer(
                g.user["id"], request.form, tenant_id=g.actor_context.tenant_id
            )
            flash("Đã thêm khách hàng.", "success")
            return redirect(url_for("customers.index"))
        except ServiceError as exc:
            errors = getattr(exc, "field_errors", {})
            form_error = str(exc)
    return render_template(
        "customers/form.html", customer=None,
        form_data=request.form if request.method == "POST" else {},
        errors=errors, form_error=form_error,
    )


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit(customer_id):
    errors = {}
    form_error = None
    try:
        customer = customer_service.get_customer(
            g.user["id"], customer_id, tenant_id=g.actor_context.tenant_id
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("customers.index"))
    if request.method == "POST":
        try:
            customer_service.update_customer(
                g.user["id"], customer_id, request.form,
                tenant_id=g.actor_context.tenant_id,
            )
            flash("Đã cập nhật khách hàng.", "success")
            return redirect(url_for("customers.index"))
        except ServiceError as exc:
            errors = getattr(exc, "field_errors", {})
            form_error = str(exc)
    return render_template(
        "customers/form.html", customer=customer,
        form_data=request.form if request.method == "POST" else customer,
        errors=errors, form_error=form_error,
    )


@bp.post("/<int:customer_id>/active")
@login_required
def active(customer_id):
    try:
        customer_service.set_active(
            g.user["id"], customer_id, True, tenant_id=g.actor_context.tenant_id
        )
        flash("Đã kích hoạt khách hàng.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("customers.index", all=1))


@bp.post("/<int:customer_id>/deactivate")
@login_required
def deactivate(customer_id):
    try:
        customer_service.set_active(
            g.user["id"], customer_id, False, tenant_id=g.actor_context.tenant_id
        )
        flash("Đã ngừng sử dụng khách hàng; lịch sử hóa đơn được giữ lại.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("customers.index", all=1))
