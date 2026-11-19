"""Bearer-protected Prometheus scrape endpoint with aggregate data only."""

import hmac

import mysql.connector
from flask import Blueprint, Response, current_app, request

from petcare.database.connection import read_connection
from petcare.services.ops_metrics_service import collect_prometheus_payload
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
            payload = collect_prometheus_payload(connection, WORKER_HEARTBEAT_STALE_SECONDS)
    except mysql.connector.Error as error:
        current_app.logger.warning(
            "Metrics scrape failed (errno=%s)", getattr(error, "errno", None)
        )
        return Response(status=503, headers={"Cache-Control": "no-store"})

    response = Response(
        payload,
        status=200,
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
