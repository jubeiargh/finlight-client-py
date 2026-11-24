"""WebSocket frame decoder.

Frames are checked for ``event`` first (v3). A frame with only ``action`` is a
control frame in v2 form, which the server sends before the first v3 subscribe
of a connection (pong, preempted, error, admit). It is mapped onto the same v3
types. A v2 ``sendArticle`` is never delivered as an article.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

ARTICLE = "article"
ADMITTED = "admitted"
PONG = "pong"
PREEMPTED = "preempted"
ERROR = "error"
OTHER = "other"
LEGACY_ARTICLE = "legacy_article"
INVALID = "invalid"

_ARTICLE_KINDS = {"article.created": "created", "article.updated": "updated"}


@dataclass
class Frame:
    type: str
    event: Optional[str] = None
    kind: Optional[str] = None
    data: Any = None
    raw: Any = None
    v2: bool = False
    fields: dict[str, Any] = field(default_factory=dict)


def _int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _str_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def decode_frame(text: Any) -> Frame:
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError:
            return Frame(INVALID, raw=None)
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return Frame(INVALID, raw=None)
    if not isinstance(obj, dict):
        return Frame(INVALID, raw=obj)

    event = obj.get("event")
    if isinstance(event, str):
        data = obj.get("data")
        if event in _ARTICLE_KINDS:
            return Frame(ARTICLE, event=event, kind=_ARTICLE_KINDS[event], data=data, raw=obj)
        d = data if isinstance(data, dict) else {}
        if event == "connection.admitted":
            return Frame(
                ADMITTED,
                event=event,
                raw=obj,
                fields={
                    "lease_id": _str_or_none(d.get("leaseId")),
                    "server_now": _int_or_none(d.get("serverNow")),
                    "client_nonce": _str_or_none(d.get("clientNonce")),
                },
            )
        if event == "connection.pong":
            return Frame(PONG, event=event, raw=obj, fields={"t": d.get("t"), "server_now": d.get("serverNow")})
        if event == "connection.preempted":
            return Frame(
                PREEMPTED,
                event=event,
                raw=obj,
                fields={
                    "reason": _str_or_none(d.get("reason")),
                    "new_lease_id": _str_or_none(d.get("newLeaseId")),
                    "timestamp": _int_or_none(d.get("timestamp")),
                },
            )
        if event == "connection.error":
            return Frame(
                ERROR,
                event=event,
                raw=obj,
                fields={
                    "code": _str_or_none(d.get("code")),
                    "message": _str_or_none(d.get("message")),
                    "details": d.get("details"),
                },
            )
        return Frame(OTHER, event=event, kind="other", data=data, raw=obj)

    action = obj.get("action")
    if isinstance(action, str):
        if action == "pong":
            return Frame(PONG, event="connection.pong", raw=obj, v2=True,
                         fields={"t": obj.get("t"), "server_now": obj.get("serverNow")})
        if action == "admit":
            return Frame(
                ADMITTED,
                event="connection.admitted",
                raw=obj,
                v2=True,
                fields={
                    "lease_id": _str_or_none(obj.get("leaseId")),
                    "server_now": _int_or_none(obj.get("serverNow")),
                    "client_nonce": _str_or_none(obj.get("clientNonce")),
                },
            )
        if action == "preempted":
            return Frame(
                PREEMPTED,
                event="connection.preempted",
                raw=obj,
                v2=True,
                fields={
                    "reason": _str_or_none(obj.get("reason")),
                    "new_lease_id": _str_or_none(obj.get("newLeaseId")),
                    "timestamp": _int_or_none(obj.get("timestamp")),
                },
            )
        if action == "error":
            text_value = obj.get("error", obj.get("data"))
            message = text_value if isinstance(text_value, str) else None
            if message is None and text_value is not None:
                message = json.dumps(text_value)[:200]
            return Frame(ERROR, event="connection.error", raw=obj, v2=True,
                         fields={"code": None, "message": message, "details": None})
        if action == "sendArticle":
            return Frame(LEGACY_ARTICLE, raw=obj, v2=True)
        return Frame(OTHER, event=None, kind="other", raw=obj, v2=True)

    return Frame(OTHER, event=None, kind="other", raw=obj)
