from decimal import Decimal

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from petcare.auth import login_required
from petcare.services import customer_service, invoice_service, pet_service, product_service
from petcare.services.exceptions import ServiceError

bp = Blueprint("invoices", __name__, url_prefix="/invoices")


@bp.get("/")
@login_required
def index():
    listing = invoice_service.list_invoices(
        g.user["id"], request.args.get("q", ""), request.args.get("status", ""),
        page=request.args.get("page", "1"),
    )
    return render_template(
        "invoices/index.html",
        invoices=listing["items"],
        pagination=listing["pagination"],
        search=request.args.get("q", ""),
        status=request.args.get("status", ""),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        selections = request.form.getlist("item_selection")
        quantities = request.form.getlist("quantity")
        if not selections or len(selections) != len(quantities):
            flash("Danh sách mặt hàng không hợp lệ.", "error")
        else:
            items = []
            try:
                for selection, quantity in zip(selections, quantities):
                    item_type, separator, item_id = selection.partition(":")
                    if not separator:
                        raise ValueError("Hãy chọn mặt hàng cho từng dòng.")
                    items.append({
                        "item_type": item_type, "item_id": item_id, "quantity": quantity
                    })
                invoice_id = invoice_service.create_invoice(
                    g.user["id"], request.form, items
                )
                flash("Đã lập hóa đơn chưa thanh toán. Tồn kho sẽ đổi sau khi thu tiền.", "success")
                return redirect(url_for("invoices.detail", invoice_id=invoice_id))
            except ValueError as exc:
                flash(str(exc), "error")
            except ServiceError as exc:
                flash(str(exc), "error")
    customer_listing = customer_service.list_customers(g.user["id"], page="1")
    product_listing = product_service.list_products(g.user["id"], page="1")
    pet_listing = pet_service.list_pets(g.user["id"], status="available", page="1")
    return render_template(
        "invoices/form.html",
        customers=customer_listing["items"],
        customer_pagination=customer_listing["pagination"],
        products=product_listing["items"],
        product_pagination=product_listing["pagination"],
        pets=pet_listing["items"],
        pet_pagination=pet_listing["pagination"],
        currency_code=g.tenant["default_currency"],
    )


@bp.get("/lookups/customers")
@login_required
def lookup_customers():
    listing = customer_service.list_customers(
        g.user["id"], request.args.get("q", ""), page=request.args.get("page", "1")
    )
    return jsonify(
        items=[
            {"id": row["id"], "full_name": row["full_name"], "phone": row["phone"]}
            for row in listing["items"]
        ],
        pagination=listing["pagination"],
    )


@bp.get("/lookups/items")
@login_required
def lookup_items():
    search = request.args.get("q", "")
    products = product_service.list_products(
        g.user["id"], search, page=request.args.get("product_page", "1")
    )
    pets = pet_service.list_pets(
        g.user["id"], search, "available", page=request.args.get("pet_page", "1")
    )
    return jsonify(
        products=[
            {
                "id": row["id"], "code": row["code"], "name": row["name"],
                "unit_price": format(Decimal(row["unit_price"]), "f"),
                "stock_qty": row["stock_qty"],
            }
            for row in products["items"]
        ],
        pets=[
            {
                "id": row["id"], "code": row["code"], "name": row["name"],
                "sale_price": format(Decimal(row["sale_price"]), "f"),
            }
            for row in pets["items"]
        ],
        product_pagination=products["pagination"],
        pet_pagination=pets["pagination"],
    )


@bp.get("/<int:invoice_id>")
@login_required
def detail(invoice_id):
    try:
        invoice = invoice_service.get_invoice(g.user["id"], invoice_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("invoices.index"))
    return render_template("invoices/detail.html", invoice=invoice)


@bp.post("/<int:invoice_id>/pay")
@login_required
def pay(invoice_id):
    try:
        result = invoice_service.pay_invoice(g.user["id"], invoice_id)
        if result == "already_paid":
            flash("Hóa đơn đã được thanh toán trước đó; không ghi nhận lần hai.", "info")
        else:
            flash("Thanh toán thành công. Tồn kho và trạng thái thú cưng đã được cập nhật.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


@bp.post("/<int:invoice_id>/cancel")
@login_required
def cancel(invoice_id):
    try:
        result = invoice_service.cancel_invoice(g.user["id"], invoice_id)
        flash(
            "Hóa đơn đã được hủy." if result == "cancelled" else "Hóa đơn này đã hủy.",
            "success",
        )
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))
