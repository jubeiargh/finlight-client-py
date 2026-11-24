"""Client configuration. All durations are seconds as ``float``."""

from __future__ import annotations

import asyncio
import random as _random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Protocol

from ._version import __version__
from .errors import FinlightValidationError

if TYPE_CHECKING:  # pragma: no cover
    import requests

DEFAULT_BASE_URL = "https://api.finlight.me"
DEFAULT_WSS_URL = "wss://wss.finlight.me"
USER_AGENT = f"finlight-client-python/{__version__}"


class AsyncClock(Protocol):
    """Time source of the stream timers. Replace it in tests to fake time."""

    def monotonic(self) -> float: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """The real clock (``time.monotonic`` and ``asyncio.sleep``)."""

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds))


@dataclass(frozen=True)
class FinlightConfig:
    """Settings of a :class:`FinlightClient`.

    REST:
        ``timeout`` applies to each attempt, ``total_timeout`` (optional) caps a
        whole call including retries and the burst wait. ``max_retries`` retries
        5xx answers, network errors and attempt timeouts with growing, jittered
        waits. ``retry_on_burst`` is ``"once"`` (default: wait ``Retry-After``
        seconds, or ``burst_wait`` (10) without the header, then try once more)
        or ``"off"``.
        ``max_pages`` caps ``articles.search_all`` (default 10).

    WebSocket:
        ``ping_interval`` (25 s), ``pong_timeout`` (60 s) and
        ``rotation_interval`` (115 min) keep connections alive and fresh.
        When the monthly WebSocket quota is exhausted, the stream tries again
        every ``quota_reconnect_interval`` seconds (1 hour) while
        ``quota_reconnect`` is True (default); with False it ends with the error.

    Injection:
        ``session`` is your own ``requests.Session``; its adapters, proxies and
        retries apply, and the SDK never closes it. ``websocket_options`` are
        passed to ``websockets.connect`` (for example ``proxy`` or ``ssl``).
        ``websocket_connect`` replaces the WebSocket transport completely.
    """

    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    wss_url: str = DEFAULT_WSS_URL

    timeout: float = 30.0
    total_timeout: Optional[float] = None
    max_retries: int = 3
    retry_backoff_base: float = 0.5
    retry_backoff_max: float = 8.0
    retry_on_burst: str = "once"
    burst_wait: float = 10.0
    max_pages: int = 10
    max_response_bytes: int = 32 * 1024 * 1024

    ping_interval: float = 25.0
    pong_timeout: float = 60.0
    rotation_interval: float = 115 * 60.0
    reconnect_backoff_base: float = 0.5
    reconnect_backoff_max: float = 30.0
    connection_limit_backoff: float = 60.0
    search_failed_threshold: int = 5
    quota_reconnect: bool = True
    quota_reconnect_interval: float = 3600.0
    takeover: bool = False
    dedupe_size: int = 1000
    max_message_bytes: int = 16 * 1024 * 1024

    session: Optional[requests.Session] = field(default=None, repr=False, compare=False)
    websocket_options: Mapping[str, Any] = field(default_factory=dict, repr=False)
    websocket_connect: Optional[Callable[..., Any]] = field(default=None, repr=False, compare=False)

    # Test seams: replaceable sleep, random source and stream clock.
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False, compare=False)
    monotonic: Callable[[], float] = field(default=time.monotonic, repr=False, compare=False)
    random: Callable[[], float] = field(default=_random.random, repr=False, compare=False)
    clock: AsyncClock = field(default_factory=SystemClock, repr=False, compare=False)
    nonce_factory: Optional[Callable[[], str]] = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise FinlightValidationError("api_key must be a non-empty string")
        for name in ("base_url", "wss_url"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise FinlightValidationError(f"{name} must be a non-empty string")
        if self.retry_on_burst not in ("once", "off"):
            raise FinlightValidationError("retry_on_burst must be 'once' or 'off'")
        if self.burst_wait < 0 or self.timeout <= 0:
            raise FinlightValidationError("timeout must be > 0 and burst_wait >= 0")
        if self.total_timeout is not None and self.total_timeout <= 0:
            raise FinlightValidationError("total_timeout must be > 0")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise FinlightValidationError("max_retries must be an integer >= 0")
        if isinstance(self.max_pages, bool) or not isinstance(self.max_pages, int) or self.max_pages < 1:
            raise FinlightValidationError("max_pages must be an integer >= 1")
        if self.quota_reconnect_interval <= 0:
            raise FinlightValidationError("quota_reconnect_interval must be > 0")
        if self.ping_interval <= 0 or self.pong_timeout <= 0 or self.rotation_interval <= 0:
            raise FinlightValidationError("ping_interval, pong_timeout and rotation_interval must be > 0")

    def __repr__(self) -> str:
        return f"FinlightConfig(base_url={self.base_url!r}, wss_url={self.wss_url!r}, api_key=***)"

    def rest_url(self, path: str) -> str:
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def ws_url(self, raw: bool) -> str:
        base = self.wss_url.rstrip("/")
        return base + "/raw" if raw else base
