"""S-01 .. S-26 and R-13/R-14: scripted WebSocket sessions against an in-process server.

The engine replays each ``ws-sessions/*.json`` fixture. Server steps are sent by
the test server, client steps are read from what the SDK really sent, time moves
through a fake clock. Steps the SDK can never produce (a truncated frame, a
legacy key, a re-subscribe on the same connection, a ping on ``$default``) are
not sent; the server answers in the fixture still are.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import pytest

from finlight_client import (
    FinlightApiError,
    FinlightClient,
    ForbiddenError,
    PreemptedError,
    StreamEvent,
    UnauthorizedError,
    ValidationFailedError,
)
from tests.support import KIT_KEY, FakeClock, ServerConn, WsServer, fixtures, load, settle, snake

SESSIONS = fixtures("ws-sessions")
FORBIDDEN = {"includeContent", "includeEntities", "extended"}
ENRICHED_KEYS = {
    "include", "query", "sources", "excludeSources", "optInSources", "language", "tickers",
    "countries", "categories", "excludeEmptyContent", "includeUpdates",
}
RAW_KEYS = {"query", "sources", "excludeSources", "language", "includeUpdates"}
DEFAULT_FRAME = {"payloadVersion": 3, "query": "ticker:XMPL", "clientNonce": "c-kit-1"}


def is_subscribe(frame: Any) -> bool:
    return isinstance(frame, dict) and "payloadVersion" in frame and "action" not in frame and "type" not in frame


def sdk_frame(frame: dict[str, Any], raw: bool) -> dict[str, Any]:
    """The frame the SDK can send for this fixture frame (legacy keys and raw include cannot be sent)."""
    out = {k: v for k, v in frame.items() if k not in FORBIDDEN}
    if raw:
        out.pop("include", None)
    return out


class Session:
    def __init__(self, fx: dict[str, Any], server: WsServer, clock: FakeClock) -> None:
        self.fx = fx
        self.server = server
        self.clock = clock
        self.raw = fx.get("endpoint") == "raw"
        self.steps: list[dict[str, Any]] = fx["steps"]
        self.items: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self.admitted: list[tuple[Any, ...]] = []
        self.admitted_seen = 0
        self.errors: list[BaseException] = []
        self.reconnects: list[tuple[Any, ...]] = []
        self.terminal: Optional[BaseException] = None
        self.done = asyncio.Event()
        self.conn: Optional[ServerConn] = None
        self.subscribed: set[int] = set()
        self.dials_consumed = 0
        self.task: Optional[asyncio.Task[None]] = None
        self.stream: Any = None
        first = next((s["frame"] for s in self.steps if s["step"] == "clientSends" and is_subscribe(s.get("frame"))), None)
        self.first_frame: dict[str, Any] = first or DEFAULT_FRAME
        server.auto_pong = not any(s["step"] == "clientSends" and "match" in s for s in self.steps)

    def api_key(self) -> str:
        dial = next(s for s in self.steps if s["step"] == "dial")
        return dial.get("expectRequestHeaders", {}).get("x-api-key") or KIT_KEY

    async def start(self) -> None:
        allowed = RAW_KEYS if self.raw else ENRICHED_KEYS
        args = {snake(k): v for k, v in self.first_frame.items() if k in allowed}
        nonce = self.first_frame.get("clientNonce", "c-kit-1")
        client = FinlightClient(
            api_key=self.api_key(),
            base_url="http://127.0.0.1:9",
            wss_url=self.server.url,
            clock=self.clock,
            random=lambda: 0.0,
            nonce_factory=lambda: nonce,
        )
        factory = client.raw_stream if self.raw else client.stream
        self.stream = factory(
            **args,
            on_admitted=lambda *a: self.admitted.append(a),
            on_error=self.errors.append,
            on_reconnect=lambda *a: self.reconnects.append(a),
        )
        self.task = asyncio.ensure_future(self._consume())

    async def _consume(self) -> None:
        try:
            async for event in self.stream:
                await self.items.put(event)
        except Exception as exc:  # noqa: BLE001
            self.terminal = exc
        finally:
            self.done.set()

    async def close(self) -> None:
        if self.stream is not None:
            await self.stream.close()
        if self.task is not None:
            await asyncio.wait_for(self.task, 5)
        assert self.clock.pending() == 0 or self.stream._closed

    async def wait_for(self, predicate: Any, what: str, timeout: float = 3.0) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not predicate():
            if loop.time() > end:
                raise AssertionError(f"timed out waiting for {what}")
            await asyncio.sleep(0.005)

    async def wait_for_dial(self, before: int, max_fake_seconds: float = 200.0) -> float:
        """Advance fake time until the client dials again; returns the fake seconds waited."""
        waited = 0.0
        for _ in range(50):
            if len(self.server.dials) > before:
                return waited
            await settle()
        while len(self.server.dials) <= before:
            if waited >= max_fake_seconds:
                raise AssertionError("client did not dial again")
            await self.clock.advance(0.5)
            waited += 0.5
        return waited

    # -- steps ----------------------------------------------------------------

    async def run(self) -> None:
        for index, step in enumerate(self.steps):
            await getattr(self, "step_" + step["step"])(step, self.steps[index + 1 :])

    async def step_dial(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        status = step["server"]["status"]
        self.server.reject_plan.append(None if status == 101 else (status, step["server"].get("body", "")))
        if self.task is None:
            await self.start()
        # The dial may already have happened (a reconnect fires while time advances).
        await self.wait_for_dial(self.dials_consumed)
        dial = self.server.dials[self.dials_consumed]
        self.dials_consumed += 1
        assert dial["path"] == ("/raw" if self.raw else "/")
        names = [name for name, _ in dial["headers"]]
        assert "x-api-key" in names, "header name must be exactly lowercase x-api-key"
        assert "apiKey" not in dial["path"]
        for name, value in step.get("expectRequestHeaders", {}).items():
            assert dict(dial["headers"])[name] == value
        assert dict(dial["headers"])["x-client-version"]
        if status == 101:
            self.conn = await self.server.next_connection()

    async def step_clientSends(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        assert self.conn is not None
        if "match" in step:
            while True:
                msg = await self.conn.recv(skip_pings=False)
                if isinstance(msg, dict) and all(msg.get(k) == v for k, v in step["match"].items()):
                    assert isinstance(msg.get("t"), int)
                    return
        frame = step["frame"]
        if not is_subscribe(frame):
            return  # truncated frame, keep-alive ping or a ping on $default: not sent by the SDK
        if id(self.conn) in self.subscribed:
            return  # a re-subscribe on the same connection: the SDK never sends one
        got = await self.conn.recv()
        assert got == sdk_frame(frame, self.raw)
        assert type(got["payloadVersion"]) is int and got["payloadVersion"] == 3
        assert not FORBIDDEN & set(got)
        self.subscribed.add(id(self.conn))

    async def step_serverSends(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        assert self.conn is not None
        frame = step["frame"]
        if frame.get("action") == "pong" or frame.get("event") == "connection.pong":
            await self.clock.advance(1.0)  # so the refreshed watchdog is visible
        await self.conn.send(frame)
        await settle()

    async def step_serverCloses(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        assert self.conn is not None
        await self.conn.close(1001)
        await settle()

    async def step_advance(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        await self.clock.advance(step["ms"] / 1000)

    async def step_expect(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        await getattr(self, "expect_" + step["outcome"])(step, rest)

    # -- expectations -------------------------------------------------------------

    async def expect_admitted(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        await self.wait_for(lambda: len(self.admitted) > self.admitted_seen, "connection.admitted")
        lease_id, server_now, nonce = self.admitted[self.admitted_seen]
        self.admitted_seen += 1
        assert isinstance(server_now, int)
        if "clientNonce" in step:
            assert nonce == step["clientNonce"]
        if "leaseId" in step:
            assert lease_id == step["leaseId"]

    async def expect_noAdmitted(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        await settle(0.05)
        assert len(self.admitted) == self.admitted_seen
        assert self.terminal is None and not self.done.is_set()

    async def expect_item(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        event = await asyncio.wait_for(self.items.get(), 3)
        assert event.kind == step["kind"]
        assert event.data is not None
        if "id" in step:
            assert event.data.id == step["id"]
        if self.raw:
            article = event.data
            assert article.available_at is None
            for flag in ("content_present", "sentiment_present", "companies_present", "events_present"):
                assert getattr(article, flag) is False

    async def expect_duplicateDropped(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        await settle(0.05)
        assert self.items.empty()

    async def expect_logOnly(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        dials = len(self.server.dials)
        await settle(0.05)
        assert self.terminal is None and not self.done.is_set()
        while not self.items.empty():
            assert self.items.get_nowait().kind == "other"  # unknown events surface as "other"
        assert len(self.server.dials) == dials
        if "code" in step:
            assert any(getattr(e, "code", None) == step["code"] for e in self.errors)

    async def expect_liveness(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        await self.wait_for(
            lambda: self.stream._sessions and self.stream._sessions[-1].last_pong == self.clock.now,
            "the pong to refresh the watchdog",
        )
        assert self.terminal is None

    async def expect_terminalError(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        await asyncio.wait_for(self.done.wait(), 5)
        err = self.terminal
        kind = step["error"]
        if kind == "DialError":
            assert isinstance(err, FinlightApiError) and err.status == step["status"]
            if step["status"] == 401:
                assert isinstance(err, UnauthorizedError)
            if step["status"] == 403:
                assert isinstance(err, ForbiddenError)
        elif kind == "PreemptedError":
            assert isinstance(err, PreemptedError)
            assert err.reason == step["reason"] and err.new_lease_id == step["newLeaseId"]
        elif kind == "ValidationError":
            assert isinstance(err, ValidationFailedError) and err.code == step["code"]
            assert err.errors and err.errors[0].field and err.errors[0].issue
        else:
            raise AssertionError(kind)

    async def expect_noReconnect(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:  # noqa: N802
        dials = len(self.server.dials)
        if self.done.is_set():
            # After a terminal error nothing may dial again, however long we wait.
            await self.clock.advance(120.0)
        else:
            await settle(0.05)  # e.g. 59 s without pong: not yet
        assert len(self.server.dials) == dials

    async def expect_reconnect(self, step: dict[str, Any], rest: list[dict[str, Any]]) -> None:
        assert self.terminal is None
        if rest and rest[0]["step"] == "dial":
            return  # the next dial step waits for the new connection
        before = len(self.server.dials)
        if step.get("backoff") == "long":
            # Long backoff: the first retry comes after at least 60 s (fixture value if given).
            minimum = step.get("firstRetryMinMs", 60000) / 1000
            await self.clock.advance(minimum - 0.001)
            assert len(self.server.dials) == before, "retried before the minimum wait"
        await self.wait_for_dial(before)
        self.dials_consumed = len(self.server.dials)
        if step.get("hint") == "takeover":
            assert any("takeover" in str(e) for e in self.errors)
        if step.get("resubscribe"):
            self.conn = await self.server.next_connection()
            got = await self.conn.recv()
            assert got == sdk_frame(self.first_frame, self.raw)
            self.subscribed.add(id(self.conn))
        if "surfaceAfterConsecutive" in step:
            await self._search_failed_until(step["surfaceAfterConsecutive"])

    async def _search_failed_until(self, threshold: int) -> None:
        """S-14: SEARCH_FAILED is reported only after ``threshold`` failures in a row."""
        def surfaced() -> int:
            return sum(1 for e in self.errors if getattr(e, "code", None) == "SEARCH_FAILED")

        assert surfaced() == 0
        for n in range(2, threshold + 1):
            assert self.conn is not None
            await self.conn.send({"event": "connection.admitted", "payloadVersion": 3,
                                  "data": {"leaseId": "l", "serverNow": 1, "clientNonce": "c-kit-1"}})
            await self.conn.send({"event": "connection.error", "payloadVersion": 3,
                                  "data": {"code": "SEARCH_FAILED", "message": "Search temporarily unavailable"}})
            await self.conn.close(1001)
            await settle()
            assert surfaced() == (1 if n == threshold else 0), n
            before = len(self.server.dials)
            await self.wait_for_dial(before)
            self.dials_consumed = len(self.server.dials)
            self.conn = await self.server.next_connection()
            await self.conn.recv()
        assert self.terminal is None


@pytest.mark.parametrize(("case", "path"), SESSIONS, ids=[c for c, _ in SESSIONS])
async def test_session(case: str, path: Path, ws_server: WsServer, fake_clock: FakeClock) -> None:
    fx = load(f"ws-sessions/{path.name}")
    session = Session(fx, ws_server, fake_clock)
    try:
        await asyncio.wait_for(session.run(), 60)
    finally:
        await session.close()
    if case == "S-18":
        assert session.reconnects and session.reconnects[-1][1] == "rotation"
        old, new = ws_server.all[0], ws_server.all[1]
        await asyncio.wait_for(old.closed.wait(), 5)  # the old connection is closed after the new one subscribed
        assert new is not old


async def run_subscribe_fixture(name: str, server: WsServer, clock: FakeClock, raw: bool) -> None:
    fx = load(f"fixtures/requests/{name}")
    nonce = fx["frame"]["clientNonce"]
    client = FinlightClient(api_key=KIT_KEY, wss_url=server.url, clock=clock, nonce_factory=lambda: nonce)
    args = {snake(k): v for k, v in fx["sdk"]["args"].items()}
    admitted: list[Any] = []
    errors: list[Any] = []
    stream = (client.raw_stream if raw else client.stream)(
        **args, on_admitted=lambda *a: admitted.append(a), on_error=errors.append
    )
    items: list[StreamEvent] = []

    async def consume() -> None:
        async for event in stream:
            items.append(event)

    task = asyncio.ensure_future(consume())
    try:
        conn = await server.next_connection()
        raw_frame = await asyncio.wait_for(conn.inbox.get(), 3)
        got = json.loads(raw_frame)
        assert got == fx["frame"]
        assert type(got["payloadVersion"]) is int
        assert "action" not in got
        for frame in fx["server"]["frames"]:
            await conn.send(frame)
        await settle(0.05)
        assert len(admitted) == 1 and admitted[0][2] == nonce
        assert errors == []
        if raw:
            assert items == []
        else:
            assert [(i.kind, i.data.id) for i in items] == [("created", fx["server"]["frames"][1]["data"]["id"])]
    finally:
        await stream.close()
        await asyncio.wait_for(task, 5)


@pytest.mark.parametrize("case", ["R-13"])
async def test_subscribe_enriched(case: str, ws_server: WsServer, fake_clock: FakeClock) -> None:
    await run_subscribe_fixture("ws-subscribe-enriched.json", ws_server, fake_clock, raw=False)


@pytest.mark.parametrize("case", ["R-14"])
async def test_subscribe_raw(case: str, ws_server: WsServer, fake_clock: FakeClock) -> None:
    await run_subscribe_fixture("ws-subscribe-raw.json", ws_server, fake_clock, raw=True)
