#!/usr/bin/env python3
"""Print one version's CHANGELOG.md section, for use as GitHub release notes.

Run by .github/workflows/release-publish.yml after release-prepare.yml's PR
has merged, so the section it reads is the one that PR just dated.
"""

import argparse
import re
import sys
from pathlib import Path

from changelog_lib import repo_slug, section_body

CHANGELOG = Path("CHANGELOG.md")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-file")
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
    repo = repo_slug()
    output = f"{body}\n\nFull history: https://github.com/{repo}/blob/main/CHANGELOG.md\n"

    if args.output_file:
        Path(args.output_file).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
