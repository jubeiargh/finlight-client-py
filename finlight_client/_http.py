"""REST transport: one request id per logical call, an explicit retry loop."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

from ._config import USER_AGENT, FinlightConfig
from ._version import __version__
from .errors import (
    FinlightApiError,
    FinlightDecodeError,
    FinlightNetworkError,
    FinlightTimeoutError,
    RateLimitedError,
    api_error_from_response,
)

logger = logging.getLogger("finlight_client")


@dataclass
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    request_id: str

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise FinlightDecodeError("response body is not valid JSON") from exc


def encode_query(params: Sequence[tuple[str, str]]) -> str:
    """Encode query parameters once. Commas inside a value are encoded as %2C."""
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in params)


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
        return seconds if seconds >= 0 else None
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    from datetime import datetime, timezone

    delta = (when - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, delta)


class HttpTransport:
    def __init__(self, config: FinlightConfig) -> None:
        self._config = config
        self._owns_session = config.session is None
        if config.session is not None:
            self._session = config.session
        else:
            session = requests.Session()
            # No hidden retries in the transport: the SDK runs its own loop.
            adapter = HTTPAdapter(max_retries=0)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._session = session

    def close(self) -> None:
        if self._owns_session:
            self._session.close()

    # -- one attempt -------------------------------------------------------

    def _send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: Optional[bytes],
        timeout: float,
    ) -> tuple[int, Mapping[str, str], bytes]:
        try:
            resp = self._session.request(
                method,
                url,
                data=body,
                headers=headers,
                timeout=timeout,
                stream=True,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            raise FinlightTimeoutError(f"request timed out after {timeout:g} s") from exc
        except requests.exceptions.RequestException as exc:
            raise FinlightNetworkError(f"network error: {type(exc).__name__}") from exc
        try:
            limit = self._config.max_response_bytes
            chunks: list[bytes] = []
            size = 0
            for chunk in resp.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > limit:
                    raise FinlightDecodeError(f"response is larger than {limit} bytes")
                chunks.append(chunk)
            return resp.status_code, resp.headers, b"".join(chunks)
        except requests.exceptions.Timeout as exc:
            raise FinlightTimeoutError(f"reading the response timed out after {timeout:g} s") from exc
        except requests.exceptions.RequestException as exc:
            raise FinlightNetworkError(f"network error while reading: {type(exc).__name__}") from exc
        finally:
            resp.close()

    # -- one logical call ----------------------------------------------------

    def call(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Sequence[tuple[str, str]]] = None,
        body: Optional[bytes] = None,
        headers: Optional[Mapping[str, str]] = None,
        ok_statuses: Sequence[int] = (200,),
    ) -> HttpResponse:
        cfg = self._config
        url = cfg.rest_url(path)
        if query:
            url += "?" + encode_query(query)
        request_id = str(uuid.uuid4())
        send_headers = {
            "X-API-KEY": cfg.api_key,
            "User-Agent": USER_AGENT,
            "x-client-version": __version__,
            "X-Request-Id": request_id,
            "Accept": "application/json",
        }
        if body is not None:
            send_headers["Content-Type"] = "application/json"
        if headers:
            send_headers.update(headers)

        start = cfg.monotonic()
        deadline = start + cfg.total_timeout if cfg.total_timeout is not None else None
        attempt = 0
        burst_used = False
        while True:
            timeout = cfg.timeout
            if deadline is not None:
                remaining = deadline - cfg.monotonic()
                if remaining <= 0:
                    raise FinlightTimeoutError(f"call ran out of its total time ({cfg.total_timeout:g} s)")
                timeout = min(timeout, remaining)

            error: Exception
            try:
                status, resp_headers, resp_body = self._send(method, url, send_headers, body, timeout)
            except (FinlightNetworkError, FinlightDecodeError) as exc:
                if isinstance(exc, FinlightDecodeError):
                    raise
                error = exc
                logger.debug("finlight: %s %s failed (%s), request id %s", method, path, exc.kind, request_id)
            else:
                logger.debug("finlight: %s %s -> %d, request id %s", method, path, status, request_id)
                if status in ok_statuses:
                    return HttpResponse(status, resp_headers, resp_body, request_id)
                api_error = api_error_from_response(
                    status,
                    resp_headers.get("content-type"),
                    resp_body,
                    sent_request_id=request_id,
                    retry_after=_parse_retry_after(resp_headers.get("retry-after")),
                )
                if isinstance(api_error, RateLimitedError):
                    if api_error.limit_type == "burst" and cfg.retry_on_burst == "once" and not burst_used:
                        # Contract: wait Retry-After seconds, burst_wait (10) when the header is missing.
                        wait = api_error.retry_after if api_error.retry_after is not None else cfg.burst_wait
                        if deadline is not None and cfg.monotonic() + wait > deadline:
                            raise api_error
                        logger.warning(
                            "finlight: burst limit reached, retrying once in %.1f s (request id %s)",
                            wait,
                            request_id,
                        )
                        burst_used = True
                        cfg.sleep(wait)
                        continue
                    raise api_error
                if status < 500:
                    raise api_error
                error = api_error

            if attempt >= cfg.max_retries:
                raise error
            delay = min(cfg.retry_backoff_max, cfg.retry_backoff_base * (2**attempt))
            delay = delay * (0.5 + 0.5 * cfg.random())
            attempt += 1
            if deadline is not None and cfg.monotonic() + delay > deadline:
                raise error
            logger.info(
                "finlight: retry %d/%d in %.2f s after %s (request id %s)",
                attempt,
                cfg.max_retries,
                delay,
                _describe(error),
                request_id,
            )
            cfg.sleep(delay)


def _describe(error: Exception) -> str:
    if isinstance(error, FinlightApiError):
        return f"HTTP {error.status}"
    return type(error).__name__
