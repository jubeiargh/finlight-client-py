"""``client.articles``: search, search_all, get, get_by_link."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any, Optional
from urllib.parse import quote

from ._config import FinlightConfig
from ._http import HttpTransport
from ._params import SEARCH_FIELDS, TimeValue, build_body, dumps, include_query
from .errors import FinlightDecodeError, FinlightValidationError
from .models import Article, ArticlePage, decode_article, decode_article_page

__all__ = ["ArticlesService", "SearchAllResult"]

logger = logging.getLogger("finlight_client")


class SearchAllResult:
    """Result of :meth:`ArticlesService.search_all`. Iterate it once (a second time raises
    :class:`FinlightValidationError`).

    Iterating yields articles; :meth:`pages` yields whole pages instead.
    The request body is frozen when ``search_all`` is called; later pages only
    add the ``cursor``. Iteration stops when ``hasMore`` is false, when
    ``nextCursor`` is null, or after ``max_pages`` pages. In the last case a
    warning is logged, ``truncated`` is True and ``next_cursor`` holds the
    cursor to continue with (pass it as ``cursor=`` to a new ``search_all``).
    Errors are raised during iteration. A monthly 429 ends it at once; it never waits.
    """

    def __init__(self, http: HttpTransport, body: dict[str, Any], max_pages: int) -> None:
        self._http = http
        self._frozen = dumps(body).decode("utf-8")
        self._max_pages = max_pages
        self._started = False
        self.next_cursor: Optional[str] = body.get("cursor")
        self.pages_fetched = 0
        self.truncated = False

    def _claim(self) -> None:
        if self._started:
            raise FinlightValidationError("search_all results can be iterated only once; call search_all again")
        self._started = True

    def _body_for(self, cursor: Optional[str]) -> bytes:
        body = json.loads(self._frozen)
        if cursor is not None:
            body["cursor"] = cursor
        return dumps(body)

    def _iter_pages(self) -> Iterator[ArticlePage]:
        cursor = self.next_cursor
        while True:
            if self.pages_fetched >= self._max_pages:
                self.truncated = True
                logger.warning(
                    "finlight: search_all stopped after max_pages=%d; continue with next_cursor",
                    self._max_pages,
                )
                return
            resp = self._http.call("POST", "/v3/articles/search", body=self._body_for(cursor))
            page = decode_article_page(resp.json())
            self.pages_fetched += 1
            self.next_cursor = page.pagination.next_cursor
            yield page
            if not page.pagination.has_more or page.pagination.next_cursor is None:
                self.next_cursor = None
                return
            cursor = page.pagination.next_cursor

    def pages(self) -> Iterator[ArticlePage]:
        """Iterate whole pages instead of articles."""
        self._claim()
        return self._iter_pages()

    def __iter__(self) -> Iterator[Article]:
        self._claim()
        return self._iter_articles()

    def _iter_articles(self) -> Iterator[Article]:
        for page in self._iter_pages():
            yield from page.articles


class ArticlesService:
    def __init__(self, http: HttpTransport, config: FinlightConfig) -> None:
        self._http = http
        self._config = config

    def search(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[Sequence[str]] = None,
        opt_in_sources: Optional[Sequence[str]] = None,
        exclude_sources: Optional[Sequence[str]] = None,
        source_types: Optional[Sequence[str]] = None,
        exclude_source_types: Optional[Sequence[str]] = None,
        from_: Optional[TimeValue] = None,
        to: Optional[TimeValue] = None,
        languages: Optional[Sequence[str]] = None,
        tickers: Optional[Sequence[str]] = None,
        countries: Optional[Sequence[str]] = None,
        categories: Optional[Sequence[str]] = None,
        has_content: Optional[bool] = None,
        roles: Optional[Sequence[str]] = None,
        min_relevance: Optional[float] = None,
        event_types: Optional[Sequence[str]] = None,
        event_directions: Optional[Sequence[str]] = None,
        min_importance: Optional[str] = None,
        sectors: Optional[Sequence[str]] = None,
        company_countries: Optional[Sequence[str]] = None,
        exchanges: Optional[Sequence[str]] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include: Optional[Sequence[str]] = None,
    ) -> ArticlePage:
        """One page of ``POST /v3/articles/search``. Only the arguments you pass are sent."""
        body = build_body(SEARCH_FIELDS, dict(locals()))
        resp = self._http.call("POST", "/v3/articles/search", body=dumps(body))
        return decode_article_page(resp.json())

    def search_all(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[Sequence[str]] = None,
        opt_in_sources: Optional[Sequence[str]] = None,
        exclude_sources: Optional[Sequence[str]] = None,
        source_types: Optional[Sequence[str]] = None,
        exclude_source_types: Optional[Sequence[str]] = None,
        from_: Optional[TimeValue] = None,
        to: Optional[TimeValue] = None,
        languages: Optional[Sequence[str]] = None,
        tickers: Optional[Sequence[str]] = None,
        countries: Optional[Sequence[str]] = None,
        categories: Optional[Sequence[str]] = None,
        has_content: Optional[bool] = None,
        roles: Optional[Sequence[str]] = None,
        min_relevance: Optional[float] = None,
        event_types: Optional[Sequence[str]] = None,
        event_directions: Optional[Sequence[str]] = None,
        min_importance: Optional[str] = None,
        sectors: Optional[Sequence[str]] = None,
        company_countries: Optional[Sequence[str]] = None,
        exchanges: Optional[Sequence[str]] = None,
        order_by: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include: Optional[Sequence[str]] = None,
        max_pages: Optional[int] = None,
    ) -> SearchAllResult:
        """All pages of a search, as articles (or pages via ``.pages()``).

        Arguments are checked now; requests are sent while you iterate.
        ``max_pages`` defaults to the client's ``max_pages`` (10).
        """
        values = dict(locals())
        values.pop("self")
        pages = values.pop("max_pages")
        if pages is None:
            pages = self._config.max_pages
        if isinstance(pages, bool) or not isinstance(pages, int) or pages < 1:
            raise FinlightValidationError("max_pages must be an integer >= 1", param="max_pages")
        body = build_body(SEARCH_FIELDS, values)
        return SearchAllResult(self._http, body, pages)

    def get(self, id: str, *, include: Optional[Sequence[str]] = None) -> Article:
        """``GET /v3/articles/{id}``. A miss raises ``NotFoundError``."""
        if not isinstance(id, str) or not id:
            raise FinlightValidationError("id must be a non-empty string", param="id")
        query = include_query(include)
        resp = self._http.call("GET", "/v3/articles/" + quote(id, safe=""), query=query)
        return _article_envelope(resp.json())

    def get_by_link(self, link: str, *, include: Optional[Sequence[str]] = None) -> Article:
        """``GET /v3/articles/by-link``. The link must match exactly. A miss raises ``NotFoundError``."""
        if not isinstance(link, str) or not link:
            raise FinlightValidationError("link must be a non-empty string", param="link")
        query = [("link", link)] + include_query(include)
        resp = self._http.call("GET", "/v3/articles/by-link", query=query)
        return _article_envelope(resp.json())


def _article_envelope(body: Any) -> Article:
    if not isinstance(body, dict) or "article" not in body:
        raise FinlightDecodeError("response has no 'article' object", raw=body)
    return decode_article(body["article"])
