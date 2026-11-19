"""Normalization for account email addresses accepted by the application."""

import re


_LOCAL_PART = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL = re.compile(rf"^{_LOCAL_PART}@{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})+$")


def normalize_email(value):
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > 254 or raw.count("@") != 1:
        return None
    local, domain = raw.rsplit("@", 1)
    if not local.isascii():
        return None
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    normalized = f"{local.casefold()}@{domain.casefold()}"
    return normalized if len(normalized) <= 254 and _EMAIL.fullmatch(normalized) else None
