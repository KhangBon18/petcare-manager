"""Flask application factory."""

from threading import BoundedSemaphore
from urllib.parse import urlsplit

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from cryptography.fernet import Fernet, MultiFernet
from flask_wtf.csrf import CSRFProtect
import mysql.connector
from werkzeug.middleware.proxy_fix import ProxyFix

from petcare.auth import load_current_user
from petcare.config import Config, mysql_config
from petcare.money import (
    currency_precision,
    currency_step,
    format_money as render_money,
    money_input_value,
)
from petcare.timezones import DEFAULT_TIMEZONE, format_tenant_datetime
from petcare.i18n import (
    LOCALE_LABELS,
    SUPPORTED_LOCALES,
    current_locale,
    translate,
    translate_audit_summary,
)
from petcare.services.mail_service import (
    validate_production_config as validate_production_mail_config,
    validate_runtime_config as validate_mail_runtime_config,
)
from petcare.vision.media_storage import validate_media_config
from petcare.services.tenant_export_storage import validate_export_storage_config

csrf = CSRFProtect()
_IMAGE_PROCESSING_ENDPOINTS = frozenset({
    "pets.find_similar", "pets.create", "pets.edit",
    "products.create", "products.edit",
})
_CATALOG_IMAGE_UPLOAD_ENDPOINTS = frozenset({
    "pets.create", "pets.edit", "products.create", "products.edit",
})


def _validate_lan_access_config(settings):
    if not settings.get("LAN_ACCESS_ENABLED"):
        return
    base_url = urlsplit(str(settings.get("LAN_ACCESS_BASE_URL", "")).strip())
    try:
        port = base_url.port
    except ValueError as exc:
        raise RuntimeError("LAN_ACCESS_BASE_URL must be a valid HTTP(S) origin.") from exc
    if (
        base_url.scheme not in {"http", "https"}
        or not base_url.hostname
        or base_url.username
        or base_url.password
        or base_url.query
        or base_url.fragment
        or base_url.path not in {"", "/"}
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise RuntimeError("LAN_ACCESS_BASE_URL must be a valid HTTP(S) origin without credentials, path, query, or fragment.")
    if settings.get("APP_ENV") == "production" and base_url.scheme != "https":
        raise RuntimeError("Production requires LAN_ACCESS_BASE_URL to use HTTPS.")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    _validate_lan_access_config(app.config)
    if app.config.get("TRUST_PROXY"):
        # Trust only the immediate proxy's forwarded client IP and scheme.
        # Do not trust forwarded host/port; the proxy must overwrite these
        # headers and must be the only network path to the application.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    if not 1 <= int(app.config.get("AI_TIMEOUT_SECONDS", 15)) <= 60:
        raise RuntimeError("AI_TIMEOUT_SECONDS must be between 1 and 60 seconds.")
    if not 1 <= int(app.config.get("DB_POOL_SIZE", 5)) <= 32:
        raise RuntimeError("DB_POOL_SIZE must be between 1 and 32 connections per process.")
    image_processing_concurrency = int(app.config.get("IMAGE_PROCESSING_CONCURRENCY", 1))
    if not 1 <= image_processing_concurrency <= 4:
        raise RuntimeError("IMAGE_PROCESSING_CONCURRENCY must be between 1 and 4 per process.")
    app.extensions["petcare_image_processing_slots"] = BoundedSemaphore(
        image_processing_concurrency
    )
    metrics_token = str(app.config.get("OPS_METRICS_TOKEN", "") or "").strip()
    if metrics_token and len(metrics_token) < 32:
        raise RuntimeError("OPS_METRICS_TOKEN must contain at least 32 characters when enabled.")
    validate_media_config(app.config)
    validate_export_storage_config(app.config)
    if not 1 <= int(app.config.get("TENANT_EXPORT_RETENTION_HOURS", 24)) <= 168:
        raise RuntimeError("TENANT_EXPORT_RETENTION_HOURS must be between 1 and 168 hours.")
    validate_mail_runtime_config(app.config)
    for setting in (
        "ASSISTANT_RATE_LIMIT_PER_MINUTE",
        "VISION_RATE_LIMIT_PER_MINUTE",
        "CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE",
        "CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE",
        "TENANT_EXPORT_RATE_LIMIT_PER_MINUTE",
        "PASSWORD_RESET_RATE_LIMIT_PER_MINUTE",
        "PASSWORD_RESET_IP_RATE_LIMIT_PER_MINUTE",
        "EMAIL_VERIFICATION_RATE_LIMIT_PER_MINUTE",
        "EMAIL_VERIFICATION_IP_RATE_LIMIT_PER_MINUTE",
        "TENANT_INVITATION_RATE_LIMIT_PER_MINUTE",
        "TENANT_OWNER_TRANSFER_RATE_LIMIT_PER_MINUTE",
        "PUBLIC_SIGNUP_EMAIL_RATE_LIMIT_PER_MINUTE",
        "PUBLIC_SIGNUP_IP_RATE_LIMIT_PER_MINUTE",
    ):
        if not 1 <= int(app.config.get(setting, 1)) <= 1000:
            raise RuntimeError(f"{setting} must be between 1 and 1000 requests per minute.")
    if app.config.get("APP_ENV") == "production":
        secret_key = app.config.get("SECRET_KEY", "")
        if (
            not app.config.get("SECRET_KEY_CONFIGURED")
            or len(secret_key) < 32
            or secret_key in {"replace-with-a-long-random-secret", "change-me"}
        ):
            raise RuntimeError("Production requires a unique SECRET_KEY of at least 32 characters.")
        if not app.config.get("SESSION_COOKIE_SECURE"):
            raise RuntimeError("Production requires secure session cookies over HTTPS.")
        if app.config.get("DEBUG"):
            raise RuntimeError("Debug mode must be disabled in production.")
        if not app.config.get("DB_PASSWORD"):
            raise RuntimeError("Production requires a dedicated MySQL password.")
        if app.config.get("DB_PASSWORD") in {
            "replace-with-a-local-password", "change-this-local-password", "password", "root"
        }:
            raise RuntimeError("Production cannot use an example or default database password.")
        if str(app.config.get("DB_USER", "")).strip().lower() == "root":
            raise RuntimeError("Production must use a least-privilege MySQL account, not root.")
        if app.config.get("DB_NAME", "").lower().endswith(("_dev", "_test")):
            raise RuntimeError("Production must use a dedicated database, not a _dev or _test database.")
        public_base = urlsplit(app.config.get("PUBLIC_BASE_URL", ""))
        if (
            public_base.scheme != "https"
            or not public_base.netloc
            or public_base.username
            or public_base.password
            or public_base.query
            or public_base.fragment
        ):
            raise RuntimeError("Production requires PUBLIC_BASE_URL to be a trusted HTTPS origin.")
        validate_production_mail_config(app.config)
        mysql_config(app.config)
        export_job_key = str(app.config.get("TENANT_EXPORT_JOB_KEY", "")).strip()
        if not export_job_key:
            raise RuntimeError("Production requires a stable TENANT_EXPORT_JOB_KEY.")
        try:
            MultiFernet([
                Fernet(key.encode("ascii"))
                for key in [export_job_key, *app.config.get("TENANT_EXPORT_JOB_FALLBACK_KEYS", ())]
            ])
        except (UnicodeEncodeError, ValueError, TypeError) as exc:
            raise RuntimeError("TENANT_EXPORT_JOB_KEY must be a valid Fernet key.") from exc
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

    from petcare.routes.auth_routes import bp as auth_bp
    from petcare.routes.assistant_routes import bp as assistant_bp
    from petcare.routes.audit_routes import bp as audit_bp
    from petcare.routes.account_routes import bp as account_bp
    from petcare.routes.customer_routes import bp as customer_bp
    from petcare.routes.invoice_routes import bp as invoice_bp
    from petcare.routes.health_routes import bp as health_bp
    from petcare.routes.main_routes import bp as main_bp
    from petcare.routes.metrics_routes import bp as metrics_bp
    from petcare.routes.pet_routes import bp as pet_bp
    from petcare.routes.product_routes import bp as product_bp
    from petcare.routes.report_routes import bp as report_bp
    from petcare.routes.store_routes import bp as store_bp
    from petcare.routes.user_routes import bp as user_bp

    for blueprint in (
        health_bp, metrics_bp, auth_bp, assistant_bp, main_bp, customer_bp, pet_bp, product_bp,
        invoice_bp, report_bp, user_bp, audit_bp, account_bp, store_bp,
    ):
        app.register_blueprint(blueprint)

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

    @app.context_processor
    def inject_helpers():
        def format_money(amount, currency_code=None):
            code = currency_code or (g.tenant or {}).get("default_currency", "VND")
            locale = "en_US" if current_locale() == "en" else "vi_VN"
            return render_money(amount, code, locale)
        def format_datetime(value, date_format=None):
            zone = (g.tenant or {}).get("timezone", DEFAULT_TIMEZONE)
            if date_format is None:
                date_format = "%b %d, %Y %H:%M" if current_locale() == "en" else "%d/%m/%Y %H:%M"
            return format_tenant_datetime(value, zone, date_format)
        def page_url(page):
            values = request.args.to_dict(flat=True)
            values["page"] = page
            return url_for(request.endpoint, **values)
        return {
            "format_money": format_money,
            "format_datetime": format_datetime,
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

    return app
