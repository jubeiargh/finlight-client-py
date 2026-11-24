"""Walk several pages with search_all (the body is frozen, only the cursor changes)."""

from __future__ import annotations

from _env import client_options

from finlight_client import FinlightClient


def main() -> None:
    with FinlightClient(**client_options()) as client:
        results = client.articles.search_all(
            query="eventType:earnings",
            order_by="publishedAt",
            limit=50,
            max_pages=3,  # every page costs quota; the default cap is 10
        )
        count = 0
        for article in results:
            count += 1
            print(article.id, article.title)
        print(f"{count} articles from {results.pages_fetched} pages")
        if results.truncated:
            # Continue later with: client.articles.search_all(..., cursor=results.next_cursor)
            print("stopped at max_pages; next cursor:", results.next_cursor)


if __name__ == "__main__":
    main()
