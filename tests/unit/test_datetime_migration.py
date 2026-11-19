import unittest

from petcare.database.initialize import (
    UTC_DATETIME_MIGRATION,
    migrate_datetime_storage_to_utc,
)


class FakeMigrationCursor:
    def __init__(self, already_applied=False):
        self.already_applied = already_applied
        self.calls = []
        self.result = None

    def execute(self, query, params=None):
        self.calls.append((query, params))
        if "SELECT 1 FROM schema_migrations" in query:
            self.result = (1,) if self.already_applied else None
        elif "FROM information_schema.columns" in query:
            self.result = [
                ("invoices", "created_at"),
                ("invoices", "paid_at"),
                ("users", "email_verified_at"),
            ]
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


class DatetimeMigrationTests(unittest.TestCase):
    def test_backfills_every_database_datetime_and_records_marker_once(self):
        cursor = FakeMigrationCursor()

        migrated = migrate_datetime_storage_to_utc(cursor)

        self.assertTrue(migrated)
        updates = [query for query, _ in cursor.calls if query.startswith("UPDATE ")]
        self.assertEqual(len(updates), 3)
        self.assertTrue(all("DATE_SUB(" in query and "INTERVAL 7 HOUR" in query for query in updates))
        self.assertEqual(
            cursor.calls[-1],
            ("INSERT INTO schema_migrations (version) VALUES (%s)", (UTC_DATETIME_MIGRATION,)),
        )

    def test_existing_marker_prevents_a_second_seven_hour_shift(self):
        cursor = FakeMigrationCursor(already_applied=True)

        migrated = migrate_datetime_storage_to_utc(cursor)

        self.assertFalse(migrated)
        self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
