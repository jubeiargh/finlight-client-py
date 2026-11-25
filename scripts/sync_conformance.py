#!/usr/bin/env python3
"""Copy the finlight API v3 contract kit into ``conformance/``.

Usage (one command):

    python scripts/sync_conformance.py [--from PATH]

PATH is the kit directory (``shared/contracts/api-v3`` in the finlight
monorepo). Default: ``$FINLIGHT_CONTRACT_KIT``, else ``../../../contracts/api-v3``
(where the kit sits when this repo is the monorepo submodule).

The source is checked against its own MANIFEST first; then ``conformance/`` is
replaced by exactly the files the MANIFEST lists, plus the MANIFEST itself.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "conformance"


def read_manifest(kit: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (kit / "MANIFEST").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        if not rel or len(digest) != 64:
            raise SystemExit(f"malformed MANIFEST line: {line!r}")
        entries[rel] = digest
    return entries


def verify(kit: Path) -> dict[str, str]:
    """Check every file of ``kit`` against its MANIFEST; return the MANIFEST entries."""
    entries = read_manifest(kit)
    problems = []
    for rel, digest in entries.items():
        path = kit / rel
        if not path.is_file():
            problems.append(f"missing: {rel}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"checksum differs: {rel}")
    listed = set(entries) | {"MANIFEST"}
    for path in kit.rglob("*"):
        if path.is_file():
            rel = path.relative_to(kit).as_posix()
            if rel not in listed:
                problems.append(f"not in MANIFEST: {rel}")
    if problems:
        raise SystemExit("contract kit does not match its MANIFEST:\n  " + "\n  ".join(problems))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default = os.environ.get("FINLIGHT_CONTRACT_KIT") or str(ROOT / ".." / ".." / ".." / "contracts" / "api-v3")
    parser.add_argument("--from", dest="source", default=default, help="kit directory")
    args = parser.parse_args()
    kit = Path(args.source).resolve()
    if not (kit / "MANIFEST").is_file():
        raise SystemExit(f"no contract kit at {kit} (pass --from PATH)")
    entries = verify(kit)
    if TARGET.exists():
        shutil.rmtree(TARGET)
    for rel in sorted(entries) + ["MANIFEST"]:
        dest = TARGET / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kit / rel, dest)
    verify(TARGET)
    version = (TARGET / "CONTRACT_VERSION").read_text(encoding="utf-8").strip()
    print(f"conformance/ synced: contract {version}, {len(entries)} files")


if __name__ == "__main__":
    sys.exit(main())
