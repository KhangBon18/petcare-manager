"""ISO currency validation, exact decimal parsing, and display formatting."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from babel.core import get_global
from babel.numbers import format_decimal, get_currency_name, get_currency_precision


_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_AMOUNT_RE = re.compile(r"^(?:0|[1-9]\d{0,15})(?:\.\d{1,4})?$")
_CURRENT_TENDER_CURRENCIES = frozenset(
    code
    for entries in get_global("territory_currencies").values()
    for code, start, end, tender in entries
    if end is None and tender and date(*start) <= date.today()
)


class CurrencyError(ValueError):
    """A code is not a currently supported ISO 4217 tender currency."""


def normalize_currency_code(value):
    code = (value or "").strip().upper()
    if not _CURRENCY_RE.fullmatch(code) or code not in _CURRENT_TENDER_CURRENCIES:
        raise CurrencyError("Mã tiền tệ không hợp lệ hoặc hiện không được hỗ trợ.")
    return code


def currency_precision(code):
    return get_currency_precision(normalize_currency_code(code))


def currency_step(code):
    """Return a native number-input step matching the currency's minor unit."""
    precision = currency_precision(code)
    return "1" if precision == 0 else "0." + ("0" * (precision - 1)) + "1"


def money_input_value(amount, code):
    """Format a stored amount for a locale-neutral HTML number input."""
    code = normalize_currency_code(code)
    precision = currency_precision(code)
    quantum = Decimal(1).scaleb(-precision)
    value = Decimal(str(amount))
    normalized = value.quantize(quantum)
    if value != normalized:
        raise ValueError(f"Stored amount exceeds the supported precision for {code}.")
    return format(normalized, "f")


def currency_options(locale="en"):
    options = []
    for code in sorted(_CURRENT_TENDER_CURRENCIES):
        name = get_currency_name(code, locale=locale)
        options.append({"code": code, "name": name or code})
    return options


def parse_money(value, code, label="Giá"):
    precision = currency_precision(code)
    raw = str(value if value is not None else "").strip()
    if not _AMOUNT_RE.fullmatch(raw):
        raise ValueError(f"{label} cần là số tiền không âm, tối đa 16 chữ số phần nguyên.")
    try:
        amount = Decimal(raw)
        quantum = Decimal(1).scaleb(-precision)
        normalized = amount.quantize(quantum)
    except InvalidOperation as exc:
        raise ValueError(f"{label} không hợp lệ.") from exc
    if amount != normalized:
        raise ValueError(f"{label} chỉ được có tối đa {precision} chữ số thập phân theo {code}.")
    return normalized


def format_money(amount, code, locale="vi_VN"):
    code = normalize_currency_code(code)
    precision = currency_precision(code)
    quantum = Decimal(1).scaleb(-precision)
    try:
        value = Decimal(str(amount or 0)).quantize(quantum)
    except (InvalidOperation, ValueError):
        value = Decimal(0).quantize(quantum)
    number_format = "#,##0" + ("." + ("0" * precision) if precision else "")
    number = format_decimal(value, format=number_format, locale=locale)
    return f"{number}\u00a0{code}"
