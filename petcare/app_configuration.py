"""Validate runtime configuration and install app-scoped infrastructure."""

from threading import BoundedSemaphore
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, MultiFernet
from werkzeug.middleware.proxy_fix import ProxyFix

from petcare.config import mysql_config
from petcare.services.mail_service import (
    validate_production_config as validate_production_mail_config,
    validate_runtime_config as validate_mail_runtime_config,
)
from petcare.services.tenant_export_storage import validate_export_storage_config
from petcare.vision.media_storage import validate_media_config


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
        raise RuntimeError(
            "LAN_ACCESS_BASE_URL must be a valid HTTP(S) origin without credentials, path, query, or fragment."
        )
    if settings.get("APP_ENV") == "production" and base_url.scheme != "https":
        raise RuntimeError("Production requires LAN_ACCESS_BASE_URL to use HTTPS.")


def validate_app_configuration(app):
    """Reject unsafe or inconsistent settings before the app serves requests."""
    settings = app.config
    _validate_lan_access_config(settings)
    if settings.get("TRUST_PROXY"):
        # Trust only the immediate proxy's forwarded client IP and scheme.
        # Do not trust forwarded host/port; the proxy must overwrite these
        # headers and must be the only network path to the application.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    if not 1 <= int(settings.get("AI_TIMEOUT_SECONDS", 15)) <= 60:
        raise RuntimeError("AI_TIMEOUT_SECONDS must be between 1 and 60 seconds.")
    if not 0 <= int(settings.get("AI_VISION_MAX_RETRIES", 1)) <= 1:
        raise RuntimeError("AI_VISION_MAX_RETRIES must be 0 or 1.")
    reasoning_effort = str(settings.get("AI_REASONING_EFFORT", "") or "").strip().lower()
    if reasoning_effort and reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
        raise RuntimeError("AI_REASONING_EFFORT must be one of none, low, medium, high, xhigh, or max.")
    if not 1 <= int(settings.get("DB_POOL_SIZE", 5)) <= 32:
        raise RuntimeError("DB_POOL_SIZE must be between 1 and 32 connections per process.")
    image_processing_concurrency = int(settings.get("IMAGE_PROCESSING_CONCURRENCY", 1))
    if not 1 <= image_processing_concurrency <= 4:
        raise RuntimeError("IMAGE_PROCESSING_CONCURRENCY must be between 1 and 4 per process.")
    app.extensions["petcare_image_processing_slots"] = BoundedSemaphore(
        image_processing_concurrency
    )
    metrics_token = str(settings.get("OPS_METRICS_TOKEN", "") or "").strip()
    if metrics_token and len(metrics_token) < 32:
        raise RuntimeError("OPS_METRICS_TOKEN must contain at least 32 characters when enabled.")
    validate_media_config(settings)
    validate_export_storage_config(settings)
    if not 1 <= int(settings.get("TENANT_EXPORT_RETENTION_HOURS", 24)) <= 168:
        raise RuntimeError("TENANT_EXPORT_RETENTION_HOURS must be between 1 and 168 hours.")
    validate_mail_runtime_config(settings)
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
        if not 1 <= int(settings.get(setting, 1)) <= 1000:
            raise RuntimeError(f"{setting} must be between 1 and 1000 requests per minute.")
    if settings.get("APP_ENV") == "production":
        secret_key = settings.get("SECRET_KEY", "")
        if (
            not settings.get("SECRET_KEY_CONFIGURED")
            or len(secret_key) < 32
            or secret_key in {"replace-with-a-long-random-secret", "change-me"}
        ):
            raise RuntimeError("Production requires a unique SECRET_KEY of at least 32 characters.")
        if not settings.get("SESSION_COOKIE_SECURE"):
            raise RuntimeError("Production requires secure session cookies over HTTPS.")
        if settings.get("DEBUG"):
            raise RuntimeError("Debug mode must be disabled in production.")
        if not settings.get("DB_PASSWORD"):
            raise RuntimeError("Production requires a dedicated MySQL password.")
        if settings.get("DB_PASSWORD") in {
            "replace-with-a-local-password", "change-this-local-password", "password", "root"
        }:
            raise RuntimeError("Production cannot use an example or default database password.")
        if str(settings.get("DB_USER", "")).strip().lower() == "root":
            raise RuntimeError("Production must use a least-privilege MySQL account, not root.")
        if settings.get("DB_NAME", "").lower().endswith(("_dev", "_test")):
            raise RuntimeError("Production must use a dedicated database, not a _dev or _test database.")
        public_base = urlsplit(settings.get("PUBLIC_BASE_URL", ""))
        if (
            public_base.scheme != "https"
            or not public_base.netloc
            or public_base.username
            or public_base.password
            or public_base.query
            or public_base.fragment
        ):
            raise RuntimeError("Production requires PUBLIC_BASE_URL to be a trusted HTTPS origin.")
        validate_production_mail_config(settings)
        mysql_config(settings)
        export_job_key = str(settings.get("TENANT_EXPORT_JOB_KEY", "")).strip()
        if not export_job_key:
            raise RuntimeError("Production requires a stable TENANT_EXPORT_JOB_KEY.")
        try:
            MultiFernet([
                Fernet(key.encode("ascii"))
                for key in [export_job_key, *settings.get("TENANT_EXPORT_JOB_FALLBACK_KEYS", ())]
            ])
        except (UnicodeEncodeError, ValueError, TypeError) as exc:
            raise RuntimeError("TENANT_EXPORT_JOB_KEY must be a valid Fernet key.") from exc
