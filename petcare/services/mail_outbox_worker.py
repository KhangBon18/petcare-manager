"""Claim, decrypt and deliver queued mail with bounded retries."""

import json
import time

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from petcare.database.connection import transaction
from petcare.repositories import (
    mail_outbox_repo,
    request_throttle_repo,
    worker_heartbeat_repo,
)
from petcare.services.mail_service import MailDeliveryError, send_text_email
from petcare.services.tenant_signup_cleanup import cleanup_expired_public_signups
from petcare.services.worker_heartbeat import WorkerHeartbeat


MAX_ATTEMPTS = 8


def _claim(message_id=None):
    with transaction() as connection:
        return mail_outbox_repo.claim_one(connection, message_id=message_id)


def _decrypt(payload_ciphertext):
    key = current_app.config.get("MAIL_OUTBOX_KEY", "")
    if not key:
        raise MailDeliveryError("Email outbox encryption is not configured.")
    try:
        payload = Fernet(key.encode("ascii")).decrypt(bytes(payload_ciphertext))
        message = json.loads(payload.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise MailDeliveryError("Queued message could not be decrypted.") from exc
    if not isinstance(message, dict):
        raise MailDeliveryError("Queued message is malformed.")
    return message


def _pulse_worker(heartbeat, app, error_code=None, force=False):
    if heartbeat is None:
        return
    try:
        heartbeat.pulse(error_code=error_code, force=force)
    except Exception:
        app.logger.warning("Email outbox worker heartbeat could not be updated")


def dispatch_one(message_id=None, heartbeat=None):
    """Deliver one due message; return False when the queue has no due work."""
    job = _claim(message_id)
    if not job:
        _pulse_worker(heartbeat, current_app._get_current_object() if heartbeat else None)
        return False
    message_id = job["id"]
    attempt = job["attempt_count"]
    try:
        message = _decrypt(job["payload_ciphertext"])
        send_text_email(message["recipient"], message["subject"], message["body"])
    except Exception as exc:
        delay = min(3600, 15 * (2 ** min(attempt - 1, 8)))
        error_code = "payload_invalid" if isinstance(exc, (InvalidToken, ValueError, TypeError)) else "delivery_failed"
        with transaction() as connection:
            mail_outbox_repo.mark_failed(
                connection, message_id, attempt, delay, error_code, MAX_ATTEMPTS
            )
        current_app.logger.warning(
            "Email outbox delivery attempt failed (message_id=%s, attempt=%s)",
            message_id,
            attempt,
        )
        _pulse_worker(heartbeat, current_app._get_current_object() if heartbeat else None)
        return True

    with transaction() as connection:
        mail_outbox_repo.mark_sent(connection, message_id)
    _pulse_worker(heartbeat, current_app._get_current_object() if heartbeat else None)
    return True


def dispatch_batch(limit=25, heartbeat=None):
    delivered_or_retried = 0
    for _ in range(max(1, min(int(limit), 250))):
        if not dispatch_one(heartbeat=heartbeat):
            break
        delivered_or_retried += 1
    return delivered_or_retried


def run_maintenance():
    """Prune expired mail, quota, worker and unverified-signup records."""
    with transaction() as connection:
        mail_outbox_repo.prune_delivered(connection)
        request_throttle_repo.prune_old(connection)
        worker_heartbeat_repo.prune_stale(connection)
        cleanup_expired_public_signups(connection)


def run_worker(poll_seconds=5):
    poll_seconds = max(1, min(int(poll_seconds), 60))
    app = current_app._get_current_object()
    heartbeat = WorkerHeartbeat("email")
    _pulse_worker(heartbeat, app, force=True)
    next_maintenance = time.monotonic()
    dispatch_backoff = poll_seconds
    while True:
        try:
            dispatch_batch(heartbeat=heartbeat)
            dispatch_backoff = poll_seconds
        except Exception:
            _pulse_worker(heartbeat, app, error_code="worker_error", force=True)
            app.logger.warning(
                "Email outbox dispatch is temporarily unavailable; retrying in %s seconds",
                dispatch_backoff,
            )
            time.sleep(dispatch_backoff)
            dispatch_backoff = min(60, dispatch_backoff * 2)
            continue

        now = time.monotonic()
        if now >= next_maintenance:
            try:
                with app.app_context():
                    run_maintenance()
                _pulse_worker(heartbeat, app)
                next_maintenance = now + 3600
            except Exception:
                _pulse_worker(heartbeat, app, error_code="maintenance_failed", force=True)
                app.logger.warning(
                    "Email outbox maintenance failed; retrying in 60 seconds"
                )
                next_maintenance = now + 60
        time.sleep(poll_seconds)
