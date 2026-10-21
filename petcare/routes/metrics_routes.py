"""Bearer-protected Prometheus scrape endpoint with aggregate data only."""

import hmac

import mysql.connector
from flask import Blueprint, Response, current_app, request

from petcare.database.connection import read_connection
from petcare.repositories.ops_metrics_repo import (
    EMAIL_STATUSES,
    EXPORT_STATUSES,
    WORKERS,
    collect,
)
from petcare.services.worker_heartbeat import WORKER_HEARTBEAT_STALE_SECONDS


bp = Blueprint("metrics", __name__)


def _authorized(expected_token):
    header = request.headers.get("Authorization", "")
    scheme, separator, supplied = header.partition(" ")
    if not separator or scheme.lower() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(
        supplied.encode("utf-8"), expected_token.encode("utf-8")
    )


def _prometheus_payload(metrics):
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


@bp.get("/metrics")
def scrape_metrics():
    expected_token = str(current_app.config.get("OPS_METRICS_TOKEN", "") or "")
    if not expected_token:
        return Response(status=404, headers={"Cache-Control": "no-store"})
    if not _authorized(expected_token):
        return Response(
            status=401,
            headers={
                "WWW-Authenticate": 'Bearer realm="petcare-metrics"',
                "Cache-Control": "no-store",
            },
        )

    try:
        with read_connection() as connection:
            metrics = collect(connection, WORKER_HEARTBEAT_STALE_SECONDS)
    except mysql.connector.Error as error:
        current_app.logger.warning(
            "Metrics scrape failed (errno=%s)", getattr(error, "errno", None)
        )
        return Response(status=503, headers={"Cache-Control": "no-store"})

    response = Response(
        _prometheus_payload(metrics),
        status=200,
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
