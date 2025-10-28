# Finlight Client – Python Library

A Python client library for interacting with the [Finlight News API](https://finlight.me).
Finlight delivers real-time and historical financial news articles, enriched with sentiment analysis, company tagging, and market metadata. This library makes it easy to integrate Finlight into your Python applications.

---

## ✨ Features

- Fetch **structured** news articles with date parsing and metadata.
- Filter by **tickers**, **sources**, **languages**, and **date ranges**.
- Stream **real-time** news updates via **WebSocket** with auto-reconnect.
- **Webhook support** with HMAC signature verification and replay attack protection.
- Advanced WebSocket features:
  - Exponential backoff reconnection strategy
  - Ping/pong keepalive mechanism
  - Proactive connection rotation (before AWS 2-hour limit)
  - Connection takeover for replacing existing connections
  - Rate limit and admin kick handling
- Strongly typed models using `pydantic` and `dataclass`.
- Lightweight and developer-friendly.

---

## 📦 Installation

```bash
pip install finlight-client
```

---

## 🚀 Quick Start

### Fetch Articles via REST API

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesParams

def main():
    # Initialize the client
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # Create query parameters
    params = GetArticlesParams(
        query="Nvidia",
        language="en",
        from_="2024-01-01",
        to="2024-12-31",
        includeContent=True
    )

    # Fetch articles
    response = client.articles.fetch_articles(params=params)

    # Print results
    for article in response.articles:
        print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

---

### Stream Real-Time Articles via WebSocket

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print("📨 Received:", article.title)

async def main():
    # Initialize the client
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # Create WebSocket parameters
    payload = GetArticlesWebSocketParams(
        query="Nvidia",
        sources=["www.reuters.com"],
        language="en",
        extended=True,
    )

    # Connect and listen for articles
    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

### `ApiConfig`

Core API configuration:

| Parameter     | Type         | Description                | Default                   |
| ------------- | ------------ | -------------------------- | ------------------------- |
| `api_key`     | `str`        | Your API key               | **Required**              |
| `base_url`    | `AnyHttpUrl` | Base REST API URL          | `https://api.finlight.me` |
| `wss_url`     | `AnyHttpUrl` | WebSocket server URL       | `wss://wss.finlight.me`   |
| `timeout`     | `int`        | Request timeout in ms      | `5000`                    |
| `retry_count` | `int`        | Retry attempts on failures | `3`                       |

### `FinlightApi` WebSocket Options

Advanced WebSocket configuration (all optional):

| Parameter                        | Type       | Description                                  | Default      |
| -------------------------------- | ---------- | -------------------------------------------- | ------------ |
| `websocket_ping_interval`        | `int`      | Ping interval in seconds                     | `25`         |
| `websocket_pong_timeout`         | `int`      | Pong timeout in seconds                      | `60`         |
| `websocket_base_reconnect_delay` | `float`    | Initial reconnect delay in seconds           | `0.5`        |
| `websocket_max_reconnect_delay`  | `float`    | Maximum reconnect delay in seconds           | `10.0`       |
| `websocket_connection_lifetime`  | `int`      | Connection lifetime in seconds               | `6900` (115m)|
| `websocket_takeover`             | `bool`     | Takeover existing connections                | `False`      |
| `websocket_on_close`             | `Callable` | Callback for close events `(code, reason)`   | `None`       |

---

## 📚 API Overview

### `ArticleService.fetch_articles(params: GetArticlesParams) -> ArticleResponse`

Fetch articles with flexible filtering:
- Supports advanced query strings with boolean operators
- Automatically parses ISO date strings into `datetime`
- Pagination with configurable page size (1-1000)
- Optional full content and entity tagging

### `SourcesService.get_sources() -> List[Source]`

Retrieve available news sources:
- Returns list of sources with metadata
- Indicates content availability and default sources
- Useful for building source filters

### `WebSocketClient.connect(request_payload, on_article)`

Subscribe to live article updates:
- Reconnects automatically with exponential backoff
- Handles rate limiting and admin actions gracefully
- Pings the server every 25s to keep the connection alive
- Proactively rotates connections before AWS 2-hour timeout
- Optional connection takeover mode

### `WebhookService.construct_event(raw_body, signature, endpoint_secret, timestamp?)`

Securely receive webhook events:
- HMAC-SHA256 signature verification
- Replay attack protection (5-minute tolerance)
- Returns validated `Article` objects
- Raises `WebhookVerificationError` on invalid requests

---

## 🧯 Error Handling

- Invalid date strings raise clear Python `ValueError`s.
- REST and WebSocket exceptions are logged and managed.
- WebSocket includes reconnect, watchdog, and ping/pong mechanisms.

---

## 📖 Additional Examples

### Fetch Available Sources

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

### Receive Webhook Events (Flask)

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
        print(f"📨 New article: {article.title}")
        return '', 200
    except WebhookVerificationError as e:
        print(f"❌ Invalid webhook: {e}")
        return '', 400

if __name__ == "__main__":
    app.run(port=3000)
```

### Advanced WebSocket with Custom Configuration

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print(f"📨 {article.title}")

def on_close(code, reason):
    print(f"🔌 Connection closed: {code} - {reason}")

async def main():
    config = ApiConfig(api_key="your_api_key")

    # Advanced WebSocket configuration
    client = FinlightApi(
        config,
        websocket_ping_interval=30,  # Custom ping interval
        websocket_pong_timeout=90,   # Custom pong timeout
        websocket_takeover=True,     # Replace existing connections
        websocket_on_close=on_close  # Close event callback
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

## 🧰 Model Summary

### `GetArticlesParams` (REST API)

Query parameters to filter articles:

| Field                  | Type           | Description                                        |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | Search text with boolean operators                 |
| `tickers`              | `List[str]`    | Filter by ticker symbols (e.g., `["AAPL", "NVDA"]`)|
| `sources`              | `List[str]`    | Include specific sources                           |
| `excludeSources`       | `List[str]`    | Exclude specific sources                           |
| `optInSources`         | `List[str]`    | Include non-default sources                        |
| `language`             | `str`          | Language filter (e.g., `"en"`, `"de"`)             |
| `countries`            | `List[str]`    | Filter by country codes (e.g., `["US", "GB"]`)     |
| `from_`                | `str`          | Start date (`YYYY-MM-DD` or ISO)                   |
| `to`                   | `str`          | End date (`YYYY-MM-DD` or ISO)                     |
| `includeContent`       | `bool`         | Include full article content (default: `False`)    |
| `includeEntities`      | `bool`         | Include tagged companies (default: `False`)        |
| `excludeEmptyContent`  | `bool`         | Only articles with content (default: `False`)      |
| `orderBy`              | `str`          | Order by `"publishDate"` or `"createdAt"`          |
| `order`                | `str`          | Sort order: `"ASC"` or `"DESC"`                    |
| `page`                 | `int`          | Page number (starts at 1)                          |
| `pageSize`             | `int`          | Results per page (1-1000)                          |

### `GetArticlesWebSocketParams` (WebSocket)

Parameters for WebSocket subscriptions:

| Field                  | Type           | Description                                        |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | Search text                                        |
| `tickers`              | `List[str]`    | Filter by ticker symbols                           |
| `sources`              | `List[str]`    | Include specific sources                           |
| `excludeSources`       | `List[str]`    | Exclude specific sources                           |
| `optInSources`         | `List[str]`    | Include non-default sources                        |
| `language`             | `str`          | Language filter                                    |
| `countries`            | `List[str]`    | Filter by country codes (e.g., `["US", "GB"]`)     |
| `extended`             | `bool`         | Include full article details (default: `False`)    |
| `includeEntities`      | `bool`         | Include tagged companies (default: `False`)        |
| `excludeEmptyContent`  | `bool`         | Only articles with content (default: `False`)      |

### `Article`

Article object fields:

| Field          | Type              | Description                                 |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | Article title                               |
| `link`         | `str`             | Article URL                                 |
| `publishDate`  | `datetime`        | Publication date                            |
| `source`       | `str`             | Source domain                               |
| `language`     | `str`             | Article language code                       |
| `summary`      | `str`             | Article summary                             |
| `content`      | `str`             | Full article content (if available)         |
| `sentiment`    | `str`             | Sentiment analysis result                   |
| `confidence`   | `float`           | Sentiment confidence score                  |
| `images`       | `List[str]`       | List of image URLs                          |
| `companies`    | `List[Company]`   | Tagged companies with metadata              |

### `Company`

Tagged company information:

| Field             | Type              | Description                              |
| ----------------- | ----------------- | ---------------------------------------- |
| `companyId`       | `int`             | Unique company identifier                |
| `name`            | `str`             | Company name                             |
| `ticker`          | `str`             | Primary ticker symbol                    |
| `confidence`      | `float`           | Tagging confidence score                 |
| `country`         | `str`             | Company country                          |
| `exchange`        | `str`             | Primary exchange                         |
| `sector`          | `str`             | Business sector                          |
| `industry`        | `str`             | Industry classification                  |
| `isin`            | `str`             | ISIN code                                |
| `openfigi`        | `str`             | OpenFIGI identifier                      |
| `primaryListing`  | `Listing`         | Primary exchange listing                 |
| `isins`           | `List[str]`       | All ISIN codes                           |
| `otherListings`   | `List[Listing]`   | Other exchange listings                  |

### `Source`

News source metadata:

| Field                | Type    | Description                                     |
| -------------------- | ------- | ----------------------------------------------- |
| `domain`             | `str`   | Source domain (e.g., `"www.reuters.com"`)       |
| `isContentAvailable` | `bool`  | Whether full content is available               |
| `isDefaultSource`    | `bool`  | Whether source is included by default           |

---

## 🤝 Contributing

We welcome contributions and suggestions!

- Fork this repo
- Create a feature branch
- Submit a pull request with tests if applicable

---

## 📄 License

MIT License – see [LICENSE](LICENSE)

---

## 🔗 Resources

- [Finlight API Documentation](https://docs.finlight.me)
- [GitHub Repository](https://github.com/jubeiargh/finlight-client-py)
- [PyPI Package](https://pypi.org/project/finlight-client)
