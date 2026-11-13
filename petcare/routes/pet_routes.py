import base64
from io import BytesIO
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from petcare.auth import admin_required, login_required
from petcare.i18n import translate
from petcare.services import pet_image_service, pet_service
from petcare.services import request_throttle_service
from petcare.services.exceptions import ForbiddenError, ServiceError, ValidationError
from petcare.services.ui_text import ui_text
from petcare.vision.image_features import read_upload
from petcare.vision.media_storage import get_media_storage

bp = Blueprint("pets", __name__, url_prefix="/pets")


@bp.get("/")
@login_required
def index():
    listing = pet_service.list_pets(
        g.user["id"], request.args.get("q", ""), request.args.get("status", ""),
        page=request.args.get("page", "1"),
        tenant_id=g.actor_context.tenant_id,
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
                filters = {"species": request.form.get("species", ""), "status": request.form.get("status", "available")}
                matches = pet_image_service.search_similar(
                    g.user["id"], image_bytes, tenant_id=g.actor_context.tenant_id, **filters
                )
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
        image_species=request.form.get("species", ""),
        image_status=request.form.get("status", "available"),
        phone_capture_enabled=phone_capture_enabled,
        phone_qr_data=phone_qr_data,
        vision_enabled=bool(
            current_app.config.get("AI_VISION_ENABLED")
            and current_app.config.get("AI_API_BASE_URL")
            and current_app.config.get("AI_MODEL")
        ),
        vision_mock_enabled=bool(
            current_app.config.get("AI_TEST_ALLOW_LOOPBACK_PROVIDER")
            and current_app.config.get("AI_MODEL") == "petcare-local-demo-mock"
        ),
    ), status_code, headers


@bp.post("/suggest-attributes")
@admin_required
def suggest_attributes():
    allowed, retry_after = request_throttle_service.consume_with_ip_limit(g.user["id"], request.remote_addr, "vision")
    if not allowed:
        return jsonify(
            status="rate_limited",
            code="vision_rate_limit",
            error=ui_text("Đã phân tích nhiều ảnh. Hãy thử lại sau.", "Too many image analyses. Try again later."),
        ), 429, {"Retry-After": str(retry_after)}
    try:
        photo = request.files.get("photo")
        if not photo or not photo.filename:
            return jsonify(
                status="invalid_input",
                code="missing_file",
                error=ui_text("Vui lòng chọn ảnh hồ sơ.", "Please choose a profile photo."),
            ), 400
        content = read_upload(photo.stream, current_app.config["PET_IMAGE_MAX_BYTES"])
        return jsonify(pet_image_service.suggest_attributes(
            g.user["id"], content, tenant_id=g.actor_context.tenant_id
        ))
    except ForbiddenError:
        return jsonify(
            status="forbidden",
            code="forbidden",
            error=ui_text("Bạn không có quyền phân tích ảnh.", "You are not allowed to analyze this image."),
        ), 403
    except (ServiceError, ValueError) as exc:
        error_status = "invalid_input" if isinstance(exc, (ValidationError, ValueError)) else "processing_error"
        return jsonify(status=error_status, code="invalid_image", error=translate(str(exc))), 400
    except Exception as exc:
        current_app.logger.error(
            "Pet photo attribute suggestion failed (%s).", type(exc).__name__
        )
        return jsonify(
            status="processing_error",
            code="vision_processing_failed",
            error=ui_text("Không xử lý được ảnh. Hãy thử lại hoặc nhập thuộc tính thủ công.", "The image could not be processed. Retry or enter the attributes manually."),
        ), 500


@bp.get("/photo/<filename>")
@login_required
def photo(filename):
    if not pet_service.owns_photo(g.user["id"], filename, tenant_id=g.actor_context.tenant_id):
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
        pet = pet_service.get_pet(g.user["id"], pet_id, tenant_id=g.actor_context.tenant_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pets.index"))
    return render_template("pets/detail.html", pet=pet)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        try:
            pet_service.create_pet(
                g.user["id"], request.form, request.files.get("photo"),
                tenant_id=g.actor_context.tenant_id,
            )
            flash("Đã thêm cá thể thú cưng vào cửa hàng.", "success")
            return redirect(url_for("pets.index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template(
        "pets/form.html",
        pet=None,
        form_data=request.form if request.method == "POST" else {},
    )


@bp.route("/<int:pet_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(pet_id):
    try:
        pet = pet_service.get_pet(g.user["id"], pet_id, tenant_id=g.actor_context.tenant_id)
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pets.index"))
    if request.method == "POST":
        try:
            pet_service.update_pet(
                g.user["id"], pet_id, request.form, request.files.get("photo"),
                tenant_id=g.actor_context.tenant_id,
            )
            flash("Đã cập nhật cá thể thú cưng.", "success")
            return redirect(url_for("pets.detail", pet_id=pet_id))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template(
        "pets/form.html",
        pet=pet,
        form_data=request.form if request.method == "POST" else {},
    )


@bp.post("/<int:pet_id>/deactivate")
@admin_required
def deactivate(pet_id):
    try:
        pet_service.set_inactive(
            g.user["id"], pet_id, True, tenant_id=g.actor_context.tenant_id
        )
        flash("Đã ngừng bán cá thể thú cưng.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("pets.index"))


@bp.post("/<int:pet_id>/active")
@admin_required
def active(pet_id):
    try:
        pet_service.set_inactive(
            g.user["id"], pet_id, False, tenant_id=g.actor_context.tenant_id
        )
        flash("Đã đưa cá thể trở lại danh sách bán.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("pets.index"))
