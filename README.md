# Finlight Client – Python Library

A Python client library for interacting with the [Finlight News API](https://finlight.me).  
Finlight delivers real-time and historical financial news articles, enriched with sentiment analysis and market insights. This library makes it easy to integrate Finlight into your Python applications.

---

## ✨ Features

- Fetch **basic** and **extended** articles via REST API.
- Stream real-time news using **WebSocket**.
- Built-in retry and timeout handling.
- Fully type-annotated models using `pydantic`.
- Lightweight and developer-friendly.

---

## 📦 Installation

```bash
pip install finlight-client
```

---

## 🚀 Quick Start

### Fetching Articles via REST API

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesParams

def main():
    client = FinlightApi(
        config=ApiConfig(
            api_key="your_api_key"
        )
    )

    params = GetArticlesParams(query="Nvidia", language="en")
    articles = client.articles.get_extended_articles(params=params)
    print(articles)

if __name__ == "__main__":
    main()
```

---

### Streaming Real-Time Articles via WebSocket

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print("📨 Received article:", article.title)

async def main():
    client = FinlightApi(
        config=ApiConfig(
            api_key="your_api_key"
        )
    )

    payload = GetArticlesWebSocketParams(
        sources=["www.reuters.com"],
        language="en"
    )

    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

`ApiConfig` accepts the following parameters:

| Parameter     | Type  | Description                      | Default                   |
| ------------- | ----- | -------------------------------- | ------------------------- |
| `api_key`     | `str` | Your API key.                    | **Required**              |
| `base_url`    | `str` | Base URL for REST API.           | `https://api.finlight.me` |
| `wss_url`     | `str` | WebSocket server URL.            | `wss://wss.finlight.me`   |
| `timeout`     | `int` | Timeout for requests (ms).       | `5000`                    |
| `retry_count` | `int` | Max retries for failed requests. | `3`                       |

---

## 📚 API Reference

### `client.articles.get_basic_articles(params)`

- Fetch short-form articles with titles, links, etc.

### `client.articles.get_extended_articles(params)`

- Fetch full articles with summaries and full text.

### `client.websocket.connect(request_payload, on_article)`

- Subscribe to a real-time feed of articles via WebSocket.
- Payload: `GetArticlesWebSocketParams`
- Callback: `on_article(article: Article)`

---

## 🧯 Error Handling

- HTTP errors raise detailed Python exceptions.
- WebSocket disconnections trigger auto-reconnect unless stopped.
- Logs are printed via the `finlight-websocket-client` logger.

---

## 🤝 Contributing

Pull requests and issues are welcome!
Please ensure any contributions are well tested and documented.

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file.

---

## 🔗 Resources

- [Finlight API Docs](https://docs.finlight.me)
- [GitHub Repo](https://github.com/jubeiargh/finlight-client-py)
- [PyPI Package](https://pypi.org/project/finlight-client)

---
