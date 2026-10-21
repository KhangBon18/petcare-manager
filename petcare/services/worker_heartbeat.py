"""Rate-limited, privacy-minimal liveness signals for background workers."""

import time
from uuid import uuid4

from petcare.database.connection import transaction
from petcare.repositories import worker_heartbeat_repo


HEARTBEAT_INTERVAL_SECONDS = 15
WORKER_HEARTBEAT_STALE_SECONDS = 90
REQUIRED_WORKERS = frozenset({"email", "tenant_export"})
ALLOWED_ERROR_CODES = frozenset({"worker_error", "maintenance_failed"})


class WorkerHeartbeat:
    def __init__(self, worker_name, instance_id=None):
        if worker_name not in REQUIRED_WORKERS:
            raise ValueError("Unknown worker name.")
        self.worker_name = worker_name
        self.instance_id = instance_id or uuid4().hex
        self._last_write = 0.0
        self._last_error_code = None

    def pulse(self, *, error_code=None, force=False):
        if error_code is not None and error_code not in ALLOWED_ERROR_CODES:
            raise ValueError("Unknown worker error code.")
        now = time.monotonic()
        force = force or error_code is not None or self._last_error_code is not None
        if not force and now - self._last_write < HEARTBEAT_INTERVAL_SECONDS:
            return False
        with transaction() as connection:
            worker_heartbeat_repo.touch(
                connection, self.worker_name, self.instance_id, error_code
            )
        self._last_write = now
        self._last_error_code = error_code
        return True
