"""Customer Storefront MVP 1.0 public shopping, checkout, AI & account blueprint."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from petcare.auth import _safe_next_url
from petcare.i18n import SUPPORTED_LOCALES
from petcare.services import (
    request_throttle_service,
    storefront_ai_service,
    storefront_auth_service,
    storefront_service,
    storefront_vision_service,
)
from petcare.services.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from petcare.vision.media_storage import get_media_storage
from petcare.vision.photo_storage import read_upload


bp = Blueprint("storefront", __name__, url_prefix="/shop")


def _active_store() -> dict:
    store = getattr(g, "public_store", None)
    if store is None:
        store = storefront_service.resolve_public_store()
        g.public_store = store
    return store


def _active_customer() -> dict | None:
    if getattr(g, "customer_loaded", False):
        return g.customer
    store = _active_store()
    account_id = session.get("customer_account_id")
    tenant_id = session.get("customer_tenant_id")
    ver = session.get("customer_session_version")
    customer = None
    if account_id and tenant_id == store["id"]:
        customer = storefront_auth_service.load_active_customer(int(account_id), int(tenant_id), ver)
        if customer is None:
            session.pop("customer_account_id", None)
            session.pop("customer_tenant_id", None)
            session.pop("customer_session_version", None)
    g.customer = customer
    g.customer_loaded = True
    return customer


@bp.before_request
def bind_storefront_context():
    store = _active_store()
    if session.get("locale") in SUPPORTED_LOCALES:
        g.locale = session["locale"]
    _active_customer()
    cart = storefront_service.sanitize_cart(session.get("storefront_cart"))
    g.storefront_cart_count = sum(int(item["quantity"]) for item in cart)
    g.storefront_order_status_labels = (
        storefront_service.ORDER_STATUS_LABELS_EN
        if g.locale == "en"
        else storefront_service.ORDER_STATUS_LABELS_VI
    )
    g.public_store = store


def _safe_shop_next(target: str | None, fallback_endpoint: str = "storefront.home") -> str:
    if isinstance(target, str) and _safe_next_url(target) and target.startswith("/shop"):
        return target
    return url_for(fallback_endpoint)


def _remember_guest_order(tenant_id: int, order_code: str) -> None:
    tokens = dict(session.get("guest_orders") or {})
    if len(tokens) >= 12:
        oldest_key = next(iter(tokens))
        tokens.pop(oldest_key, None)
    tokens[order_code] = storefront_service.sign_guest_order_token(tenant_id, order_code)
    session["guest_orders"] = tokens


@bp.post("/language")
def set_language():
    locale = request.form.get("locale", "")
    if locale not in SUPPORTED_LOCALES:
        abort(400)
    session["locale"] = locale
    g.locale = locale
    return redirect(_safe_shop_next(request.form.get("next"), "storefront.home"))


@bp.get("")
@bp.get("/")
def home():
    store = _active_store()
    data = storefront_service.get_storefront_home_data(store["id"])
    return render_template("storefront/home.html", store=store, **data)


@bp.get("/products")
def products():
    store = _active_store()
    search = request.args.get("q", "")
    category = request.args.get("category", "")
    in_stock_only = request.args.get("in_stock") == "1"
    sort = request.args.get("sort", "featured")
    page = request.args.get("page", "1")
    listing = storefront_service.list_public_products(
        store["id"],
        search=search,
        category=category,
        in_stock_only=in_stock_only,
        sort=sort,
        page=page,
    )
    return render_template(
        "storefront/products.html",
        store=store,
        products=listing["items"],
        categories=listing["categories"],
        pagination=listing["pagination"],
        search=search,
        selected_category=category,
        in_stock_only=in_stock_only,
        sort=sort,
    )


@bp.get("/products/<int:product_id>")
def product_detail(product_id: int):
    store = _active_store()
    try:
        product = storefront_service.get_public_product(store["id"], product_id)
    except ServiceError:
        abort(404)
    return render_template("storefront/product_detail.html", store=store, product=product)


@bp.get("/pets")
def pets():
    store = _active_store()
    search = request.args.get("q", "")
    species = request.args.get("species", "")
    sort = request.args.get("sort", "featured")
    page = request.args.get("page", "1")
    listing = storefront_service.list_public_pets(
        store["id"],
        search=search,
        species=species,
        sort=sort,
        page=page,
    )
    return render_template(
        "storefront/pets.html",
        store=store,
        pets=listing["items"],
        pagination=listing["pagination"],
        search=search,
        selected_species=species,
        sort=sort,
    )


@bp.get("/pets/<int:pet_id>")
def pet_detail(pet_id: int):
    store = _active_store()
    try:
        pet = storefront_service.get_public_pet(store["id"], pet_id)
    except ServiceError:
        abort(404)
    return render_template("storefront/pet_detail.html", store=store, pet=pet)


@bp.get("/media/products/<filename>")
def public_product_photo(filename: str):
    store = _active_store()
    if not storefront_service.public_owns_product_photo(store["id"], filename):
        abort(404)
    try:
        image = get_media_storage(current_app.config, "products").read(filename)
    except FileNotFoundError:
        abort(404)
    response = send_file(BytesIO(image), mimetype="image/jpeg", conditional=False, max_age=300)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@bp.get("/media/pets/<filename>")
def public_pet_photo(filename: str):
    store = _active_store()
    if not storefront_service.public_owns_pet_photo(store["id"], filename):
        abort(404)
    try:
        image = get_media_storage(current_app.config, "pets").read(filename)
    except FileNotFoundError:
        abort(404)
    response = send_file(BytesIO(image), mimetype="image/jpeg", conditional=False, max_age=300)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


# ---------- Cart ----------
@bp.get("/cart")
def cart():
    store = _active_store()
    snapshot = storefront_service.price_cart_snapshot(store["id"], session.get("storefront_cart"))
    return render_template("storefront/cart.html", store=store, cart=snapshot)


@bp.post("/cart/add")
def cart_add():
    store = _active_store()
    item_type = (request.form.get("item_type") or "").strip()
    item_id = request.form.get("item_id")
    quantity = request.form.get("quantity", "1")
    next_url = _safe_shop_next(request.form.get("next"), "storefront.cart")
    try:
        updated = storefront_service.add_item_to_cart(
            store["id"], session.get("storefront_cart"), item_type, item_id, quantity
        )
        session["storefront_cart"] = updated
        flash(
            "Đã thêm vào giỏ hàng." if g.locale != "en" else "Added to cart.",
            "success",
        )
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(next_url)


@bp.post("/cart/update")
def cart_update():
    store = _active_store()
    item_type = (request.form.get("item_type") or "").strip()
    item_id = request.form.get("item_id")
    quantity = request.form.get("quantity", "1")
    try:
        updated = storefront_service.update_cart_item(
            store["id"], session.get("storefront_cart"), item_type, item_id, quantity
        )
        session["storefront_cart"] = updated
        flash(
            "Đã cập nhật giỏ hàng." if g.locale != "en" else "Cart updated.",
            "success",
        )
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("storefront.cart"))


@bp.post("/cart/remove")
def cart_remove():
    item_type = (request.form.get("item_type") or "").strip()
    try:
        target_id = int(request.form.get("item_id", "0"))
    except (TypeError, ValueError):
        target_id = 0
    cart_items = storefront_service.sanitize_cart(session.get("storefront_cart"))
    session["storefront_cart"] = [
        c for c in cart_items if not (c["item_type"] == item_type and c["item_id"] == target_id)
    ]
    flash("Đã xóa mặt hàng khỏi giỏ." if g.locale != "en" else "Item removed.", "success")
    return redirect(url_for("storefront.cart"))


@bp.post("/cart/clear")
def cart_clear():
    session["storefront_cart"] = []
    flash("Đã làm trống giỏ hàng." if g.locale != "en" else "Cart cleared.", "info")
    return redirect(url_for("storefront.cart"))


# ---------- Checkout & Orders ----------
@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    store = _active_store()
    customer = _active_customer()
    snapshot = storefront_service.price_cart_snapshot(store["id"], session.get("storefront_cart"))
    if not snapshot["items"]:
        flash("Giỏ hàng của bạn đang trống." if g.locale != "en" else "Your cart is empty.", "warning")
        return redirect(url_for("storefront.cart"))

    form_data = {
        "customer_name": customer["full_name"] if customer else "",
        "customer_phone": customer["phone"] if customer else "",
        "customer_email": customer["email"] if customer else "",
        "delivery_address": customer["default_address"] if customer else "",
        "fulfillment_method": "pickup",
        "customer_note": "",
        "request_key": session.get("checkout_request_key") or str(uuid4()),
    }
    field_errors: dict[str, str] = {}
    session["checkout_request_key"] = form_data["request_key"]

    if request.method == "POST":
        allowed, retry_after = request_throttle_service.consume(
            request.remote_addr or "unknown", "public_checkout_ip"
        )
        if not allowed:
            flash("Bạn gửi quá nhiều yêu cầu đặt hàng. Vui lòng thử lại sau ít phút.", "error")
            return (
                render_template(
                    "storefront/checkout.html",
                    store=store,
                    cart=snapshot,
                    form_data=request.form,
                    field_errors=field_errors,
                ),
                429,
                {"Retry-After": str(retry_after)},
            )
        try:
            result = storefront_service.place_order(
                store["id"],
                store["default_currency"],
                store["timezone"],
                session.get("storefront_cart"),
                request.form,
                customer_account_id=customer["id"] if customer else None,
            )
            order = result["order"]
            session["storefront_cart"] = []
            session["checkout_request_key"] = str(uuid4())
            if customer is None:
                _remember_guest_order(store["id"], order["order_code"])
            flash(
                f"Đã tiếp nhận đơn hàng {order['order_code']}. Cửa hàng sẽ liên hệ xác nhận sớm."
                if g.locale != "en"
                else f"Order {order['order_code']} received and pending confirmation.",
                "success",
            )
            return redirect(url_for("storefront.order_detail", order_code=order["order_code"]))
        except (ValidationError, ConflictError) as exc:
            flash(str(exc), "error")
            field_errors = dict(getattr(exc, "field_errors", {}) or {})
            form_data = dict(request.form)
            snapshot = storefront_service.price_cart_snapshot(store["id"], session.get("storefront_cart"))

    return render_template(
        "storefront/checkout.html", store=store, cart=snapshot, form_data=form_data, field_errors=field_errors
    )


@bp.get("/orders")
def orders():
    store = _active_store()
    customer = _active_customer()
    if not customer:
        flash("Đăng nhập tài khoản khách hàng hoặc tra cứu bằng mã đơn + số điện thoại.", "info")
        return redirect(url_for("storefront.order_lookup"))
    order_list = storefront_service.list_customer_orders(store["id"], customer["id"])
    return render_template("storefront/orders.html", store=store, customer=customer, orders=order_list)


@bp.route("/orders/lookup", methods=["GET", "POST"])
def order_lookup():
    store = _active_store()
    if request.method == "POST":
        allowed, retry_after = request_throttle_service.consume(
            request.remote_addr or "unknown", "public_order_lookup_ip"
        )
        if not allowed:
            flash("Quá nhiều lượt tra cứu. Vui lòng thử lại sau.", "error")
            return render_template("storefront/order_lookup.html", store=store), 429, {"Retry-After": str(retry_after)}
        try:
            order = storefront_service.lookup_guest_order(
                store["id"],
                request.form.get("order_code", ""),
                request.form.get("phone", ""),
            )
            _remember_guest_order(store["id"], order["order_code"])
            return redirect(url_for("storefront.order_detail", order_code=order["order_code"]))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("storefront/order_lookup.html", store=store)


@bp.get("/orders/<order_code>")
def order_detail(order_code: str):
    store = _active_store()
    customer = _active_customer()
    try:
        order = storefront_service.get_customer_order(
            store["id"],
            order_code,
            customer_account_id=customer["id"] if customer else None,
            guest_tokens=session.get("guest_orders"),
        )
    except NotFoundError:
        abort(404)
    except ForbiddenError:
        flash("Vui lòng đăng nhập đúng tài khoản hoặc tra cứu bằng mã đơn và số điện thoại.", "warning")
        return redirect(url_for("storefront.order_lookup"))
    return render_template("storefront/order_detail.html", store=store, order=order)


@bp.post("/orders/<order_code>/cancel")
def cancel_order(order_code: str):
    store = _active_store()
    customer = _active_customer()
    try:
        order = storefront_service.cancel_customer_pending_order(
            store["id"],
            order_code,
            customer_account_id=customer["id"] if customer else None,
            guest_tokens=session.get("guest_orders"),
        )
        flash(
            f"Đã hủy đơn hàng {order['order_code']}." if g.locale != "en" else f"Cancelled order {order['order_code']}.",
            "success",
        )
        return redirect(url_for("storefront.order_detail", order_code=order["order_code"]))
    except ForbiddenError:
        abort(403)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("storefront.order_detail", order_code=order_code))


# ---------- Customer Accounts ----------
@bp.route("/register", methods=["GET", "POST"])
def register():
    store = _active_store()
    if _active_customer():
        return redirect(url_for("storefront.account"))
    if request.method == "POST":
        try:
            account = storefront_auth_service.register_customer(store["id"], request.form)
            session["customer_account_id"] = account["id"]
            session["customer_tenant_id"] = store["id"]
            session["customer_session_version"] = account["session_version"]
            flash(
                f"Chào mừng {account['full_name']}! Tài khoản mua sắm đã sẵn sàng."
                if g.locale != "en"
                else f"Welcome {account['full_name']}! Your account is ready.",
                "success",
            )
            return redirect(_safe_shop_next(request.form.get("next"), "storefront.home"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("storefront/register.html", store=store, form_data=request.form)


@bp.route("/login", methods=["GET", "POST"])
def customer_login():
    store = _active_store()
    if _active_customer():
        return redirect(url_for("storefront.account"))
    if request.method == "POST":
        email = request.form.get("email", "")
        remote_addr = request.remote_addr or "unknown"
        if storefront_auth_service.customer_login_blocked(store["id"], email, remote_addr):
            flash("Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau 15 phút.", "error")
            return render_template("storefront/login.html", store=store), 429, {"Retry-After": "900"}
        account = storefront_auth_service.authenticate_customer(
            store["id"], email, request.form.get("password", "")
        )
        if not account:
            storefront_auth_service.record_customer_login_failure(store["id"], email, remote_addr)
            flash("Email hoặc mật khẩu chưa đúng.", "error")
            return render_template("storefront/login.html", store=store), 401
        storefront_auth_service.clear_customer_login_failures(store["id"], email, remote_addr)
        session["customer_account_id"] = account["id"]
        session["customer_tenant_id"] = store["id"]
        session["customer_session_version"] = account["session_version"]
        flash(
            f"Xin chào {account['full_name']}!" if g.locale != "en" else f"Welcome back, {account['full_name']}!",
            "success",
        )
        return redirect(_safe_shop_next(request.args.get("next") or request.form.get("next"), "storefront.home"))
    return render_template("storefront/login.html", store=store)


@bp.post("/logout")
def customer_logout():
    session.pop("customer_account_id", None)
    session.pop("customer_tenant_id", None)
    session.pop("customer_session_version", None)
    session.pop("guest_orders", None)
    session.pop("checkout_request_key", None)
    flash("Bạn đã đăng xuất tài khoản khách hàng." if g.locale != "en" else "Signed out.", "success")
    return redirect(url_for("storefront.home"))


@bp.route("/account", methods=["GET", "POST"])
def account():
    store = _active_store()
    customer = _active_customer()
    if not customer:
        return redirect(url_for("storefront.customer_login", next=url_for("storefront.account")))
    if request.method == "POST":
        try:
            customer = storefront_auth_service.update_customer_profile(
                store["id"], customer["id"], request.form
            )
            g.customer = customer
            flash("Đã cập nhật thông tin tài khoản." if g.locale != "en" else "Profile updated.", "success")
        except ServiceError as exc:
            flash(str(exc), "error")
    recent_orders = storefront_service.list_customer_orders(store["id"], customer["id"])
    return render_template(
        "storefront/account.html",
        store=store,
        customer=customer,
        recent_orders=recent_orders,
    )


# ---------- Public AI Shopping Assistant ----------
@bp.get("/ai-assistant")
def ai_assistant():
    store = _active_store()
    prompts = storefront_ai_service.public_assistant_prompts(g.locale)
    initial_q = str(request.args.get("q") or "").strip()[:300]
    return render_template(
        "storefront/ai_assistant.html",
        store=store,
        prompts=prompts,
        initial_prompt=initial_q,
    )


@bp.post("/ai-assistant/chat")
def ai_assistant_chat():
    store = _active_store()
    allowed, retry_after = request_throttle_service.consume(
        request.remote_addr or "unknown", "public_ai_ip"
    )
    if not allowed:
        return jsonify(
            error="Trợ lý đang nhận nhiều câu hỏi. Vui lòng thử lại sau." if g.locale != "en" else "Rate limit exceeded. Try again shortly."
        ), 429, {"Retry-After": str(retry_after)}
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error="Dữ liệu chưa hợp lệ."), 400
    question = payload.get("question", "")
    history = payload.get("history")
    try:
        reply = storefront_ai_service.answer_public_question(
            store,
            question,
            history=history if isinstance(history, list) else None,
            locale=g.locale,
        )
        return jsonify(reply)
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Public storefront AI assistant failed.")
        return jsonify(
            error="Trợ lý đang bận; bạn có thể tìm trực tiếp trên danh mục sản phẩm và thú cưng."
        ), 500


# ---------- Public AI Image Search ----------
@bp.route("/image-search", methods=["GET", "POST"])
def image_search():
    store = _active_store()
    matches = None
    status_code = 200
    headers = {}
    selected_species = request.form.get("species", "")
    if request.method == "POST":
        allowed, retry_after = request_throttle_service.consume(
            request.remote_addr or "unknown", "public_vision_ip"
        )
        if not allowed:
            flash("Bạn đã quét nhiều ảnh trong thời gian ngắn. Vui lòng thử lại sau.", "error")
            status_code = 429
            headers["Retry-After"] = str(retry_after)
        else:
            try:
                photo = request.files.get("photo")
                if not photo or not photo.filename:
                    raise ValueError("Hãy chọn ảnh chó hoặc mèo để tìm cá thể tương tự.")
                image_bytes = read_upload(photo.stream, current_app.config["PET_IMAGE_MAX_BYTES"])
                matches = storefront_vision_service.search_public_pets_by_image(
                    store["id"], image_bytes, species=selected_species
                )
            except (ServiceError, ValueError) as exc:
                flash(str(exc), "error")
    return render_template(
        "storefront/image_search.html",
        store=store,
        matches=matches,
        selected_species=selected_species,
    ), status_code, headers

