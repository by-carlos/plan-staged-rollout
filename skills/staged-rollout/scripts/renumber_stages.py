#!/usr/bin/env python3
"""Renumber the unstarted stages of a `.plan/` after an edit to its stage index.

Stage IDs are plain numbers in running order (`S0`, `S1`, ...) plus `SF` for the
final review. When a stage is added or moved, the numbers after it go stale;
this script puts them right without touching a stage that has started.

Usage (from the repo root, on the stage branch that made the edit):

    python <path>/renumber_stages.py --slug <plan-slug> [--plan-dir .plan]

How the edit is expressed. The caller edits the stage index in `PLAN.md`: the
row order is the running order. A new stage gets a row, a `LEDGER.md` row and a
stage file under any plain ID not yet in use (the next free number is the
obvious one), placed where it should run. This script then assigns numbers.

What it does, in place and in one pass:

  * A stage is STARTED when its ledger status is not `todo`, when a
    `plan-<slug>-s<N>` branch exists (local or remote, redo branches included),
    or when `.plan/BLOCKED.md` has a `### S<N>` section for it. A started stage
    keeps its number -- it is already on branches, in PRs and in notes.
  * Every other stage, walking the index top to bottom, takes the next free
    plain number above the one before it. Stages that sit side by side in the
    index therefore get consecutive numbers, and a stage never ends up with a
    lower number than a stage it depends on (checked; otherwise it refuses).
  * It renames the stage files and rewrites every `S<N>` reference in
    `PLAN.md` (the index, `depends` cells, prose), `LEDGER.md`, `BLOCKED.md`
    and the stage files, all from one mapping, so a swap of two numbers cannot
    collide.

What it does not do. It does not touch `.plan/BRIEF.md`: the caller
regenerates the brief in the same commit. It does not reorder ledger rows or
notes blocks. There is no insert mode and no dry-run flag; git on the stage
branch is the undo. A bare `S3` in prose that means something else (a storage
service, say) is rewritten like any other reference -- review the diff.

Untrusted input. The index is plain text anyone with a pen could edit, so every
ID and `File` cell is checked against the grammar, every path must stay inside
the plan directory and may not be a symlink, and every refusal happens before
the first write. A suffixed ID is read when the stage has started (plans in
flight keep running) and refused otherwise: this script never creates one.

Exit codes
----------
  0  renumbered, or nothing to do
  2  refused or failed (the message says why; nothing was written)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ID_RE = re.compile(r"S(\d+)([a-z]?)|SF")
CELL_ID_RE = re.compile(r"(S\d+[a-z]?|SF)(?:\s|$)")
FILE_CELL_RE = re.compile(r"`stage-(\d+[a-z]?|f)-([a-z0-9][a-z0-9-]*)\.md`")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
# An ID in prose: not glued to a word, so `AES256` or `Stages` never match.
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])S(\d+[a-z]?)(?![A-Za-z0-9_])")
FILENAME_RE = re.compile(r"stage-\d+[a-z]?-[a-z0-9][a-z0-9-]*\.md")
NO_DEPENDS = {"", "—", "–", "-"}


class Refusal(Exception):
    """A reason to stop before writing anything."""


class Stage:
    def __init__(self, sid, file_slug, depends):
        self.id = sid
        self.file_slug = file_slug
        self.depends = depends
        m = ID_RE.fullmatch(sid)
        self.num = int(m.group(1)) if m.group(1) else None
        self.letter = (m.group(2) or "") if m.group(1) else ""
        self.status = None
        self.started = False
        self.new_num = None

    @property
    def is_final(self):
        return self.id == "SF"

    @property
    def old_file(self):
        return f"stage-{self.id[1:].lower()}-{self.file_slug}.md"

    def final_id(self):
        if self.new_num is None:
            return self.id
        return f"S{self.new_num}"

    def final_key(self):
        if self.is_final:
            return (float("inf"), "")
        if self.new_num is not None:
            return (self.new_num, "")
        return (self.num, self.letter)

    @property
    def new_file(self):
        return f"stage-{self.final_id()[1:].lower()}-{self.file_slug}.md"


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_index(text):
    lines = text.splitlines()
    start = next(
        (i for i, l in enumerate(lines) if l.startswith("## Stage index")), None
    )
    if start is None:
        raise Refusal("PLAN.md has no '## Stage index' section")
    stages, seen_files = [], set()
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if stages:
                break
            continue
        cells = split_row(line)
        if cells[0] == "Stage" or set(cells[0]) <= set("-: "):
            continue
        if len(cells) < 3:
            raise Refusal(f"stage index row has too few cells: {line.strip()!r}")
        m = CELL_ID_RE.match(cells[0])
        if not m:
            raise Refusal(
                f"stage cell does not start with an ID (S<number> or SF): {cells[0]!r}"
            )
        sid = m.group(1)
        fm = FILE_CELL_RE.fullmatch(cells[1])
        if not fm:
            raise Refusal(
                f"{sid}: File cell {cells[1]!r} is outside the grammar "
                "`stage-<id>-<slug>.md` (lowercase letters, digits and dashes only)"
            )
        if fm.group(1) != sid[1:].lower():
            raise Refusal(f"{sid}: File cell {cells[1]!r} names a different stage ID")
        deps = []
        if cells[2] not in NO_DEPENDS:
            for d in (c.strip() for c in cells[2].split(",")):
                if not re.fullmatch(r"S\d+[a-z]?", d):
                    raise Refusal(f"{sid}: Depends cell has {d!r}, which is not a stage ID")
                deps.append(d)
        stage = Stage(sid, fm.group(2), deps)
        if any(s.id == sid for s in stages):
            raise Refusal(f"{sid} appears twice in the stage index")
        if stage.old_file in seen_files:
            raise Refusal(f"{stage.old_file} appears twice in the stage index")
        seen_files.add(stage.old_file)
        stages.append(stage)
    if not stages:
        raise Refusal("the stage index has no rows")
    return stages


def parse_ledger(text):
    statuses, in_status = {}, False
    for line in text.splitlines():
        if line.startswith("## "):
            in_status = line.startswith("## Status")
            continue
        if in_status and line.startswith("|"):
            cells = split_row(line)
            m = CELL_ID_RE.match(cells[0]) if len(cells) >= 2 else None
            if m:
                statuses[m.group(1)] = cells[1].lower()
    return statuses


def blocked_ids(text):
    return set(re.findall(r"^###\s+(S\d+[a-z]?|SF)\b", text, re.M))


def branch_stage_ids(repo, slug):
    """Stage IDs that have a `plan-<slug>-s<N>` branch, local or remote."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "for-each-ref", "--format=%(refname)",
         "refs/heads", "refs/remotes"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise Refusal(
            "cannot list branches to tell which stages have started: "
            + (proc.stderr.strip() or "git failed")
        )
    pat = re.compile(
        rf"refs/(?:heads/|remotes/[^/]+/)plan-{re.escape(slug)}-s(\d+[a-z]?)(?:-redo-\d+)?"
    )
    return {f"S{m.group(1)}" for r in proc.stdout.split() if (m := pat.fullmatch(r))}


def safe_file(plan_dir, name, must_exist=True):
    """The path of `name` inside `plan_dir`, or a Refusal."""
    path = plan_dir / name
    if path.is_symlink():
        raise Refusal(f"{name} is a symlink")
    if path.exists() and not path.is_file():
        raise Refusal(f"{name} is not a regular file")
    if must_exist and not path.exists():
        raise Refusal(f"{name} does not exist")
    try:
        path.resolve().relative_to(plan_dir.resolve())
    except ValueError:
        raise Refusal(f"{name} resolves outside {plan_dir}") from None
    return path


def read_text(path):
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal(f"{path.name} is not valid UTF-8") from None


def assign_numbers(stages, ledger, blocked, branch_ids):
    for s in stages:
        if s.id not in ledger:
            raise Refusal(f"{s.id} has no row in LEDGER.md, so its status is unknown")
        s.status = ledger[s.id]
        s.started = (
            s.status != "todo" or s.id in blocked or s.id in branch_ids or s.is_final
        )
        if not s.is_final and s.letter and not s.started:
            raise Refusal(
                f"{s.id} is a suffixed ID on a stage that has not started; "
                "suffixed IDs are never created"
            )
    finals = [i for i, s in enumerate(stages) if s.is_final]
    if finals and finals != [len(stages) - 1]:
        raise Refusal("SF must be the last row of the stage index")

    fixed_plain = {s.num for s in stages if s.started and not s.is_final and not s.letter}
    floor = -1
    for s in stages:
        if s.is_final:
            continue
        if s.started:
            floor = max(floor, s.num)
            continue
        n = floor + 1
        while n in fixed_plain:
            n += 1
        s.new_num = n
        floor = n

    keys = {s.id: s for s in stages}
    for s in stages:
        for d in s.depends:
            dep = keys.get(d)
            if dep is None:
                raise Refusal(f"{s.id} depends on {d}, which is not in the stage index")
            if dep.final_key() >= s.final_key():
                raise Refusal(
                    f"{s.id} would be numbered {s.final_id()} but depends on "
                    f"{dep.id} (numbered {dep.final_id()}): put {dep.id}'s row "
                    f"above {s.id}'s in the stage index"
                )


def rewrite(text, id_map, file_map):
    text = FILENAME_RE.sub(lambda m: file_map.get(m.group(0), m.group(0)), text)
    return TOKEN_RE.sub(lambda m: "S" + id_map.get(m.group(1), m.group(1)), text)


def write_atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def renumber(plan_dir, slug, branch_ids=None):
    """Renumber in place; returns [(old_id, new_id), ...] for the changed stages."""
    plan_dir = Path(plan_dir)
    if not SLUG_RE.fullmatch(slug):
        raise Refusal(f"plan slug {slug!r} is outside [a-z0-9-]")
    if plan_dir.is_symlink() or not plan_dir.is_dir():
        raise Refusal(f"{plan_dir} is not a plain directory")

    plan_path = safe_file(plan_dir, "PLAN.md")
    ledger_path = safe_file(plan_dir, "LEDGER.md")
    blocked_path = safe_file(plan_dir, "BLOCKED.md", must_exist=False)
    plan_text = read_text(plan_path)
    stages = parse_index(plan_text)
    blocked = blocked_ids(read_text(blocked_path)) if blocked_path.exists() else set()
    if branch_ids is None:
        branch_ids = branch_stage_ids(plan_dir.resolve().parent, slug)
    assign_numbers(stages, parse_ledger(read_text(ledger_path)), blocked, branch_ids)

    moved = [s for s in stages if s.new_file != s.old_file]
    id_map = {s.id[1:]: s.final_id()[1:] for s in stages if s.final_id() != s.id}
    file_map = {s.old_file: s.new_file for s in moved}

    sources = {s.id: safe_file(plan_dir, s.old_file) for s in stages}
    old_names = {s.old_file for s in moved}
    for s in moved:
        target = safe_file(plan_dir, s.new_file, must_exist=False)
        if target.exists() and s.new_file not in old_names:
            raise Refusal(f"{s.new_file} already exists and is not a stage being renumbered")

    # Everything is read and checked; compute the new contents before any write.
    contents = {}
    for name, path in [("PLAN.md", plan_path), ("LEDGER.md", ledger_path),
                       ("BLOCKED.md", blocked_path)]:
        if path.exists():
            contents[plan_dir / name] = path
    for s in stages:
        contents[plan_dir / s.new_file] = sources[s.id]
    pending = {}
    for dest, src in contents.items():
        old = read_text(src)
        new = rewrite(old, id_map, file_map)
        if new != old:
            pending[dest] = new.encode("utf-8")

    for i, s in enumerate(moved):
        os.replace(sources[s.id], plan_dir / f".renumber-{i}.tmp")
    for i, s in enumerate(moved):
        os.replace(plan_dir / f".renumber-{i}.tmp", plan_dir / s.new_file)
    for dest, data in pending.items():
        write_atomic(dest, data)
    return [(s.id, s.final_id()) for s in stages if s.final_id() != s.id]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True, help="plan slug (branches are plan-<slug>-s<N>)")
    ap.add_argument("--plan-dir", default=".plan", help="the .plan directory (default: .plan)")
    args = ap.parse_args(argv)
    try:
        changed = renumber(args.plan_dir, args.slug)
    except (Refusal, OSError) as e:
        print(f"renumber_stages: refused: {e}", file=sys.stderr)
        return 2
    if not changed:
        print("renumber_stages: nothing to renumber")
        return 0
    for old, new in changed:
        print(f"{old} -> {new}")
    print("renumber_stages: done; regenerate .plan/BRIEF.md in the same commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
