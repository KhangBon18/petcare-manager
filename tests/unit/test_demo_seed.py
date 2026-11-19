import secrets
import unittest
from unittest.mock import patch

from petcare.config import Config
from petcare.database import seed as seed_module


class DemoSeedSecurityTests(unittest.TestCase):
    def setUp(self):
        self.admin_password = secrets.token_urlsafe(24)
        self.staff_password = secrets.token_urlsafe(24)
        self.environ = {
            "APP_ENV": "test",
            "PETCARE_DEMO_MODE": "1",
            "PETCARE_DEMO_ADMIN_PASSWORD": self.admin_password,
            "PETCARE_DEMO_STAFF_PASSWORD": self.staff_password,
        }

    def test_seed_identities_have_no_password_defaults(self):
        self.assertEqual(
            seed_module.USERS,
            (
                ("admin", "Quản trị cửa hàng", "admin"),
                ("staff1", "Nhân viên cửa hàng", "staff"),
            ),
        )

    def test_explicit_test_mode_uses_external_distinct_passwords_and_keeps_roles(self):
        with patch.object(Config, "DB_NAME", "petcare_isolated_test"):
            records = seed_module._demo_user_records(self.environ)

        self.assertEqual(
            records,
            (
                ("admin", self.admin_password, "Quản trị cửa hàng", "admin"),
                ("staff1", self.staff_password, "Nhân viên cửa hàng", "staff"),
            ),
        )

    def test_requires_explicit_demo_mode(self):
        environment = {**self.environ, "PETCARE_DEMO_MODE": "0"}
        with patch.object(Config, "DB_NAME", "petcare_isolated_test"):
            with self.assertRaisesRegex(RuntimeError, "PETCARE_DEMO_MODE"):
                seed_module._demo_user_records(environment)

    def test_refuses_production_even_with_demo_flag_and_test_database_name(self):
        environment = {**self.environ, "APP_ENV": "production"}
        with patch.object(Config, "DB_NAME", "petcare_isolated_test"):
            with self.assertRaisesRegex(RuntimeError, "PETCARE_DEMO_MODE"):
                seed_module._demo_user_records(environment)

    def test_environment_and_database_suffix_must_match(self):
        with patch.object(Config, "DB_NAME", "petcare_isolated_dev"):
            with self.assertRaisesRegex(RuntimeError, "matching"):
                seed_module._demo_user_records(self.environ)

    def test_passwords_are_required_distinct_and_at_least_sixteen_characters(self):
        variants = (
            {**self.environ, "PETCARE_DEMO_ADMIN_PASSWORD": ""},
            {**self.environ, "PETCARE_DEMO_STAFF_PASSWORD": "short"},
            {**self.environ, "PETCARE_DEMO_STAFF_PASSWORD": self.admin_password},
        )
        with patch.object(Config, "DB_NAME", "petcare_isolated_test"):
            for environment in variants:
                with self.subTest(variant=list(environment)[-1]):
                    with self.assertRaises(RuntimeError):
                        seed_module._demo_user_records(environment)

    def test_invalid_configuration_fails_before_opening_a_database_transaction(self):
        with patch.object(Config, "DB_NAME", "petcare_shop_dev"), patch.dict(
            "os.environ", self.environ, clear=False
        ):
            with patch.object(seed_module, "transaction") as transaction:
                with self.assertRaises(RuntimeError):
                    seed_module.seed_database()
                transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
