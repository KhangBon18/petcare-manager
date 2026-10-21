"""Queue, authorize and inspect encrypted tenant data exports."""

import base64
import hashlib
import hmac
from secrets import token_hex

from cryptography.fernet import Fernet, MultiFernet
from flask import current_app

from petcare.database.connection import read_connection, transaction
from petcare.repositories import tenant_export_repo, user_repo
from petcare.secure_bundle import validate_passphrase
from petcare.services import request_throttle_service
from petcare.services.common import require_actor
from petcare.services.exceptions import ForbiddenError, NotFoundError, RateLimitError, ValidationError
from petcare.security import verify_password


def _fernet():
    key = str(current_app.config.get("TENANT_EXPORT_JOB_KEY", "")).strip()
    if not key:
        if current_app.config.get("APP_ENV") == "production":
            raise RuntimeError("TENANT_EXPORT_JOB_KEY must be configured in production.")
        secret = str(current_app.config.get("SECRET_KEY", "")).encode("utf-8")
        key = base64.urlsafe_b64encode(
            hashlib.sha256(b"petcare-tenant-export-job-v1\0" + secret).digest()
        ).decode("ascii")
    keys = [key, *current_app.config.get("TENANT_EXPORT_JOB_FALLBACK_KEYS", ())]
    try:
        return MultiFernet([Fernet(item.encode("ascii")) for item in keys])
    except (UnicodeEncodeError, ValueError, TypeError) as exc:
        raise RuntimeError("TENANT_EXPORT_JOB_KEY must be a valid Fernet key.") from exc


def enqueue_export(actor_id, current_password, passphrase, confirmation):
    """Create a durable job; the request never reads tenant data or writes an artifact."""
    allowed, retry_after = request_throttle_service.consume(actor_id, "tenant_export")
    if not allowed:
        raise RateLimitError(
            "Bạn đã yêu cầu nhiều bản xuất gần đây. Vui lòng thử lại sau.", retry_after
        )
    if not isinstance(passphrase, str) or not isinstance(confirmation, str):
        raise ValidationError("Nhập và xác nhận passphrase mã hóa.")
    if not hmac.compare_digest(passphrase, confirmation):
        raise ValidationError("Hai passphrase không khớp.")
    try:
        validate_passphrase(passphrase)
    except ValueError as exc:
        raise ValidationError(
            "Passphrase cần ít nhất 12 ký tự và không vượt quá 1024 byte."
        ) from exc

    encrypted_passphrase = _fernet().encrypt(passphrase.encode("utf-8"))
    with transaction() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        user = user_repo.get_by_id(connection, actor_id, actor["tenant_id"])
        if not user or not verify_password(current_password, user["password_hash"]):
            raise ForbiddenError("Mật khẩu hiện tại không đúng hoặc phiên không còn hợp lệ.")
        artifact_key = f"tenants/{actor['tenant_id']}/exports/{token_hex(16)}.pcarexport"
        job_id = tenant_export_repo.enqueue(
            connection, actor["tenant_id"], actor_id, artifact_key, encrypted_passphrase
        )
    return job_id


def get_export_job(actor_id, job_id, include_storage_key=False):
    """Return only the requesting admin's job in the currently selected tenant."""
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        job = tenant_export_repo.get_for_requester(
            connection, actor["tenant_id"], actor_id, job_id
        )
        if not job:
            raise NotFoundError("Không tìm thấy bản xuất.")
        if not include_storage_key:
            job.pop("artifact_key", None)
        return job


def list_export_jobs(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id, admin=True)
        return tenant_export_repo.list_for_requester(
            connection, actor["tenant_id"], actor_id, limit=10
        )


def get_downloadable_export(actor_id, job_id):
    job = get_export_job(actor_id, job_id, include_storage_key=True)
    if job["status"] != "ready" or job["expired"]:
        raise NotFoundError("Bản xuất chưa sẵn sàng hoặc đã hết hạn.")
    return job
