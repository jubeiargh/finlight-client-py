from typing import Callable

from ._base_websocket_client import BaseWebSocketClient
from .models import Article, GetArticlesWebSocketParams


class WebSocketClient(BaseWebSocketClient):
    _logger_name = "finlight-websocket-client"
    _log_prefix = ""
    _article_model = Article
    _dedupe_articles = True

    def _get_wss_url(self) -> str:
        return self.config.wss_url

    async def connect(
        self,
        request_payload: GetArticlesWebSocketParams,
        on_article: Callable[[Article], None],
    ):
        await self._connect(request_payload, on_article)
