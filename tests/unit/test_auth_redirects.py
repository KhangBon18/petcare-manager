import unittest

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


if __name__ == "__main__":
    unittest.main()
