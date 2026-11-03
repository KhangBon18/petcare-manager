from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from petcare.i18n import current_locale
from petcare.money import format_number
from petcare.services.ui_text import ui_text
from petcare.services.exceptions import ValidationError
from petcare.services import restock_service

from petcare.database.connection import read_connection
from petcare.repositories import report_repo
from petcare.services.common import date_value, require_actor
from petcare.timezones import (
    format_tenant_date,
    tenant_today,
    utc_window_for_local_dates,
    utc_window_for_local_day,
)


def _period(start, end, timezone_name):
    local_today = tenant_today(timezone_name)
    start_date = date_value(start, "Từ ngày") if start else local_today.replace(day=1)
    end_date = date_value(end, "Đến ngày") if end else local_today
    if start_date > end_date:
        raise ValueError("Ngày bắt đầu không được sau ngày kết thúc.")
    if (end_date - start_date).days >= 366:
        raise ValidationError(
            ui_text(
                "Chọn khoảng báo cáo tối đa 366 ngày.",
                "Choose a report period of no more than 366 days.",
            )
        )
    try:
        start_at_utc, end_at_utc = utc_window_for_local_dates(
            start_date, end_date + timedelta(days=1), timezone_name
        )
    except OverflowError as exc:
        raise ValidationError(
            ui_text(
                "Khoảng ngày báo cáo không hợp lệ.", "The report date range is invalid."
            )
        ) from exc
    return start_date, end_date, start_at_utc, end_at_utc


def dashboard(actor_id):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        today = tenant_today(actor["timezone"])
        start_at_utc, end_at_utc = utc_window_for_local_day(today, actor["timezone"])
        metrics = report_repo.dashboard(connection, start_at_utc, end_at_utc)
        week_start, week_end = utc_window_for_local_dates(
            today - timedelta(days=6), today + timedelta(days=1), actor["timezone"]
        )
        metrics["last_seven_days"] = report_repo.summary(
            connection, week_start, week_end
        )["revenue"]
        metrics["week_start"] = (today - timedelta(days=6)).isoformat()
        metrics["week_end"] = today.isoformat()
        metrics["restock"] = [
            item
            for item in restock_service.for_connection(connection, actor)
            if item["warning"]
        ][:5]
        try:
            metrics["business"] = _report(
                connection,
                actor,
                (today - timedelta(days=6)).isoformat(),
                today.isoformat(),
            )
        except ValidationError as exc:
            # The headline aggregates remain exact even when a detailed chart
            # period exceeds the deliberate MVP export bound.
            metrics["business_error"] = str(exc)
        return metrics


def report(actor_id, start=None, end=None, period=None):
    with read_connection() as connection:
        actor = require_actor(connection, actor_id)
        if period:
            today = tenant_today(actor["timezone"])
            starts = {
                "today": today,
                "7d": today - timedelta(days=6),
                "30d": today - timedelta(days=29),
                "month": today.replace(day=1),
            }
            if period not in starts:
                raise ValidationError(
                    ui_text("Kỳ báo cáo không hợp lệ.", "The report period is invalid.")
                )
            start, end = starts[period].isoformat(), today.isoformat()
        return _report(connection, actor, start, end)


def _report(connection, actor, start, end):
    start_date, end_date, start_at, end_at = _period(start, end, actor["timezone"])
    count_days = (end_date - start_date).days + 1
    try:
        previous_start = start_date - timedelta(days=count_days)
    except OverflowError as exc:
        raise ValidationError(
            ui_text(
                "Khoảng ngày báo cáo không hợp lệ.", "The report date range is invalid."
            )
        ) from exc
    previous_at, previous_end = utc_window_for_local_dates(
        previous_start, start_date, actor["timezone"]
    )
    rows = report_repo.paid_lines(connection, start_at, end_at)
    if len(rows) > 5000:
        raise ValidationError(
            ui_text(
                "Kỳ có hơn 5.000 dòng hàng; hãy chọn khoảng ngày ngắn hơn để xuất đầy đủ.",
                "This period has over 5,000 line items. Choose a shorter period to export all details.",
            )
        )
    zone = ZoneInfo(actor["timezone"])
    daily = {
        start_date + timedelta(days=i): {"revenue": Decimal(0), "invoices": set()}
        for i in range(count_days)
    }
    details = []
    for row in rows:
        local_paid = row["paid_at"].replace(tzinfo=timezone.utc).astimezone(zone)
        day = local_paid.date()
        daily[day]["revenue"] += row["line_total"]
        if row["entry_type"] == "sale":
            daily[day]["invoices"].add(row["invoice_id"])
        details.append({**row, "paid_at": local_paid.isoformat()})
    series = [
        {
            "date": day.isoformat(),
            "revenue": value["revenue"],
            "invoice_count": len(value["invoices"]),
        }
        for day, value in daily.items()
    ]
    summary = {
        "revenue": sum((row["revenue"] for row in series), Decimal(0)),
        "invoice_count": len({row["invoice_id"] for row in rows if row["entry_type"] == "sale"}),
    }
    previous = report_repo.summary(connection, previous_at, previous_end)
    growth = (
        ((summary["revenue"] - previous["revenue"]) / previous["revenue"] * 100)
        if previous["revenue"]
        else None
    )
    peak = max(series, key=lambda row: row["revenue"])
    maximum = max((row["revenue"] for row in series), default=Decimal(0))
    maximum = max(maximum, Decimal(1))
    bars = [
        {
            "x": round(i * 680 / count_days + 1, 2),
            "width": round(max(0.5, 680 / count_days - 2), 2),
            "y": round(160 - max(0, float(row["revenue"] / maximum)) * 150, 2),
            "height": round(max(0, float(row["revenue"] / maximum)) * 150, 2),
            **row,
        }
        for i, row in enumerate(series)
    ]
    result = {
        "start_date": start_date,
        "end_date": end_date,
        "summary": summary,
        "previous": previous,
        "previous_start": previous_start,
        "previous_end": start_date - timedelta(days=1),
        "growth": growth,
        "daily": series,
        "chart_bars": bars,
        "peak": peak,
        "details": details,
        "top_products": report_repo.top_products(connection, start_at, end_at),
        "inventory": report_repo.inventory(connection),
        "pets_sold": report_repo.pets_sold(connection, start_at, end_at),
        "currency_code": actor["default_currency"],
        "tenant_name": actor.get("tenant_name", "PetCare"),
        "timezone": actor["timezone"],
        "captured_at": datetime.now(zone).isoformat(timespec="seconds"),
    }
    result["brief"] = business_brief(result, current_locale())
    return result


def business_brief(report, locale="vi"):
    summary, previous = report["summary"], report["previous"]
    count = summary["invoice_count"]
    number_locale = "en_US" if locale == "en" else "vi_VN"
    growth = Decimal(str(report["growth"])) if report["growth"] is not None else None
    if locale == "en":
        first = f"{format_number(count, number_locale)} paid invoices. Unpaid and cancelled invoices are excluded."
        trend = (
            f"Revenue changed by {'+' if growth >= 0 else '−'}{format_number(abs(growth), number_locale, '#,##0.0')}% versus the previous equal-length period."
            if growth is not None
            else "Previous period had no revenue; percentage growth is not defined."
        )
        peak_date = (report.get("peak") or {}).get("date")
        peak = (
            f"Best day: {format_tenant_date(peak_date, locale)}."
            if count and peak_date
            else "No paid sales in this period. Try a different period."
            if not count
            else "Peak-day details are unavailable for this snapshot."
        )
    else:
        first = f"Có {format_number(count, number_locale)} hóa đơn đã thu; không tính hóa đơn chưa thu hoặc đã hủy."
        trend = (
            f"Doanh thu thay đổi {'+' if growth >= 0 else '−'}{format_number(abs(growth), number_locale, '#,##0.0')}% so với kỳ trước cùng số ngày."
            if growth is not None
            else "Kỳ trước chưa có doanh thu; không tính tỷ lệ tăng trưởng từ nền bằng 0."
        )
        peak_date = (report.get("peak") or {}).get("date")
        peak = (
            f"Ngày doanh thu cao nhất: {format_tenant_date(peak_date, locale)}."
            if count and peak_date
            else "Chưa có giao dịch đã thu trong kỳ. Hãy thử kỳ khác."
            if not count
            else "Snapshot này không lưu chi tiết ngày doanh thu cao nhất."
        )
    lines = [first, trend, peak]
    if report.get("top_products"):
        best = report["top_products"][0]
        lines.append(
            f"Best seller by units: {best['name']} ({format_number(best['quantity_sold'], number_locale)})."
            if locale == "en"
            else f"Bán chạy theo số lượng: {best['name']} ({format_number(best['quantity_sold'], number_locale)})."
        )
    return lines
