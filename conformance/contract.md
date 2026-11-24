# finlight API v3 wire contract

Contract version: see `CONTRACT_VERSION`. This document is the public wire contract for API v3 clients (REST,
WebSocket, Webhooks). The fixtures in this kit are generated from the server code and are the authority where
this text and a fixture disagree; `conformance.md` lists the cases every client must pass.

## 1. Channels and versions

| Channel | Endpoint | Auth |
|---|---|---|
| REST | `https://api.finlight.me/v3/...` | header `X-API-KEY` |
| WebSocket, enriched | `wss://wss.finlight.me` | header `x-api-key` (lowercase, see 3.1) |
| WebSocket, raw | `wss://wss.finlight.me/raw` | same |
| Webhooks | finlight POSTs to the customer URL | HMAC signature (section 4) |

- REST is versioned in the path (`/v3/`).
- WebSocket and webhooks use the same endpoints for every version. The version is chosen per subscription by
  `payloadVersion`. Only the JSON integer `3` selects v3; anything else (absent, `"3"`, `2`, `4`) means v2.
- REST, WebSocket and webhooks deliver the same article object (section 2.5), built by one mapper.
- Projection vocabulary everywhere: `include` with values `content`, `companies`, `events`. Sentiment needs no
  include.
- All timestamps in responses are ISO 8601 UTC with milliseconds (`2026-11-23T21:04:05.123Z`).

## 2. REST v3

### 2.1 Common rules

- Auth: `X-API-KEY: <key>`. Missing or invalid key: 401 `UNAUTHORIZED`.
- Success is `application/json`. Errors from the v3 routes are `application/problem+json` (2.8).
- Metering and throttling apply to the article endpoints (`/v3/articles/search`, `/v3/articles/{id}`,
  `/v3/articles/by-link`):
  - Monthly quota exhausted: 429 `RATE_LIMITED` with `"limitType": "monthly"` and no `Retry-After`.
  - Burst limit: 429 `RATE_LIMITED` with `"limitType": "burst"` and a `Retry-After` header in seconds (the rest
    of the 10-second window, 1 to 10).
  - Tell the two apart by `limitType`, not by `detail` (the text is not stable). `limitType` is an open list: an
    unknown value is kept as a string and not retried. There are no other rate-limit headers.
  - A request that fails validation has already been counted.
- `X-Request-Id`: when sent, it is echoed as `requestId` in error bodies. Without it the server generates
  `req_<uuid>`. It is not returned as a response header.
- Unknown request fields (body or query) are **removed silently**, not rejected. Enum values are validated
  strictly. Clients therefore reject unknown request keys themselves (conformance R-12).

### 2.2 `POST /v3/articles/search`

JSON body, every field optional.

| Field | Type | Rules | Default |
|---|---|---|---|
| `query` | string | Query language. An unknown field name is a 400. Free text containing `:` must be quoted. | – |
| `sources`, `optInSources`, `excludeSources` | string[] | Domains. `sources` and `optInSources` cannot be combined. | – |
| `sourceTypes`, `excludeSourceTypes` | string[] | `vocab.json` `request.sourceTypes`. Articles of unclassified sources (`source.type` null) never match `sourceTypes` and are kept by `excludeSourceTypes`. Both filter inside the source pool and never add a source to it. | – |
| `from`, `to` | string | ISO 8601 (send UTC with milliseconds). Bounds on the `orderBy` timestamp. | `to` = now |
| `languages` | string[] | ISO 639-1, non-empty (`[]` is a 400). | `["en"]` |
| `tickers` | string[] | `SYMBOL`, `SYMBOL@MIC`, vendor notations (`000660.KS`, `NASDAQ:AAPL`). | – |
| `countries` | string[] | ISO 3166-1 alpha-2: the story's geographic focus. | – |
| `categories` | string[] | Open vocabulary. | – |
| `hasContent` | boolean | `true` keeps only articles with content. | `false` |
| `roles` | string[] | `vocab.json` `request.roles`. Correlated with `tickers`/`minRelevance` on the same company. | – |
| `minRelevance` | number | 0 to 1. | – |
| `eventTypes`, `eventDirections` | string[] | `vocab.json`. Correlated on the same event. | – |
| `minImportance` | string | `low`, `medium`, `high`, `critical` (ordinal). | – |
| `sectors`, `companyCountries`, `exchanges` | string[] | Apply to the event when an event filter is present, otherwise to the tagged company. | – |
| `orderBy` | string | `publishedAt`, `firstSeenAt`, `revisedAt`, `availableAt`. | `publishedAt` |
| `order` | string | `asc`, `desc` (lowercase). | `desc` |
| `limit` | integer | 1 to 100. | 20 |
| `cursor` | string | `pagination.nextCursor` of the previous page. | – |
| `include` | string[] | `content`, `companies`, `events`. | `[]` |

Semantics:
- Filtering is free; the plan decides which blocks are delivered, not which filters may be used.
- The date range is clamped by the plan, silently. Because an upper bound is always applied to the `orderBy`
  field, articles that lack that field never appear (for example `orderBy: availableAt` returns only articles
  from after `availableAt` was introduced).
- Sorting is by timestamp only; there is no relevance sort and no `total`.

Response 200: `{"articles": Article[], "pagination": {"limit", "returned", "hasMore", "nextCursor"}}`.

**Cursor rules**
- The cursor is opaque. Do not parse it.
- Re-send the identical body on every page; only `cursor`, `limit` and `include` may change.
- Filters are compared as sets (order and duplicates in lists do not matter) but values are not normalised:
  `["EN"]` differs from `["en"]`, and an absent field differs from its default. A client that adds `to = now`,
  default languages or any other default on a later page gets 400 `CURSOR_MISMATCH`.
- Changed sort or changed filters: 400 `CURSOR_MISMATCH`. A cursor that cannot be read: 400 `CURSOR_INVALID`.
- End of results: `hasMore: false` and `nextCursor: null`. Cursors do not expire. Pages are not a snapshot.

### 2.3 `GET /v3/articles/{id}`

- `include` as one comma-joined value (`?include=content,events`). The repeated form also works; SDKs use the
  comma form.
- 200 `{"article": Article}`. 404 `NOT_FOUND` also for articles indexed before ids were introduced; those are
  reachable by link.

### 2.4 `GET /v3/articles/by-link?link=<url-encoded>&include=...`

- `link` is required and must equal the delivered `link` exactly. Reaches every article.
- 200 `{"article": Article}`, 404 `NOT_FOUND`.

### 2.5 The article object

| Field | Type | Presence | Notes |
|---|---|---|---|
| `id` | string | always | 22 characters, base64url alphabet. Same in every channel, derived from the link. Opaque. |
| `link` | string | always | |
| `source` | object | always | `{domain: string, type: string\|null}`. `type` is the source type (open enum, `vocab.json` `response.sourceTypes`) when the article was indexed. It can lag `type` in `/v3/sources` after a reclassification. Null when the source is not classified or the article was indexed before source types existed. |
| `title` | string | always | Original-language title. |
| `summary` | string\|null | always | Never `""`: an empty or whitespace-only summary is delivered as `null`. |
| `language` | string\|null | always | ISO 639-1. |
| `media` | `{url}[]` | always, may be `[]` | Images, at most 3. |
| `publishedAt` | string\|null | always | As claimed by the source. Legacy data can carry `1970-01-01T00:00:00.000Z`; delivered as is. |
| `firstSeenAt` | string\|null | always | When finlight first saw the article. |
| `revisedAt` | string\|null | always | The source's revision time; null when none or when it equals `publishedAt`. Not an update signal. |
| `availableAt` | string\|null | always | When the enriched article became available. Null on older data and always null on raw. |
| `countries` | string[] | always, may be `[]` | |
| `categories` | string[] | always, may be `[]` | Open vocabulary. |
| `content` | string\|null | gated | Present only with `include: content` and full-article access; never on raw. Never `""`: empty or whitespace-only is `null`. |
| `sentiment` | object\|null | gated | Present with sentiment access (no include needed); never on raw. `{label: string\|null, confidence: number\|null}`. |
| `companies` | Company[] | gated | Present only with `include: companies` and entity access. `[]` = tagged, no company. |
| `events` | Event[] | gated | Present only with `include: events` and event access. `[]` = classified, no event. |

Company: `{companyId: integer, name: string, isin: string|null, primaryListing: {ticker, mic|null, country|null}|null,
confidence: number|null, role: string|null, relevance: number|null}`. `primaryListing: null` means no listing (for
example a private company). `role` is the company's position in the story; `relevance` (0 to 1) is how much the
article is about it. Both are null on articles tagged before roles existed.

Event: `{type: string, direction: string|null, importance: string|null, confidence: number|null, companyIds?: integer[]}`.
`companyIds` is present only when `companies` is present in the same payload; otherwise the key is absent.

Numbers are JSON numbers and are not rounded.

### 2.6 Companies (entity access required, else 403 `FORBIDDEN`)

`GET /v3/companies?q=<text>&mic=<mic>` or `GET /v3/companies?ids=<id>,<id>`:
- Exactly one of `q` (at most 200 characters) or `ids` (1 to 10 comma-joined integers). Neither or both: 400.
- `mic` narrows a `q` lookup; it does not change the ranking.
- At most 10 results, no pagination. Unknown ids are left out. Result order is not guaranteed.
- 200 `{"companies": CompanyRecord[]}`.

`GET /v3/companies/{companyId}`: 200 `{"company": CompanyRecord}` with `ETag` and
`Cache-Control: public, max-age=86400, stale-while-revalidate=604800`. A matching `If-None-Match` answers 304 with
an empty body. A non-integer id is a 400; an unknown id a 404.

CompanyRecord: `{companyId, name, country|null, sector|null, industry|null, isins: string[],
primaryListing: {ticker, mic, country}|null, listings: {ticker, mic, country, active}[], updatedAt|null}`.
`listings` names each exchange (`mic`) at most once. The primary listing is always in it and comes first; for every
other exchange the server picks one listing (active before expired, then the primary's symbol, then the shortest).
Expired listings appear (`active: false`) where they are the only one on their exchange.

The company endpoints are not metered.

### 2.7 `GET /v3/sources`

No parameters, not metered. 200 `{"sources": Source[]}`, sorted by domain.
Source: `{domain, name: string|null, type: string|null, isDefault: boolean, isCustom: boolean, country: string|null,
languages: string[], hasContent?: boolean}`. `type` is the source type (open enum, `vocab.json` `response.sourceTypes`), null when not
classified. `hasContent` is present only with full-article access; absent means
"not entitled to know", never "no content". Custom sources appear only when granted to the subscription.

### 2.8 Errors (RFC 9457)

```json
{
  "type": "https://docs.finlight.me/errors/validation-failed",
  "title": "Validation failed",
  "status": 400,
  "detail": "1 request field is not valid.",
  "code": "VALIDATION_FAILED",
  "requestId": "req-123",
  "errors": [ { "field": "eventTypes", "issue": "each value in eventTypes must be one of ...", "allowedValues": ["earnings", "..."] } ]
}
```

- `type` is `https://docs.finlight.me/errors/<code in lower case, _ as ->`.
- `errors[]` appears for validation and cursor errors. `field` names the request field (a path such as `a.b` or
  `list[0]` where the server reports one; see the error fixtures for the exact values). `issue` is a human-readable
  text, not a stable value. `allowedValues` appears for the closed vocabularies (`include`, `orderBy`, `order`,
  `roles`, `eventTypes`, `eventDirections`, `minImportance`, `sourceTypes`, `excludeSourceTypes`). A
  query-language error names the field `badQuery`.

| `code` | HTTP | When |
|---|---|---|
| `VALIDATION_FAILED` | 400 | Invalid field, query-language error, companies `q`/`ids` rules. |
| `CURSOR_INVALID` | 400 | Cursor cannot be read or has an unsupported version. |
| `CURSOR_MISMATCH` | 400 | Sort or filters changed since the cursor was issued. |
| `UNAUTHORIZED` | 401 | Missing or invalid API key. |
| `FORBIDDEN` | 403 | Entity access missing on `/v3/companies*`. |
| `NOT_FOUND` | 404 | Lookup miss. |
| `RATE_LIMITED` | 429 | Monthly quota or burst limit; member `limitType` (`monthly`, `burst`), burst with `Retry-After` (see 2.1). |
| `INTERNAL_ERROR` | 500 | `detail` is always `The request could not be processed.` |

Problem codes are an open list. Two failures come back in the framework's default form `{statusCode, message, error}`
instead of problem+json: a malformed JSON body (400) and an unknown route (404). Clients fall back to the HTTP status
and `message`. Infrastructure in front of the API can answer with a non-JSON body (for example a 502 HTML page).

**Retry model (all clients)**
- Never retried: 400, 401, 403, 404, and a 429 with `limitType` `monthly` (or a value the client does not know).
  A REST call never waits for a new quota period: a monthly 429 fails at once, inside `searchAll` too.
- Burst 429 (`limitType: "burst"`): one retry after exactly `Retry-After` seconds, 10 when the header is missing.
  On by default, can be switched off; it does not count against the normal retries.
- 5xx, non-JSON gateway errors and network errors: exponential backoff, POST search included.
- One `X-Request-Id` per logical call, reused on every retry.

## 3. WebSocket v3

### 3.1 Connect

- URL `wss://wss.finlight.me` (enriched) or `wss://wss.finlight.me/raw`.
- API key in the header `x-api-key`. The header name must be sent **in lower case**: the lookup is case-sensitive.
  (A query parameter `apiKey` also works but puts the key into URLs and logs; SDKs do not use it.)
- Optional: `x-takeover: true` (replace the stalest existing connection), `x-client-version: <sdk/version>`.
- `payloadVersion` is chosen per subscribe message, not at connect.
- A refused connect answers with an HTTP status; many WebSocket libraries expose only the status:

| Status | Body | Cause | Client |
|---|---|---|---|
| 401 | `{"error":"Missing API-KEY"}` | No key. | terminal |
| 401 | `{"message":"Invalid API key"}` / `{"message":"Invalid API key format"}` | Invalid key. | terminal |
| 403 | `{"message":"Your subscription does not include WebSockets"}` | Plan without WebSockets. | terminal |
| 403 | `{"message":"Too many concurrent connections. Use x-takeover: true header to replace an existing connection."}` | At the connection limit. | reconnect, long backoff (first retry after about 60 s), takeover hint |
| 403 | `{"message":"WebSocket quota exceeded for the current period"}` | Delivery quota used up. | redial once per hour, each attempt reported (default; terminal when switched off) |
| 403 | `{"message":"Too many concurrent connections"}` | Lost a race at admission. | reconnect with backoff |
| 500 | `{"error":"Internal server error"}` | Server error. | reconnect with backoff |

- The connection limit is shared between enriched and raw connections and between old and new SDKs.
- A connection not seen for 60 s no longer counts against the limit.
- A connection lives at most 2 hours; the idle timeout is 10 minutes. Clients rotate at about 115 minutes.

### 3.2 Subscribe

Send the subscribe message as a JSON object without an `action` key. It is v3 only with `"payloadVersion": 3`
(JSON integer).

Enriched: `payloadVersion`, `include` (`content`, `companies`, `events`), `query` (lenient grammar: unknown fields
fall back to full text; a known field with an unknown value, e.g. `sourceType:wire`, is rejected), `sources`, `excludeSources`, `optInSources`, `language` (one language, default `en`),
`tickers`, `countries`, `categories`, `sourceTypes`, `excludeSourceTypes` (same vocabulary and meaning as in 2.2),
`excludeEmptyContent`, `includeUpdates` (without it no `article.updated` is
delivered), `clientNonce`. Unknown keys are dropped silently. `includeContent`, `includeEntities` and `extended` are
forbidden with v3: `connection.error` `VALIDATION_FAILED`, then the connection is closed.

Raw: `payloadVersion`, `query`, `sources`, `excludeSources`, `sourceTypes`, `excludeSourceTypes`, `language`,
`includeUpdates`, `clientNonce`. Any `include` value (unknown ones too) is a `VALIDATION_FAILED` with
`constraints.raw` and no `allowedValues`, and the connection is closed; send no `include` key.

An unknown value of a closed vocabulary (`sourceTypes`, `excludeSourceTypes`, and `include` on the enriched stream),
or a value that is not an array, is a `VALIDATION_FAILED` and the connection is closed; its `details[]` entry carries
`allowedValues` (`ws-sessions/validation-failed-source-type.json`).

Order of handling: unreadable JSON → error in v2 form; ping on the wrong route → `PING_ON_DEFAULT_ROUTE`;
admission (`connection.admitted`); validation (failure closes the connection); enriched only: an initial search
(failure: `SEARCH_FAILED`, then closed). A later subscribe on the same connection replaces the first and runs the
initial push again.

### 3.3 Frames

Article frame: `{"event": "article.created" | "article.updated", "payloadVersion": 3, "data": Article}`.
- No `eventId`, `occurredAt` or `changedFields` on WebSocket. Dedupe on `event` + `data.id` + payload.
- Initial push (enriched): right after a valid subscribe, the single most recent matching article as
  `article.created`. It can be old and can repeat on every reconnect and rotation.
- A live frame larger than 32,000 bytes is dropped without notice (relevant with `include: content`; fetch content
  through REST instead).
- No ordering guarantee; duplicates are possible.

Control frames (`{"event", "payloadVersion": 3, "data"}`):

| event | data | v2 form (see below) |
|---|---|---|
| `connection.admitted` | `{leaseId, serverNow (epoch ms), clientNonce\|null}` | `{"action":"admit", ...}` |
| `connection.pong` | `{t\|null, serverNow}` | `{"action":"pong","t","serverNow"}` |
| `connection.preempted` | `{reason: "connection_limit"\|"quota_exceeded", newLeaseId\|null, timestamp}` | `{"action":"preempted", ...}` |
| `connection.error` | `{code, message, details?}` | `{"action":"error","error"\|"data"}` |

`connection.admitted` is sent on the first subscribe of a connection, and again only when a later subscribe repeats
the same `clientNonce`. It precedes validation, so it does not mean the subscribe was accepted.

`connection.error` codes (open list): `PING_ON_DEFAULT_ROUTE` (log only), `HANDSHAKE_FAILED` (reconnect),
`VALIDATION_FAILED` (terminal), `SEARCH_FAILED` (reconnect), `INTERNAL_ERROR` (log only).

**v2-form frames reach v3 clients.** Before the first v3 subscribe of a connection the server cannot know the
version, so a pong, a preempt and an error for unreadable JSON arrive in the v2 `{"action": ...}` form. A v3 decoder
dispatches on `event` first and falls back to `action`. This is protocol handling, not v2 support.

### 3.4 Liveness and lifecycle (all clients)

- Ping with `{"action":"ping","t":<number>}` every 25 s. Either pong form refreshes a 60 s watchdog; without a pong
  for 60 s the client reconnects and re-sends the same subscribe.
- Terminal (stream ends with a typed error, no reconnect): dial 401; dial 403 "does not include WebSockets";
  `VALIDATION_FAILED`; `connection.preempted` with reason `connection_limit` (as `PreemptedError{reason, newLeaseId}`);
  close code 1008. Dial refusals and `VALIDATION_FAILED` surface as `FinlightApiError` (kind from the status or code).
- Quota exhausted (dial 403 "quota exceeded", `connection.preempted` with reason `quota_exceeded`): by default the
  stream keeps running and redials once per hour until the quota allows it; every wait is logged as a warning and
  passed to a quota hook. Switched off, both are terminal (`FinlightApiError` 403 and `PreemptedError`).
- Reconnect with backoff: dial 403 "Too many concurrent connections"; dial 5xx; `HANDSHAKE_FAILED`; `SEARCH_FAILED`
  (surface as an error after 5 consecutive failures); abnormal close; watchdog; rotation at about 115 minutes.
- Log only: `PING_ON_DEFAULT_ROUTE`, `INTERNAL_ERROR`, unknown codes and unknown events.
- The dedupe cache survives reconnects and rotation. A reconnect hook passes the last seen `availableAt`
  (`firstSeenAt` on raw) for gap-filling through REST; there is no automatic backfill.

## 4. Webhooks v3

### 4.1 Envelope

```json
{
  "eventId": "evt_Q2x9k3LmN8pR4tV7wZ1aBc",
  "event": "article.updated",
  "occurredAt": "2026-11-23T21:04:05.123Z",
  "payloadVersion": 3,
  "subscriptionId": "3b9f0c2e-6d1a-4c7e-9a52-0f1e2d3c4b5a",
  "changedFields": ["title"],
  "data": { }
}
```

| Field | Meaning |
|---|---|
| `eventId` | Idempotency key, opaque. Same on every retry of the same event. Test webhook: starts with `evt_test`. **Dedupe on it.** |
| `event` | `article.created` or `article.updated` (open list). |
| `occurredAt` | When the event happened (not the delivery time); stable across retries. Raw: `firstSeenAt` on `article.created`, the time finlight recorded the update (not `revisedAt`) on `article.updated`. Each update gets its own `eventId`. |
| `payloadVersion` | `3`. |
| `subscriptionId` | The webhook id (UUID). |
| `changedFields` | Only on `article.updated`, only fields this subscription can see (`title`, `summary`, and `content` when requested and entitled). Absent otherwise. |
| `data` | The article object (2.5), cut by the plan at send time. |

An update whose visible changes are empty is not delivered. Without `includeUpdates: true` in the webhook
criteria no update is delivered. Raw webhooks deliver the skeleton only. v3 webhook criteria also take
`sourceTypes` and `excludeSourceTypes` (same vocabulary and meaning as in 2.2, raw included); webhooks are set up in
the dashboard, not by the SDK.

The test webhook (sent from the dashboard) carries a fixed sample with exactly the requested blocks and is not cut
by entitlements.

### 4.2 HTTP request and signature

- `POST <destination>`, body = the compact JSON envelope, `Content-Type: application/json`.
- `X-Webhook-Timestamp`: ISO 8601 UTC with milliseconds, new for every attempt (not unix seconds).
- `X-Webhook-Signature`: `sha256=<lowercase hex>`.
- Optional auth headers configured on the webhook: `Authorization: Basic ...`, `X-Finlight-Key`, `X-Make-ApiKey`.

Verification:
1. Use the raw body bytes exactly as received; never re-serialize parsed JSON.
2. `message = X-Webhook-Timestamp + "." + rawBody`.
3. `expected = hex(HMAC-SHA256(key = the webhook secret as the UTF-8 bytes of its 64-character hex string — NOT
   hex-decoded, data = message))`.
4. Strip `sha256=` and compare in constant time. Any other prefix is a failure.
5. Reject when the timestamp is missing, cannot be parsed, or is further than the tolerance (default 300 s) from
   now in either direction.

Header lookup is case-insensitive.

### 4.3 Delivery

- Success is any 2xx within 5 s. Do slow work after answering.
- On failure: up to 3 retries after +10, +30 and +60 minutes, each re-cut by the plan at that time, with the same
  `eventId` and `occurredAt`.
- A 410 answer disables the webhook at once; 10 failures in a row disable it.

### 4.4 v2 bodies

A webhook is switched between v2 and v3 in the dashboard. Retries queued before a switch are still delivered in the
old format for up to about 2 hours. A v3 client therefore checks `payloadVersion` after verifying the signature: a
body without `payloadVersion: 3` is returned as a **`WrongPayloadVersion` result** (not an error; Go alone reports it
as `*webhook.WrongPayloadVersionError`), carrying the detected version, the raw `payloadVersion`, the parsed JSON and
its `link`, and is never decoded as a half-empty v3 event. Answer it with 2xx so the delivery does not count as a failure.

## 5. Entitlements and the absent / null / [] rules

Plan features that change payloads: full-article access (`content`, `/v3/sources hasContent`), sentiment access
(`sentiment`), entity access (`companies`, `/v3/companies*`), event access (`events`).

1. **Absent** key: not entitled, not requested through `include`, or not available on the channel (raw).
2. **null**: requested and entitled, but no value exists (yet). Text fields (`summary`, `content`) are never `""`:
   no text is `null`.
3. Arrays are never null; `[]` is a real empty set.
4. Every key outside the gated blocks is always present.

| Key | REST / enriched WS / enriched webhook | raw WS / raw webhook |
|---|---|---|
| `content` | present iff `include` has `content` and full-article access | absent |
| `sentiment` | present iff sentiment access | absent |
| `companies` | present iff `include` has `companies` and entity access | absent |
| `events` | present iff `include` has `events` and event access | absent |
| `events[].companyIds` | present iff `companies` is present in the same payload | n/a |
| `availableAt` | always present, nullable | always null |

Clients keep the three states apart (never coerce absent to `false`, `0` or `[]`) and offer the presence helpers
`contentPresent`, `sentimentPresent`, `companiesPresent`, `eventsPresent` (not `hasContent`, which is a search filter
and a `Source` field). Only `id`, `link`, `title` and `source.domain` are required
when decoding; timestamps decode fail-soft.

## 6. Forward compatibility

- Unknown response fields are ignored. Adding fields is part of the contract (planned: `source.name`, `media[].type`,
  `wordCount`, `sentiment.score`, `events[].subtype`, `story`, and others).
- Response enums are open: `event`, `connection.*` names, `connection.error` codes, `sentiment.label`,
  `companies[].role`, `events[].type/direction/importance`, `source.type`, `/v3/sources type`, `categories`,
  preempt reasons, problem codes, the 429 `limitType`. Model them as a string plus known constants and keep unknown values.
- Request vocabularies are validated by the server (400 with `allowedValues`) and can grow without an SDK release;
  clients do not block unknown values. Clients do run cheap structural checks: `limit` 1 to 100, non-empty
  `languages`, `q` xor `ids`, at most 10 ids, no `include` on raw, no unknown request keys.
- Envelopes are objects with named keys; new top-level keys can appear.
- The cursor, `eventId` and the article `id` are opaque.
- `payloadVersion` is always sent as the integer `3`, set by the SDK.
