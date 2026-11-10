#!/usr/bin/env python3
"""Check the docs against the commands and skills they describe.

Truth sources: commands/*.md and skills/*/SKILL.md. Three checks:

1. Every command in commands/ has an entry in docs/reference.md: a table row
   whose first cell starts with `/<command>`, and the row (or the entry) names
   every `--flag` in the command's argument-hint.
2. A slash name that looks like one of this plugin's (it starts with `plan-`,
   `stage-`, `work-`, `create-`, `triage-` or `staged-`, optionally behind
   `plan-staged-rollout:`) must be a command or a skill that exists.
3. A flag written after a known command or skill in an invocation
   (`/stage-run 3 --unattended`) must appear in that command's or skill's
   own file.

Searched: every tracked Markdown file except CHANGELOG.md and DECISIONS.md,
which record history.
"""

import re
import sys

from checklib import HISTORY_FILES, ROOT, read_text, report, tracked_files

NAMESPACE = "plan-staged-rollout"
PLUGIN_PREFIXES = ("plan-", "stage-", "work-", "create-", "triage-", "staged-")
SLASH_RE = re.compile(r"(?<![\w/.:<-])/(?:plan-staged-rollout:)?([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![\w/.:-])([^`\n\"]*)")
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
HINT_RE = re.compile(r"^argument-hint:\s*(.*)$", re.MULTILINE)
REFERENCE = "docs/reference.md"


def truth(paths, texts):
    """{name: file text} for every command and skill."""
    sources = {}
    for path in paths:
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == "commands" and path.endswith(".md"):
            sources[parts[1][:-3]] = texts[path]
        elif len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            sources[parts[1]] = texts[path]
    return sources


def reference_hits(sources, reference_text, commands):
    hits = []
    rows = {}
    for number, line in enumerate(reference_text.splitlines(), 1):
        match = re.match(r"^\|\s*`/([a-z][a-z0-9-]*)", line)
        if match:
            rows[match.group(1)] = (number, line)
    for name in sorted(commands):
        if name not in rows:
            hits.append((REFERENCE, 1, f"no entry for command /{name}"))
            continue
        number, row = rows[name]
        hint = HINT_RE.search(sources[name])
        for flag in sorted(set(FLAG_RE.findall(hint.group(1) if hint else ""))):
            if flag not in row:
                hits.append((REFERENCE, number, f"entry for /{name} does not name its flag {flag}"))
    for name, (number, _) in rows.items():
        if name not in commands:
            hits.append((REFERENCE, number, f"entry for /{name}, which is not a command"))
    return hits


def doc_hits(path, text, sources):
    hits = []
    known = set(sources) | {NAMESPACE}
    for number, line in enumerate(text.splitlines(), 1):
        for match in SLASH_RE.finditer(line):
            name, rest = match.group(1), match.group(2)
            if name not in known:
                if name.startswith(PLUGIN_PREFIXES):
                    hits.append((path, number, f"names /{name}, which is not a command or skill"))
                continue
            if name == NAMESPACE:
                continue
            for flag in FLAG_RE.findall(rest):
                if flag not in sources[name]:
                    hits.append((path, number, f"/{name} is given {flag}, which its file does not have"))
    return hits


def main():
    paths = [p for p in tracked_files() if p.endswith(".md")]
    texts = {p: read_text(p) for p in paths}
    texts = {p: t for p, t in texts.items() if t is not None}
    sources = truth(texts, texts)
    commands = {p.split("/")[1][:-3] for p in texts if p.startswith("commands/") and p.count("/") == 1}

    hits = []
    if REFERENCE in texts:
        hits.extend(reference_hits(sources, texts[REFERENCE], commands))
    else:
        hits.append((REFERENCE, 1, "file not found"))
    for path, text in texts.items():
        if path not in HISTORY_FILES:
            hits.extend(doc_hits(path, text, sources))
    return report("check-docs-truth", hits)


if __name__ == "__main__":
    sys.exit(main())
