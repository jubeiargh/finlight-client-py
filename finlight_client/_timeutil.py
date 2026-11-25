"""Strict RFC 3339 parsing and the SDK's own datetime formatting."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

_RFC3339 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


def parse_rfc3339(value: Any) -> Optional[datetime]:
    """Parse a strict RFC 3339 timestamp with ``Z`` or an offset.

    Returns an aware ``datetime`` in UTC, or ``None`` when the value is not a
    string in that exact form. Unix seconds, dates without time and times
    without a zone are not accepted.
    """
    if not isinstance(value, str):
        return None
    m = _RFC3339.match(value)
    if not m:
        return None
    year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
    frac = m.group(7)
    micro = 0
    if frac:
        digits = frac[1:7].ljust(6, "0")
        micro = int(digits)
    zone = m.group(8)
    if zone in ("Z", "z"):
        tz = timezone.utc
    else:
        sign = 1 if zone[0] == "+" else -1
        hh, mm = int(zone[1:3]), int(zone[4:6])
        if hh > 23 or mm > 59:
            return None
        tz = timezone(sign * timedelta(hours=hh, minutes=mm))
    try:
        parsed = datetime(year, month, day, hour, minute, second, micro, tzinfo=tz)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def format_datetime(value: datetime) -> str:
    """UTC ISO 8601 with milliseconds and ``Z``. Naive datetimes are rejected by the caller."""
    utc = value.astimezone(timezone.utc)
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ" % (
        utc.year,
        utc.month,
        utc.day,
        utc.hour,
        utc.minute,
        utc.second,
        utc.microsecond // 1000,
    )


def format_date(value: date) -> str:
    return "%04d-%02d-%02d" % (value.year, value.month, value.day)
