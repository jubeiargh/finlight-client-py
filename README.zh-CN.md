# Finlight Client – Python 客户端库

*[English](README.md) | 简体中文 | [日本語](README.ja.md) | [한국어](README.ko.md)*

用于对接 [Finlight News API](https://finlight.me) 的 Python 客户端库。
Finlight 提供实时和历史财经新闻，并附带情感分析、公司实体标注和市场元数据。本库让你能够方便地在 Python 应用中集成 Finlight。

---

## ✨ 功能特性

- 获取**结构化**新闻文章，自动解析日期并附带元数据。
- 按**股票代码**、**新闻源**、**语言**和**日期区间**过滤。
- 通过 **Enhanced** 和 **Raw WebSocket** 订阅**实时**新闻推送，支持自动重连。
- **支持 Webhook**，包含 HMAC 签名验证和重放攻击防护。
- 进阶 WebSocket 能力：
  - 指数退避重连策略
  - Ping/Pong 保活机制
  - 主动连接轮换（在 AWS 2 小时限制之前）
  - 连接接管，用于替换已有连接
  - 速率限制与管理端强制断开的处理
- 基于 `pydantic` 和 `dataclass` 的强类型模型。
- 轻量，对开发者友好。

---

## 📦 安装

```bash
pip install finlight-client
```

---

## 🚀 快速开始

### 通过 REST API 获取文章

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesParams

def main():
    # 初始化客户端
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # 构造查询参数
    params = GetArticlesParams(
        query="Nvidia",
        language="en",
        from_="2024-01-01",
        to="2024-12-31",
        includeContent=True
    )

    # 获取文章
    response = client.articles.fetch_articles(params=params)

    # 输出结果
    for article in response.articles:
        print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

### 通过链接获取单篇文章

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

### 通过 WebSocket 订阅实时文章

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print("📨 收到:", article.title)

async def main():
    # 初始化客户端
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # 构造 WebSocket 参数
    payload = GetArticlesWebSocketParams(
        query="Nvidia",
        sources=["www.reuters.com"],
        language="en",
        extended=True,
    )

    # 建立连接并接收文章
    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 通过 Raw WebSocket 订阅原始文章

Raw WebSocket 跳过 AI 增强处理（不含情感、置信度和公司标注），因此推送更快。它支持 `source:`、`title:` 和 `summary:` 字段级过滤。

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig, RawWebSocketOptions
from finlight_client.models import GetRawArticlesWebSocketParams

def on_article(article):
    print("📨 收到:", article.title)

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

## ⚙️ 配置

### `ApiConfig`

核心 API 配置：

| 参数          | 类型         | 说明                       | 默认值                    |
| ------------- | ------------ | -------------------------- | ------------------------- |
| `api_key`     | `str`        | 你的 API 密钥              | **必填**                  |
| `base_url`    | `AnyHttpUrl` | REST API 基础地址          | `https://api.finlight.me` |
| `wss_url`     | `AnyHttpUrl` | WebSocket 服务地址         | `wss://wss.finlight.me`   |
| `timeout`     | `int`        | 请求超时（毫秒）           | `5000`                    |
| `retry_count` | `int`        | 失败重试次数               | `3`                       |

### `FinlightApi` WebSocket 选项

进阶 WebSocket 配置（全部可选）。可以使用扁平关键字参数，也可以使用选项对象：

```python
# 使用扁平关键字参数（仅限 Enhanced WebSocket）
client = FinlightApi(config, websocket_takeover=True)

# 使用选项对象（Enhanced 和 Raw WebSocket 均可）
from finlight_client import WebSocketOptions, RawWebSocketOptions

client = FinlightApi(
    config,
    websocket_options=WebSocketOptions(takeover=True),
    raw_websocket_options=RawWebSocketOptions(takeover=True),
)
```

`WebSocketOptions` 和 `RawWebSocketOptions` 接受相同的字段：

| 字段                     | 类型       | 说明                                         | 默认值        |
| ------------------------ | ---------- | -------------------------------------------- | ------------- |
| `ping_interval`          | `int`      | Ping 间隔（秒）                              | `25`          |
| `pong_timeout`           | `int`      | Pong 超时（秒）                              | `60`          |
| `base_reconnect_delay`   | `float`    | 初始重连延迟（秒）                           | `0.5`         |
| `max_reconnect_delay`    | `float`    | 最大重连延迟（秒）                           | `10.0`        |
| `connection_lifetime`    | `int`      | 连接生命周期（秒）                           | `6900`（115 分钟）|
| `takeover`               | `bool`     | 接管已有连接                                 | `False`       |
| `on_close`               | `Callable` | 关闭事件回调 `(code, reason)`                | `None`        |

---

## 📚 API 概览

### `ArticleService.fetch_articles(params: GetArticlesParams) -> ArticleResponse`

按条件灵活获取文章：
- 支持带布尔运算符的进阶查询语句
- 自动将 ISO 日期字符串解析为 `datetime`
- 分页，页大小可配置（1-1000）
- 可选返回全文和实体标注

### `ArticleService.fetch_article_by_link(params: GetArticleByLinkParams) -> Article`

按 URL 获取单篇文章：

- 若数据库中存在该文章则返回
- 可选返回全文和实体标注
- 适用于按 URL 精确取回特定文章

### `SourcesService.get_sources() -> List[Source]`

获取可用的新闻源：
- 返回带元数据的新闻源列表
- 标明是否提供全文，以及是否为默认源
- 适用于构建新闻源过滤条件

### `WebSocketClient.connect(request_payload, on_article)`

订阅实时文章更新：
- 采用指数退避自动重连
- 妥善处理速率限制和管理端操作
- 每 25 秒向服务端发送 Ping 以保持连接
- 在 AWS 2 小时超时之前主动轮换连接
- 可选连接接管模式

### `RawWebSocketClient.connect(request_payload, on_article)`

订阅实时原始文章更新（推送更快，不含 AI 增强）：
- 重连与保活机制与 Enhanced WebSocket 相同
- 连接至 `wss://wss.finlight.me/raw`
- 返回 `RawArticle` 对象（不含情感、置信度和公司信息）
- 支持字段级查询过滤：`source:`、`title:`、`summary:`

### `WebhookService.construct_event(raw_body, signature, endpoint_secret, timestamp?)`

安全地接收 Webhook 事件：
- HMAC-SHA256 签名验证
- 重放攻击防护（5 分钟容差）
- 返回校验通过的 `Article` 对象
- 请求非法时抛出 `WebhookVerificationError`

---

## 🧯 错误处理

- 非法日期字符串会抛出语义明确的 Python `ValueError`。
- REST 和 WebSocket 异常均会被记录和处理。
- WebSocket 内置重连、看门狗和 Ping/Pong 机制。

---

## 📖 更多示例

### 获取可用新闻源

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

### 接收 Webhook 事件（Flask）

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
        print(f"📨 新文章: {article.title}")
        return '', 200
    except WebhookVerificationError as e:
        print(f"❌ Webhook 校验失败: {e}")
        return '', 400

if __name__ == "__main__":
    app.run(port=3000)
```

### 自定义配置的进阶 WebSocket 用法

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print(f"📨 {article.title}")

def on_close(code, reason):
    print(f"🔌 连接已关闭: {code} - {reason}")

async def main():
    config = ApiConfig(api_key="your_api_key")

    # 进阶 WebSocket 配置
    client = FinlightApi(
        config,
        websocket_ping_interval=30,  # 自定义 Ping 间隔
        websocket_pong_timeout=90,   # 自定义 Pong 超时
        websocket_takeover=True,     # 替换已有连接
        websocket_on_close=on_close  # 关闭事件回调
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

## 🧰 数据模型速览

### `GetArticlesParams`（REST API）

用于过滤文章的查询参数：

| 字段                   | 类型           | 说明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 支持布尔运算符的搜索文本                           |
| `tickers`              | `List[str]`    | 按股票代码过滤（例如 `["AAPL", "NVDA"]`）          |
| `sources`              | `List[str]`    | 指定包含的新闻源                                   |
| `excludeSources`       | `List[str]`    | 指定排除的新闻源                                   |
| `optInSources`         | `List[str]`    | 纳入非默认新闻源                                   |
| `language`             | `str`          | 语言过滤（例如 `"en"`、`"de"`）                    |
| `countries`            | `List[str]`    | 按国家代码过滤（例如 `["US", "GB"]`）              |
| `from_`                | `str`          | 起始日期（`YYYY-MM-DD` 或 ISO 格式）               |
| `to`                   | `str`          | 结束日期（`YYYY-MM-DD` 或 ISO 格式）               |
| `includeContent`       | `bool`         | 是否返回文章全文（默认 `False`）                   |
| `includeEntities`      | `bool`         | 是否返回标注的公司（默认 `False`）                 |
| `excludeEmptyContent`  | `bool`         | 仅返回含全文的文章（默认 `False`）                 |
| `orderBy`              | `str`          | 排序字段：`"publishDate"`、`"createdAt"` 或 `"revisedDate"` |
| `order`                | `str`          | 排序方向：`"ASC"` 或 `"DESC"`                      |
| `page`                 | `int`          | 页码（从 1 开始）                                  |
| `pageSize`             | `int`          | 每页条数（1-1000）                                 |

### `GetArticleByLinkParams`（REST API）

按 URL 获取单篇文章的参数：

| 字段                   | 类型           | 说明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `link`                 | `str`          | 待获取文章的 URL（必填）                           |
| `includeContent`       | `bool`         | 是否返回文章全文（默认 `None`）                    |
| `includeEntities`      | `bool`         | 是否返回标注的公司（默认 `None`）                  |

### `GetArticlesWebSocketParams`（WebSocket）

WebSocket 订阅参数：

| 字段                   | 类型           | 说明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 搜索文本                                           |
| `tickers`              | `List[str]`    | 按股票代码过滤                                     |
| `sources`              | `List[str]`    | 指定包含的新闻源                                   |
| `excludeSources`       | `List[str]`    | 指定排除的新闻源                                   |
| `optInSources`         | `List[str]`    | 纳入非默认新闻源                                   |
| `language`             | `str`          | 语言过滤                                           |
| `countries`            | `List[str]`    | 按国家代码过滤（例如 `["US", "GB"]`）              |
| `extended`             | `bool`         | 是否返回完整文章详情（默认 `False`）               |
| `includeEntities`      | `bool`         | 是否返回标注的公司（默认 `False`）                 |
| `excludeEmptyContent`  | `bool`         | 仅返回含全文的文章（默认 `False`）                 |

### `GetRawArticlesWebSocketParams`（Raw WebSocket）

Raw WebSocket 订阅参数：

| 字段                   | 类型           | 说明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 支持字段过滤的搜索文本（`source:`、`title:`、`summary:`） |
| `sources`              | `List[str]`    | 指定包含的新闻源                                   |
| `excludeSources`       | `List[str]`    | 指定排除的新闻源                                   |
| `optInSources`         | `List[str]`    | 纳入非默认新闻源                                   |
| `language`             | `str`          | 语言过滤                                           |

### `Article`

文章对象字段（Enhanced WebSocket / REST API）：

| 字段           | 类型              | 说明                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 文章标题                                    |
| `link`         | `str`             | 文章 URL                                    |
| `publishDate`  | `datetime`        | 发布时间                                    |
| `source`       | `str`             | 新闻源域名                                  |
| `language`     | `str`             | 文章语言代码                                |
| `summary`      | `str`             | 文章摘要                                    |
| `content`      | `str`             | 文章全文（若可用）                          |
| `sentiment`    | `str`             | 情感分析结果                                |
| `confidence`   | `float`           | 情感分析置信度                              |
| `images`       | `List[str]`       | 图片 URL 列表                               |
| `companies`    | `List[Company]`   | 标注的公司及其元数据                        |

### `RawArticle`

原始文章对象字段（Raw WebSocket）：

| 字段           | 类型              | 说明                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 文章标题                                    |
| `link`         | `str`             | 文章 URL                                    |
| `publishDate`  | `datetime`        | 发布时间                                    |
| `source`       | `str`             | 新闻源域名                                  |
| `language`     | `str`             | 文章语言代码                                |
| `summary`      | `str`             | 文章摘要                                    |
| `images`       | `List[str]`       | 图片 URL 列表                               |

### `Company`

标注的公司信息：

| 字段              | 类型              | 说明                                     |
| ----------------- | ----------------- | ---------------------------------------- |
| `companyId`       | `int`             | 公司唯一标识                             |
| `name`            | `str`             | 公司名称                                 |
| `ticker`          | `str`             | 主要股票代码                             |
| `confidence`      | `float`           | 标注置信度                               |
| `country`         | `str`             | 公司所属国家                             |
| `exchange`        | `str`             | 主要交易所                               |
| `sector`          | `str`             | 所属板块                                 |
| `industry`        | `str`             | 行业分类                                 |
| `isin`            | `str`             | ISIN 代码                                |
| `openfigi`        | `str`             | OpenFIGI 标识                            |
| `primaryListing`  | `Listing`         | 主要交易所上市信息                       |
| `isins`           | `List[str]`       | 全部 ISIN 代码                           |
| `otherListings`   | `List[Listing]`   | 其他交易所上市信息                       |

### `Source`

新闻源元数据：

| 字段                 | 类型    | 说明                                            |
| -------------------- | ------- | ----------------------------------------------- |
| `domain`             | `str`   | 新闻源域名（例如 `"www.reuters.com"`）          |
| `isContentAvailable` | `bool`  | 是否提供全文                                    |
| `isDefaultSource`    | `bool`  | 是否为默认包含的新闻源                          |

---

## 🤝 参与贡献

欢迎贡献代码和提出建议！

- Fork 本仓库
- 创建功能分支
- 提交 Pull Request，如涉及逻辑改动请附带测试

---

## 📄 许可证

MIT License – 参见 [LICENSE](LICENSE)

---

## 🔗 相关资源

- [Finlight API 文档](https://docs.finlight.me)
- [GitHub 仓库](https://github.com/jubeiargh/finlight-client-py)
- [PyPI 包](https://pypi.org/project/finlight-client)
- [中文产品页](https://finlight.me/zh/news-api)
