"""D-01 .. D-11: decoding articles, presence of every key (absent / null / [] / value)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from finlight_client import Article, raw_json, to_wire
from finlight_client.models import decode_article
from tests.support import fixtures, helper_presence, load, presence

GATED = ("content", "sentiment", "companies", "events")


def check_presence(article: Article, expect: dict[str, str]) -> None:
    for path, state in expect.items():
        assert presence(article, path) == state, path
        if path in GATED:
            assert helper_presence(article, path) == state, f"helper for {path}"
    # companyIds only appears when companies is in the same payload.
    if article.events:
        for event in article.events:
            if not article.companies_present:
                assert event.company_ids is None


def check_roundtrip(article: Article, wire: dict[str, Any]) -> None:
    """Writing the model back keeps absent keys absent and null as null."""
    assert raw_json(article) == wire
    out = to_wire(article)
    for key in GATED:
        assert (key in out) == (key in wire)
        if key in wire and wire[key] is None:
            assert out[key] is None


DECODE = [(cid, p) for cid, p in fixtures("fixtures/decode") if cid != "D-10"]


@pytest.mark.parametrize(("case", "path"), DECODE, ids=[c for c, _ in DECODE])
def test_decode(case: str, path: Path) -> None:
    fx = load(f"fixtures/decode/{path.name}")
    article = decode_article(fx["wire"])
    check_presence(article, fx["expect"]["presence"])
    check_roundtrip(article, fx["wire"])
    wire = fx["wire"]

    if case == "D-01":
        assert len(article.media) == 3
        assert article.revised_at == wire["revisedAt"]
        assert article.companies[1].primary_listing is None
        assert article.events[0].company_ids == [900001, 900002]
        assert article.sentiment.confidence == 0.9812
        assert article.available_at_time is not None
    if case == "D-02":
        assert article.available_at is None
        for key in GATED:
            assert helper_presence(article, key) == "absent"
    if case == "D-04":
        assert article.content is None and article.companies is None and article.events is None
        assert not article.content_present and not article.sentiment_present
    if case == "D-07":
        assert article.published_at == "1970-01-01T00:00:00.000Z"
        assert article.published_at_time is not None and article.published_at_time.year == 1970
        assert article.summary == wire["summary"]
        assert article.companies[0].role is None and article.companies[0].relevance is None
        assert article.events == [] and article.events_present
        assert article.countries == [] and article.categories == []
    if case == "D-08":
        assert article.title == wire["title"]
        assert article.content == wire["content"]
    if case == "D-09":
        assert article.sentiment.label is None and article.sentiment.confidence == 0.42
        assert article.companies == [] and article.companies_present
        assert article.events[0].direction is None
    if case == "D-11":
        assert article.summary is None and article.content is None and article.content_present
        assert article.title == wire["title"]


MATRIX = load("fixtures/decode/matrix.json")["cases"]


@pytest.mark.parametrize("sub", MATRIX, ids=[c["id"] for c in MATRIX])
def test_decode_matrix(sub: dict[str, Any]) -> None:
    article = decode_article(sub["wire"])
    check_presence(article, sub["expect"]["presence"])
    check_roundtrip(article, sub["wire"])
    if sub["channel"] == "raw":
        assert article.available_at is None
