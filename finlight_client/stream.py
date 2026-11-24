"""Real-time streams over the finlight WebSocket (``payloadVersion`` 3).

Use ``client.stream(...)`` (enriched) or ``client.raw_stream(...)`` (raw)::

    async with client.stream(query="ticker:NVDA", include=["companies"]) as stream:
        async for event in stream:
            print(event.kind, event.data.title if event.data else event.event)

The stream keeps the connection alive (ping every 25 s, reconnect after 60 s
without pong, fresh connection after 115 min), re-sends the same subscribe after
each reconnect and drops duplicate deliveries. It never backfills by itself: use
``on_reconnect`` and ``articles.search_all`` to fill gaps.

Terminal problems end the iteration with an error: a refused dial (401, 403
without WebSockets), ``VALIDATION_FAILED``, ``connection.preempted`` with reason
``connection_limit`` (:class:`PreemptedError`) and close code 1008. An exhausted
monthly WebSocket quota (dial 403 "quota exceeded" or ``connection.preempted``
with reason ``quota_exceeded``) is not terminal by default: the stream tries
again every ``quota_reconnect_interval`` seconds (1 hour) until the quota allows
it, logging a warning and calling ``on_quota_wait`` (not ``on_error``) on every
wait. With
``quota_reconnect=False`` it ends with the error instead. Other problems
reconnect with backoff and are reported through ``on_error``.

Notes:

* ``connection.admitted`` arrives before the server checks the subscribe; it
  does not mean the subscribe was accepted.
* The server silently drops live frames larger than 32,000 bytes (for example
  ``include=["content"]`` on long articles). Fetch such articles with
  ``articles.get``.
* The connection limit of your plan is shared by enriched, raw and older SDKs.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, Union

from . import _frames
from ._config import USER_AGENT, FinlightConfig
from ._timeutil import parse_rfc3339
from ._version import __version__
from .errors import (
    FinlightApiError,
    FinlightDecodeError,
    FinlightNetworkError,
    FinlightValidationError,
    ForbiddenError,
    InternalServerError,
    PreemptedError,
    RateLimitedError,
    UnauthorizedError,
    ValidationFailedError,
    _issues_from,
)
from .models import StreamEvent, decode_article

__all__ = [
    "FinlightStream",
    "AdmittedInfo",
    "ReconnectInfo",
    "QuotaWaitInfo",
    "WebSocketConnection",
    "DialRefused",
    "WebSocketClosed",
]

logger = logging.getLogger("finlight_client")

Hook = Callable[..., Union[None, Awaitable[None]]]


# --------------------------------------------------------------------------
# Transport seam
# --------------------------------------------------------------------------


class WebSocketConnection(Protocol):
    """What a custom ``websocket_connect`` must return."""

    async def send(self, message: str) -> None: ...

    async def recv(self) -> Union[str, bytes]: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class DialRefused(Exception):
    """Raise from a custom ``websocket_connect`` when the server refused the upgrade."""

    def __init__(self, status: int, body: Optional[bytes] = None) -> None:
        super().__init__(f"WebSocket upgrade refused with HTTP {status}")
        self.status = status
        self.body = body


class WebSocketClosed(Exception):
    """Raise from ``recv`` of a custom connection when the socket closed."""

    def __init__(self, code: Optional[int], reason: str = "") -> None:
        super().__init__(f"WebSocket closed ({code})")
        self.code = code
        self.reason = reason


class _QuietLogger(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Logger for the websockets library: never emits DEBUG (it would log request headers)."""

    def isEnabledFor(self, level: int) -> bool:  # noqa: N802 - logging API
        return level > logging.DEBUG and self.logger.isEnabledFor(level)

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        if level > logging.DEBUG:
            super().log(level, msg, *args, **kwargs)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        return None


class _WebsocketsConnection:
    def __init__(self, ws: Any) -> None:
        self._ws = ws

    async def send(self, message: str) -> None:
        from websockets.exceptions import ConnectionClosed

        try:
            await self._ws.send(message)
        except ConnectionClosed as exc:
            raise WebSocketClosed(_close_code(exc), _close_reason(exc)) from None

    async def recv(self) -> Union[str, bytes]:
        from websockets.exceptions import ConnectionClosed

        try:
            message: Union[str, bytes] = await self._ws.recv()
            return message
        except ConnectionClosed as exc:
            raise WebSocketClosed(_close_code(exc), _close_reason(exc)) from None

    async def close(self, code: int = 1000, reason: str = "") -> None:
        await self._ws.close(code, reason)


def _close_code(exc: Any) -> Optional[int]:
    rcvd = getattr(exc, "rcvd", None)
    return getattr(rcvd, "code", None) if rcvd is not None else None


def _close_reason(exc: Any) -> str:
    rcvd = getattr(exc, "rcvd", None)
    return str(getattr(rcvd, "reason", "")) if rcvd is not None else ""


async def _default_connect(
    url: str, headers: list[tuple[str, str]], config: FinlightConfig
) -> WebSocketConnection:
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus

    options = dict(config.websocket_options)
    options.setdefault("open_timeout", config.connect_timeout)
    options.setdefault("close_timeout", 5)
    try:
        ws = await connect(
            url,
            additional_headers=headers,
            user_agent_header=USER_AGENT,
            # Protocol-level pings are off on purpose: the app ping drives liveness.
            ping_interval=None,
            ping_timeout=None,
            max_size=config.max_message_bytes,
            logger=_QuietLogger(logging.getLogger("finlight_client.websocket"), {}),
            **options,
        )
    except InvalidStatus as exc:
        response = exc.response
        raise DialRefused(response.status_code, getattr(response, "body", None)) from None
    return _WebsocketsConnection(ws)


# --------------------------------------------------------------------------
# Outcomes
# --------------------------------------------------------------------------


@dataclass
class _Outcome:
    kind: str  # "terminal" | "reconnect" | "rotate" | "quota"
    reason: str = ""
    error: Optional[BaseException] = None
    delay: Optional[float] = None  # None: normal backoff


_END = object()


@dataclass(frozen=True)
class AdmittedInfo:
    """Passed to ``on_admitted`` for each ``connection.admitted``.

    It arrives before the server checks the subscribe and does not mean the subscribe was accepted.
    """

    lease_id: Optional[str]
    server_now: Optional[int]
    client_nonce: Optional[str]


@dataclass(frozen=True)
class ReconnectInfo:
    """Passed to ``on_reconnect`` after every new connection but the first.

    ``last_seen_at``: latest ``availableAt`` (fallback ``firstSeenAt``; raw: ``firstSeenAt``)
    delivered so far, or ``None``. ``reason``: why the previous connection ended or the
    last dial failed (``ReconnectReason``). ``connection``: number of connections of this
    stream, the new one included.
    """

    last_seen_at: Optional[str]
    reason: str
    connection: int


@dataclass(frozen=True)
class QuotaWaitInfo:
    """Passed to ``on_quota_wait`` whenever the stream waits for a new WebSocket quota.

    ``error`` is the ``PreemptedError`` (reason ``quota_exceeded``) or the refused dial
    (``ForbiddenError``, status 403). ``next_attempt_in`` is in seconds; ``attempt`` counts
    the waits in a row, from 1.
    """

    error: BaseException
    next_attempt_in: float
    attempt: int


def _closed_outcome(exc: WebSocketClosed) -> _Outcome:
    if exc.code == 1008:
        error = FinlightApiError(
            f"WebSocket closed by the server with 1008 (policy violation) {exc.reason}".strip(),
            detail=exc.reason or None,
        )
        return _Outcome("terminal", error=error)
    return _Outcome("reconnect", reason="closed")


class _Session:
    def __init__(self, stream: FinlightStream, conn: WebSocketConnection, nonce: str) -> None:
        self.stream = stream
        self.conn = conn
        self.nonce = nonce
        clock = stream._config.clock
        self.opened_at = clock.monotonic()
        self.last_pong = self.opened_at
        self.last_ping = self.opened_at
        self.admitted = False
        # Set by a pong or an article: the connection really works. Only then is the
        # reconnect backoff reset (admitted comes before the subscribe is checked).
        self.healthy = False
        self.retiring = False
        self.outcome: asyncio.Future[_Outcome] = asyncio.get_running_loop().create_future()
        self.tasks: list[asyncio.Task[Any]] = []

    def finish(self, outcome: _Outcome) -> None:
        if not self.outcome.done():
            self.outcome.set_result(outcome)

    async def start(self, frame: dict[str, Any]) -> None:
        message = dict(frame)
        message["clientNonce"] = self.nonce
        await self.conn.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
        self.tasks.append(asyncio.ensure_future(self._reader()))
        self.tasks.append(asyncio.ensure_future(self._ticker()))

    async def close(self, code: int = 1000) -> None:
        self.retiring = True
        for task in self.tasks:
            if task is not asyncio.current_task():
                task.cancel()
        try:
            await asyncio.wait_for(self.conn.close(code), timeout=5)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - closing a dead socket may fail in any way
            pass
        for task in self.tasks:
            if task is not asyncio.current_task():
                try:
                    await task
                except BaseException:  # noqa: BLE001 - task was cancelled on purpose
                    pass

    async def _reader(self) -> None:
        while True:
            try:
                message = await self.conn.recv()
            except asyncio.CancelledError:
                raise
            except WebSocketClosed as exc:
                self.finish(_closed_outcome(exc))
                return
            except Exception as exc:  # noqa: BLE001 - any transport failure means reconnect
                logger.warning("finlight: WebSocket receive failed: %s", type(exc).__name__)
                self.finish(_Outcome("reconnect", reason="closed"))
                return
            # During rotation the old connection keeps delivering until it is closed.
            self.stream._handle_frame(self, _frames.decode_frame(message))
            if self.outcome.done() and self.outcome.result().kind != "rotate":
                return

    async def _ticker(self) -> None:
        cfg = self.stream._config
        clock = cfg.clock
        while not self.outcome.done():
            now = clock.monotonic()
            watchdog_at = self.last_pong + cfg.watchdog_timeout
            if now >= watchdog_at:
                logger.warning("finlight: no pong for %.0f s, reconnecting", cfg.watchdog_timeout)
                self.finish(_Outcome("reconnect", reason="watchdog", delay=0.0))
                return
            rotate_at = self.opened_at + cfg.rotation_interval
            if now >= rotate_at and not self.retiring:
                self.finish(_Outcome("rotate", reason="rotation", delay=0.0))
                return
            next_ping = self.last_ping + cfg.ping_interval
            if now >= next_ping:
                self.last_ping = now
                ping = json.dumps({"action": "ping", "t": int(time.time() * 1000)})
                try:
                    await self.conn.send(ping)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - a failed send means the socket is gone
                    self.finish(_Outcome("reconnect", reason="closed"))
                    return
                continue
            wake = min(watchdog_at, next_ping, rotate_at if not self.retiring else watchdog_at)
            await clock.sleep(max(0.0, wake - now))


class FinlightStream:
    """An async iterator of :class:`StreamEvent`. Iterate it once (a second time raises
    :class:`FinlightValidationError`).

    Prefer ``async with client.stream(...) as stream: async for ev in stream``:
    leaving the block closes the socket with code 1000 and stops every timer.
    Breaking out of a bare ``async for`` also closes it, shortly after.
    """

    def __init__(
        self,
        config: FinlightConfig,
        frame: dict[str, Any],
        *,
        raw: bool,
        takeover: bool = False,
        on_reconnect: Optional[Hook] = None,
        on_admitted: Optional[Hook] = None,
        on_error: Optional[Hook] = None,
        on_quota_wait: Optional[Hook] = None,
    ) -> None:
        self._config = config
        self._takeover = takeover
        self._on_quota_wait = on_quota_wait
        self._quota_attempt = 0
        self._connections = 0
        self._frame = frame
        self._raw = raw
        self._url = config.ws_url(raw)
        self._on_reconnect = on_reconnect
        self._on_admitted = on_admitted
        self._on_error = on_error
        self._iterated = False
        self._closed = False
        self._queue: Optional[asyncio.Queue[Any]] = None
        self._supervisor: Optional[asyncio.Task[None]] = None
        self._sessions: list[_Session] = []
        self._hook_tasks: set[asyncio.Task[Any]] = set()
        self._bg_tasks: set[asyncio.Task[Any]] = set()
        self._dedupe: OrderedDict[tuple[str, str, str], None] = OrderedDict()
        self._search_failed = 0
        self._last_seen: Optional[str] = None
        self._last_seen_time: Optional[datetime] = None
        self._dial_count = 0

    # -- public -------------------------------------------------------------

    @property
    def last_seen_at(self) -> Optional[str]:
        """Latest timestamp seen: ``availableAt`` (fallback ``firstSeenAt``) on enriched, ``firstSeenAt`` on raw."""
        return self._last_seen

    @property
    def closed(self) -> bool:
        """True once the stream was closed or ended."""
        return self._closed

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        if self._iterated:
            raise FinlightValidationError("a stream can be iterated only once; call stream() again")
        self._iterated = True
        return self._iterate()

    async def __aenter__(self) -> FinlightStream:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Stop the stream: close the socket with 1000 and end all background work."""
        if self._closed:
            return
        self._closed = True
        supervisor = self._supervisor
        if supervisor is not None and supervisor is not asyncio.current_task():
            supervisor.cancel()
            try:
                await supervisor
            except BaseException:  # noqa: BLE001 - cancelled on purpose
                pass
        for session in list(self._sessions):
            await session.close(1000)
        self._sessions.clear()
        if self._bg_tasks:
            await asyncio.wait(list(self._bg_tasks), timeout=6)
        for task in list(self._hook_tasks):
            task.cancel()
        self._hook_tasks.clear()
        if self._queue is not None:
            self._queue.put_nowait(_END)

    # -- iteration ----------------------------------------------------------

    async def _iterate(self) -> AsyncIterator[StreamEvent]:
        self._start()
        assert self._queue is not None
        try:
            while True:
                item = await self._queue.get()
                if item is _END:
                    return
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            await self.close()

    def _start(self) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue()
        if self._supervisor is None and not self._closed:
            self._supervisor = asyncio.ensure_future(self._run())

    # -- supervisor ---------------------------------------------------------

    def _nonce(self) -> str:
        factory = self._config.nonce_factory
        return factory() if factory is not None else "c-" + uuid.uuid4().hex[:16]

    def _backoff(self, attempt: int) -> float:
        cfg = self._config
        delay = min(cfg.reconnect_max_delay, cfg.reconnect_base_delay * (2**attempt))
        return float(delay * (0.5 + 0.5 * cfg.random()))

    def _long_backoff(self) -> float:
        cfg = self._config
        return float(cfg.long_backoff * (1 + 0.25 * cfg.random()))

    def _headers(self) -> list[tuple[str, str]]:
        # Exactly lowercase: the gateway looks the key up case-sensitively.
        headers = [("x-api-key", self._config.api_key), ("x-client-version", __version__)]
        if self._takeover:
            headers.append(("x-takeover", "true"))
        return headers

    async def _dial(self) -> WebSocketConnection:
        self._dial_count += 1
        connect = self._config.websocket_connect
        if connect is not None:
            conn: WebSocketConnection = await connect(self._url, self._headers())
            return conn
        return await _default_connect(self._url, self._headers(), self._config)

    def _end(self, error: Optional[BaseException]) -> None:
        assert self._queue is not None
        if error is not None:
            self._queue.put_nowait(error)
        self._queue.put_nowait(_END)

    async def _run(self) -> None:
        clock = self._config.clock
        attempt = 0
        delay = 0.0
        reconnect_reason: Optional[str] = None
        current: Optional[_Session] = None
        try:
            while True:
                if delay > 0:
                    await clock.sleep(delay)
                delay = 0.0
                try:
                    conn = await self._dial()
                except asyncio.CancelledError:
                    raise
                except DialRefused as refused:
                    verdict = _classify_dial(refused.status, refused.body)
                    if verdict.kind == "quota" and not self._config.quota_reconnect:
                        verdict = _DialVerdict("terminal", verdict.error)
                    if current is not None:
                        # Rotation dial failed: free the slot first, then dial again.
                        await current.close(1000)
                        self._sessions.remove(current)
                        current = None
                        if verdict.kind != "terminal":
                            continue
                    if verdict.kind == "terminal":
                        self._end(verdict.error)
                        return
                    if verdict.kind == "quota":
                        reconnect_reason = "quota_exceeded"
                        delay = self._quota_wait(verdict.error)
                        continue
                    reconnect_reason = verdict.reason
                    if verdict.error is not None:
                        self._emit_error(verdict.error)
                    if verdict.kind == "long":
                        delay = self._long_backoff()
                    else:
                        delay = self._backoff(attempt)
                    attempt += 1
                    logger.warning(
                        "finlight: WebSocket dial refused (HTTP %d), retrying in %.1f s", refused.status, delay
                    )
                    continue
                except Exception as exc:  # noqa: BLE001 - network failure on dial
                    if current is not None:
                        # Rotation dial failed: free the slot first, then dial again at once.
                        await current.close(1000)
                        self._sessions.remove(current)
                        current = None
                        continue
                    error = FinlightNetworkError(f"WebSocket dial failed: {type(exc).__name__}")
                    error.__cause__ = exc
                    reconnect_reason = "dial_failed"
                    self._emit_error(error)
                    delay = self._backoff(attempt)
                    attempt += 1
                    logger.warning("finlight: WebSocket dial failed (%s), retrying in %.1f s", type(exc).__name__, delay)
                    continue

                session = _Session(self, conn, self._nonce())
                self._connections += 1
                self._sessions.append(session)
                try:
                    await session.start(self._frame)
                except asyncio.CancelledError:
                    raise
                except WebSocketClosed as exc:
                    session.finish(_closed_outcome(exc))
                except Exception:  # noqa: BLE001 - socket died right away
                    session.finish(_Outcome("reconnect", reason="closed"))
                if current is not None:
                    old = current
                    old.retiring = True
                    await old.close(1000)
                    if old in self._sessions:
                        self._sessions.remove(old)
                current = session
                if self._connections > 1:
                    info = ReconnectInfo(self._last_seen, reconnect_reason or "closed", self._connections)
                    self._call_hook(self._on_reconnect, info)

                outcome = await session.outcome
                if outcome.kind == "terminal":
                    await session.close(1000)
                    self._sessions.remove(session)
                    current = None
                    self._end(outcome.error)
                    return
                if outcome.kind == "quota":
                    self._retire(session)
                    current = None
                    reconnect_reason = outcome.reason
                    delay = self._quota_wait(outcome.error)
                    continue
                reconnect_reason = outcome.reason
                healthy = session.healthy and outcome.reason in ("watchdog", "closed", "rotation")
                if healthy:
                    attempt = 0
                if outcome.kind == "rotate":
                    logger.info("finlight: rotating the WebSocket connection")
                    continue  # keep the old session open until the new one is subscribed
                self._retire(session)
                current = None
                if outcome.delay is not None and healthy:
                    delay = outcome.delay
                else:
                    delay = self._backoff(attempt)
                    attempt += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never let the supervisor die silently
            logger.error("finlight: stream failed: %s", type(exc).__name__)
            failure = FinlightNetworkError(f"stream failed: {type(exc).__name__}")
            failure.__cause__ = exc
            self._end(failure)

    def _quota_wait(self, error: Optional[BaseException]) -> float:
        """Monthly WebSocket quota exhausted: report it to on_quota_wait (only) and wait the interval."""
        delay = float(self._config.quota_reconnect_interval)
        self._quota_attempt += 1
        logger.warning(
            "finlight: WebSocket quota exhausted, trying again in %.0f s (wait %d)", delay, self._quota_attempt
        )
        if error is not None:
            self._call_hook(self._on_quota_wait, QuotaWaitInfo(error, delay, self._quota_attempt))
        return delay

    def _retire(self, session: _Session) -> None:
        """Close a dead session in the background so a hanging close never delays the reconnect."""
        if session in self._sessions:
            self._sessions.remove(session)
        task = asyncio.ensure_future(session.close(1000))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    # -- frames ---------------------------------------------------------------

    def _handle_frame(self, session: _Session, frame: _frames.Frame) -> None:
        clock = self._config.clock
        ftype = frame.type
        if ftype == _frames.PONG:
            session.last_pong = clock.monotonic()
            session.healthy = True
            if not frame.v2:
                self._search_failed = 0  # a v3 pong means the subscribe was stored
            return
        if ftype == _frames.ADMITTED:
            session.admitted = True
            self._quota_attempt = 0
            f = frame.fields
            logger.debug("finlight: connection admitted")
            info = AdmittedInfo(f.get("lease_id"), f.get("server_now"), f.get("client_nonce"))
            self._call_hook(self._on_admitted, info)
            return
        if ftype == _frames.ARTICLE:
            session.healthy = True
            self._deliver_article(frame)
            return
        if ftype == _frames.PREEMPTED:
            if session.retiring:
                return
            f = frame.fields
            error = PreemptedError(
                f"stream preempted: {f.get('reason')}",
                reason=f.get("reason"),
                new_lease_id=f.get("new_lease_id"),
                timestamp=f.get("timestamp"),
            )
            if f.get("reason") == "quota_exceeded" and self._config.quota_reconnect:
                session.finish(_Outcome("quota", reason="quota_exceeded", error=error))
            else:
                session.finish(_Outcome("terminal", error=error))
            return
        if ftype == _frames.ERROR:
            self._handle_error_frame(session, frame)
            return
        if ftype == _frames.LEGACY_ARTICLE:
            logger.warning("finlight: dropped a v2 article frame on a v3 stream")
            return
        if ftype == _frames.INVALID:
            logger.warning("finlight: dropped a frame that is not a JSON object")
            return
        # Unknown event: delivered as kind "other" with the raw frame, never an error.
        logger.debug("finlight: unknown event %r", frame.event)
        event = StreamEvent(
            event=frame.event or "",
            kind="other",
            data=None,
            _raw=frame.raw,
        )
        self._put(event)

    def _handle_error_frame(self, session: _Session, frame: _frames.Frame) -> None:
        f = frame.fields
        code = f.get("code")
        message = f.get("message") or ""
        details = f.get("details")
        raw_text = json.dumps(frame.raw, ensure_ascii=False) if frame.raw is not None else None
        if code == "VALIDATION_FAILED":
            error: FinlightApiError = ValidationFailedError(
                f"subscribe rejected: {message}".strip(),
                code=code,
                detail=message or None,
                errors=_issues_from(details),
                raw=raw_text,
            )
            session.finish(_Outcome("terminal", error=error))
            return
        error = FinlightApiError(
            f"stream error {code or '(v2 form)'}: {message}".strip(),
            code=code,
            detail=message or None,
            errors=_issues_from(details),
            raw=raw_text,
        )
        if code == "HANDSHAKE_FAILED":
            logger.warning("finlight: HANDSHAKE_FAILED, reconnecting")
            session.finish(_Outcome("reconnect", reason="handshake_failed"))
            return
        if code == "SEARCH_FAILED":
            self._search_failed += 1
            logger.warning("finlight: SEARCH_FAILED (%d in a row), reconnecting", self._search_failed)
            if self._search_failed >= self._config.search_failed_threshold:
                self._emit_error(error)
            session.finish(_Outcome("reconnect", reason="search_failed"))
            return
        # PING_ON_DEFAULT_ROUTE, INTERNAL_ERROR, v2-form errors and unknown codes: report only.
        logger.warning("finlight: stream error %s: %s", code or "(v2 form)", message)
        self._emit_error(error)

    def _deliver_article(self, frame: _frames.Frame) -> None:
        try:
            article = decode_article(frame.data)
        except FinlightDecodeError as exc:
            logger.warning("finlight: dropped an unreadable %s frame: %s", frame.event, exc.message)
            self._emit_error(exc)
            return
        canonical = json.dumps(frame.data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        key = (frame.event or "", article.id, digest)
        if key in self._dedupe:
            self._dedupe.move_to_end(key)
            logger.debug("finlight: dropped a duplicate delivery")
            return
        self._dedupe[key] = None
        while len(self._dedupe) > self._config.dedupe_cache_size:
            self._dedupe.popitem(last=False)
        self._search_failed = 0
        seen = article.first_seen_at if self._raw else (article.available_at or article.first_seen_at)
        seen_time = parse_rfc3339(seen)
        if seen_time is not None and (self._last_seen_time is None or seen_time > self._last_seen_time):
            self._last_seen_time = seen_time
            self._last_seen = seen
        event = StreamEvent(
            event=frame.event or "",
            kind=frame.kind or "other",
            data=article,
            _raw=frame.raw,
        )
        self._put(event)

    def _put(self, item: Any) -> None:
        if self._queue is not None and not self._closed:
            self._queue.put_nowait(item)

    # -- hooks ----------------------------------------------------------------

    def _emit_error(self, error: BaseException) -> None:
        self._call_hook(self._on_error, error)

    def _call_hook(self, hook: Optional[Hook], *args: Any) -> None:
        if hook is None:
            return
        try:
            result = hook(*args)
        except Exception:  # noqa: BLE001 - user code must not stop the stream
            logger.exception("finlight: stream hook raised")
            return
        if inspect.isawaitable(result):
            task = asyncio.ensure_future(self._await_hook(result))
            self._hook_tasks.add(task)
            task.add_done_callback(self._hook_tasks.discard)

    async def _await_hook(self, awaitable: Awaitable[Any]) -> None:
        try:
            await awaitable
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - user code must not stop the stream
            logger.exception("finlight: stream hook raised")


@dataclass
class _DialVerdict:
    kind: str  # "terminal" | "quota" | "long" | "backoff"
    error: Optional[FinlightApiError]
    reason: str = "dial_refused"


def _dial_message(body: Optional[bytes]) -> Optional[str]:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        return text.strip() or None
    if isinstance(parsed, dict):
        for key in ("message", "error"):
            if isinstance(parsed.get(key), str):
                return str(parsed[key])
    return None


def _classify_dial(status: int, body: Optional[bytes]) -> _DialVerdict:
    message = _dial_message(body)
    raw = body.decode("utf-8", errors="replace") if body else None
    text = f"WebSocket connection refused with HTTP {status}" + (f": {message}" if message else "")
    if status == 401:
        return _DialVerdict("terminal", UnauthorizedError(text, status=401, detail=message, raw=raw))
    if status == 403:
        if message and message.startswith("Your subscription does not include WebSockets"):
            return _DialVerdict("terminal", ForbiddenError(text, status=403, detail=message, raw=raw))
        if message and message.startswith("WebSocket quota exceeded"):
            return _DialVerdict("quota", ForbiddenError(text, status=403, detail=message, raw=raw))
        if message and message.startswith("Too many concurrent connections"):
            hint = text + ". Another connection holds the slot; pass takeover=True to stream() to replace it."
            return _DialVerdict("long", ForbiddenError(hint, status=403, detail=message, raw=raw), "connection_limit")
        # Body missing or unknown: long wait plus a report.
        return _DialVerdict("long", ForbiddenError(text, status=403, detail=message, raw=raw))
    if status == 429:
        return _DialVerdict("long", RateLimitedError(text, status=429, detail=message, raw=raw), "rate_limited")
    if status >= 500:
        return _DialVerdict("backoff", InternalServerError(text, status=status, detail=message, raw=raw))
    return _DialVerdict("terminal", FinlightApiError(text, status=status, detail=message, raw=raw))
