# finlight client for Python

*[English](README.md) | 简体中文 | [日本語](README.ja.md) | [한국어](README.ko.md)*

> 本文译自 [README.md](README.md)，可能会稍晚更新；如有出入，以英文版为准。

> **Breaking release.** 3.0.0 只支持 finlight API v3。为 2.x 编写的代码不能直接运行。
> 如需继续使用 2.x（API v2），请固定 `finlight-client<3`。参见[从 2.x 迁移](#从-2x-迁移)。

[finlight](https://finlight.me) 新闻 API 的 Python 客户端：通过 REST 搜索和查询金融新闻、公司和来源，
通过 WebSocket 实时接收文章，并验证 Webhook。

## 版本

| SDK version | API version | Status |
|---|---|---|
| 3.x | v3（REST `/v3`、WebSocket `payloadVersion` 3、v3 Webhook） | 当前版本 |
| 2.x | v2 | 不再发布新版本 |

SDK 版本与 API 版本相互独立。支持 API v3 的 finlight SDK：TypeScript 4.x、Python 3.x、PHP 2.x、
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
    page = client.articles.search(query="ticker:NVDA", limit=10)
    for article in page.articles:
        print(article.title)
```

REST 调用是同步的，实时流是异步迭代器。参数使用 snake_case，每个参数对应 API 中唯一的一个键
（`from_` 即 `from`）。只有你传入的参数才会被发送。

## 搜索文章

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

`search_all` 会自动翻页。调用时请求内容即被固定，之后的页面只追加 cursor。
由于每一页都会消耗配额，它在 `max_pages` 页（默认 10）后停止。

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

用相同参数加上 `cursor=results.next_cursor` 再调用一次 `search_all` 即可继续。结果只能遍历一次。
未知参数会抛出 `TypeError`；形式错误（例如 `limit=0` 或 `languages=[]`）会在发送前抛出
`FinlightValidationError`。词表取值不在本地检查，因此服务器新增的取值无需更新 SDK 即可使用。

`source_types` 和 `exclude_source_types` 按来源类型筛选（`SourceType.ALL`，例如 `SourceType.NEWSWIRE`）。
未分类来源的文章不会匹配 `source_types`，在 `exclude_source_types` 下会保留。两者只会缩小你已能获取的来源范围。
`stream()` 和 `raw_stream()` 同样支持这两个参数。

## 查询文章、公司和来源

```python
from finlight_client import cache_info

article = client.articles.get("EU8JwpsZ8iJehuyPZjMqRz", include=["content"])
article = client.articles.get_by_link("https://www.reuters.com/...")

companies = client.companies.search("NVDA", mic="XNAS")   # at most 10, no pages
companies = client.companies.get_many([4821, 1001])
company = client.companies.get(4821)                      # the SDK keeps no cache
info = cache_info(company)                                # etag, cache_control
again = client.companies.get(4821, if_none_match=info.etag)  # None on 304 (not modified)

sources = client.sources.list()
```

- 查不到时抛出 `NotFoundError`，绝不会返回空结果。
- 在文章 id 上线前入库的文章只能通过链接查询。
- 公司查询需要 `entityAccess` 权限（否则抛出 `ForbiddenError`）。
- 查询接口与文章使用同一月度配额和突发限制。`companies.search`、`companies.get_many`、`companies.get` 和
  `sources.list` 每次调用消耗 1 个额度（`get_many` 按调用计，不按公司计）。304 响应（ETag 重新验证）和错误也消耗 1 个额度。
- SDK 不缓存公司记录，每次调用都会请求服务器。想节省额度，请自行保存记录，并在 Cache-Control 的
  `max-age` 内不再调用（重要的公司字段已随每篇文章提供）。`cache_info(record)` 提供 `etag` 和 `cache_control`。
  将 ETag 作为 `if_none_match=...` 传回即可重新验证：304 响应返回 `None`。这样省下的是下载，不是额度。
  不传 `if_none_match` 时不会发送 `If-None-Match`。
- `companies.search`、`companies.get_many` 和 `sources.list` 返回带 `skipped` 属性的列表；搜索页的
  `ArticlePage.skipped` 同理。无法读取的条目会放在那里。

## 缺失、null 与空值

有些键取决于你的套餐或 `include`，最多有三种状态：

| 状态 | 含义 | 判断方式 |
|---|---|---|
| 缺失 | 未请求、无权限或 raw 流 | `article.content_present` 为 `False` |
| `None` | 已请求且有权限，但没有值 | `content_present` 为 `True` 且 `content is None` |
| 有值 | 值本身 | `content` 有内容 |

- `content` 和 `sentiment` 有全部三种状态：使用 `content_present` 和 `sentiment_present`。
- `companies` 和 `events` 缺失时为 `None`，文章已打标签但没有结果时为 `[]`。请使用 `companies_present` 和
  `events_present`。`[]` 绝不表示"无权限"。
- 只有当 `companies` 在同一响应中时，`events[].company_ids` 才不为 `None`。
- 没有 `fullArticleAccess` 时 `Source.has_content` 为 `None`：表示未知，而不是"没有正文"。
- 时间戳保留发送时的字符串（`published_at`）。`published_at_time` 等 `*_time` 属性会严格解析，
  无法解析时返回 `None`。
- 新版服务器返回的未知键会被忽略。`finlight_client.raw_json(article)` 可取得原始 JSON；
  `to_wire(model)` 将模型写回 JSON，缺失的键保持缺失。
- 词表取值始终是普通字符串，可与 `finlight_client` 中的常量比较（`EventType.MNA`、`CompanyRole.ACQUIRER` 等）。
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
        on_reconnect=lambda info: print("reconnected", info.reason, info.last_seen_at),
    ) as stream:
        async for event in stream:
            print(event.kind, event.data.title if event.data else event.event)

asyncio.run(main())
```

- `event.kind` 为 `created`、`updated` 或 `other`（本 SDK 尚不认识的事件）。
- `client.raw_stream(query=..., sources=..., exclude_sources=..., source_types=..., exclude_source_types=...,
  language=..., include_updates=...)`
  推送尚未增强处理的文章：没有 `include`，也没有 content、sentiment、companies 或 events。
- Hook 可以是普通函数或 `async def`：`on_admitted(AdmittedInfo)`；除第一次外每次新连接后的
  `on_reconnect(ReconnectInfo)`；不会结束流的问题交给 `on_error(FinlightError)`；以及
  `on_quota_wait(QuotaWaitInfo)`。Hook 中抛出的错误会被记录，绝不会中断流。
- 流每 25 秒发送一次 ping，60 秒未收到 pong 时重新连接，115 分钟后建立新连接。
  每次重连后都会发送相同的订阅并丢弃重复的推送。
- 它从不自动补数据。`ReconnectInfo.last_seen_at` 是你看到的最新 `availableAt`（raw 为 `firstSeenAt`）。
  可用 `articles.search_all(from_=info.last_seen_at, order_by="availableAt")` 补齐缺口
  （raw 用 `order_by="firstSeenAt"`）。
- 终止性问题会以错误结束循环：无效密钥（`UnauthorizedError`）、无 WebSocket 权限（`ForbiddenError`）、
  订阅被拒（`ValidationFailedError`），以及被其他连接接管时的 `PreemptedError`。其他问题会自动重连并交给
  `on_error`。
- 每月 WebSocket 配额用尽时（连接被拒绝，或原因为 `quota_exceeded` 的抢占），流不会结束：它每小时重试一次，
  直到配额恢复。每次等待都会记录一条警告并调用 `on_quota_wait`。设置 `quota_reconnect=False` 可改为以错误
  结束流；`quota_reconnect_interval` 可修改间隔。
- 离开 `async with` 代码块即关闭连接。取消操作永远不会被吞掉。

需要了解的限制：

- 套餐的连接数上限由 enriched、raw 以及旧版 SDK 的连接共同占用。达到上限时新连接会被拒绝，
  SDK 会在 60 秒后重试。给 `stream()` 或 `raw_stream()` 传入 `takeover=True` 可改为替换最旧的连接。
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
- 时间戳必须在 `DEFAULT_WEBHOOK_TOLERANCE`（300 秒）之内，前后两个方向都适用。
- `WebhookVerificationError.reason` 说明原因，例如 `signature_mismatch` 或 `timestamp_outside_tolerance`。
  传入已解析的请求体而不是原始请求体会以 `invalid_raw_body` 失败。
- 控制台发送的测试 Webhook 的 `result.is_test` 为 true，它不受套餐权限裁剪。
- 永远不要返回 410：它会立即停用该 Webhook。连续 10 次非 2xx 响应也会将其停用。

获取原始请求体：

| 框架 | 原始请求体 |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

## 错误与重试

所有错误都继承自 `FinlightError`，并带有 `kind`：`api`、`validation`、`network`、`timeout`、`decode`、
`webhook_verification` 或 `preempted`。

| 错误 | 场景 |
|---|---|
| `FinlightApiError` | API 返回了错误：REST、被拒绝的流连接或流错误。包含 `status`、`code`、`type`、`title`、`detail`、`request_id`、`errors`（`FieldIssue`）、`api_kind`、`raw`。子类：`ValidationFailedError`、`CursorInvalidError`、`CursorMismatchError`、`UnauthorizedError`、`ForbiddenError`、`NotFoundError`、`RateLimitedError`、`InternalServerError`。其他情况的 `api_kind` 为 `other`。 |
| `RateLimitedError` | `limit_type` 为 `monthly`、`burst`、`unknown` 或更新的取值；`retry_after` 以秒为单位。 |
| `FinlightValidationError` | 请求在本地被拒绝（也是 `ValueError`）；`param` 指出对应的键。 |
| `FinlightNetworkError`、`FinlightTimeoutError` | 网络故障或超时。原始错误位于 `__cause__`。 |
| `FinlightDecodeError` | 响应无法读取（`path`、`raw`）。 |
| `WebhookVerificationError` | Webhook 验证失败（`reason`）。 |
| `PreemptedError` | 流被其他连接接管（`reason`、`new_lease_id`）。设置 `quota_reconnect=False` 时，配额用尽也会抛出。 |

重试：5xx 响应、网络错误和超时最多重试 3 次，等待时间逐次增加，搜索请求也不例外。
400、401、403、404 以及按月配额的 429 永不重试：按月配额的 429 会立即报错，`search_all` 中也是如此；
只有流会等待配额恢复（见上文）。突发（burst）429 会精确等待 `Retry-After` 秒（没有该请求头时为 10 秒）
后再试一次；默认开启，不计入 `max_retries`，设置 `retry_on_burst="off"` 可关闭。每次调用都发送自己的
`X-Request-Id`，重试时保持不变。按 Ctrl+C 会立即中止 REST 调用且不重试；取消任务即可停止流。

## 配置

```python
client = FinlightClient(
    api_key="YOUR_API_KEY",
    base_url="https://api.finlight.me",   # a trailing slash is fine
    wss_url="wss://wss.finlight.me",      # raw streams use <wss_url>/raw
    timeout=30.0,                         # seconds per attempt
)
```

所有键都可以作为关键字参数或通过 `FinlightConfig`（`config=`）设置。时间单位均为秒。

| 键 | 默认值 | 含义 |
|---|---|---|
| `api_key` | 必填 | API 密钥，不能为空 |
| `base_url` | `https://api.finlight.me` | REST 基础 URL |
| `wss_url` | `wss://wss.finlight.me` | WebSocket URL，raw 位于 `/raw` |
| `timeout` | 30 | 每次 REST 尝试 |
| `total_timeout` | 无 | 每次调用的上限，含重试和 burst 等待 |
| `max_retries` | 3 | 5xx、网络错误和超时的重试次数 |
| `retry_base_delay`、`retry_max_delay` | 0.5、8 | 重试之间逐渐增加的等待 |
| `retry_on_burst` | `"once"` | `"off"` 关闭 burst 重试 |
| `burst_wait` | 10 | 缺少 `Retry-After` 时的 burst 等待 |
| `max_pages` | 10 | `search_all` 的页数上限 |
| `max_response_bytes` | 32 MiB | REST 响应的大小上限 |
| `ping_interval` | 25 | 流的 ping 间隔 |
| `watchdog_timeout` | 60 | 超过该时间未收到 pong 即重连 |
| `rotation_interval` | 6900（115 分钟） | 在 2 小时上限前建立新连接 |
| `reconnect_base_delay`、`reconnect_max_delay` | 1、30 | 重连之间逐渐增加的等待 |
| `long_backoff` | 60 | 因连接数上限或 429 被拒后的等待 |
| `quota_reconnect` | `True` | 等待每月 WebSocket 配额而不是结束 |
| `quota_reconnect_interval` | 3600 | 配额重试之间的等待 |
| `search_failed_threshold` | 5 | 连续多少次 `SEARCH_FAILED` 后调用 `on_error` |
| `dedupe_cache_size` | 1000 | 每个流记住的推送数 |
| `max_message_bytes` | 32 MiB | 流消息的大小上限 |
| `connect_timeout` | 30 | WebSocket 握手 |
| `session` | 无 | 你自己的 `requests.Session` |
| `websocket_options`、`websocket_connect` | 无 | `websockets.connect` 的选项，或你自己的 WebSocket 传输 |
| `clock` | 系统时钟 | 流计时器的时间来源（用于测试） |

使用自己的 `requests.Session` 时，其超时、代理和适配器生效；请不要添加重试适配器，因为每次尝试都会消耗配额。
SDK 永远不会关闭不是它创建的 session。

## 日志

SDK 通过标准 `logging` 模块以 `finlight_client` 名称记录日志。未做设置时不输出任何内容。警告涉及被跳过的条目、
重连和配额等待。API 密钥、Webhook 密钥、签名和完整的请求体绝不会出现在日志或错误信息中，`websockets` 库的
调试输出（会显示请求头）也被屏蔽。SDK 不会修改全局日志设置，也不会安装信号处理器。

```python
import logging

logging.getLogger("finlight_client").setLevel(logging.INFO)
```

## 数据说明

- 旧文章的 `published_at` 可能是 `"1970-01-01T00:00:00.000Z"`，按原样提供。
- 空文本以 `None` 表示（`summary`、`content`）。
- 在角色功能上线前打标签的文章，`role` 和 `relevance` 为 `None`，`events` 为 `[]`。
- 在 id 功能上线前入库的文章，`articles.get(id)` 返回 404。请使用 `get_by_link`。
- 旧文章的 `available_at` 为 `None`，raw 流中始终为 `None`。
- 来源未分类时，`source.type` 和 `Source.type` 为 `None`。来源类型出现之前索引的文章也为 `None`。
  来源重新分类后，旧文章保留原来的类型。

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

将 Webhook 切换到 v3 的四个步骤：

1. 部署本 SDK。
2. 对 `WrongPayloadVersion` 返回 2xx 并保留其 `raw` JSON。
3. 在控制台将 Webhook 切换为 `payloadVersion` 3。
4. 等待约 2 小时：切换前排队的重试仍会以旧格式到达。

不要在同一个密钥上同时运行 2.x 和 3.x 的流：它们共用连接数上限。

## 开发

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`conformance/` 是契约套件的副本，附带 `CONTRACT_VERSION` 和 sha256 `MANIFEST`；`CONFORMANCE.md` 列出每个用例
对应的测试。在线测试只针对 dev 环境运行，需要 `FINLIGHT_API_KEY`、`FINLIGHT_BASE_URL` 和 `FINLIGHT_WSS_URL`：
`pytest tests/live -m live --force-enable-socket`。

## 许可证

MIT
