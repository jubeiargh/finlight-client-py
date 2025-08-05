from .api_client import ApiClient
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
        # Use Pydantic validation to handle all type conversions automatically
        return ArticleResponse.model_validate(response)
