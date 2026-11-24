"""R-01 .. R-12: what the SDK puts on the wire, checked on a real local HTTP server."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import pytest

from finlight_client import CompanyRecord, FinlightClient, cache_info
from tests.support import KIT, fixtures, load, snake_args

HTTP_CASES = [(cid, p) for cid, p in fixtures("fixtures/requests") if p.name not in (
    "ws-subscribe-enriched.json", "ws-subscribe-raw.json")]


def serve(httpserver: Any, fx: dict[str, Any]) -> None:
    resp = fx["response"]
    body = resp["body"]
    data = "" if body is None else json.dumps(body)
    headers = {k: v for k, v in resp["headers"].items() if k.lower() != "content-type"}
    content_type = resp["headers"].get("content-type")
    httpserver.expect_request(fx["request"]["path"], method=fx["request"]["method"]).respond_with_data(
        data, status=resp["status"], headers=headers, content_type=content_type
    )


def call(client: FinlightClient, sdk: dict[str, Any]) -> Any:
    method, args = sdk["method"], dict(sdk["args"])
    if method == "articles.search":
        return client.articles.search(**snake_args(args))
    if method == "articles.get":
        return client.articles.get(args.pop("id"), **snake_args(args))
    if method == "articles.getByLink":
        return client.articles.get_by_link(args.pop("link"), **snake_args(args))
    if method == "companies.search":
        return client.companies.search(args.pop("q"), **snake_args(args))
    if method == "companies.getMany":
        return client.companies.get_many(args["ids"])
    if method == "companies.get":
        return client.companies.get(args.pop("companyId"), **snake_args(args))
    if method == "sources.list":
        return client.sources.list()
    raise AssertionError(method)


def check_request(httpserver: Any, fx: dict[str, Any]) -> Any:
    assert len(httpserver.log) == 1
    request = httpserver.log[0][0]
    want = fx["request"]
    assert request.method == want["method"]
    assert request.path == want["path"]
    got_query = parse_qsl(request.query_string.decode(), keep_blank_values=True)
    want_query = parse_qsl(want.get("query", ""), keep_blank_values=True)
    assert got_query == want_query
    assert "include[]" not in request.query_string.decode()
    for name, value in want["headers"].items():
        if name.upper() == "X-API-KEY":
            assert request.headers.get(name) == value
        elif name.lower() == "if-none-match":
            assert request.headers.get(name) == value
    if "body" in want:
        assert request.headers.get("Content-Type") == "application/json"
        assert json.loads(request.get_data()) == want["body"]
    return request


@pytest.mark.parametrize(("case", "path"), HTTP_CASES, ids=[c for c, _ in HTTP_CASES])
def test_request(case: str, path: Path, httpserver: Any, make_client: Any) -> None:
    fx = load(f"fixtures/requests/{path.name}")
    client = make_client(api_key=fx["request"]["headers"]["X-API-KEY"])
    serve(httpserver, fx)

    if case == "R-12":
        with pytest.raises(TypeError, match="event_type"):
            call(client, fx["sdk"])
        assert httpserver.log == []
        return

    result = call(client, fx["sdk"])
    request = check_request(httpserver, fx)
    body = fx["response"]["body"]

    if case in ("R-01", "R-03"):
        assert request.get_data() == json.dumps(fx["request"]["body"], separators=(",", ":")).encode()
        assert [a.id for a in result.articles] == [a["id"] for a in body["articles"]]
        assert result.pagination.has_more is False and result.pagination.next_cursor is None
    elif case == "R-02":
        assert [a.id for a in result.articles] == [a["id"] for a in body["articles"]]
        assert result.articles[0].companies_present and result.articles[0].content_present
        sent = json.loads(request.get_data())
        assert sent["sourceTypes"] == ["newswire", "financial_media"]
        assert sent["excludeSourceTypes"] == ["press_release"]
    elif case in ("R-04", "R-05"):
        assert result.id == body["article"]["id"]
        assert set(result.model_fields_set) >= {"id", "link"}
    elif case in ("R-06", "R-07"):
        assert [c.company_id for c in result] == [c["companyId"] for c in body["companies"]]
        if case == "R-07":
            private = result[1]
            assert private.primary_listing is None and private.listings == [] and private.isins == []
    elif case == "R-08":
        assert isinstance(result, CompanyRecord)
        info = cache_info(result)
        assert info is not None and not info.not_modified
        assert info.etag == fx["response"]["headers"]["etag"]
        assert info.cache_control == fx["response"]["headers"]["cache-control"]
        mics = [listing.mic for listing in result.listings]
        assert len(mics) == len(set(mics))
        assert result.listings[0].mic == result.primary_listing.mic
    elif case == "R-09":
        assert result is None  # 304 with a caller-managed ETag: not modified
    elif case == "R-10":
        assert all(s.has_content is not None for s in result)
        assert {s.domain: s.is_custom for s in result}["custom.example.net"] is True
        assert result[1].is_default is False and result[2].is_default is True
        assert [s.type for s in result] == [s["type"] for s in body["sources"]]
    elif case == "R-11":
        assert all(s.has_content is None for s in result)
        assert all("has_content" not in s.model_fields_set for s in result)
    else:
        raise AssertionError(f"no assertions for {case}")


def test_r02_native_datetimes_serialize_like_the_kit(httpserver: Any, make_client: Any) -> None:
    fx = load("fixtures/requests/search-all-parameters.json")
    serve(httpserver, fx)
    args = snake_args(fx["sdk"]["args"])
    args["from_"] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    args["to"] = datetime(2026, 11, 23, tzinfo=timezone.utc)
    make_client().articles.search(**args)
    assert json.loads(httpserver.log[0][0].get_data()) == fx["request"]["body"]


def test_r09_client_cache_serves_record_on_304(httpserver: Any, make_client: Any) -> None:
    ok = load("fixtures/requests/companies-get.json")
    nm = load("fixtures/requests/companies-get-not-modified.json")
    client = make_client()
    serve(httpserver, ok)
    first = client.companies.get(900001)
    httpserver.clear()
    serve(httpserver, nm)
    second = client.companies.get(900001)
    assert httpserver.log[0][0].headers.get("If-None-Match") == ok["response"]["headers"]["etag"]
    assert second is first and cache_info(second).not_modified


def test_kit_files_present() -> None:
    assert (KIT / "fixtures/requests/ws-subscribe-enriched.json").is_file()
