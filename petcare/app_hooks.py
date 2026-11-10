"""Register request lifecycle hooks and shared Flask error/template handlers."""

import mysql.connector
from flask import flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect

from petcare.auth import load_current_user
from petcare.i18n import (
    LOCALE_LABELS,
    SUPPORTED_LOCALES,
    current_locale,
    translate,
    translate_audit_summary,
)
from petcare.money import (
    currency_precision,
    currency_step,
    format_money as render_money,
    format_number as render_number,
    money_input_value,
)
from petcare.timezones import DEFAULT_TIMEZONE, format_tenant_date, format_tenant_datetime

_IMAGE_PROCESSING_ENDPOINTS = frozenset({
    "pets.find_similar", "pets.suggest_attributes", "pets.create", "pets.edit",
    "products.create", "products.edit",
})
_CATALOG_IMAGE_UPLOAD_ENDPOINTS = frozenset({
    "pets.create", "pets.edit", "products.create", "products.edit",
})


def register_request_hooks(app, csrf: CSRFProtect):
    csrf.init_app(app)
    app.before_request(load_current_user)

    @app.before_request
    def select_locale():
        user_locale = g.user.get("preferred_locale") if g.get("user") else None
        locale = user_locale or session.get("locale")
        if locale not in SUPPORTED_LOCALES:
            locale = request.accept_languages.best_match(SUPPORTED_LOCALES, default="vi")
        g.locale = locale

    @app.before_request
    def reserve_image_processing_slot():
        if (
            not g.get("user")
            or request.method != "POST"
            or request.endpoint not in _IMAGE_PROCESSING_ENDPOINTS
        ):
            return None
        photo = request.files.get("photo")
        if photo is None or not photo.filename:
            return None
        if (
            request.endpoint in _CATALOG_IMAGE_UPLOAD_ENDPOINTS
            and g.user.get("role") == "admin"
        ):
            from petcare.services import request_throttle_service

            allowed, retry_after = request_throttle_service.consume_with_ip_limit(
                g.user["id"], request.remote_addr, "catalog_image_upload"
            )
            if not allowed:
                flash("Bạn đã tải lên nhiều ảnh trong thời gian ngắn. Vui lòng thử lại sau.", "warning")
                response = redirect(url_for(request.endpoint, **(request.view_args or {})))
                response.headers["Retry-After"] = str(retry_after)
                return response
        slots = app.extensions["petcare_image_processing_slots"]
        if slots.acquire(blocking=False):
            g.image_processing_slot_acquired = True
            return None
        if request.endpoint == "pets.suggest_attributes":
            message = (
                "Đang xử lý ảnh khác. Hãy thử lại sau."
                if g.locale == "vi"
                else "Other images are being processed. Try again shortly."
            )
            return jsonify(
                status="rate_limited",
                code="image_processing_busy",
                error=message,
            ), 429, {"Retry-After": "2"}
        flash("Đang xử lý ảnh khác. Vui lòng thử lại sau vài giây.", "warning")
        response = redirect(url_for(request.endpoint, **(request.view_args or {})))
        response.headers["Retry-After"] = "2"
        return response

    @app.teardown_request
    def release_image_processing_slot(_error=None):
        if getattr(g, "image_processing_slot_acquired", False):
            app.extensions["petcare_image_processing_slots"].release()

    @app.after_request
    def set_security_headers(response):
        # Authenticated pages and JSON responses can contain store data. Do not
        # let browsers or shared intermediaries retain one tenant's records
        # after logout or a store switch.
        if g.get("user"):
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(self), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; object-src 'none'; script-src 'self'; "
            "style-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
            "media-src 'self' blob:; connect-src 'self'",
        )
        if app.config.get("APP_ENV") == "production" and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def payload_too_large(_error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_error(error):
        original = getattr(error, "original_exception", None)
        if original:
            app.logger.error(
                "Unhandled request error",
                exc_info=(type(original), original, original.__traceback__),
            )
        else:
            app.logger.error("Internal server error")
        return render_template("errors/500.html"), 500

    @app.errorhandler(mysql.connector.Error)
    def database_unavailable(error):
        app.logger.error("MySQL request failed (errno=%s)", getattr(error, "errno", None))
        return render_template("errors/database.html"), 503


def register_template_helpers(app):
    @app.context_processor
    def inject_helpers():
        def format_money(amount, currency_code=None):
            code = currency_code or (g.tenant or {}).get("default_currency", "VND")
            locale = "en_US" if current_locale() == "en" else "vi_VN"
            return render_money(amount, code, locale)

        def format_datetime(value, date_format=None):
            zone = (g.tenant or {}).get("timezone", DEFAULT_TIMEZONE)
            return format_tenant_datetime(value, zone, date_format, current_locale())

        def format_date(value):
            return format_tenant_date(value, current_locale())

        def format_number(value, pattern=None):
            locale = "en_US" if current_locale() == "en" else "vi_VN"
            return render_number(value, locale, pattern)

        def page_url(page):
            values = request.args.to_dict(flat=True)
            values.update(request.view_args or {})
            values["page"] = page
            return url_for(request.endpoint, **values)

        return {
            "format_money": format_money,
            "format_datetime": format_datetime,
            "format_date": format_date,
            "format_number": format_number,
            "currency_precision": currency_precision,
            "currency_step": currency_step,
            "money_input_value": money_input_value,
            "page_url": page_url,
            "public_signup_enabled": app.config.get("PUBLIC_SIGNUP_ENABLED", False),
            "locale": current_locale(),
            "locale_labels": LOCALE_LABELS,
            "t": translate,
            "translate_audit_summary": translate_audit_summary,
        }
