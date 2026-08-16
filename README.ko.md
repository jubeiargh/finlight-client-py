# Finlight Client – Python 라이브러리

*[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | 한국어*

[Finlight News API](https://finlight.me)를 사용하기 위한 Python 클라이언트 라이브러리입니다.
Finlight는 감성 분석, 기업 태깅, 시장 메타데이터가 부가된 실시간 및 과거 금융 뉴스 기사를 제공합니다. 이 라이브러리를 사용하면 Python 애플리케이션에 Finlight를 손쉽게 통합할 수 있습니다.

---

## ✨ 주요 기능

- 날짜 파싱과 메타데이터를 포함한 **구조화된** 뉴스 기사 조회.
- **티커**, **뉴스 소스**, **언어**, **기간**으로 필터링.
- **Enhanced** 및 **Raw WebSocket**을 통한 **실시간** 뉴스 수신, 자동 재연결 지원.
- **Webhook 지원**: HMAC 서명 검증 및 재생 공격 방지 포함.
- 고급 WebSocket 기능:
  - 지수 백오프 재연결 전략
  - Ping/Pong 킵얼라이브 메커니즘
  - 선제적 연결 교체(AWS 2시간 제한 이전에 수행)
  - 기존 연결을 대체하는 테이크오버
  - 속도 제한 및 관리자 강제 종료 처리
- `pydantic`과 `dataclass` 기반의 엄격한 타입 모델.
- 가볍고 개발자 친화적인 설계.

---

## 📦 설치

```bash
pip install finlight-client
```

---

## 🚀 빠른 시작

### REST API로 기사 조회하기

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesParams

def main():
    # 클라이언트 초기화
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # 쿼리 파라미터 생성
    params = GetArticlesParams(
        query="Nvidia",
        language="en",
        from_="2024-01-01",
        to="2024-12-31",
        includeContent=True
    )

    # 기사 조회
    response = client.articles.fetch_articles(params=params)

    # 결과 출력
    for article in response.articles:
        print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

### 링크로 기사 조회하기

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticleByLinkParams

def main():
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    params = GetArticleByLinkParams(
        link="https://www.reuters.com/technology/example-article",
        includeContent=True,
        includeEntities=True
    )

    article = client.articles.fetch_article_by_link(params=params)
    print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

---

### WebSocket으로 실시간 기사 수신하기

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print("📨 수신:", article.title)

async def main():
    # 클라이언트 초기화
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # WebSocket 파라미터 생성
    payload = GetArticlesWebSocketParams(
        query="Nvidia",
        sources=["www.reuters.com"],
        language="en",
        extended=True,
    )

    # 연결 후 기사 수신
    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Raw WebSocket으로 원본 기사 수신하기

Raw WebSocket은 AI 보강 처리(감성, 신뢰도, 기업 태깅)를 건너뛰기 때문에 더 빠르게 기사를 전달합니다. `source:`, `title:`, `summary:` 필드 단위 필터링을 지원합니다.

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig, RawWebSocketOptions
from finlight_client.models import GetRawArticlesWebSocketParams

def on_article(article):
    print("📨 수신:", article.title)

async def main():
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(
        config,
        raw_websocket_options=RawWebSocketOptions(
            takeover=True
        )
    )

    payload = GetRawArticlesWebSocketParams(
        query="title:Nvidia",
        sources=["www.reuters.com"],
        language="en",
    )

    await client.raw_websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ 설정

### `ApiConfig`

핵심 API 설정:

| 파라미터      | 타입         | 설명                       | 기본값                    |
| ------------- | ------------ | -------------------------- | ------------------------- |
| `api_key`     | `str`        | 사용자의 API 키            | **필수**                  |
| `base_url`    | `AnyHttpUrl` | REST API 기본 URL          | `https://api.finlight.me` |
| `wss_url`     | `AnyHttpUrl` | WebSocket 서버 URL         | `wss://wss.finlight.me`   |
| `timeout`     | `int`        | 요청 타임아웃(ms)          | `5000`                    |
| `retry_count` | `int`        | 실패 시 재시도 횟수        | `3`                       |

### `FinlightApi` WebSocket 옵션

고급 WebSocket 설정(모두 선택 사항)입니다. 플랫 키워드 인자 또는 옵션 객체 중 하나를 사용할 수 있습니다:

```python
# 플랫 키워드 인자 사용(Enhanced WebSocket 전용)
client = FinlightApi(config, websocket_takeover=True)

# 옵션 객체 사용(Enhanced 및 Raw WebSocket 모두)
from finlight_client import WebSocketOptions, RawWebSocketOptions

client = FinlightApi(
    config,
    websocket_options=WebSocketOptions(takeover=True),
    raw_websocket_options=RawWebSocketOptions(takeover=True),
)
```

`WebSocketOptions`와 `RawWebSocketOptions`는 동일한 필드를 받습니다:

| 필드                     | 타입       | 설명                                         | 기본값        |
| ------------------------ | ---------- | -------------------------------------------- | ------------- |
| `ping_interval`          | `int`      | Ping 간격(초)                                | `25`          |
| `pong_timeout`           | `int`      | Pong 타임아웃(초)                            | `60`          |
| `base_reconnect_delay`   | `float`    | 최초 재연결 지연(초)                         | `0.5`         |
| `max_reconnect_delay`    | `float`    | 최대 재연결 지연(초)                         | `10.0`        |
| `connection_lifetime`    | `int`      | 연결 수명(초)                                | `6900`(115분) |
| `takeover`               | `bool`     | 기존 연결을 테이크오버                       | `False`       |
| `on_close`               | `Callable` | 종료 이벤트 콜백 `(code, reason)`            | `None`        |

---

## 📚 API 개요

### `ArticleService.fetch_articles(params: GetArticlesParams) -> ArticleResponse`

유연한 필터링으로 기사를 조회합니다:
- 불리언 연산자를 포함한 고급 쿼리 문자열 지원
- ISO 형식 날짜 문자열을 `datetime`으로 자동 변환
- 페이지 크기를 지정할 수 있는 페이지네이션(1~1000)
- 전문 및 엔티티 태깅은 선택 사항

### `ArticleService.fetch_article_by_link(params: GetArticleByLinkParams) -> Article`

URL로 단일 기사를 조회합니다:

- 데이터베이스에 존재하면 해당 기사를 반환합니다
- 전문 및 엔티티 태깅은 선택 사항
- URL을 지정해 특정 기사를 가져올 때 유용합니다

### `SourcesService.get_sources() -> List[Source]`

사용 가능한 뉴스 소스를 조회합니다:
- 메타데이터가 포함된 소스 목록을 반환합니다
- 전문 제공 여부와 기본 소스 여부를 표시합니다
- 소스 필터를 구성할 때 유용합니다

### `WebSocketClient.connect(request_payload, on_article)`

기사 실시간 업데이트를 구독합니다:
- 지수 백오프로 자동 재연결합니다
- 속도 제한과 관리자 조치를 적절히 처리합니다
- 연결 유지를 위해 25초마다 서버로 Ping을 보냅니다
- AWS 2시간 타임아웃 이전에 선제적으로 연결을 교체합니다
- 테이크오버 모드는 선택 사항

### `RawWebSocketClient.connect(request_payload, on_article)`

원본 기사 실시간 업데이트를 구독합니다(더 빠른 전달, AI 보강 없음):
- 재연결 및 킵얼라이브 동작은 Enhanced WebSocket과 동일합니다
- `wss://wss.finlight.me/raw`에 연결합니다
- `RawArticle` 객체를 반환합니다(감성, 신뢰도, 기업 정보 없음)
- 필드 단위 쿼리 필터 지원: `source:`, `title:`, `summary:`

### `WebhookService.construct_event(raw_body, signature, endpoint_secret, timestamp?)`

Webhook 이벤트를 안전하게 수신합니다:
- HMAC-SHA256 서명 검증
- 재생 공격 방지(허용 오차 5분)
- 검증된 `Article` 객체를 반환합니다
- 요청이 유효하지 않으면 `WebhookVerificationError`를 발생시킵니다

---

## 🧯 오류 처리

- 잘못된 날짜 문자열은 내용이 명확한 Python `ValueError`를 발생시킵니다.
- REST 및 WebSocket 예외는 로그로 기록되고 처리됩니다.
- WebSocket에는 재연결, 워치독, Ping/Pong 메커니즘이 내장되어 있습니다.

---

## 📖 추가 예제

### 사용 가능한 뉴스 소스 조회

```python
from finlight_client import FinlightApi, ApiConfig

def main():
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    sources = client.sources.get_sources()

    for source in sources:
        print(f"{source.domain} - Content: {source.isContentAvailable}")

if __name__ == "__main__":
    main()
```

### Webhook 이벤트 수신(Flask)

```python
from flask import Flask, request
from finlight_client import WebhookService, WebhookVerificationError
import os

app = Flask(__name__)
webhook_service = WebhookService()

@app.route('/webhook', methods=['POST'])
def webhook():
    raw_body = request.get_data(as_text=True)
    signature = request.headers.get('X-Webhook-Signature')
    timestamp = request.headers.get('X-Webhook-Timestamp')

    try:
        article = webhook_service.construct_event(
            raw_body,
            signature,
            os.getenv('WEBHOOK_SECRET'),
            timestamp
        )
        print(f"📨 새 기사: {article.title}")
        return '', 200
    except WebhookVerificationError as e:
        print(f"❌ Webhook 검증 실패: {e}")
        return '', 400

if __name__ == "__main__":
    app.run(port=3000)
```

### 사용자 지정 설정을 적용한 고급 WebSocket 사용

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print(f"📨 {article.title}")

def on_close(code, reason):
    print(f"🔌 연결이 종료되었습니다: {code} - {reason}")

async def main():
    config = ApiConfig(api_key="your_api_key")

    # 고급 WebSocket 설정
    client = FinlightApi(
        config,
        websocket_ping_interval=30,  # Ping 간격 사용자 지정
        websocket_pong_timeout=90,   # Pong 타임아웃 사용자 지정
        websocket_takeover=True,     # 기존 연결 대체
        websocket_on_close=on_close  # 종료 이벤트 콜백
    )

    payload = GetArticlesWebSocketParams(
        tickers=["NVDA", "AAPL"],
        language="en",
        extended=True,
        includeEntities=True
    )

    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧰 모델 요약

### `GetArticlesParams`(REST API)

기사를 필터링하는 쿼리 파라미터:

| 필드                   | 타입           | 설명                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 불리언 연산자를 사용할 수 있는 검색어              |
| `tickers`              | `List[str]`    | 티커로 필터링(예: `["AAPL", "NVDA"]`)              |
| `sources`              | `List[str]`    | 특정 뉴스 소스 포함                                |
| `excludeSources`       | `List[str]`    | 특정 뉴스 소스 제외                                |
| `optInSources`         | `List[str]`    | 기본이 아닌 소스 추가                              |
| `language`             | `str`          | 언어 필터(예: `"en"`, `"de"`)                      |
| `countries`            | `List[str]`    | 국가 코드로 필터링(예: `["US", "GB"]`)             |
| `from_`                | `str`          | 시작일(`YYYY-MM-DD` 또는 ISO 형식)                 |
| `to`                   | `str`          | 종료일(`YYYY-MM-DD` 또는 ISO 형식)                 |
| `includeContent`       | `bool`         | 기사 전문 포함(기본값: `False`)                    |
| `includeEntities`      | `bool`         | 태깅된 기업 포함(기본값: `False`)                  |
| `excludeEmptyContent`  | `bool`         | 전문이 있는 기사만(기본값: `False`)                |
| `orderBy`              | `str`          | 정렬 기준: `"publishDate"`, `"createdAt"`, `"revisedDate"` |
| `order`                | `str`          | 정렬 방향: `"ASC"` 또는 `"DESC"`                   |
| `page`                 | `int`          | 페이지 번호(1부터 시작)                            |
| `pageSize`             | `int`          | 페이지당 결과 수(1~1000)                           |

### `GetArticleByLinkParams`(REST API)

URL로 단일 기사를 조회하기 위한 파라미터:

| 필드                   | 타입           | 설명                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `link`                 | `str`          | 조회할 기사의 URL(필수)                            |
| `includeContent`       | `bool`         | 기사 전문 포함(기본값: `None`)                     |
| `includeEntities`      | `bool`         | 태깅된 기업 포함(기본값: `None`)                   |

### `GetArticlesWebSocketParams`(WebSocket)

WebSocket 구독 파라미터:

| 필드                   | 타입           | 설명                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 검색어                                             |
| `tickers`              | `List[str]`    | 티커로 필터링                                      |
| `sources`              | `List[str]`    | 특정 뉴스 소스 포함                                |
| `excludeSources`       | `List[str]`    | 특정 뉴스 소스 제외                                |
| `optInSources`         | `List[str]`    | 기본이 아닌 소스 추가                              |
| `language`             | `str`          | 언어 필터                                          |
| `countries`            | `List[str]`    | 국가 코드로 필터링(예: `["US", "GB"]`)             |
| `extended`             | `bool`         | 기사 상세 전체 포함(기본값: `False`)               |
| `includeEntities`      | `bool`         | 태깅된 기업 포함(기본값: `False`)                  |
| `excludeEmptyContent`  | `bool`         | 전문이 있는 기사만(기본값: `False`)                |

### `GetRawArticlesWebSocketParams`(Raw WebSocket)

Raw WebSocket 구독 파라미터:

| 필드                   | 타입           | 설명                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 필드 필터를 포함한 검색어(`source:`, `title:`, `summary:`) |
| `sources`              | `List[str]`    | 특정 뉴스 소스 포함                                |
| `excludeSources`       | `List[str]`    | 특정 뉴스 소스 제외                                |
| `optInSources`         | `List[str]`    | 기본이 아닌 소스 추가                              |
| `language`             | `str`          | 언어 필터                                          |

### `Article`

기사 객체 필드(Enhanced WebSocket / REST API):

| 필드           | 타입              | 설명                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 기사 제목                                   |
| `link`         | `str`             | 기사 URL                                    |
| `publishDate`  | `datetime`        | 발행 일시                                   |
| `source`       | `str`             | 소스 도메인                                 |
| `language`     | `str`             | 기사 언어 코드                              |
| `summary`      | `str`             | 기사 요약                                   |
| `content`      | `str`             | 기사 전문(제공되는 경우)                    |
| `sentiment`    | `str`             | 감성 분석 결과                              |
| `confidence`   | `float`           | 감성 분석 신뢰도 점수                       |
| `images`       | `List[str]`       | 이미지 URL 목록                             |
| `companies`    | `List[Company]`   | 태깅된 기업 및 메타데이터                   |

### `RawArticle`

원본 기사 객체 필드(Raw WebSocket):

| 필드           | 타입              | 설명                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 기사 제목                                   |
| `link`         | `str`             | 기사 URL                                    |
| `publishDate`  | `datetime`        | 발행 일시                                   |
| `source`       | `str`             | 소스 도메인                                 |
| `language`     | `str`             | 기사 언어 코드                              |
| `summary`      | `str`             | 기사 요약                                   |
| `images`       | `List[str]`       | 이미지 URL 목록                             |

### `Company`

태깅된 기업 정보:

| 필드              | 타입              | 설명                                     |
| ----------------- | ----------------- | ---------------------------------------- |
| `companyId`       | `int`             | 기업 고유 식별자                         |
| `name`            | `str`             | 기업명                                   |
| `ticker`          | `str`             | 주요 티커 심볼                           |
| `confidence`      | `float`           | 태깅 신뢰도 점수                         |
| `country`         | `str`             | 기업 소재 국가                           |
| `exchange`        | `str`             | 주요 거래소                              |
| `sector`          | `str`             | 섹터                                     |
| `industry`        | `str`             | 산업 분류                                |
| `isin`            | `str`             | ISIN 코드                                |
| `openfigi`        | `str`             | OpenFIGI 식별자                          |
| `primaryListing`  | `Listing`         | 주요 거래소 상장 정보                    |
| `isins`           | `List[str]`       | 전체 ISIN 코드                           |
| `otherListings`   | `List[Listing]`   | 기타 거래소 상장 정보                    |

### `Source`

뉴스 소스 메타데이터:

| 필드                 | 타입    | 설명                                            |
| -------------------- | ------- | ----------------------------------------------- |
| `domain`             | `str`   | 소스 도메인(예: `"www.reuters.com"`)            |
| `isContentAvailable` | `bool`  | 전문 제공 여부                                  |
| `isDefaultSource`    | `bool`  | 기본으로 포함되는 소스인지 여부                 |

---

## 🤝 기여

기여와 제안을 환영합니다.

- 이 저장소를 포크하세요
- 기능 브랜치를 생성하세요
- 필요한 경우 테스트를 포함해 풀 리퀘스트를 보내주세요

---

## 📄 라이선스

MIT License – [LICENSE](LICENSE) 참조

---

## 🔗 관련 링크

- [Finlight API 문서](https://docs.finlight.me)
- [GitHub 저장소](https://github.com/jubeiargh/finlight-client-py)
- [PyPI 패키지](https://pypi.org/project/finlight-client)
- [한국어 제품 페이지](https://finlight.me/ko/news-api)
