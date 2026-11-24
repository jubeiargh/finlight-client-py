#!/usr/bin/env python3
"""Check the READMEs: the shared section skeleton, the version table, one structure for every language.

README.md must have exactly the headings below, in this order. The translations must have the same
heading levels and the same code blocks as README.md. Python code blocks must compile.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKELETON = [
    "# finlight-client (Python)",
    "## Versions",
    "## Requirements",
    "## Installation",
    "## Quick start",
    "## Search articles",
    "## Look up articles, companies and sources",
    "### Reading articles",
    "## Real-time streams",
    "## Webhooks",
    "## Errors and retries",
    "## Configuration",
    "## Data notes",
    "## Migrating from 2.x",
    "## Development",
    "## License",
]
TRANSLATIONS = ["README.zh-CN.md", "README.ja.md", "README.ko.md"]
FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)


def headings(text: str) -> list[str]:
    body = FENCE.sub("", text)
    return [line.strip() for line in body.splitlines() if re.match(r"^#{1,6} ", line)]


def main() -> int:
    problems: list[str] = []
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    if headings(english) != SKELETON:
        problems.append(f"README.md headings differ from the skeleton: {headings(english)}")
    if "| SDK version | API version |" not in english:
        problems.append("README.md has no version table")
    if "**Breaking release.**" not in english.split("## Versions")[0]:
        problems.append("README.md must start with the breaking-change notice")
    blocks = FENCE.findall(english)
    for lang, code in blocks:
        if lang == "python":
            try:
                compile(code, "README.md", "exec")
            except SyntaxError as exc:
                problems.append(f"README.md python block does not compile: {exc}")
    levels = [h.split(" ")[0] for h in SKELETON]
    for name in TRANSLATIONS:
        text = (ROOT / name).read_text(encoding="utf-8")
        if [h.split(" ")[0] for h in headings(text)] != levels:
            problems.append(f"{name}: heading structure differs from README.md")
        if FENCE.findall(text) != blocks:
            problems.append(f"{name}: code blocks differ from README.md")
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
