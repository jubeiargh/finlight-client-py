"""Look up articles, companies and sources."""

from __future__ import annotations

from _env import client_options

from finlight_client import FinlightClient, NotFoundError


def main() -> None:
    with FinlightClient(**client_options()) as client:
        page = client.articles.search(query="ticker:NVDA", limit=1)
        if page.articles:
            first = page.articles[0]
            by_id = client.articles.get(first.id, include=["content", "companies"])
            print("by id:", by_id.title, "| content present:", by_id.content_present)
            by_link = client.articles.get_by_link(first.link)
            print("by link:", by_link.id)
        try:
            client.articles.get("does-not-exist")
        except NotFoundError as error:
            print("not found:", error.detail)

        # Company master data needs the entityAccess entitlement.
        matches = client.companies.search("NVDA", mic="XNAS")
        for company in matches:
            print("company:", company.company_id, company.name, [listing.mic for listing in company.listings])
        if matches:
            record = client.companies.get(matches[0].company_id)  # revalidated with its ETag next time
            print("record:", record.name, record.sector, "etag:", record.etag)

        sources = client.sources.list()
        print(f"{len(sources)} sources, e.g.", [source.domain for source in sources[:3]])


if __name__ == "__main__":
    main()
