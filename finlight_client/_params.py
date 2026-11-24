"""Building request bodies and subscribe frames.

Only keys the caller set are sent (``None`` means "not set"). Keys come from a
fixed list; values of vocabularies are not checked. Only the shape is checked,
before anything goes on the wire.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Optional, Union

from ._timeutil import format_date, format_datetime
from .errors import FinlightValidationError

TimeValue = Union[str, datetime, date]

# (python name, wire name, kind) in the order they are written to the body.
SEARCH_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("query", "query", "str"),
    ("sources", "sources", "strlist"),
    ("opt_in_sources", "optInSources", "strlist"),
    ("exclude_sources", "excludeSources", "strlist"),
    ("from_", "from", "time"),
    ("to", "to", "time"),
    ("languages", "languages", "languages"),
    ("tickers", "tickers", "strlist"),
    ("countries", "countries", "strlist"),
    ("categories", "categories", "strlist"),
    ("has_content", "hasContent", "bool"),
    ("roles", "roles", "strlist"),
    ("min_relevance", "minRelevance", "unit"),
    ("event_types", "eventTypes", "strlist"),
    ("event_directions", "eventDirections", "strlist"),
    ("min_importance", "minImportance", "str"),
    ("sectors", "sectors", "strlist"),
    ("company_countries", "companyCountries", "strlist"),
    ("exchanges", "exchanges", "strlist"),
    ("order_by", "orderBy", "str"),
    ("order", "order", "str"),
    ("limit", "limit", "limit"),
    ("cursor", "cursor", "str"),
    ("include", "include", "include"),
)

STREAM_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("include", "include", "include"),
    ("query", "query", "str"),
    ("sources", "sources", "strlist"),
    ("exclude_sources", "excludeSources", "strlist"),
    ("opt_in_sources", "optInSources", "strlist"),
    ("language", "language", "str"),
    ("tickers", "tickers", "strlist"),
    ("countries", "countries", "strlist"),
    ("categories", "categories", "strlist"),
    ("exclude_empty_content", "excludeEmptyContent", "bool"),
    ("include_updates", "includeUpdates", "bool"),
)

RAW_STREAM_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("query", "query", "str"),
    ("sources", "sources", "strlist"),
    ("exclude_sources", "excludeSources", "strlist"),
    ("language", "language", "str"),
    ("include_updates", "includeUpdates", "bool"),
)

def _fail(message: str) -> FinlightValidationError:
    return FinlightValidationError(message)


def str_list(name: str, value: Any) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise _fail(f"{name} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _fail(f"{name} must contain only strings")
        out.append(item)
    return out


def include_list(value: Any) -> list[str]:
    items = str_list("include", value)
    if len(items) > 3:
        raise _fail("include takes at most 3 values")
    return items


def time_value(name: str, value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise _fail(f"{name} is a datetime without a time zone; pass an aware datetime")
        return format_datetime(value)
    if isinstance(value, date):
        return format_date(value)
    raise _fail(f"{name} must be a string, datetime or date")


def _convert(name: str, kind: str, value: Any) -> Any:
    if kind == "str":
        if not isinstance(value, str):
            raise _fail(f"{name} must be a string")
        return value
    if kind == "strlist":
        return str_list(name, value)
    if kind == "languages":
        items = str_list(name, value)
        if not items:
            raise _fail("languages must not be empty")
        return items
    if kind == "include":
        return include_list(value)
    if kind == "bool":
        if not isinstance(value, bool):
            raise _fail(f"{name} must be True or False")
        return value
    if kind == "time":
        return time_value(name, value)
    if kind == "unit":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _fail(f"{name} must be a number")
        if not 0 <= value <= 1:
            raise _fail(f"{name} must be between 0 and 1")
        return value
    if kind == "limit":
        if isinstance(value, bool) or not isinstance(value, int):
            raise _fail("limit must be an integer")
        if not 1 <= value <= 100:
            raise _fail("limit must be between 1 and 100")
        return value
    raise AssertionError(kind)  # pragma: no cover


def build_body(fields: Sequence[tuple[str, str, str]], values: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for py_name, wire_name, kind in fields:
        value = values.get(py_name)
        if value is None:
            continue
        converted = _convert(py_name, kind, value)
        if kind == "include" and not converted:
            continue  # an empty include is left out
        body[wire_name] = converted
    return body


def dumps(body: dict[str, Any]) -> bytes:
    """Compact JSON, UTF-8. An empty body is ``{}``."""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def build_subscribe(
    fields: Sequence[tuple[str, str, str]], values: dict[str, Any]
) -> dict[str, Any]:
    """The subscribe frame without ``clientNonce`` (added per connection).

    Built only from the fixed key list, never by copying caller objects, so no
    other key can reach the wire. ``payloadVersion`` is always the integer 3.
    """
    frame: dict[str, Any] = {"payloadVersion": 3}
    frame.update(build_body(fields, values))
    return frame


def include_query(include: Optional[Sequence[str]]) -> list[tuple[str, str]]:
    if include is None:
        return []
    items = include_list(include)
    if not items:
        return []
    return [("include", ",".join(items))]


def company_ids(value: Any) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise _fail("ids must be a list of integers")
    if not 1 <= len(value) <= 10:
        raise _fail("ids takes 1 to 10 company ids")
    out: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise _fail("ids must be integers >= 1")
        out.append(item)
    return out
