"""Supplier and purchase-order web workflows."""

from uuid import uuid4

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from petcare.auth import admin_required
from petcare.i18n import translate
from petcare.services import purchase_service
from petcare.services.exceptions import ServiceError


bp = Blueprint("purchasing", __name__, url_prefix="/purchasing")


def _posted_lines():
    product_ids = request.form.getlist("product_id[]")
    labels = request.form.getlist("product_label[]")
    quantities = request.form.getlist("quantity[]")
    costs = request.form.getlist("unit_cost[]")
    lengths = {len(product_ids), len(labels), len(quantities), len(costs)}
    if len(lengths) != 1:
        return None
    return [
        {
            "product_id": product_id,
            "label": label,
            "quantity": quantity,
            "unit_cost": cost,
        }
        for product_id, label, quantity, cost in zip(product_ids, labels, quantities, costs)
    ]


def _supplier_form(supplier=None):
    return render_template("purchasing/supplier_form.html", supplier=supplier)


@bp.get("/", strict_slashes=False)
@admin_required
def index():
    status = request.args.get("status") or None
    try:
        listing = purchase_service.list_purchase_orders(
            g.user["id"], status, request.args.get("page", "1"),
            tenant_id=g.tenant_id,
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("purchasing.index"))
    return render_template(
        "purchasing/index.html",
        orders=listing["items"],
        pagination=listing["pagination"],
        status=status,
    )


@bp.get("/products")
@admin_required
def products():
    try:
        items = purchase_service.search_active_products(
            g.user["id"], request.args.get("q", ""), tenant_id=g.tenant_id
        )
    except ServiceError as exc:
        return jsonify(error=translate(str(exc))), 400
    return jsonify(items=items)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    try:
        suppliers = purchase_service.list_active_suppliers(
            g.user["id"], tenant_id=g.tenant_id
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("purchasing.index"))
    lines = _posted_lines() if request.method == "POST" else []
    if request.method == "POST":
        try:
            order_id = purchase_service.create_purchase_order(
                g.user["id"], request.form, lines, tenant_id=g.tenant_id
            )
            flash("Đã tạo đơn nhập. Tồn kho sẽ tăng khi xác nhận nhận hàng.", "success")
            return redirect(url_for("purchasing.detail", purchase_order_id=order_id))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template(
        "purchasing/order_form.html",
        suppliers=suppliers,
        lines=lines or [],
        currency_code=g.tenant["default_currency"],
    )


@bp.get("/<int:purchase_order_id>")
@admin_required
def detail(purchase_order_id):
    try:
        order = purchase_service.get_purchase_order_detail(
            g.user["id"], purchase_order_id, tenant_id=g.tenant_id
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("purchasing.index"))
    return render_template(
        "purchasing/detail.html", order=order, receipt_request_key=str(uuid4())
    )


@bp.post("/<int:purchase_order_id>/receive")
@admin_required
def receive(purchase_order_id):
    lines = _posted_lines_for_receipt()
    try:
        request_key = request.form.get("receipt_request_key", "")
        if not request_key:
            raise ServiceError("Biểu mẫu đã cũ. Hãy tải lại trang trước khi nhận hàng.")
        status = purchase_service.receive_purchase_order(
            g.user["id"], purchase_order_id, lines,
            tenant_id=g.tenant_id, request_key=request_key,
        )
        flash(
            "Đã ghi nhận số hàng nhận. Đơn nhập đã hoàn tất." if status == "received"
            else "Đã ghi nhận số hàng nhận; bạn có thể nhận tiếp phần còn lại.",
            "success",
        )
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("purchasing.detail", purchase_order_id=purchase_order_id))


def _posted_lines_for_receipt():
    item_ids = request.form.getlist("item_id[]")
    quantities = request.form.getlist("quantity[]")
    if len(item_ids) != len(quantities):
        return None
    return [
        {"item_id": item_id, "quantity": quantity}
        for item_id, quantity in zip(item_ids, quantities)
    ]


@bp.post("/<int:purchase_order_id>/cancel")
@admin_required
def cancel(purchase_order_id):
    try:
        purchase_service.cancel_purchase_order(
            g.user["id"], purchase_order_id, tenant_id=g.tenant_id
        )
        flash("Đã đóng đơn nhập; các lần nhận trước đó vẫn được giữ trong lịch sử.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("purchasing.detail", purchase_order_id=purchase_order_id))


@bp.get("/suppliers")
@admin_required
def suppliers_index():
    listing = purchase_service.list_suppliers(
        g.user["id"], request.args.get("q", ""), request.args.get("all") == "1",
        request.args.get("page", "1"), tenant_id=g.tenant_id,
    )
    return render_template(
        "purchasing/suppliers.html",
        suppliers=listing["items"], pagination=listing["pagination"],
        search=request.args.get("q", ""), include_inactive=request.args.get("all") == "1",
    )


@bp.route("/suppliers/new", methods=["GET", "POST"])
@admin_required
def supplier_create():
    if request.method == "POST":
        try:
            purchase_service.create_supplier(
                g.user["id"], request.form, tenant_id=g.tenant_id
            )
            flash("Đã thêm nhà cung cấp.", "success")
            return redirect(url_for("purchasing.suppliers_index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return _supplier_form()


@bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def supplier_edit(supplier_id):
    try:
        supplier = purchase_service.get_supplier(
            g.user["id"], supplier_id, tenant_id=g.tenant_id
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("purchasing.suppliers_index"))
    if request.method == "POST":
        try:
            purchase_service.update_supplier(
                g.user["id"], supplier_id, request.form, tenant_id=g.tenant_id
            )
            flash("Đã cập nhật nhà cung cấp.", "success")
            return redirect(url_for("purchasing.suppliers_index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return _supplier_form(supplier)


@bp.post("/suppliers/<int:supplier_id>/activate")
@admin_required
def supplier_activate(supplier_id):
    try:
        purchase_service.set_supplier_active(
            g.user["id"], supplier_id, True, tenant_id=g.tenant_id
        )
        flash("Đã kích hoạt nhà cung cấp.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("purchasing.suppliers_index", all=1))


@bp.post("/suppliers/<int:supplier_id>/deactivate")
@admin_required
def supplier_deactivate(supplier_id):
    try:
        purchase_service.set_supplier_active(
            g.user["id"], supplier_id, False, tenant_id=g.tenant_id
        )
        flash("Đã ngừng sử dụng nhà cung cấp; lịch sử đơn nhập được giữ lại.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("purchasing.suppliers_index", all=1))
