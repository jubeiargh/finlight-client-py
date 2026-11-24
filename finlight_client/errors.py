"""Error types of the finlight client.

Every error raised by the SDK derives from :class:`FinlightError` and carries a
``kind`` string, so callers can tell errors apart without ``isinstance``.
Errors of third-party libraries are never raised directly; they are wrapped and
kept as ``__cause__``.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple, Optional

__all__ = [
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
    "classify_rate_limit",
]


class FinlightError(Exception):
    """Base class of every error the SDK raises."""

    kind: str = "finlight"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FieldIssue(NamedTuple):
    """One entry of ``errors[]`` in a problem response."""

    field: Optional[str]
    issue: Optional[str]
    allowed_values: Optional[list[str]] = None


class FinlightApiError(FinlightError):
    """An error answered by the finlight API (REST status or WebSocket error).

    ``code`` is an open string. Known codes have their own subclass; an unknown
    code stays on this base class.
    """

    kind = "api"

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        type: Optional[str] = None,
        title: Optional[str] = None,
        detail: Optional[str] = None,
        request_id: Optional[str] = None,
        errors: Optional[list[FieldIssue]] = None,
        raw: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.type = type
        self.title = title
        self.detail = detail
        self.request_id = request_id
        self.errors: list[FieldIssue] = list(errors or [])
        self.raw = raw
        self.retry_after = retry_after

    @property
    def docs_url(self) -> Optional[str]:
        """Link to the error page on docs.finlight.me (the problem ``type``)."""
        return self.type

    def raw_json(self) -> Any:
        """The error body parsed as a JSON tree, or ``None`` if it is not JSON."""
        if self.raw is None:
            return None
        try:
            return json.loads(self.raw)
        except ValueError:
            return None

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status={self.status!r}, code={self.code!r}, "
            f"detail={self.detail!r}, request_id={self.request_id!r})"
        )


class ValidationFailedError(FinlightApiError):
    """``VALIDATION_FAILED``: the server rejected the request or subscribe."""


class CursorInvalidError(FinlightApiError):
    """``CURSOR_INVALID``: the cursor could not be decoded."""


class CursorMismatchError(FinlightApiError):
    """``CURSOR_MISMATCH``: sort or filters changed since the cursor was issued."""


class UnauthorizedError(FinlightApiError):
    """``UNAUTHORIZED``: missing or invalid API key."""


class ForbiddenError(FinlightApiError):
    """``FORBIDDEN``: the plan lacks the needed entitlement."""


class NotFoundError(FinlightApiError):
    """``NOT_FOUND``: the lookup found nothing."""


class RateLimitedError(FinlightApiError):
    """``RATE_LIMITED``: monthly quota or burst limit reached.

    ``limit_type`` is ``"monthly"``, ``"burst"``, ``"unknown"`` or a newer value
    the server sent (kept as a string). ``retry_after`` is the ``Retry-After``
    header in seconds (sent on burst only).
    """

    def __init__(self, message: str, *, limit_type: str = "unknown", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.limit_type = limit_type

    @property
    def is_quota_exhausted(self) -> bool:
        return self.limit_type == "monthly"


class InternalServerError(FinlightApiError):
    """``INTERNAL_ERROR``: the server could not process the request."""


class FinlightValidationError(FinlightError, ValueError):
    """A request was rejected locally, before anything was sent."""

    kind = "validation"


class FinlightNetworkError(FinlightError):
    """The request or connection failed on the network level."""

    kind = "network"


class FinlightTimeoutError(FinlightNetworkError, TimeoutError):
    """An attempt or the whole call ran out of time."""

    kind = "timeout"


class FinlightDecodeError(FinlightError):
    """A response could not be read into the SDK models."""

    kind = "decode"

    def __init__(self, message: str, *, raw: Any = None) -> None:
        super().__init__(message)
        self.raw = raw


class WebhookVerificationError(FinlightError):
    """A webhook request failed verification. ``reason`` says why."""

    kind = "webhook_verification"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class PreemptedError(FinlightError):
    """The server ended the stream with ``connection.preempted``. Terminal."""

    kind = "preempted"

    def __init__(
        self,
        message: str,
        *,
        reason: Optional[str],
        new_lease_id: Optional[str],
        timestamp: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.new_lease_id = new_lease_id
        self.timestamp = timestamp


_CODE_CLASSES: dict[str, type[FinlightApiError]] = {
    "VALIDATION_FAILED": ValidationFailedError,
    "CURSOR_INVALID": CursorInvalidError,
    "CURSOR_MISMATCH": CursorMismatchError,
    "UNAUTHORIZED": UnauthorizedError,
    "FORBIDDEN": ForbiddenError,
    "NOT_FOUND": NotFoundError,
    "RATE_LIMITED": RateLimitedError,
    "INTERNAL_ERROR": InternalServerError,
}


_STATUS_CLASSES: dict[int, type[FinlightApiError]] = {
    400: ValidationFailedError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
}


def classify_rate_limit(limit_type: Any, detail: Any) -> str:
    """The one place that sorts a 429 into ``monthly``, ``burst`` or ``unknown``.

    The problem member ``limitType`` wins and is kept as sent (it is an open list:
    an unknown value stays a string and is never retried). Without it the
    ``detail`` text decides, compared as exact, case-sensitive substrings.
    """
    if isinstance(limit_type, str) and limit_type:
        return limit_type
    if isinstance(detail, str):
        if "Exceeded token limit" in detail:
            return "monthly"
        if "Exceeded rate limit" in detail:
            return "burst"
    return "unknown"


def _issues_from(value: Any) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    if not isinstance(value, list):
        return issues
    for item in value:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        issue = item.get("issue")
        allowed = item.get("allowedValues")
        if issue is None and isinstance(item.get("constraints"), dict):
            texts = [str(v) for v in item["constraints"].values()]
            issue = "; ".join(texts) if texts else None
        issues.append(
            FieldIssue(
                field=field if isinstance(field, str) else None,
                issue=issue if isinstance(issue, str) else None,
                allowed_values=(
                    [v for v in allowed if isinstance(v, str)] if isinstance(allowed, list) else None
                ),
            )
        )
    return issues


def api_error_from_response(
    status: int,
    content_type: Optional[str],
    body: bytes,
    *,
    sent_request_id: Optional[str],
    retry_after: Optional[float] = None,
) -> FinlightApiError:
    """Build the API error for a non-2xx REST answer.

    Reading order: ``application/problem+json``, then the NestJS form
    ``{statusCode, message}``, then a body that is not JSON (status plus text).
    """
    text = body.decode("utf-8", errors="replace")
    parsed: Any = None
    try:
        parsed = json.loads(text) if text.strip() else None
    except ValueError:
        parsed = None

    ctype = (content_type or "").lower()
    is_problem = isinstance(parsed, dict) and (
        "problem+json" in ctype or ("code" in parsed and ("type" in parsed or "title" in parsed))
    )
    if is_problem:
        assert isinstance(parsed, dict)
        code = parsed.get("code") if isinstance(parsed.get("code"), str) else None
        detail = parsed.get("detail") if isinstance(parsed.get("detail"), str) else None
        title = parsed.get("title") if isinstance(parsed.get("title"), str) else None
        ptype = parsed.get("type") if isinstance(parsed.get("type"), str) else None
        request_id = parsed.get("requestId") if isinstance(parsed.get("requestId"), str) else None
        problem_status = parsed.get("status")
        eff_status = status
        if not status and isinstance(problem_status, int) and not isinstance(problem_status, bool):
            eff_status = problem_status
        kwargs: dict[str, Any] = dict(
            status=eff_status,
            code=code,
            type=ptype,
            title=title,
            detail=detail,
            request_id=request_id or sent_request_id,
            errors=_issues_from(parsed.get("errors")),
            raw=text,
            retry_after=retry_after,
        )
        message = f"finlight API error {eff_status}"
        if code:
            message += f" {code}"
        if detail:
            message += f": {detail}"
        if code == "RATE_LIMITED" or (code is None and eff_status == 429):
            return RateLimitedError(
                message, limit_type=classify_rate_limit(parsed.get("limitType"), detail), **kwargs
            )
        cls = _CODE_CLASSES.get(code or "", FinlightApiError)
        return cls(message, **kwargs)

    if isinstance(parsed, dict) and "statusCode" in parsed and "message" in parsed:
        msg = parsed.get("message")
        if isinstance(msg, list):
            detail = "; ".join(str(m) for m in msg)
            issues = [FieldIssue(field=None, issue=str(m)) for m in msg]
        else:
            detail = str(msg) if msg is not None else None
            issues = []
        message = f"finlight API error {status}"
        if detail:
            message += f": {detail}"
        if status == 429:
            return RateLimitedError(
                message,
                limit_type=classify_rate_limit(None, detail),
                status=status,
                detail=detail,
                title=parsed.get("error") if isinstance(parsed.get("error"), str) else None,
                request_id=sent_request_id,
                errors=issues,
                raw=text,
                retry_after=retry_after,
            )
        # No code in this form: the HTTP status picks the kind.
        cls = _STATUS_CLASSES.get(status, FinlightApiError)
        return cls(
            message,
            status=status,
            detail=detail,
            title=parsed.get("error") if isinstance(parsed.get("error"), str) else None,
            request_id=sent_request_id,
            errors=issues,
            raw=text,
            retry_after=retry_after,
        )

    snippet = text.strip()
    if len(snippet) > 200:
        snippet = snippet[:200] + "..."
    message = f"finlight API error {status}"
    if snippet:
        message += f": {snippet}"
    if status == 429:
        return RateLimitedError(
            message,
            limit_type="unknown",
            status=status,
            detail=text or None,
            request_id=sent_request_id,
            raw=text,
            retry_after=retry_after,
        )
    return FinlightApiError(
        message,
        status=status,
        detail=text or None,
        request_id=sent_request_id,
        raw=text,
        retry_after=retry_after,
    )
