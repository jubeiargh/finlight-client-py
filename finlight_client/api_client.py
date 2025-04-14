import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .models import ApiConfig


class ApiClient:
    def __init__(self, config: ApiConfig):
        self.config = config

        self.session = requests.Session()

        retries = Retry(
            total=self.config.retry_count,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({"X-API-KEY": self.config.api_key})

    def request(
        self, method: str, endpoint: str, params: dict = None, data: dict = None
    ):
        url = f"{self.config.base_url}{endpoint}"
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            timeout=self.config.timeout / 1000,  # Convert ms to seconds
        )
        response.raise_for_status()
        return response.json()
