#!/usr/bin/env python3
"""Compare the files a stage changed against the paths its `## Artifacts` declares.

The finish protocol runs this from the stage worktree and pastes its one line
into the stage's ledger notes. It is a record, never a gate: a stage touching a
file nobody listed is routine more often than not, and the final review judges
each `outside` line against the stage's Goal and the plan's Outcome.

Usage (from the stage worktree):

    python <path>/artifacts_check.py --stage-file .plan/<stage file> --base origin/plan-<slug>

It prints one line and exits 0:

    Artifacts check: match
    Artifacts check: undeclared
    Artifacts check: outside: <path>, <path>, ...

What a stage changed. Every tracked file that differs between the merge base of
`--base` and HEAD and the working tree, plus untracked files git does not
ignore. Files under `.plan/` and `.gitkeep` placeholders are left out: the
ledger and the stage file always change, and an empty-directory marker is not
work.

What a stage declared. `## Artifacts` is free prose, so only its backticked
spans are read, with `{a,b}` lists expanded. A span counts as a path when it
contains `/` or looks like `name.ext`, and does not start with `-` (a flag),
`[` (a config key), `/` or `~` (a path outside the repository). A path ending
in `/` covers everything under it; `*` and `?` match as shell globs. Anything
else in the section (a dependency name, a secret's description, a sentence
that forbids a file) is ignored. A section with no path at all is
`undeclared`: the comparison is skipped, and that is never a mismatch.

Exit codes
----------
  0  the line was printed
  2  failed (no stage file, no such base, not a git work tree)
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^## Artifacts[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
SPAN_RE = re.compile(r"`([^`\n]+)`")
BRACE_RE = re.compile(r"\{([^{}]*,[^{}]*)\}")
FILE_RE = re.compile(r"[\w.-]*\w\.\w+")
NOT_A_PATH = ("-", "[", "/", "~")


def fail(message: str) -> None:
    print(f"artifacts_check: {message}", file=sys.stderr)
    sys.exit(2)


def expand(span: str) -> list[str]:
    """Expand the first `{a,b}` list in a span, then the rest, recursively."""
    match = BRACE_RE.search(span)
    if not match:
        return [span]
    head, tail = span[: match.start()], span[match.end():]
    out: list[str] = []
    for choice in match.group(1).split(","):
        out.extend(expand(head + choice.strip() + tail))
    return out


def declared_paths(stage_text: str) -> list[str]:
    """The repository paths the stage's `## Artifacts` section names."""
    section = SECTION_RE.search(stage_text)
    if not section:
        return []
    paths: list[str] = []
    for span in SPAN_RE.findall(section.group(1)):
        for token in expand(span.strip()):
            if not token or token.startswith(NOT_A_PATH) or re.search(r"\s", token):
                continue
            if token.startswith("./"):
                token = token[2:]
            if "/" in token or FILE_RE.fullmatch(token):
                paths.append(token)
    return paths


def covered(path: str, declared: list[str]) -> bool:
    for entry in declared:
        if entry.endswith("/"):
            if path.startswith(entry):
                return True
        elif any(ch in entry for ch in "*?"):
            if fnmatch.fnmatchcase(path, entry):
                return True
        elif path == entry:
            return True
    return False


def counted(path: str) -> bool:
    """False for the files no stage declares: the plan itself and placeholders."""
    return not (path.startswith(".plan/") or Path(path).name == ".gitkeep")


def classify(declared: list[str], changed: list[str]) -> str:
    """The ledger line for a stage's declared paths and its changed files."""
    if not declared:
        return "Artifacts check: undeclared"
    outside = [p for p in changed if counted(p) and not covered(p, declared)]
    if not outside:
        return "Artifacts check: match"
    return "Artifacts check: outside: " + ", ".join(outside)


def git(top: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(top), *args], capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode != 0:
        fail(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def changed_files(top: Path, base: str) -> list[str]:
    fork = git(top, "merge-base", base, "HEAD").strip()
    tracked = git(top, "diff", "--name-only", "--no-renames", fork).splitlines()
    untracked = git(top, "ls-files", "--others", "--exclude-standard", "--full-name").splitlines()
    return sorted(set(p for p in tracked + untracked if p))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage-file", required=True, help="the stage's file under .plan/")
    parser.add_argument("--base", required=True, help="the plan branch, e.g. origin/plan-<slug>")
    args = parser.parse_args(argv)

    stage = Path(args.stage_file)
    if not stage.is_file():
        fail(f"no stage file at {stage}")
    probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True, encoding="utf-8")
    if probe.returncode != 0:
        fail("not inside a git work tree")
    top = Path(probe.stdout.strip())

    declared = declared_paths(stage.read_text(encoding="utf-8"))
    changed = changed_files(top, args.base) if declared else []
    print(classify(declared, changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
