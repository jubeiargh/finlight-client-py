#!/usr/bin/env python3
"""Build sdist and wheel into an empty folder and fail if test data or local files would ship."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("conformance/", "local/", "tests/", "examples/", "scripts/", ".env", ".venv")


def main() -> int:
    with tempfile.TemporaryDirectory() as out:
        subprocess.run([sys.executable, "-m", "build", "--outdir", out, str(ROOT)], check=True,
                       stdout=subprocess.DEVNULL)
        problems = []
        names: dict[str, list[str]] = {}
        for path in Path(out).iterdir():
            if path.suffix == ".whl":
                names[path.name] = zipfile.ZipFile(path).namelist()
            elif path.name.endswith(".tar.gz"):
                names[path.name] = [m.split("/", 1)[1] if "/" in m else m for m in tarfile.open(path).getnames()]
        for artifact, members in sorted(names.items()):
            print(artifact)
            for member in sorted(members):
                print("  ", member)
                if any(member.startswith(bad) or f"/{bad}" in member for bad in FORBIDDEN):
                    problems.append(f"{artifact}: {member}")
            if artifact.endswith(".whl") and "finlight_client/py.typed" not in members:
                problems.append(f"{artifact}: py.typed missing")
        if len(names) != 2:
            problems.append(f"expected one wheel and one sdist, got {sorted(names)}")
        for problem in problems:
            print("FORBIDDEN:", problem)
        return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
