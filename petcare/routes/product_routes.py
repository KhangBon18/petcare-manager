from io import BytesIO

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from petcare.auth import admin_required, login_required
from petcare.services import product_service
from petcare.services.exceptions import ServiceError
from petcare.vision.media_storage import get_media_storage

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.get("/")
@login_required
def index():
    listing = product_service.list_products(
        g.user["id"], request.args.get("q", ""),
        request.args.get("all") == "1", page=request.args.get("page", "1"),
    )
    return render_template(
        "products/index.html",
        products=listing["items"],
        pagination=listing["pagination"],
        search=request.args.get("q", ""),
        include_inactive=request.args.get("all") == "1",
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        try:
            product_service.create_product(g.user["id"], request.form, request.files.get("photo"))
            flash("Đã tạo sản phẩm.", "success")
            return redirect(url_for("products.index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("products/form.html", product=None)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(product_id):
    try:
        product = product_service.get_product(g.user["id"], product_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("products.index"))
    if request.method == "POST":
        try:
            product_service.update_product(
                g.user["id"], product_id, request.form, request.files.get("photo")
            )
            flash("Đã cập nhật thông tin sản phẩm.", "success")
            return redirect(url_for("products.index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("products/form.html", product=product)


@bp.get("/photo/<filename>")
@login_required
def photo(filename):
    if not product_service.owns_photo(g.user["id"], filename):
        abort(404)
    try:
        image = get_media_storage(current_app.config, "products").read(filename)
    except FileNotFoundError:
        abort(404)
    response = send_file(BytesIO(image), mimetype="image/jpeg", conditional=False, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.post("/<int:product_id>/stock")
@admin_required
def stock(product_id):
    try:
        product_service.adjust_stock(g.user["id"], product_id, request.form)
        flash("Đã ghi nhận điều chỉnh tồn kho.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("products.edit", product_id=product_id))


@bp.post("/<int:product_id>/active")
@admin_required
def active(product_id):
    try:
        product_service.set_active(g.user["id"], product_id, True)
        flash("Đã kích hoạt sản phẩm.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("products.index", all=1))


@bp.post("/<int:product_id>/deactivate")
@admin_required
def deactivate(product_id):
    try:
        product_service.set_active(g.user["id"], product_id, False)
        flash("Đã ngừng bán sản phẩm; lịch sử giao dịch được giữ lại.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("products.index", all=1))
