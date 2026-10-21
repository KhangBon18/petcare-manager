import base64
from io import BytesIO
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for

from petcare.auth import admin_required, login_required
from petcare.services import pet_image_service, pet_service
from petcare.services import request_throttle_service
from petcare.services.exceptions import ServiceError
from petcare.vision.image_features import read_upload
from petcare.vision.media_storage import get_media_storage

bp = Blueprint("pets", __name__, url_prefix="/pets")


@bp.get("/")
@login_required
def index():
    listing = pet_service.list_pets(
        g.user["id"], request.args.get("q", ""), request.args.get("status", ""),
        page=request.args.get("page", "1"),
    )
    return render_template(
        "pets/index.html",
        pets=listing["items"],
        pagination=listing["pagination"],
        search=request.args.get("q", ""),
        status=request.args.get("status", ""),
    )


@bp.route("/find-similar", methods=["GET", "POST"])
@login_required
def find_similar():
    matches = None
    status_code = 200
    headers = {}
    if request.method == "POST":
        allowed, retry_after = request_throttle_service.consume_with_ip_limit(
            g.user["id"], request.remote_addr, "vision"
        )
        if not allowed:
            flash("Bạn đã quét nhiều ảnh trong thời gian ngắn. Vui lòng thử lại sau.", "error")
            status_code = 429
            headers["Retry-After"] = str(retry_after)
        if allowed:
            try:
                photo = request.files.get("photo")
                if not photo or not photo.filename:
                    raise ValueError("Hãy chọn ảnh mèo hoặc thú cưng để tìm kiếm.")
                image_bytes = read_upload(photo.stream, current_app.config["PET_IMAGE_MAX_BYTES"])
                matches = pet_image_service.search_similar(g.user["id"], image_bytes)
            except (ServiceError, ValueError) as exc:
                flash(str(exc), "error")
    phone_qr_data = None
    base_url = current_app.config.get("LAN_ACCESS_BASE_URL", "").strip().rstrip("/")
    parsed_url = urlparse(base_url)
    phone_capture_enabled = bool(
        current_app.config.get("LAN_ACCESS_ENABLED")
        and parsed_url.scheme in {"http", "https"}
        and parsed_url.netloc
        and not parsed_url.username
        and not parsed_url.password
    )
    if phone_capture_enabled:
        try:
            import qrcode

            phone_url = f"{base_url}{url_for('pets.find_similar')}"
            qr = qrcode.QRCode(box_size=5, border=2)
            qr.add_data(phone_url)
            qr.make(fit=True)
            image = qr.make_image(fill_color="#24323a", back_color="white")
            output = BytesIO()
            image.save(output, format="PNG")
            phone_qr_data = base64.b64encode(output.getvalue()).decode("ascii")
        except ImportError:
            current_app.logger.error("Install the qrcode package to enable phone QR links.")
            phone_capture_enabled = False

    return render_template(
        "pets/search_image.html",
        matches=matches,
        phone_capture_enabled=phone_capture_enabled,
        phone_qr_data=phone_qr_data,
        vision_enabled=bool(
            current_app.config.get("AI_VISION_ENABLED")
            and current_app.config.get("AI_API_BASE_URL")
            and current_app.config.get("AI_MODEL")
        ),
    ), status_code, headers


@bp.get("/photo/<filename>")
@login_required
def photo(filename):
    if not pet_service.owns_photo(g.user["id"], filename):
        abort(404)
    try:
        image = get_media_storage(current_app.config, "pets").read(filename)
    except FileNotFoundError:
        abort(404)
    response = send_file(BytesIO(image), mimetype="image/jpeg", conditional=False, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.get("/<int:pet_id>")
@login_required
def detail(pet_id):
    try:
        pet = pet_service.get_pet(g.user["id"], pet_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pets.index"))
    return render_template("pets/detail.html", pet=pet)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        try:
            pet_service.create_pet(g.user["id"], request.form, request.files.get("photo"))
            flash("Đã thêm cá thể thú cưng vào cửa hàng.", "success")
            return redirect(url_for("pets.index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("pets/form.html", pet=None)


@bp.route("/<int:pet_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(pet_id):
    try:
        pet = pet_service.get_pet(g.user["id"], pet_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pets.index"))
    if request.method == "POST":
        try:
            pet_service.update_pet(
                g.user["id"], pet_id, request.form, request.files.get("photo")
            )
            flash("Đã cập nhật cá thể thú cưng.", "success")
            return redirect(url_for("pets.detail", pet_id=pet_id))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("pets/form.html", pet=pet)


@bp.post("/<int:pet_id>/deactivate")
@admin_required
def deactivate(pet_id):
    try:
        pet_service.set_inactive(g.user["id"], pet_id, True)
        flash("Đã ngừng bán cá thể thú cưng.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("pets.index"))


@bp.post("/<int:pet_id>/active")
@admin_required
def active(pet_id):
    try:
        pet_service.set_inactive(g.user["id"], pet_id, False)
        flash("Đã đưa cá thể trở lại danh sách bán.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("pets.index"))
