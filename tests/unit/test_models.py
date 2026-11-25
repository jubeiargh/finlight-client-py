"""R-MODELS-1..3, R-NULL-1: tolerant reading, raw values, skipped entries."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from finlight_client import Article, FinlightDecodeError, raw_json, to_wire
from finlight_client.models import decode_article, decode_article_page
from tests.support import load

FULL = load("fixtures/decode/full-article.json")["wire"]


def test_values_arrive_unchanged() -> None:
    wire = copy.deepcopy(FULL)
    wire.update(publishedAt="1970-01-01T00:00:00.000Z", summary="", firstSeenAt="now", revisedAt="garbage")
    wire["sentiment"]["confidence"] = 0.912345678
    wire["companies"][0]["companyId"] = 9007199254740991
    article = decode_article(wire)
    assert article.published_at == "1970-01-01T00:00:00.000Z" and article.published_at_time.year == 1970
    assert article.summary == ""
    assert article.first_seen_at == "now" and article.first_seen_at_time is None
    assert article.revised_at_time is None
    assert article.sentiment.confidence == 0.912345678
    assert article.companies[0].company_id == 9007199254740991


@pytest.mark.parametrize("value", ["2026-09-18T12:01:03", "2026-09-18", "1795467845", "2026-09-18 12:01:03Z",
                                   "2026-13-01T00:00:00Z", "2026-09-18T12:01:03+25:00"])
def test_strict_time_parsing(value: str) -> None:
    article = decode_article(dict(FULL, publishedAt=value))
    assert article.published_at == value and article.published_at_time is None


def test_time_with_offset_is_parsed() -> None:
    article = decode_article(dict(FULL, publishedAt="2026-09-18T14:01:03.5+02:00"))
    assert article.published_at_time.isoformat() == "2026-09-18T12:01:03.500000+00:00"


@pytest.mark.parametrize("mutation", [
    lambda a: a.pop("link"), lambda a: a.update(id=None), lambda a: a.update(title=5),
    lambda a: a["source"].pop("domain"), lambda a: a["sentiment"].update(confidence="0.95"),
    lambda a: a["companies"][0].update(companyId="900001"), lambda a: a["companies"][0].update(companyId=True),
    lambda a: a["events"][0].pop("type"), lambda a: a.update(media="x"),
])
def test_broken_entries_fail(mutation: Any) -> None:
    wire = copy.deepcopy(FULL)
    mutation(wire)
    with pytest.raises(FinlightDecodeError):
        decode_article(wire)


def test_missing_optional_and_null_lists() -> None:
    minimal = {"id": "a", "link": "l", "title": "t", "source": {"domain": "d"}, "media": None, "countries": None}
    article = decode_article(minimal)
    assert article.media == [] and article.countries == [] and article.categories == []
    assert article.summary is None and article.first_seen_at is None
    assert not article.content_present and article.companies is None
    assert to_wire(article) == {"id": "a", "link": "l", "title": "t", "source": {"domain": "d"},
                                "media": [], "countries": []}


def test_page_skips_broken_entry(caplog: Any) -> None:
    broken = dict(FULL, id=None)
    page = decode_article_page({"articles": [FULL, broken, FULL], "pagination": {"hasMore": False}})
    assert len(page.articles) == 2
    assert len(page.skipped) == 1 and page.skipped[0].index == 1 and page.skipped[0].raw == broken
    assert "skipped" in caplog.text


def test_raw_json_and_unknown_keys() -> None:
    wire = dict(FULL, story={"id": "s1"})
    article = decode_article(wire)
    assert raw_json(article)["story"] == {"id": "s1"}
    assert not hasattr(article, "raw") and not hasattr(article, "story")
    assert json.loads(json.dumps(raw_json(article))) == wire


def test_keys_match_exactly() -> None:
    wire = dict(FULL)
    wire["first_seen_at"] = wire.pop("firstSeenAt")
    article = decode_article(wire)
    assert article.first_seen_at is None
    with pytest.raises(FinlightDecodeError):
        decode_article({"ID": "a", "link": "l", "title": "t", "source": {"domain": "d"}})


def test_model_is_the_public_article_type() -> None:
    assert isinstance(decode_article(FULL), Article)


def test_decode_error_names_the_path() -> None:
    wire = copy.deepcopy(FULL)
    wire["companies"][1]["companyId"] = "900002"
    with pytest.raises(FinlightDecodeError) as info:
        decode_article(wire)
    assert info.value.path == "companies[1].companyId" and info.value.raw == "900002"
    assert raw_json(info.value) == "900002"
