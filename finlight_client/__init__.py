"""finlight client for the finlight API v3.

This major version speaks only API v3 (REST ``/v3``, WebSocket
``payloadVersion`` 3, v3 webhooks).
"""

import logging as _logging

from ._config import FinlightConfig
from ._version import __version__
from .articles import SearchAll
from .client import FinlightClient
from .companies import CompanyList
from .errors import (
    CursorInvalidError,
    CursorMismatchError,
    FieldIssue,
    FinlightApiError,
    FinlightDecodeError,
    FinlightError,
    FinlightNetworkError,
    FinlightTimeoutError,
    FinlightValidationError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    PreemptedError,
    RateLimitedError,
    UnauthorizedError,
    ValidationFailedError,
    WebhookVerificationError,
)
from .models import (
    Article,
    ArticlePage,
    ArticleSource,
    Company,
    CompanyRecord,
    EventTag,
    Listing,
    Media,
    Pagination,
    Sentiment,
    SkippedItem,
    Source,
    StreamEvent,
    WebhookEvent,
    WrongPayloadVersion,
    raw_json,
    to_wire,
)
from .sources import SourceList
from .stream import DialRefused, Stream, WebSocketClosed, WebSocketConnection
from .vocab import (
    ConnectionErrorCode,
    EventDirection,
    EventType,
    Importance,
    Include,
    LimitType,
    Order,
    OrderBy,
    PreemptReason,
    ProblemCode,
    Role,
    SentimentLabel,
    SourceType,
    StreamEventName,
    WebhookEventName,
)
from .webhooks import Webhooks

_logging.getLogger("finlight_client").addHandler(_logging.NullHandler())

__all__ = [
    "__version__",
    # client and config
    "FinlightClient",
    "FinlightConfig",
    # models
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
    "SkippedItem",
    "StreamEvent",
    "WebhookEvent",
    "WrongPayloadVersion",
    "SearchAll",
    "CompanyList",
    "SourceList",
    "Stream",
    "raw_json",
    "to_wire",
    # webhooks
    "Webhooks",
    # errors
    "FinlightError",
    "FinlightApiError",
    "ValidationFailedError",
    "CursorInvalidError",
    "CursorMismatchError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitedError",
    "InternalServerError",
    "FinlightValidationError",
    "FinlightNetworkError",
    "FinlightTimeoutError",
    "FinlightDecodeError",
    "WebhookVerificationError",
    "PreemptedError",
    "FieldIssue",
    # custom WebSocket transport
    "WebSocketConnection",
    "DialRefused",
    "WebSocketClosed",
    # vocabularies
    "Include",
    "OrderBy",
    "Order",
    "Role",
    "EventType",
    "EventDirection",
    "Importance",
    "SentimentLabel",
    "SourceType",
    "StreamEventName",
    "WebhookEventName",
    "ConnectionErrorCode",
    "PreemptReason",
    "ProblemCode",
    "LimitType",
]
