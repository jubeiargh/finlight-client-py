# Finlight Client - Python Library

<!-- ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/finlight-client)
![PyPI](https://img.shields.io/pypi/v/finlight-client)
![License](https://img.shields.io/github/license/jubeiargh/finlight-client) -->

A Python client library for interacting with the [Finlight News API](https://finlight.me). Finlight provides financial news articles, sentiment analysis, and market insights to help users stay updated on global financial trends. This library simplifies integration with the API, allowing developers to access articles and real-time data with ease.

## Features

- Fetch **basic articles** with metadata such as titles, authors, and links.
- Retrieve **extended articles** with full content and summaries.
- Stream articles in real-time using **WebSocket** connections.
- Automatic retry for API requests with exponential backoff.
- Fully type-annotated and Pythonic interface.

## Installation

Install the package via pip:

```bash
pip install finlight-client
```

## Quick Start

### Basic Usage

```python
from finlight_client import FinlightApi

# Initialize the client
config = {
    "api_key": "your_api_key",  # Replace with your API key
}
client = FinlightApi(config)

# Fetch basic articles
params = {
    "query": "financial market",
    "from": "2024-01-01",
    "to": "2024-01-31",
    "language": "en",
    "pageSize": 10,
}
response = client.articles.get_basic_articles(params)

# Print the articles
for article in response['articles']:
    print(article['title'], article['publishDate'])  # publishDate is a datetime object
```

### Streaming Real-Time Articles

```python
def on_message(article):
    print(f"Received article: {article['title']}")

# Set up WebSocket client
client.websocket.connect(
    {"query": "finance", "language": "en", "extended": True},
    on_message
)

# Keep the WebSocket running (use Ctrl+C to stop)
import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Disconnecting WebSocket...")
    client.websocket.disconnect()
```

## Configuration Options

The `FinlightApi` client accepts the following configuration parameters:

| Parameter     | Type  | Description                               | Default                   |
| ------------- | ----- | ----------------------------------------- | ------------------------- |
| `api_key`     | `str` | Your API key for authenticating requests. | **Required**              |
| `base_url`    | `str` | Base URL for API requests.                | `https://api.finlight.me` |
| `timeout`     | `int` | Timeout for API requests in milliseconds. | `5000`                    |
| `retry_count` | `int` | Number of retries for failed requests.    | `3`                       |
| `wss_url`     | `str` | WebSocket server URL.                     | `wss://wss.finlight.me`   |

## API Methods

### Articles

1. **Fetch Basic Articles**

   Fetch articles with metadata like title, author, and source.

   ```python
   client.articles.get_basic_articles(params)
   ```

   - **Parameters**:
     - `query`: Search query string.
     - `from`: Start date in `YYYY-MM-DD` format.
     - `to`: End date in `YYYY-MM-DD` format.
     - `language`: Language filter (default: `en`).
     - `pageSize`: Number of results per page (1-1000).
     - `page`: Page number.

2. **Fetch Extended Articles**

   Fetch articles with full content and summaries.

   ```python
   client.articles.get_extended_articles(params)
   ```

### WebSocket

1. **Real-Time Article Streaming**

   Stream articles in real-time using WebSocket. Supports both basic and extended articles.

   ```python
   client.websocket.connect(request_payload, on_message)
   ```

   - **Parameters**:
     - `query`: Search query string.
     - `language`: Language filter (default: `en`).
     - `extended`: Boolean to enable full content.

## Error Handling

- HTTP errors are raised as exceptions with detailed messages.
- WebSocket errors are logged to the console.

### Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Resources

- [Finlight API Documentation](https://docs.finlight.me)
- [PyPI Package](https://pypi.org/project/finlight-client)
- [GitHub Repository](https://github.com/jubeiargh/finlight-client-py)
