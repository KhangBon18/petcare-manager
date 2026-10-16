"""Tiện ích chuẩn hóa và kiểm tra ngày tháng, thời gian trong toàn bộ hệ thống PetCare."""

from datetime import date, datetime
import re
from typing import Any


def parse_date(value: Any, field_name: str = "Ngày") -> date:
    """Chuyển đổi chuỗi ngày thành đối tượng datetime.date.
    
    Hỗ trợ các định dạng phổ biến:
    - YYYY-MM-DD (chuẩn ISO)
    - YYYYMMDD (chuỗi gọn 8 chữ số)
    - YYYY/MM/DD
    - DD/MM/YYYY hoặc DD-MM-YYYY
    """
    if value is None:
        raise ValueError(f"{field_name} không được để trống")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    val_str = str(value).strip()
    if not val_str:
        raise ValueError(f"{field_name} không được để trống")

    # Thử parse ISO YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val_str):
        try:
            return date.fromisoformat(val_str)
        except ValueError:
            raise ValueError(f"{field_name} '{val_str}' không phải là ngày hợp lệ theo lịch")

    # Thử parse compact YYYYMMDD
    if re.fullmatch(r"\d{8}", val_str):
        try:
            year = int(val_str[0:4])
            month = int(val_str[4:6])
            day = int(val_str[6:8])
            return date(year, month, day)
        except ValueError:
            raise ValueError(f"{field_name} '{val_str}' không phải là ngày hợp lệ theo lịch")

    # Thử parse YYYY/MM/DD
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", val_str):
        try:
            parts = val_str.split("/")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            raise ValueError(f"{field_name} '{val_str}' không phải là ngày hợp lệ theo lịch")

    # Thử parse DD/MM/YYYY hoặc DD-MM-YYYY
    match_dmy = re.fullmatch(r"(\d{2})[/-](\d{2})[/-](\d{4})", val_str)
    if match_dmy:
        day, month, year = match_dmy.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            raise ValueError(f"{field_name} '{val_str}' không phải là ngày hợp lệ theo lịch")

    raise ValueError(f"{field_name} '{val_str}' không đúng định dạng ngày (quy chuẩn: YYYY-MM-DD)")


def normalize_date(value: Any, field_name: str = "Ngày", default_today: bool = False) -> str:
    """Chuẩn hóa ngày về chuỗi ISO 'YYYY-MM-DD' đồng nhất và hợp lệ."""
    if (value is None or not str(value).strip()) and default_today:
        return date.today().isoformat()
    d = parse_date(value, field_name=field_name)
    return d.isoformat()


def parse_datetime(value: Any, field_name: str = "Thời gian") -> datetime:
    """Chuyển đổi chuỗi thời gian thành đối tượng datetime.
    
    Hỗ trợ:
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DD HH:MM
    - YYYY-MM-DDTHH:MM:SS
    - YYYY-MM-DDTHH:MM
    - YYYY/MM/DD HH:MM
    - DD/MM/YYYY HH:MM
    - YYYY-MM-DD (mặc định 09:00:00 cho lịch hẹn)
    """
    if value is None:
        raise ValueError(f"{field_name} không được để trống")
    if isinstance(value, datetime):
        return value

    val_str = str(value).strip()
    if not val_str:
        raise ValueError(f"{field_name} không được để trống")

    # Thay thế T bằng khoảng trắng để đồng nhất
    standardized = val_str.replace("T", " ")

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(standardized, fmt)
        except ValueError:
            continue

    # Nếu chỉ có ngày YYYY-MM-DD
    try:
        d = parse_date(val_str, field_name=field_name)
        return datetime(d.year, d.month, d.day, 9, 0, 0)
    except ValueError:
        pass

    raise ValueError(f"{field_name} '{val_str}' không đúng định dạng ngày giờ hợp lệ (quy chuẩn: YYYY-MM-DD HH:MM)")


def normalize_datetime(
    value: Any,
    field_name: str = "Thời gian",
    format_str: str = "%Y-%m-%d %H:%M",
) -> str:
    """Chuẩn hóa chuỗi thời gian về định dạng lưu trữ thống nhất."""
    dt = parse_datetime(value, field_name=field_name)
    return dt.strftime(format_str)
