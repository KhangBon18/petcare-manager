import unittest
from unittest.mock import MagicMock, call, patch

from petcare.config import Config
from petcare.database import connection as database_connection


class RuntimeConnectionPoolTests(unittest.TestCase):
    def setUp(self):
        self.original_pools = database_connection._RUNTIME_POOLS
        database_connection._RUNTIME_POOLS = {}

    def tearDown(self):
        database_connection._RUNTIME_POOLS = self.original_pools

    def test_pool_is_cached_by_config_and_resets_sessions(self):
        pool = MagicMock()
        config = {
            "host": "db.internal",
            "port": 3306,
            "database": "petcare_test",
            "user": "runtime",
            "password": "secret",
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
            "connection_timeout": 5,
            "autocommit": False,
        }
        with (
            patch.object(database_connection, "mysql_config", return_value=config),
            patch.object(Config, "DB_POOL_SIZE", 3),
            patch.object(database_connection, "MySQLConnectionPool", return_value=pool) as factory,
        ):
            first = database_connection._runtime_pool()
            second = database_connection._runtime_pool()

        self.assertIs(first, second)
        factory.assert_called_once()
        kwargs = factory.call_args.kwargs
        self.assertEqual(kwargs["pool_size"], 3)
        self.assertTrue(kwargs["pool_reset_session"])
        self.assertNotIn("secret", kwargs["pool_name"])

    def test_checkout_reapplies_utc_and_clears_tenant_context(self):
        pooled = MagicMock()
        cursor = pooled.cursor.return_value
        with patch.object(database_connection, "_runtime_pool") as runtime_pool:
            runtime_pool.return_value.get_connection.return_value = pooled

            result = database_connection.get_connection()

        self.assertIs(result, pooled)
        self.assertEqual(
            cursor.execute.call_args_list,
            [call("SET time_zone = '+00:00'"), call("SET @petcare_tenant_id = NULL")],
        )
        cursor.close.assert_called_once_with()

    def test_tls_trust_bundle_rotation_creates_a_new_pool(self):
        pools = [MagicMock(), MagicMock()]
        first_config = {"host": "db.internal", "ssl_ca": "/run/secrets/old-ca.pem"}
        second_config = {"host": "db.internal", "ssl_ca": "/run/secrets/new-ca.pem"}
        with (
            patch.object(database_connection, "mysql_config", side_effect=[first_config, second_config]),
            patch.object(Config, "DB_POOL_SIZE", 3),
            patch.object(database_connection, "MySQLConnectionPool", side_effect=pools) as factory,
        ):
            first = database_connection._runtime_pool()
            second = database_connection._runtime_pool()

        self.assertIsNot(first, second)
        self.assertEqual(factory.call_count, 2)

    def test_invalid_pool_size_fails_before_opening_database_connections(self):
        with (
            patch.object(Config, "DB_POOL_SIZE", 33),
            patch.object(database_connection, "mysql_config", return_value={}),
            patch.object(database_connection, "MySQLConnectionPool") as factory,
            self.assertRaisesRegex(RuntimeError, "DB_POOL_SIZE"),
        ):
            database_connection._runtime_pool()


if __name__ == "__main__":
    unittest.main()
