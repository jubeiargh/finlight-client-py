"""The finlight client."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Optional
from urllib.parse import urlparse

from ._config import FinlightConfig
from ._http import HttpTransport
from ._params import RAW_STREAM_FIELDS, STREAM_FIELDS, build_subscribe
from .articles import ArticlesService
from .companies import CompaniesService
from .errors import FinlightValidationError
from .sources import SourcesService
from .stream import FinlightStream, Hook

__all__ = ["FinlightClient"]


class FinlightClient:
    """Client for the finlight API v3.

    REST calls are synchronous; streams are async iterators::

        from finlight_client import FinlightClient

        with FinlightClient(api_key="...") as client:
            page = client.articles.search(query="ticker:NVDA", limit=10)

    Pass settings as keyword arguments or a :class:`FinlightConfig`. The client
    is safe to share between threads and may run several streams at once.
    """

    def __init__(self, api_key: Optional[str] = None, *, config: Optional[FinlightConfig] = None, **options: Any) -> None:
        if config is not None:
            if api_key is not None or options:
                changes: dict[str, Any] = dict(options)
                if api_key is not None:
                    changes["api_key"] = api_key
                config = replace(config, **changes)
        else:
            if api_key is None:
                raise FinlightValidationError("api_key is required")
            config = FinlightConfig(api_key=api_key, **options)
        for name, url, schemes in (
            ("base_url", config.base_url, ("http", "https")),
            ("wss_url", config.wss_url, ("ws", "wss")),
        ):
            parsed = urlparse(url)
            if parsed.scheme not in schemes or not parsed.netloc:
                raise FinlightValidationError(f"{name} must be an absolute {'/'.join(schemes)} URL")
            if parsed.query or "apikey" in url.lower():
                raise FinlightValidationError(f"{name} must not carry a query string")
        self._config = config
        self._http = HttpTransport(config)
        self.articles = ArticlesService(self._http, config)
        self.companies = CompaniesService(self._http, config.company_cache_size)
        self.sources = SourcesService(self._http)

    @property
    def config(self) -> FinlightConfig:
        return self._config

    def __repr__(self) -> str:
        return f"FinlightClient(base_url={self._config.base_url!r}, api_key=***)"

    def close(self) -> None:
        """Close the HTTP session the client created (an injected session stays open)."""
        self._http.close()

    def __enter__(self) -> FinlightClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def stream(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[Sequence[str]] = None,
        exclude_sources: Optional[Sequence[str]] = None,
        opt_in_sources: Optional[Sequence[str]] = None,
        source_types: Optional[Sequence[str]] = None,
        exclude_source_types: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        tickers: Optional[Sequence[str]] = None,
        countries: Optional[Sequence[str]] = None,
        categories: Optional[Sequence[str]] = None,
        exclude_empty_content: Optional[bool] = None,
        include_updates: Optional[bool] = None,
        include: Optional[Sequence[str]] = None,
        takeover: bool = False,
        on_admitted: Optional[Hook] = None,
        on_reconnect: Optional[Hook] = None,
        on_error: Optional[Hook] = None,
        on_quota_wait: Optional[Hook] = None,
    ) -> FinlightStream:
        """Enriched real-time stream. Arguments are checked now; the connection opens on iteration.

        ``takeover=True`` replaces the stalest connection of your key when the
        connection limit is reached (off by default).

        Hooks may be plain functions or coroutine functions:

        * ``on_admitted(AdmittedInfo)`` for each ``connection.admitted``.
        * ``on_reconnect(ReconnectInfo)`` after every new connection but the first;
          ``last_seen_at`` is the latest ``availableAt`` (fallback ``firstSeenAt``) seen.
        * ``on_error(FinlightError)`` for problems that do not end the stream.
        * ``on_quota_wait(QuotaWaitInfo)`` whenever the stream waits for a new
          monthly WebSocket quota (see ``quota_reconnect``).
        """
        values = dict(locals())
        frame = build_subscribe(STREAM_FIELDS, values)
        return self._make_stream(frame, False, values)

    def raw_stream(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[Sequence[str]] = None,
        exclude_sources: Optional[Sequence[str]] = None,
        source_types: Optional[Sequence[str]] = None,
        exclude_source_types: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        include_updates: Optional[bool] = None,
        takeover: bool = False,
        on_admitted: Optional[Hook] = None,
        on_reconnect: Optional[Hook] = None,
        on_error: Optional[Hook] = None,
        on_quota_wait: Optional[Hook] = None,
    ) -> FinlightStream:
        """Raw real-time stream (skeleton articles, before enrichment). Same hooks as :meth:`stream`.

        Raw takes no ``include``; ``ReconnectInfo.last_seen_at`` is the latest ``firstSeenAt``.
        """
        values = dict(locals())
        frame = build_subscribe(RAW_STREAM_FIELDS, values)
        return self._make_stream(frame, True, values)

    def _make_stream(self, frame: dict[str, Any], raw: bool, values: dict[str, Any]) -> FinlightStream:
        if not isinstance(values["takeover"], bool):
            raise FinlightValidationError("takeover must be True or False", param="takeover")
        return FinlightStream(
            self._config,
            frame,
            raw=raw,
            takeover=values["takeover"],
            on_admitted=values["on_admitted"],
            on_reconnect=values["on_reconnect"],
            on_error=values["on_error"],
            on_quota_wait=values["on_quota_wait"],
        )
