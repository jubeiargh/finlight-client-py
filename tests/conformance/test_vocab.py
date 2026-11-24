"""V-01: the constants the SDK ships equal vocab.json."""

from __future__ import annotations

import pytest

from finlight_client import (
    CompanyRole,
    ConnectionErrorCode,
    EventDirection,
    EventType,
    FinlightConfig,
    Importance,
    IncludeBlock,
    OrderBy,
    PreemptReason,
    ProblemCode,
    RateLimitType,
    SentimentLabel,
    SortOrder,
    SourceType,
    StreamEventName,
    WebhookEventName,
)
from finlight_client.models import decode_article
from finlight_client.vocab import PAYLOAD_VERSION
from tests.support import load


@pytest.mark.parametrize("case", ["V-01"])
def test_vocab(case: str) -> None:
    vocab = load("vocab.json")
    req, resp, ws = vocab["request"], vocab["response"], vocab["websocket"]
    assert PAYLOAD_VERSION == vocab["payloadVersion"] == 3

    assert list(IncludeBlock.ALL) == req["include"]["values"]
    assert list(OrderBy.ALL) == req["orderBy"]["values"]
    assert list(SortOrder.ALL) == req["order"]["values"]
    assert list(CompanyRole.ALL) == req["roles"]["values"] == resp["roles"]["values"]
    assert list(EventType.ALL) == req["eventTypes"]["values"] == resp["eventTypes"]["values"]
    assert list(EventDirection.ALL) == req["eventDirections"]["values"] == resp["eventDirections"]["values"]
    assert list(Importance.ALL) == req["minImportance"]["values"] == resp["importance"]["values"]
    assert list(SentimentLabel.ALL) == resp["sentimentLabels"]["values"]
    assert list(SourceType.ALL) == resp["sourceTypes"]["values"]

    assert list(StreamEventName.ALL) == ws["events"]["values"]
    assert list(StreamEventName.ARTICLE_EVENTS) == ws["articleEvents"]["values"]
    assert list(StreamEventName.CONNECTION_EVENTS) == ws["connectionEvents"]["values"]
    assert list(ConnectionErrorCode.ALL) == ws["connectionErrorCodes"]["values"]
    assert list(PreemptReason.ALL) == ws["preemptReasons"]["values"]
    assert list(WebhookEventName.ALL) == vocab["webhook"]["events"]["values"]

    assert [{"code": c, "type": ProblemCode.TYPES[c]} for c in ProblemCode.ALL] == vocab["problemCodes"]["values"]
    assert list(RateLimitType.ALL) == vocab["limitTypes"]["values"]

    defaults = FinlightConfig(api_key="k")
    assert defaults.ping_interval * 1000 == ws["heartbeatMs"]
    assert defaults.watchdog_timeout * 1000 == ws["staleMs"]
    assert defaults.rotation_interval * 1000 < ws["maxLifetimeMs"]

    # Response enums are open: unknown strings survive decoding unchanged.
    wire = load("fixtures/forward-compat/unknown-enum-values.json")["wire"]
    article = decode_article(wire)
    assert article.events[0].type == "esg_controversy"
    assert article.events[0].type not in EventType.ALL
