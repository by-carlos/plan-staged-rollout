#!/usr/bin/env python3
"""Fail when a link or section anchor in a tracked Markdown file does not
resolve. Covers inline links, images, reference definitions and HTML href
attributes; skips fenced code blocks and inline code. External URLs are not
fetched. Anchors are checked against the GitHub heading slugs of the target
file (and its explicit id/name anchors).
"""

import posixpath
import re
import sys
from urllib.parse import unquote

from checklib import read_text, report, tracked_files

INLINE_RE = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFDEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
HREF_RE = re.compile(r"""href=["']([^"']+)["']""")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR_RE = re.compile(r"""<a\s[^>]*?(?:id|name)=["']([^"']+)["']""")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
CODE_SPAN_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "ftp:", "data:")


def prose_lines(text):
    """Yield (line number, line) outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None:
            yield number, line


def slugify(heading):
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = CODE_SPAN_RE.sub(lambda m: m.group(0).strip("`").replace("<", "").replace(">", ""), text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "").replace("*", "")
    text = re.sub(r"(?<!\w)_|_(?!\w)", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors_of(text):
    """The set of anchors a Markdown file offers."""
    found = set()
    counts = {}
    for _, line in prose_lines(text):
        match = HEADING_RE.match(line)
        if match:
            slug = slugify(match.group(2))
            n = counts.get(slug, 0)
            counts[slug] = n + 1
            found.add(slug if n == 0 else f"{slug}-{n}")
        found.update(HTML_ANCHOR_RE.findall(line))
    return found


def targets_of(text):
    """Yield (line number, raw link target) for every link in the file."""
    for number, line in prose_lines(text):
        line = CODE_SPAN_RE.sub("", line)
        raw = INLINE_RE.findall(line) + HREF_RE.findall(line)
        ref = REFDEF_RE.match(line)
        if ref:
            raw.append(ref.group(1))
        for target in raw:
            yield number, target.strip("<>")


def check_files(markdown, all_paths):
    """markdown: {path: text}; all_paths: every tracked path. Returns hits."""
    dirs = {posixpath.dirname(p) for p in all_paths}
    for p in list(dirs):
        while p:
            p = posixpath.dirname(p)
            dirs.add(p)
    cache = {}

    def anchors(path):
        if path not in cache:
            cache[path] = anchors_of(markdown[path])
        return cache[path]

    hits = []
    for path, text in markdown.items():
        for number, target in targets_of(text):
            if not target or target.lower().startswith(EXTERNAL):
                continue
            base, _, fragment = target.partition("#")
            base = unquote(base.split("?", 1)[0])
            fragment = unquote(fragment)
            if base:
                if base.startswith("/"):
                    resolved = posixpath.normpath(base.lstrip("/"))
                else:
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), base))
                if resolved.startswith(".."):
                    hits.append((path, number, f"link '{target}' leaves the repository"))
                    continue
                if resolved == ".":
                    resolved = ""
                if resolved not in all_paths and resolved not in dirs:
                    hits.append((path, number, f"broken link '{target}'"))
                    continue
            else:
                resolved = path
            if fragment and resolved in markdown and fragment.lower() not in anchors(resolved):
                hits.append((path, number, f"broken anchor '{target}' (no such section in {resolved})"))
    return hits


def main():
    all_paths = set(tracked_files())
    markdown = {}
    for path in sorted(all_paths):
        if path.lower().endswith(".md"):
            text = read_text(path)
            if text is not None:
                markdown[path] = text
    return report("check-links", check_files(markdown, all_paths))


if __name__ == "__main__":
    sys.exit(main())
