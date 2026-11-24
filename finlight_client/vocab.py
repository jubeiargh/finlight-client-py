"""Known values of the finlight vocabularies.

Response values are open: fields hold plain strings, and a value that is not in
these lists is kept as it was sent. Request values are not checked by the SDK;
the server answers unknown ones with ``VALIDATION_FAILED`` and ``allowedValues``.
Compare with ``==`` against the constants below.
"""

from __future__ import annotations

__all__ = [
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
    "ConnectionErrorCode",
    "PreemptReason",
    "ProblemCode",
    "WebhookEventName",
    "RateLimitType",
    "StreamEventKind",
    "ReconnectReason",
]

PAYLOAD_VERSION = 3


class IncludeBlock:
    CONTENT = "content"
    COMPANIES = "companies"
    EVENTS = "events"
    ALL = (CONTENT, COMPANIES, EVENTS)


class OrderBy:
    PUBLISHED_AT = "publishedAt"
    FIRST_SEEN_AT = "firstSeenAt"
    REVISED_AT = "revisedAt"
    AVAILABLE_AT = "availableAt"
    ALL = (PUBLISHED_AT, FIRST_SEEN_AT, REVISED_AT, AVAILABLE_AT)


class SortOrder:
    ASC = "asc"
    DESC = "desc"
    ALL = (ASC, DESC)


class CompanyRole:
    ACQUIRER = "acquirer"
    TARGET = "target"
    SELLER = "seller"
    DEFENDANT = "defendant"
    SUBJECT = "subject"
    COUNTERPARTY = "counterparty"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    MENTIONED = "mentioned"
    ALL = (
        ACQUIRER,
        TARGET,
        SELLER,
        DEFENDANT,
        SUBJECT,
        COUNTERPARTY,
        SUPPLIER,
        CUSTOMER,
        COMPETITOR,
        MENTIONED,
    )


class EventType:
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    MNA = "mna"
    IPO_LISTING = "ipo_listing"
    CAPITAL_ACTION = "capital_action"
    RATING_ACTION = "rating_action"
    MANAGEMENT_CHANGE = "management_change"
    LEGAL = "legal"
    REGULATORY = "regulatory"
    BANKRUPTCY_DISTRESS = "bankruptcy_distress"
    PRODUCT_PARTNERSHIP = "product_partnership"
    INVESTMENT_EXPANSION = "investment_expansion"
    OPERATIONAL_INCIDENT = "operational_incident"
    LABOR_RESTRUCTURING = "labor_restructuring"
    MACRO = "macro"
    GEOPOLITICS = "geopolitics"
    ALL = (
        EARNINGS,
        GUIDANCE,
        MNA,
        IPO_LISTING,
        CAPITAL_ACTION,
        RATING_ACTION,
        MANAGEMENT_CHANGE,
        LEGAL,
        REGULATORY,
        BANKRUPTCY_DISTRESS,
        PRODUCT_PARTNERSHIP,
        INVESTMENT_EXPANSION,
        OPERATIONAL_INCIDENT,
        LABOR_RESTRUCTURING,
        MACRO,
        GEOPOLITICS,
    )


class EventDirection:
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNCLEAR = "unclear"
    ALL = (POSITIVE, NEGATIVE, NEUTRAL, UNCLEAR)


class Importance:
    """Ordinal: ``ALL`` is sorted from lowest to highest."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    ALL = (LOW, MEDIUM, HIGH, CRITICAL)


class SentimentLabel:
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    ALL = (POSITIVE, NEGATIVE, NEUTRAL)


class SourceType:
    """``source.type`` of an article and ``type`` of a ``/v3/sources`` entry.

    The field is ``None`` when the source is not classified. Also the values for
    the ``source_types`` and ``exclude_source_types`` arguments of search and of
    both streams.
    """

    NEWSWIRE = "newswire"
    PRESS_RELEASE = "press_release"
    FINANCIAL_MEDIA = "financial_media"
    GENERAL_MEDIA = "general_media"
    AGGREGATOR = "aggregator"
    BLOG = "blog"
    GOVERNMENT = "government"
    ALL = (
        NEWSWIRE,
        PRESS_RELEASE,
        FINANCIAL_MEDIA,
        GENERAL_MEDIA,
        AGGREGATOR,
        BLOG,
        GOVERNMENT,
    )


class StreamEventName:
    ARTICLE_CREATED = "article.created"
    ARTICLE_UPDATED = "article.updated"
    CONNECTION_ADMITTED = "connection.admitted"
    CONNECTION_PONG = "connection.pong"
    CONNECTION_PREEMPTED = "connection.preempted"
    CONNECTION_ERROR = "connection.error"
    ARTICLE_EVENTS = (ARTICLE_CREATED, ARTICLE_UPDATED)
    CONNECTION_EVENTS = (
        CONNECTION_ADMITTED,
        CONNECTION_PONG,
        CONNECTION_PREEMPTED,
        CONNECTION_ERROR,
    )
    ALL = ARTICLE_EVENTS + CONNECTION_EVENTS


class WebhookEventName:
    ARTICLE_CREATED = "article.created"
    ARTICLE_UPDATED = "article.updated"
    ALL = (ARTICLE_CREATED, ARTICLE_UPDATED)


class ConnectionErrorCode:
    PING_ON_DEFAULT_ROUTE = "PING_ON_DEFAULT_ROUTE"
    HANDSHAKE_FAILED = "HANDSHAKE_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SEARCH_FAILED = "SEARCH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ALL = (
        PING_ON_DEFAULT_ROUTE,
        HANDSHAKE_FAILED,
        VALIDATION_FAILED,
        SEARCH_FAILED,
        INTERNAL_ERROR,
    )


class PreemptReason:
    CONNECTION_LIMIT = "connection_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    ALL = (CONNECTION_LIMIT, QUOTA_EXCEEDED)


class ProblemCode:
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CURSOR_INVALID = "CURSOR_INVALID"
    CURSOR_MISMATCH = "CURSOR_MISMATCH"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ALL = (
        VALIDATION_FAILED,
        CURSOR_INVALID,
        CURSOR_MISMATCH,
        UNAUTHORIZED,
        FORBIDDEN,
        NOT_FOUND,
        RATE_LIMITED,
        INTERNAL_ERROR,
    )
    #: Problem ``type`` URL per code.
    TYPES = {
        code: "https://docs.finlight.me/errors/" + code.lower().replace("_", "-") for code in ALL
    }


class RateLimitType:
    """``limitType`` of a 429 ``RATE_LIMITED`` problem (open list). ``UNKNOWN`` is the SDK's
    value when the server sent no ``limitType`` and the detail text did not tell."""

    MONTHLY = "monthly"
    BURST = "burst"
    UNKNOWN = "unknown"
    ALL = (MONTHLY, BURST)


class StreamEventKind:
    """``StreamEvent.kind``."""

    CREATED = "created"
    UPDATED = "updated"
    OTHER = "other"
    ALL = (CREATED, UPDATED, OTHER)


class ReconnectReason:
    """``ReconnectInfo.reason`` (open list)."""

    ROTATION = "rotation"
    WATCHDOG = "watchdog"
    CLOSED = "closed"
    HANDSHAKE_FAILED = "handshake_failed"
    SEARCH_FAILED = "search_failed"
    DIAL_FAILED = "dial_failed"
    DIAL_REFUSED = "dial_refused"
    CONNECTION_LIMIT = "connection_limit"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    ALL = (
        ROTATION,
        WATCHDOG,
        CLOSED,
        HANDSHAKE_FAILED,
        SEARCH_FAILED,
        DIAL_FAILED,
        DIAL_REFUSED,
        CONNECTION_LIMIT,
        RATE_LIMITED,
        QUOTA_EXCEEDED,
    )
