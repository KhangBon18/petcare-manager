from datetime import timedelta

from petcare.database.connection import read_connection
from petcare.repositories import report_repo
from petcare.services.common import date_value, require_actor
from petcare.timezones import tenant_today, utc_window_for_local_dates, utc_window_for_local_day


def _period(start, end, timezone_name):
    local_today = tenant_today(timezone_name)
    start_date = date_value(start, "Từ ngày") if start else local_today.replace(day=1)
    end_date = date_value(end, "Đến ngày") if end else local_today
    if start_date > end_date:
        raise ValueError("Ngày bắt đầu không được sau ngày kết thúc.")
    start_at_utc, end_at_utc = utc_window_for_local_dates(
        start_date, end_date + timedelta(days=1), timezone_name
    )
    return start_date, end_date, start_at_utc, end_at_utc


def dashboard(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        today = tenant_today(actor["timezone"])
        start_at_utc, end_at_utc = utc_window_for_local_day(today, actor["timezone"])
        return report_repo.dashboard(connection, start_at_utc, end_at_utc)


def report(actor_id, start=None, end=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        start_date, end_date, start_at_utc, end_at_utc = _period(
            start, end, actor["timezone"]
        )
        return {
            "start_date": start_date,
            "end_date": end_date,
            "summary": report_repo.summary(connection, start_at_utc, end_at_utc),
            "top_products": report_repo.top_products(connection, start_at_utc, end_at_utc),
            "inventory": report_repo.inventory(connection),
            "pets_sold": report_repo.pets_sold(connection, start_at_utc, end_at_utc),
        }
