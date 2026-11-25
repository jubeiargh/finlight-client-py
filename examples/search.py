"""Search one page of articles."""

from __future__ import annotations

from _env import client_options

from finlight_client import FinlightApiError, FinlightClient


def main() -> None:
    with FinlightClient(**client_options()) as client:
        try:
            page = client.articles.search(
                query="ticker:NVDA",
                languages=["en"],
                include=["companies", "events"],
                limit=10,
            )
        except FinlightApiError as error:
            print("API error:", error.status, error.code, error.request_id)
            return
        for article in page.articles:
            # published_at_time parses the timestamp strictly (None if unreadable).
            print(article.published_at_time, article.source.domain, article.title)
            if article.companies_present:
                tickers = [c.primary_listing.ticker for c in article.companies or [] if c.primary_listing]
                print("  companies:", tickers)
        print("has more:", page.pagination.has_more)


if __name__ == "__main__":
    main()
