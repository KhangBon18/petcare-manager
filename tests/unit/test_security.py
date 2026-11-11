import secrets
import unittest

from petcare.security import hash_password, verify_password


class PasswordHashTests(unittest.TestCase):
    def test_hash_verifies_password_and_is_salted(self):
        password = secrets.token_urlsafe(24)
        first = hash_password(password)
        second = hash_password(password)
        self.assertNotEqual(first, password)
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password(password, first))
        self.assertFalse(verify_password("wrong", first))

    def test_rejects_short_password(self):
        with self.assertRaises(ValueError):
            hash_password("short")


if __name__ == "__main__":
    unittest.main()
