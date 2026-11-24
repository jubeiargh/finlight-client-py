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
from .stream import Hook, Stream

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
        self.companies = CompaniesService(self._http)
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
        language: Optional[str] = None,
        tickers: Optional[Sequence[str]] = None,
        countries: Optional[Sequence[str]] = None,
        categories: Optional[Sequence[str]] = None,
        exclude_empty_content: Optional[bool] = None,
        include_updates: Optional[bool] = None,
        include: Optional[Sequence[str]] = None,
        on_reconnect: Optional[Hook] = None,
        on_admitted: Optional[Hook] = None,
        on_error: Optional[Hook] = None,
    ) -> Stream:
        """Enriched real-time stream. Arguments are checked now; the connection opens on iteration.

        Hooks may be plain functions or coroutine functions:

        * ``on_reconnect(last_seen, reason)`` after every new connection but the first;
          ``last_seen`` is the latest ``availableAt`` (fallback ``firstSeenAt``) seen.
        * ``on_admitted(lease_id, server_now, client_nonce)`` for each ``connection.admitted``.
        * ``on_error(error)`` for problems that do not end the stream.
        """
        values = dict(locals())
        frame = build_subscribe(STREAM_FIELDS, values)
        return Stream(
            self._config,
            frame,
            raw=False,
            on_reconnect=on_reconnect,
            on_admitted=on_admitted,
            on_error=on_error,
        )

    def raw_stream(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[Sequence[str]] = None,
        exclude_sources: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        include_updates: Optional[bool] = None,
        on_reconnect: Optional[Hook] = None,
        on_admitted: Optional[Hook] = None,
        on_error: Optional[Hook] = None,
    ) -> Stream:
        """Raw real-time stream (skeleton articles, before enrichment). Same hooks as :meth:`stream`.

        Raw takes no ``include``; ``on_reconnect`` gets the latest ``firstSeenAt``.
        """
        values = dict(locals())
        frame = build_subscribe(RAW_STREAM_FIELDS, values)
        return Stream(
            self._config,
            frame,
            raw=True,
            on_reconnect=on_reconnect,
            on_admitted=on_admitted,
            on_error=on_error,
        )
