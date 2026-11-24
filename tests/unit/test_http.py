"""R-ERR-1, R-RETRY-1, R-CONFIG-1: transport, retries, request ids, headers, limits."""

from __future__ import annotations

import json
import socket
import time
import uuid
from typing import Any

import pytest
import requests
from werkzeug.wrappers import Response

from finlight_client import (
    FinlightApiError,
    FinlightClient,
    FinlightConfig,
    FinlightDecodeError,
    FinlightNetworkError,
    FinlightTimeoutError,
    FinlightValidationError,
    InternalServerError,
    NotFoundError,
    RateLimitedError,
    __version__,
)

EMPTY_PAGE = {"articles": [], "pagination": {"limit": 20, "returned": 0, "hasMore": False, "nextCursor": None}}
BURST = {"type": "https://docs.finlight.me/errors/rate-limited", "title": "Too many requests", "status": 429,
         "detail": "Throttling Exception: Exceeded rate limit of 5 requests per 10 seconds.",
         "code": "RATE_LIMITED", "requestId": "r", "limitType": "burst"}
LEGACY_BURST = {k: v for k, v in BURST.items() if k != "limitType"}
LEGACY_MONTHLY = dict(LEGACY_BURST, detail="Throttling Exception: Exceeded token limit of 1000 for the current period.")


def sequence(httpserver: Any, responses: list[tuple[int, Any, dict[str, str]]], path: str = "/v3/articles/search") -> None:
    queue = list(responses)

    def handler(request: Any) -> Response:
        status, body, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        ctype = headers.pop("content-type", "application/problem+json" if status >= 400 else "application/json")
        return Response(json.dumps(body) if not isinstance(body, str) else body, status=status,
                        headers=headers, content_type=ctype)

    httpserver.expect_request(path).respond_with_handler(handler)


def test_rest_headers(httpserver: Any, make_client: Any) -> None:
    sequence(httpserver, [(200, EMPTY_PAGE, {})])
    make_client(api_key="sk_test").articles.search()
    request = httpserver.log[0][0]
    assert request.headers["X-API-KEY"] == "sk_test"
    assert request.headers["User-Agent"] == f"finlight-client-python/{__version__}"
    assert request.headers["x-client-version"] == __version__ and not __version__.startswith("v")
    uuid.UUID(request.headers["X-Request-Id"])
    assert request.headers["Content-Type"] == "application/json"


@pytest.mark.parametrize("suffix", ["", "/"])
def test_base_url_with_or_without_trailing_slash(httpserver: Any, make_client: Any, suffix: str) -> None:
    sequence(httpserver, [(200, EMPTY_PAGE, {})])
    make_client(base_url=httpserver.url_for("/").rstrip("/") + suffix).articles.search()
    assert httpserver.log[0][0].path == "/v3/articles/search"


def test_5xx_retried_with_same_request_id(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(500, {"code": "INTERNAL_ERROR", "type": "t", "status": 500}, {}),
                          (503, "<html>busy</html>", {"content-type": "text/html"}),
                          (200, EMPTY_PAGE, {})])
    page = make_client().articles.search(query="x")
    assert page.articles == []
    ids = {entry[0].headers["X-Request-Id"] for entry in httpserver.log}
    assert len(httpserver.log) == 3 and len(ids) == 1
    assert sleeps.calls == [0.25, 0.5]  # 0.5 * 2^n, jitter factor 0.5 with random() = 0


def test_retries_are_capped_at_three(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(500, {"code": "INTERNAL_ERROR", "type": "t"}, {})])
    with pytest.raises(InternalServerError):
        make_client().articles.search()
    assert len(httpserver.log) == 4 and len(sleeps.calls) == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_never_retried(httpserver: Any, make_client: Any, sleeps: Any, status: int) -> None:
    sequence(httpserver, [(status, {"statusCode": status, "message": "nope"}, {"content-type": "application/json"})])
    with pytest.raises(FinlightApiError) as info:
        make_client().articles.search()
    assert info.value.status == status and len(httpserver.log) == 1 and sleeps.calls == []


def test_burst_without_retry_after_waits_ten_seconds(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, BURST, {}), (200, EMPTY_PAGE, {})])
    make_client().articles.search()
    assert sleeps.calls == [10.0] and len(httpserver.log) == 2


def test_burst_retry_after_is_used(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, BURST, {"Retry-After": "3"}), (200, EMPTY_PAGE, {})])
    make_client().articles.search()
    assert sleeps.calls == [3.0]


def test_burst_retry_can_be_switched_off(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, BURST, {}), (200, EMPTY_PAGE, {})])
    with pytest.raises(RateLimitedError):
        make_client(retry_on_burst="off").articles.search()
    assert len(httpserver.log) == 1 and sleeps.calls == []


def test_burst_retried_only_once(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, BURST, {})])
    with pytest.raises(RateLimitedError) as info:
        make_client().articles.search()
    assert info.value.limit_type == "burst" and len(httpserver.log) == 2


@pytest.mark.parametrize(("body", "kind"), [(LEGACY_BURST, "burst"), (LEGACY_MONTHLY, "monthly"),
                                             (dict(LEGACY_BURST, detail="slow down"), "unknown")])
def test_429_without_limit_type_falls_back_to_detail(httpserver: Any, make_client: Any, sleeps: Any,
                                                      body: dict[str, Any], kind: str) -> None:
    sequence(httpserver, [(429, body, {})])
    with pytest.raises(RateLimitedError) as info:
        make_client().articles.search()
    assert info.value.limit_type == kind
    assert len(httpserver.log) == (2 if kind == "burst" else 1)


def test_cancel_during_burst_wait_is_not_retried(httpserver: Any, make_client: Any) -> None:
    sequence(httpserver, [(429, BURST, {}), (200, EMPTY_PAGE, {})])

    def interrupted_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        make_client(sleep=interrupted_sleep).articles.search()
    assert len(httpserver.log) == 1


def test_total_timeout_caps_the_burst_wait(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, BURST, {"Retry-After": "9"}), (200, EMPTY_PAGE, {})])
    with pytest.raises(RateLimitedError):
        make_client(total_timeout=5.0).articles.search()
    assert sleeps.calls == [] and len(httpserver.log) == 1


def test_network_error_is_wrapped_and_retried(sleeps: Any) -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    client = FinlightClient(api_key="k", base_url=f"http://127.0.0.1:{port}", sleep=sleeps, random=lambda: 0.0)
    with pytest.raises(FinlightNetworkError) as info:
        client.articles.search()
    assert isinstance(info.value.__cause__, requests.exceptions.ConnectionError)
    assert not isinstance(info.value, requests.exceptions.RequestException)
    assert len(sleeps.calls) == 3


def test_attempt_timeout(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    def slow(request: Any) -> Response:
        time.sleep(0.4)
        return Response(json.dumps(EMPTY_PAGE), content_type="application/json")

    httpserver.expect_request("/v3/articles/search").respond_with_handler(slow)
    with pytest.raises(FinlightTimeoutError) as info:
        make_client(timeout=0.1, max_retries=1).articles.search()
    assert isinstance(info.value, TimeoutError) and isinstance(info.value, FinlightNetworkError)
    assert len(sleeps.calls) == 1


def test_response_size_limit(httpserver: Any, make_client: Any) -> None:
    sequence(httpserver, [(200, {"articles": [], "pagination": {}, "pad": "x" * 5000}, {})])
    with pytest.raises(FinlightDecodeError):
        make_client(max_response_bytes=1000).articles.search()


def test_redirects_are_not_followed(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    httpserver.expect_request("/v3/sources").respond_with_data("", status=302, headers={"Location": "http://evil.example/"})
    with pytest.raises(FinlightApiError) as info:
        make_client().sources.list()
    assert info.value.status == 302 and len(httpserver.log) == 1


def test_not_found_is_an_error_not_an_empty_result(httpserver: Any, make_client: Any) -> None:
    httpserver.expect_request("/v3/articles/nope").respond_with_json(
        {"type": "https://docs.finlight.me/errors/not-found", "title": "Not found", "status": 404,
         "detail": "No article with id 'nope'.", "code": "NOT_FOUND", "requestId": "x"}, status=404)
    with pytest.raises(NotFoundError):
        make_client().articles.get("nope")


def test_injected_session_is_used_and_never_closed(httpserver: Any) -> None:
    sequence(httpserver, [(200, EMPTY_PAGE, {})])
    session = requests.Session()
    closed: list[bool] = []
    session.close = lambda: closed.append(True)  # type: ignore[method-assign]
    with FinlightClient(api_key="k", base_url=httpserver.url_for("/"), session=session) as client:
        client.articles.search()
    assert closed == []


def test_own_session_closed_with_context_manager(httpserver: Any) -> None:
    with FinlightClient(api_key="k", base_url=httpserver.url_for("/")) as client:
        session = client._http._session
    assert session.adapters == {} or all(a.max_retries.total == 0 for a in session.adapters.values())


def test_config_validation_and_overrides() -> None:
    for bad in ("", "   "):
        with pytest.raises(FinlightValidationError):
            FinlightClient(api_key=bad)
    with pytest.raises(FinlightValidationError):
        FinlightClient()
    with pytest.raises(FinlightValidationError):
        FinlightClient(api_key="k", retry_on_burst="twice")
    with pytest.raises(FinlightValidationError):
        FinlightClient(api_key="k", wss_url="https://wss.example")
    with pytest.raises(FinlightValidationError):
        FinlightClient(api_key="k", wss_url="wss://wss.example?apiKey=k")
    cfg = FinlightConfig(api_key="k")
    assert (cfg.base_url, cfg.wss_url) == ("https://api.finlight.me", "wss://wss.finlight.me")
    assert cfg.ws_url(raw=True) == "wss://wss.finlight.me/raw"
    assert FinlightConfig(api_key="k", wss_url="wss://x.example/").ws_url(raw=True) == "wss://x.example/raw"
    client = FinlightClient(config=cfg, max_pages=3)
    assert client.config.max_pages == 3 and client.config.api_key == "k"


def test_monthly_429_ends_search_all_at_once(httpserver: Any, make_client: Any, sleeps: Any) -> None:
    sequence(httpserver, [(429, dict(BURST, limitType="monthly",
                                     detail="Throttling Exception: Exceeded token limit of 1000 for the current period."), {})])
    with pytest.raises(RateLimitedError) as info:
        list(make_client().articles.search_all(query="x"))
    assert info.value.limit_type == "monthly" and len(httpserver.log) == 1 and sleeps.calls == []
