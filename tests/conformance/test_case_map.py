"""R-TEST-1: the vendored kit matches its MANIFEST and every kit case has a test."""

from __future__ import annotations

import re
import sys
from typing import Any

import pytest

from tests.support import ROOT, case_ids_from_conformance

sys.path.insert(0, str(ROOT / "scripts"))
from sync_conformance import TARGET, verify  # noqa: E402


def mapped() -> dict[str, str]:
    text = (ROOT / "CONFORMANCE.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\| ([A-Z]-\d+) \| [^|]+ \| `([^`]+)` \|", text, flags=re.M))


def test_manifest_matches() -> None:
    verify(TARGET)


def test_every_case_is_mapped() -> None:
    cases = case_ids_from_conformance()
    declared = re.search(r"Total: (\d+) cases", (TARGET / "conformance.md").read_text(encoding="utf-8"))
    assert declared and int(declared.group(1)) == len(cases) == len(set(cases))
    assert sorted(mapped()) == sorted(cases)


def test_every_mapped_test_exists(request: Any) -> None:
    collected = {item.nodeid for item in request.session.items}
    files = {node.split("::")[0] for node in mapped().values()}
    if not all(any(n.startswith(f + "::") for n in collected) for f in files):
        pytest.skip("run the whole conformance folder to check the map")
    missing = []
    for case, node in mapped().items():
        if node.endswith("*]"):
            ok = any(n.startswith(node[:-2]) for n in collected)
        else:
            ok = node in collected
        if not ok:
            missing.append(f"{case}: {node}")
    assert missing == []
