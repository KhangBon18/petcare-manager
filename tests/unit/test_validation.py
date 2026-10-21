import unittest
from datetime import date

from petcare.security import verify_password
from petcare.services.account_security_service import reset_password
from petcare.services.common import (
    date_value, integer_value, page_window, password_hash_value, phone_value,
    text_value, username_value,
)
from petcare.services.exceptions import ValidationError


class ValidationTests(unittest.TestCase):
    def test_integer_rejects_fractional_and_out_of_range_values(self):
        self.assertEqual(integer_value("12", "Số lượng", 1), 12)
        for value in ("1.5", "-1", "abc"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                integer_value(value, "Số lượng", 1)

    def test_phone_accepts_local_format_and_rejects_bad_length(self):
        self.assertEqual(phone_value("+84 901 234 567"), "+84 901 234 567")
        with self.assertRaises(ValidationError):
            phone_value("123")

    def test_text_is_trimmed_and_limited(self):
        self.assertEqual(text_value(" Lan ", "Tên", 10), "Lan")
        with self.assertRaises(ValidationError):
            text_value("long name", "Tên", 3)

    def test_username_uses_shared_account_policy(self):
        self.assertEqual(username_value("  lan.nguyen_2  "), "lan.nguyen_2")
        for value in ("ab", "lan nguyen", "tên", "x" * 81):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                username_value(value)

    def test_password_hash_policy_returns_safe_validation_errors(self):
        encoded = password_hash_value("correct-horse")
        self.assertTrue(verify_password("correct-horse", encoded))
        for value in ("short", "x" * 1025, None):
            with self.subTest(length=len(value) if isinstance(value, str) else value), self.assertRaises(ValidationError):
                password_hash_value(value)

    def test_password_reset_rejects_weak_password_before_database_access(self):
        with self.assertRaises(ValidationError):
            reset_password("A" * 43, "short", "short")

    def test_date_requires_iso_calendar_date(self):
        self.assertEqual(date_value("2026-10-17"), date(2026, 10, 17))
        for value in ("2026-02-30", "17/10/2026"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                date_value(value)

    def test_empty_optional_date(self):
        self.assertIsNone(date_value("", allow_empty=True))

    def test_page_window_bounds_invalid_and_out_of_range_pages(self):
        page, offset, metadata = page_window("9999999", 52)
        self.assertEqual((page, offset), (3, 50))
        self.assertEqual((metadata["first"], metadata["last"], metadata["pages"]), (51, 52, 3))

        page, offset, metadata = page_window("-5", 0)
        self.assertEqual((page, offset), (1, 0))
        self.assertEqual((metadata["first"], metadata["last"], metadata["pages"]), (0, 0, 1))


if __name__ == "__main__":
    unittest.main()
