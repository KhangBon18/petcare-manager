from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, request, session, url_for

from petcare.i18n import SUPPORTED_LOCALES
from petcare.services.auth_service import load_active_user


def _safe_next_url(target):
    """Accept only same-origin absolute paths for post-login redirects."""
    if not isinstance(target, str) or not target.startswith("/"):
        return False
    if target.startswith("//") or "\\" in target or any(ord(char) < 32 for char in target):
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc


def load_current_user():
    if request.endpoint in {
        "static", "health.healthz", "health.readyz", "health.workersz"
    }:
        g.user = None
        g.tenant = None
        return
    user_id = session.get("user_id")
    tenant_id = session.get("tenant_id")
    g.user = load_active_user(
        user_id, tenant_id, session.get("session_version")
    ) if user_id else None
    if user_id and g.user is None:
        locale = session.get("locale") or request.accept_languages.best_match(
            SUPPORTED_LOCALES, default="vi"
        )
        session.clear()
        if locale in SUPPORTED_LOCALES:
            session["locale"] = locale
        flash("Phiên đăng nhập đã hết hạn hoặc tài khoản đã bị khóa.", "warning")
    if g.user:
        g.tenant = g.user.pop("tenant")
        g.tenant_id = g.tenant["id"]
        session["tenant_id"] = g.tenant_id
    else:
        g.tenant = None
        g.tenant_id = None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("auth.login"))
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
