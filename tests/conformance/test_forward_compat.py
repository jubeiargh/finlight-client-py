"""F-01 .. F-04: unknown fields, unknown enum values, new envelope keys, unknown codes."""

from __future__ import annotations

import json

import pytest

from finlight_client import (
    FinlightApiError,
    RateLimitedError,
    _frames,
    raw_json,
    to_wire,
)
from finlight_client.articles import _article_envelope
from finlight_client.models import decode_article, decode_article_page, decode_webhook_event
from tests.support import load


@pytest.mark.parametrize("case", ["F-01"])
def test_unknown_fields(case: str) -> None:
    fx = load("fixtures/forward-compat/unknown-fields.json")
    article = decode_article(fx["wire"])
    assert to_wire(article) == fx["known"]
    raw = raw_json(article)
    assert raw["wordCount"] == fx["wire"]["wordCount"]
    assert raw["source"]["name"] == "Example News"
    assert "subtype" in raw["events"][0]


@pytest.mark.parametrize("case", ["F-02"])
def test_unknown_enum_values(case: str) -> None:
    fx = load("fixtures/forward-compat/unknown-enum-values.json")
    article = decode_article(fx["wire"])
    assert to_wire(article) == fx["wire"]
    assert article.source.type == "wire_service"
    assert article.sentiment.label == "mixed"
    assert article.companies[0].role == "guarantor"
    assert (article.events[0].type, article.events[0].direction, article.events[0].importance) == (
        "esg_controversy",
        "mixed",
        "extreme",
    )
    assert article.categories[1] == "synthetic-new-category"


@pytest.mark.parametrize("case", ["F-03"])
def test_envelope_keys(case: str) -> None:
    fx = load("fixtures/forward-compat/envelope-keys.json")
    kinds = set()
    for env in fx["envelopes"]:
        kind, wire = env["kind"], env["wire"]
        kinds.add(kind)
        if kind == "rest.search":
            page = decode_article_page(wire)
            assert len(page.articles) == 1 and page.pagination.has_more is False
        elif kind == "rest.article":
            assert _article_envelope(wire).id == wire["article"]["id"]
        elif kind == "webhook":
            event = decode_webhook_event(wire)
            assert event.event_id == wire["eventId"] and event.data.id == wire["data"]["id"]
            assert raw_json(event)["deliveryAttempt"] == 1
        elif kind == "ws.article":
            frame = _frames.decode_frame(json.dumps(wire))
            assert frame.type == _frames.ARTICLE and frame.kind == "created"
            assert decode_article(frame.data).id == wire["data"]["id"]
        elif kind == "ws.control":
            frame = _frames.decode_frame(json.dumps(wire))
            assert frame.type == _frames.PONG
        else:
            raise AssertionError(kind)
    assert kinds == {"rest.search", "rest.article", "webhook", "ws.article", "ws.control"}


@pytest.mark.parametrize("case", ["F-04"])
def test_unknown_events_and_codes(case: str, httpserver, make_client, sleeps) -> None:
    fx = load("fixtures/forward-compat/unknown-events-and-codes.json")
    for item in fx["items"]:
        kind = item["kind"]
        if kind == "webhook.event":
            event = decode_webhook_event(item["wire"])
            assert event.event == "article.retracted"
            continue
        httpserver.clear()
        httpserver.expect_request("/v3/articles/search", method="POST").respond_with_data(
            json.dumps(item["wire"]), status=item["status"], headers=item["headers"]
        )
        client = make_client()
        with pytest.raises(FinlightApiError) as info:
            client.articles.search(query="x")
        err = info.value
        assert len(httpserver.log) == 1, "not retried"
        assert err.status == item["status"] and err.code == item["wire"]["code"]
        assert err.request_id == item["wire"]["requestId"] and err.detail == item["wire"]["detail"]
        if kind == "problem.code":
            assert type(err) is FinlightApiError and err.api_kind == "other"
        elif kind == "problem.limitType":
            assert isinstance(err, RateLimitedError) and err.api_kind == "rate_limited"
            assert err.limit_type == item["wire"]["limitType"]
        else:
            raise AssertionError(kind)
    assert sleeps.calls == []
