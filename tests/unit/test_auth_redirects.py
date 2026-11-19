import unittest
from unittest.mock import patch

from flask import Flask, g, session

from petcare import auth
from petcare.auth import _safe_next_url


class SafeRedirectTests(unittest.TestCase):
    def test_allows_local_paths_and_query_strings(self):
        self.assertTrue(_safe_next_url("/invoices/?status=unpaid"))
        self.assertTrue(_safe_next_url("/pets/12"))

    def test_rejects_external_or_ambiguous_targets(self):
        for target in (
            "https://example.com/",
            "//example.com/",
            "/\\example.com",
            "/dashboard\nLocation: https://example.com",
            "dashboard",
        ):
            with self.subTest(target=target):
                self.assertFalse(_safe_next_url(target))

    def test_authentication_builds_explicit_user_and_tenant_context(self):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/dashboard"):
            session["user_id"] = 12
            session["tenant_id"] = 31
            session["session_version"] = 4
            with patch.object(auth, "load_active_user", return_value={
                "id": 12,
                "tenant": {"id": 31, "name": "Shop"},
            }) as load_user:
                auth.load_current_user()
            self.assertEqual(g.actor_context.user_id, 12)
            self.assertEqual(g.actor_context.tenant_id, 31)
            load_user.assert_called_once_with(12, 31, 4)


if __name__ == "__main__":
    unittest.main()
