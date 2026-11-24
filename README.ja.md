# finlight-client (Python)

*[English](README.md) | [简体中文](README.zh-CN.md) | 日本語 | [한국어](README.ko.md)*

> この文書は [README.md](README.md) の翻訳です。内容が異なる場合は英語版が優先されます。

> **互換性のない新バージョン。** 3.0.0 は finlight API v3 のみに対応します。2.x 向けのコードはそのままでは
> 動きません。2.x（API v2）を使い続ける場合は `finlight-client<3` に固定してください。
> [2.x からの移行](#2x-からの移行) を参照してください。

[finlight](https://finlight.me) ニュース API の Python クライアントです。REST で金融ニュース、企業、ソースを
検索・参照し、WebSocket で記事をリアルタイムに受信し、Webhook を検証できます。

## バージョン

| SDK バージョン | API バージョン | 状態 |
|---|---|---|
| 3.x | v3（REST `/v3`、WebSocket `payloadVersion` 3、v3 Webhook） | 現行 |
| 2.x | v2 | 今後のリリースなし |

SDK と API のバージョンは独立しています。API v3 に対応する他の finlight SDK：TypeScript 4.x、PHP 2.x、
Go モジュール `/v2`、.NET 2.x、Java 1.x、Ruby 1.x、Rust 0.2。

## 動作要件

- Python 3.10 以上
- `requests` 2.31 以上、`pydantic` 2.7 以上、`websockets` 15.0 以上

## インストール

```bash
pip install "finlight-client>=3,<4"
```

## クイックスタート

```python
from finlight_client import FinlightClient

with FinlightClient(api_key="YOUR_API_KEY") as client:
    page = client.articles.search(query="ticker:NVDA", limit=10, include=["companies"])
    for article in page.articles:
        print(article.published_at, article.title)
```

REST 呼び出しは同期、ストリームは非同期イテレーターです。引数は snake_case で、それぞれ API の
キー 1 つに対応します（`from_` は `from`）。渡した引数だけが送信されます。

## 記事の検索

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

`search_all` はページを自動でたどります。呼び出した時点でリクエスト内容が固定され、以降のページでは
cursor だけが追加されます。各ページがクォータを消費するため、`max_pages` ページ（既定値 10）で止まります。

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

結果は 1 回だけ反復できます。未知の引数は `TypeError` になり、形式の誤り（例：`limit=0`、
`languages=[]`）は送信前に `FinlightValidationError` になります。語彙の値はローカルで検査しないため、
サーバー側で追加された値も SDK を更新せずに使えます。

## 記事・企業・ソースの参照

```python
article = client.articles.get("EU8JwpsZ8iJehuyPZjMqRz", include=["content"])
article = client.articles.get_by_link("https://www.reuters.com/...")

companies = client.companies.search("NVDA", mic="XNAS")   # at most 10, no pages
companies = client.companies.get_many([4821, 1001])
company = client.companies.get(4821)                      # revalidated with its ETag next time

sources = client.sources.list()
```

見つからない場合は `NotFoundError` になります。企業の参照には `entityAccess` 権限が必要です
（ない場合は `ForbiddenError`）。

### 記事の読み方

- `content` と `sentiment` には 3 つの状態があります。キーが送られていない（未リクエストまたは権限なし）
  場合 `article.content_present` は false です。`content_present` が true で `article.content is None` なら
  「テキストなし」です。`sentiment_present` も同様です。
- `companies` と `events` は送られていない場合 `None`、タグ付け済みで該当なしの場合 `[]` です。
  `companies_present` と `events_present` で確認してください。
- `events[].company_ids` は同じ応答に `companies` がある場合だけ送られます。
- タイムスタンプは送られた文字列のまま保持されます（`published_at`）。`published_at_time` などの
  `*_time` プロパティは厳密に解析し、読めない値には `None` を返します。
- 新しいサーバーからの未知のキーは無視されます。`finlight_client.raw_json(article)` で元の JSON を取得できます。
- 語彙の値は通常の文字列です。`finlight_client` の定数（`EventType.MNA`、`Role.ACQUIRER` など）と
  比較してください。未知の値は送られたまま保持されます。

## リアルタイムストリーム

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

- `event.kind` は `created`、`updated`、`other`（この SDK がまだ知らないイベント）のいずれかです。
- `client.raw_stream(query=..., sources=..., exclude_sources=..., language=..., include_updates=...)`
  はエンリッチ前の記事を配信します。`include` はなく、content、sentiment、companies、events もありません。
- ストリームは 25 秒ごとに ping を送り、60 秒 pong がなければ再接続し、115 分後に新しい接続を開きます。
  再接続のたびに同じ購読を送り、重複した配信を捨てます。
- 自動でのバックフィルは行いません。`on_reconnect(last_seen, reason)` は最後に見た `availableAt`
  （raw では `firstSeenAt`）を受け取ります。欠けた分は `articles.search_all(from_=last_seen,
  order_by="availableAt")`（raw では `order_by="firstSeenAt"`）で補ってください。
- 致命的な問題はエラーでループを終了します：無効なキー（`UnauthorizedError`）、WebSocket の権限なしや
  クォータ切れ（`ForbiddenError`）、購読の拒否（`ValidationFailedError`）、別の接続による乗っ取りや
  クォータ切れの `PreemptedError`。その他の問題は再接続し、`on_error` に通知されます。
- `async with` ブロックを抜けると接続が閉じます。キャンセルが握りつぶされることはありません。

知っておくべき制限：

- プランの接続数上限は enriched、raw、旧 SDK の接続で共有されます。上限に達しているときの新しい接続は
  拒否され、SDK は 60 秒後に再試行します。クライアントに `takeover=True` を渡すと、代わりに最も古い
  接続を置き換えます。
- 購読直後に、条件に合う最新の記事が 1 件送られます（再接続のたびにも）。古い記事のこともあります。
- 32,000 バイトを超えるライブフレームはサーバーが通知なしに破棄します。長い記事で
  `include=["content"]` を使うと起こり得ます。`articles.get` で取得してください。
- `connection.admitted` はサーバーが購読を検査する前に届きます。受け入れられたという意味ではありません。
- WebSocket 接続は `websockets` ライブラリと同様に環境変数のプロキシ設定（`HTTPS_PROXY`、`ALL_PROXY`）を
  使います。無効にするには `websocket_options={"proxy": None}` を渡してください。

## Webhook

finlight はすべての Webhook に署名します。何かを解析する前に、**生の**リクエストボディで検証してください：

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

- `headers` には任意のヘッダーのマッピングやペアのリストを渡せます（Flask、Django、Starlette、
  `http.server`、WSGI environ）。名前の大文字・小文字は区別しません。
  `construct_event_from_values(raw_body, signature, timestamp, secret)` は 2 つのヘッダー値を直接受け取り、
  `verify_signature` は検証だけを行います。
- タイムスタンプは前後どちらの方向にも 300 秒（`tolerance`）以内である必要があります。
- ダッシュボードのテスト Webhook では `result.is_test` が true になります。プランによる制限はかかりません。
- 410 は絶対に返さないでください。Webhook が即座に無効化されます。2xx 以外が 10 回続いても無効化されます。

生のボディの取得方法：

| フレームワーク | 生のボディ |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

Webhook を v3 に切り替える手順：まずこの SDK をデプロイし、`WrongPayloadVersion` には 2xx を返して
元の JSON を保存します。次にダッシュボードで Webhook を `payloadVersion` 3 に切り替えます。切り替え前に
キューに入った再送は古い形式のまま届くため、その後約 2 時間待ってください。

## エラーと再試行

すべてのエラーは `FinlightError` を継承し、`kind` 文字列を持ちます。

| エラー | 発生条件 |
|---|---|
| `FinlightApiError` | API がエラーを返した。`status`、`code`、`title`、`detail`、`request_id`、`errors`、`raw`、`docs_url` を持つ。code ごとのサブクラス：`ValidationFailedError`、`CursorInvalidError`、`CursorMismatchError`、`UnauthorizedError`、`ForbiddenError`、`NotFoundError`、`RateLimitedError`、`InternalServerError`。未知の code は基底クラスのまま。 |
| `RateLimitedError` | `limit_type` は `monthly`、`burst`、またはより新しい値。`retry_after` は秒。 |
| `FinlightValidationError` | リクエストがローカルで拒否された（`ValueError` の一種）。 |
| `FinlightNetworkError`、`FinlightTimeoutError` | ネットワーク障害またはタイムアウト。元のエラーは `__cause__`。 |
| `FinlightDecodeError` | 単一の応答を読み取れなかった。 |
| `WebhookVerificationError` | Webhook の検証に失敗した（`reason`）。 |
| `PreemptedError` | ストリームが乗っ取られたかクォータが切れた（`reason`、`new_lease_id`）。 |

再試行：5xx 応答、ネットワークエラー、タイムアウトは待ち時間を延ばしながら最大 3 回再試行します
（検索も含む）。400、401、403、404 と月間クォータの 429 は再試行しません。バースト 429 は
`Retry-After` 秒（ヘッダーがなければ 10 秒）待ってからもう一度だけ試します。`retry_on_burst="off"` で
無効にできます。呼び出しごとに専用の `X-Request-Id` を送り、再試行でも同じ値を使います。
Ctrl+C で呼び出しを中断でき、待機はすぐに終わり、再試行もされません。

## 設定

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
    session=None,                         # your own requests.Session
)
```

時間はすべて秒です。`FinlightConfig` を作って `config=` で渡すこともできます。独自の
`requests.Session` を使う場合は、そのタイムアウト、プロキシ、アダプターが適用されます。試行ごとに
クォータを消費するため、再試行アダプターは追加しないでください。SDK は自分で作っていない session を
閉じることはありません。`websocket_options` は `websockets.connect` に渡されます。SDK は
`finlight_client` ロガーでログを出し、既定では何も出力しません。

## データに関する注意

- 古い記事では `published_at` が `"1970-01-01T00:00:00.000Z"` のことがあります。送られたまま提供されます。
- 空のテキストは `None` として届きます（`summary`、`content`）。
- ロール機能より前にタグ付けされた記事は、`role` と `relevance` が `None`、`events` が `[]` です。
- id 導入前に登録された記事では `articles.get(id)` が 404 になります。`get_by_link` を使ってください。
- 古い記事の `available_at` は `None`、raw ストリームでは常に `None` です。

## 2.x からの移行

完全なガイドは [docs.finlight.me](https://docs.finlight.me/migration/v2-to-v3) にあります。概要：

| 2.x | 3.x |
|---|---|
| `FinlightApi(ApiConfig(api_key=...))` | `FinlightClient(api_key=...)` |
| `articles.fetch_articles(GetArticlesParams(...))` | `articles.search(...)`、`articles.search_all(...)` |
| `page` / `pageSize` | `limit` / `cursor` |
| `includeContent`、`includeEntities` | `include=["content", "companies", "events"]` |
| `order="DESC"` | `order="desc"` |
| `publishDate`、`createdAt`、`revisedDate` | `published_at`、`first_seen_at`、`revised_at` |
| `images` | `media[].url` |
| `source`（文字列） | `source.domain` |
| `sentiment`、`confidence` | `sentiment.label`、`sentiment.confidence` |
| `api.websocket.connect(...)` | `async for event in client.stream(...)` |
| `api.raw_websocket` | `client.raw_stream(...)` |
| Webhook の `isUpdate` | `event.event == "article.updated"` |
| Webhook のボディ | `event.data` と重複排除用の `event.event_id` |

同じキーで 2.x と 3.x のストリームを並行して動かさないでください。接続数の上限を共有します。

## 開発

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`CONFORMANCE.md` は契約キットの各ケースと対応するテストの一覧です。ライブテストは dev 環境に対してのみ
実行し、`FINLIGHT_API_KEY`、`FINLIGHT_BASE_URL`、`FINLIGHT_WSS_URL` が必要です：
`pytest tests/live -m live --force-enable-socket`。

## ライセンス

MIT
