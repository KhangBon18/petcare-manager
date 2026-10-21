import unittest
from unittest.mock import patch

from petcare.services.tenant_signup_cleanup import cleanup_expired_public_signups


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.result = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.queries.append(normalized)
        self.rowcount = 0
        if normalized.startswith("SELECT email_verified_at FROM users"):
            self.result = (None,)
        elif normalized.startswith("SELECT tenant_id FROM tenant_users"):
            self.result = (42,)
        elif normalized.startswith("SELECT COUNT(*) FROM tenant_users WHERE tenant_id"):
            self.result = (1,)
        elif normalized.startswith("SELECT COUNT(*) FROM tenant_users WHERE user_id"):
            self.result = (0,)
        elif normalized.startswith("SELECT COUNT(*) FROM audit_events"):
            self.result = (0,)
        elif normalized.startswith("SELECT COUNT(*) FROM "):
            self.result = (0,)
        elif normalized.startswith("DELETE FROM tenant_users"):
            self.rowcount = 1
        elif normalized.startswith("DELETE FROM tenants"):
            self.rowcount = 1
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


class TenantSignupCleanupTests(unittest.TestCase):
    def test_cleanup_locks_account_before_membership(self):
        connection = FakeConnection()

        def candidates(_connection, sql, _params):
            self.assertNotIn("FOR UPDATE", sql)
            return [{"tenant_id": 42, "user_id": 7}]

        with patch(
            "petcare.services.tenant_signup_cleanup.fetch_all",
            side_effect=candidates,
        ):
            self.assertEqual(cleanup_expired_public_signups(connection), 1)

        queries = connection.cursor_instance.queries
        account_lock = next(
            index for index, sql in enumerate(queries)
            if sql.startswith("SELECT email_verified_at FROM users")
        )
        membership_lock = next(
            index for index, sql in enumerate(queries)
            if sql.startswith("SELECT tenant_id FROM tenant_users")
        )
        self.assertLess(account_lock, membership_lock)


if __name__ == "__main__":
    unittest.main()
