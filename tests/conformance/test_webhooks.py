"""W-01 .. W-16: webhook verification and decoding."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from finlight_client import WebhookEvent, Webhooks, WebhookVerificationError, WrongPayloadVersion
from finlight_client._timeutil import parse_rfc3339
from tests.support import fixtures, load

CASES = fixtures("fixtures/webhook")


def body_of(fx: dict) -> bytes:
    return base64.b64decode(fx["request"]["rawBodyBase64"])


@pytest.mark.parametrize(("case", "path"), CASES, ids=[c for c, _ in CASES])
def test_webhook(case: str, path: Path) -> None:
    fx = load(f"fixtures/webhook/{path.name}")
    raw = body_of(fx)
    assert raw.decode("utf-8") == fx["request"]["rawBody"]
    headers = fx["request"]["headers"]
    now = parse_rfc3339(fx["verify"]["now"])
    tolerance = fx["verify"]["toleranceSeconds"]
    expect = fx["expect"]

    def run(body: object) -> object:
        return Webhooks.construct_event(body, headers, fx["secret"], tolerance, now=now)

    if expect["outcome"] == "event":
        for body in (raw, raw.decode("utf-8")):  # bytes and the UTF-8 string give the same result
            event = run(body)
            assert isinstance(event, WebhookEvent)
            want = expect["event"]
            assert event.event_id == want["eventId"] and event.event == want["event"]
            assert event.occurred_at == want["occurredAt"]
            assert event.subscription_id == want["subscriptionId"]
            assert event.is_test is want["isTest"]
            assert event.data.link == want["link"]
            assert event.changed_fields == want.get("changedFields")
            assert event.payload_version == 3
        if case == "W-03":
            assert not event.data.content_present
        if case == "W-04":
            assert event.data.available_at is None and event.occurred_at == event.data.first_seen_at
            for flag in ("content_present", "sentiment_present", "companies_present", "events_present"):
                assert getattr(event.data, flag) is False
        return

    if expect["error"] == "PayloadVersionMismatch":
        # The rules make this a result (WrongPayloadVersion), not an exception.
        result = run(raw)
        assert isinstance(result, WrongPayloadVersion)
        assert result.version == 2
        assert result.payload_version == expect["receivedPayloadVersion"]
        assert result.payload_version_present is False
        assert result.link == expect["link"]
        assert isinstance(result.raw, dict) and result.raw["link"] == expect["link"]
        return

    assert expect["error"] == "WebhookSignatureError"
    with pytest.raises(WebhookVerificationError) as info:
        run(raw)
    assert info.value.reason == expect["reason"]
    # The two-string variant fails the same way.
    sig = next((v for k, v in headers.items() if k.lower() == "x-webhook-signature"), None)
    ts = next((v for k, v in headers.items() if k.lower() == "x-webhook-timestamp"), None)
    with pytest.raises(WebhookVerificationError):
        Webhooks.construct_event_from_values(raw, sig, ts, fx["secret"], tolerance=tolerance, now=now)
