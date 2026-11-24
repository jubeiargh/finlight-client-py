"""``client.sources``: list."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ._http import HttpTransport
from .errors import FinlightDecodeError
from .models import Source, decode_list

__all__ = ["SourcesService", "SourceList"]


class SourceList(list):  # type: ignore[type-arg]
    """A list of :class:`Source`. ``skipped`` holds entries that could not be read."""

    def __init__(self, items: Sequence[Source], skipped: list[Any]) -> None:
        super().__init__(items)
        self.skipped = skipped


class SourcesService:
    def __init__(self, http: HttpTransport) -> None:
        self._http = http

    def list(self) -> SourceList:
        """``GET /v3/sources``: the full catalog, sorted by domain."""
        resp = self._http.call("GET", "/v3/sources")
        body = resp.json()
        if not isinstance(body, dict):
            raise FinlightDecodeError("sources response is not a JSON object", raw=body)
        items, skipped = decode_list(body.get("sources"), Source, "source")
        return SourceList(items, skipped)
