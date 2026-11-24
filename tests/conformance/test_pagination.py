"""P-01 .. P-06: the cursor walk."""

from __future__ import annotations

import json
from typing import Any

import pytest
from werkzeug.wrappers import Response

from finlight_client import CursorMismatchError, FinlightValidationError
from tests.support import load, snake_args


def scripted(httpserver: Any, responses: list[dict[str, Any]]) -> None:
    queue = list(responses)

    def handler(request: Any) -> Response:
        resp = queue.pop(0)
        return Response(json.dumps(resp["body"]), status=resp["status"],
                        content_type=resp["headers"]["content-type"])

    httpserver.expect_request("/v3/articles/search", method="POST").respond_with_handler(handler)


@pytest.mark.parametrize("case", ["P-01"])
def test_three_pages(case: str, httpserver: Any, make_client: Any) -> None:
    fx = load("fixtures/pagination/three-pages.json")
    scripted(httpserver, [s["response"] for s in fx["steps"]])
    args = snake_args(fx["sdk"]["args"])
    sources = args["sources"]
    result = make_client().articles.search_all(**args)
    sources.append("mutated.example.org")  # the body is frozen at call time
    ids = [a.id for a in result]
    expected = [a["id"] for s in fx["steps"] for a in s["response"]["body"]["articles"]]
    assert ids == expected and len(ids) == 5
    sent = [entry[0].get_data() for entry in httpserver.log]
    assert len(sent) == 3
    assert [json.loads(b) for b in sent] == [s["request"]["body"] for s in fx["steps"]]
    for page, step in zip(sent[1:], fx["steps"][1:], strict=True):
        cursor = json.dumps(step["request"]["body"]["cursor"])
        assert page == sent[0][:-1] + b',"cursor":' + cursor.encode() + b"}"
    assert result.pages_fetched == 3 and result.next_cursor is None and not result.truncated
    with pytest.raises(FinlightValidationError):
        iter(result)


def test_p01_request_ids_differ_per_page(httpserver: Any, make_client: Any) -> None:
    fx = load("fixtures/pagination/three-pages.json")
    scripted(httpserver, [s["response"] for s in fx["steps"]])
    list(make_client().articles.search_all(**snake_args(fx["sdk"]["args"])).pages())
    ids = [entry[0].headers.get("X-Request-Id") for entry in httpserver.log]
    assert len(set(ids)) == 3


def test_p01_max_pages_stops_and_keeps_cursor(httpserver: Any, make_client: Any, caplog: Any) -> None:
    fx = load("fixtures/pagination/three-pages.json")
    scripted(httpserver, [s["response"] for s in fx["steps"]])
    result = make_client().articles.search_all(**snake_args(fx["sdk"]["args"]), max_pages=2)
    pages = list(result.pages())
    assert len(pages) == 2 and len(httpserver.log) == 2
    assert result.truncated
    assert result.next_cursor == fx["steps"][1]["response"]["body"]["pagination"]["nextCursor"]
    assert "max_pages" in caplog.text


PAGE_CASES = {
    "P-02": "resize-and-reproject.json",
    "P-03": "injected-to.json",
    "P-04": "injected-default-languages.json",
    "P-05": "changed-order.json",
    "P-06": "reordered-list.json",
}


@pytest.mark.parametrize("case", sorted(PAGE_CASES))
def test_page_rules(case: str, httpserver: Any, make_client: Any, sleeps: Any) -> None:
    fx = load(f"fixtures/pagination/{PAGE_CASES[case]}")
    scripted(httpserver, [fx["response"]])
    client = make_client()
    args = snake_args(fx["request"]["body"])
    if fx["response"]["status"] == 200:
        page = client.articles.search(**args)
        assert [a.id for a in page.articles] == [a["id"] for a in fx["response"]["body"]["articles"]]
    else:
        with pytest.raises(CursorMismatchError) as info:
            client.articles.search(**args)
        assert info.value.errors[0].field == "cursor"
        if case == "P-05":
            assert "publishedAt:desc" in info.value.detail and "publishedAt:asc" in info.value.detail
        assert len(httpserver.log) == 1 and sleeps.calls == []
    assert json.loads(httpserver.log[0][0].get_data()) == fx["request"]["body"]


def test_pager_never_injects_defaults(httpserver: Any, make_client: Any) -> None:
    """P-03/P-04 from the client side: later pages add nothing but the cursor."""
    fx = load("fixtures/pagination/three-pages.json")
    scripted(httpserver, [s["response"] for s in fx["steps"]])
    list(make_client().articles.search_all(**snake_args(fx["sdk"]["args"])))
    for entry in httpserver.log:
        body = json.loads(entry[0].get_data())
        assert "to" not in body and "languages" not in body
