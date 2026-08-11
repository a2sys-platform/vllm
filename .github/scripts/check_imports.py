#!/usr/bin/env python3
"""G2b — the dependency between upstream code and ours runs one way only.

vllm/a2sys/ may import from vllm/. The reverse is a seam, and seams are declared.

vllm/a2sys/ is a subpackage rather than a separate distribution, which buys one install
and one import namespace but costs the boundary that separate packaging would have
enforced. This check is that boundary, moved from packaging into CI.
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

POLICY = Path(".github/a2sys-policy.yml")
REGISTRY = Path("seams/registry.yml")
IMPORT = re.compile(r"^\s*(?:from\s+vllm\.a2sys|import\s+vllm\.a2sys|from\s+vllm\s+import\s+a2sys)")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    ours = yaml.safe_load(POLICY.read_text())["ours_prefix"]
    registry = yaml.safe_load(REGISTRY.read_text()) or {}
    allowed = {e.get("file") for e in (registry.get("seams") or [])}

    tracked = git("ls-files", "vllm/").splitlines()
    failures: list[str] = []

    for path in tracked:
        if not path.endswith(".py") or path.startswith(ours) or path in allowed:
            continue
        try:
            text = Path(path).read_text(errors="replace")
        except OSError:
            continue
        if "a2sys" not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if IMPORT.match(line):
                failures.append(f"{path}:{lineno}: {line.strip()}")

    if not failures:
        print("Import direction holds: no upstream file reaches into vllm.a2sys.")
        return 0

    print("::error::Upstream files import vllm.a2sys outside a declared seam.")
    for f in failures:
        path, lineno, _ = f.split(":", 2)
        print(f"::error file={path},line={lineno}::{f}")
    print()
    print("Either declare the file as a seam in seams/registry.yml — which requires a")
    print("contract test and an upstream issue — or invert the dependency so vllm/a2sys/")
    print("registers itself through a registration API instead of being called directly.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
