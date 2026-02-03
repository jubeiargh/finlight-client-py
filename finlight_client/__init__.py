from .api_client import ApiClient
from .articles import ArticleService
from .sources import SourcesService
from .websocket_client import WebSocketClient
from .raw_websocket_client import RawWebSocketClient
from .webhook_service import WebhookService, WebhookVerificationError
from .models import ApiConfig, WebSocketOptions, RawWebSocketOptions
from typing import Optional, Callable


class FinlightApi:
    def __init__(
        self,
        config: ApiConfig,
        # WebSocket configuration options (flat kwargs for backward compat)
        websocket_ping_interval: int = 25,
        websocket_pong_timeout: int = 60,
        websocket_base_reconnect_delay: float = 0.5,
        websocket_max_reconnect_delay: float = 10.0,
        websocket_connection_lifetime: int = 115 * 60,  # 115 minutes
        websocket_takeover: bool = False,
        websocket_on_close: Optional[Callable[[int, str], None]] = None,
        # Options objects (take precedence over flat kwargs when provided)
        websocket_options: Optional[WebSocketOptions] = None,
        raw_websocket_options: Optional[RawWebSocketOptions] = None,
    ):
        self.config: ApiConfig = config or ApiConfig()
        self.api_client = ApiClient(self.config)
        self.articles = ArticleService(self.api_client)

        # Resolve enhanced WebSocket options
        ws_opts = websocket_options or WebSocketOptions()
        self.websocket = WebSocketClient(
            config=self.config,
            ping_interval=ws_opts.ping_interval if websocket_options else websocket_ping_interval,
            pong_timeout=ws_opts.pong_timeout if websocket_options else websocket_pong_timeout,
            base_reconnect_delay=ws_opts.base_reconnect_delay if websocket_options else websocket_base_reconnect_delay,
            max_reconnect_delay=ws_opts.max_reconnect_delay if websocket_options else websocket_max_reconnect_delay,
            connection_lifetime=ws_opts.connection_lifetime if websocket_options else websocket_connection_lifetime,
            takeover=ws_opts.takeover if websocket_options else websocket_takeover,
            on_close=ws_opts.on_close if websocket_options else websocket_on_close,
        )

        # Resolve raw WebSocket options
        raw_ws_opts = raw_websocket_options or RawWebSocketOptions()
        self.raw_websocket = RawWebSocketClient(
            config=self.config,
            ping_interval=raw_ws_opts.ping_interval,
            pong_timeout=raw_ws_opts.pong_timeout,
            base_reconnect_delay=raw_ws_opts.base_reconnect_delay,
            max_reconnect_delay=raw_ws_opts.max_reconnect_delay,
            connection_lifetime=raw_ws_opts.connection_lifetime,
            takeover=raw_ws_opts.takeover,
            on_close=raw_ws_opts.on_close,
        )

        self.sources = SourcesService(self.api_client)
        self.webhook = WebhookService()


# Export main classes and types for easy importing
__all__ = [
    "FinlightApi",
    "WebSocketClient",
    "RawWebSocketClient",
    "ApiClient",
    "ArticleService",
    "SourcesService",
    "WebhookService",
    "WebhookVerificationError",
    "ApiConfig",
    "WebSocketOptions",
    "RawWebSocketOptions",
]
