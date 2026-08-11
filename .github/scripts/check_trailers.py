#!/usr/bin/env python3
"""N3 — every commit that touches an upstream file declares when it can be deleted.

GitHub rulesets have no commit-message rule, so this lives in CI.

A B or C commit is debt. Debt without a stated payoff condition becomes permanent by
default, so each one carries:

    Upstream-status: not-submitted | submitted <url> | merged-in <version>
    Removable-when:  <condition>

Only MODIFYING a file that exists upstream creates that debt. Adding a new file creates
none — an added file has no upstream original to drift from, which is the definition of
category A. So the rule is not "under vllm/" but "does upstream/main have this path":
.github/PULL_REQUEST_TEMPLATE.md is upstream's too, and editing it is just as much a B as
editing a model file.
"""

import subprocess
import sys
from pathlib import Path

import yaml

POLICY = Path(".github/a2sys-policy.yml")
REQUIRED = ("Upstream-status:", "Removable-when:")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def exists_upstream(path: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"upstream/main:{path}"],
            capture_output=True,
        ).returncode
        == 0
    )


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    ours = yaml.safe_load(POLICY.read_text())["ours_prefix"]

    shas = git("log", "--no-merges", "--format=%H", f"{base}..HEAD").split()
    if not shas:
        print("No commits of ours to check.")
        return 0

    failures: list[str] = []
    checked = 0

    for sha in shas:
        # M/D/R only: an added file has no upstream original, so it carries no debt.
        rows = git(
            "show", "--name-status", "--diff-filter=MDR", "--format=", sha
        ).splitlines()
        modified = [r.split("\t")[-1] for r in rows if r.strip()]
        touched = [
            f for f in modified if not f.startswith(ours) and exists_upstream(f)
        ]
        if not touched:
            continue
        checked += 1
        body = git("show", "--no-patch", "--format=%B", sha)
        missing = [t for t in REQUIRED if t not in body]
        if missing:
            subject = git("show", "--no-patch", "--format=%s", sha).strip()
            failures.append(f"{sha[:10]} {subject} — missing {', '.join(missing)}")

    if not failures:
        print(f"{checked} commit(s) touch upstream files. All carry trailers.")
        return 0

    print("::error::Commits touching upstream files are missing required trailers.")
    for f in failures:
        print(f"::error::{f}")
    print()
    print("Add to the commit message:")
    print("  Upstream-status: not-submitted | submitted <url> | merged-in <version>")
    print("  Removable-when:  <the condition under which this commit is dropped>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
