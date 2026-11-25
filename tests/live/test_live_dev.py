"""Live smoke tests against the finlight dev API. Small load, never prod.

Run only with the owner's okay:

    FINLIGHT_API_KEY=... FINLIGHT_BASE_URL=https://api.dev.finlight.me \\
    FINLIGHT_WSS_URL=wss://wss.dev.finlight.me \\
    pytest tests/live -m live --force-enable-socket

Without all three variables every test is skipped.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

import pytest

from finlight_client import (
    AdmittedInfo,
    FinlightClient,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    cache_info,
)

pytestmark = pytest.mark.live

KEY = os.environ.get("FINLIGHT_API_KEY")
BASE = os.environ.get("FINLIGHT_BASE_URL")
WSS = os.environ.get("FINLIGHT_WSS_URL")
PROD_HOSTS = {"api.finlight.me", "wss.finlight.me"}

if not (KEY and BASE and WSS):
    pytest.skip("live tests need FINLIGHT_API_KEY, FINLIGHT_BASE_URL and FINLIGHT_WSS_URL", allow_module_level=True)
for _url in (BASE, WSS):
    if urlparse(_url).hostname in PROD_HOSTS:
        raise RuntimeError("live tests never run against prod")


@pytest.fixture(scope="module")
def client() -> Any:
    with FinlightClient(api_key=KEY, base_url=BASE, wss_url=WSS, max_retries=1) as c:
        yield c


@pytest.fixture(scope="module")
def page(client: FinlightClient) -> Any:
    return client.articles.search(query="ticker:NVDA", limit=3, include=["companies", "events"])


def test_sources(client: FinlightClient) -> None:
    sources = client.sources.list()
    assert sources and all(s.domain for s in sources)
    assert sources.skipped == []


def test_search_decodes(page: Any) -> None:
    assert page.skipped == []
    assert page.pagination.limit == 3 and page.pagination.returned == len(page.articles)
    for article in page.articles:
        assert article.id and article.link and article.source.domain
        assert not article.content_present  # content not requested
        if article.companies_present:
            for company in article.companies:
                assert isinstance(company.company_id, int)
        if article.events_present and article.companies_present:
            for event in article.events:
                assert event.company_ids is not None


def test_get_and_get_by_link(client: FinlightClient, page: Any) -> None:
    if not page.articles:
        pytest.skip("no article to look up")
    first = page.articles[0]
    by_link = client.articles.get_by_link(first.link, include=["content"])
    assert by_link.link == first.link and by_link.content_present in (True, False)
    try:
        by_id = client.articles.get(first.id)
        assert by_id.id == first.id
    except NotFoundError:
        pass  # articles indexed before the id rollout are reachable by link only


def test_search_all_two_pages(client: FinlightClient) -> None:
    results = client.articles.search_all(query="ticker:NVDA", limit=2, max_pages=2)
    articles = list(results)
    assert len(articles) <= 4 and results.pages_fetched <= 2


def test_not_found(client: FinlightClient) -> None:
    with pytest.raises(NotFoundError) as info:
        client.articles.get("finlight-sdk-smoke-does-not-exist")
    assert info.value.code == "NOT_FOUND" and info.value.request_id


def test_invalid_key() -> None:
    with FinlightClient(api_key="sk_invalid_smoke_key", base_url=BASE, max_retries=0) as bad:
        with pytest.raises(UnauthorizedError) as info:
            bad.sources.list()
    assert info.value.status == 401


def test_companies(client: FinlightClient) -> None:
    try:
        matches = client.companies.search("NVDA")
    except ForbiddenError:
        pytest.skip("key has no entityAccess")
    assert matches
    record = client.companies.get(matches[0].company_id)
    info = cache_info(record)
    assert info is not None and info.etag
    again = client.companies.get(matches[0].company_id, if_none_match=info.etag)  # caller revalidates
    assert again is None or again.company_id == record.company_id
    mics = [listing.mic for listing in record.listings]
    assert len(mics) == len(set(mics)), "listings name each exchange at most once (contract rc.2)"
    if record.primary_listing is not None and record.listings:
        assert record.listings[0].mic == record.primary_listing.mic


async def _first_admitted(make_stream: Any, timeout: float = 20.0) -> tuple[Any, list[Any]]:
    admitted: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    items: list[Any] = []
    stream = make_stream(lambda info: admitted.done() or admitted.set_result(info))

    async def consume() -> None:
        async for event in stream:
            items.append(event)

    task = asyncio.ensure_future(consume())
    try:
        info = await asyncio.wait_for(asyncio.shield(admitted), timeout)
        await asyncio.sleep(3)  # give the initial push a moment
        return info, items
    finally:
        await stream.close()
        await asyncio.wait_for(task, 10)


async def test_stream_admitted(client: FinlightClient) -> None:
    errors: list[Any] = []
    info, items = await _first_admitted(
        lambda hook: client.stream(query="ticker:NVDA", include=["companies"], on_error=errors.append,
                                   on_admitted=hook)
    )
    assert isinstance(info, AdmittedInfo)
    assert info.lease_id and isinstance(info.server_now, int) and info.client_nonce
    assert errors == []
    for item in items:
        assert item.kind in ("created", "updated", "other")


async def test_raw_stream_admitted(client: FinlightClient) -> None:
    info, items = await _first_admitted(
        lambda hook: client.raw_stream(query="ticker:NVDA", on_admitted=hook)
    )
    assert info.lease_id
    for item in items:
        assert item.data is None or item.data.available_at is None


async def test_stream_invalid_key() -> None:
    bad = FinlightClient(api_key="sk_invalid_smoke_key", wss_url=WSS)
    with pytest.raises(UnauthorizedError):
        async for _ in bad.stream(query="x"):
            pass
