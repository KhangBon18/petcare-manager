"""Process encrypted tenant exports outside web request workers."""

import json
import os
from pathlib import Path
import tempfile
from threading import Event, Thread
import time

from cryptography.fernet import InvalidToken
from flask import current_app

from petcare.database.connection import transaction
from petcare.database.export_tenant import export_tenant
from petcare.repositories import audit_repo, tenant_export_repo
from petcare.services.tenant_export_service import _fernet
from petcare.services.tenant_export_storage import get_export_storage
from petcare.services.worker_heartbeat import WorkerHeartbeat

LEASE_SECONDS = 300
HEARTBEAT_SECONDS = 45


def _claim(job_id=None):
    with transaction() as connection:
        return tenant_export_repo.claim_one(connection, LEASE_SECONDS, job_id)


def _pulse_worker(heartbeat, app, error_code=None, force=False):
    if heartbeat is None:
        return
    try:
        with app.app_context():
            heartbeat.pulse(error_code=error_code, force=force)
    except Exception:
        app.logger.warning("Tenant export worker heartbeat could not be updated")


def _renew_until_stopped(app, job, stop_event, lost_lease, worker_heartbeat=None):
    while not stop_event.wait(HEARTBEAT_SECONDS):
        try:
            with app.app_context(), transaction() as connection:
                still_owner = tenant_export_repo.renew_lease(
                    connection, job["id"], job["artifact_key"], LEASE_SECONDS
                )
            if not still_owner:
                lost_lease.set()
                return
            _pulse_worker(worker_heartbeat, app, force=True)
        except Exception:
            app.logger.warning("Tenant export lease renewal failed (job_id=%s)", job["id"])


def _membership_is_active_admin(connection, job):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM tenant_export_jobs j JOIN tenants t ON t.id = j.tenant_id "
            "JOIN tenant_users tu ON tu.tenant_id = j.tenant_id AND tu.user_id = j.requested_by "
            "JOIN users u ON u.id = j.requested_by "
            "WHERE j.id = %s AND j.tenant_id = %s AND j.requested_by = %s "
            "AND j.status = 'processing' AND j.artifact_key = %s "
            "AND t.status = 'active' AND tu.active = 1 "
            "AND tu.role IN ('owner', 'admin') AND u.active = 1",
            (job["id"], job["tenant_id"], job["requested_by"], job["artifact_key"]),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _complete(job, result, artifact_size):
    payload = json.dumps(
        {"format": "petcare-tenant-export-v1", "tables": result["tables"],
         "media_files": result["media_files"]},
        ensure_ascii=False, separators=(",", ":"),
    )
    with transaction() as connection:
        if not _membership_is_active_admin(connection, job):
            tenant_export_repo.mark_failed(
                connection, job, "requester_access_revoked", 0, retryable=False
            )
            return False
        updated = tenant_export_repo.mark_ready(
            connection,
            job,
            payload,
            artifact_size,
            int(current_app.config["TENANT_EXPORT_RETENTION_HOURS"]),
        )
        if not updated:
            return False
        cursor = connection.cursor()
        try:
            cursor.execute("SET @petcare_tenant_id = %s", (job["tenant_id"],))
        finally:
            cursor.close()
        audit_repo.add_event(
            connection,
            job["requested_by"],
            "tenant.exported",
            "tenant",
            job["tenant_id"],
            "Tạo bản xuất dữ liệu mã hóa cho cửa hàng",
            {"format": "petcare-tenant-export-v1", "tables": result["tables"],
             "media_files": result["media_files"]},
        )
    return True


class _InvalidExportSecret(Exception):
    pass


def _process_claimed(job, storage, worker_heartbeat=None):
    app = current_app._get_current_object()
    stop_event = Event()
    lost_lease = Event()
    heartbeat = Thread(
        target=_renew_until_stopped,
        args=(app, job, stop_event, lost_lease, worker_heartbeat),
        name=f"tenant-export-lease-{job['id']}",
        daemon=True,
    )
    heartbeat.start()
    artifact_written = False
    try:
        if job.get("previous_artifact_key"):
            storage.delete(job["previous_artifact_key"])
        try:
            passphrase = _fernet().decrypt(bytes(job["passphrase_ciphertext"])).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
            raise _InvalidExportSecret from exc

        export_root = Path(app.config["TENANT_EXPORT_DIR"])
        export_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            export_root.chmod(0o700)
        with tempfile.TemporaryDirectory(prefix=f"job-{job['id']}-", dir=export_root) as temp_dir:
            os.chmod(temp_dir, 0o700)
            output = Path(temp_dir) / "tenant.pcarexport"
            result = export_tenant(job["tenant_slug"], output, passphrase)
            if lost_lease.is_set():
                return True
            artifact_size = storage.put(job["artifact_key"], output)
            artifact_written = True
            published = _complete(job, result, artifact_size)
        if not published and artifact_written:
            storage.delete(job["artifact_key"])
        return True
    except Exception as exc:
        if artifact_written:
            try:
                storage.delete(job["artifact_key"])
            except Exception:
                app.logger.warning("Could not remove failed export artifact (job_id=%s)", job["id"])
        retryable = not isinstance(exc, _InvalidExportSecret)
        delay = min(3600, 30 * (2 ** min(int(job["attempt_count"]) - 1, 7)))
        try:
            with transaction() as connection:
                tenant_export_repo.mark_failed(
                    connection,
                    job,
                    "passphrase_unavailable" if not retryable else "export_generation_failed",
                    delay,
                    retryable=retryable,
                )
        except Exception:
            app.logger.exception("Could not record tenant export failure (job_id=%s)", job["id"])
        app.logger.warning(
            "Tenant export attempt failed (job_id=%s, attempt=%s, error_type=%s)",
            job["id"], job["attempt_count"], type(exc).__name__,
        )
        return True
    finally:
        stop_event.set()
        heartbeat.join(timeout=1)


def process_one(job_id=None, worker_heartbeat=None):
    """Claim and process one due export. Returns False when no job is due."""
    job = _claim(job_id)
    if not job:
        _pulse_worker(
            worker_heartbeat,
            current_app._get_current_object() if worker_heartbeat else None,
        )
        return False
    storage = get_export_storage(current_app.config)
    processed = _process_claimed(job, storage, worker_heartbeat)
    _pulse_worker(worker_heartbeat, current_app._get_current_object())
    return processed


def cleanup_expired(limit=100):
    storage = get_export_storage(current_app.config)
    with transaction() as connection:
        rows = tenant_export_repo.expired_artifacts(connection, limit)
    deleted_ids = []
    for row in rows:
        storage.delete(row["artifact_key"])
        deleted_ids.append(row["id"])
    if deleted_ids:
        with transaction() as connection:
            tenant_export_repo.delete_expired(connection, deleted_ids)
    return len(deleted_ids)


def maintenance():
    with transaction() as connection:
        tenant_export_repo.fail_stale_jobs(connection)
    return cleanup_expired()


def dispatch_batch(limit=10, worker_heartbeat=None):
    processed = 0
    for _ in range(max(1, min(int(limit), 100))):
        if not process_one(worker_heartbeat=worker_heartbeat):
            break
        processed += 1
    return processed


def run_worker(poll_seconds=3):
    poll_seconds = max(1, min(int(poll_seconds), 60))
    app = current_app._get_current_object()
    worker_heartbeat = WorkerHeartbeat("tenant_export")
    _pulse_worker(worker_heartbeat, app, force=True)
    next_maintenance = 0.0
    backoff = poll_seconds
    while True:
        try:
            processed = dispatch_batch(worker_heartbeat=worker_heartbeat)
            backoff = poll_seconds
            if processed == 0:
                time.sleep(poll_seconds)
        except Exception:
            _pulse_worker(
                worker_heartbeat, app, error_code="worker_error", force=True
            )
            app.logger.exception(
                "Tenant export worker temporarily failed; retrying in %s seconds", backoff
            )
            time.sleep(backoff)
            backoff = min(60, backoff * 2)
            continue
        if time.monotonic() >= next_maintenance:
            try:
                maintenance()
                _pulse_worker(worker_heartbeat, app)
                next_maintenance = time.monotonic() + 300
            except Exception:
                _pulse_worker(
                    worker_heartbeat, app, error_code="maintenance_failed", force=True
                )
                app.logger.exception("Tenant export maintenance failed")
                next_maintenance = time.monotonic() + 60
