# Finlight Client – Python ライブラリ

*[English](README.md) | [简体中文](README.zh-CN.md) | 日本語 | [한국어](README.ko.md)*

[Finlight News API](https://finlight.me) を利用するための Python クライアントライブラリです。
Finlight は、センチメント分析、企業タグ付け、マーケットメタデータを付与したリアルタイムおよび過去の金融ニュース記事を提供します。本ライブラリにより、Python アプリケーションへの Finlight の組み込みが容易になります。

---

## ✨ 主な機能

- 日付パースとメタデータを備えた**構造化**ニュース記事の取得。
- **ティッカー**、**ニュースソース**、**言語**、**日付範囲**によるフィルタリング。
- **Enhanced** および **Raw WebSocket** による**リアルタイム**ニュース配信（自動再接続対応）。
- **Webhook 対応**。HMAC 署名検証とリプレイ攻撃対策を含みます。
- 高度な WebSocket 機能:
  - 指数バックオフによる再接続戦略
  - Ping/Pong キープアライブ機構
  - 先回りのコネクションローテーション（AWS の 2 時間制限の手前で実施）
  - 既存コネクションを置き換えるテイクオーバー
  - レート制限および管理者による切断のハンドリング
- `pydantic` と `dataclass` による厳密な型付けモデル。
- 軽量で開発者にやさしい設計。

---

## 📦 インストール

```bash
pip install finlight-client
```

---

## 🚀 クイックスタート

### REST API で記事を取得する

```python
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesParams

def main():
    # クライアントを初期化
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # クエリパラメータを作成
    params = GetArticlesParams(
        query="Nvidia",
        language="en",
        from_="2024-01-01",
        to="2024-12-31",
        includeContent=True
    )

    # 記事を取得
    response = client.articles.fetch_articles(params=params)

    # 結果を出力
    for article in response.articles:
        print(f"{article.publishDate} | {article.title}")

if __name__ == "__main__":
    main()
```

### リンクから記事を取得する

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

### WebSocket でリアルタイム記事を受信する

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print("📨 受信:", article.title)

async def main():
    # クライアントを初期化
    config = ApiConfig(api_key="your_api_key")
    client = FinlightApi(config)

    # WebSocket パラメータを作成
    payload = GetArticlesWebSocketParams(
        query="Nvidia",
        sources=["www.reuters.com"],
        language="en",
        extended=True,
    )

    # 接続して記事を受信
    await client.websocket.connect(
        request_payload=payload,
        on_article=on_article
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Raw WebSocket で未加工の記事を受信する

Raw WebSocket は AI エンリッチメント（センチメント、確信度、企業タグ付け）を行わないぶん、より高速に記事を配信します。`source:`、`title:`、`summary:` のフィールド単位フィルタに対応しています。

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig, RawWebSocketOptions
from finlight_client.models import GetRawArticlesWebSocketParams

def on_article(article):
    print("📨 受信:", article.title)

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

## ⚙️ 設定

### `ApiConfig`

API の基本設定:

| パラメータ    | 型           | 説明                       | デフォルト                |
| ------------- | ------------ | -------------------------- | ------------------------- |
| `api_key`     | `str`        | あなたの API キー          | **必須**                  |
| `base_url`    | `AnyHttpUrl` | REST API のベース URL      | `https://api.finlight.me` |
| `wss_url`     | `AnyHttpUrl` | WebSocket サーバーの URL   | `wss://wss.finlight.me`   |
| `timeout`     | `int`        | リクエストタイムアウト(ms) | `5000`                    |
| `retry_count` | `int`        | 失敗時のリトライ回数       | `3`                       |

### `FinlightApi` の WebSocket オプション

高度な WebSocket 設定（すべて任意）。フラットなキーワード引数でも、オプションオブジェクトでも指定できます:

```python
# フラットなキーワード引数を使う場合（Enhanced WebSocket のみ）
client = FinlightApi(config, websocket_takeover=True)

# オプションオブジェクトを使う場合（Enhanced / Raw 両方）
from finlight_client import WebSocketOptions, RawWebSocketOptions

client = FinlightApi(
    config,
    websocket_options=WebSocketOptions(takeover=True),
    raw_websocket_options=RawWebSocketOptions(takeover=True),
)
```

`WebSocketOptions` と `RawWebSocketOptions` は同じフィールドを受け付けます:

| フィールド               | 型         | 説明                                         | デフォルト     |
| ------------------------ | ---------- | -------------------------------------------- | -------------- |
| `ping_interval`          | `int`      | Ping 間隔（秒）                              | `25`           |
| `pong_timeout`           | `int`      | Pong タイムアウト（秒）                      | `60`           |
| `base_reconnect_delay`   | `float`    | 初回再接続までの遅延（秒）                   | `0.5`          |
| `max_reconnect_delay`    | `float`    | 再接続遅延の上限（秒）                       | `10.0`         |
| `connection_lifetime`    | `int`      | コネクションの寿命（秒）                     | `6900`（115 分）|
| `takeover`               | `bool`     | 既存コネクションをテイクオーバーする         | `False`        |
| `on_close`               | `Callable` | クローズイベントのコールバック `(code, reason)` | `None`      |

---

## 📚 API 概要

### `ArticleService.fetch_articles(params: GetArticlesParams) -> ArticleResponse`

柔軟なフィルタリングで記事を取得します:
- ブール演算子を使った高度なクエリ文字列に対応
- ISO 形式の日付文字列を `datetime` に自動変換
- ページサイズを指定できるページネーション（1〜1000）
- 全文と企業タグの取得は任意

### `ArticleService.fetch_article_by_link(params: GetArticleByLinkParams) -> Article`

URL から単一の記事を取得します:

- データベースに存在すればその記事を返します
- 全文と企業タグの取得は任意
- URL を指定して特定の記事を取り出す用途に適しています

### `SourcesService.get_sources() -> List[Source]`

利用可能なニュースソースを取得します:
- メタデータ付きのソース一覧を返します
- 全文の可否とデフォルトソースかどうかを示します
- ソースフィルタの構築に役立ちます

### `WebSocketClient.connect(request_payload, on_article)`

記事のライブ配信を購読します:
- 指数バックオフで自動的に再接続します
- レート制限や管理者操作を適切に処理します
- 接続維持のため 25 秒ごとにサーバーへ Ping を送信します
- AWS の 2 時間タイムアウトの手前でコネクションを先回りしてローテーションします
- テイクオーバーモードは任意

### `RawWebSocketClient.connect(request_payload, on_article)`

未加工記事のライブ配信を購読します（低遅延、AI エンリッチメントなし）:
- 再接続とキープアライブの挙動は Enhanced WebSocket と同じです
- `wss://wss.finlight.me/raw` に接続します
- `RawArticle` オブジェクトを返します（センチメント、確信度、企業情報は含みません）
- フィールド単位のクエリフィルタに対応: `source:`、`title:`、`summary:`

### `WebhookService.construct_event(raw_body, signature, endpoint_secret, timestamp?)`

Webhook イベントを安全に受信します:
- HMAC-SHA256 による署名検証
- リプレイ攻撃対策（許容範囲 5 分）
- 検証済みの `Article` オブジェクトを返します
- 不正なリクエストの場合は `WebhookVerificationError` を送出します

---

## 🧯 エラーハンドリング

- 不正な日付文字列は、内容の明確な Python の `ValueError` を送出します。
- REST および WebSocket の例外はログ出力のうえ処理されます。
- WebSocket には再接続、ウォッチドッグ、Ping/Pong の各機構が組み込まれています。

---

## 📖 その他の例

### 利用可能なニュースソースを取得する

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

### Webhook イベントを受信する（Flask）

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
        print(f"📨 新しい記事: {article.title}")
        return '', 200
    except WebhookVerificationError as e:
        print(f"❌ Webhook の検証に失敗: {e}")
        return '', 400

if __name__ == "__main__":
    app.run(port=3000)
```

### カスタム設定による高度な WebSocket の利用

```python
import asyncio
from finlight_client import FinlightApi, ApiConfig
from finlight_client.models import GetArticlesWebSocketParams

def on_article(article):
    print(f"📨 {article.title}")

def on_close(code, reason):
    print(f"🔌 コネクションを閉じました: {code} - {reason}")

async def main():
    config = ApiConfig(api_key="your_api_key")

    # 高度な WebSocket 設定
    client = FinlightApi(
        config,
        websocket_ping_interval=30,  # Ping 間隔をカスタマイズ
        websocket_pong_timeout=90,   # Pong タイムアウトをカスタマイズ
        websocket_takeover=True,     # 既存コネクションを置き換える
        websocket_on_close=on_close  # クローズイベントのコールバック
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

## 🧰 モデル一覧

### `GetArticlesParams`（REST API）

記事を絞り込むためのクエリパラメータ:

| フィールド             | 型             | 説明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | ブール演算子を使える検索テキスト                   |
| `tickers`              | `List[str]`    | ティッカーで絞り込み（例: `["AAPL", "NVDA"]`）     |
| `sources`              | `List[str]`    | 特定のニュースソースを含める                       |
| `excludeSources`       | `List[str]`    | 特定のニュースソースを除外する                     |
| `optInSources`         | `List[str]`    | デフォルト以外のソースを追加する                   |
| `language`             | `str`          | 言語フィルタ（例: `"en"`、`"de"`）                 |
| `countries`            | `List[str]`    | 国コードで絞り込み（例: `["US", "GB"]`）           |
| `from_`                | `str`          | 開始日（`YYYY-MM-DD` または ISO 形式）             |
| `to`                   | `str`          | 終了日（`YYYY-MM-DD` または ISO 形式）             |
| `includeContent`       | `bool`         | 記事全文を含める（デフォルト: `False`）            |
| `includeEntities`      | `bool`         | タグ付けされた企業を含める（デフォルト: `False`）  |
| `excludeEmptyContent`  | `bool`         | 全文のある記事のみ（デフォルト: `False`）          |
| `orderBy`              | `str`          | 並び替え項目: `"publishDate"`、`"createdAt"`、`"revisedDate"` |
| `order`                | `str`          | 並び順: `"ASC"` または `"DESC"`                    |
| `page`                 | `int`          | ページ番号（1 から開始）                           |
| `pageSize`             | `int`          | 1 ページあたりの件数（1〜1000）                    |

### `GetArticleByLinkParams`（REST API）

URL から単一記事を取得するためのパラメータ:

| フィールド             | 型             | 説明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `link`                 | `str`          | 取得する記事の URL（必須）                         |
| `includeContent`       | `bool`         | 記事全文を含める（デフォルト: `None`）             |
| `includeEntities`      | `bool`         | タグ付けされた企業を含める（デフォルト: `None`）   |

### `GetArticlesWebSocketParams`（WebSocket）

WebSocket 購読用のパラメータ:

| フィールド             | 型             | 説明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | 検索テキスト                                       |
| `tickers`              | `List[str]`    | ティッカーで絞り込み                               |
| `sources`              | `List[str]`    | 特定のニュースソースを含める                       |
| `excludeSources`       | `List[str]`    | 特定のニュースソースを除外する                     |
| `optInSources`         | `List[str]`    | デフォルト以外のソースを追加する                   |
| `language`             | `str`          | 言語フィルタ                                       |
| `countries`            | `List[str]`    | 国コードで絞り込み（例: `["US", "GB"]`）           |
| `extended`             | `bool`         | 記事の詳細をすべて含める（デフォルト: `False`）    |
| `includeEntities`      | `bool`         | タグ付けされた企業を含める（デフォルト: `False`）  |
| `excludeEmptyContent`  | `bool`         | 全文のある記事のみ（デフォルト: `False`）          |

### `GetRawArticlesWebSocketParams`（Raw WebSocket）

Raw WebSocket 購読用のパラメータ:

| フィールド             | 型             | 説明                                               |
| ---------------------- | -------------- | -------------------------------------------------- |
| `query`                | `str`          | フィールドフィルタ付きの検索テキスト（`source:`、`title:`、`summary:`） |
| `sources`              | `List[str]`    | 特定のニュースソースを含める                       |
| `excludeSources`       | `List[str]`    | 特定のニュースソースを除外する                     |
| `optInSources`         | `List[str]`    | デフォルト以外のソースを追加する                   |
| `language`             | `str`          | 言語フィルタ                                       |

### `Article`

記事オブジェクトのフィールド（Enhanced WebSocket / REST API）:

| フィールド     | 型                | 説明                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 記事タイトル                                |
| `link`         | `str`             | 記事の URL                                  |
| `publishDate`  | `datetime`        | 公開日時                                    |
| `source`       | `str`             | ソースのドメイン                            |
| `language`     | `str`             | 記事の言語コード                            |
| `summary`      | `str`             | 記事の要約                                  |
| `content`      | `str`             | 記事全文（取得可能な場合）                  |
| `sentiment`    | `str`             | センチメント分析の結果                      |
| `confidence`   | `float`           | センチメントの確信度スコア                  |
| `images`       | `List[str]`       | 画像 URL のリスト                           |
| `companies`    | `List[Company]`   | タグ付けされた企業とそのメタデータ          |

### `RawArticle`

未加工記事オブジェクトのフィールド（Raw WebSocket）:

| フィールド     | 型                | 説明                                        |
| -------------- | ----------------- | ------------------------------------------- |
| `title`        | `str`             | 記事タイトル                                |
| `link`         | `str`             | 記事の URL                                  |
| `publishDate`  | `datetime`        | 公開日時                                    |
| `source`       | `str`             | ソースのドメイン                            |
| `language`     | `str`             | 記事の言語コード                            |
| `summary`      | `str`             | 記事の要約                                  |
| `images`       | `List[str]`       | 画像 URL のリスト                           |

### `Company`

タグ付けされた企業の情報:

| フィールド        | 型                | 説明                                     |
| ----------------- | ----------------- | ---------------------------------------- |
| `companyId`       | `int`             | 企業の一意な識別子                       |
| `name`            | `str`             | 企業名                                   |
| `ticker`          | `str`             | 主要ティッカーシンボル                   |
| `confidence`      | `float`           | タグ付けの確信度スコア                   |
| `country`         | `str`             | 企業の所在国                             |
| `exchange`        | `str`             | 主要取引所                               |
| `sector`          | `str`             | セクター                                 |
| `industry`        | `str`             | 業種分類                                 |
| `isin`            | `str`             | ISIN コード                              |
| `openfigi`        | `str`             | OpenFIGI 識別子                          |
| `primaryListing`  | `Listing`         | 主要取引所での上場情報                   |
| `isins`           | `List[str]`       | すべての ISIN コード                     |
| `otherListings`   | `List[Listing]`   | その他の取引所での上場情報               |

### `Source`

ニュースソースのメタデータ:

| フィールド           | 型      | 説明                                            |
| -------------------- | ------- | ----------------------------------------------- |
| `domain`             | `str`   | ソースのドメイン（例: `"www.reuters.com"`）     |
| `isContentAvailable` | `bool`  | 全文を取得できるかどうか                        |
| `isDefaultSource`    | `bool`  | デフォルトで含まれるソースかどうか              |

---

## 🤝 コントリビューション

コントリビューションやご提案を歓迎します。

- 本リポジトリをフォークしてください
- フィーチャーブランチを作成してください
- 必要に応じてテストを添えてプルリクエストを送ってください

---

## 📄 ライセンス

MIT License – [LICENSE](LICENSE) を参照してください

---

## 🔗 関連リンク

- [Finlight API ドキュメント](https://docs.finlight.me)
- [GitHub リポジトリ](https://github.com/jubeiargh/finlight-client-py)
- [PyPI パッケージ](https://pypi.org/project/finlight-client)
- [日本語の製品ページ](https://finlight.me/ja/news-api)
