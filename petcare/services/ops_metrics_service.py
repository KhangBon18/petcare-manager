"""Build privacy-minimal Prometheus metrics for operational monitoring."""

from petcare.repositories.ops_metrics_repo import (
    EMAIL_STATUSES,
    EXPORT_STATUSES,
    WORKERS,
    collect,
)


def prometheus_payload(metrics):
    lines = [
        "# HELP petcare_queue_jobs Number of queue jobs by queue and status.",
        "# TYPE petcare_queue_jobs gauge",
    ]
    for queue, statuses in (
        ("email", EMAIL_STATUSES),
        ("tenant_export", EXPORT_STATUSES),
    ):
        values = metrics["email_jobs"] if queue == "email" else metrics["export_jobs"]
        for status in statuses:
            lines.append(
                f'petcare_queue_jobs{{queue="{queue}",status="{status}"}} '
                f'{values.get(status, 0)}'
            )

    lines.extend((
        "# HELP petcare_queue_oldest_pending_seconds Age of the oldest pending queue job.",
        "# TYPE petcare_queue_oldest_pending_seconds gauge",
        'petcare_queue_oldest_pending_seconds{queue="email"} '
        f'{metrics["oldest_email_pending_seconds"]}',
        'petcare_queue_oldest_pending_seconds{queue="tenant_export"} '
        f'{metrics["oldest_export_pending_seconds"]}',
        "# HELP petcare_worker_up Whether a worker has a fresh successful heartbeat.",
        "# TYPE petcare_worker_up gauge",
    ))
    for worker in WORKERS:
        value = 1 if worker in metrics["healthy_workers"] else 0
        lines.append(f'petcare_worker_up{{worker="{worker}"}} {value}')
    return "\n".join(lines) + "\n"


def collect_prometheus_payload(connection, stale_after_seconds):
    """Read aggregate operational state and serialize it for a Prometheus scrape."""
    metrics = collect(connection, stale_after_seconds)
    return prometheus_payload(metrics)
