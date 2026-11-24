"""Test helpers: kit loading, a fake async clock and an in-process WebSocket server."""

from __future__ import annotations

import asyncio
import heapq
import itertools
import json
import re
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "conformance"
KIT_KEY = "sk_0000000000000000000000000000000000000000000000000000000000000001"


def load(rel: str) -> Any:
    return json.loads((KIT / rel).read_text(encoding="utf-8"))


def fixtures(folder: str, *, exclude: tuple[str, ...] = ()) -> list[tuple[str, Path]]:
    """``(case id, path)`` for every fixture in a kit folder, sorted by case id."""
    out = []
    for path in sorted((KIT / folder).glob("*.json")):
        if path.name in exclude:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append((data.get("id", path.stem), path))
    return sorted(out)


def case_ids_from_conformance() -> list[str]:
    text = (KIT / "conformance.md").read_text(encoding="utf-8")
    return re.findall(r"^\| ([A-Z]-\d+) \|", text, flags=re.M)


_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def snake(name: str) -> str:
    if name == "from":
        return "from_"
    return _CAMEL.sub("_", name).lower()


def snake_args(args: dict[str, Any]) -> dict[str, Any]:
    return {snake(k): v for k, v in args.items()}


# ---------------------------------------------------------------------------
# Fake clock
# ---------------------------------------------------------------------------


async def settle(real_seconds: float = 0.004) -> None:
    for _ in range(6):
        await asyncio.sleep(0)
    await asyncio.sleep(real_seconds)
    for _ in range(6):
        await asyncio.sleep(0)


class FakeClock:
    """Async clock whose time only moves through :meth:`advance`."""

    def __init__(self) -> None:
        self.now = 0.0
        self._heap: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq = itertools.count()

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._heap, (self.now + seconds, next(self._seq), fut))
        await fut

    def pending(self) -> int:
        return sum(1 for _, _, f in self._heap if not f.done())

    async def advance(self, seconds: float) -> None:
        target = self.now + seconds
        while True:
            while self._heap and self._heap[0][2].done():
                heapq.heappop(self._heap)
            if self._heap and self._heap[0][0] <= target:
                deadline, _, fut = heapq.heappop(self._heap)
                self.now = max(self.now, deadline)
                fut.set_result(None)
                await settle()
                continue
            break
        self.now = target
        await settle()


# ---------------------------------------------------------------------------
# In-process WebSocket server
# ---------------------------------------------------------------------------


class ServerConn:
    def __init__(self, ws: Any, headers: list[tuple[str, str]], path: str) -> None:
        self.ws = ws
        self.headers = headers
        self.path = path
        self.inbox: asyncio.Queue[str] = asyncio.Queue()
        self.closed = asyncio.Event()

    def header(self, name: str) -> Optional[str]:
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return None

    async def send(self, frame: Any) -> None:
        await self.ws.send(frame if isinstance(frame, str) else json.dumps(frame))

    async def recv(self, timeout: float = 3.0, *, skip_pings: bool = True) -> Any:
        while True:
            text = await asyncio.wait_for(self.inbox.get(), timeout)
            try:
                obj = json.loads(text)
            except ValueError:
                return text
            if skip_pings and isinstance(obj, dict) and obj.get("action") == "ping":
                continue
            return obj

    async def close(self, code: int = 1001) -> None:
        try:
            await self.ws.close(code)
        except Exception:  # noqa: BLE001
            pass


class WsServer:
    """websockets server on 127.0.0.1 with scripted dial answers."""

    def __init__(self) -> None:
        self.connections: asyncio.Queue[ServerConn] = asyncio.Queue()
        self.all: list[ServerConn] = []
        self.dials: list[dict[str, Any]] = []
        self.reject_plan: list[Optional[tuple[int, str]]] = []
        self.auto_pong = False
        self._server: Any = None
        self.port = 0

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    async def start(self) -> None:
        from websockets.asyncio.server import serve

        self._server = await serve(
            self._handler,
            "127.0.0.1",
            0,
            process_request=self._process_request,
            ping_interval=None,
            max_size=None,
        )
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for conn in self.all:
            await conn.close(1001)
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def _process_request(self, connection: Any, request: Any) -> Any:
        headers = list(request.headers.raw_items())
        self.dials.append({"path": request.path, "headers": headers})
        if self.reject_plan:
            plan = self.reject_plan.pop(0)
            if plan is not None:
                status, body = plan
                from websockets.datastructures import Headers
                from websockets.http11 import Response

                return Response(
                    status,
                    "Refused",
                    Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body.encode())))]),
                    body.encode(),
                )
        return None

    async def _handler(self, ws: Any) -> None:
        req = ws.request
        conn = ServerConn(ws, list(req.headers.raw_items()), req.path)
        self.all.append(conn)
        await self.connections.put(conn)
        try:
            async for message in ws:
                text = message if isinstance(message, str) else message.decode()
                if self.auto_pong:
                    try:
                        obj = json.loads(text)
                    except ValueError:
                        obj = None
                    if isinstance(obj, dict) and obj.get("action") == "ping":
                        await ws.send(
                            json.dumps(
                                {"event": "connection.pong", "payloadVersion": 3,
                                 "data": {"t": obj.get("t"), "serverNow": 1}}
                            )
                        )
                        continue
                await conn.inbox.put(text)
        except Exception:  # noqa: BLE001
            pass
        finally:
            conn.closed.set()

    async def next_connection(self, timeout: float = 3.0) -> ServerConn:
        return await asyncio.wait_for(self.connections.get(), timeout)


# ---------------------------------------------------------------------------
# Presence view of a decoded model (absent / null / empty / value)
# ---------------------------------------------------------------------------

_SEGMENT = re.compile(r"^([A-Za-z]+)(?:\[(\d+)\])?$")


def presence(model: Any, path: str) -> str:
    """Presence state of a wire path, read from the decoded model."""
    parent = model
    parts = path.split(".")
    for i, part in enumerate(parts):
        m = _SEGMENT.match(part)
        assert m, part
        name, index = m.group(1), m.group(2)
        attr = snake(name)
        last = i == len(parts) - 1
        if attr not in type(parent).model_fields:
            raise AssertionError(f"model {type(parent).__name__} has no field for wire key {name!r}")
        if attr not in parent.model_fields_set:
            state = "absent"
            value = None
        else:
            value = getattr(parent, attr)
            state = "null" if value is None else ("empty" if value == [] else "value")
        if index is not None:
            if state != "value":
                return state
            value = value[int(index)]
            state = "value"
        if last:
            return state
        if state != "value":
            return state
        parent = value
    raise AssertionError("unreachable")


def helper_presence(article: Any, key: str) -> str:
    """Presence of a gated top-level key through the public helpers only."""
    if key == "content":
        if not article.content_present:
            return "absent"
        return "null" if article.content is None else "value"
    if key == "sentiment":
        if not article.sentiment_present:
            return "absent"
        return "null" if article.sentiment is None else "value"
    if key == "companies":
        if not article.companies_present:
            return "absent"
        return "empty" if article.companies == [] else "value"
    if key == "events":
        if not article.events_present:
            return "absent"
        return "empty" if article.events == [] else "value"
    raise KeyError(key)
