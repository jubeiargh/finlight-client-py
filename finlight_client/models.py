"""Response models of the finlight API v3.

Rules the models follow:

* Every wire key maps to one attribute in snake_case; keys are matched exactly.
* Unknown keys are ignored on every level. The raw JSON of an ``Article``,
  ``StreamEvent``, ``WebhookEvent`` and ``CompanyRecord`` is reachable through
  :func:`finlight_client.raw_json`.
* Only ``id``, ``link``, ``title``, ``source.domain`` (articles), ``companyId``
  and ``name`` (companies), ``domain`` (sources) and ``type`` (events) are
  required. Everything else may be missing or ``null`` and reads as ``None``;
  ``media``, ``countries``, ``categories``, ``isins`` and ``listings`` read as ``[]``.
* Values are never coerced (strict mode): ``"0.95"`` stays an error, not 0.95.
* Timestamps are kept as the strings that were sent. ``*_time`` properties parse
  them strictly (RFC 3339) and return ``None`` for anything else.
* ``content`` and ``sentiment`` have three states: key absent, ``null``, value.
  ``content_present`` / ``sentiment_present`` tell absent from ``null``.
  ``companies``, ``events``, ``EventTag.company_ids`` and ``Source.has_content``
  are ``None`` when the key is absent (the server never sends ``null`` there).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError, field_validator
from pydantic.alias_generators import to_camel

from ._timeutil import parse_rfc3339
from .errors import FinlightApiError, FinlightDecodeError

__all__ = [
    "Article",
    "ArticleSource",
    "Media",
    "Sentiment",
    "Company",
    "Listing",
    "EventTag",
    "CompanyRecord",
    "Source",
    "Pagination",
    "ArticlePage",
    "SkippedEntry",
    "CacheInfo",
    "StreamEvent",
    "WebhookEvent",
    "WrongPayloadVersion",
    "raw_json",
    "cache_info",
    "to_wire",
]

logger = logging.getLogger("finlight_client")


class _WireModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        strict=True,
        alias_generator=to_camel,
        populate_by_name=False,
        frozen=False,
    )

    _raw: Any = PrivateAttr(default=None)


def _none_to_list(value: Any) -> Any:
    return [] if value is None else value


class ArticleSource(_WireModel):
    domain: str
    type: Optional[str] = None


class Media(_WireModel):
    url: Optional[str] = None


class Sentiment(_WireModel):
    label: Optional[str] = None
    confidence: Optional[float] = None


class Listing(_WireModel):
    """A listing: ``primaryListing`` of a company, or one of ``CompanyRecord.listings``.

    ``active`` is only sent inside ``CompanyRecord.listings``.
    """

    ticker: Optional[str] = None
    mic: Optional[str] = None
    country: Optional[str] = None
    active: Optional[bool] = None


class Company(_WireModel):
    """A company tagged on an article."""

    company_id: int
    name: str
    isin: Optional[str] = None
    primary_listing: Optional[Listing] = None
    confidence: Optional[float] = None
    role: Optional[str] = None
    relevance: Optional[float] = None


class EventTag(_WireModel):
    """An event classified on an article.

    ``company_ids`` is ``None`` when the key is absent: it is only sent when the
    ``companies`` block is in the same payload.
    """

    type: str
    direction: Optional[str] = None
    importance: Optional[str] = None
    confidence: Optional[float] = None
    company_ids: Optional[list[int]] = None


class Article(_WireModel):
    id: str
    link: str
    source: ArticleSource
    title: str
    summary: Optional[str] = None
    language: Optional[str] = None
    media: list[Media] = []
    published_at: Optional[str] = None
    first_seen_at: Optional[str] = None
    revised_at: Optional[str] = None
    available_at: Optional[str] = None
    countries: list[str] = []
    categories: list[str] = []
    content: Optional[str] = None
    sentiment: Optional[Sentiment] = None
    companies: Optional[list[Company]] = None
    events: Optional[list[EventTag]] = None

    @field_validator("media", "countries", "categories", mode="before")
    @classmethod
    def _null_lists(cls, value: Any) -> Any:
        return _none_to_list(value)

    @property
    def content_present(self) -> bool:
        """True when the ``content`` key was in the JSON (even as ``null``)."""
        return "content" in self.model_fields_set

    @property
    def sentiment_present(self) -> bool:
        """True when the ``sentiment`` key was in the JSON (even as ``null``)."""
        return "sentiment" in self.model_fields_set

    @property
    def companies_present(self) -> bool:
        """True when the ``companies`` key was in the JSON. ``[]`` means: tagged, no company."""
        return "companies" in self.model_fields_set and self.companies is not None

    @property
    def events_present(self) -> bool:
        """True when the ``events`` key was in the JSON. ``[]`` means: classified, no event."""
        return "events" in self.model_fields_set and self.events is not None

    @property
    def published_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.published_at)

    @property
    def first_seen_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.first_seen_at)

    @property
    def revised_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.revised_at)

    @property
    def available_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.available_at)


class CompanyRecord(_WireModel):
    """Company master data from ``/v3/companies``."""

    company_id: int
    name: str
    country: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    isins: list[str] = []
    primary_listing: Optional[Listing] = None
    listings: list[Listing] = []
    updated_at: Optional[str] = None

    _cache_info: Optional[CacheInfo] = PrivateAttr(default=None)

    @field_validator("isins", "listings", mode="before")
    @classmethod
    def _null_lists(cls, value: Any) -> Any:
        return _none_to_list(value)

    @property
    def updated_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.updated_at)



class Source(_WireModel):
    """A source from ``/v3/sources``.

    ``has_content`` is ``None`` when the plan has no ``fullArticleAccess``
    (the key is absent): that means "unknown", not "no content".
    """

    domain: str
    name: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = None
    has_content: Optional[bool] = None
    is_custom: Optional[bool] = None
    country: Optional[str] = None
    languages: Optional[list[str]] = None


class Pagination(_WireModel):
    """``pagination`` of a search page. The end is ``has_more`` false or ``next_cursor`` ``None``."""

    limit: Optional[int] = None
    returned: Optional[int] = None
    has_more: Optional[bool] = None
    next_cursor: Optional[str] = None


@dataclass(frozen=True)
class SkippedEntry:
    """An entry of a list response that could not be read. It is left out of the result."""

    index: int
    raw: Any
    reason: str


@dataclass(frozen=True)
class CacheInfo:
    """ETag and Cache-Control of a record from ``companies.get`` (see :func:`cache_info`).

    The SDK keeps no cache. Keep the record yourself within ``max-age`` and pass ``etag``
    back as ``if_none_match`` to revalidate it.
    """

    etag: Optional[str]
    cache_control: Optional[str]


@dataclass
class ArticlePage:
    """One page of ``articles.search``."""

    articles: list[Article]
    pagination: Pagination
    skipped: list[SkippedEntry] = field(default_factory=list)


@dataclass
class StreamEvent:
    """One element of ``stream()`` / ``raw_stream()``.

    ``kind`` is ``"created"``, ``"updated"`` or ``"other"``. ``event`` is the
    wire name (open string). ``data`` is the article for article events and
    ``None`` for any other event; the full frame is reachable through
    :func:`raw_json`.
    """

    event: str
    kind: str
    data: Optional[Article]
    _raw: Any = field(default=None, repr=False, compare=False)


class WebhookEvent(_WireModel):
    """A verified v3 webhook delivery. Deduplicate on ``event_id``."""

    event_id: str
    event: str
    occurred_at: Optional[str] = None
    payload_version: Optional[Union[int, float]] = None
    subscription_id: Optional[str] = None
    changed_fields: Optional[list[str]] = None
    data: Article

    @property
    def is_test(self) -> bool:
        """True for the dashboard test webhook (``eventId`` starts with ``evt_test``)."""
        return self.event_id.startswith("evt_test")

    @property
    def occurred_at_time(self) -> Optional[datetime]:
        return parse_rfc3339(self.occurred_at)


@dataclass(frozen=True)
class WrongPayloadVersion:
    """A correctly signed webhook body that is not ``payloadVersion`` 3.

    This is a result, not an error: answer it with 2xx (for example the v2
    retries that still arrive for about 2 h after switching the webhook to v3)
    and keep ``raw`` if you need the data.

    * ``detected_version``: the version as the server reads it (always 2 here).
    * ``payload_version``: the raw ``payloadVersion`` value as received;
      ``payload_version_present`` is False when the key was missing.
    * ``raw``: the parsed JSON body.
    * ``link``: the article link, when it can be read.
    """

    detected_version: int
    payload_version: Any
    payload_version_present: bool
    raw: Any
    link: Optional[str]


def raw_json(obj: Any) -> Any:
    """The raw JSON tree (standard ``dict``/``list`` values) an object was read from.

    Works for ``Article``, ``CompanyRecord``, ``Source``, ``StreamEvent``,
    ``WebhookEvent``, ``WrongPayloadVersion`` and the errors (``FinlightApiError``:
    the parsed body or ``None``; ``FinlightDecodeError``: the value that did not
    fit). Unknown keys sent by the server are readable here. Treat the result as
    read-only.
    """
    if isinstance(obj, WrongPayloadVersion):
        return obj.raw
    if isinstance(obj, FinlightApiError):
        return obj.raw_json()
    if isinstance(obj, FinlightDecodeError):
        return obj.raw
    return getattr(obj, "_raw", None)


def cache_info(record: CompanyRecord) -> Optional[CacheInfo]:
    """ETag and Cache-Control of a record from ``companies.get`` (``None`` for other records)."""
    return record._cache_info


def to_wire(model: BaseModel) -> dict[str, Any]:
    """Write a model back to its wire form. Absent keys stay absent, ``null`` stays ``null``."""
    return model.model_dump(by_alias=True, exclude_unset=True, mode="json")


def _short_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)


def _json_path(loc: Any) -> Optional[str]:
    path = ""
    for part in loc or ():
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += ("." if path else "") + str(part)
    return path or None


def _decode_error(what: str, exc: ValidationError) -> FinlightDecodeError:
    errors = exc.errors()
    first: dict[str, Any] = dict(errors[0]) if errors else {}
    return FinlightDecodeError(
        f"{what} could not be read: {_short_error(exc)}",
        raw=first.get("input"),
        path=_json_path(first.get("loc")),
    )


def _validate(model: type[_WireModel], value: Any, what: str) -> Any:
    if not isinstance(value, dict):
        raise FinlightDecodeError(f"{what} is not a JSON object", raw=value)
    try:
        obj = model.model_validate(value)
    except ValidationError as exc:
        raise _decode_error(what, exc) from None
    obj._raw = value
    return obj


def decode_article(value: Any) -> Article:
    result: Article = _validate(Article, value, "article")
    return result


def decode_company_record(value: Any) -> CompanyRecord:
    result: CompanyRecord = _validate(CompanyRecord, value, "company")
    return result


def decode_list(items: Any, model: type[_WireModel], what: str) -> tuple[list[Any], list[SkippedEntry]]:
    if not isinstance(items, list):
        raise FinlightDecodeError(f"'{what}' is not a JSON array", raw=items)
    good: list[Any] = []
    skipped: list[SkippedEntry] = []
    for index, item in enumerate(items):
        try:
            good.append(_validate(model, item, what))
        except FinlightDecodeError as exc:
            logger.warning("finlight: skipped unreadable %s at index %d: %s", what, index, exc.message)
            skipped.append(SkippedEntry(index=index, raw=item, reason=exc.message))
    return good, skipped


def decode_article_page(body: Any) -> ArticlePage:
    if not isinstance(body, dict):
        raise FinlightDecodeError("search response is not a JSON object", raw=body)
    articles, skipped = decode_list(body.get("articles"), Article, "article")
    pagination_raw = body.get("pagination")
    if not isinstance(pagination_raw, dict):
        raise FinlightDecodeError("search response has no 'pagination' object", raw=body)
    try:
        pagination = Pagination.model_validate(pagination_raw)
    except ValidationError as exc:
        raise _decode_error("pagination", exc) from None
    pagination._raw = pagination_raw
    return ArticlePage(articles=articles, pagination=pagination, skipped=skipped)


def decode_webhook_event(value: Any) -> WebhookEvent:
    result: WebhookEvent = _validate(WebhookEvent, value, "webhook event")
    return result
