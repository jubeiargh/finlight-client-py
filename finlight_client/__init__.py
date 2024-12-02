from .api_client import ApiClient
from .articles import ArticleService
from .websocket_client import WebSocketClient
from .config import DEFAULT_API_CONFIG


class FinlightApi:
    def __init__(self, config):
        self.config = {**DEFAULT_API_CONFIG, **config}
        self.api_client = ApiClient(self.config)
        self.articles = ArticleService(self.api_client)
        self.websocket = WebSocketClient(self.config)
