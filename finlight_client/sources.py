from typing import List
from .api_client import ApiClient
from .models import Source


class SourcesService:
    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def get_sources(self) -> List[Source]:
        response = self.api_client.request(
            "GET",
            "/v2/sources",
        )

        return response
