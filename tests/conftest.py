from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest

from finlight_client import FinlightClient
from tests.support import KIT_KEY, FakeClock, WsServer


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def sleeps() -> SleepRecorder:
    return SleepRecorder()


@pytest.fixture
def make_client(httpserver: Any, sleeps: SleepRecorder) -> Callable[..., FinlightClient]:
    clients: list[FinlightClient] = []

    def factory(**options: Any) -> FinlightClient:
        options.setdefault("api_key", KIT_KEY)
        options.setdefault("base_url", httpserver.url_for("/"))
        options.setdefault("sleep", sleeps)
        options.setdefault("random", lambda: 0.0)
        client = FinlightClient(**options)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def ws_server() -> AsyncIterator[WsServer]:
    server = WsServer()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()
