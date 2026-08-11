#!/usr/bin/env python3
"""G1b + G3 — keep seams small, declared, and covered by a contract test.

A seam (C) is a hook of a few lines in an upstream file that calls into vllm/a2sys/. Two
things go wrong with seams, and both are mechanical to check:

  G1b  the hook grows until it is really an in-place rewrite wearing a seam's name
  G3   the hook stops being reached, and nothing notices, because vLLM ignores
       unsupported configuration silently rather than raising

So: every seam is declared in seams/registry.yml, its hunks are capped, and each one
carries a contract test whose job is to assert OUR CODE RAN — not that output is correct.
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

POLICY = Path(".github/a2sys-policy.yml")
REGISTRY = Path("seams/registry.yml")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,(\d+))? @@")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def changed_lines_per_hunk(base: str, path: str) -> list[int]:
    """Added/removed line counts, one entry per hunk."""
    diff = git("diff", "--unified=0", f"{base}...HEAD", "--", path)
    counts: list[int] = []
    for line in diff.splitlines():
        if HUNK.match(line):
            counts.append(0)
        elif counts and line[:1] in "+-" and not line.startswith(("+++", "---")):
            counts[-1] += 1
    return counts


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    policy = yaml.safe_load(POLICY.read_text())
    budget = policy["budget"]
    ours = policy["ours_prefix"]

    registry = yaml.safe_load(REGISTRY.read_text()) or {}
    seams = registry.get("seams") or []

    failures: list[str] = []

    if len(seams) > budget["max_seams"]:
        failures.append(
            f"{len(seams)} seams declared, budget is {budget['max_seams']}. "
            "Push some upstream or fold them back into B before adding more."
        )

    seen_ids: set[str] = set()
    for entry in seams:
        sid = entry.get("id", "<missing id>")
        if sid in seen_ids:
            failures.append(f"{sid}: duplicate id")
        seen_ids.add(sid)

        for field in ("id", "file", "why", "test", "upstream", "removable_when"):
            if not entry.get(field):
                failures.append(f"{sid}: missing required field `{field}`")

        seam_file = entry.get("file", "")
        if seam_file.startswith(ours):
            failures.append(
                f"{sid}: {seam_file} is our own code, not an upstream file. "
                "A seam only exists to reach into an upstream file."
            )

        # G3 — the contract test must exist. Whether it passes is the test job's problem.
        test = entry.get("test", "")
        if test and not Path(test).exists():
            failures.append(f"{sid}: contract test {test} does not exist")

        # G1b — cap the hook size.
        if seam_file and Path(seam_file).exists():
            for n, size in enumerate(changed_lines_per_hunk(base, seam_file), 1):
                if size > budget["max_seam_hunk_lines"]:
                    failures.append(
                        f"{sid}: {seam_file} hunk {n} changes {size} lines, "
                        f"budget is {budget['max_seam_hunk_lines']}. "
                        "Move the body into vllm/a2sys/ and leave only the call."
                    )

    # An upstream file edited by this PR that is not declared as a seam is B, which is
    # allowed and unbudgeted — but a seam-shaped edit hiding as B skips G3, so surface
    # small edits for the reviewer rather than failing on them.
    declared = {e.get("file") for e in seams}
    small_undeclared = []
    modified = git(
        "diff", "--name-only", "--diff-filter=M", f"{base}...HEAD", "--", "vllm/"
    ).splitlines()
    for path in modified:
        if not path or path.startswith(ours) or path in declared:
            continue
        hunks = changed_lines_per_hunk(base, path)
        if hunks and all(h <= budget["max_seam_hunk_lines"] for h in hunks):
            small_undeclared.append(f"{path} ({sum(hunks)} lines)")

    if small_undeclared:
        print("::notice::Small undeclared edits to upstream files. If any of these is a")
        print("::notice::hook into vllm/a2sys/, declare it in seams/registry.yml so G3")
        print("::notice::requires a contract test for it.")
        for item in small_undeclared:
            print(f"::notice::  {item}")

    if not failures:
        print(f"{len(seams)} seam(s) declared. All within budget and covered.")
        return 0

    print("::error::Seam registry violations.")
    for f in failures:
        print(f"::error::{f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
