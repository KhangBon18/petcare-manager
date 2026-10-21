import unittest

from petcare.security import hash_password, verify_password


class PasswordHashTests(unittest.TestCase):
    def test_hash_verifies_password_and_is_salted(self):
        first = hash_password("Admin@123")
        second = hash_password("Admin@123")
        self.assertNotEqual(first, "Admin@123")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("Admin@123", first))
        self.assertFalse(verify_password("wrong", first))

    def test_rejects_short_password(self):
        with self.assertRaises(ValueError):
            hash_password("short")


if __name__ == "__main__":
    unittest.main()
