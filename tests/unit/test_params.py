"""R-REQ-1..3: only set keys are sent, shape checks run before any network call."""

from __future__ import annotations

import json
import locale
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from finlight_client import FinlightClient, FinlightValidationError

OFFLINE = dict(api_key="k", base_url="http://127.0.0.1:9", wss_url="ws://127.0.0.1:9", max_retries=0)


@pytest.fixture
def offline() -> FinlightClient:
    return FinlightClient(**OFFLINE)


BAD_SEARCH: list[dict[str, Any]] = [
    {"limit": 0}, {"limit": 101}, {"limit": True}, {"limit": "20"}, {"limit": 2.0},
    {"languages": []}, {"languages": "en"}, {"tickers": "AAPL"}, {"tickers": [1]},
    {"min_relevance": 1.5}, {"min_relevance": -0.1}, {"min_relevance": True}, {"min_relevance": "0.5"},
    {"include": ["content", "companies", "events", "content"]}, {"has_content": "true"},
    {"from_": datetime(2026, 1, 1)}, {"to": 1700000000}, {"query": 5},
]


@pytest.mark.parametrize("bad", BAD_SEARCH, ids=[str(b) for b in BAD_SEARCH])
def test_search_shape_errors_are_local(offline: FinlightClient, bad: dict[str, Any]) -> None:
    with pytest.raises(FinlightValidationError) as info:
        offline.articles.search(**bad)
    assert isinstance(info.value, ValueError)
    with pytest.raises(FinlightValidationError):
        offline.articles.search_all(**bad)  # checked at call time, before iteration


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.companies.get_many([]),
        lambda c: c.companies.get_many(list(range(1, 12))),
        lambda c: c.companies.get_many([0]),
        lambda c: c.companies.get_many([True]),
        lambda c: c.companies.get_many("1,2"),
        lambda c: c.companies.search("x" * 201),
        lambda c: c.companies.search("AAPL", mic="X" * 33),
        lambda c: c.companies.get("900001"),
        lambda c: c.articles.get_by_link(""),
        lambda c: c.articles.get(""),
        lambda c: c.articles.get("id", include=["content"] * 4),
        lambda c: c.stream(include=["content", "events", "companies", "x"]),
        lambda c: c.stream(tickers="NVDA"),
        lambda c: c.raw_stream(include_updates="yes"),
        lambda c: c.articles.search_all(max_pages=0),
    ],
)
def test_other_shape_errors_are_local(offline: FinlightClient, call: Any) -> None:
    with pytest.raises(FinlightValidationError):
        call(offline)


def test_unknown_keyword_names_the_key(offline: FinlightClient) -> None:
    for call in (offline.articles.search, offline.articles.search_all, offline.stream, offline.raw_stream):
        with pytest.raises(TypeError, match="event_type"):
            call(event_type=["mna"])


def test_source_types_are_search_only(offline: FinlightClient) -> None:
    for call in (offline.stream, offline.raw_stream):
        for name in ("source_types", "exclude_source_types"):
            with pytest.raises(TypeError, match=name):
                call(**{name: ["newswire"]})


def test_source_types_are_sent(httpserver: Any, make_client: Any) -> None:
    body = json.loads(body_for(httpserver, make_client, source_types=["newswire"], exclude_source_types=["blog"]))
    assert body == {"sourceTypes": ["newswire"], "excludeSourceTypes": ["blog"]}


def test_values_of_vocabularies_are_not_checked(httpserver: Any, make_client: Any) -> None:
    httpserver.expect_request("/v3/articles/search").respond_with_json(
        {"articles": [], "pagination": {"limit": 20, "returned": 0, "hasMore": False, "nextCursor": None}}
    )
    make_client().articles.search(event_types=["brand_new_type"], order_by="futureField", order="sideways")
    assert json.loads(httpserver.log[0][0].get_data()) == {
        "eventTypes": ["brand_new_type"], "orderBy": "futureField", "order": "sideways"}


def body_for(httpserver: Any, make_client: Any, **kwargs: Any) -> bytes:
    httpserver.expect_request("/v3/articles/search").respond_with_json(
        {"articles": [], "pagination": {"limit": 20, "returned": 0, "hasMore": False, "nextCursor": None}}
    )
    make_client().articles.search(**kwargs)
    data: bytes = httpserver.log[-1][0].get_data()
    return data


def test_explicit_false_and_zero_like_values_are_sent(httpserver: Any, make_client: Any) -> None:
    assert json.loads(body_for(httpserver, make_client, has_content=False, min_relevance=0)) == {
        "hasContent": False, "minRelevance": 0}


def test_empty_include_and_none_are_left_out(httpserver: Any, make_client: Any) -> None:
    assert body_for(httpserver, make_client, include=[], query=None, tickers=None) == b"{}"


def test_time_values(httpserver: Any, make_client: Any) -> None:
    berlin = timezone(timedelta(hours=1))
    body = json.loads(body_for(
        httpserver, make_client,
        from_=datetime(2026, 11, 1, 1, 2, 3, 456789, tzinfo=berlin),
        to=date(2026, 11, 23),
    ))
    assert body == {"from": "2026-11-01T00:02:03.456Z", "to": "2026-11-23"}
    raw = json.loads(body_for(httpserver, make_client, from_="2026-11-01", to="yesterday"))
    assert raw == {"from": "2026-11-01", "to": "yesterday"}  # caller strings go out unchanged


@pytest.mark.parametrize("name", ["de_DE.UTF-8", "tr_TR.UTF-8"])
def test_formatting_ignores_the_system_locale(httpserver: Any, make_client: Any, name: str) -> None:
    old = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, name)
    except locale.Error:
        pytest.skip(f"locale {name} not installed")
    try:
        body = body_for(
            httpserver, make_client, min_relevance=0.5, include=["content"],
            from_=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc), query="TITLE:İstanbul",
        )
        assert json.loads(body) == {
            "query": "TITLE:İstanbul", "from": "2026-01-02T03:04:05.000Z", "minRelevance": 0.5, "include": ["content"]}
    finally:
        locale.setlocale(locale.LC_ALL, old)


def test_get_by_link_encodes_once(httpserver: Any, make_client: Any) -> None:
    link = "https://example.com/a b?x=1&y=%20"
    httpserver.expect_request("/v3/articles/by-link").respond_with_json(
        {"article": {"id": "a", "link": link, "title": "t", "source": {"domain": "example.com"}}}
    )
    make_client().articles.get_by_link(link, include=["content", "events"])
    request = httpserver.log[0][0]
    assert request.args.get("link") == link
    assert request.args.get("include") == "content,events"
    assert "include[]" not in request.query_string.decode()


def test_validation_errors_name_the_param(offline: FinlightClient) -> None:
    cases = [
        (lambda: offline.articles.search(limit=0), "limit"),
        (lambda: offline.articles.search(from_=datetime(2026, 1, 1)), "from_"),
        (lambda: offline.articles.get("id", include=["a", "b", "c", "d"]), "include"),
        (lambda: offline.companies.get_many([]), "ids"),
        (lambda: offline.companies.search("x" * 201), "q"),
        (lambda: offline.stream(takeover="yes"), "takeover"),
    ]
    for call, param in cases:
        with pytest.raises(FinlightValidationError) as info:
            call()
        assert info.value.param == param
