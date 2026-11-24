# finlight-client (Python)

*[English](README.md) | 简体中文 | [日本語](README.ja.md) | [한국어](README.ko.md)*

> 本文译自 [README.md](README.md)，如有出入以英文版为准。

> **不兼容的新版本。** 3.0.0 只支持 finlight API v3。为 2.x 编写的代码不能直接运行。
> 如需继续使用 2.x（API v2），请固定 `finlight-client<3`。参见[从 2.x 迁移](#从-2x-迁移)。

[finlight](https://finlight.me) 新闻 API 的 Python 客户端：通过 REST 搜索和查询金融新闻、公司和来源，
通过 WebSocket 实时接收文章，并验证 Webhook。

## 版本

| SDK 版本 | API 版本 | 状态 |
|---|---|---|
| 3.x | v3（REST `/v3`、WebSocket `payloadVersion` 3、v3 Webhook） | 当前版本 |
| 2.x | v2 | 不再发布新版本 |

SDK 版本与 API 版本相互独立。其他支持 API v3 的 finlight SDK：TypeScript 4.x、PHP 2.x、
Go 模块 `/v2`、.NET 2.x、Java 1.x、Ruby 1.x、Rust 0.2。

## 环境要求

- Python 3.10 或更高版本
- `requests` 2.31+、`pydantic` 2.7+、`websockets` 15.0+

## 安装

```bash
pip install "finlight-client>=3,<4"
```

## 快速开始

```python
from finlight_client import FinlightClient

with FinlightClient(api_key="YOUR_API_KEY") as client:
    page = client.articles.search(query="ticker:NVDA", limit=10, include=["companies"])
    for article in page.articles:
        print(article.published_at, article.title)
```

REST 调用是同步的，实时流是异步迭代器。参数使用 snake_case，每个参数对应 API 中唯一的一个键
（`from_` 即 `from`）。只有你传入的参数才会被发送。

## 搜索文章

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

`search_all` 会自动翻页。调用时请求内容即被固定，之后的页面只追加 cursor。
由于每一页都会消耗配额，它在 `max_pages` 页（默认 10）后停止。

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

结果只能遍历一次。未知参数会抛出 `TypeError`；形式错误（例如 `limit=0` 或 `languages=[]`）会在发送前
抛出 `FinlightValidationError`。词表中的取值不在本地检查，因此服务器新增的取值无需更新 SDK 即可使用。

## 查询文章、公司和来源

```python
article = client.articles.get("EU8JwpsZ8iJehuyPZjMqRz", include=["content"])
article = client.articles.get_by_link("https://www.reuters.com/...")

companies = client.companies.search("NVDA", mic="XNAS")   # at most 10, no pages
companies = client.companies.get_many([4821, 1001])
company = client.companies.get(4821)                      # revalidated with its ETag next time

sources = client.sources.list()
```

查不到时抛出 `NotFoundError`。公司查询需要 `entityAccess` 权限（否则抛出 `ForbiddenError`）。

### 读取文章

- `content` 和 `sentiment` 有三种状态。键未发送（未请求或无权限）时 `article.content_present` 为 false；
  `content_present` 为 true 且 `article.content is None` 表示"没有文本"。`sentiment_present` 同理。
- `companies` 和 `events` 未发送时为 `None`；文章已打标签但没有结果时为 `[]`。
  请使用 `companies_present` 和 `events_present` 判断。
- 只有当 `companies` 在同一响应中时，才会发送 `events[].company_ids`。
- 时间戳保留发送时的原始字符串（`published_at`）。`published_at_time` 等 `*_time` 属性会严格解析，
  无法解析时返回 `None`。
- 新版服务器返回的未知键会被忽略。`finlight_client.raw_json(article)` 可取得原始 JSON。
- 词表取值始终是普通字符串，可与 `finlight_client` 中的常量比较（`EventType.MNA`、`Role.ACQUIRER` 等）。
  未知取值按原样保留。

## 实时流

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

- `event.kind` 为 `created`、`updated` 或 `other`（本 SDK 尚不认识的事件）。
- `client.raw_stream(query=..., sources=..., exclude_sources=..., language=..., include_updates=...)`
  推送尚未增强处理的文章：没有 `include`，也没有 content、sentiment、companies 或 events。
- 流每 25 秒发送一次 ping，60 秒未收到 pong 时重新连接，115 分钟后建立新连接。
  每次重连后都会发送相同的订阅并丢弃重复的推送。
- 它从不自动补数据。`on_reconnect(last_seen, reason)` 会收到你看到的最新 `availableAt`
  （raw 为 `firstSeenAt`）。可用 `articles.search_all(from_=last_seen, order_by="availableAt")`
  补齐缺口（raw 用 `order_by="firstSeenAt"`）。
- 终止性问题会以错误结束循环：无效密钥（`UnauthorizedError`）、无 WebSocket 权限（`ForbiddenError`）、
  订阅被拒（`ValidationFailedError`），以及被其他连接接管时的 `PreemptedError`。其他问题会自动重连并交给
  `on_error`。
- 每月 WebSocket 配额用尽时（连接被拒绝，或原因为 `quota_exceeded` 的 `PreemptedError`），流不会结束：
  它每小时重试一次，直到配额恢复。每次尝试都会记录一条警告并调用 `on_error`。设置 `quota_reconnect=False`
  可改为以错误结束流；`quota_reconnect_interval` 可修改间隔。
- 离开 `async with` 代码块即关闭连接。取消操作永远不会被吞掉。

需要了解的限制：

- 套餐的连接数上限由 enriched、raw 以及旧版 SDK 的连接共同占用。达到上限时新连接会被拒绝，
  SDK 会在 60 秒后重试。给客户端传入 `takeover=True` 可改为替换最旧的连接。
- 订阅后服务器会立即推送一篇最新的匹配文章（每次重连后也会），这篇文章可能较旧。
- 超过 32,000 字节的实时帧会被服务器静默丢弃。对长文章使用 `include=["content"]` 时可能发生。
  请通过 `articles.get` 获取。
- `connection.admitted` 在服务器检查订阅之前到达，并不表示订阅已被接受。
- WebSocket 连接会像 `websockets` 库一样使用环境变量中的代理设置（`HTTPS_PROXY`、`ALL_PROXY`）。
  传入 `websocket_options={"proxy": None}` 可关闭。

## Webhook

finlight 会对每个 Webhook 签名。请在解析任何内容之前，用**原始**请求体验证：

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

- `headers` 可以是任何请求头映射或键值对列表（Flask、Django、Starlette、`http.server`、WSGI environ）。
  名称匹配不区分大小写。`construct_event_from_values(raw_body, signature, timestamp, secret)`
  直接接收两个请求头的值；`verify_signature` 只做校验。
- 时间戳必须在 300 秒（`tolerance`）之内，前后两个方向都适用。
- 控制台发送的测试 Webhook 的 `result.is_test` 为 true，它不受套餐权限裁剪。
- 永远不要返回 410：它会立即停用该 Webhook。连续 10 次非 2xx 响应也会将其停用。

获取原始请求体：

| 框架 | 原始请求体 |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

将 Webhook 切换到 v3：先部署本 SDK；对 `WrongPayloadVersion` 返回 2xx 并保留其原始 JSON；
然后在控制台将 Webhook 切换为 `payloadVersion` 3；再等待约 2 小时，因为切换前排队的重试仍会以旧格式到达。

## 错误与重试

所有错误都继承自 `FinlightError`，并带有一个 `kind` 字符串。

| 错误 | 场景 |
|---|---|
| `FinlightApiError` | API 返回了错误。包含 `status`、`code`、`title`、`detail`、`request_id`、`errors`、`raw`、`docs_url`。每个 code 有对应子类：`ValidationFailedError`、`CursorInvalidError`、`CursorMismatchError`、`UnauthorizedError`、`ForbiddenError`、`NotFoundError`、`RateLimitedError`、`InternalServerError`。未知 code 使用基类。 |
| `RateLimitedError` | `limit_type` 为 `monthly`、`burst` 或更新的取值；`retry_after` 以秒为单位。 |
| `FinlightValidationError` | 请求在本地被拒绝（属于 `ValueError`）。 |
| `FinlightNetworkError`、`FinlightTimeoutError` | 网络故障或超时。原始错误位于 `__cause__`。 |
| `FinlightDecodeError` | 单个响应无法读取。 |
| `WebhookVerificationError` | Webhook 验证失败（`reason`）。 |
| `PreemptedError` | 流被其他连接接管（`reason`、`new_lease_id`）。设置 `quota_reconnect=False` 时，配额用尽也会抛出。 |

重试：5xx 响应、网络错误和超时最多重试 3 次，等待时间逐次增加，搜索请求也不例外。
400、401、403、404 以及按月配额的 429 永不重试：按月配额的 429 会立即报错，`search_all` 中也是如此；
只有流会等待配额恢复（见上文）。突发（burst）429 会等待 `Retry-After` 秒
（没有该请求头时为 10 秒）后再试一次；设置 `retry_on_burst="off"` 可关闭。每次调用都发送自己的
`X-Request-Id`，重试时保持不变。按 Ctrl+C 可中止调用；等待会立即结束，且不会重试。

## 配置

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

所有时间单位均为秒。也可以构造 `FinlightConfig` 并通过 `config=` 传入。使用自己的 `requests.Session`
时，其超时、代理和适配器生效；请不要添加重试适配器，因为每次尝试都会消耗配额。SDK 永远不会关闭
不是它创建的 session。`websocket_options` 会传给 `websockets.connect`。SDK 通过 `finlight_client`
日志记录器输出日志，默认不输出。

## 数据说明

- 旧文章的 `published_at` 可能是 `"1970-01-01T00:00:00.000Z"`，按原样提供。
- 空文本以 `None` 表示（`summary`、`content`）。
- 在角色功能上线前打标签的文章，`role` 和 `relevance` 为 `None`，`events` 为 `[]`。
- 在 id 功能上线前入库的文章，`articles.get(id)` 返回 404。请使用 `get_by_link`。
- 旧文章的 `available_at` 为 `None`，raw 流中始终为 `None`。

## 从 2.x 迁移

完整指南见 [docs.finlight.me](https://docs.finlight.me/migration/v2-to-v3)。简要对照：

| 2.x | 3.x |
|---|---|
| `FinlightApi(ApiConfig(api_key=...))` | `FinlightClient(api_key=...)` |
| `articles.fetch_articles(GetArticlesParams(...))` | `articles.search(...)`、`articles.search_all(...)` |
| `page` / `pageSize` | `limit` / `cursor` |
| `includeContent`、`includeEntities` | `include=["content", "companies", "events"]` |
| `order="DESC"` | `order="desc"` |
| `publishDate`、`createdAt`、`revisedDate` | `published_at`、`first_seen_at`、`revised_at` |
| `images` | `media[].url` |
| `source`（字符串） | `source.domain` |
| `sentiment`、`confidence` | `sentiment.label`、`sentiment.confidence` |
| `api.websocket.connect(...)` | `async for event in client.stream(...)` |
| `api.raw_websocket` | `client.raw_stream(...)` |
| Webhook `isUpdate` | `event.event == "article.updated"` |
| Webhook 请求体 | `event.data`，以及用于去重的 `event.event_id` |

不要在同一个密钥上同时运行 2.x 和 3.x 的流：它们共用连接数上限。

## 开发

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`CONFORMANCE.md` 列出了契约套件中每个用例对应的测试。在线测试只针对 dev 环境运行，需要
`FINLIGHT_API_KEY`、`FINLIGHT_BASE_URL` 和 `FINLIGHT_WSS_URL`：
`pytest tests/live -m live --force-enable-socket`。

## 许可证

MIT
