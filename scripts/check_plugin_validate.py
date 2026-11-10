#!/usr/bin/env python3
"""Run `claude plugin validate --strict` and fail on anything except the one
known warning: CLAUDE.md at the plugin root. That file is this repository's
own project instructions, not plugin context, so the warning is expected.

The CLI comes from the CI step that installs a pinned @anthropic-ai/claude-code;
set CLAUDE_BIN to use a different executable.
"""

import os
import shutil
import subprocess
import sys

from checklib import ROOT, report

ALLOWED = "CLAUDE.md at the plugin root"
STRICT_SUMMARY = "Validation failed (--strict treats warnings as errors)"


def findings(output):
    """The lines that report a warning or error, minus the strict summary."""
    lines = [line.strip() for line in output.splitlines()]
    found = [line for line in lines if line.startswith("❯")]
    found += [line for line in lines if line.startswith("✘") and STRICT_SUMMARY not in line]
    return found


def judge(returncode, output):
    """Hits for one run of the validator: [] means pass."""
    found = findings(output)
    unexpected = [line for line in found if ALLOWED not in line]
    hits = [("claude plugin validate", 0, line) for line in unexpected]
    if returncode != 0 and not found:
        hits.append(("claude plugin validate", 0, f"exit {returncode} with no finding to explain it"))
    return hits


def main():
    claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if not claude:
        print("check-plugin-validate: the claude CLI is not on PATH (set CLAUDE_BIN)")
        return 2
    result = subprocess.run(
        [claude, "plugin", "validate", "--strict", "."],
        cwd=ROOT,
        capture_output=True,
    )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    print(output)
    return report("check-plugin-validate", judge(result.returncode, output))


if __name__ == "__main__":
    sys.exit(main())
