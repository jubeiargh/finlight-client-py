"""Search one page of articles."""

from __future__ import annotations

from _env import client_options

from finlight_client import FinlightClient


def main() -> None:
    with FinlightClient(**client_options()) as client:
        page = client.articles.search(
            query="ticker:NVDA",
            languages=["en"],
            include=["companies", "events"],
            limit=10,
        )
        for article in page.articles:
            # published_at is the string as sent; published_at_time parses it (None if unreadable).
            print(article.published_at, article.source.domain, article.title)
            if article.sentiment_present and article.sentiment is not None:
                print("  sentiment:", article.sentiment.label, article.sentiment.confidence)
            if article.companies_present:
                tickers = [c.primary_listing.ticker for c in article.companies or [] if c.primary_listing]
                print("  companies:", tickers)
        print("more pages:", page.has_more)


if __name__ == "__main__":
    main()
