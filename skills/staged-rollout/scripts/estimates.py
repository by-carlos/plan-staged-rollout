#!/usr/bin/env python3
"""Time estimates for a `.plan/`, and the actuals measured against them.

Three jobs, each a reading of files that already exist -- nothing here writes:

  plan       Sum the stage index's `estimate` column two ways: summed (every
             stage end to end) and elapsed (the longest `depends` chain, the
             floor when independent stages run in parallel). With the ledger
             beside it, also what is left: the stages not yet `done`/`skipped`.
  report     The usage report `/plan-close` shows: per stage, the estimate
             against the `Actuals:` lines its ledger notes block carries, and
             the plan's totals.
  calibrate  Read the effort log's `stage-run` rows that carry both an
             estimate and a measured span, and say by how much past estimates
             ran long or short. `/plan-stages` scales its judged ranges by it.

Why a script. Adding ranges across a dependency graph is arithmetic the model
gets wrong quietly; a stage table that says "elapsed 4-7h" must be the same
answer every time it is read.

Estimates are ranges in hours -- `1-2h`, `0.5–1h` (hyphen or en dash) or a
bare `2h`. A cell of `—` or `-` means "no estimate" and is counted, not
guessed at. Actuals include time spent waiting on the user; estimates do not.

Invoke as `python <path>/estimates.py <subcommand> ...`.

Exit codes: 0 printed, 2 usage/IO failure or an unreadable plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:[–-]\s*(\d+(?:\.\d+)?))?\s*h\s*$")
STAGE_RE = re.compile(r"^(S\d+[a-z]?|SF)\b")
DEP_RE = re.compile(r"S\d+[a-z]?|SF")
NO_VALUE = {"", "—", "-", "–"}
ACTUALS_RE = re.compile(
    r"Actuals:\s*(?P<start>\S+)\s*→\s*(?P<finish>\S+)\s*·\s*(?P<min>\d+|None)\s*min\s*·\s*"
    r"tokens in=(?P<in>\d+) out=(?P<out>\d+) cache_read=(?P<cr>\d+) cache_write=(?P<cw>\d+)"
)
CLOSED = {"done", "skipped"}
MIN_ROWS = 3  # fewer calibrated rows than this say nothing a judgement doesn't


class PlanError(Exception):
    pass


def parse_range(cell: str) -> tuple[float, float] | None:
    if cell.strip() in NO_VALUE:
        return None
    m = RANGE_RE.match(cell)
    if not m:
        raise PlanError(f"estimate {cell!r} is not a range in hours such as 1-2h")
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    if hi < lo:
        raise PlanError(f"estimate {cell!r} runs high to low")
    return lo, hi


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_index(text: str) -> list[dict]:
    """Stage rows of `## Stage index`, columns found by header name."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("## Stage index")), None)
    if start is None:
        raise PlanError("PLAN.md has no '## Stage index' section")
    header, stages = None, []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if stages:
                break
            continue
        cells = split_row(line)
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if set(cells[0]) <= set("-: "):
            continue
        m = STAGE_RE.match(cells[0])
        if not m:
            continue
        row = dict(zip(header, cells))
        depends = row.get("depends", "")
        stages.append({
            "id": m.group(1),
            "name": cells[0],
            "depends": [] if depends in NO_VALUE else DEP_RE.findall(depends),
            "estimate": parse_range(row.get("estimate", "")),
            "estimate_text": row.get("estimate", "—") or "—",
        })
    if header is None or not stages:
        raise PlanError("the stage index has no rows")
    if "estimate" not in header:
        raise PlanError("the stage index has no `estimate` column")
    return stages


def parse_ledger(text: str) -> tuple[dict, dict]:
    """Statuses from `## Status`, and every `Actuals:` line per notes block."""
    statuses, actuals = {}, {}
    section, block = None, None
    for line in text.splitlines():
        if line.startswith("## "):
            section, block = line[3:].strip(), None
            continue
        if line.startswith("### "):
            m = STAGE_RE.match(line[4:].strip())
            block = m.group(1) if m else None
            continue
        if section == "Status" and line.startswith("|"):
            cells = split_row(line)
            m = STAGE_RE.match(cells[0]) if len(cells) > 1 else None
            if m:
                statuses[m.group(1)] = cells[1].lower()
        if block:
            m = ACTUALS_RE.search(line)
            if m:
                actuals.setdefault(block, []).append(m)
    return statuses, actuals


def longest_path(stages: list[dict], end: int) -> float:
    """Longest `depends` chain, taking each stage's low (0) or high (1) end."""
    by_id = {s["id"]: s for s in stages}
    memo: dict[str, float] = {}

    def finish(sid: str, trail: tuple = ()) -> float:
        if sid in memo:
            return memo[sid]
        if sid in trail:
            raise PlanError(f"depends cycle through {sid}")
        stage = by_id.get(sid)
        if stage is None:
            return 0.0
        own = stage["estimate"][end] if stage["estimate"] else 0.0
        memo[sid] = own + max((finish(d, trail + (sid,)) for d in stage["depends"]), default=0.0)
        return memo[sid]

    return max((finish(s["id"]) for s in stages), default=0.0)


def totals(stages: list[dict]) -> dict:
    est = [s["estimate"] for s in stages if s["estimate"]]
    return {
        "summed": [sum(e[0] for e in est), sum(e[1] for e in est)],
        "elapsed": [longest_path(stages, 0), longest_path(stages, 1)],
        "unestimated": [s["id"] for s in stages if not s["estimate"]],
    }


def hours(pair: list[float]) -> str:
    lo, hi = (f"{v:g}" for v in pair)
    return f"{lo}h" if lo == hi else f"{lo}–{hi}h"


def total_line(label: str, t: dict) -> str:
    line = f"{label}: summed {hours(t['summed'])} · elapsed {hours(t['elapsed'])}"
    if t["unestimated"]:
        line += f" · no estimate: {', '.join(t['unestimated'])}"
    return line


def load(plan_dir: Path) -> tuple[list[dict], dict, dict]:
    plan = plan_dir / "PLAN.md"
    if not plan.is_file():
        raise PlanError(f"no PLAN.md in {plan_dir}")
    stages = parse_index(plan.read_text(encoding="utf-8"))
    ledger = plan_dir / "LEDGER.md"
    statuses, actuals = ({}, {})
    if ledger.is_file():
        statuses, actuals = parse_ledger(ledger.read_text(encoding="utf-8"))
    return stages, statuses, actuals


def cmd_plan(args: argparse.Namespace) -> int:
    stages, statuses, _ = load(Path(args.plan_dir))
    out = {"plan": totals(stages)}
    out["line"] = total_line("Plan estimate", out["plan"])
    if statuses:
        open_ids = {s["id"] for s in stages if statuses.get(s["id"], "todo") not in CLOSED}
        left = [
            {**s, "depends": [d for d in s["depends"] if d in open_ids]}
            for s in stages if s["id"] in open_ids
        ]
        out["remaining"] = totals(left)
        out["remaining_line"] = total_line("Left", out["remaining"])
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def stamp(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def cmd_report(args: argparse.Namespace) -> int:
    stages, statuses, actuals = load(Path(args.plan_dir))
    rows, grand = [], {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    spent_min, starts, finishes, measured = 0, [], [], 0
    for s in stages:
        lines = actuals.get(s["id"], [])
        minutes = sum(int(m["min"]) for m in lines if m["min"] != "None")
        tok = {
            "in": sum(int(m["in"]) for m in lines),
            "out": sum(int(m["out"]) for m in lines),
            "cache_read": sum(int(m["cr"]) for m in lines),
            "cache_write": sum(int(m["cw"]) for m in lines),
        }
        for k in grand:
            grand[k] += tok[k]
        spent_min += minutes
        if lines:
            measured += 1
        starts += [t for t in (stamp(m["start"]) for m in lines) if t]
        finishes += [t for t in (stamp(m["finish"]) for m in lines) if t]
        rows.append(
            f"| {s['name']} | {statuses.get(s['id'], '—')} | {s['estimate_text']} | "
            + (f"{minutes / 60:.1f}h | {tok['in'] + tok['cache_read'] + tok['cache_write']} | {tok['out']} | {len(lines)} |"
               if lines else "— | — | — | 0 |")
        )
    t = totals(stages)
    span = (max(finishes) - min(starts)).total_seconds() / 3600 if starts and finishes else None
    report = [
        "| Stage | Status | Estimate | Actual | Tokens in (incl. cache) | Tokens out | Sessions |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        f"- **Estimate:** {total_line('plan', t).split(': ', 1)[1]}.",
        f"- **Actual:** summed {spent_min / 60:.1f}h over {measured} measured stage(s)"
        + (f" · elapsed {span:.1f}h, first start to last finish" if span is not None else "")
        + ". Actuals include time waiting on the user; the estimate does not.",
        f"- **Tokens:** in {grand['in']} · out {grand['out']} · cache read {grand['cache_read']}"
        f" · cache write {grand['cache_write']}, subagents included.",
    ]
    unmeasured = [s["id"] for s in stages if s["id"] not in actuals]
    if unmeasured:
        report.append(f"- **Not measured:** {', '.join(unmeasured)} (no `Actuals:` line in the ledger).")
    print("\n".join(report))
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    path = args.log or os.environ.get("CLAUDE_EFFORT_LOG")
    if not path or not Path(path).is_file():
        print(json.dumps({"rows": 0, "factor": None,
                          "line": "No effort log to calibrate from; use the reference ranges as written."}))
        return 0
    # A resumed stage logs one row per session, each a slice of one estimate:
    # sum a stage's sessions first, and count only stages that finished.
    stages: dict = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if row.get("source") != "stage-run" or not row.get("estimate") or not row.get("elapsed_minutes"):
            continue
        try:
            est = parse_range(str(row["estimate"]))
        except PlanError:
            continue
        if not est or sum(est) == 0:
            continue
        entry = stages.setdefault(row.get("target") or id(row), {"est": est, "minutes": 0, "done": False})
        entry["minutes"] += row["elapsed_minutes"]
        entry["done"] = entry["done"] or row.get("outcome") == "stage-done"
    ratios = [
        (e["minutes"] / 60) / (sum(e["est"]) / 2) for e in stages.values() if e["done"]
    ]
    if len(ratios) < MIN_ROWS:
        print(json.dumps({"rows": len(ratios), "factor": None,
                          "line": f"{len(ratios)} measured stage(s), fewer than {MIN_ROWS}; use the reference ranges as written."}))
        return 0
    factor = round(statistics.median(ratios), 2)
    print(json.dumps({
        "rows": len(ratios),
        "factor": factor,
        "line": f"Past stages took {factor}x their estimate's midpoint (median of {len(ratios)}); "
                f"scale judged ranges by {factor}.",
    }))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="estimates.py")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="the plan total, summed and elapsed, and what is left")
    plan.add_argument("--plan-dir", default=".plan")
    plan.set_defaults(func=cmd_plan)
    report = sub.add_parser("report", help="estimate against actuals, per stage and for the plan")
    report.add_argument("--plan-dir", default=".plan")
    report.set_defaults(func=cmd_report)
    cal = sub.add_parser("calibrate", help="how far past estimates ran from their actuals")
    cal.add_argument("--log", help="NDJSON effort log; defaults to CLAUDE_EFFORT_LOG")
    cal.set_defaults(func=cmd_calibrate)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PlanError, OSError) as exc:
        print(f"estimates: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
