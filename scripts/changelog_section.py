#!/usr/bin/env python3
"""Print one version's CHANGELOG.md section, for use as GitHub release notes.

Run by .github/workflows/release-publish.yml after release-prepare.yml's PR
has merged, so the section it reads is the one that PR just dated.

The section body may start with a `**Codename:** <name>` line -- a one-off,
hand-edited addition to that release's CHANGELOG.md section, not something
release-prepare.yml writes. When present it is stripped from the notes body
and surfaced separately via --github-output so the caller can fold it into
the release title.
"""

import argparse
import re
import sys
from pathlib import Path

from changelog_lib import repo_slug, section_body

CHANGELOG = Path("CHANGELOG.md")
CODENAME_RE = re.compile(r"^\*\*Codename:\*\* (.+)\n?", re.MULTILINE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-file")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    text = CHANGELOG.read_text(encoding="utf-8")
    heading = re.search(
        rf"^## \[{re.escape(args.version)}\] - \d{{4}}-\d{{2}}-\d{{2}}[ \t]*$",
        text,
        re.MULTILINE,
    )
    if not heading:
        sys.exit(f"CHANGELOG.md has no section for {args.version}")

    body = section_body(text, heading.end())

    codename = None
    codename_match = CODENAME_RE.match(body)
    if codename_match:
        codename = codename_match.group(1).strip()
        body = body[codename_match.end() :].lstrip("\n")

    repo = repo_slug()
    output = f"{body}\n\nFull history: https://github.com/{repo}/blob/main/CHANGELOG.md\n"

    if args.output_file:
        Path(args.output_file).write_text(output, encoding="utf-8")
    else:
        print(output)

    if args.github_output and codename:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"codename={codename}\n")


if __name__ == "__main__":
    main()
