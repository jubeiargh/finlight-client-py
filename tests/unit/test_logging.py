"""R-LOG-1: no key, secret or signature in logs, errors or reprs; no global handlers."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import traceback
from typing import Any

import pytest

from finlight_client import FinlightClient, FinlightConfig, FinlightError, Webhooks, WebhookVerificationError
from tests.support import FakeClock, WsServer, settle

SECRET_KEY = "sk_SECRET_TEST_KEY_8f2a91"
WEBHOOK_SECRET = "whsec_SECRET_value_771"


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("websockets.server"):
            return  # the in-process test server's own logs, not the SDK
        self.lines.append(f"{record.name}: {self.format(record)}")
        if record.exc_info:
            self.lines.append("".join(traceback.format_exception(*record.exc_info)))


@pytest.fixture
def collect() -> Any:
    handler = Collect()
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    logging.getLogger("finlight_client").setLevel(logging.DEBUG)
    yield handler
    root.removeHandler(handler)
    root.setLevel(old)
    logging.getLogger("finlight_client").setLevel(logging.NOTSET)


def texts_of(error: BaseException) -> str:
    return "\n".join([str(error), repr(error), "".join(traceback.format_exception(error))])


async def test_no_secrets_anywhere(collect: Any, httpserver: Any, ws_server: WsServer) -> None:
    seen: list[str] = []
    httpserver.expect_request("/v3/sources").respond_with_json(
        {"type": "t", "title": "Unauthorized", "status": 401, "code": "UNAUTHORIZED", "detail": "Invalid key"},
        status=401)
    client = FinlightClient(api_key=SECRET_KEY, base_url=httpserver.url_for("/"), wss_url=ws_server.url,
                            clock=FakeClock(), sleep=lambda s: None)
    seen += [repr(client), repr(client.config), str(client.config)]
    try:
        client.sources.list()
    except FinlightError as exc:
        seen.append(texts_of(exc))
    broken = FinlightClient(api_key=SECRET_KEY, base_url="http://127.0.0.1:9", sleep=lambda s: None, max_retries=1)
    try:
        broken.articles.search(query="x")
    except FinlightError as exc:
        seen.append(texts_of(exc))

    ws_server.reject_plan.append((401, '{"message":"Invalid API key"}'))
    try:
        async for _ in client.stream(query="x"):
            pass
    except FinlightError as exc:
        seen.append(texts_of(exc))
    stream = client.stream(query="x")
    task = asyncio.ensure_future(stream.__aiter__().__anext__())
    conn = await ws_server.next_connection()
    await conn.send({"event": "connection.error", "payloadVersion": 3, "data": {"code": "INTERNAL_ERROR", "message": "m"}})
    await settle()
    await stream.close()
    task.cancel()

    try:
        Webhooks.construct_event(b"{}", {"X-Webhook-Signature": "sha256=" + "ab" * 32,
                                         "X-Webhook-Timestamp": "2026-11-23T21:04:05.123Z"}, WEBHOOK_SECRET)
    except WebhookVerificationError as exc:
        seen.append(texts_of(exc))

    blob = "\n".join(seen + collect.lines)
    client_lines = collect.lines
    assert SECRET_KEY not in "\n".join(seen + client_lines)
    assert WEBHOOK_SECRET not in blob and "ab" * 32 not in blob
    assert not any("x-api-key" in line.lower() for line in client_lines)
    assert any("finlight" in line for line in collect.lines)  # the SDK does log, under its own name


def test_no_global_handlers_or_output(capsys: Any) -> None:
    root_handlers = list(logging.getLogger().handlers)
    sigint = signal.getsignal(signal.SIGINT)
    sigterm = signal.getsignal(signal.SIGTERM)
    hook = sys.excepthook
    FinlightClient(api_key="k").stream(query="x")
    FinlightConfig(api_key="k")
    assert logging.getLogger().handlers == root_handlers
    assert signal.getsignal(signal.SIGINT) == sigint and signal.getsignal(signal.SIGTERM) == sigterm
    assert sys.excepthook is hook
    assert any(isinstance(h, logging.NullHandler) for h in logging.getLogger("finlight_client").handlers)
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
