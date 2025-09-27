from .api_client import ApiClient
from .articles import ArticleService
from .sources import SourcesService
from .websocket_client import WebSocketClient
from .webhook_service import WebhookService, WebhookVerificationError
from .models import ApiConfig
from typing import Optional, Callable


class FinlightApi:
    def __init__(
        self, 
        config: ApiConfig,
        # WebSocket configuration options
        websocket_ping_interval: int = 25,
        websocket_pong_timeout: int = 60,
        websocket_base_reconnect_delay: float = 0.5,
        websocket_max_reconnect_delay: float = 10.0,
        websocket_connection_lifetime: int = 115 * 60,  # 115 minutes
        websocket_takeover: bool = False,
        websocket_on_close: Optional[Callable[[int, str], None]] = None,
    ):
        self.config: ApiConfig = config or ApiConfig()
        self.api_client = ApiClient(self.config)
        self.articles = ArticleService(self.api_client)
        
        # Create WebSocket client with exposed settings
        self.websocket = WebSocketClient(
            config=self.config,
            ping_interval=websocket_ping_interval,
            pong_timeout=websocket_pong_timeout,
            base_reconnect_delay=websocket_base_reconnect_delay,
            max_reconnect_delay=websocket_max_reconnect_delay,
            connection_lifetime=websocket_connection_lifetime,
            takeover=websocket_takeover,
            on_close=websocket_on_close,
        )
        
        self.sources = SourcesService(self.api_client)
        self.webhook = WebhookService()


# Export main classes and types for easy importing
__all__ = [
    "FinlightApi",
    "WebSocketClient", 
    "ApiClient",
    "ArticleService",
    "SourcesService", 
    "WebhookService",
    "WebhookVerificationError",
    "ApiConfig",
]
