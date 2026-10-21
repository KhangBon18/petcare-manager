from flask import Blueprint, Response, abort, current_app, flash, g, jsonify, make_response, redirect, render_template, request, session, stream_with_context, url_for

from petcare.auth import admin_required
from petcare.services import auth_service
from petcare.services.exceptions import NotFoundError, ServiceError
from petcare.services.exceptions import RateLimitError
from petcare.services import tenant_export_service
from petcare.services.tenant_export_storage import get_export_storage
from petcare.services import tenant_invite_service
from petcare.services import tenant_owner_transfer_service
from petcare.services import mail_service

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.get("/")
@admin_required
def index():
    return render_template(
        "users/index.html",
        users=auth_service.list_users(g.user["id"]),
        invitations=tenant_invite_service.list_invitations(g.user["id"]),
        invitation_email_configured=mail_service.is_configured(),
    )


@bp.post("/invitations")
@admin_required
def create_invitation():
    try:
        invitation = tenant_invite_service.create_invitation(
            g.user["id"], request.form.get("email", ""), request.form.get("role", "staff")
        )
        if invitation["email_queued"]:
            flash(
                f"Đã xếp lời mời vào hàng gửi email tới {invitation['email']}. "
                "Liên kết chấp nhận không hiển thị trong trang quản trị.",
                "success",
            )
        else:
            invite_path = url_for("users.accept_invitation", token=invitation["token"])
            invite_link = f"{current_app.config['PUBLIC_BASE_URL']}{invite_path}"
            flash(
                f"Lời mời tới {invitation['email']} có hiệu lực 7 ngày. "
                f"Sao chép và gửi riêng liên kết này: {invite_link}",
                "success",
            )
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.index"))


@bp.post("/invitations/<int:invitation_id>/revoke")
@admin_required
def revoke_invitation(invitation_id):
    try:
        tenant_invite_service.revoke_invitation(g.user["id"], invitation_id)
        flash("Đã thu hồi lời mời.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.index"))


@bp.get("/ownership")
@admin_required
def ownership():
    try:
        context = tenant_owner_transfer_service.get_page_context(g.user["id"])
    except ServiceError:
        abort(403)
    response = make_response(render_template("users/ownership.html", **context))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


@bp.post("/ownership")
@admin_required
def start_ownership_transfer():
    try:
        transfer = tenant_owner_transfer_service.initiate_transfer(
            g.user["id"],
            request.form.get("target_user_id", ""),
            request.form.get("current_password", ""),
        )
        if transfer["email_queued"]:
            flash("Đã gửi thông báo xác nhận tới email đã xác minh của quản trị viên được chọn.", "success")
        else:
            flash("Đã tạo yêu cầu. Quản trị viên được chọn cần đăng nhập, mở trang này và xác nhận.", "success")
    except RateLimitError as exc:
        flash(str(exc), "error")
        response = make_response(redirect(url_for("users.ownership")), 429)
        response.headers["Retry-After"] = str(exc.retry_after)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.ownership"))


@bp.post("/ownership/<int:transfer_id>/cancel")
@admin_required
def cancel_ownership_transfer(transfer_id):
    try:
        tenant_owner_transfer_service.cancel_transfer(
            g.user["id"], transfer_id, request.form.get("current_password", "")
        )
        flash("Đã thu hồi yêu cầu bàn giao.", "success")
    except RateLimitError as exc:
        flash(str(exc), "error")
        response = make_response(redirect(url_for("users.ownership")), 429)
        response.headers["Retry-After"] = str(exc.retry_after)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except NotFoundError:
        abort(404)
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.ownership"))


@bp.post("/ownership/<int:transfer_id>/accept")
@admin_required
def accept_ownership_transfer(transfer_id):
    try:
        tenant_owner_transfer_service.accept_transfer(
            g.user["id"], transfer_id, request.form.get("current_password", "")
        )
        flash("Bạn đã nhận bàn giao quyền chủ cửa hàng; người gửi trở thành quản trị viên.", "success")
    except RateLimitError as exc:
        flash(str(exc), "error")
        response = make_response(redirect(url_for("users.ownership")), 429)
        response.headers["Retry-After"] = str(exc.retry_after)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except NotFoundError:
        abort(404)
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.ownership"))


@bp.route("/invitations/accept", methods=["GET", "POST"])
def accept_invitation():
    token = request.form.get("token", "") if request.method == "POST" else request.args.get("token", "")
    try:
        invite = tenant_invite_service.preview_invitation(token)
        if request.method == "POST":
            user = tenant_invite_service.accept_invitation(
                token,
                request.form.get("username", ""),
                request.form.get("password", ""),
                request.form.get("full_name", ""),
            )
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["tenant_id"] = user["tenant_id"]
            session["session_version"] = user["session_version"]
            flash(f"Bạn đã tham gia {user['tenant_name']}.", "success")
            return redirect(url_for("main.dashboard"))
    except ServiceError as exc:
        if request.method == "GET" or isinstance(exc, NotFoundError):
            abort(404)
        flash(str(exc), "error")
        try:
            invite = tenant_invite_service.preview_invitation(token)
        except ServiceError:
            abort(404)
    return render_template("users/accept_invitation.html", invite=invite, token=token)


@bp.after_request
def protect_invitation_token(response):
    if request.endpoint == "users.accept_invitation":
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        try:
            auth_service.create_user(g.user["id"], request.form)
            flash("Đã tạo tài khoản.", "success")
            return redirect(url_for("users.index"))
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template("users/form.html")


@bp.post("/<int:user_id>/update")
@admin_required
def update(user_id):
    try:
        auth_service.update_user(g.user["id"], user_id, request.form)
        flash("Đã cập nhật tài khoản.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("users.index"))


@bp.route("/export", methods=["GET", "POST"])
@admin_required
def export_current_store():
    if request.method == "GET":
        response = make_response(render_template(
            "users/export.html", export_jobs=tenant_export_service.list_export_jobs(g.user["id"])
        ))
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response

    try:
        job_id = tenant_export_service.enqueue_export(
            g.user["id"],
            request.form.get("current_password", ""),
            request.form.get("passphrase", ""),
            request.form.get("passphrase_confirmation", ""),
        )
        flash("Đã xếp yêu cầu xuất vào hàng đợi. Bạn có thể theo dõi tiến độ tại đây.", "success")
        return redirect(url_for("users.export_job", job_id=job_id))
    except RateLimitError as exc:
        flash(str(exc), "error")
        response = make_response(render_template("users/export.html"), 429)
        response.headers["Retry-After"] = str(exc.retry_after)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except ServiceError as exc:
        flash(str(exc), "error")
        response = make_response(render_template("users/export.html"), 400)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response
    except (OSError, ValueError, RuntimeError):
        current_app.logger.exception("Could not queue tenant self-service export")
        flash("Chưa thể xếp yêu cầu xuất dữ liệu. Kiểm tra cấu hình rồi thử lại.", "error")
        response = make_response(render_template("users/export.html"), 500)
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        return response


@bp.get("/export/jobs/<int:job_id>")
@admin_required
def export_job(job_id):
    try:
        job = tenant_export_service.get_export_job(g.user["id"], job_id)
    except NotFoundError:
        abort(404)
    response = make_response(render_template("users/export_job.html", job=job))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


@bp.get("/export/jobs/<int:job_id>/status")
@admin_required
def export_job_status(job_id):
    try:
        job = tenant_export_service.get_export_job(g.user["id"], job_id)
    except NotFoundError:
        abort(404)
    status = job["status"]
    if job["expired"]:
        status = "expired"
    payload = {"status": status, "attempt": job["attempt_count"]}
    if status == "ready":
        payload["download_url"] = url_for("users.download_export", job_id=job_id)
        payload["expires_at"] = job["expires_at"].isoformat() if job["expires_at"] else None
    elif status == "failed":
        payload["message"] = "Không thể tạo bản xuất. Hãy thử gửi yêu cầu mới hoặc liên hệ quản trị hệ thống."
    response = jsonify(payload)
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


@bp.get("/export/jobs/<int:job_id>/download")
@admin_required
def download_export(job_id):
    try:
        job = tenant_export_service.get_downloadable_export(g.user["id"], job_id)
    except NotFoundError:
        abort(404)
    try:
        storage = get_export_storage(current_app.config)
        artifact_exists = storage.exists(job["artifact_key"])
    except Exception:
        current_app.logger.exception("Tenant export storage is unavailable (job_id=%s)", job_id)
        abort(503)
    if not artifact_exists:
        abort(404)

    def stream():
        with storage.open(job["artifact_key"]) as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    response = Response(
        stream_with_context(stream()),
        mimetype="application/vnd.petcare.encrypted-export",
        headers={
            "Content-Disposition": f'attachment; filename="petcare-export-{job_id}.pcarexport"',
            "Content-Length": str(job["artifact_size"]),
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
    return response
