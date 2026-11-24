# finlight client for Python

*[English](README.md) | [简体中文](README.zh-CN.md) | 日本語 | [한국어](README.ko.md)*

> この文書は [README.md](README.md) の翻訳で、更新が遅れることがあります。内容が異なる場合は英語版が優先されます。

> **Breaking release.** 3.0.0 は finlight API v3 のみに対応します。2.x 向けのコードはそのままでは動きません。
> 2.x（API v2）を使い続ける場合は `finlight-client<3` に固定してください。
> [2.x からの移行](#2x-からの移行) を参照してください。

[finlight](https://finlight.me) ニュース API の Python クライアントです。REST で金融ニュース、企業、ソースを
検索・参照し、WebSocket で記事をリアルタイムに受信し、Webhook を検証できます。

## バージョン

| SDK version | API version | Status |
|---|---|---|
| 3.x | v3（REST `/v3`、WebSocket `payloadVersion` 3、v3 Webhook） | 現行 |
| 2.x | v2 | 今後のリリースなし |

SDK と API のバージョンは独立しています。API v3 に対応する finlight SDK：TypeScript 4.x、Python 3.x、
PHP 2.x、Go モジュール `/v2`、.NET 2.x、Java 1.x、Ruby 1.x、Rust 0.2。

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
    page = client.articles.search(query="ticker:NVDA", limit=10)
    for article in page.articles:
        print(article.title)
```

REST 呼び出しは同期、ストリームは非同期イテレーターです。引数は snake_case で、それぞれ API の
キー 1 つに対応します（`from_` は `from`）。渡した引数だけが送信されます。

## 記事の検索

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

`search_all` はページを自動でたどります。呼び出した時点でリクエスト内容が固定され、以降のページでは
cursor だけが追加されます。各ページがクォータを消費するため、`max_pages` ページ（既定値 10）で止まります。

```python
results = client.articles.search_all(query="ticker:AAPL", limit=100, max_pages=5)
for article in results:            # or: for page in results.pages()
    print(article.id, article.title)
if results.truncated:
    print("continue with cursor", results.next_cursor)
```

続きを取得するには、同じ引数に `cursor=results.next_cursor` を加えて `search_all` を再度呼び出します。
結果は 1 回だけ反復できます。未知の引数は `TypeError` になり、形式の誤り（例：`limit=0`、`languages=[]`）は
送信前に `FinlightValidationError` になります。語彙の値はローカルで検査しないため、サーバー側で追加された値も
SDK を更新せずに使えます。

`source_types` と `exclude_source_types` はソースの種類で絞り込みます（`SourceType.ALL`、例：
`SourceType.NEWSWIRE`）。種類が未分類のソースの記事は `source_types` に一致せず、`exclude_source_types` では
残ります。どちらも受け取れるソースを狭めるだけです。`stream()` と `raw_stream()` でも使えます。

## 記事・企業・ソースの参照

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

- 見つからない場合は `NotFoundError` になり、空の結果にはなりません。
- 記事 id の導入前に登録された記事はリンクでのみ取得できます。
- 企業の参照には `entityAccess` 権限が必要です（ない場合は `ForbiddenError`）。
- 参照系の呼び出しは記事と同じ月間クォータとバースト制限を使います。`companies.search`、`companies.get_many`、
  `companies.get`、`sources.list` は呼び出しごとに 1 クレジットかかります（`get_many` は企業ごとではなく 1 回の
  呼び出しごとに 1）。304 応答（ETag による再検証）とエラーも 1 クレジットかかります。
- SDK は企業レコードをキャッシュしません。呼び出しは毎回サーバーに届きます。クレジットを節約するには、
  レコードを自分で保持し、Cache-Control の `max-age` の間は再度呼び出さないでください（重要な企業フィールドは
  各記事にすでに含まれています）。`cache_info(record)` は `etag` と `cache_control` を返します。ETag を
  `if_none_match=...` として渡すと再検証でき、304 応答では `None` が返ります。節約できるのはダウンロードで、
  クレジットではありません。`if_none_match` がなければ `If-None-Match` は送られません。
- `companies.search`、`companies.get_many`、`sources.list` は `skipped` 属性付きのリストを返します。
  検索ページの `ArticlePage.skipped` も同様で、読み取れなかったエントリが入ります。

## 欠落、null、空

一部のキーはプランや `include` によって変わり、最大 3 つの状態があります：

| 状態 | 意味 | 確認方法 |
|---|---|---|
| 欠落 | 未リクエスト、権限なし、または raw ストリーム | `article.content_present` が `False` |
| `None` | リクエスト済みで権限もあるが値がない | `content_present` が `True` かつ `content is None` |
| 値 | 値そのもの | `content` に値がある |

- `content` と `sentiment` は 3 つの状態すべてを持ちます。`content_present` と `sentiment_present` を使います。
- `companies` と `events` は欠落時に `None`、タグ付け済みで該当なしの場合に `[]` です。`companies_present` と
  `events_present` を使ってください。`[]` が「権限なし」を意味することはありません。
- `events[].company_ids` は同じ応答に `companies` がある場合を除き `None` です。
- `fullArticleAccess` がない場合 `Source.has_content` は `None` です。「本文なし」ではなく「不明」の意味です。
- タイムスタンプは送られた文字列のまま保持されます（`published_at`）。`published_at_time` などの `*_time`
  プロパティは厳密に解析し、読めない値には `None` を返します。
- 新しいサーバーからの未知のキーは無視されます。`finlight_client.raw_json(article)` で元の JSON を取得でき、
  `to_wire(model)` は欠落したキーを省いたままモデルを書き戻します。
- 語彙の値は通常の文字列です。`finlight_client` の定数（`EventType.MNA`、`CompanyRole.ACQUIRER` など）と
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
        on_reconnect=lambda info: print("reconnected", info.reason, info.last_seen_at),
    ) as stream:
        async for event in stream:
            print(event.kind, event.data.title if event.data else event.event)

asyncio.run(main())
```

- `event.kind` は `created`、`updated`、`other`（この SDK がまだ知らないイベント）のいずれかです。
- `client.raw_stream(query=..., sources=..., exclude_sources=..., source_types=..., exclude_source_types=...,
  language=..., include_updates=...)`
  はエンリッチ前の記事を配信します。`include` はなく、content、sentiment、companies、events もありません。
- フックは通常の関数でも `async def` でも構いません：`on_admitted(AdmittedInfo)`、最初を除く新しい接続の
  たびの `on_reconnect(ReconnectInfo)`、ストリームを終わらせない問題の `on_error(FinlightError)`、そして
  `on_quota_wait(QuotaWaitInfo)`。フック内で発生したエラーはログに出るだけで、ストリームは止まりません。
- ストリームは 25 秒ごとに ping を送り、60 秒 pong がなければ再接続し、115 分後に新しい接続を開きます。
  再接続のたびに同じ購読を送り、重複した配信を捨てます。
- 自動でのバックフィルは行いません。`ReconnectInfo.last_seen_at` は最後に見た `availableAt`（raw では
  `firstSeenAt`）です。欠けた分は `articles.search_all(from_=info.last_seen_at, order_by="availableAt")`
  （raw では `order_by="firstSeenAt"`）で補ってください。
- 致命的な問題はエラーでループを終了します：無効なキー（`UnauthorizedError`）、WebSocket の権限なし
  （`ForbiddenError`）、購読の拒否（`ValidationFailedError`）、別の接続による乗っ取りの `PreemptedError`。
  その他の問題は再接続し、`on_error` に通知されます。
- 月間の WebSocket クォータを使い切った場合（接続の拒否、または理由が `quota_exceeded` のプリエンプト）、
  ストリームは終了しません。クォータが戻るまで 1 時間ごとに再試行します。待機のたびに警告をログに出し、
  `on_quota_wait` を呼びます。`quota_reconnect=False` にするとエラーで終了します。間隔は
  `quota_reconnect_interval` で変更できます。
- `async with` ブロックを抜けると接続が閉じます。キャンセルが握りつぶされることはありません。

知っておくべき制限：

- プランの接続数上限は enriched、raw、旧 SDK の接続で共有されます。上限に達しているときの新しい接続は
  拒否され、SDK は 60 秒後に再試行します。`stream()` または `raw_stream()` に `takeover=True` を渡すと、
  代わりに最も古い接続を置き換えます。
- 購読直後に、条件に合う最新の記事が 1 件送られます（再接続のたびにも）。古い記事のこともあります。
- 32,000 バイトを超えるライブフレームはサーバーが通知なしに破棄します。長い記事で `include=["content"]` を
  使うと起こり得ます。`articles.get` で取得してください。
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
- タイムスタンプは前後どちらの方向にも `DEFAULT_WEBHOOK_TOLERANCE`（300 秒）以内である必要があります。
- `WebhookVerificationError.reason` が理由を示します（例：`signature_mismatch`、`timestamp_outside_tolerance`）。
  生のボディではなく解析済みのボディを渡すと `invalid_raw_body` で失敗します。
- ダッシュボードのテスト Webhook では `result.is_test` が true になります。プランによる制限はかかりません。
- 410 は絶対に返さないでください。Webhook が即座に無効化されます。2xx 以外が 10 回続いても無効化されます。

生のボディの取得方法：

| フレームワーク | 生のボディ |
|---|---|
| Flask | `request.get_data()` |
| Django | `request.body` |
| FastAPI / Starlette | `await request.body()` |
| `http.server` | `self.rfile.read(int(self.headers["Content-Length"]))` |

## エラーと再試行

すべてのエラーは `FinlightError` を継承し、`kind`（`api`、`validation`、`network`、`timeout`、`decode`、
`webhook_verification`、`preempted`）を持ちます。

| エラー | 発生条件 |
|---|---|
| `FinlightApiError` | API がエラーを返した：REST、拒否されたストリーム接続、ストリームのエラー。`status`、`code`、`type`、`title`、`detail`、`request_id`、`errors`（`FieldIssue`）、`api_kind`、`raw` を持つ。サブクラス：`ValidationFailedError`、`CursorInvalidError`、`CursorMismatchError`、`UnauthorizedError`、`ForbiddenError`、`NotFoundError`、`RateLimitedError`、`InternalServerError`。それ以外は `api_kind` が `other`。 |
| `RateLimitedError` | `limit_type` は `monthly`、`burst`、`unknown`、またはより新しい値。`retry_after` は秒。 |
| `FinlightValidationError` | リクエストがローカルで拒否された（`ValueError` でもある）。`param` がキーを示す。 |
| `FinlightNetworkError`、`FinlightTimeoutError` | ネットワーク障害またはタイムアウト。元のエラーは `__cause__`。 |
| `FinlightDecodeError` | 応答を読み取れなかった（`path`、`raw`）。 |
| `WebhookVerificationError` | Webhook の検証に失敗した（`reason`）。 |
| `PreemptedError` | 別の接続がストリームを引き継いだ（`reason`、`new_lease_id`）。`quota_reconnect=False` のときはクォータ切れでも発生。 |

再試行：5xx 応答、ネットワークエラー、タイムアウトは待ち時間を延ばしながら最大 3 回再試行します（検索も含む）。
400、401、403、404 と月間クォータの 429 は再試行しません。月間クォータの 429 は `search_all` の中でも
すぐにエラーになり、クォータを待つのはストリームだけです（上記参照）。バースト 429 は `Retry-After` 秒
（ヘッダーがなければ 10 秒）ちょうど待ってからもう一度だけ試します。既定で有効で、`max_retries` には数えず、
`retry_on_burst="off"` で無効にできます。呼び出しごとに専用の `X-Request-Id` を送り、再試行でも同じ値を
使います。Ctrl+C で REST 呼び出しは再試行なしですぐに止まり、タスクをキャンセルするとストリームが止まります。

## 設定

```python
client = FinlightClient(
    api_key="YOUR_API_KEY",
    base_url="https://api.finlight.me",   # a trailing slash is fine
    wss_url="wss://wss.finlight.me",      # raw streams use <wss_url>/raw
    timeout=30.0,                         # seconds per attempt
)
```

すべてのキーはキーワード引数または `FinlightConfig`（`config=`）で設定できます。時間は秒です。

| キー | 既定値 | 意味 |
|---|---|---|
| `api_key` | 必須 | API キー（空は不可） |
| `base_url` | `https://api.finlight.me` | REST のベース URL |
| `wss_url` | `wss://wss.finlight.me` | WebSocket の URL、raw は `/raw` |
| `timeout` | 30 | REST の試行ごと |
| `total_timeout` | なし | 呼び出しごとの上限（再試行とバースト待機を含む） |
| `max_retries` | 3 | 5xx、ネットワークエラー、タイムアウトの再試行回数 |
| `retry_base_delay`、`retry_max_delay` | 0.5、8 | 再試行間の増えていく待ち時間 |
| `retry_on_burst` | `"once"` | `"off"` でバースト再試行を無効化 |
| `burst_wait` | 10 | `Retry-After` がないときのバースト待機 |
| `max_pages` | 10 | `search_all` のページ上限 |
| `max_response_bytes` | 32 MiB | REST 応答のサイズ上限 |
| `ping_interval` | 25 | ストリームの ping |
| `watchdog_timeout` | 60 | この時間 pong がなければ再接続 |
| `rotation_interval` | 6900（115 分） | 2 時間の上限前に新しい接続を開く |
| `reconnect_base_delay`、`reconnect_max_delay` | 1、30 | 再接続間の増えていく待ち時間 |
| `long_backoff` | 60 | 接続数上限や 429 で拒否された後の待機 |
| `quota_reconnect` | `True` | 終了せずに月間 WebSocket クォータを待つ |
| `quota_reconnect_interval` | 3600 | クォータ再試行の間隔 |
| `search_failed_threshold` | 5 | `on_error` までの連続 `SEARCH_FAILED` 回数 |
| `dedupe_cache_size` | 1000 | ストリームごとに記憶する配信数 |
| `max_message_bytes` | 32 MiB | ストリームメッセージのサイズ上限 |
| `connect_timeout` | 30 | WebSocket ハンドシェイク |
| `session` | なし | 独自の `requests.Session` |
| `websocket_options`、`websocket_connect` | なし | `websockets.connect` のオプション、または独自の WebSocket トランスポート |
| `clock` | システム時計 | ストリームのタイマーの時刻源（テスト用） |

独自の `requests.Session` を使う場合は、そのタイムアウト、プロキシ、アダプターが適用されます。試行ごとに
クォータを消費するため、再試行アダプターは追加しないでください。SDK は自分で作っていない session を閉じません。

## ログ

SDK は標準の `logging` モジュールで `finlight_client` という名前でログを出します。設定しなければ何も出力しません。
警告は読み飛ばしたエントリ、再接続、クォータ待機を扱います。API キー、Webhook シークレット、署名、ボディ全体が
ログやエラーメッセージに出ることはなく、ヘッダーを表示する `websockets` ライブラリのデバッグ出力も抑止されます。
SDK はグローバルなログ設定を変更せず、シグナルハンドラーも登録しません。

```python
import logging

logging.getLogger("finlight_client").setLevel(logging.INFO)
```

## データに関する注意

- 古い記事では `published_at` が `"1970-01-01T00:00:00.000Z"` のことがあります。送られたまま提供されます。
- 空のテキストは `None` として届きます（`summary`、`content`）。
- ロール機能より前にタグ付けされた記事は、`role` と `relevance` が `None`、`events` が `[]` です。
- id 導入前に登録された記事では `articles.get(id)` が 404 になります。`get_by_link` を使ってください。
- 古い記事の `available_at` は `None`、raw ストリームでは常に `None` です。
- `source.type` と `Source.type` は、ソースが未分類なら `None` です。ソースの種類が導入される前に索引された記事も
  `None` です。ソースが再分類されても、古い記事は以前の種類のままです。

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

Webhook を v3 に切り替える 4 つの手順：

1. この SDK をデプロイします。
2. `WrongPayloadVersion` には 2xx を返し、その `raw` JSON を保存します。
3. ダッシュボードで Webhook を `payloadVersion` 3 に切り替えます。
4. 約 2 時間待ちます。切り替え前にキューに入った再送は古い形式のまま届きます。

同じキーで 2.x と 3.x のストリームを並行して動かさないでください。接続数の上限を共有します。

## 開発

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                   # unit and conformance tests, no network
python scripts/sync_conformance.py --from <monorepo>/shared/contracts/api-v3
python scripts/check_conformance.py
```

`conformance/` は契約キットのコピーで、`CONTRACT_VERSION` と sha256 の `MANIFEST` を含みます。`CONFORMANCE.md`
は各ケースと対応するテストの一覧です。ライブテストは dev 環境に対してのみ実行し、`FINLIGHT_API_KEY`、
`FINLIGHT_BASE_URL`、`FINLIGHT_WSS_URL` が必要です：`pytest tests/live -m live --force-enable-socket`。

## ライセンス

MIT
