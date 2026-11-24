# finlight client for Python

*[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | 한국어*

> 이 문서는 [README.md](README.md)의 번역본이며 업데이트가 늦을 수 있습니다. 내용이 다를 경우 영어판이 우선합니다.

> **Breaking release.** 3.0.0은 finlight API v3만 지원합니다. 2.x용으로 작성한 코드는 그대로 동작하지 않습니다.
> 2.x(API v2)를 계속 쓰려면 `finlight-client<3`으로 고정하세요. [2.x에서 마이그레이션](#2x에서-마이그레이션)을 참고하세요.

[finlight](https://finlight.me) 뉴스 API의 Python 클라이언트입니다. REST로 금융 뉴스, 기업, 소스를
검색·조회하고, WebSocket으로 기사를 실시간으로 받고, Webhook을 검증할 수 있습니다.

## 버전

| SDK version | API version | Status |
|---|---|---|
| 3.x | v3 (REST `/v3`, WebSocket `payloadVersion` 3, v3 Webhook) | 현재 버전 |
| 2.x | v2 | 더 이상 릴리스 없음 |

SDK 버전과 API 버전은 서로 독립적입니다. API v3를 지원하는 finlight SDK: TypeScript 4.x, Python 3.x,
PHP 2.x, Go 모듈 `/v2`, .NET 2.x, Java 1.x, Ruby 1.x, Rust 0.2.

## 요구 사항

- Python 3.10 이상
- `requests` 2.31+, `pydantic` 2.7+, `websockets` 15.0+

## 설치

```bash
pip install "finlight-client>=3,<4"
```

## 빠른 시작

```python
from finlight_client import FinlightClient

with FinlightClient(api_key="YOUR_API_KEY") as client:
    page = client.articles.search(query="ticker:NVDA", limit=10)
    for article in page.articles:
        print(article.title)
```

REST 호출은 동기 방식이고, 스트림은 비동기 이터레이터입니다. 인자는 snake_case이며 각각 API의 키
하나에 대응합니다(`from_`은 `from`). 전달한 인자만 전송됩니다.

## 기사 검색

```python
page = client.articles.search(
    query="eventType:mna AND companyCountry:US",
    languages=["en", "de"],
    source_types=["newswire", "financial_media"],
    from_="2026-11-01",               # str, date, or an aware datetime
    event_types=["mna"],
    min_relevance=0.5,
    order_by="availableAt",
    include=["content", "companies", "events"],
    limit=50,
)
print(page.pagination.has_more, page.pagination.next_cursor)
```

`search_all`은 페이지를 자동으로 넘깁니다. 호출 시점에 요청 내용이 고정되고, 이후 페이지에는 cursor만
추가됩니다. 페이지마다 할당량을 쓰므로 `max_pages` 페이지(기본값 10) 후에 멈춥니다.

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

이어서 가져오려면 같은 인자에 `cursor=results.next_cursor`를 더해 `search_all`을 다시 호출하세요.
결과는 한 번만 순회할 수 있습니다. 알 수 없는 인자는 `TypeError`가 되고, 형식 오류(예: `limit=0`,
`languages=[]`)는 전송 전에 `FinlightValidationError`가 됩니다. 어휘 값은 로컬에서 검사하지 않으므로
서버에 새 값이 추가되어도 SDK를 업데이트하지 않고 사용할 수 있습니다.

`source_types`와 `exclude_source_types`는 소스 유형으로 거릅니다(`SourceType.ALL`, 예: `SourceType.NEWSWIRE`).
분류되지 않은 소스의 기사는 `source_types`에 일치하지 않고, `exclude_source_types`에서는 남습니다.
둘 다 이미 받을 수 있는 소스를 좁히기만 합니다. `stream()`과 `raw_stream()`도 이 둘을 받습니다.

## 기사, 기업, 소스 조회

```python
from finlight_client import cache_info

article = client.articles.get("EU8JwpsZ8iJehuyPZjMqRz", include=["content"])
article = client.articles.get_by_link("https://www.reuters.com/...")

companies = client.companies.search("NVDA", mic="XNAS")   # at most 10, no pages
companies = client.companies.get_many([4821, 1001])
company = client.companies.get(4821)                      # revalidated with its ETag next time
print(cache_info(company))

sources = client.sources.list()
```

- 찾지 못하면 `NotFoundError`가 발생하며, 빈 결과를 반환하지 않습니다.
- 기사 id 도입 전에 색인된 기사는 링크로만 가져올 수 있습니다.
- 기업 조회에는 `entityAccess` 권한이 필요합니다(없으면 `ForbiddenError`).
- 조회는 기사와 같은 월간 할당량과 버스트 제한을 사용합니다. `companies.search`, `companies.get_many`,
  `companies.get`, `sources.list`는 호출마다 1 크레딧이 듭니다(`get_many`는 기업별이 아니라 호출당 1).
  304 응답(ETag 재검증)과 오류도 1 크레딧이 듭니다.
- `companies.get`은 최근 레코드를 보관하고 ETag로 다시 검증합니다(`company_cache_size`). 직접
  `if_none_match=...`를 주면 304 응답에서 `None`을 반환합니다. `cache_info(record)`는 `etag`, `cache_control`,
  `not_modified`를 제공합니다.
- `companies.search`, `companies.get_many`, `sources.list`는 `skipped` 속성이 있는 리스트를 반환합니다.
  검색 페이지의 `ArticlePage.skipped`도 같으며, 읽을 수 없는 항목이 여기에 들어갑니다.

## 없음, null, 빈 값

일부 키는 요금제나 `include`에 따라 달라지며 최대 세 가지 상태가 있습니다:

| 상태 | 의미 | 확인 방법 |
|---|---|---|
| 없음 | 요청하지 않음, 권한 없음, 또는 raw 스트림 | `article.content_present`가 `False` |
| `None` | 요청했고 권한도 있지만 값이 없음 | `content_present`가 `True`이고 `content is None` |
| 값 | 값 자체 | `content`에 값이 있음 |

- `content`와 `sentiment`는 세 상태를 모두 가집니다. `content_present`와 `sentiment_present`를 쓰세요.
- `companies`와 `events`는 없으면 `None`, 태깅했지만 결과가 없으면 `[]`입니다. `companies_present`와
  `events_present`를 쓰세요. `[]`가 "권한 없음"을 뜻하는 일은 없습니다.
- `events[].company_ids`는 같은 응답에 `companies`가 있을 때만 `None`이 아닙니다.
- `fullArticleAccess`가 없으면 `Source.has_content`는 `None`입니다. "본문 없음"이 아니라 "알 수 없음"입니다.
- 타임스탬프는 전송된 문자열 그대로 유지됩니다(`published_at`). `published_at_time` 등 `*_time` 속성은
  엄격하게 파싱하며, 읽을 수 없는 값에는 `None`을 반환합니다.
- 새 서버가 보내는 알 수 없는 키는 무시됩니다. `finlight_client.raw_json(article)`로 원본 JSON을 얻고,
  `to_wire(model)`은 없는 키를 뺀 채로 모델을 다시 씁니다.
- 어휘 값은 일반 문자열입니다. `finlight_client`의 상수(`EventType.MNA`, `CompanyRole.ACQUIRER` 등)와
  비교하세요. 알 수 없는 값은 전송된 그대로 유지됩니다.

## 실시간 스트림

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
        on_reconnect=lambda info: print("reconnected", info.reason, info.last_seen_at),
    ) as stream:
        async for event in stream:
            print(event.kind, event.data.title if event.data else event.event)

asyncio.run(main())
```

- `event.kind`는 `created`, `updated` 또는 `other`(이 SDK가 아직 모르는 이벤트)입니다.
- `client.raw_stream(query=..., sources=..., exclude_sources=..., source_types=..., exclude_source_types=...,
  language=..., include_updates=...)`는
  보강 전의 기사를 전달합니다. `include`가 없고 content, sentiment, companies, events도 없습니다.
- 훅은 일반 함수나 `async def` 모두 가능합니다: `on_admitted(AdmittedInfo)`, 첫 연결을 제외한 새 연결마다
  `on_reconnect(ReconnectInfo)`, 스트림을 끝내지 않는 문제에 `on_error(FinlightError)`, 그리고
  `on_quota_wait(QuotaWaitInfo)`. 훅에서 발생한 오류는 기록만 되고 스트림을 멈추지 않습니다.
- 스트림은 25초마다 ping을 보내고, 60초 동안 pong이 없으면 다시 연결하며, 115분 후 새 연결을 엽니다.
  재연결할 때마다 같은 구독을 보내고 중복 전달을 버립니다.
- 자동 백필은 하지 않습니다. `ReconnectInfo.last_seen_at`은 마지막으로 본 `availableAt`(raw는 `firstSeenAt`)
  입니다. 빈 구간은 `articles.search_all(from_=info.last_seen_at, order_by="availableAt")`
  (raw는 `order_by="firstSeenAt"`)로 채우세요.
- 치명적인 문제는 오류로 루프를 끝냅니다: 잘못된 키(`UnauthorizedError`), WebSocket 권한 없음
  (`ForbiddenError`), 구독 거부(`ValidationFailedError`), 다른 연결의 인계에 따른 `PreemptedError`.
  그 밖의 문제는 다시 연결하고 `on_error`로 알립니다.
- 월간 WebSocket 할당량을 다 쓰면(연결 거부, 또는 이유가 `quota_exceeded`인 선점) 스트림은 끝나지 않고,
  할당량이 회복될 때까지 1시간마다 다시 시도합니다. 기다릴 때마다 경고를 기록하고 `on_quota_wait`를
  호출합니다. `quota_reconnect=False`로 설정하면 오류로 끝납니다. 간격은 `quota_reconnect_interval`로
  바꿀 수 있습니다.
- `async with` 블록을 벗어나면 연결이 닫힙니다. 취소는 절대 무시되지 않습니다.

알아 둘 제한:

- 요금제의 연결 수 한도는 enriched, raw, 이전 SDK 연결이 함께 사용합니다. 한도에 도달한 상태의 새 연결은
  거부되며, SDK는 60초 후 다시 시도합니다. `stream()` 또는 `raw_stream()`에 `takeover=True`를 주면 대신
  가장 오래된 연결을 교체합니다.
- 구독 직후 서버는 조건에 맞는 최신 기사 1건을 보냅니다(재연결할 때마다 다시). 오래된 기사일 수 있습니다.
- 32,000바이트를 넘는 라이브 프레임은 서버가 알림 없이 버립니다. 긴 기사에 `include=["content"]`를
  쓰면 생길 수 있습니다. `articles.get`으로 가져오세요.
- `connection.admitted`는 서버가 구독을 검사하기 전에 도착합니다. 구독이 수락되었다는 뜻이 아닙니다.
- WebSocket 연결은 `websockets` 라이브러리처럼 환경 변수의 프록시 설정(`HTTPS_PROXY`, `ALL_PROXY`)을
  사용합니다. 끄려면 `websocket_options={"proxy": None}`을 전달하세요.

## Webhook

finlight는 모든 Webhook에 서명합니다. 무엇이든 파싱하기 전에 **원본** 요청 본문으로 검증하세요:

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

- `headers`에는 어떤 헤더 매핑이나 쌍의 목록도 쓸 수 있습니다(Flask, Django, Starlette, `http.server`,
  WSGI environ). 이름은 대소문자를 구분하지 않습니다. `construct_event_from_values(raw_body, signature,
  timestamp, secret)`는 두 헤더 값을 직접 받고, `verify_signature`는 검증만 합니다.
- 타임스탬프는 앞뒤 어느 방향으로든 `DEFAULT_WEBHOOK_TOLERANCE`(300초) 이내여야 합니다.
- `WebhookVerificationError.reason`이 이유를 알려 줍니다(예: `signature_mismatch`, `timestamp_outside_tolerance`).
  원본 대신 파싱된 본문을 넘기면 `invalid_raw_body`로 실패합니다.
- 대시보드 테스트 Webhook에서는 `result.is_test`가 true입니다. 요금제에 따른 제한이 적용되지 않습니다.
- 410으로 응답하지 마세요. Webhook이 즉시 비활성화됩니다. 2xx가 아닌 응답이 10번 연속되어도 비활성화됩니다.

원본 본문 얻기:

| 프레임워크 | 원본 본문 |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

## 오류와 재시도

모든 오류는 `FinlightError`를 상속하며 `kind`(`api`, `validation`, `network`, `timeout`, `decode`,
`webhook_verification`, `preempted`)를 가집니다.

| 오류 | 발생 조건 |
|---|---|
| `FinlightApiError` | API가 오류를 반환함: REST, 거부된 스트림 연결, 스트림 오류. `status`, `code`, `type`, `title`, `detail`, `request_id`, `errors`(`FieldIssue`), `api_kind`, `raw`를 가짐. 하위 클래스: `ValidationFailedError`, `CursorInvalidError`, `CursorMismatchError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `RateLimitedError`, `InternalServerError`. 그 밖에는 `api_kind`가 `other`. |
| `RateLimitedError` | `limit_type`은 `monthly`, `burst`, `unknown` 또는 더 새로운 값. `retry_after`는 초 단위. |
| `FinlightValidationError` | 요청이 로컬에서 거부됨(`ValueError`이기도 함). `param`이 키를 알려 줌. |
| `FinlightNetworkError`, `FinlightTimeoutError` | 네트워크 장애 또는 시간 초과. 원래 오류는 `__cause__`. |
| `FinlightDecodeError` | 응답을 읽을 수 없음(`path`, `raw`). |
| `WebhookVerificationError` | Webhook 검증 실패(`reason`). |
| `PreemptedError` | 다른 연결이 스트림을 인계함(`reason`, `new_lease_id`). `quota_reconnect=False`이면 할당량 소진 시에도 발생. |

재시도: 5xx 응답, 네트워크 오류, 시간 초과는 대기 시간을 늘려 가며 최대 3번 재시도합니다(검색 포함).
400, 401, 403, 404와 월간 할당량 429는 재시도하지 않습니다. 월간 할당량 429는 `search_all` 안에서도 즉시
오류가 되며, 할당량을 기다리는 것은 스트림뿐입니다(위 참고). 버스트 429는 정확히 `Retry-After`초(헤더가 없으면
10초)를 기다린 뒤 한 번만 다시 시도합니다. 기본으로 켜져 있고 `max_retries`에 포함되지 않으며,
`retry_on_burst="off"`로 끌 수 있습니다. 호출마다 고유한 `X-Request-Id`를 보내며 재시도에도 같은 값을 씁니다.
Ctrl+C로 REST 호출을 재시도 없이 즉시 멈출 수 있고, 태스크를 취소하면 스트림이 멈춥니다.

## 설정

```python
client = FinlightClient(
    api_key="YOUR_API_KEY",
    base_url="https://api.finlight.me",   # a trailing slash is fine
    wss_url="wss://wss.finlight.me",      # raw streams use <wss_url>/raw
    timeout=30.0,                         # seconds per attempt
)
```

모든 키는 키워드 인자나 `FinlightConfig`(`config=`)로 설정할 수 있습니다. 시간은 초 단위입니다.

| 키 | 기본값 | 의미 |
|---|---|---|
| `api_key` | 필수 | API 키, 비어 있으면 안 됨 |
| `base_url` | `https://api.finlight.me` | REST 기본 URL |
| `wss_url` | `wss://wss.finlight.me` | WebSocket URL, raw는 `/raw` |
| `timeout` | 30 | REST 시도마다 |
| `total_timeout` | 없음 | 호출당 상한(재시도와 버스트 대기 포함) |
| `max_retries` | 3 | 5xx, 네트워크 오류, 시간 초과의 재시도 횟수 |
| `retry_base_delay`, `retry_max_delay` | 0.5, 8 | 재시도 사이의 늘어나는 대기 |
| `retry_on_burst` | `"once"` | `"off"`는 버스트 재시도를 끔 |
| `burst_wait` | 10 | `Retry-After`가 없을 때의 버스트 대기 |
| `max_pages` | 10 | `search_all`의 페이지 상한 |
| `max_response_bytes` | 32 MiB | REST 응답의 크기 상한 |
| `company_cache_size` | 256 | `companies.get`이 보관하는 레코드 수, 0이면 끔 |
| `ping_interval` | 25 | 스트림 ping |
| `watchdog_timeout` | 60 | 이 시간 동안 pong이 없으면 재연결 |
| `rotation_interval` | 6900(115분) | 2시간 한도 전에 새 연결 |
| `reconnect_base_delay`, `reconnect_max_delay` | 1, 30 | 재연결 사이의 늘어나는 대기 |
| `long_backoff` | 60 | 연결 수 한도나 429로 거부된 뒤의 대기 |
| `quota_reconnect` | `True` | 끝내지 않고 월간 WebSocket 할당량을 기다림 |
| `quota_reconnect_interval` | 3600 | 할당량 재시도 사이의 대기 |
| `search_failed_threshold` | 5 | `on_error` 전까지 연속 `SEARCH_FAILED` 횟수 |
| `dedupe_cache_size` | 1000 | 스트림마다 기억하는 전달 수 |
| `max_message_bytes` | 32 MiB | 스트림 메시지의 크기 상한 |
| `connect_timeout` | 30 | WebSocket 핸드셰이크 |
| `session` | 없음 | 직접 만든 `requests.Session` |
| `websocket_options`, `websocket_connect` | 없음 | `websockets.connect` 옵션, 또는 직접 만든 WebSocket 전송 |
| `clock` | 시스템 시계 | 스트림 타이머의 시간 소스(테스트용) |

직접 만든 `requests.Session`을 쓰면 그 시간 제한, 프록시, 어댑터가 적용됩니다. 시도마다 할당량을 쓰므로
재시도 어댑터는 추가하지 마세요. SDK는 직접 만들지 않은 session을 닫지 않습니다.

## 로깅

SDK는 표준 `logging` 모듈로 `finlight_client`라는 이름으로 로그를 남깁니다. 설정하지 않으면 아무것도 출력하지
않습니다. 경고는 건너뛴 항목, 재연결, 할당량 대기를 다룹니다. API 키, Webhook 시크릿, 서명, 전체 본문은 로그나
오류 메시지에 나타나지 않으며, 헤더를 보여 주는 `websockets` 라이브러리의 디버그 출력도 막습니다. SDK는 전역
로깅 설정을 바꾸지 않고 시그널 핸들러도 설치하지 않습니다.

```python
import logging

logging.getLogger("finlight_client").setLevel(logging.INFO)
```

## 데이터 참고 사항

- 오래된 기사는 `published_at`이 `"1970-01-01T00:00:00.000Z"`일 수 있습니다. 전송된 그대로 제공됩니다.
- 빈 텍스트는 `None`으로 옵니다(`summary`, `content`).
- 역할 기능 이전에 태깅된 기사는 `role`과 `relevance`가 `None`, `events`가 `[]`입니다.
- id 도입 전에 색인된 기사는 `articles.get(id)`가 404를 반환합니다. `get_by_link`를 사용하세요.
- 오래된 기사의 `available_at`은 `None`이며, raw 스트림에서는 항상 `None`입니다.
- `source.type`과 `Source.type`은 소스가 분류되지 않았으면 `None`입니다. 소스 유형이 생기기 전에 색인된
  기사도 `None`입니다. 소스가 다시 분류되어도 오래된 기사는 이전 유형을 유지합니다.

## 2.x에서 마이그레이션

전체 가이드는 [docs.finlight.me](https://docs.finlight.me/migration/v2-to-v3)에 있습니다. 요약:

| 2.x | 3.x |
|---|---|
| `FinlightApi(ApiConfig(api_key=...))` | `FinlightClient(api_key=...)` |
| `articles.fetch_articles(GetArticlesParams(...))` | `articles.search(...)`, `articles.search_all(...)` |
| `page` / `pageSize` | `limit` / `cursor` |
| `includeContent`, `includeEntities` | `include=["content", "companies", "events"]` |
| `order="DESC"` | `order="desc"` |
| `publishDate`, `createdAt`, `revisedDate` | `published_at`, `first_seen_at`, `revised_at` |
| `images` | `media[].url` |
| `source`(문자열) | `source.domain` |
| `sentiment`, `confidence` | `sentiment.label`, `sentiment.confidence` |
| `api.websocket.connect(...)` | `async for event in client.stream(...)` |
| `api.raw_websocket` | `client.raw_stream(...)` |
| Webhook `isUpdate` | `event.event == "article.updated"` |
| Webhook 본문 | `event.data`, 그리고 중복 제거용 `event.event_id` |

Webhook을 v3로 전환하는 네 단계:

1. 이 SDK를 배포합니다.
2. `WrongPayloadVersion`에는 2xx로 응답하고 `raw` JSON을 보관합니다.
3. 대시보드에서 Webhook을 `payloadVersion` 3으로 전환합니다.
4. 약 2시간 기다립니다. 전환 전에 대기열에 들어간 재시도는 이전 형식으로 계속 도착합니다.

같은 키로 2.x와 3.x 스트림을 동시에 실행하지 마세요. 연결 수 한도를 함께 씁니다.

## 개발

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`conformance/`는 계약 키트의 사본이며 `CONTRACT_VERSION`과 sha256 `MANIFEST`를 포함합니다. `CONFORMANCE.md`는
각 케이스와 해당 테스트를 연결한 목록입니다. 라이브 테스트는 dev 환경에서만 실행하며 `FINLIGHT_API_KEY`,
`FINLIGHT_BASE_URL`, `FINLIGHT_WSS_URL`이 필요합니다: `pytest tests/live -m live --force-enable-socket`.

## 라이선스

MIT
