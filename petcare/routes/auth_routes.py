from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, session, url_for

from petcare.auth import _safe_next_url, login_required
from petcare.i18n import SUPPORTED_LOCALES, translate
from petcare.money import currency_options
from petcare.timezones import COMMON_TIMEZONES, DEFAULT_TIMEZONE
from petcare.services import account_security_service, auth_service
from petcare.services.exceptions import RateLimitError, ServiceError

bp = Blueprint("auth", __name__)


@bp.post("/language")
def set_language():
    locale = request.form.get("locale", "")
    if locale not in SUPPORTED_LOCALES:
        abort(400)
    if g.user:
        auth_service.update_preferred_locale(g.user["id"], locale)
    session["locale"] = locale
    g.locale = locale
    target = request.form.get("next", "")
    if not _safe_next_url(target):
        target = url_for("main.dashboard") if g.user else url_for("auth.login")
    return redirect(target)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        remote_addr = request.remote_addr or "unknown"
        if auth_service.login_blocked(username, remote_addr):
            flash("Quá nhiều lần đăng nhập không thành công. Vui lòng thử lại sau 15 phút.", "error")
            return render_template("auth/login.html"), 429, {"Retry-After": "900"}
        user = auth_service.authenticate(
            username, request.form.get("password"), request.form.get("store_slug", "main")
        )
        if user is None:
            auth_service.record_login_failure(username, remote_addr)
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
            return render_template("auth/login.html"), 401
        auth_service.clear_login_failures(username, remote_addr)
        if not auth_service.record_auth_event(
            user["id"], user["tenant_id"], "auth.login_succeeded", "Đăng nhập thành công"
        ):
            flash("Cửa hàng hoặc quyền truy cập đã thay đổi. Vui lòng đăng nhập lại.", "error")
            return render_template("auth/login.html"), 403
        locale = user.get("preferred_locale") or g.locale
        session.clear()
        if locale in SUPPORTED_LOCALES:
            session["locale"] = locale
        session.permanent = True
        session["user_id"] = user["id"]
        session["tenant_id"] = user["tenant_id"]
        session["session_version"] = user["session_version"]
        flash(f"{translate('Xin chào')} {user['full_name']}!", "success")
        target = request.args.get("next", "")
        if not _safe_next_url(target):
            target = url_for("main.dashboard")
        return redirect(target)
    if g.user:
        return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    user_id = g.user["id"]
    tenant_id = g.tenant["id"]
    locale = g.locale
    session.clear()
    if locale in SUPPORTED_LOCALES:
        session["locale"] = locale
    auth_service.record_auth_event(user_id, tenant_id, "auth.logout", "Đăng xuất")
    flash("Bạn đã đăng xuất.", "success")
    return redirect(url_for("auth.login"))


@bp.post("/stores/switch")
@login_required
def switch_store():
    slug = request.form.get("store_slug", "")
    membership = auth_service.store_membership(g.user["id"], slug)
    if not membership:
        flash("Tài khoản của bạn không có quyền truy cập cửa hàng đó.", "error")
        return redirect(url_for("main.dashboard"))
    auth_service.record_auth_event(
        g.user["id"], g.tenant["id"], "auth.store_switched", "Chuyển cửa hàng"
    )
    session["tenant_id"] = membership["tenant_id"]
    flash(f"{translate('Đã chuyển sang cửa hàng')} {membership['tenant_name']}.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if not current_app.config.get("PUBLIC_SIGNUP_ENABLED", False):
        abort(404)
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            result = account_security_service.create_public_store(
                request.form.get("owner_name", ""),
                request.form.get("username", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
                request.form.get("store_name", ""),
                request.form.get("store_slug", ""),
                request.remote_addr or "unknown",
                request.form.get("default_currency", "VND"),
                request.form.get("timezone", DEFAULT_TIMEZONE),
            )
            if result["email_queued"]:
                flash(
                    f"Cửa hàng {result['tenant_name']} đã tạo. Mở email xác minh rồi đăng nhập "
                    f"bằng mã cửa hàng {result['tenant_slug']}.",
                    "success",
                )
            else:
                verify_path = url_for(
                    "account.verify_email", token=result["verification_token"]
                )
                verify_link = current_app.config["PUBLIC_BASE_URL"] + verify_path
                return render_template(
                    "auth/signup_complete.html",
                    tenant_name=result["tenant_name"],
                    tenant_slug=result["tenant_slug"],
                    verify_link=verify_link,
                )
            return redirect(url_for("auth.login"))
        except RateLimitError as exc:
            flash(str(exc), "error")
            response = make_response(render_template(
                "auth/signup.html", currency_options=currency_options(g.locale),
                common_timezones=COMMON_TIMEZONES,
            ), 429)
            response.headers["Retry-After"] = str(exc.retry_after)
            return response
        except ServiceError as exc:
            flash(str(exc), "error")
    return render_template(
        "auth/signup.html", currency_options=currency_options(g.locale),
        common_timezones=COMMON_TIMEZONES,
    )


@bp.after_request
def protect_signup_responses(response):
    if request.endpoint == "auth.signup":
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
