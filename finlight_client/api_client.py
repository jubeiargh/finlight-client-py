import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import DEFAULT_API_CONFIG


class ApiClient:
    def __init__(self, config):
        self.base_url = config.get("base_url", DEFAULT_API_CONFIG["base_url"])
        self.timeout = config.get("timeout", DEFAULT_API_CONFIG["timeout"])
        self.retry_count = config.get("retry_count", DEFAULT_API_CONFIG["retry_count"])
        self.api_key = config.get("api_key", DEFAULT_API_CONFIG["api_key"])

        self.session = requests.Session()
        retries = Retry(
            total=self.retry_count,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({"X-API-KEY": self.api_key})

    def request(self, method, endpoint, params=None, data=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(
            method, url, params=params, json=data, timeout=self.timeout / 1000
        )
        response.raise_for_status()
        return response.json()
