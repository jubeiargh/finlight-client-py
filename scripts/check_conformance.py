#!/usr/bin/env python3
"""Fail when ``conformance/`` does not match its MANIFEST (sha256 per file, no extra files)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_conformance import TARGET, verify  # noqa: E402


def main() -> int:
    entries = verify(TARGET)
    version = (TARGET / "CONTRACT_VERSION").read_text(encoding="utf-8").strip()
    print(f"conformance/ matches MANIFEST: contract {version}, {len(entries)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
