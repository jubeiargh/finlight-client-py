# Changelog

## 3.0.0 (unreleased)

**Breaking release.** 3.0.0 speaks only the finlight API v3 (REST `/v3`, WebSocket `payloadVersion` 3,
v3 webhooks). Code written for 2.x does not run unchanged. To stay on 2.x, pin `finlight-client<3`.
Migration guide: https://docs.finlight.me/migration/v2-to-v3

Contract kit: 3.0.0-rc.3.

### Removed

- Everything from API v1 and v2: `FinlightApi`, `ApiConfig`, `ArticleService`, `SourcesService`,
  `WebSocketClient`, `RawWebSocketClient`, `WebhookService`, the v2 models and parameter classes.
- `setup.py` (the package is built from `pyproject.toml`).
- Python 3.7 to 3.9.

### Added

- `FinlightClient` and `FinlightConfig` with `articles.search`, `articles.search_all`
  (`SearchAllResult`), `articles.get`, `articles.get_by_link`, `companies.search`, `companies.get_many`,
  `companies.get` (ETag revalidation, `cache_info(record)`) and `sources.list`. Lists carry `skipped`
  (`SkippedEntry`) for entries that could not be read.
- `client.stream(...)` and `client.raw_stream(...)` return a `FinlightStream` (async iterator of
  `StreamEvent`): ping and pong watchdog, rotation before the 2 hour limit, the same subscribe after every
  reconnect, duplicate filter, `takeover` option, typed terminal errors (`PreemptedError`).
  Hooks get info objects: `on_admitted(AdmittedInfo)`, `on_reconnect(ReconnectInfo)`,
  `on_error(FinlightError)`, `on_quota_wait(QuotaWaitInfo)`.
- The reconnect backoff starts again from the base only after a pong or an article arrived on the
  connection. `connection.admitted` alone does not reset it (it comes before the subscribe is checked).
- Rotation opens the new connection before closing the old one. If that dial is refused or fails (for
  example 403 at a connection limit of 1, a network error or a 5xx), the stream closes the old connection
  and dials again at once, without `on_error`. Only a second failure waits as usual. A 401, missing
  WebSocket access or an exhausted quota with `quota_reconnect=False` still end the stream.
- When the monthly WebSocket quota is exhausted (dial 403 "quota exceeded" or `connection.preempted`
  with reason `quota_exceeded`), the stream tries again every hour until the quota allows it, logging a
  warning and calling `on_quota_wait` each time. On by default; `quota_reconnect=False` ends the stream
  with the error instead; `quota_reconnect_interval` sets the interval. A preempt with reason
  `connection_limit` stays terminal.
- `Webhooks.construct_event`, `Webhooks.construct_event_from_values` and `Webhooks.verify_signature`
  (`DEFAULT_WEBHOOK_TOLERANCE` 300 s). A correctly signed body that is not `payloadVersion` 3 returns
  `WrongPayloadVersion` (answer it with 2xx). Verification failures carry a snake_case `reason`.
- Errors: `FinlightApiError` (with `api_kind`) and one subclass per kind, `FinlightValidationError`
  (`param`), `FinlightNetworkError`, `FinlightTimeoutError`, `FinlightDecodeError` (`path`, `raw`),
  `WebhookVerificationError`, `PreemptedError`. Every error has a `kind` string.
- Retries: up to 3 for 5xx, network errors and timeouts; never for 400, 401, 403, 404 and monthly 429.
  A monthly 429 fails at once on REST, also inside `search_all`.
  A burst 429 waits exactly `Retry-After` (10 s without it) and retries once.
  This is on by default (`retry_on_burst="once"`); set `retry_on_burst="off"` to turn it off.
- Vocabulary constants (`EventType`, `CompanyRole`, `IncludeBlock`, `SortOrder`, `RateLimitType`, ...) as
  plain strings; unknown values are kept.
- `py.typed`, `User-Agent: finlight-client-python/3.0.0` and `x-client-version` on every request.
- Conformance suite: the shared API v3 contract kit runs in pytest (`CONFORMANCE.md`).

### Requirements

- Python 3.10+, `requests` 2.31+, `pydantic` 2.7+, `websockets` 15.0+.
