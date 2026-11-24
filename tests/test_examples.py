"""R-TEST-1: the five standard examples run against the local mocks."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import http.client
import importlib
import json
import re
import sys
import threading
from datetime import datetime, timezone
from typing import Any

import pytest

from finlight_client._timeutil import format_datetime
from tests.support import ROOT, WsServer, load

sys.path.insert(0, str(ROOT / "examples"))


def example(name: str) -> Any:
    return importlib.import_module(name)


@pytest.fixture
def rest(httpserver: Any, monkeypatch: Any) -> Any:
    def body(name: str) -> Any:
        return load(f"fixtures/requests/{name}")["response"]["body"]

    httpserver.expect_request("/v3/articles/search").respond_with_json(body("search-minimal.json"))
    httpserver.expect_request("/v3/articles/by-link").respond_with_json(body("get-by-link.json"))
    httpserver.expect_request("/v3/articles/does-not-exist").respond_with_json(
        load("fixtures/errors/not-found-id.json")["response"]["body"], status=404,
        content_type="application/problem+json")
    httpserver.expect_request(re.compile(r"^/v3/articles/[^/]+$")).respond_with_json(body("get-by-id.json"))
    httpserver.expect_request("/v3/companies").respond_with_json(body("companies-search.json"))
    httpserver.expect_request(re.compile(r"^/v3/companies/\d+$")).respond_with_json(
        body("companies-get.json"), headers={"ETag": '"abc"'})
    httpserver.expect_request("/v3/sources").respond_with_json(body("sources-list-full.json"))
    monkeypatch.setenv("FINLIGHT_API_KEY", "sk_example")
    monkeypatch.setenv("FINLIGHT_BASE_URL", httpserver.url_for("/"))
    return httpserver


def test_search_example(rest: Any, capsys: Any) -> None:
    example("search").main()
    assert "more pages: False" in capsys.readouterr().out


def test_search_all_example(rest: Any, capsys: Any) -> None:
    example("search_all").main()
    assert "5 articles from 1 pages" in capsys.readouterr().out


def test_lookup_example(rest: Any, capsys: Any) -> None:
    example("lookup").main()
    out = capsys.readouterr().out
    assert "by id:" in out and "not found:" in out and "etag:" in out and "3 sources" in out


async def test_stream_example(ws_server: WsServer, monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setenv("FINLIGHT_API_KEY", "sk_example")
    monkeypatch.setenv("FINLIGHT_WSS_URL", ws_server.url)
    frames = load("fixtures/requests/ws-subscribe-enriched.json")["server"]["frames"]
    task = asyncio.ensure_future(example("stream").main(max_events=1))
    conn = await ws_server.next_connection()
    subscribe = await conn.recv()
    assert subscribe["payloadVersion"] == 3 and subscribe["include"] == ["companies", "events"]
    for frame in frames:
        await conn.send(frame)
    await asyncio.wait_for(task, 5)
    assert "created EU8JwpsZ8iJehuyPZjMqRz" in capsys.readouterr().out


def test_webhook_example(monkeypatch: Any) -> None:
    secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    module = example("webhook_endpoint")
    monkeypatch.setattr(module, "SECRET", secret)
    handled: list[Any] = []
    monkeypatch.setattr(module, "process", lambda kind, item: handled.append((kind, item)))
    server = module.make_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    def post(body: bytes, *, good: bool = True) -> int:
        ts = format_datetime(datetime.now(timezone.utc))
        sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/hook", body=body, headers={
            "Content-Type": "application/json", "X-Webhook-Timestamp": ts,
            "X-Webhook-Signature": "sha256=" + (sig if good else "0" * 64)})
        status = conn.getresponse().status
        conn.close()
        return status

    try:
        envelope = {"eventId": "evt_test0123456789abcdef01", "event": "article.created",
                    "occurredAt": "2026-11-23T21:04:05.123Z", "payloadVersion": 3, "subscriptionId": "s",
                    "data": load("fixtures/decode/full-article.json")["wire"]}
        body = json.dumps(envelope, ensure_ascii=False).encode()
        assert post(body) == 204
        assert post(body) == 204  # duplicate: answered, not processed again
        assert post(json.dumps({"link": "https://x.example/a", "title": "t"}).encode()) == 204
        assert post(body, good=False) == 400
        module.work.join()
        kinds = [k for k, _ in handled]
        assert kinds == ["event", "legacy"]
        assert handled[0][1].is_test
    finally:
        server.shutdown()
        server.server_close()
