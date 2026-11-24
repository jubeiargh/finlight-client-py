"""R-SCOPE-1: no v1/v2 surface left; legacy keys never reach the wire."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from finlight_client import FinlightClient
from finlight_client._params import (
    RAW_STREAM_FIELDS,
    SEARCH_FIELDS,
    STREAM_FIELDS,
    build_body,
    build_subscribe,
)

LEGACY = ("includeContent", "includeEntities", "extended", "pageSize", "publishDate", "isUpdate")
SRC = Path(__file__).resolve().parents[2] / "finlight_client"
# R-WS-1 (frame decoder) and R-HOOK-2 (webhook version check) may know v2.
ALLOWED = {"_frames.py", "webhooks.py"}


def full_values(fields):
    sample = {"str": "x", "strlist": ["x"], "languages": ["en"], "include": ["content", "companies", "events"],
              "bool": True, "time": "2026-01-01", "unit": 0.5, "limit": 10}
    return {py: sample[kind] for py, _, kind in fields}


@pytest.mark.parametrize("fields", [SEARCH_FIELDS, STREAM_FIELDS, RAW_STREAM_FIELDS])
def test_every_request_type_serialized_without_legacy_keys(fields) -> None:
    text = json.dumps(build_subscribe(fields, full_values(fields)) if fields is not SEARCH_FIELDS
                      else build_body(fields, full_values(fields)))
    for key in LEGACY:
        assert f'"{key}"' not in text


def test_source_has_no_v1_v2_leftovers() -> None:
    pattern = re.compile(
        r"/v1/|/v2/|sendarticle|admin_kick|include_?content|include_?entities|\bextended\b|page_?size|"
        r"publish_?date|is_?update\b",
        re.I,
    )
    hits = []
    for path in SRC.rglob("*.py"):
        if path.name in ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.name}:{number}: {line.strip()}")
    assert hits == []


def test_legacy_keys_cannot_be_smuggled_into_a_subscribe() -> None:
    client = FinlightClient(api_key="k")
    for key in ("includeContent", "include_content", "extended", "payload_version", "payloadVersion"):
        with pytest.raises(TypeError):
            client.stream(**{key: True})
    with pytest.raises(TypeError, match="include"):
        client.raw_stream(include=["content"])  # type: ignore[call-arg]


def test_subscribe_with_only_query() -> None:
    stream = FinlightClient(api_key="k").stream(query="ticker:XMPL")
    assert stream._frame == {"payloadVersion": 3, "query": "ticker:XMPL"}
    assert type(stream._frame["payloadVersion"]) is int
