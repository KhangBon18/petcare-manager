"""Environment-backed Flask and MySQL configuration."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


class Config:
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()
    _configured_secret = os.getenv("SECRET_KEY", "").strip()
    SECRET_KEY_CONFIGURED = bool(_configured_secret)
    SECRET_KEY = _configured_secret or secrets.token_hex(32)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv(
        "COOKIE_SECURE", "1" if APP_ENV == "production" else "0"
    ) == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
    WTF_CSRF_TIME_LIMIT = 60 * 60
    WTF_CSRF_SSL_STRICT = APP_ENV == "production"
    APP_PORT = int(os.getenv("APP_PORT", "5000"))
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://127.0.0.1:{APP_PORT}").strip().rstrip("/")
    PUBLIC_SIGNUP_ENABLED = os.getenv("PUBLIC_SIGNUP_ENABLED", "0") == "1"
    PUBLIC_SIGNUP_EMAIL_RATE_LIMIT_PER_MINUTE = int(os.getenv("PUBLIC_SIGNUP_EMAIL_RATE_LIMIT_PER_MINUTE", "3"))
    PUBLIC_SIGNUP_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("PUBLIC_SIGNUP_IP_RATE_LIMIT_PER_MINUTE", "5"))
    MAIL_HOST = os.getenv("MAIL_HOST", "").strip()
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "").strip()
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "PetCare Manager").strip()
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "1") == "1"
    MAIL_TIMEOUT_SECONDS = int(os.getenv("MAIL_TIMEOUT_SECONDS", "10"))
    MAIL_OUTBOX_KEY = os.getenv("MAIL_OUTBOX_KEY", "").strip()

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "petcare_shop_dev")
    DB_USER = os.getenv("DB_USER", "petcare_app")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    IMAGE_PROCESSING_CONCURRENCY = int(os.getenv("IMAGE_PROCESSING_CONCURRENCY", "1"))
    # Schema migration credentials are optional for development/test. Keep them
    # out of the long-running web container; only one-off initializer jobs use them.
    MIGRATION_DB_HOST = os.getenv("MIGRATION_DB_HOST", "").strip()
    MIGRATION_DB_PORT = os.getenv("MIGRATION_DB_PORT", "").strip()
    MIGRATION_DB_NAME = os.getenv("MIGRATION_DB_NAME", "").strip()
    MIGRATION_DB_USER = os.getenv("MIGRATION_DB_USER", "").strip()
    MIGRATION_DB_PASSWORD = os.getenv("MIGRATION_DB_PASSWORD", "")
    PET_IMAGE_DIR = os.getenv("PET_IMAGE_DIR", str(ROOT_DIR / "instance" / "pet-images"))
    PET_IMAGE_MAX_BYTES = 5 * 1024 * 1024
    PRODUCT_IMAGE_DIR = os.getenv("PRODUCT_IMAGE_DIR", str(ROOT_DIR / "instance" / "product-images"))
    PRODUCT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
    MEDIA_STORAGE_BACKEND = os.getenv("MEDIA_STORAGE_BACKEND", "local").strip().lower()
    MEDIA_S3_BUCKET = os.getenv("MEDIA_S3_BUCKET", "").strip()
    MEDIA_S3_REGION = os.getenv("MEDIA_S3_REGION", "").strip()
    MEDIA_S3_ENDPOINT_URL = os.getenv("MEDIA_S3_ENDPOINT_URL", "").strip()
    MEDIA_S3_ACCESS_KEY_ID = os.getenv("MEDIA_S3_ACCESS_KEY_ID", "").strip()
    MEDIA_S3_SECRET_ACCESS_KEY = os.getenv("MEDIA_S3_SECRET_ACCESS_KEY", "")
    MEDIA_S3_ADDRESSING_STYLE = os.getenv("MEDIA_S3_ADDRESSING_STYLE", "auto").strip().lower()
    MEDIA_S3_PREFIX = os.getenv("MEDIA_S3_PREFIX", "petcare").strip("/")
    MEDIA_S3_SERVER_SIDE_ENCRYPTION = os.getenv("MEDIA_S3_SERVER_SIDE_ENCRYPTION", "AES256").strip()
    MAX_CONTENT_LENGTH = 7 * 1024 * 1024
    AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "").strip()
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "").strip()
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "15"))
    AI_VISION_ENABLED = os.getenv("AI_VISION_ENABLED", "0") == "1"
    ASSISTANT_RATE_LIMIT_PER_MINUTE = int(os.getenv("ASSISTANT_RATE_LIMIT_PER_MINUTE", "20"))
    ASSISTANT_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("ASSISTANT_IP_RATE_LIMIT_PER_MINUTE", "120"))
    VISION_RATE_LIMIT_PER_MINUTE = int(os.getenv("VISION_RATE_LIMIT_PER_MINUTE", "8"))
    VISION_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("VISION_IP_RATE_LIMIT_PER_MINUTE", "40"))
    CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE = int(os.getenv("CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE", "12"))
    CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE", "60"))
    TENANT_EXPORT_RATE_LIMIT_PER_MINUTE = int(os.getenv("TENANT_EXPORT_RATE_LIMIT_PER_MINUTE", "2"))
    TENANT_EXPORT_JOB_KEY = os.getenv("TENANT_EXPORT_JOB_KEY", "").strip()
    TENANT_EXPORT_JOB_FALLBACK_KEYS = tuple(
        key.strip() for key in os.getenv("TENANT_EXPORT_JOB_FALLBACK_KEYS", "").split(",")
        if key.strip()
    )
    TENANT_EXPORT_STORAGE_BACKEND = os.getenv(
        "TENANT_EXPORT_STORAGE_BACKEND", MEDIA_STORAGE_BACKEND
    ).strip().lower()
    TENANT_EXPORT_DIR = os.getenv("TENANT_EXPORT_DIR", str(ROOT_DIR / "instance" / "tenant-exports"))
    TENANT_EXPORT_RETENTION_HOURS = int(os.getenv("TENANT_EXPORT_RETENTION_HOURS", "24"))
    PASSWORD_RESET_RATE_LIMIT_PER_MINUTE = int(os.getenv("PASSWORD_RESET_RATE_LIMIT_PER_MINUTE", "3"))
    PASSWORD_RESET_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("PASSWORD_RESET_IP_RATE_LIMIT_PER_MINUTE", "15"))
    EMAIL_VERIFICATION_RATE_LIMIT_PER_MINUTE = int(os.getenv("EMAIL_VERIFICATION_RATE_LIMIT_PER_MINUTE", "3"))
    EMAIL_VERIFICATION_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv("EMAIL_VERIFICATION_IP_RATE_LIMIT_PER_MINUTE", "10"))
    TENANT_INVITATION_RATE_LIMIT_PER_MINUTE = int(os.getenv("TENANT_INVITATION_RATE_LIMIT_PER_MINUTE", "10"))
    TENANT_OWNER_TRANSFER_RATE_LIMIT_PER_MINUTE = int(os.getenv("TENANT_OWNER_TRANSFER_RATE_LIMIT_PER_MINUTE", "5"))
    AI_ALLOW_HTTP_ENDPOINT = os.getenv("AI_ALLOW_HTTP_ENDPOINT", "0") == "1"
    # Phone access is opt-in: setting both values is required before run.py
    # binds to the local network interface.
    LAN_ACCESS_ENABLED = os.getenv("LAN_ACCESS_ENABLED", "0") == "1"
    LAN_ACCESS_BASE_URL = os.getenv("LAN_ACCESS_BASE_URL", "").strip().rstrip("/")
    TRUST_PROXY = os.getenv("TRUST_PROXY", "0") == "1"
    OPS_METRICS_TOKEN = os.getenv("OPS_METRICS_TOKEN", "").strip()


def _config_value(settings, name, default=None):
    if hasattr(settings, "get"):
        return settings.get(name, default)
    return getattr(settings, name, default)


def mysql_config(settings=None):
    """Build runtime or migration connection options with verified TLS when configured."""
    settings = Config if settings is None else settings
    config = {
        "host": _config_value(settings, "DB_HOST", Config.DB_HOST),
        "port": _config_value(settings, "DB_PORT", Config.DB_PORT),
        "database": _config_value(settings, "DB_NAME", Config.DB_NAME),
        "user": _config_value(settings, "DB_USER", Config.DB_USER),
        "password": _config_value(settings, "DB_PASSWORD", Config.DB_PASSWORD),
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "connection_timeout": 5,
        "autocommit": False,
    }
    ca_path = str(_config_value(settings, "DB_SSL_CA", "") or "").strip()
    app_env = str(_config_value(settings, "APP_ENV", Config.APP_ENV)).strip().lower()
    if app_env == "production" and not ca_path:
        raise RuntimeError("Production requires DB_SSL_CA for verified MySQL TLS connections.")
    if ca_path:
        if not Path(ca_path).is_file() or not os.access(ca_path, os.R_OK):
            raise RuntimeError("DB_SSL_CA must point to a readable CA certificate file.")
        config.update(
            ssl_ca=ca_path,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )
    return config


def migration_mysql_config():
    """Return the one-off schema account config, with dev/test-only fallback."""
    user = Config.MIGRATION_DB_USER
    password = Config.MIGRATION_DB_PASSWORD
    if bool(user) != bool(password):
        raise RuntimeError("MIGRATION_DB_USER and MIGRATION_DB_PASSWORD must be set together.")
    if not user:
        if Config.APP_ENV == "production":
            raise RuntimeError(
                "Production schema initialization requires a dedicated migration database account."
            )
        return mysql_config()
    if user == Config.DB_USER:
        raise RuntimeError("The migration database account must differ from the runtime account.")

    database = Config.MIGRATION_DB_NAME or Config.DB_NAME
    if database != Config.DB_NAME:
        raise RuntimeError("Migration and runtime accounts must target the same database.")
    config = mysql_config()
    config.update(
        host=Config.MIGRATION_DB_HOST or Config.DB_HOST,
        port=int(Config.MIGRATION_DB_PORT or Config.DB_PORT),
        database=database,
        user=user,
        password=password,
    )
    return config
