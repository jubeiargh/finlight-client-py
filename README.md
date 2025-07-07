# Finlight Client – Python Library

A Python client library for interacting with the [Finlight News API](https://finlight.me).
Finlight delivers real-time and historical financial news articles, enriched with sentiment analysis, company tagging, and market metadata. This library makes it easy to integrate Finlight into your Python applications.

---

## ✨ Features

* Fetch **structured** news articles with date parsing and metadata.
* Filter by **tickers**, **sources**, **languages**, and **date ranges**.
* Stream **real-time** news updates via **WebSocket**.
* Auto-reconnect and ping/pong watchdog for WebSocket.
* Strongly typed models using `pydantic` and `dataclass`.
* Lightweight and developer-friendly.

---

## 📦 Installation

```bash
pip install finlight-client
```

---

## 🚀 Quick Start

### Fetch Articles via REST API

```python
from finlight_client import ApiClient, ApiConfig
from finlight_client.services import ArticleService
from finlight_client.models import GetArticlesParams

def main():
    api_client = ApiClient(config=ApiConfig(api_key="your_api_key"))
    service = ArticleService(api_client)

    params = GetArticlesParams(
        query="Nvidia",
        language="en",
        from_="2024-01-01",
        to="2024-12-31",
        includeContent=True
    )
    response = service.fetch_articles(params=params)

    for article in response.articles:
        print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

---

### Stream Real-Time Articles via WebSocket

```python
import asyncio
from finlight_client.websocket_client import WebSocketClient
from finlight_client.models import GetArticlesWebSocketParams, ApiConfig

def on_article(article):
    print("📨 Received:", article.title)

async def main():
    ws_client = WebSocketClient(config=ApiConfig(api_key="your_api_key"))

    payload = GetArticlesWebSocketParams(
        query="Nvidia",
        sources=["www.reuters.com"],
        language="en",
        extended=True,
    )

    await ws_client.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

`ApiConfig` allows fine-tuning of your API client:

| Parameter     | Type         | Description                | Default                   |
| ------------- | ------------ | -------------------------- | ------------------------- |
| `api_key`     | `str`        | Your API key               | **Required**              |
| `base_url`    | `AnyHttpUrl` | Base REST API URL          | `https://api.finlight.me` |
| `wss_url`     | `AnyHttpUrl` | WebSocket server URL       | `wss://wss.finlight.me`   |
| `timeout`     | `int`        | Request timeout in ms      | `5000`                    |
| `retry_count` | `int`        | Retry attempts on failures | `3`                       |

---

## 📚 API Overview

### `ArticleService.fetch_articles(params: GetArticlesParams) -> ArticleResponse`

* Fetch articles with flexible filtering.
* Automatically parses ISO date strings into `datetime`.

### `WebSocketClient.connect(request_payload, on_article)`

* Subscribe to live article updates.
* Reconnects automatically on disconnects.
* Pings the server every 30s to keep the connection alive.

---

## 🧯 Error Handling

* Invalid date strings raise clear Python `ValueError`s.
* REST and WebSocket exceptions are logged and managed.
* WebSocket includes reconnect, watchdog, and ping/pong mechanisms.

---

## 🧰 Model Summary

### `GetArticlesParams`

Query parameters to filter articles, including:

* `query`: Search text
* `tickers`: List of ticker symbols
* `sources`, `excludeSources`, `optInSources`
* `language`: e.g., `"en"`, `"de"`
* `from_`, `to`: Date range (`YYYY-MM-DD` or ISO)
* `includeContent`, `includeEntities`, `excludeEmptyContent`
* `order`, `page`, `pageSize`

### `Article`

Each article includes:

* `title`, `link`, `publishDate`, `source`, `language`
* `summary`, `content`, `sentiment`, `confidence`
* `images`: List of image URLs
* `companies`: List of tagged `Company` objects

---

## 🤝 Contributing

We welcome contributions and suggestions!

* Fork this repo
* Create a feature branch
* Submit a pull request with tests if applicable

---

## 📄 License

MIT License – see [LICENSE](LICENSE)

---

## 🔗 Resources

* [Finlight API Documentation](https://docs.finlight.me)
* [GitHub Repository](https://github.com/jubeiargh/finlight-client-py)
* [PyPI Package](https://pypi.org/project/finlight-client)