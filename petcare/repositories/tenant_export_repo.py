"""Durable queue operations for encrypted tenant data exports."""

from secrets import token_hex

from petcare.repositories.base import execute, fetch_one

MAX_ATTEMPTS = 4


def enqueue(connection, tenant_id, requester_id, artifact_key, passphrase_ciphertext):
    return execute(
        connection,
        "INSERT INTO tenant_export_jobs "
        "(tenant_id, requested_by, artifact_key, passphrase_ciphertext) "
        "VALUES (%s, %s, %s, %s)",
        (tenant_id, requester_id, artifact_key, passphrase_ciphertext),
    )[0]


def claim_one(connection, lease_seconds=300, job_id=None):
    sql = (
        "SELECT j.id, j.tenant_id, j.requested_by, j.artifact_key, "
        "j.passphrase_ciphertext, j.attempt_count, t.slug tenant_slug "
        "FROM tenant_export_jobs j JOIN tenants t ON t.id = j.tenant_id "
        "JOIN tenant_users tu ON tu.tenant_id = j.tenant_id AND tu.user_id = j.requested_by "
        "JOIN users u ON u.id = j.requested_by "
        "WHERE j.status IN ('pending', 'processing') "
        "AND j.attempt_count < %s AND j.next_attempt_at <= CURRENT_TIMESTAMP "
        "AND (j.locked_until IS NULL OR j.locked_until < CURRENT_TIMESTAMP) "
        "AND t.status = 'active' AND tu.active = 1 AND tu.role IN ('owner', 'admin') AND u.active = 1 "
    )
    params = [MAX_ATTEMPTS]
    if job_id is not None:
        sql += "AND j.id = %s "
        params.append(job_id)
    sql += "ORDER BY j.next_attempt_at, j.id LIMIT 1 FOR UPDATE SKIP LOCKED"
    row = fetch_one(connection, sql, tuple(params))
    if not row:
        return None
    previous_key = row["artifact_key"]
    # A new immutable artifact key prevents an expired worker lease from
    # overwriting the result of the worker that reclaimed the job.
    artifact_key = f"tenants/{row['tenant_id']}/exports/{token_hex(16)}.pcarexport"
    attempt = int(row["attempt_count"]) + 1
    execute(
        connection,
        "UPDATE tenant_export_jobs SET status = 'processing', attempt_count = %s, "
        "started_at = COALESCE(started_at, CURRENT_TIMESTAMP), locked_until = "
        "DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND), artifact_key = %s "
        "WHERE id = %s",
        (attempt, lease_seconds, artifact_key, row["id"]),
    )
    return {**row, "attempt_count": attempt, "previous_artifact_key": previous_key, "artifact_key": artifact_key}


def renew_lease(connection, job_id, artifact_key, lease_seconds=300):
    return execute(
        connection,
        "UPDATE tenant_export_jobs SET locked_until = "
        "DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND) "
        "WHERE id = %s AND status = 'processing' AND artifact_key = %s",
        (lease_seconds, job_id, artifact_key),
    )[1] == 1


def mark_ready(connection, job, result_json, artifact_size, retention_hours):
    return execute(
        connection,
        "UPDATE tenant_export_jobs SET status = 'ready', passphrase_ciphertext = NULL, "
        "locked_until = NULL, last_error_code = NULL, result_json = %s, artifact_size = %s, "
        "completed_at = CURRENT_TIMESTAMP, expires_at = "
        "DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s HOUR) "
        "WHERE id = %s AND status = 'processing' AND artifact_key = %s",
        (result_json, artifact_size, retention_hours, job["id"], job["artifact_key"]),
    )[1] == 1


def mark_failed(connection, job, error_code, retry_delay_seconds, retryable=True):
    terminal = not retryable or int(job["attempt_count"]) >= MAX_ATTEMPTS
    status = "failed" if terminal else "pending"
    expiry = (
        "expires_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 30 DAY), "
        if terminal else "expires_at = NULL, "
    )
    return execute(
        connection,
        "UPDATE tenant_export_jobs SET status = %s, "
        "passphrase_ciphertext = IF(%s = 'failed', NULL, passphrase_ciphertext), "
        "locked_until = NULL, last_error_code = %s, "
        "next_attempt_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND), "
        + expiry
        + "completed_at = IF(%s = 'failed', CURRENT_TIMESTAMP, NULL) "
        "WHERE id = %s AND status = 'processing' AND artifact_key = %s",
        (status, status, error_code[:64], retry_delay_seconds, status, job["id"], job["artifact_key"]),
    )[1] == 1


def get_for_requester(connection, tenant_id, requester_id, job_id):
    return fetch_one(
        connection,
        "SELECT id, tenant_id, requested_by, artifact_key, status, attempt_count, "
        "last_error_code, result_json, artifact_size, created_at, completed_at, expires_at, "
        "(expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP) expired "
        "FROM tenant_export_jobs WHERE id = %s AND tenant_id = %s AND requested_by = %s",
        (job_id, tenant_id, requester_id),
    )


def list_for_requester(connection, tenant_id, requester_id, limit=10):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, status, attempt_count, created_at, completed_at, expires_at, "
            "(expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP) expired "
            "FROM tenant_export_jobs WHERE tenant_id = %s AND requested_by = %s "
            "ORDER BY id DESC LIMIT %s",
            (tenant_id, requester_id, limit),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def expired_artifacts(connection, limit=100):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, artifact_key FROM tenant_export_jobs WHERE expires_at IS NOT NULL "
            "AND expires_at <= CURRENT_TIMESTAMP ORDER BY expires_at, id LIMIT %s",
            (limit,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def delete_expired(connection, job_ids):
    if not job_ids:
        return 0
    marks = ",".join(["%s"] * len(job_ids))
    return execute(
        connection,
        "DELETE FROM tenant_export_jobs WHERE id IN (" + marks + ") "
        "AND expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP",
        tuple(job_ids),
    )[1]


def fail_stale_jobs(connection):
    return execute(
        connection,
        "UPDATE tenant_export_jobs j LEFT JOIN tenants t ON t.id = j.tenant_id "
        "LEFT JOIN tenant_users tu ON tu.tenant_id = j.tenant_id AND tu.user_id = j.requested_by "
        "LEFT JOIN users u ON u.id = j.requested_by "
        "SET j.status = 'failed', j.passphrase_ciphertext = NULL, j.locked_until = NULL, "
        "j.last_error_code = CASE WHEN t.status <> 'active' OR tu.active <> 1 "
        "OR tu.role NOT IN ('owner', 'admin') OR u.active <> 1 OR tu.user_id IS NULL "
        "THEN 'requester_access_revoked' ELSE 'export_job_expired' END, "
        "j.completed_at = CURRENT_TIMESTAMP, "
        "j.expires_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 30 DAY) "
        "WHERE j.status IN ('pending', 'processing') "
        "AND (j.status = 'pending' OR j.locked_until IS NULL OR j.locked_until < CURRENT_TIMESTAMP) "
        "AND (t.status <> 'active' OR tu.active <> 1 "
        "OR tu.role NOT IN ('owner', 'admin') OR u.active <> 1 OR tu.user_id IS NULL "
        "OR j.created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 DAY) "
        "OR j.attempt_count >= 4)",
    )[1]
