"""Tenant-local business dates backed by canonical UTC DATETIME storage."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from babel.dates import format_date as babel_format_date
from babel.dates import format_datetime as babel_format_datetime


DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
UTC = timezone.utc
COMMON_TIMEZONES = (
    "UTC",
    "America/Los_Angeles",
    "America/Denver",
    "America/Chicago",
    "America/New_York",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Africa/Johannesburg",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Ho_Chi_Minh",
    "Asia/Singapore",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Perth",
    "Australia/Sydney",
    "Pacific/Auckland",
)


class TimezoneError(ValueError):
    """The supplied IANA time zone name is invalid or unavailable."""


def normalize_timezone_name(value):
    name = (value or "").strip()
    if not name or len(name) > 64:
        raise TimezoneError("Múi giờ không hợp lệ.")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TimezoneError("Múi giờ cần là tên IANA hợp lệ, ví dụ Asia/Ho_Chi_Minh.") from exc
    return name


def tenant_today(timezone_name):
    return datetime.now(ZoneInfo(normalize_timezone_name(timezone_name))).date()


def _local_midnight_utc_naive(day, zone):
    local_midnight = datetime.combine(day, time.min, tzinfo=zone)
    return local_midnight.astimezone(UTC).replace(tzinfo=None)


def utc_window_for_local_dates(start_date, end_exclusive, timezone_name):
    """Map a half-open tenant-local date range to UTC-naive MySQL DATETIME bounds."""
    zone = ZoneInfo(normalize_timezone_name(timezone_name))
    return (
        _local_midnight_utc_naive(start_date, zone),
        _local_midnight_utc_naive(end_exclusive, zone),
    )


def utc_window_for_local_day(day, timezone_name):
    return utc_window_for_local_dates(day, day + timedelta(days=1), timezone_name)


def format_tenant_date(value, locale="vi"):
    """Format a date-only value for the selected interface locale."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    elif isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, date):
        return str(value)
    if locale == "en":
        return babel_format_date(value, format="MMM d, yyyy", locale="en_US")
    return babel_format_date(value, format="dd/MM/yyyy", locale="vi_VN")


def format_tenant_datetime(value, timezone_name, date_format=None, locale="vi"):
    """Render a UTC or ISO timestamp in a tenant zone using UI-locale conventions."""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)
    zone = ZoneInfo(normalize_timezone_name(timezone_name))
    # MySQL DATETIME has no zone metadata. Application writes are UTC-naive.
    instant = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    local = instant.astimezone(zone)
    if date_format is not None:
        return local.strftime(date_format)
    if locale == "en":
        return babel_format_datetime(local, format="MMM d, yyyy h:mm a", locale="en_US")
    return babel_format_datetime(local, format="dd/MM/yyyy HH:mm", locale="vi_VN")
