"""Self-service email verification and account recovery routes."""

from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, session, url_for

from petcare.auth import login_required
from petcare.services import account_security_service, request_throttle_service
from petcare.services.exceptions import RateLimitError, ServiceError


bp = Blueprint("account", __name__, url_prefix="/account")


def _private_response(template, **context):
    response = make_response(render_template(template, **context))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _consume_ip_limit(scope, message):
    allowed, retry_after = request_throttle_service.consume(
        request.remote_addr or "unknown", scope
    )
    if not allowed:
        raise RateLimitError(message, retry_after)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        try:
            result = account_security_service.set_account_email(
                g.user["id"], g.tenant["id"],
                request.form.get("current_password", ""),
                request.form.get("email", ""),
            )
            session["session_version"] = result["session_version"]
            if result["status"] == "unchanged":
                flash("Địa chỉ email hiện tại đã được xác minh.", "success")
            elif result["status"] == "removed":
                flash("Đã gỡ email. Tài khoản sẽ không thể khôi phục mật khẩu bằng email.", "success")
            elif result["email_sent"]:
                flash("Đã ghi nhận yêu cầu. Liên kết xác minh sẽ được gửi qua email sau ít phút.", "success")
            else:
                flash("Email đã lưu nhưng chưa xác minh. Không thể xếp thư xác minh; hãy kiểm tra SMTP và outbox.", "warning")
        except ServiceError as exc:
            flash(str(exc), "error")
        return redirect(url_for("account.settings"))

    return _private_response("account/settings.html", user=g.user)


@bp.post("/profile")
@login_required
def update_profile():
    try:
        result = account_security_service.update_account_profile(
            g.user["id"],
            request.form.get("current_password", ""),
            request.form.get("full_name", ""),
        )
        if result["status"] == "unchanged":
            flash("Tên hiển thị hiện tại chưa thay đổi.", "info")
        else:
            flash("Tên hiển thị đã được cập nhật.", "success")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("account.settings"))


@bp.post("/verification/resend")
@login_required
def resend_verification():
    try:
        result = account_security_service.resend_email_verification(g.user["id"])
        if result["status"] == "not_pending":
            flash("Không có email nào đang chờ xác minh.", "info")
        elif result["email_sent"]:
            flash("Đã xếp yêu cầu gửi lại liên kết xác minh.", "success")
        else:
            flash("Chưa thể xếp thư vào hàng đợi. Kiểm tra SMTP/outbox rồi thử lại.", "error")
    except RateLimitError as exc:
        response = _private_response("account/settings.html", user=g.user)
        response.status_code = 429
        response.headers["Retry-After"] = str(exc.retry_after)
        flash(str(exc), "error")
        response.set_data(render_template("account/settings.html", user=g.user))
        return response
    return redirect(url_for("account.settings"))


@bp.route("/email/verify", methods=["GET", "POST"])
def verify_email():
    token = request.form.get("token", "") if request.method == "POST" else request.args.get("token", "")
    if request.method == "GET":
        if not account_security_service.preview_email_verification(token):
            abort(404)
        return _private_response("account/verify_email.html", token=token)

    try:
        _consume_ip_limit("email_verification_ip", "Bạn đã thử xác minh quá nhiều lần. Hãy chờ rồi thử lại.")
        if not account_security_service.verify_account_email(token):
            abort(404)
    except RateLimitError as exc:
        response = _private_response("account/verify_email.html", token=token)
        response.status_code = 429
        response.headers["Retry-After"] = str(exc.retry_after)
        flash(str(exc), "error")
        return response
    flash("Email đã được xác minh. Bạn có thể dùng nó để khôi phục tài khoản.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/password/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        try:
            account_security_service.request_password_reset(
                request.form.get("email", ""), request.remote_addr or "unknown"
            )
        except RateLimitError as exc:
            response = _private_response("account/forgot_password.html")
            response.status_code = 429
            response.headers["Retry-After"] = str(exc.retry_after)
            flash("Vui lòng chờ rồi thử lại. Nếu tài khoản tồn tại, hướng dẫn sẽ được gửi tới email đã xác minh.", "info")
            response.set_data(render_template("account/forgot_password.html"))
            return response
        flash(
            "Nếu tài khoản tồn tại và email đã xác minh, hướng dẫn đặt lại mật khẩu sẽ được gửi.",
            "success",
        )
        return redirect(url_for("account.forgot_password"))
    return _private_response("account/forgot_password.html")


@bp.route("/password/reset", methods=["GET", "POST"])
def reset_password():
    token = request.form.get("token", "") if request.method == "POST" else request.args.get("token", "")
    if request.method == "GET":
        if not account_security_service.preview_password_reset(token):
            abort(404)
        return _private_response("account/reset_password.html", token=token)

    try:
        _consume_ip_limit("password_reset_ip", "Bạn đã thử quá nhiều lần. Hãy chờ rồi thử lại.")
        if not account_security_service.reset_password(
            token, request.form.get("password", ""), request.form.get("confirmation", "")
        ):
            abort(404)
    except ServiceError as exc:
        response = _private_response("account/reset_password.html", token=token)
        response.status_code = 400 if not isinstance(exc, RateLimitError) else 429
        if isinstance(exc, RateLimitError):
            response.headers["Retry-After"] = str(exc.retry_after)
        flash(str(exc), "error")
        response.set_data(render_template("account/reset_password.html", token=token))
        return response
    flash("Mật khẩu đã được đặt lại. Đăng nhập bằng mật khẩu mới để tiếp tục.", "success")
    return redirect(url_for("auth.login"))
