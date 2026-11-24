"""R-HOOK-1..3 beyond the kit vectors."""

from __future__ import annotations

import hashlib
import hmac
import json
from email.message import Message
from typing import Any

import pytest

from finlight_client import (
    DEFAULT_WEBHOOK_TOLERANCE,
    FinlightDecodeError,
    WebhookEvent,
    Webhooks,
    WebhookVerificationError,
    WrongPayloadVersion,
)
from finlight_client._timeutil import parse_rfc3339
from tests.support import load

SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TS = "2026-11-23T21:04:05.123Z"
NOW = parse_rfc3339(TS)
ARTICLE = load("fixtures/decode/full-article.json")["wire"]


def sign(body: bytes, ts: str = TS, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()


def envelope(**overrides: Any) -> bytes:
    env = {"eventId": "evt_abc", "event": "article.created", "occurredAt": TS, "payloadVersion": 3,
           "subscriptionId": "s", "data": ARTICLE}
    env.update(overrides)
    for key in [k for k, v in overrides.items() if v is ...]:
        env.pop(key)
    return json.dumps(env, separators=(",", ":"), ensure_ascii=False).encode()


def construct(body: Any, headers: Any) -> Any:
    return Webhooks.construct_event(body, headers, SECRET, now=NOW)


def test_payload_version_rules() -> None:
    b = envelope(payloadVersion=3.0)
    assert isinstance(construct(b, {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS}), WebhookEvent)
    for value in ("3", True, 2, 4, None):
        b = envelope(payloadVersion=value)
        result = construct(b, {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS})
        assert isinstance(result, WrongPayloadVersion) and result.detected_version == 2
        assert result.payload_version == value and result.payload_version_present
        assert result.link == ARTICLE["link"]
    assert not issubclass(WrongPayloadVersion, BaseException)  # a result, never an error


def test_tampered_v2_body_fails_the_signature_first() -> None:
    fx = load("fixtures/webhook/v2-body.json")
    import base64

    raw = base64.b64decode(fx["request"]["rawBodyBase64"]) + b" "
    with pytest.raises(WebhookVerificationError):
        Webhooks.construct_event(raw, fx["request"]["headers"], fx["secret"], now=NOW)


def test_header_collections() -> None:
    b = envelope()
    sig = sign(b)
    variants: list[Any] = [
        {"x-webhook-signature": sig, "x-webhook-timestamp": TS},
        [("X-WEBHOOK-SIGNATURE", sig), ("X-Webhook-Timestamp", TS)],
        [(b"x-webhook-signature", sig.encode()), (b"x-webhook-timestamp", TS.encode())],
        {"HTTP_X_WEBHOOK_SIGNATURE": sig, "HTTP_X_WEBHOOK_TIMESTAMP": TS, "wsgi.input": object()},
    ]
    msg = Message()
    msg["X-Webhook-Signature"] = sig
    msg["X-Webhook-Timestamp"] = TS
    variants.append(msg)
    try:
        from werkzeug.datastructures import Headers

        variants.append(Headers([("X-Webhook-Signature", sig), ("X-Webhook-Timestamp", TS)]))
    except ImportError:  # pragma: no cover
        pass
    for headers in variants:
        assert isinstance(construct(b, headers), WebhookEvent), headers


def test_duplicate_and_non_ascii_headers_fail() -> None:
    b = envelope()
    sig = sign(b)
    dupes: list[Any] = [
        [("X-Webhook-Signature", sig), ("X-Webhook-Timestamp", TS), ("x-webhook-timestamp", TS)],
        {"X-Webhook-Signature": sig, "x-webhook-signature": sig, "X-Webhook-Timestamp": TS},
    ]
    msg = Message()
    msg["X-Webhook-Signature"] = sig
    msg["X-Webhook-Timestamp"] = TS
    msg["X-Webhook-Timestamp"] = TS
    dupes.append(msg)
    for headers in dupes:
        with pytest.raises(WebhookVerificationError) as info:
            construct(b, headers)
        assert info.value.reason == "duplicate_header"
    with pytest.raises(WebhookVerificationError) as info:
        construct(b, {"X-Webhook-Signature": sig, "X-Webhook-Timestamp": "2026-11-23T21:04:05.123Ζ"})
    assert info.value.reason == "non_ascii_header"


def test_parsed_body_and_empty_secret_are_verification_errors() -> None:
    with pytest.raises(WebhookVerificationError, match="raw request body") as info:
        construct(json.loads(envelope()), {"X-Webhook-Signature": "x", "X-Webhook-Timestamp": TS})
    assert info.value.reason == "invalid_raw_body"
    b = envelope()
    with pytest.raises(WebhookVerificationError) as info:
        Webhooks.construct_event(b, {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS}, "", now=NOW)
    assert info.value.reason == "invalid_secret"
    assert DEFAULT_WEBHOOK_TOLERANCE == 300.0


def test_signed_body_that_is_not_an_object() -> None:
    for body in (b"[1,2]", b"not json"):
        with pytest.raises(FinlightDecodeError):
            construct(body, {"X-Webhook-Signature": sign(body), "X-Webhook-Timestamp": TS})


def test_v3_body_without_link_is_a_decode_error() -> None:
    data = dict(ARTICLE)
    data.pop("link")
    b = envelope(data=data)
    with pytest.raises(FinlightDecodeError):
        construct(b, {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS})


def test_tolerance_and_clock() -> None:
    b = envelope()
    headers = {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS}
    late = parse_rfc3339("2026-11-23T21:14:05.123Z")
    with pytest.raises(WebhookVerificationError):
        Webhooks.construct_event(b, headers, SECRET, now=late)
    assert isinstance(Webhooks.construct_event(b, headers, SECRET, 900, now=lambda: late), WebhookEvent)


def test_verify_signature_alone() -> None:
    b = envelope()
    assert Webhooks.verify_signature(b, sign(b), TS, SECRET, now=NOW) is None
    with pytest.raises(WebhookVerificationError):
        Webhooks.verify_signature(b, sign(b).upper().replace("SHA256=", "sha256="), TS, SECRET, now=NOW)
    with pytest.raises(WebhookVerificationError):
        Webhooks.verify_signature(b, sign(b)[:-2], TS, SECRET, now=NOW)


def test_changed_fields_absent_and_is_test() -> None:
    b = envelope(eventId="evt_test0123", changedFields=...)
    event = construct(b, {"X-Webhook-Signature": sign(b), "X-Webhook-Timestamp": TS})
    assert event.is_test and event.changed_fields is None
