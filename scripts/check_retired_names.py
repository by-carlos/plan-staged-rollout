#!/usr/bin/env python3
"""Fail when a retired command name still appears in a tracked file.

Searches every tracked text file (SVG labels included), except the history
files (CHANGELOG.md, DECISIONS.md) and this script's own tests. Each retired
name is a regex, matched so a longer current name does not hit: `/plan-run`
must not match `/plan-run-local` or `/plan-run-cloud`.

To retire another name, add it to RETIRED with the name that replaced it.
"""

import re
import sys

from checklib import HISTORY_FILES, read_text, report, tracked_files

# (pattern, replaced by). Names come from the CHANGELOG history.
RETIRED = [
    (re.compile(r"/plan-run(?![-\w])"), "/plan-run-local or /plan-run-cloud"),
    (re.compile(r"/triage-issue(?![-\w])"), "/triage-issues"),
]

SKIP_PREFIXES = ("scripts/tests/",)
SKIP_FILES = HISTORY_FILES | {"scripts/check_retired_names.py"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2"}


def find_hits(path, text):
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, replacement in RETIRED:
            match = pattern.search(line)
            if match:
                hits.append((path, number, f"retired name '{match.group(0)}' (now {replacement})"))
    return hits


def main():
    hits = []
    for path in tracked_files():
        if path in SKIP_FILES or path.startswith(SKIP_PREFIXES):
            continue
        if "." + path.rsplit(".", 1)[-1].lower() in BINARY_SUFFIXES:
            continue
        text = read_text(path)
        if text is not None:
            hits.extend(find_hits(path, text))
    return report("check-retired-names", hits)


if __name__ == "__main__":
    sys.exit(main())
