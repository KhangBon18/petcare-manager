"""Unauthenticated probes for local and container orchestration."""

import hashlib
import hmac
import json

import mysql.connector
from flask import Blueprint, current_app, jsonify, request

from petcare.database.connection import read_connection
from petcare.database.readiness import (
    REQUIRED_COLUMNS,
    REQUIRED_GLOBAL_FOREIGN_KEYS,
    REQUIRED_TENANT_FOREIGN_KEYS,
    schema_contract_is_ready,
)
from petcare.repositories.worker_heartbeat_repo import healthy_worker_names
from petcare.services.worker_heartbeat import (
    REQUIRED_WORKERS,
    WORKER_HEARTBEAT_STALE_SECONDS,
)

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


def demo_database_signature(settings):
    """Local-only proof that the web process and preflight share DB/config."""
    value = settings.get if hasattr(settings, "get") else lambda name: getattr(settings, name)
    identity = json.dumps([str(value(name)) for name in ("DB_HOST", "DB_PORT", "DB_NAME")], separators=(",", ":"))
    return hmac.new(str(value("SECRET_KEY")).encode(), identity.encode(), hashlib.sha256).hexdigest()


@bp.get("/readyz")
def readyz():
    try:
        with read_connection() as connection:
            cursor = connection.cursor()
            try:
                ready = schema_contract_is_ready(cursor)
            finally:
                cursor.close()
    except mysql.connector.Error as error:
        current_app.logger.warning(
            "Readiness check failed (errno=%s)", getattr(error, "errno", None)
        )
        return jsonify(status="unavailable"), 503
    if not ready:
        current_app.logger.warning("Readiness check failed (required schema is incomplete)")
        return jsonify(status="unavailable"), 503
    response = jsonify(status="ready")
    if (current_app.config["APP_ENV"] != "production"
            and current_app.config["DB_NAME"].endswith(("_dev", "_test"))
            and request.remote_addr in {"127.0.0.1", "::1"}):
        response.headers["X-PetCare-Demo-Database"] = demo_database_signature(current_app.config)
    return response, 200


@bp.get("/workersz")
def workersz():
    """Report whether each required background worker has a fresh heartbeat."""
    try:
        with read_connection() as connection:
            healthy = healthy_worker_names(connection, WORKER_HEARTBEAT_STALE_SECONDS)
    except mysql.connector.Error as error:
        current_app.logger.warning(
            "Worker health check failed (errno=%s)", getattr(error, "errno", None)
        )
        return jsonify(status="unavailable"), 503
    if not REQUIRED_WORKERS.issubset(healthy):
        return jsonify(status="unavailable"), 503
    return jsonify(status="ready"), 200
