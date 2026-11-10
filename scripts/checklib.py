"""Shared helpers for the repository check scripts (retired names, links,
docs truth table). Standard library only; every file is read as UTF-8."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# History files record old names on purpose, so they never count as hits.
HISTORY_FILES = {"CHANGELOG.md", "DECISIONS.md"}


def tracked_files():
    """Repo-relative POSIX paths of every file git tracks."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    return [name.decode("utf-8") for name in out if name]


def read_text(rel):
    """The file's text, or None when it is not valid UTF-8 (binary)."""
    try:
        return (ROOT / rel).read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def report(tool, hits):
    """Print one `path:line: message` per hit and return the exit code."""
    for path, line, message in hits:
        print(f"{path}:{line}: {message}")
    if hits:
        print(f"{tool}: {len(hits)} hit(s)")
        return 1
    print(f"{tool}: OK")
    return 0
