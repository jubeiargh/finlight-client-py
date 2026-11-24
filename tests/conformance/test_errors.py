"""E-01 .. E-25: error classes and retry classes, against a real local HTTP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from werkzeug.wrappers import Response

from finlight_client import (
    CursorInvalidError,
    CursorMismatchError,
    FinlightApiError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    ValidationFailedError,
)
from tests.support import fixtures, load

CASES = fixtures("fixtures/errors", exclude=("retry-classes.json",))

CLASSES = {
    "VALIDATION_FAILED": ValidationFailedError,
    "CURSOR_INVALID": CursorInvalidError,
    "CURSOR_MISMATCH": CursorMismatchError,
    "UNAUTHORIZED": UnauthorizedError,
    "FORBIDDEN": ForbiddenError,
    "NOT_FOUND": NotFoundError,
    "RATE_LIMITED": RateLimitedError,
    "INTERNAL_ERROR": InternalServerError,
}



@pytest.mark.parametrize(("case", "path"), CASES, ids=[c for c, _ in CASES])
def test_error(case: str, path: Path, httpserver: Any, make_client: Any, sleeps: Any) -> None:
    fx = load(f"fixtures/errors/{path.name}")
    req, resp, expect = fx["request"], fx["response"], fx["expect"]
    httpserver.expect_request(req["path"], method=req["method"]).respond_with_handler(
        lambda r: Response(
            resp["body"] if isinstance(resp["body"], str) else json.dumps(resp["body"]),
            status=resp["status"],
            headers={k: v for k, v in resp["headers"].items() if k.lower() != "content-type"},
            content_type=resp["headers"]["content-type"],
        )
    )
    # E-12 sends no key; the SDK always sends one, the server answer is what is tested.
    client = make_client(api_key=req["headers"].get("X-API-KEY", "sk_missing"))
    if "rawBody" in req:
        body = req["rawBody"].encode()
    elif "body" in req:
        body = json.dumps(req["body"]).encode()
    else:
        body = None

    with pytest.raises(FinlightApiError) as info:
        if req.get("query"):
            from urllib.parse import parse_qsl

            client._http.call(req["method"], req["path"], query=parse_qsl(req["query"]), body=body)
        else:
            client._http.call(req["method"], req["path"], body=body)
    err = info.value
    assert err.status == resp["status"]
    sent_ids = {entry[0].headers.get("X-Request-Id") for entry in httpserver.log}
    assert len(sent_ids) == 1, "one X-Request-Id per logical call, the same on every retry"

    code = expect["code"]
    if code == "NESTJS_FALLBACK":
        assert err.code is None
        assert err.detail == resp["body"]["message"]
        assert err.request_id == sent_ids.pop()
        if resp["status"] == 400:
            assert isinstance(err, ValidationFailedError)
        if resp["status"] == 404:
            assert isinstance(err, NotFoundError)
    elif code is None:
        assert type(err) is FinlightApiError and err.code is None
        assert err.raw == resp["body"]
        assert err.request_id == sent_ids.pop()
    else:
        assert type(err) is CLASSES[code] and err.code == code
        assert err.detail == resp["body"]["detail"] and err.title == resp["body"]["title"]
        assert err.type == resp["body"]["type"] == err.docs_url
        assert err.request_id == resp["body"]["requestId"]
        want_errors = resp["body"].get("errors", [])
        assert [(e.field, e.issue, e.allowed_values) for e in err.errors] == [
            (e["field"], e["issue"], e.get("allowedValues")) for e in want_errors
        ]
        assert json.loads(err.raw) == resp["body"]

    attempts = len(httpserver.log)
    retry = expect["retry"]
    if retry == "never":
        assert attempts == 1 and sleeps.calls == []
    elif retry == "once-after-burst-wait":
        assert isinstance(err, RateLimitedError) and err.limit_type == "burst"
        retry_after = resp["headers"].get("retry-after")
        assert err.retry_after == (float(retry_after) if retry_after else None)
        assert attempts == 2 and sleeps.calls == [err.retry_after if retry_after else 10.0]
    elif retry == "backoff":
        assert attempts == 4
        assert len(sleeps.calls) == 3 and sleeps.calls == sorted(sleeps.calls)
    else:
        raise AssertionError(retry)

    if case == "E-18":
        assert isinstance(err, RateLimitedError) and err.limit_type == "monthly" and err.is_quota_exhausted
        assert err.retry_after is None
    if case == "E-23":
        assert err.request_id.startswith("req_")
