import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from petcare.config import Config, migration_mysql_config, mysql_config
from petcare.database.connection import get_migration_connection


class MigrationDatabaseConfigTests(unittest.TestCase):
    def _base_settings(self, **overrides):
        settings = {
            "APP_ENV": "test",
            "DB_HOST": "runtime-db.internal",
            "DB_PORT": 3306,
            "DB_NAME": "petcare_test",
            "DB_USER": "petcare_runtime",
            "DB_PASSWORD": "runtime-password",
            "DB_SSL_CA": "",
            "MIGRATION_DB_HOST": "",
            "MIGRATION_DB_PORT": "",
            "MIGRATION_DB_NAME": "",
            "MIGRATION_DB_USER": "",
            "MIGRATION_DB_PASSWORD": "",
        }
        settings.update(overrides)
        return settings

    def test_nonproduction_without_migration_credentials_uses_runtime_config(self):
        with patch.multiple(Config, **self._base_settings()):
            self.assertEqual(migration_mysql_config(), mysql_config())

    def test_production_requires_a_separate_migration_account(self):
        with patch.multiple(Config, **self._base_settings(APP_ENV="production")):
            with self.assertRaisesRegex(RuntimeError, "dedicated migration"):
                migration_mysql_config()

    def test_migration_account_must_be_complete_distinct_and_same_database(self):
        cases = (
            (
                self._base_settings(
                    MIGRATION_DB_USER="petcare_migrator",
                    MIGRATION_DB_PASSWORD="",
                ),
                "must be set together",
            ),
            (
                self._base_settings(
                    MIGRATION_DB_USER="petcare_runtime",
                    MIGRATION_DB_PASSWORD="migration-password",
                ),
                "must differ",
            ),
            (
                self._base_settings(
                    MIGRATION_DB_NAME="another_database",
                    MIGRATION_DB_USER="petcare_migrator",
                    MIGRATION_DB_PASSWORD="migration-password",
                ),
                "same database",
            ),
        )
        for settings, message in cases:
            with self.subTest(message=message), patch.multiple(Config, **settings):
                with self.assertRaisesRegex(RuntimeError, message):
                    migration_mysql_config()

    def test_migration_config_selects_separate_host_user_and_password(self):
        settings = self._base_settings(
            MIGRATION_DB_HOST="primary-db.internal",
            MIGRATION_DB_PORT="3307",
            MIGRATION_DB_NAME="petcare_test",
            MIGRATION_DB_USER="petcare_migrator",
            MIGRATION_DB_PASSWORD="migration-password",
        )
        with patch.multiple(Config, **settings):
            config = migration_mysql_config()

        self.assertEqual(config["host"], "primary-db.internal")
        self.assertEqual(config["port"], 3307)
        self.assertEqual(config["database"], "petcare_test")
        self.assertEqual(config["user"], "petcare_migrator")
        self.assertEqual(config["password"], "migration-password")

    def test_runtime_config_never_uses_migration_credentials(self):
        settings = self._base_settings(
            MIGRATION_DB_USER="petcare_migrator",
            MIGRATION_DB_PASSWORD="migration-password",
        )
        with patch.multiple(Config, **settings):
            config = mysql_config()

        self.assertEqual(config["user"], "petcare_runtime")
        self.assertEqual(config["password"], "runtime-password")

    def test_production_requires_a_database_tls_ca_bundle(self):
        settings = self._base_settings(APP_ENV="production", DB_SSL_CA="")
        with self.assertRaisesRegex(RuntimeError, "DB_SSL_CA"):
            mysql_config(settings)

    def test_database_tls_verifies_certificate_and_server_identity(self):
        with tempfile.TemporaryDirectory() as root:
            ca_file = Path(root) / "provider-ca.pem"
            ca_file.write_text("test CA bundle", encoding="utf-8")
            config = mysql_config(self._base_settings(APP_ENV="production", DB_SSL_CA=str(ca_file)))

        self.assertEqual(config["ssl_ca"], str(ca_file))
        self.assertTrue(config["ssl_verify_cert"])
        self.assertTrue(config["ssl_verify_identity"])

    def test_configured_ca_must_be_a_file(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "CA certificate file"):
                mysql_config(self._base_settings(DB_SSL_CA=root))

    def test_migration_connection_uses_migration_config(self):
        connection = MagicMock()
        with (
            patch("petcare.database.connection.migration_mysql_config", return_value={"user": "migrator"}) as config,
            patch("petcare.database.connection.mysql.connector.connect", return_value=connection) as connect,
        ):
            self.assertIs(get_migration_connection(), connection)

        config.assert_called_once_with()
        connect.assert_called_once_with(user="migrator")
        connection.cursor.return_value.execute.assert_any_call("SET time_zone = '+00:00'")
        connection.cursor.return_value.execute.assert_any_call("SET @petcare_tenant_id = NULL")

    def test_initializer_uses_migration_transaction(self):
        module = importlib.import_module("petcare.database.initialize")
        connection = MagicMock()
        transaction_context = MagicMock()
        transaction_context.__enter__.return_value = connection
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = []

        with (
            patch.object(module, "SCHEMA_PATH", MagicMock(read_text=MagicMock(return_value="CREATE TABLE example (id INT);"))),
            patch.object(module, "migration_transaction", return_value=transaction_context) as transaction,
            patch.object(module, "migrate_tenancy") as migrate,
        ):
            module.initialize_database()

        transaction.assert_called_once_with()
        migrate.assert_called_once_with(cursor)


if __name__ == "__main__":
    unittest.main()
