"""Database operations for process liveness signals."""

from petcare.repositories.base import execute, fetch_all


def touch(connection, worker_name, instance_id, error_code=None):
    execute(
        connection,
        "INSERT INTO worker_heartbeats "
        "(worker_name, instance_id, started_at, last_seen_at, last_success_at, last_error_code) "
        "VALUES (%s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), "
        "IF(%s IS NULL, UTC_TIMESTAMP(), NULL), %s) "
        "ON DUPLICATE KEY UPDATE last_seen_at = UTC_TIMESTAMP(), "
        "last_success_at = IF(%s IS NULL, UTC_TIMESTAMP(), last_success_at), "
        "last_error_code = %s",
        (worker_name, instance_id, error_code, error_code, error_code, error_code),
    )


def healthy_worker_names(connection, stale_after_seconds):
    rows = fetch_all(
        connection,
        "SELECT DISTINCT worker_name FROM worker_heartbeats "
        "WHERE worker_name IN ('email', 'tenant_export') "
        "AND last_seen_at >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND) "
        "AND last_error_code IS NULL",
        (int(stale_after_seconds),),
    )
    return {row["worker_name"] for row in rows}


def prune_stale(connection, retention_days=30):
    """Bound heartbeat history while retaining a short operational trail."""
    return execute(
        connection,
        "DELETE FROM worker_heartbeats "
        "WHERE worker_name IN ('email', 'tenant_export') "
        "AND last_seen_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY)",
        (max(1, min(int(retention_days), 365)),),
    )[1]
