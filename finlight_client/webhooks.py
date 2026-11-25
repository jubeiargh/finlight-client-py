"""Verify and read finlight webhooks on your own server.

Always pass the raw request body exactly as received (bytes, or its UTF-8
string). A parsed and re-serialized body never matches the signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Optional, Union

from ._timeutil import parse_rfc3339
from .errors import FinlightDecodeError, FinlightValidationError, WebhookVerificationError
from .models import WebhookEvent, WrongPayloadVersion, decode_webhook_event

__all__ = ["Webhooks", "SIGNATURE_HEADER", "TIMESTAMP_HEADER", "DEFAULT_WEBHOOK_TOLERANCE"]

SIGNATURE_HEADER = "X-Webhook-Signature"
TIMESTAMP_HEADER = "X-Webhook-Timestamp"
DEFAULT_WEBHOOK_TOLERANCE = 300.0
DEFAULT_TOLERANCE = DEFAULT_WEBHOOK_TOLERANCE

RawBody = Union[bytes, bytearray, memoryview, str]
Headers = Union[Mapping[str, Any], Iterable[tuple[Any, Any]]]
Now = Union[datetime, Callable[[], datetime], None]

_MISSING = object()


def _fail(reason: str, message: str) -> WebhookVerificationError:
    return WebhookVerificationError(f"webhook verification failed: {message}", reason=reason)


def _to_bytes(raw_body: Any) -> bytes:
    if isinstance(raw_body, (bytes, bytearray, memoryview)):
        return bytes(raw_body)
    if isinstance(raw_body, str):
        return raw_body.encode("utf-8")
    raise _fail(
        "invalid_raw_body",
        "raw_body must be the raw request body as bytes or str, exactly as received. "
        "Do not pass parsed JSON: re-serialized JSON never matches the signature.",
    )


def _header_pairs(headers: Any) -> list[tuple[Any, Any]]:
    if headers is None:
        return []
    items = getattr(headers, "items", None)
    if callable(items) and not isinstance(headers, (list, tuple)):
        pairs = list(items())
        # Multi-dicts (werkzeug, aiohttp, starlette) expose duplicates through getlist/getall.
        for getter_name in ("getlist", "getall", "get_all"):
            getter = getattr(headers, getter_name, None)
            if callable(getter):
                expanded: list[tuple[Any, Any]] = []
                seen: set[str] = set()
                for key, _ in pairs:
                    key_s = key.decode("latin-1") if isinstance(key, bytes) else str(key)
                    if key_s.lower() in seen:
                        continue
                    seen.add(key_s.lower())
                    try:
                        values = getter(key)
                    except Exception:  # noqa: BLE001 - foreign mapping, fall back to items()
                        expanded = pairs
                        break
                    expanded.extend((key, v) for v in values)
                pairs = expanded
                break
        return pairs
    return list(headers)


def _normalize_name(name: Any) -> str:
    if isinstance(name, bytes):
        name = name.decode("latin-1")
    lowered = str(name).lower()
    if lowered.startswith("http_"):  # CGI / WSGI / Rack form: HTTP_X_WEBHOOK_TIMESTAMP
        lowered = lowered[5:].replace("_", "-")
    return lowered


def _find_header(pairs: list[tuple[Any, Any]], wanted: str) -> Optional[str]:
    wanted_l = wanted.lower()
    found: list[Any] = []
    for name, value in pairs:
        if _normalize_name(name) == wanted_l:
            found.append(value)
    if not found:
        return None
    if len(found) > 1:
        raise _fail("duplicate_header", f"header {wanted} was sent more than once")
    value = found[0]
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise _fail("duplicate_header", f"header {wanted} was sent more than once")
        value = value[0]
    if isinstance(value, bytes):
        try:
            return value.decode("ascii")
        except UnicodeDecodeError:
            raise _fail("non_ascii_header", f"header {wanted} contains non-ASCII bytes") from None
    return str(value)


def _resolve_now(now: Now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    value = now() if callable(now) else now
    if value.tzinfo is None:
        raise FinlightValidationError("now must be an aware datetime", param="now")
    return value


class Webhooks:
    """Webhook helpers. All methods are static."""

    @staticmethod
    def verify_signature(
        raw_body: RawBody,
        signature: Optional[str],
        timestamp: Optional[str],
        secret: str,
        *,
        tolerance: float = DEFAULT_TOLERANCE,
        now: Now = None,
    ) -> None:
        """Check signature and timestamp. Raises :class:`WebhookVerificationError`, returns ``None`` when valid.

        ``signature`` and ``timestamp`` are the values of the
        ``X-Webhook-Signature`` and ``X-Webhook-Timestamp`` headers. The HMAC
        key is the UTF-8 bytes of the secret (not hex-decoded). The timestamp
        must be RFC 3339 and within ``tolerance`` seconds of ``now`` in both
        directions.
        """
        body = _to_bytes(raw_body)
        if not isinstance(secret, str) or not secret:
            raise _fail("invalid_secret", "the webhook secret must be a non-empty string")
        if signature is None or signature == "":
            raise _fail("missing_signature", "no X-Webhook-Signature header")
        if timestamp is None or timestamp == "":
            raise _fail("missing_timestamp", "no X-Webhook-Timestamp header")
        for name, value in ((SIGNATURE_HEADER, signature), (TIMESTAMP_HEADER, timestamp)):
            if not isinstance(value, str) or not value.isascii():
                raise _fail("non_ascii_header", f"header {name} contains non-ASCII characters")
        if not signature.startswith("sha256="):
            raise _fail("unsupported_signature_scheme", "signature must start with sha256=")
        sent_time = parse_rfc3339(timestamp)
        if sent_time is None:
            raise _fail("unparseable_timestamp", "X-Webhook-Timestamp is not an RFC 3339 timestamp")
        expected = hmac.new(
            secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256
        ).hexdigest().encode("ascii")
        given = signature[len("sha256=") :].encode("ascii")
        if len(given) != len(expected) or not hmac.compare_digest(given, expected):
            raise _fail("signature_mismatch", "signature does not match")
        current = _resolve_now(now)
        if abs((current - sent_time).total_seconds()) > tolerance:
            raise _fail("timestamp_outside_tolerance", "timestamp is outside the tolerance")

    @staticmethod
    def construct_event(
        raw_body: RawBody,
        headers: Headers,
        secret: str,
        tolerance: float = DEFAULT_TOLERANCE,
        *,
        now: Now = None,
    ) -> Union[WebhookEvent, WrongPayloadVersion]:
        """Verify a webhook request and read its body.

        ``headers`` may be any mapping or list of ``(name, value)`` pairs (dict,
        Flask/werkzeug, Django, Starlette, aiohttp, WSGI environ). Names are
        matched without regard to case.

        Returns a :class:`WebhookEvent`, or :class:`WrongPayloadVersion` when the
        signed body is not ``payloadVersion`` 3 (answer that with 2xx too).
        Raises :class:`WebhookVerificationError` when verification fails and
        :class:`FinlightDecodeError` when a signed body cannot be read.
        """
        body = _to_bytes(raw_body)
        pairs = _header_pairs(headers)
        signature = _find_header(pairs, SIGNATURE_HEADER)
        timestamp = _find_header(pairs, TIMESTAMP_HEADER)
        return Webhooks.construct_event_from_values(
            body, signature, timestamp, secret, tolerance=tolerance, now=now
        )

    @staticmethod
    def construct_event_from_values(
        raw_body: RawBody,
        signature: Optional[str],
        timestamp: Optional[str],
        secret: str,
        *,
        tolerance: float = DEFAULT_TOLERANCE,
        now: Now = None,
    ) -> Union[WebhookEvent, WrongPayloadVersion]:
        """Like :meth:`construct_event`, with the two header values passed as strings."""
        body = _to_bytes(raw_body)
        Webhooks.verify_signature(body, signature, timestamp, secret, tolerance=tolerance, now=now)
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise FinlightDecodeError("webhook body is not valid JSON") from None
        if not isinstance(parsed, dict):
            raise FinlightDecodeError("webhook body is not a JSON object", raw=parsed)
        version = parsed.get("payloadVersion", _MISSING)
        if not _is_v3(version):
            return WrongPayloadVersion(
                detected_version=2,
                payload_version=None if version is _MISSING else version,
                payload_version_present=version is not _MISSING,
                raw=parsed,
                link=_link_of(parsed),
            )
        return decode_webhook_event(parsed)


def _is_v3(value: Any) -> bool:
    # Same rule as the server (v === 3): a JSON number equal to 3, never a bool or string.
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value == 3


def _link_of(parsed: dict[str, Any]) -> Optional[str]:
    link = parsed.get("link")
    if isinstance(link, str):
        return link
    data = parsed.get("data")
    if isinstance(data, dict) and isinstance(data.get("link"), str):
        return str(data["link"])
    return None
