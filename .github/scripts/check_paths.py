#!/usr/bin/env python3
"""Fail when the diff touches a path the fork policy forbids.

Compares against the merge-base with the base branch, so only OUR changes are considered.
Upstream commits arriving through the daily sync merge are excluded by construction: after
a merge, the merge-base IS the upstream commit we integrated.

This is why a GitHub push ruleset cannot do this job. Push rules see every commit in the
push, including the hundreds of upstream commits a sync brings in, and those legitimately
touch csrc/.
"""

import subprocess
import sys
from pathlib import Path

import yaml

POLICY = Path(".github/a2sys-policy.yml")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    policy = yaml.safe_load(POLICY.read_text())

    changed = [p for p in git("diff", "--name-only", f"{base}...HEAD").splitlines() if p]
    if not changed:
        print("No changes.")
        return 0

    failures: list[str] = []

    for path in changed:
        for tree in policy["forbidden_trees"]:
            if path.startswith(tree):
                failures.append(f"{path}: {tree} is off limits (neither edit nor add)")
        if path in policy["forbidden_files"]:
            failures.append(f"{path}: this upstream file must not be edited")

    for path, rule in (policy.get("restricted_files") or {}).items():
        if path not in changed:
            continue
        import re

        allowed = re.compile(rule["allowed_pattern"])
        diff = git("diff", f"{base}...HEAD", "--", path)
        stray = [
            line
            for line in diff.splitlines()
            if line[:1] in "+-"
            and not line.startswith(("+++", "---"))
            and not allowed.search(line)
        ]
        if stray:
            failures.append(
                f"{path}: only the entry-point block may change; "
                f"{len(stray)} other line(s) differ"
            )

    if not failures:
        print(f"Checked {len(changed)} changed file(s). No forbidden paths touched.")
        return 0

    print("::error::The diff touches paths the fork policy forbids.")
    for f in failures:
        print(f"::error::{f}")
    print()
    print("See .github/a2sys-policy.yml. New CUDA kernels belong in vllm/a2sys/ops/ as a")
    print("separate torch extension; configuration belongs under --additional-config.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
