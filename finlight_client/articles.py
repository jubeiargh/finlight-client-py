from .api_client import ApiClient
from datetime import datetime
from .models import ArticleResponse, GetArticlesParams


class ArticleService:
    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def fetch_articles(self, params: GetArticlesParams) -> ArticleResponse:
        response = self.api_client.request(
            "POST",
            "/v2/articles",
            data=params.model_dump(by_alias=True, exclude_none=True),
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
