"""Privacy-minimal aggregate metrics for protected operations scraping."""

from petcare.repositories.base import fetch_all, fetch_one


EMAIL_STATUSES = ("pending", "processing", "failed")
EXPORT_STATUSES = ("pending", "processing", "ready", "failed")
WORKERS = ("email", "tenant_export")


def collect(connection, stale_after_seconds):
    email_jobs = fetch_all(
        connection,
        "SELECT status, COUNT(*) total FROM email_outbox "
        "WHERE status IN ('pending', 'processing', 'failed') GROUP BY status",
    )
    export_jobs = fetch_all(
        connection,
        "SELECT status, COUNT(*) total FROM tenant_export_jobs "
        "WHERE status IN ('pending', 'processing', 'ready', 'failed') GROUP BY status",
    )
    oldest_email = fetch_one(
        connection,
        "SELECT COALESCE(MAX(TIMESTAMPDIFF(SECOND, created_at, UTC_TIMESTAMP())), 0) age "
        "FROM email_outbox WHERE status = 'pending'",
    )["age"]
    oldest_export = fetch_one(
        connection,
        "SELECT COALESCE(MAX(TIMESTAMPDIFF(SECOND, created_at, UTC_TIMESTAMP())), 0) age "
        "FROM tenant_export_jobs WHERE status = 'pending'",
    )["age"]
    healthy = fetch_all(
        connection,
        "SELECT DISTINCT worker_name FROM worker_heartbeats "
        "WHERE worker_name IN ('email', 'tenant_export') "
        "AND last_seen_at >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND) "
        "AND last_error_code IS NULL",
        (int(stale_after_seconds),),
    )
    return {
        "email_jobs": {row["status"]: int(row["total"]) for row in email_jobs},
        "export_jobs": {row["status"]: int(row["total"]) for row in export_jobs},
        "oldest_email_pending_seconds": max(0, int(oldest_email or 0)),
        "oldest_export_pending_seconds": max(0, int(oldest_export or 0)),
        "healthy_workers": {row["worker_name"] for row in healthy},
    }
