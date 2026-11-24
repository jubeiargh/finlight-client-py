"""R-WS-2, R-WS-4..6: stream lifecycle, hooks, dedupe across reconnects, refusals."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

import pytest

from finlight_client import (
    AdmittedInfo,
    FinlightApiError,
    FinlightClient,
    FinlightConfig,
    FinlightValidationError,
    ForbiddenError,
    QuotaWaitInfo,
    ReconnectInfo,
    StreamEvent,
)
from tests.support import FakeClock, WsServer, load, settle

ARTICLE = load("fixtures/decode/full-article.json")["wire"]
RAW_ARTICLE = load("fixtures/decode/raw-skeleton.json")["wire"]
ADMITTED = {"event": "connection.admitted", "payloadVersion": 3,
            "data": {"leaseId": "l1", "serverNow": 1795467845123, "clientNonce": "n"}}


def frame(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "payloadVersion": 3, "data": data}


def make(server: WsServer, clock: FakeClock, **options: Any) -> FinlightClient:
    return FinlightClient(api_key="k", wss_url=server.url, clock=clock, random=lambda: 0.0,
                          nonce_factory=lambda: "n", **options)


class Consumer:
    def __init__(self, stream: Any) -> None:
        self.stream = stream
        self.items: list[StreamEvent] = []
        self.error: BaseException | None = None
        self.task = asyncio.ensure_future(self._run())

    async def _run(self) -> None:
        try:
            async for event in self.stream:
                self.items.append(event)
        except Exception as exc:  # noqa: BLE001
            self.error = exc

    async def wait_items(self, n: int) -> None:
        for _ in range(400):
            if len(self.items) >= n or self.task.done():
                break
            await asyncio.sleep(0.005)
        assert len(self.items) >= n, self.items


def test_default_intervals() -> None:
    cfg = FinlightConfig(api_key="k")
    assert (cfg.ping_interval, cfg.watchdog_timeout, cfg.rotation_interval) == (25.0, 60.0, 115 * 60.0)
    assert cfg.max_message_bytes == 32 * 1024 * 1024 and cfg.connect_timeout == 30.0
    assert (cfg.reconnect_base_delay, cfg.reconnect_max_delay, cfg.long_backoff) == (1.0, 30.0, 60.0)
    assert cfg.company_cache_size == 256 and cfg.search_failed_threshold == 5
    assert cfg.dedupe_cache_size == 1000 and cfg.max_pages == 10 and cfg.max_retries == 3
    assert cfg.retry_on_burst == "once" and cfg.burst_wait == 10.0
    assert not hasattr(cfg, "takeover")  # a stream option, not a config key
    assert cfg.quota_reconnect is True and cfg.quota_reconnect_interval == 3600.0


async def test_stop_closes_socket_with_1000_and_leaves_nothing(ws_server: WsServer, fake_clock: FakeClock) -> None:
    before = asyncio.all_tasks()
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.recv()
    await conn.send(ADMITTED)
    await settle()
    await stream.close()
    await asyncio.wait_for(consumer.task, 3)
    await asyncio.wait_for(conn.closed.wait(), 3)
    assert conn.ws.close_code == 1000
    assert fake_clock.pending() == 0
    await settle()
    leftover = [t for t in asyncio.all_tasks() - before if t is not asyncio.current_task() and not t.done()]
    assert leftover == []


async def test_breaking_out_of_the_loop_closes(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")

    async def run() -> None:
        async for _ in stream:
            break

    task = asyncio.ensure_future(run())
    conn = await ws_server.next_connection()
    await conn.recv()
    await conn.send(frame("article.created", ARTICLE))
    await asyncio.wait_for(task, 3)
    await asyncio.wait_for(conn.closed.wait(), 3)
    assert stream._closed and fake_clock.pending() == 0


async def test_async_with_closes(ws_server: WsServer, fake_clock: FakeClock) -> None:
    async with make(ws_server, fake_clock).stream(query="x") as stream:
        iterator = stream.__aiter__()
        pending = asyncio.ensure_future(iterator.__anext__())
        conn = await ws_server.next_connection()
        await conn.recv()
        await conn.send(frame("article.created", ARTICLE))
        assert (await asyncio.wait_for(pending, 3)).data.id == ARTICLE["id"]
    await asyncio.wait_for(conn.closed.wait(), 3)
    with pytest.raises(FinlightValidationError):
        stream.__aiter__()
    assert stream.closed


async def test_cancellation_propagates_and_closes(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    consumer.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer.task
    await asyncio.wait_for(conn.closed.wait(), 3)
    assert stream._closed


async def test_hook_errors_do_not_stop_the_stream(ws_server: WsServer, fake_clock: FakeClock) -> None:
    seen: list[Any] = []

    def broken(*args: Any) -> None:
        seen.append(args)
        raise RuntimeError("user bug")

    async def async_hook(*args: Any) -> None:
        seen.append(args)
        raise RuntimeError("async user bug")

    stream = make(ws_server, fake_clock).stream(query="x", on_admitted=broken, on_error=async_hook)
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.send(ADMITTED)
    await conn.send({"event": "connection.error", "payloadVersion": 3,
                     "data": {"code": "INTERNAL_ERROR", "message": "Message processing failed"}})
    await conn.send(frame("article.created", ARTICLE))
    await consumer.wait_items(1)
    assert consumer.error is None
    assert isinstance(seen[0][0], AdmittedInfo) and seen[0][0].lease_id == "l1"
    assert seen[1][0].code == "INTERNAL_ERROR"
    await stream.close()


async def test_raw_reconnect_reports_first_seen_and_dedupe_survives(ws_server: WsServer, fake_clock: FakeClock) -> None:
    reconnects: list[Any] = []
    stream = make(ws_server, fake_clock).raw_stream(query="x", on_reconnect=reconnects.append)
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.recv()
    await conn.send(ADMITTED)
    await conn.send(frame("article.created", RAW_ARTICLE))
    await consumer.wait_items(1)
    await conn.close(1001)
    await settle()
    for _ in range(10):
        if len(ws_server.dials) > 1:
            break
        await fake_clock.advance(0.5)
    conn2 = await ws_server.next_connection()
    assert (await conn2.recv())["query"] == "x"
    await conn2.send(ADMITTED)
    await conn2.send(frame("article.created", RAW_ARTICLE))  # replayed: must not come twice
    other = copy.deepcopy(RAW_ARTICLE)
    other["id"], other["link"] = "other-id", "https://news.example.com/other"
    await conn2.send(frame("article.created", other))
    await consumer.wait_items(2)
    await settle(0.05)
    assert [i.data.id for i in consumer.items] == [RAW_ARTICLE["id"], "other-id"]
    assert reconnects == [ReconnectInfo(RAW_ARTICLE["firstSeenAt"], "closed", 2)]
    assert stream.last_seen_at == RAW_ARTICLE["firstSeenAt"]
    await stream.close()


async def test_enriched_last_seen_prefers_available_at(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    late = copy.deepcopy(ARTICLE)
    late["availableAt"] = None
    late["id"] = "late"
    late["firstSeenAt"] = "2026-09-18T13:00:00.000Z"
    await conn.send(frame("article.created", ARTICLE))
    await conn.send(frame("article.updated", late))
    await consumer.wait_items(2)
    assert stream.last_seen_at == "2026-09-18T13:00:00.000Z"
    await stream.close()


async def test_v2_send_article_is_never_an_article(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.send({"action": "sendArticle", "data": {"link": "l", "title": "t"}})
    await conn.send({"action": "admit", "leaseId": "l", "serverNow": 1, "clientNonce": "n"})
    await conn.send(frame("article.created", ARTICLE))
    await consumer.wait_items(1)
    assert [i.kind for i in consumer.items] == ["created"]
    await stream.close()


async def test_two_streams_on_one_client(ws_server: WsServer, fake_clock: FakeClock) -> None:
    client = make(ws_server, fake_clock)
    a, b = Consumer(client.stream(query="a")), Consumer(client.raw_stream(query="b"))
    c1, c2 = await ws_server.next_connection(), await ws_server.next_connection()
    for conn in (c1, c2):
        await conn.send(frame("article.created", RAW_ARTICLE))
    await a.wait_items(1)
    await b.wait_items(1)
    await a.stream.close()
    await b.stream.close()


@pytest.mark.parametrize("body", ["", "not json", '{"message":"Forbidden"}'])
async def test_403_without_a_known_body_waits_long_and_reports(ws_server: WsServer, fake_clock: FakeClock,
                                                                body: str) -> None:
    errors: list[Any] = []
    ws_server.reject_plan.append((403, body))
    stream = make(ws_server, fake_clock).stream(query="x", on_error=errors.append)
    consumer = Consumer(stream)
    for _ in range(100):
        if ws_server.dials:
            break
        await asyncio.sleep(0.005)
    await settle()
    await fake_clock.advance(59.9)
    assert len(ws_server.dials) == 1 and consumer.error is None
    await fake_clock.advance(0.2)
    await settle(0.05)
    assert len(ws_server.dials) == 2
    assert errors and isinstance(errors[0], ForbiddenError)
    await stream.close()


async def test_dial_429_waits_long(ws_server: WsServer, fake_clock: FakeClock) -> None:
    ws_server.reject_plan.append((429, ""))
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    for _ in range(100):
        if ws_server.dials:
            break
        await asyncio.sleep(0.005)
    await settle()
    await fake_clock.advance(59.0)
    assert len(ws_server.dials) == 1
    await fake_clock.advance(2.0)
    await settle(0.05)
    assert len(ws_server.dials) == 2 and consumer.error is None
    await stream.close()


async def test_close_1008_is_terminal(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.close(1008)
    await asyncio.wait_for(consumer.task, 3)
    assert isinstance(consumer.error, FinlightApiError)
    await fake_clock.advance(120)
    assert len(ws_server.dials) == 1


async def test_unknown_close_reconnects(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.close(4000)
    await settle()
    await fake_clock.advance(1.0)
    await settle(0.05)
    assert len(ws_server.dials) == 2 and consumer.error is None
    await stream.close()


async def test_large_frame_is_accepted(ws_server: WsServer, fake_clock: FakeClock) -> None:
    big = copy.deepcopy(ARTICLE)
    big["content"] = "x" * (2 * 1024 * 1024)
    stream = make(ws_server, fake_clock).stream(query="x", include=["content"])
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.send(frame("article.created", big))
    await consumer.wait_items(1)
    assert len(consumer.items[0].data.content) == 2 * 1024 * 1024
    await stream.close()


async def test_quota_reconnect_interval_is_configurable(ws_server: WsServer, fake_clock: FakeClock,
                                                         caplog: Any) -> None:
    errors: list[Any] = []
    waits: list[QuotaWaitInfo] = []
    refusal = (403, '{"message":"WebSocket quota exceeded for the current period"}')
    ws_server.reject_plan.extend([refusal, refusal])
    stream = make(ws_server, fake_clock, quota_reconnect_interval=600.0).stream(
        query="x", on_error=errors.append, on_quota_wait=waits.append)
    consumer = Consumer(stream)
    for _ in range(100):
        if ws_server.dials and waits:
            break
        await asyncio.sleep(0.005)
    await fake_clock.advance(599.9)
    assert len(ws_server.dials) == 1 and consumer.error is None
    await fake_clock.advance(0.2)
    await settle(0.05)
    assert len(ws_server.dials) == 2 and errors == []
    assert [(w.attempt, w.next_attempt_in) for w in waits] == [(1, 600.0), (2, 600.0)]
    assert all(isinstance(w.error, ForbiddenError) and w.error.api_kind == "forbidden" for w in waits)
    assert caplog.text.count("quota exhausted") == 2
    await stream.close()


async def test_quota_preempt_is_terminal_when_switched_off(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock, quota_reconnect=False).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.send({"event": "connection.preempted", "payloadVersion": 3,
                     "data": {"reason": "quota_exceeded", "newLeaseId": None, "timestamp": 1}})
    await asyncio.wait_for(consumer.task, 3)
    assert getattr(consumer.error, "reason", None) == "quota_exceeded"
    await fake_clock.advance(7200)
    assert len(ws_server.dials) == 1


async def test_connection_limit_preempt_stays_terminal(ws_server: WsServer, fake_clock: FakeClock) -> None:
    stream = make(ws_server, fake_clock).stream(query="x")
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    await conn.send({"event": "connection.preempted", "payloadVersion": 3,
                     "data": {"reason": "connection_limit", "newLeaseId": "l2", "timestamp": 1}})
    await asyncio.wait_for(consumer.task, 3)
    assert getattr(consumer.error, "reason", None) == "connection_limit"
    await fake_clock.advance(7200)
    assert len(ws_server.dials) == 1


async def test_reconnect_reason_reports_the_last_dial_failure(ws_server: WsServer, fake_clock: FakeClock) -> None:
    reconnects: list[ReconnectInfo] = []
    stream = make(ws_server, fake_clock).stream(query="x", on_reconnect=reconnects.append)
    consumer = Consumer(stream)
    conn = await ws_server.next_connection()
    ws_server.reject_plan.append((429, ""))
    await conn.close(1001)
    for _ in range(200):
        if len(ws_server.dials) >= 3:
            break
        await fake_clock.advance(1.0)
    await ws_server.next_connection()
    await settle(0.05)
    assert reconnects == [ReconnectInfo(None, "rate_limited", 2)]
    assert consumer.error is None
    await stream.close()
