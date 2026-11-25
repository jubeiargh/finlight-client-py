"""finlight client for the finlight API v3.

This major version speaks only API v3 (REST ``/v3``, WebSocket
``payloadVersion`` 3, v3 webhooks).
"""

import logging as _logging

from ._config import FinlightConfig
from ._version import __version__
from .articles import SearchAllResult
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
    CacheInfo,
    Company,
    CompanyRecord,
    EventTag,
    Listing,
    Media,
    Pagination,
    Sentiment,
    SkippedEntry,
    Source,
    StreamEvent,
    WebhookEvent,
    WrongPayloadVersion,
    cache_info,
    raw_json,
    to_wire,
)
from .sources import SourceList
from .stream import (
    AdmittedInfo,
    DialRefused,
    FinlightStream,
    QuotaWaitInfo,
    ReconnectInfo,
    WebSocketClosed,
    WebSocketConnection,
)
from .vocab import (
    PAYLOAD_VERSION,
    CompanyRole,
    ConnectionErrorCode,
    EventDirection,
    EventType,
    Importance,
    IncludeBlock,
    OrderBy,
    PreemptReason,
    ProblemCode,
    RateLimitType,
    ReconnectReason,
    SentimentLabel,
    SortOrder,
    SourceType,
    StreamEventKind,
    StreamEventName,
    WebhookEventName,
)
from .webhooks import DEFAULT_WEBHOOK_TOLERANCE, Webhooks

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
    "SkippedEntry",
    "CacheInfo",
    "StreamEvent",
    "WebhookEvent",
    "WrongPayloadVersion",
    "SearchAllResult",
    "CompanyList",
    "SourceList",
    "FinlightStream",
    "AdmittedInfo",
    "ReconnectInfo",
    "QuotaWaitInfo",
    "raw_json",
    "cache_info",
    "to_wire",
    # webhooks
    "Webhooks",
    "DEFAULT_WEBHOOK_TOLERANCE",
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
    "PAYLOAD_VERSION",
    "IncludeBlock",
    "OrderBy",
    "SortOrder",
    "CompanyRole",
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
    "RateLimitType",
    "StreamEventKind",
    "ReconnectReason",
]
