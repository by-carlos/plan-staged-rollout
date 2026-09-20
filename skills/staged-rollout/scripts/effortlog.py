#!/usr/bin/env python3
"""Runaway-spend circuit breaker, and the one-line run record it leaves behind.

Two jobs, deliberately kept in a script rather than in skill prose:

  check  Read *this* session's own transcript, total the current context, and
         say whether it has blown a generous budget for the declared scope.
  log    Append one NDJSON row describing how the run went.

Why a script. A skill could in principle instruct the model to do the same
arithmetic inline, but the session that most needs this check is the one that
has already lost the thread — exactly the session least likely to do careful
bookkeeping. The measurement has to work without the model's cooperation, so
it reads a file and returns a number.

Why the transcript and not a usage tool. `CLAUDE_CODE_SESSION_ID` is always in
the environment and Claude Code always writes `<id>.jsonl` under some
`projects/` directory, so this works identically in an attended desktop session
and an unattended cloud run. A host-provided usage tool does not: it may be
absent from the very unattended runs this exists to stop. Note that the two do
not agree to the token -- they sample at different moments and may account
differently -- so a budget is only meaningful in the unit that `check` reports.

This is a BREAKER, not a classifier. The budgets carry 2-3x headroom over a
healthy run: blowing one means something has gone wrong, not that the work was
merely chunky. Nothing here tries to decide whether a model tier was correct --
that judgement needs many rows and belongs to whatever reads the log later.

Invoke as `python <path>/effortlog.py <subcommand> ...` -- one native command
that behaves identically in PowerShell 5.1, pwsh and git-bash.

Logging is opt-in and silent when off: with `CLAUDE_EFFORT_LOG` unset, `log`
writes nothing and still exits 0. A plugin distributed to other people must
not start appending files to their home directory because it was installed.

Exit codes
----------
  check   0 under budget, 3 over budget (the trip), 2 usage/IO failure
  log     0 written or deliberately skipped, 2 usage/IO failure
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Generous by design -- see the module docstring. Units are the context total
# that `check` reports, which is NOT interchangeable with a host usage tool's
# figure. Starting values, expected to be revised once the log has rows.
BUDGETS = {
    "XS": 150_000,
    "S": 250_000,
    "M": 400_000,
    "L": 600_000,
    "XL": 800_000,
}
DEFAULT_BUDGET = 400_000  # scopes with no declared size (e.g. a plan stage)

CONTEXT_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def fail(message: str) -> "int":
    print(f"effortlog: {message}", file=sys.stderr)
    return 2


def session_id() -> str | None:
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def is_attended() -> bool:
    """Whether a human is watching. The harness states this outright.

    Absent means unattended: the safe reading, since a cloud run that lost the
    variable should still be stopped rather than left to burn.
    """
    return os.environ.get("CLAUDE_CODE_SESSION_ATTENDED", "") == "1"


def profile_roots() -> list[Path]:
    """`~/.claude` plus every `~/.claude-*` profile that holds transcripts."""
    home = Path.home()
    roots = []
    for candidate in [home / ".claude"] + sorted(home.glob(".claude-*")):
        projects = candidate / "projects"
        if projects.is_dir():
            roots.append(projects)
    return roots


def find_transcript(sid: str) -> Path | None:
    """Locate `<sid>.jsonl` by search rather than by rebuilding the slug.

    The project directory name is a mangled form of the working directory, and
    re-deriving that mangling here would be a second implementation of someone
    else's rule -- one that breaks silently the day it changes.
    """
    for projects in profile_roots():
        for path in projects.glob(f"*/{sid}.jsonl"):
            return path
        direct = projects / f"{sid}.jsonl"
        if direct.is_file():
            return direct
    return None


def read_transcript(transcript: Path) -> tuple[int | None, str | None]:
    """Context total and model name, as of the last assistant turn with usage.

    Deliberately the LAST turn's figure, not a sum across turns: context is a
    working-set size, and summing would double-count every cached read.

    The model is taken from the same row rather than from the environment,
    which carries no model variable -- and reading it here means the caller
    cannot misreport what it was actually running on.
    """
    latest_usage = None
    latest_model = None
    with transcript.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "assistant":
                continue
            message = row.get("message") or {}
            usage = message.get("usage") or {}
            if usage:
                latest_usage = usage
                latest_model = message.get("model") or latest_model
    if latest_usage is None:
        return None, latest_model
    total = sum(int(latest_usage.get(key, 0) or 0) for key in CONTEXT_KEYS)
    return total, latest_model


def measure() -> tuple[int, str | None]:
    sid = session_id()
    if not sid:
        raise RuntimeError("CLAUDE_CODE_SESSION_ID is not set")
    transcript = find_transcript(sid)
    if transcript is None:
        raise RuntimeError(f"no transcript found for session {sid}")
    total, model = read_transcript(transcript)
    if total is None:
        raise RuntimeError(f"no assistant usage recorded yet in {transcript}")
    return total, model


def cmd_check(args: argparse.Namespace) -> int:
    try:
        total, _ = measure()
    except RuntimeError as exc:
        return fail(str(exc))

    if args.budget is not None:
        budget = args.budget
    elif args.size:
        budget = BUDGETS.get(args.size.upper(), DEFAULT_BUDGET)
    else:
        budget = DEFAULT_BUDGET

    over = total > budget
    print(
        f"context={total} budget={budget} "
        f"attended={'yes' if is_attended() else 'no'} "
        f"verdict={'OVER' if over else 'ok'}"
    )
    if over:
        action = "warn and continue" if is_attended() else "STOP and report"
        print(f"effortlog: over budget -- {action}", file=sys.stderr)
        return 3
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    destination = os.environ.get("CLAUDE_EFFORT_LOG")
    if not destination:
        print("effortlog: CLAUDE_EFFORT_LOG unset, nothing logged")
        return 0

    try:
        total, model = measure()
    except RuntimeError:
        # A record without a measurement still beats no record at all.
        total, model = None, None

    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": args.source,
        "repo": args.repo,
        "target": args.target,
        "estimated_tier": args.estimated_tier,
        "actual_model": args.model or model,
        "actual_effort": os.environ.get("CLAUDE_EFFORT"),
        "size": args.size,
        "context_tokens": total,
        "tripped": bool(args.tripped),
        "attended": is_attended(),
        "outcome": args.outcome,
        "note": args.note,
        "session_id": session_id(),
    }

    path = Path(destination)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    except OSError as exc:
        return fail(f"could not append to {path}: {exc}")

    print(f"effortlog: appended to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="effortlog.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="context total vs a scope budget")
    check.add_argument("--size", help="XS|S|M|L|XL; omitted uses the default budget")
    check.add_argument("--budget", type=int, help="explicit token budget, overrides --size")
    check.set_defaults(func=cmd_check)

    log = subparsers.add_parser("log", help="append one run record")
    log.add_argument("--source", required=True, choices=["work-issue", "stage-run"])
    log.add_argument("--repo", help="owner/repo")
    log.add_argument("--target", help="issue number, or <plan-slug>/S<n>")
    log.add_argument("--estimated-tier", dest="estimated_tier", help="the Effort the run was launched on")
    log.add_argument("--model", help="override; by default read from the transcript")
    log.add_argument("--size", help="declared scope, when there is one")
    log.add_argument("--outcome", help="merged | pr-open | abandoned | stage-done | stage-blocked")
    log.add_argument("--tripped", action="store_true", help="the breaker fired during this run")
    log.add_argument("--note", help="one free-text line for a human reading this later")
    log.set_defaults(func=cmd_log)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
