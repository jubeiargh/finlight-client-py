from .api_client import ApiClient
from datetime import datetime


class ArticleService:
    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def get_basic_articles(self, params):
        response = self.api_client.request("GET", "/v1/articles", params=params)
        response["articles"] = [
            {**article, "publishDate": self._parse_date(article["publishDate"])}
            for article in response.get("articles", [])
        ]
        return response

    def get_extended_articles(self, params):
        response = self.api_client.request(
            "GET", "/v1/articles/extended", params=params
        )
        response["articles"] = [
            {**article, "publishDate": self._parse_date(article["publishDate"])}
            for article in response.get("articles", [])
        ]
        return response

    @staticmethod
    def _parse_date(date_str):
        """Converts a date string into a datetime object."""
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}")
