#!/usr/bin/env python3
"""Pick the final plan PR's merge method from what the repository allows.

Bootstrap runs `decide` once and records the answer as the `final-merge` plan
flag; closeout runs `line` to word the final PR body's merge line from that
flag. Neither guesses: an unreadable lookup is `unchecked`, and a repository
that offers neither a merge commit nor a squash is a question for the person.

Usage:

    python <path>/final_merge.py decide --repo-json <file> --rules-json <file>
    python <path>/final_merge.py line --method merge|squash|unchecked

`--repo-json` is the output of `gh api repos/<owner>/<repo>` (the three
`allow_*_merge` booleans). `--rules-json` is the output of
`gh api repos/<owner>/<repo>/rules/branches/<default>`; every `pull_request`
rule's `allowed_merge_methods` narrows what the settings allow. Both files are
written by the caller, so a failed `gh` call is an absent or unreadable file,
and a missing `--rules-json` counts as one: a repository with no rules returns
a readable `[]`.

`decide` prints one word and exits 0:

    merge       a merge commit is allowed, so each stage keeps its own commit
    squash      only squash (no merge commit): the history stays in stage PRs
    ask         only rebase, or nothing, is allowed: stop and ask the person
    unchecked   a file was missing or unreadable, or the settings lack the keys

`line` prints the sentence that goes near the top of the final PR body, and
exits 2 on any other method name.

Exit codes
----------
  0  the word or line was printed
  2  bad arguments
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SETTINGS = (
    ("merge", "allow_merge_commit"),
    ("squash", "allow_squash_merge"),
    ("rebase", "allow_rebase_merge"),
)

LINES = {
    "merge": (
        "**Merge method: normal merge (merge commit), not squash.** Each stage's "
        "squashed commit lands on the default branch as its own commit; "
        "\"Squash and merge\" would collapse them into one."
    ),
    "squash": (
        "**Merge method: squash merge.** This repository does not allow a merge "
        "commit into its default branch, so the final PR lands as one commit and "
        "the stage history stays in the merged stage PRs."
    ),
    "unchecked": (
        "**Merge method: normal merge (merge commit), not squash.** Each stage's "
        "squashed commit lands on the default branch as its own commit; "
        "\"Squash and merge\" would collapse them into one. The repository's "
        "allowed merge methods were not checked, so confirm a merge commit is "
        "offered."
    ),
}


def read_json(path: str | None):
    """The parsed file, or None when it is absent or not valid JSON."""
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def allowed_methods(settings: dict, rules: list) -> set[str] | None:
    """The merge methods the settings and branch rules both allow.

    None when the settings do not carry the three booleans, so the caller
    reports `unchecked` instead of reading a missing key as "not allowed".
    """
    if not all(isinstance(settings.get(key), bool) for _, key in SETTINGS):
        return None
    allowed = {name for name, key in SETTINGS if settings[key]}
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "pull_request":
            continue
        methods = (rule.get("parameters") or {}).get("allowed_merge_methods")
        if isinstance(methods, list):
            allowed &= {m for m in methods if isinstance(m, str)}
    return allowed


def decide(settings, rules) -> str:
    if not isinstance(settings, dict) or not isinstance(rules, list):
        return "unchecked"
    allowed = allowed_methods(settings, rules)
    if allowed is None:
        return "unchecked"
    if "merge" in allowed:
        return "merge"
    if "squash" in allowed:
        return "squash"
    return "ask"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide", help="print merge, squash, ask or unchecked")
    d.add_argument("--repo-json", required=True)
    d.add_argument("--rules-json")
    ln = sub.add_parser("line", help="print the PR body's merge line")
    ln.add_argument("--method", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "line":
        if args.method not in LINES:
            print(f"final_merge: unknown method {args.method!r}; use "
                  f"{', '.join(LINES)}", file=sys.stderr)
            return 2
        print(LINES[args.method])
        return 0

    settings = read_json(args.repo_json)
    # No rules file is a lookup that failed, not "no rules": an empty rule
    # list (a readable `[]`) is what a repository without rulesets returns.
    rules = read_json(args.rules_json) if args.rules_json else None
    print(decide(settings, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
