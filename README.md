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
    for article in response['articles']:
        print(f"{article['publishDate']} | {article['title']}")

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

### `ArticleService.fetch_articles(params: GetArticlesParams) -> dict`

* Fetch articles with flexible filtering.
* Automatically parses ISO date strings into `datetime`.

### `SourcesService.get_sources() -> List[Source]`

* Retrieve available news sources.
* Returns list of sources with metadata about content availability.

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

## 📖 Additional Examples

### Fetch Available Sources

```python
from finlight_client import FinlightApi, ApiConfig

def main():
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)
    
    sources = client.sources.get_sources()
    
    for source in sources:
        print(f"{source['domain']} - Content: {source['isContentAvailable']}")

if __name__ == "__main__":
    main()
```

---

## 🧰 Model Summary

### `GetArticlesParams`

Query parameters to filter articles, including:

* `query`: Search text
* `tickers`: List of ticker symbols
* `sources`, `excludeSources`: Source filtering
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