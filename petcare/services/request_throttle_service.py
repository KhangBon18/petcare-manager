"""Per-account rate limits for costly AI and image-analysis routes."""

import hashlib
import hmac

from flask import current_app

from petcare.database.connection import transaction
from petcare.repositories import request_throttle_repo


def consume(actor_id, scope):
    limit = _configured_limit(scope)
    key_hash = _key_hash(actor_id, scope)
    with transaction() as connection:
        result = request_throttle_repo.consume(connection, key_hash, scope, limit)
        if scope in {
            "password_reset", "password_reset_ip", "email_verification",
            "email_verification_ip", "tenant_invitation", "tenant_owner_transfer", "public_signup_email",
            "public_signup_ip",
        }:
            request_throttle_repo.prune_old(connection)
        return result


def consume_with_ip_limit(actor_id, remote_addr, scope):
    """Atomically apply a per-network and per-account quota for a costly route."""
    if scope not in {"assistant", "vision", "catalog_image_upload"}:
        raise ValueError("Network-scoped limits are not configured for this route.")
    ip_scope = f"{scope}_ip"
    ip_limit = _configured_limit(ip_scope)
    actor_limit = _configured_limit(scope)
    ip_key = _key_hash(remote_addr or "unknown", ip_scope)
    actor_key = _key_hash(actor_id, scope)
    with transaction() as connection:
        ip_allowed, retry_after = request_throttle_repo.consume(
            connection, ip_key, ip_scope, ip_limit
        )
        if not ip_allowed:
            return False, retry_after
        return request_throttle_repo.consume(connection, actor_key, scope, actor_limit)


def _configured_limit(scope):
    setting = {
        "assistant": "ASSISTANT_RATE_LIMIT_PER_MINUTE",
        "assistant_ip": "ASSISTANT_IP_RATE_LIMIT_PER_MINUTE",
        "vision": "VISION_RATE_LIMIT_PER_MINUTE",
        "vision_ip": "VISION_IP_RATE_LIMIT_PER_MINUTE",
        "catalog_image_upload": "CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE",
        "catalog_image_upload_ip": "CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE",
        "tenant_export": "TENANT_EXPORT_RATE_LIMIT_PER_MINUTE",
        "password_reset": "PASSWORD_RESET_RATE_LIMIT_PER_MINUTE",
        "password_reset_ip": "PASSWORD_RESET_IP_RATE_LIMIT_PER_MINUTE",
        "email_verification": "EMAIL_VERIFICATION_RATE_LIMIT_PER_MINUTE",
        "email_verification_ip": "EMAIL_VERIFICATION_IP_RATE_LIMIT_PER_MINUTE",
        "tenant_invitation": "TENANT_INVITATION_RATE_LIMIT_PER_MINUTE",
        "tenant_owner_transfer": "TENANT_OWNER_TRANSFER_RATE_LIMIT_PER_MINUTE",
        "public_signup_email": "PUBLIC_SIGNUP_EMAIL_RATE_LIMIT_PER_MINUTE",
        "public_signup_ip": "PUBLIC_SIGNUP_IP_RATE_LIMIT_PER_MINUTE",
    }.get(scope)
    if not setting:
        raise ValueError("Unknown request limit scope.")
    limit = int(current_app.config[setting])
    if not 1 <= limit <= 1000:
        raise ValueError("Request limit must be between 1 and 1000 requests per minute.")
    return limit


def _key_hash(identity, scope):
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    return hmac.new(
        secret, f"api:{scope}:{str(identity)[:254]}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
