from .api_client import ApiClient
from .models import Article, ArticleResponse, GetArticleByLinkParams, GetArticlesParams


class ArticleService:
    """Service for fetching and managing financial news articles."""

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def fetch_articles(self, params: GetArticlesParams) -> ArticleResponse:
        """Fetches financial news articles based on the provided search parameters.

        Supports advanced filtering by tickers, sources, dates, and custom queries.
        Articles are returned with metadata including sentiment, company tags, and content.

        Args:
            params: Search parameters for filtering articles. Supports:
                - query: Advanced query string with boolean operators
                - tickers: Filter by company tickers (e.g., ['AAPL', 'NVDA'])
                - sources: Limit to specific news sources
                - exclude_sources: Sources to exclude from results
                - from_date: Start date in YYYY-MM-DD format or ISO string
                - to_date: End date in YYYY-MM-DD format or ISO string
                - include_content: Whether to include full article content
                - include_entities: Whether to include tagged company data
                - page: Page number for pagination
                - page_size: Number of results per page (1-1000)

        Returns:
            ArticleResponse: Paginated article results with metadata

        Raises:
            Exception: If the API request fails

        Example:
            >>> params = GetArticlesParams(
            ...     tickers=['AAPL'],
            ...     from_='2024-01-01',
            ...     includeContent=True,
            ...     pageSize=20
            ... )
            >>> response = article_service.fetch_articles(params)
            >>> print(f"Found {len(response.articles)} articles")
        """
        response = self.api_client.request(
            "POST",
            "/v2/articles",
            data=params.model_dump(by_alias=True, exclude_none=True),
        )
        # Use Pydantic validation to handle all type conversions automatically
        return ArticleResponse.model_validate(response)

    def fetch_article_by_link(self, params: GetArticleByLinkParams) -> Article:
        """Fetches a single article by its URL.

        Args:
            params: Parameters for fetching article by link. Supports:
                - link: The URL of the article to fetch (required)
                - includeContent: Whether to include full article content
                - includeEntities: Whether to include tagged company data

        Returns:
            Article: The article if found

        Raises:
            Exception: If the API request fails or article is not found

        Example:
            >>> params = GetArticleByLinkParams(
            ...     link='https://www.reuters.com/technology/example-article',
            ...     includeContent=True
            ... )
            >>> article = article_service.fetch_article_by_link(params)
            >>> print(article.title)
        """
        response = self.api_client.request(
            "GET",
            "/v2/articles/by-link",
            params=params.model_dump(by_alias=True, exclude_none=True),
        )
        return Article.model_validate(response)
