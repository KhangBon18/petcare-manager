"""Ephemeral account credentials shared by isolated integration tests."""

import os
import secrets


# Test-only provisioning inputs are created at runtime so no reusable demo
# password is stored in source, fixtures, test logs, or documentation.
os.environ["APP_ENV"] = "test"
os.environ["PETCARE_DEMO_MODE"] = "1"
if not all(len(os.environ.get(key, "")) >= 16 for key in (
    "PETCARE_DEMO_ADMIN_PASSWORD", "PETCARE_DEMO_STAFF_PASSWORD"
)):
    os.environ["PETCARE_DEMO_ADMIN_PASSWORD"] = secrets.token_urlsafe(32)
    os.environ["PETCARE_DEMO_STAFF_PASSWORD"] = secrets.token_urlsafe(32)

DEMO_ADMIN_PASSWORD = os.environ["PETCARE_DEMO_ADMIN_PASSWORD"]
DEMO_STAFF_PASSWORD = os.environ["PETCARE_DEMO_STAFF_PASSWORD"]
CHANGED_TEST_PASSWORD = secrets.token_urlsafe(32)
