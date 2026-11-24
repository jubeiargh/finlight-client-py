# finlight-client (Python)

*English | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md)*

> **Breaking release.** Version 3.0.0 speaks only the finlight API v3. Code written for 2.x does not run
> unchanged. To stay on 2.x (API v2), pin `finlight-client<3`. See [Migrating from 2.x](#migrating-from-2x).

Python client for the [finlight](https://finlight.me) news API: search and look up financial news,
companies and sources over REST, stream articles in real time over WebSocket, and verify webhooks.

## Versions

| SDK version | API version | Status |
|---|---|---|
| 3.x | v3 (REST `/v3`, WebSocket `payloadVersion` 3, v3 webhooks) | current |
| 2.x | v2 | no further releases |

SDK and API versions are independent. Other finlight SDKs that speak API v3: TypeScript 4.x, PHP 2.x,
Go module `/v2`, .NET 2.x, Java 1.x, Ruby 1.x, Rust 0.2.

## Requirements

- Python 3.10 or newer
- `requests` 2.31+, `pydantic` 2.7+, `websockets` 15.0+

## Installation

```bash
pip install "finlight-client>=3,<4"
```

## Quick start

```python
from finlight_client import FinlightClient

with FinlightClient(api_key="YOUR_API_KEY") as client:
    page = client.articles.search(query="ticker:NVDA", limit=10, include=["companies"])
    for article in page.articles:
        print(article.published_at, article.title)
```

REST calls are synchronous. Streams are async iterators. Arguments use snake_case; each one maps to
exactly one key of the API (`from_` is `from`). Only the arguments you pass are sent.

## Search articles

```python
page = client.articles.search(
    query="eventType:mna AND companyCountry:US",
    languages=["en", "de"],
    from_="2026-11-01",               # str, date, or an aware datetime
    event_types=["mna"],
    min_relevance=0.5,
    order_by="availableAt",
    include=["content", "companies", "events"],
    limit=50,
)
print(page.has_more, page.next_cursor)
```

`search_all` walks the pages for you. It freezes the request when you call it and only adds the
cursor on later pages. It stops after `max_pages` pages (default 10), because every page costs quota.

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

A result can be iterated once. Unknown arguments raise `TypeError`; wrong shapes (for example `limit=0`
or `languages=[]`) raise `FinlightValidationError` before anything is sent. Values of vocabularies are
not checked locally, so new server values work without an SDK update.

## Look up articles, companies and sources

```python
article = client.articles.get("EU8JwpsZ8iJehuyPZjMqRz", include=["content"])
article = client.articles.get_by_link("https://www.reuters.com/...")

companies = client.companies.search("NVDA", mic="XNAS")   # at most 10, no pages
companies = client.companies.get_many([4821, 1001])
company = client.companies.get(4821)                      # revalidated with its ETag next time

sources = client.sources.list()
```

A miss raises `NotFoundError`. Company lookups need the `entityAccess` entitlement (`ForbiddenError`
otherwise).

### Reading articles

- `content` and `sentiment` have three states. `article.content_present` is false when the key was not
  sent (not requested or not entitled); `article.content is None` with `content_present` true means "no
  text". The same goes for `sentiment_present`.
- `companies` and `events` are `None` when not sent, and `[]` when the article was tagged and nothing
  was found. Check `companies_present` and `events_present`.
- `events[].company_ids` is only sent when `companies` is in the same answer.
- Timestamps are kept as the strings that were sent (`published_at`). `published_at_time` and the other
  `*_time` properties parse them strictly and return `None` for anything unreadable.
- Unknown keys from newer servers are ignored. `finlight_client.raw_json(article)` gives the raw JSON.
- Vocabulary values stay plain strings. Compare them with the constants in `finlight_client`
  (`EventType.MNA`, `Role.ACQUIRER`, ...). Unknown values are kept as sent.

## Real-time streams

```python
import asyncio
from finlight_client import FinlightClient

async def main() -> None:
    client = FinlightClient(api_key="YOUR_API_KEY")
    async with client.stream(
        query="ticker:NVDA",
        language="en",
        include=["companies", "events"],
        include_updates=True,
        on_reconnect=lambda last_seen, reason: print("reconnected", reason, last_seen),
    ) as stream:
        async for event in stream:
            print(event.kind, event.data.title if event.data else event.event)

asyncio.run(main())
```

- `event.kind` is `created`, `updated` or `other` (an event this SDK does not know yet).
- `client.raw_stream(query=..., sources=..., exclude_sources=..., language=..., include_updates=...)`
  delivers articles before enrichment: no `include`, no content, sentiment, companies or events.
- The stream pings every 25 s, reconnects when no pong came for 60 s, and opens a fresh connection
  after 115 minutes. After each reconnect it sends the same subscribe and drops duplicates.
- It never backfills. `on_reconnect(last_seen, reason)` gets the latest `availableAt` (raw:
  `firstSeenAt`) you saw. Fill gaps with `articles.search_all(from_=last_seen, order_by="availableAt")`
  (raw: `order_by="firstSeenAt"`).
- Terminal problems end the loop with an error: invalid key (`UnauthorizedError`), no WebSocket access
  (`ForbiddenError`), a rejected subscribe (`ValidationFailedError`), and `PreemptedError` when another
  connection took over. Other problems reconnect and go to `on_error`.
- When the monthly WebSocket quota is used up (the dial is refused, or `PreemptedError` with reason
  `quota_exceeded`), the stream does not end: it tries again every hour until the quota allows it. Each
  attempt logs a warning and calls `on_error`. Set `quota_reconnect=False` to end the stream with the
  error instead; `quota_reconnect_interval` changes the hour.
- Leaving the `async with` block closes the socket. Cancellation is never swallowed.

Limits to know:

- Your plan's connection limit is shared by enriched, raw and older SDK connections. A new connection
  while the limit is reached is refused; the SDK retries after 60 s. Pass `takeover=True` to the client
  to replace the oldest connection instead.
- Right after subscribing, the server sends the newest matching article once (also after every
  reconnect). It can be old.
- Live frames over 32,000 bytes are dropped by the server without notice. This can happen with
  `include=["content"]` on long articles. Fetch them with `articles.get`.
- `connection.admitted` arrives before the server checks the subscribe. It does not mean it was accepted.
- WebSocket connections use the proxy settings from the environment (`HTTPS_PROXY`, `ALL_PROXY`), as the
  `websockets` library does. Pass `websocket_options={"proxy": None}` to turn that off.

## Webhooks

finlight signs every webhook. Verify it with the **raw** request body, before parsing anything:

```python
from finlight_client import Webhooks, WebhookEvent, WrongPayloadVersion, WebhookVerificationError

def handle(raw_body: bytes, headers) -> int:
    try:
        result = Webhooks.construct_event(raw_body, headers, WEBHOOK_SECRET)
    except WebhookVerificationError:
        return 400
    if isinstance(result, WrongPayloadVersion):
        keep_for_later(result.raw)          # an old v2 body: answer 2xx anyway
        return 204
    if already_seen(result.event_id):       # deliveries can repeat: deduplicate on event_id
        return 204
    queue_for_processing(result)            # answer within 5 s, work afterwards
    return 204
```

- `headers` can be any header mapping or list of pairs (Flask, Django, Starlette, `http.server`, WSGI
  environ). Names are matched without regard to case. `construct_event_from_values(raw_body, signature,
  timestamp, secret)` takes the two header values directly; `verify_signature` only checks.
- The timestamp must be within 300 s (`tolerance`) in both directions.
- `result.is_test` is true for the dashboard test webhook. It is not cut by your plan.
- Never answer with 410: it disables the webhook at once. Ten non-2xx answers in a row disable it too.

Getting the raw body:

| Framework | Raw body |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

Switching a webhook to v3: deploy this SDK first; answer `WrongPayloadVersion` with 2xx and keep its
raw JSON; then switch the webhook to `payloadVersion` 3 in the dashboard; then wait about 2 hours,
because retries queued before the switch still arrive in the old format.

## Errors and retries

All errors derive from `FinlightError` and carry a `kind` string.

| Error | When |
|---|---|
| `FinlightApiError` | The API answered with an error. `status`, `code`, `title`, `detail`, `request_id`, `errors`, `raw`, `docs_url`. Subclasses per code: `ValidationFailedError`, `CursorInvalidError`, `CursorMismatchError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `RateLimitedError`, `InternalServerError`. Unknown codes stay on the base class. |
| `RateLimitedError` | `limit_type` is `monthly`, `burst` or a newer value; `retry_after` in seconds. |
| `FinlightValidationError` | A request was rejected locally (a `ValueError`). |
| `FinlightNetworkError`, `FinlightTimeoutError` | Network failure or timeout. The original error is `__cause__`. |
| `FinlightDecodeError` | A single response could not be read. |
| `WebhookVerificationError` | A webhook failed verification (`reason`). |
| `PreemptedError` | Another connection took over the stream (`reason`, `new_lease_id`). With `quota_reconnect=False` also when the quota ran out. |

Retries: 5xx answers, network errors and timeouts are retried up to 3 times with growing waits, the
search included. 400, 401, 403, 404 and a monthly 429 are never retried: a monthly 429 fails at once,
also inside `search_all`; only streams wait for the quota (see above). A burst 429 waits
`Retry-After` seconds (10 without the header) and tries once more; set `retry_on_burst="off"` to turn
that off. Every call sends its own `X-Request-Id`, the same on each retry. Press Ctrl+C to stop a call;
waits end at once and nothing is retried.

## Configuration

```python
client = FinlightClient(
    api_key="YOUR_API_KEY",
    base_url="https://api.finlight.me",   # a trailing slash is fine
    wss_url="wss://wss.finlight.me",      # raw streams use <wss_url>/raw
    timeout=30.0,                         # seconds per attempt
    total_timeout=None,                   # optional cap per call, retries included
    max_retries=3,
    retry_on_burst="once",                # or "off"
    max_pages=10,
    ping_interval=25.0, pong_timeout=60.0, rotation_interval=6900.0,
    takeover=False,
    quota_reconnect=True, quota_reconnect_interval=3600.0,
    session=None,                         # your own requests.Session
)
```

All times are seconds. You can also build a `FinlightConfig` and pass `config=`. With your own
`requests.Session`, its timeouts, proxies and adapters apply; do not add retry adapters, because every
attempt costs quota. The SDK never closes a session it did not create. `websocket_options` go to
`websockets.connect`. The SDK logs through the `finlight_client` logger and is silent by default.

## Data notes

- Old articles can carry `published_at` `"1970-01-01T00:00:00.000Z"`. It is delivered as sent.
- Empty texts come as `None` (`summary`, `content`).
- Articles tagged before roles existed have `role` and `relevance` `None` and `events` `[]`.
- `articles.get(id)` answers 404 for articles indexed before ids existed. Use `get_by_link`.
- `available_at` is `None` on older articles and always `None` on raw streams.

## Migrating from 2.x

The full guide is on [docs.finlight.me](https://docs.finlight.me/migration/v2-to-v3). The short version:

| 2.x | 3.x |
|---|---|
| `FinlightApi(ApiConfig(api_key=...))` | `FinlightClient(api_key=...)` |
| `articles.fetch_articles(GetArticlesParams(...))` | `articles.search(...)`, `articles.search_all(...)` |
| `page` / `pageSize` | `limit` / `cursor` |
| `includeContent`, `includeEntities` | `include=["content", "companies", "events"]` |
| `order="DESC"` | `order="desc"` |
| `publishDate`, `createdAt`, `revisedDate` | `published_at`, `first_seen_at`, `revised_at` |
| `images` | `media[].url` |
| `source` (string) | `source.domain` |
| `sentiment`, `confidence` | `sentiment.label`, `sentiment.confidence` |
| `api.websocket.connect(...)` | `async for event in client.stream(...)` |
| `api.raw_websocket` | `client.raw_stream(...)` |
| webhook `isUpdate` | `event.event == "article.updated"` |
| webhook body | `event.data`, plus `event.event_id` for deduplication |

Do not run 2.x and 3.x streams side by side on one key: they share the connection limit.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`CONFORMANCE.md` maps every case of the contract kit to its test. Live tests run only against dev
and need `FINLIGHT_API_KEY`, `FINLIGHT_BASE_URL` and `FINLIGHT_WSS_URL`:
`pytest tests/live -m live --force-enable-socket`.

## License

MIT
