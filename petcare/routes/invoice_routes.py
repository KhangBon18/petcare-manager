from decimal import Decimal
from uuid import uuid4

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from petcare.auth import admin_required, login_required
from petcare.i18n import translate
from petcare.services import customer_service, invoice_service, pet_service, product_service, refund_service
from petcare.services.exceptions import NotFoundError, ServiceError, ValidationError

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
    errors, form_error = {}, None
    selections = request.form.getlist("item_selection")
    quantities = request.form.getlist("quantity")
    if request.method == "POST":
        if not selections or len(selections) != len(quantities):
            form_error = "Danh sách mặt hàng không hợp lệ."
            errors["item_0"] = form_error
        else:
            items = []
            try:
                for selection, quantity in zip(selections, quantities):
                    item_type, separator, item_id = selection.partition(":")
                    items.append({
                        "item_type": item_type if separator else "",
                        "item_id": item_id, "quantity": quantity
                    })
                invoice_id = invoice_service.create_invoice(
                    g.user["id"], request.form, items
                )
                flash("Đã lập hóa đơn chưa thanh toán. Tồn kho sẽ đổi sau khi thu tiền.", "success")
                return redirect(url_for("invoices.detail", invoice_id=invoice_id))
            except ServiceError as exc:
                form_error = str(exc)
                errors = getattr(exc, "field_errors", {})
    customer_listing = customer_service.list_customers(g.user["id"], page="1")
    product_listing = product_service.list_products(g.user["id"], page="1")
    pet_listing = pet_service.list_pets(g.user["id"], status="available", page="1")
    # Restore selections even when their records are outside the first lookup
    # page. These service calls enforce tenant scope and never trust posted prices.
    selected_customer = (
        request.form.get("customer_id", "")
        if request.method == "POST"
        else request.args.get("customer_id", "")
    )
    if selected_customer and not any(
        str(row["id"]) == selected_customer for row in customer_listing["items"]
    ):
        try:
            customer_listing["items"].append(
                customer_service.get_customer(g.user["id"], selected_customer)
            )
        except (NotFoundError, ValidationError):
            customer_listing["items"].append({"id": selected_customer, "full_name": "—", "phone": "—"})
    seen = set()
    for selection in selections:
        kind, _, item_id = selection.partition(":")
        if kind not in {"product", "pet"} or selection in seen:
            continue
        seen.add(selection)
        listing, get_item = (
            (product_listing, product_service.get_product) if kind == "product"
            else (pet_listing, pet_service.get_pet)
        )
        if any(str(row["id"]) == item_id for row in listing["items"]):
            continue
        try:
            listing["items"].append(get_item(g.user["id"], item_id))
        except (NotFoundError, ValidationError):
            # The original value remains visible as an unavailable option.
            continue
    form_lines = [
        {"selection": selections[index] if index < len(selections) else "",
         "quantity": quantities[index] if index < len(quantities) else ""}
        for index in range(max(len(selections), len(quantities)))
    ] or [{"selection": "", "quantity": "1"}]
    form_data = (
        request.form
        if request.method == "POST"
        else {"customer_id": selected_customer}
    )
    return render_template(
        "invoices/form.html",
        customers=customer_listing["items"],
        customer_pagination=customer_listing["pagination"],
        products=product_listing["items"],
        product_pagination=product_listing["pagination"],
        pets=pet_listing["items"],
        pet_pagination=pet_listing["pagination"],
        currency_code=g.tenant["default_currency"],
        form_data=form_data, form_lines=form_lines,
        errors=errors, form_error=form_error,
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


@bp.post("/customers/quick")
@login_required
def quick_customer():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error=translate("Nội dung gửi lên chưa hợp lệ.")), 400
    try:
        customer_id = customer_service.create_customer(g.user["id"], payload)
        customer = customer_service.get_customer(g.user["id"], customer_id)
    except ServiceError as exc:
        return jsonify(
            error=translate(str(exc)),
            errors={field: translate(message) for field, message in getattr(exc, "field_errors", {}).items()},
        ), 400
    return jsonify(customer={key: customer[key] for key in ("id", "full_name", "phone")}), 201


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
                "photo_url": url_for("products.photo", filename=row["photo_filename"]) if row.get("photo_filename") else None,
            }
            for row in products["items"]
        ],
        pets=[
            {
                "id": row["id"], "code": row["code"], "name": row["name"],
                "sale_price": format(Decimal(row["sale_price"]), "f"),
                "photo_url": url_for("pets.photo", filename=row["photo_filename"]) if row.get("photo_filename") else None,
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
    return render_template(
        "invoices/detail.html", invoice=invoice, refund_request_key=str(uuid4())
    )


@bp.post("/<int:invoice_id>/refund")
@admin_required
def refund(invoice_id):
    invoice_item_ids = request.form.getlist("invoice_item_id")
    lines = [
        {
            "invoice_item_id": item_id,
            "quantity": request.form.get(f"quantity_{item_id}", "0"),
            "disposition": request.form.get(f"disposition_{item_id}", ""),
        }
        for item_id in invoice_item_ids
    ]
    try:
        result = refund_service.refund_invoice(
            g.user["id"], invoice_id, request.form, lines
        )
        if result["status"] == "already_recorded":
            flash("Yêu cầu này đã được ghi nhận trước đó; không tạo khoản hoàn trùng.", "info")
        else:
            flash("Đã ghi nhận hoàn tiền và cập nhật tình trạng hàng trả.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


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
