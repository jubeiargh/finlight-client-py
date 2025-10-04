from typing import List
from .api_client import ApiClient
from .models import Source


class SourcesService:
    """Service for managing and querying available news sources."""

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def get_sources(self) -> List[Source]:
        """Retrieves all available news sources with their configuration.

        Returns metadata for each source including domain, content availability,
        and whether it's included in the default source set.

        Returns:
            List[Source]: List of all available news sources

        Raises:
            Exception: If the API request fails

        Example:
            >>> sources = sources_service.get_sources()
            >>> defaults = [s for s in sources if s.isDefaultSource]
            >>> print(f"Found {len(defaults)} default sources")
        """
        response = self.api_client.request(
            "GET",
            "/v2/sources",
        )

        # Parse response into Source models
        return [Source.model_validate(source) for source in response]
