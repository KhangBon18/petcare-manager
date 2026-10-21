import unittest
from datetime import date, datetime

from petcare.timezones import (
    TimezoneError,
    format_tenant_datetime,
    normalize_timezone_name,
    utc_window_for_local_day,
)


class TenantTimezoneTests(unittest.TestCase):
    def test_timezone_names_are_trimmed_and_validated(self):
        self.assertEqual(normalize_timezone_name(" America/New_York "), "America/New_York")
        for value in ("", "Not/A_Timezone", "x" * 65):
            with self.subTest(value=value), self.assertRaises(TimezoneError):
                normalize_timezone_name(value)

    def test_local_day_maps_to_utc_half_open_window(self):
        start, end = utc_window_for_local_day(date(2026, 10, 18), "Asia/Ho_Chi_Minh")
        self.assertEqual(start, datetime(2026, 10, 17, 17))
        self.assertEqual(end, datetime(2026, 10, 18, 17))

    def test_local_day_bounds_follow_spring_dst_transition(self):
        start, end = utc_window_for_local_day(date(2026, 3, 8), "America/Los_Angeles")
        self.assertEqual(start, datetime(2026, 3, 8, 8))
        self.assertEqual(end, datetime(2026, 3, 9, 7))
        self.assertEqual((end - start).total_seconds(), 23 * 60 * 60)

    def test_local_day_bounds_follow_fall_dst_transition(self):
        start, end = utc_window_for_local_day(date(2026, 11, 1), "America/Los_Angeles")
        self.assertEqual(start, datetime(2026, 11, 1, 7))
        self.assertEqual(end, datetime(2026, 11, 2, 8))
        self.assertEqual((end - start).total_seconds(), 25 * 60 * 60)

    def test_utc_naive_database_timestamp_renders_in_tenant_timezone(self):
        self.assertEqual(
            format_tenant_datetime(datetime(2026, 10, 18, 6, 30), "America/Los_Angeles"),
            "17/10/2026 23:30",
        )


if __name__ == "__main__":
    unittest.main()
