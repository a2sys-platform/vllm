#!/usr/bin/env python3
"""Fail when a file added under vllm/a2sys/ is a copy of an upstream file.

A copy stops receiving upstream bugfixes and nothing ever reports the divergence, which is
the failure the whole A/B/C split exists to prevent. Merge conflicts are the mechanism that
pulls those fixes in, and a copy has none — so derived code is edited in place under vllm/
instead. See vllm/a2sys/CLAUDE.md.

vllm/a2sys/vendor/ is exempt: it is the sanctioned copy, kept honest by a pinned _base/.
"""

import difflib
import subprocess
import sys
from pathlib import Path

THRESHOLD = 0.60
EXEMPT_PREFIX = "vllm/a2sys/vendor/"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def added_a2sys_files(base: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=A", f"{base}...HEAD", "--", "vllm/a2sys/")
    return [p for p in out.splitlines() if p and not p.startswith(EXEMPT_PREFIX)]


def upstream_candidates() -> dict[str, list[str]]:
    """Upstream paths under vllm/, indexed by basename."""
    index: dict[str, list[str]] = {}
    for path in git("ls-tree", "-r", "--name-only", "upstream/main", "vllm/").splitlines():
        if path.endswith(".py"):
            index.setdefault(Path(path).name, []).append(path)
    return index


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    new_files = added_a2sys_files(base)
    if not new_files:
        print("No new files under vllm/a2sys/.")
        return 0

    index = upstream_candidates()
    findings = []

    for path in new_files:
        name = Path(path).name
        # Compare against upstream files sharing a basename, plus the whole tree when the
        # name was deliberately changed to hide the origin.
        candidates = index.get(name, [])
        if not candidates:
            stem = Path(path).stem.replace("_a2sys", "").replace("_copy", "")
            candidates = [p for p in sum(index.values(), []) if Path(p).stem == stem]
        if not candidates:
            continue

        ours = Path(path).read_text(errors="replace")
        for upstream_path in candidates:
            theirs = git("show", f"upstream/main:{upstream_path}")
            ratio = difflib.SequenceMatcher(None, ours, theirs).quick_ratio()
            if ratio < THRESHOLD:
                continue
            ratio = difflib.SequenceMatcher(None, ours, theirs).ratio()
            if ratio >= THRESHOLD:
                findings.append((path, upstream_path, ratio))

    if not findings:
        print(f"Checked {len(new_files)} new file(s). No copies found.")
        return 0

    print("::error::Upstream files appear to have been copied into vllm/a2sys/.")
    for ours, theirs, ratio in sorted(findings, key=lambda f: -f[2]):
        print(f"::error file={ours}::{ours} is {ratio:.0%} similar to {theirs}")
    print()
    print("Edit the upstream file in place instead (category B), so merge conflicts keep")
    print("pulling upstream fixes in. If physical separation is unavoidable, use")
    print("vllm/a2sys/vendor/ with a pinned _base/ — see vllm/a2sys/CLAUDE.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
