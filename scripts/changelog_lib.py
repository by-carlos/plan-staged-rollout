"""Shared helpers for the release scripts."""

import os
import re
import subprocess
import sys

HEADING_RE = re.compile(r"^## \[", re.MULTILINE)
REMOTE_SLUG_RE = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$")


def section_body(text, body_start):
    """Return the trimmed body of the section that starts at body_start.

    body_start is the offset right after a `## [...]` heading line; the
    section runs up to the next `## [...]` heading or end of file.
    """
    next_heading = HEADING_RE.search(text, body_start)
    body_end = next_heading.start() if next_heading else len(text)
    return text[body_start:body_end].strip("\n")


def repo_slug():
    """Return `owner/repo` for the repository these scripts are running in.

    Read from GITHUB_REPOSITORY, which Actions always sets, and derived from
    the origin remote otherwise so the scripts also work in a local checkout.
    Deriving it rather than hardcoding it is what lets this file be copied
    between repositories unchanged.
    """
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug

    url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    match = REMOTE_SLUG_RE.search(url)
    if not match:
        sys.exit(f"could not derive owner/repo from the origin remote: {url}")
    return match.group(1)
