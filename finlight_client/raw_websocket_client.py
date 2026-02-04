from typing import Callable

from ._base_websocket_client import BaseWebSocketClient
from .models import RawArticle, GetRawArticlesWebSocketParams


class RawWebSocketClient(BaseWebSocketClient):
    _logger_name = "finlight-raw-websocket-client"
    _log_prefix = "[Raw] "
    _article_model = RawArticle

    def _get_wss_url(self) -> str:
        return str(self.config.wss_url) + "/raw"

    async def connect(
        self,
        request_payload: GetRawArticlesWebSocketParams,
        on_article: Callable[[RawArticle], None],
    ):
        await self._connect(request_payload, on_article)
