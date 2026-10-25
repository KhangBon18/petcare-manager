"""Small, deterministic query filters shared by local and provider lookups."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


@dataclass(frozen=True)
class PriceFilter:
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    include_minimum: bool = True
    include_maximum: bool = True

    def matches(self, value):
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return False
        if not amount.is_finite():
            return False
        if self.minimum is not None and (
            amount < self.minimum or (amount == self.minimum and not self.include_minimum)
        ):
            return False
        if self.maximum is not None and (
            amount > self.maximum or (amount == self.maximum and not self.include_maximum)
        ):
            return False
        return True


_NUMBER = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
_UNIT = r"trieu|million|nghin|ngan|tr|k|m"
_TIME = re.compile(r"\b(?:hom nay|tuan nay|thang nay|today|this week|this month|weekly|monthly)\b")


def query_period(query):
    if re.search(r"\b(?:thang|this month|monthly)\b", query):
        return "month"
    if re.search(r"\b(?:tuan|this week|weekly)\b", query):
        return "week"
    return "today"


def _amount(number, unit):
    # Repeated separators, or a single three-digit group, are thousands.
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", number):
        number = number.replace(".", "").replace(",", "")
    else:
        number = number.replace(",", ".")
    scale = Decimal(1_000_000) if unit in {"trieu", "million", "tr", "m"} else (
        Decimal(1_000) if unit in {"nghin", "ngan", "k"} else Decimal(1)
    )
    return Decimal(number) * scale


def catalog_filters(query):
    """Return text without consumed time/price phrases, plus price constraints.

    Vietnamese ranges share the last unit ("từ 2 đến 3 triệu"). "Khoảng N"
    means N ±10%; explicit ranges and minimum/maximum wording are preferable.
    Only successfully parsed price phrases are consumed from the search text.
    """
    query = _TIME.sub(" ", query)
    filters = []
    number_unit = rf"({_NUMBER})\s*({_UNIT})?\b"
    range_pattern = re.compile(
        rf"\b(?:tu|from|khoang|between)\s+{number_unit}\s*(?:den|toi|to|and|-)\s*{number_unit}"
    )

    def price_range(match):
        first, first_unit, last, last_unit = match.groups()
        minimum = _amount(first, first_unit or last_unit)
        maximum = _amount(last, last_unit or first_unit)
        filters.append(PriceFilter(minimum, maximum))
        return " "

    query = range_pattern.sub(price_range, query)
    bound_pattern = re.compile(
        rf"\b(toi da|toida|khong vuot qua|khong qua|up to|upto|at most|"
        rf"toi thieu|at least|less than|more than|duoi|under|below|tren|above|over|"
        rf"tu|from|den|khoang|about)\s+{number_unit}"
    )

    def price_bound(match):
        operator, number, unit = match.groups()
        amount = _amount(number, unit)
        if operator in {"khoang", "about"}:
            filters.append(PriceFilter(amount * Decimal("0.9"), amount * Decimal("1.1")))
        elif operator in {"tren", "above", "over", "more than", "toi thieu", "at least", "tu", "from"}:
            filters.append(PriceFilter(minimum=amount, include_minimum=operator not in {"tren", "above", "over", "more than"}))
        else:
            filters.append(PriceFilter(maximum=amount, include_maximum=operator not in {"duoi", "under", "below", "less than"}))
        return " "

    query = bound_pattern.sub(price_bound, query)
    if filters:
        query = re.sub(r"\b(?:vnd|dong)\b|₫", " ", query)
    return query, filters
