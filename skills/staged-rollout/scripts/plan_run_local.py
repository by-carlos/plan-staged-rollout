#!/usr/bin/env python3
"""Drive a plan's remaining stages as fresh local `claude -p` sessions.

`/plan-run-local` starts `run` in the background from an interactive session
-- the orchestrator -- and is woken when it exits. The driver holds the loop:
it reads the runnable set, runs `/plan-staged-rollout:stage-run <N>
--unattended --runner local` for each stage as its own headless session at
the model and effort the stage index books, re-reads the ledger as each one
ends, and carries on while stages land `done`. It exits only when a person
is needed, printing one `STATUS:` line that the orchestrator reads instead
of any stage output.

Subcommands:

  run     Run runnable stages, several side by side, until a person is needed.
  next    Say which stages `run` would start, and the exact command. Runs nothing.
  status  Print the status file: the stages run so far and those in flight.

Stages side by side. Every stage whose `depends` are all `done` or `skipped`
is runnable, and the driver keeps several in flight, in index order. Each
session starts in the clone, which stays on the plan branch, and makes its
own stage worktree (the skill's Git model), so they never share a checkout.
The ramp-up: before any stage's usage is measured, at most START_AT_ONCE run
at once; after that, one more starts only while the share plus the largest
measured jump, once for each stage in flight and once for the next, stays
within GATE_CEILING. No cost is assumed for a stage that has not been
measured. Starts are START_STAGGER_SECONDS apart, so two stage preflights do
not run git in the clone together. A stage never starts beside one it
depends on, and never two `gate: live` stages at once (the driver fires no
`live` stage at all). When one stage needs a person, nothing more starts;
the stages in flight run to their end and the STATUS line names each stop.
Each session merges its own stage PR into the plan branch, so the merges
stay one at a time as the skill's Parallel stages section says.

The machine's room. Beside stages in flight, one more also starts only while
fewer than CLAUDE_STAGE_MAX_PARALLEL are running and, when free memory can be
read (Windows GlobalMemoryStatusEx, Linux /proc/meminfo, macOS vm_stat), at
least STAGE_SESSION_MB × MEMORY_MARGIN is free. When it cannot be read, the
cap alone decides. A start held for room waits for a stage to end; the first
stage is never held, and a running stage is never stopped to make room. CPU
load is not read: the core count only sets the cap's default.

A dead or hung driver. Every status-file write is the main loop's
heartbeat, refreshed at least every HEARTBEAT_SECONDS while stages run or
during a wait. A watchdog thread reads it: when it is older than
STALE_SECONDS, the watchdog prints `STATUS: driver-hung` naming the step the
loop was on, stops every stage session in flight, records it and exits the
process. Each git command is stopped after GIT_TIMEOUT_SECONDS
(`git-timeout`); sessions in flight then run to their end, unread. `status`
reports a `running` file with a stale heartbeat as a driver that is gone.
Each stage session's process id is recorded; `run` refuses to start while a
session an earlier driver recorded is still running (`stage-session-alive`),
and reports it rather than stopping it.

What it never does: write `.plan/LEDGER.md` or `.plan/BLOCKED.md` (a stage's
own push is the only completion signal), fire a stage whose `gate` is
`human`, `live` or unknown, open or merge a pull request, or read a secret.
Logging in is the launcher's job.

The usage gate. Every stage session's stream carries `rate_limit_event`
lines with the account's 5-hour window: the share used and the reset time.
The driver keeps the latest one from any session, and `run --usage-percent
P --usage-resets-at T` seeds it for the first stage (the orchestrator reads
the desktop app's usage card). With nothing in flight it holds the next
stage when the share is at GATE_CUTOFF or more and no stage has been
measured yet, or when the share plus the largest per-stage jump measured
this run would pass GATE_CEILING; beside stages in flight it applies the
ramp-up above instead, and a stage it does not start waits for one to end.
A held stage with nothing in flight waits until the reset, then starts
without a second check. A jump is the change in the account's share across
one stage, so other sessions' use counts in it, stages running beside it
included: it is an upper bound, and the ramp-up errs towards fewer at once.
One measured across a reset is discarded. With no reading at all the gate
does not hold, the ramp-up stays at START_AT_ONCE, and the final STATUS
line says once that the gate was skipped. Nothing estimates tokens or turns
them into a share.

A stage session that ends on the usage limit (`stage-limited`) is waited out
the same way and the stage is run again, which `/stage-run` treats as a
resume; nothing new starts meanwhile, and the wait begins once the stages
in flight have ended. The run stops instead when no reset time can be
read, when the reset is more than CLAUDE_STAGE_MAX_WAIT_HOURS away (a weekly
limit), when the same stage hits the limit again right after a reset, or
when another stage has already stopped the run.

Settings, from the environment:

  CLAUDE_STAGE_LAUNCHER         One executable, no arguments, run in place of
                                `claude` with the same arguments (a wrapper
                                that supplies a login). Default `claude`.
  CLAUDE_STAGE_PERMISSION_MODE  `auto` (default), `manual`, `acceptEdits` or
                                `dontAsk`.
  CLAUDE_STAGE_IDLE_MINUTES     Minutes without a stream-json line before a
                                stage session is stopped. Default 15.
  CLAUDE_STAGE_MAX_BUDGET_USD   Passed as `--max-budget-usd`. Unset: no cap.
  CLAUDE_STAGE_MAX_WAIT_HOURS   The longest the driver waits for a usage
                                reset before stopping for a person. Default 6.
  CLAUDE_STAGE_MAX_PARALLEL     The most stages in flight at once, a whole
                                number from 1. Default half the cores, at
                                least 1. `1` runs stages one at a time.

The status file and the logs live outside `.plan/`, in the clone's git
directory: `<git common dir>/plan-run-local/<plan slug>/`.

The events file. Beside the status file, `events.log` gets one plain-text
line per progress event, appended and flushed as it happens, for the
orchestrator to pass on as notifications (`next` names its path as
`events_file`):

  S1 started (sonnet, low)
  S1 finished: done
  S2, S3 waiting for the usage reset at 2026-11-23 14:05 UTC

The outcome after `finished:` is the one the status file records. Runs append
to the same file, so a reader notes its length before it starts one. A line
that cannot be written is dropped: the file never stops a run, and nothing in
the driver reads it.

Invoke as `python3 <path>/plan_run_local.py <subcommand> [--repo <dir>]`.

Exit codes: 0 a STATUS line was printed (whatever it says), 2 usage/IO failure.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

STAGE_RE = re.compile(r"^(S\d+[a-z]?|SF)\b")
DEP_RE = re.compile(r"S\d+[a-z]?|SF")
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
NO_VALUE = {"", "—", "-", "–"}
CLOSED = {"done", "skipped"}
FIRED_GATES = {"auto", "local"}  # an absent gate reads as auto
KNOWN_GATES = {"auto", "local", "human", "live"}
EFFORTS = {"low": "low", "med": "medium", "medium": "medium", "high": "high",
           "xhigh": "xhigh", "max": "max"}
PERMISSION_MODES = {"auto", "manual", "acceptEdits", "dontAsk"}
MODE_ALIASES = {"default": "manual"}  # the SDK reports Manual as `default`
PROTECTED = {"main", "master", "release", "trunk", "develop"}
MIN_VERSION = (2, 1, 268)
IDLE_MINUTES = 15
GRACE_SECONDS = 120     # a finished session's push settling before the dead-run read
INTERRUPT_SECONDS = 30  # SIGINT, then terminate (POSIX)
HEARTBEAT_SECONDS = 60  # status file refresh while a stage runs
STALE_SECONDS = 300     # an older heartbeat means the driver that wrote it is gone
EVENTS_FILE = "events.log"  # progress lines, beside the status file
WATCH_SECONDS = 15      # how often the watchdog reads the main loop's heartbeat
GIT_TIMEOUT_SECONDS = 120  # one git command; kept under STALE_SECONDS so a stuck fetch is named
PLAN_DIR = ".plan"
# The usage gate, in percent of the 5-hour limit. Starting values: 95 leaves
# room for the measurement being a step behind; 90 covers a first stage of
# unknown size.
GATE_CEILING = 95       # hold when the share plus the largest stage jump would pass this
GATE_CUTOFF = 90        # hold at this share before any stage has a measured jump
RESET_MARGIN_SECONDS = 60  # start this long after the reset, not on its second
MAX_WAIT_HOURS = 6
LIMIT_RETRIES = 1       # runs of one stage straight after a limit reset before stopping
# The ramp-up. Starting values: two sessions at once before anything is
# measured is the smallest step that is parallel at all, and a minute apart
# keeps their preflights' git commands in the shared clone from overlapping.
START_AT_ONCE = 2       # stages in flight before any stage's usage is measured
START_STAGGER_SECONDS = 60  # between two starts while a stage is in flight
# The room check. STAGE_SESSION_MB is one stage session's measured peak: the
# `claude` process and every process under it. The margin covers sessions in
# flight that have not reached their peak yet, since free memory is read as
# they stand now. Measured on Windows over six Sonnet stage sessions
# (#321): private bytes peaked at 529 MB, working set at 423 MB, summed
# over the process tree; rounded up to 600.
STAGE_SESSION_MB = 600   # one stage session's peak memory, measured
MEMORY_MARGIN = 1.5      # free memory needed before a start: STAGE_SESSION_MB × this


class PlanError(Exception):
    pass


class GitTimeout(PlanError):
    """A git command gave no answer within GIT_TIMEOUT_SECONDS."""


class Hung(Exception):
    """The watchdog has reported the driver hung; the main loop stops here."""


# --- reading the plan --------------------------------------------------------

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
        gate = row.get("gate", "").strip("` ").lower()
        stages.append({
            "id": m.group(1),
            "name": cells[0],
            "depends": [] if depends in NO_VALUE else DEP_RE.findall(depends),
            "model": "" if row.get("model", "") in NO_VALUE else row["model"].strip("` "),
            "effort": "" if row.get("effort", "") in NO_VALUE else row["effort"].strip("` ").lower(),
            "gate": "auto" if gate in NO_VALUE else gate,
        })
    if header is None or not stages:
        raise PlanError("the stage index has no rows")
    return stages


def parse_ledger(text: str) -> dict:
    """Stage id -> status, from `## Status`, plus the row's Result cell."""
    rows, section = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section == "Status" and line.startswith("|"):
            cells = split_row(line)
            m = STAGE_RE.match(cells[0]) if len(cells) > 1 else None
            if m:
                words = cells[1].lower().split()
                rows[m.group(1)] = {
                    "status": words[0].strip("`") if words else "todo",
                    "result": cells[4] if len(cells) > 4 else "",
                }
    return rows


def parse_blocked(text: str) -> dict:
    """Stage id -> first line of its `### S<N>` section in BLOCKED.md."""
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("### "):
            m = STAGE_RE.match(line[4:].strip())
            current = m.group(1) if m else None
            if current:
                out[current] = ""
            continue
        if line.startswith("## "):
            current = None
            continue
        if current and not out[current] and line.strip():
            out[current] = line.strip()
    return out


def stage_arg(stage_id: str) -> str:
    """`S3` -> `3`, `S3a` -> `3a`, `SF` -> `f`: what `/stage-run` takes."""
    return "f" if stage_id == "SF" else stage_id[1:]


def effort_flag(value: str) -> str:
    """Index effort -> `--effort` value; empty when the row books none."""
    if not value:
        return ""
    if value not in EFFORTS:
        raise PlanError(f"effort {value!r} is not one of {', '.join(sorted(EFFORTS))}")
    return EFFORTS[value]


def select(stages: list[dict], ledger: dict, blocked: dict | None = None) -> dict:
    """The runnable set, and why nothing else is.

    Returns {"runnable": [<row>, ...], "stage": <the first, or None>,
    "gated": [...], "waiting": [...], "complete": bool}. A stage is runnable
    when its row reads `todo` (or is missing) and every `depends` entry reads
    `done` or `skipped`; it is fired only when its gate is `auto`, absent or
    `local`. The set is in index order. A stage with a BLOCKED.md section
    reads `blocked` until a person deletes the section, whatever its row
    says, as it does for the cloud runner.
    """
    status = {s["id"]: ledger.get(s["id"], {}).get("status", "todo") for s in stages}
    for sid in blocked or {}:
        if sid in status and status[sid] not in CLOSED:
            status[sid] = "blocked"
    gated, waiting, runnable = [], [], []
    for s in stages:
        if status[s["id"]] != "todo":
            if status[s["id"]] not in CLOSED:
                waiting.append({"id": s["id"], "status": status[s["id"]]})
            continue
        if not all(status.get(d) in CLOSED for d in s["depends"]):
            continue
        if s["gate"] not in FIRED_GATES:
            gated.append({"id": s["id"], "gate": s["gate"],
                          "known": s["gate"] in KNOWN_GATES})
            continue
        runnable.append(s)
    complete = all(v in CLOSED for v in status.values())
    return {"runnable": runnable, "stage": runnable[0] if runnable else None,
            "gated": gated, "waiting": waiting, "complete": complete}


def next_to_start(candidates: list[dict], running: list[dict]) -> dict | None:
    """The first candidate that may start beside the stages in `running`.

    Skipped: a stage already running, one that depends on a running stage,
    and a second `gate: live` stage. The runnable set never holds the last
    two (its `depends` are closed, and `live` is never fired); a stage named
    by `--resume` or waiting out a limit is checked here all the same.
    """
    ids = {s["id"] for s in running}
    live = any(s["gate"] == "live" for s in running)
    for s in candidates:
        if s["id"] in ids or ids & set(s["depends"]):
            continue
        if live and s["gate"] == "live":
            continue
        return s
    return None


def outcome(before: str, after: str, blocked: bool, killed: bool, pushed: bool = False,
            limited: bool = False) -> str:
    """Classify a finished stage session by its ledger row and stage branch.

    `done`/`skipped` carry on; `blocked`, or `doing` with a BLOCKED.md
    section, is a block; a session that ended on the usage limit is
    `stage-limited`, whatever its row says; `doing` with none is a stop (a
    refused merge, the breaker). A row that never moved is a stop too when the
    session pushed its stage branch, since the `doing` flip rides that branch
    until it merges; with no push it is a dead run, as in remote-driver.md.
    """
    if after in CLOSED:
        return "done"
    if after == "blocked" or (after == "doing" and blocked):
        return "stage-blocked"
    if limited:
        return "stage-limited"
    if killed:
        return "stage-dead"
    if after == before:
        return "stage-stopped" if pushed else "stage-dead"
    if after == "doing":
        return "stage-stopped"
    return "stage-dead"


# --- the usage limit ------------------------------------------------------------

def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def five_hour(event: dict) -> dict | None:
    """The 5-hour window in a `rate_limit_event` line: {"percent", "resets_at"}.

    `utilization` is a fraction and `resetsAt` epoch seconds. The window sits
    under `unifiedWindows.five_hour`; an older line carries it at the top
    level with `rateLimitType: five_hour`.
    """
    if not isinstance(event, dict) or event.get("type") != "rate_limit_event":
        return None
    info = event.get("rate_limit_info")
    if not isinstance(info, dict):
        return None
    window = (info.get("unifiedWindows") or {}).get("five_hour") if isinstance(info.get("unifiedWindows"), dict) else None
    if not isinstance(window, dict):
        window = info if info.get("rateLimitType") == "five_hour" else None
    if window is None or _number(window.get("utilization")) is None:
        return None
    return {"percent": round(_number(window["utilization"]) * 100, 1),
            "resets_at": _number(window.get("resetsAt"))}


def limit_hit(event: dict) -> dict | None:
    """{"resets_at", "type"} when a stream-json line says the session hit its limit.

    Two signs: a `rate_limit_event` whose status is `rejected` while no extra
    usage is being drawn, and an assistant line whose `error` is `rate_limit`
    (the CLI's own "You've hit your limit" message). Either may carry the
    reset; the prose is never parsed.
    """
    if not isinstance(event, dict):
        return None
    if event.get("type") == "rate_limit_event":
        info = event.get("rate_limit_info")
        if isinstance(info, dict) and info.get("status") == "rejected" and not info.get("isUsingOverage"):
            return {"resets_at": _number(info.get("resetsAt")), "type": info.get("rateLimitType")}
        return None
    if event.get("type") == "assistant" and event.get("error") == "rate_limit":
        for holder in (event, event.get("message")):
            params = holder.get("apiErrorParams") if isinstance(holder, dict) else None
            info = params.get("rate_limit_info") if isinstance(params, dict) else None
            if isinstance(info, dict):
                return {"resets_at": _number(info.get("resetsAt")), "type": info.get("rateLimitType")}
        return {"resets_at": None, "type": None}
    return None


def transcript_limit(session_id: str | None, env: dict) -> dict | None:
    """The limit hit recorded in a stage session's own transcript, if any.

    The transcript keeps the CLI's limit message with `apiErrorParams`
    (`usage_limit_reached`, the reset in epoch seconds) even when the
    stream-json line did not carry it. Only the last hit counts.
    """
    if not session_id or not re.fullmatch(r"[A-Za-z0-9-]+", session_id):
        return None
    base = Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    found = None
    for path in base.glob(f"*/{session_id}.jsonl"):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"rate_limit"' not in line:
                        continue
                    try:
                        hit = limit_hit(json.loads(line))
                    except ValueError:
                        continue
                    if hit:
                        found = hit
        except OSError:
            continue
    return found


def stage_jump(start: dict | None, end: dict | None) -> float | None:
    """Points of the 5-hour share one stage moved, or None when unmeasurable:
    a reading missing, or the two in different windows (a reset between)."""
    if not start or not end or start.get("resets_at") is None or end.get("resets_at") is None:
        return None
    # Same window: the desktop app's reset carries milliseconds, the stream's does not.
    if abs(start["resets_at"] - end["resets_at"]) > 60 or end["percent"] < start["percent"]:
        return None
    return round(end["percent"] - start["percent"], 1)


def gate_holds(percent: float | None, jump: float | None) -> bool:
    """Hold the next stage? No reading never holds."""
    if percent is None:
        return False
    if jump is None:
        return percent >= GATE_CUTOFF
    return percent + jump > GATE_CEILING


def ramp_allows(percent: float | None, jump: float | None, in_flight: int) -> bool:
    """May one more stage start beside `in_flight` running ones?

    With none in flight this is the gate itself. Beside running stages: at
    most START_AT_ONCE in all while no jump is measured or no share is known,
    and once both are, only while the share plus the largest jump for each
    stage in flight and the next stays within GATE_CEILING. No floor is put
    on a jump: a stage nobody has measured is never assumed cheap.
    """
    if gate_holds(percent, jump):
        return False
    if in_flight == 0:
        return True
    if jump is None or percent is None:
        return in_flight < START_AT_ONCE
    return percent + jump * (in_flight + 1) <= GATE_CEILING


def ramp_line(stage_id: str, reading: dict | None, jump: float | None,
              running: list[str], allowed: bool) -> str:
    """The ramp-up's one-line verdict for a stage beside stages in flight."""
    used = ("no 5-hour reading yet" if reading is None else
            f"{reading['percent']:g}% of the 5-hour limit used, resets {clock_text(reading['resets_at'])}")
    flight = f"{len(running)} in flight ({', '.join(running)})"
    if reading is not None and jump is not None:
        total = round(reading["percent"] + jump * (len(running) + 1), 1)
        rule = (f"largest stage jump so far {jump:g} points, so {reading['percent']:g} + {jump:g} × "
                f"{len(running) + 1} = {total:g}% against {GATE_CEILING}%")
    elif reading is not None and jump is None and reading["percent"] >= GATE_CUTOFF:
        rule = f"no stage measured yet, holding at {GATE_CUTOFF}%"
    else:
        why = "no stage measured yet" if jump is None else "no share read since the reset"
        rule = f"{why}, so at most {START_AT_ONCE} at once"
    verdict = f"{stage_id} starts beside them" if allowed else f"{stage_id} waits for a stage to end"
    return f"usage gate: {used}; {flight}; {rule}: {verdict}"


# --- the machine's room -------------------------------------------------------

def parse_meminfo(text: str) -> float | None:
    """`/proc/meminfo`'s MemAvailable, in MB."""
    m = re.search(r"^MemAvailable:\s+(\d+)\s*kB", text, re.M)
    return int(m.group(1)) / 1024 if m else None


def parse_vm_stat(text: str) -> float | None:
    """macOS `vm_stat`: free, inactive and speculative pages, in MB."""
    size = re.search(r"page size of (\d+) bytes", text)
    pages = [re.search(rf"^Pages {name}:\s+(\d+)", text, re.M) for name in ("free", "inactive", "speculative")]
    if not size or not pages[0]:
        return None
    return sum(int(m.group(1)) for m in pages if m) * int(size.group(1)) / 2**20


def free_memory_windows() -> float | None:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    *((name, ctypes.c_ulonglong) for name in (
                        "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                        "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual"))]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullAvailPhys / 2**20


def free_memory_mb() -> float | None:
    """Free physical memory in MB, read from the platform; None when it
    cannot be read, and then the cap alone decides."""
    try:
        if sys.platform == "win32":
            return free_memory_windows()
        if sys.platform.startswith("linux"):
            return parse_meminfo(Path("/proc/meminfo").read_text(encoding="ascii", errors="replace"))
        if sys.platform == "darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10)
            return parse_vm_stat(out.stdout) if out.returncode == 0 else None
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None
    return None


def default_parallel(cores: int | None) -> int:
    """The cap when CLAUDE_STAGE_MAX_PARALLEL is unset: half the cores, at least one."""
    return max(1, (cores or 1) // 2)


def room_allows(free_mb: float | None, in_flight: int, cap: int) -> bool:
    """May one more stage start beside `in_flight` running ones, for the
    machine? The first stage is never held: with nothing in flight the run
    goes on as a serial run would. Beside running stages: under the cap, and
    with STAGE_SESSION_MB × MEMORY_MARGIN free when free memory can be read."""
    if in_flight == 0:
        return True
    if in_flight >= cap:
        return False
    return free_mb is None or free_mb >= STAGE_SESSION_MB * MEMORY_MARGIN


def room_line(stage_id: str, free_mb: float | None, running: list[str], cap: int,
              cap_from: str, allowed: bool) -> str:
    """The room check's one-line verdict, as the status file gives it."""
    flight = f"{len(running)} in flight ({', '.join(running)})" if running else "nothing in flight"
    need = STAGE_SESSION_MB * MEMORY_MARGIN
    if free_mb is None:
        memory = "free memory could not be read, so the cap alone decides"
    else:
        memory = (f"{free_mb:,.0f} MB free against {need:,.0f} MB needed "
                  f"({STAGE_SESSION_MB:,} MB a stage session × {MEMORY_MARGIN:g})")
    rule = f"at most {cap} at once ({cap_from})"
    if not running:
        verdict = f"{stage_id} starts (the first stage is never held for room)"
    elif allowed:
        verdict = f"{stage_id} starts beside them"
    else:
        short = "the cap is reached" if len(running) >= cap else "memory is short"
        verdict = f"{stage_id} is held for resources ({short}) and waits for a stage to end"
    return f"resources: {flight}; {rule}; {memory}: {verdict}"


def clock_text(epoch: float | None) -> str:
    if epoch is None:
        return "an unknown time"
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def gate_line(stage_id: str, reading: dict | None, jump: float | None, hold: bool) -> str:
    """The gate's one-line verdict, as the status file and `next` give it."""
    if reading is None:
        return f"usage gate: no 5-hour reading yet; {stage_id} starts unchecked"
    used = f"{reading['percent']:g}% of the 5-hour limit used, resets {clock_text(reading['resets_at'])}"
    rule = (f"largest stage jump so far {jump:g} points, holding above {GATE_CEILING}%" if jump is not None
            else f"no stage measured yet, holding at {GATE_CUTOFF}%")
    verdict = f"{stage_id} waits for the reset" if hold else f"{stage_id} starts"
    return f"usage gate: {used}; {rule}: {verdict}"


def parse_reset(text: str) -> float:
    """`--usage-resets-at`: epoch seconds, or an ISO 8601 time such as the
    desktop app's `resetsAt` (`2026-11-23T16:00:00.885Z`)."""
    try:
        return float(text)
    except ValueError:
        pass
    try:
        when = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        raise PlanError(f"--usage-resets-at {text!r}: give epoch seconds or an ISO 8601 time") from None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.timestamp()


def seed_reading(percent: float | None, resets_at: str | None) -> dict | None:
    if percent is None and resets_at is None:
        return None
    if percent is None or resets_at is None:
        raise PlanError("--usage-percent and --usage-resets-at go together")
    if not 0 <= percent <= 100:
        raise PlanError(f"--usage-percent {percent:g}: give 0 to 100")
    return {"percent": float(percent), "resets_at": parse_reset(resets_at)}


# --- the launcher -------------------------------------------------------------

def parse_version(text: str) -> tuple[int, int, int] | None:
    m = VERSION_RE.search(text or "")
    return tuple(int(g) for g in m.groups()) if m else None


def settings(env: dict) -> dict:
    mode = env.get("CLAUDE_STAGE_PERMISSION_MODE", "").strip() or "auto"
    if mode not in PERMISSION_MODES:
        raise PlanError(f"CLAUDE_STAGE_PERMISSION_MODE={mode!r}: use one of "
                        f"{', '.join(sorted(PERMISSION_MODES))}")
    idle = env.get("CLAUDE_STAGE_IDLE_MINUTES", "").strip() or str(IDLE_MINUTES)
    budget = env.get("CLAUDE_STAGE_MAX_BUDGET_USD", "").strip()
    wait = env.get("CLAUDE_STAGE_MAX_WAIT_HOURS", "").strip() or str(MAX_WAIT_HOURS)
    try:
        idle_min = float(idle)
        wait_hours = float(wait)
        if idle_min <= 0 or wait_hours < 0:
            raise ValueError
        if budget:
            float(budget)
    except ValueError:
        raise PlanError("CLAUDE_STAGE_IDLE_MINUTES must be a positive number, "
                        "CLAUDE_STAGE_MAX_WAIT_HOURS zero or more and "
                        "CLAUDE_STAGE_MAX_BUDGET_USD a number") from None
    parallel = env.get("CLAUDE_STAGE_MAX_PARALLEL", "").strip()
    if parallel:
        if not (parallel.isascii() and parallel.isdigit()) or int(parallel) < 1:
            raise PlanError(f"CLAUDE_STAGE_MAX_PARALLEL={parallel!r}: give a whole number, 1 or more")
        cap, cap_from = int(parallel), "CLAUDE_STAGE_MAX_PARALLEL"
    else:
        cores = os.cpu_count()
        cap = default_parallel(cores)
        cap_from = f"half of {cores} cores" if cores else "the core count could not be read"
    return {
        "max_parallel": cap,
        "max_parallel_from": cap_from,
        "launcher": env.get("CLAUDE_STAGE_LAUNCHER", "").strip() or "claude",
        "mode": mode,
        "idle_seconds": idle_min * 60,
        "max_wait_seconds": wait_hours * 3600,
        "budget": budget,
        "scrub": env.get("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", "").strip().lower() not in ("", "0", "false"),
    }


def stage_command(launcher: list[str], stage: dict, conf: dict) -> list[str]:
    prompt = f"/plan-staged-rollout:stage-run {stage_arg(stage['id'])} --unattended --runner local"
    cmd = [*launcher, "-p", prompt]
    if stage["model"]:
        cmd += ["--model", stage["model"]]
    effort = effort_flag(stage["effort"])
    if effort:
        cmd += ["--effort", effort]
    cmd += ["--output-format", "stream-json", "--verbose",
            "--permission-prompts", "none", "--permission-mode", conf["mode"]]
    if conf["budget"]:
        cmd += ["--max-budget-usd", conf["budget"]]
    return cmd


def check_init(init: dict, stage: dict, conf: dict) -> list[str]:
    """What in the session's opening line differs from what was asked."""
    problems = []
    mode = init.get("permissionMode") or ""
    if MODE_ALIASES.get(mode, mode) != conf["mode"]:
        problems.append(f"permission mode {mode or 'unreported'!r}, asked {conf['mode']!r}"
                        + ((" (CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set, which forces Manual)" if conf.get("scrub")
                            else " (auto mode is unavailable to this session)") if conf["mode"] == "auto" else ""))
    model = (init.get("model") or "").lower()
    if stage["model"] and stage["model"].lower() not in model:
        problems.append(f"model {init.get('model')!r}, asked {stage['model']!r}")
    effort = init.get("effort")
    want = effort_flag(stage["effort"])
    if want and effort and effort != want:
        problems.append(f"effort {effort!r}, asked {want!r}")
    return problems


# --- git and files ------------------------------------------------------------

def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """One git command, stopped after GIT_TIMEOUT_SECONDS (raises GitTimeout).

    A child that keeps git's output pipe open after git is stopped (an ssh
    transport, on Windows) can still block the wait; the watchdog is the
    backstop for that.
    """
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise GitTimeout(f"`git {' '.join(args)}` gave no answer in {GIT_TIMEOUT_SECONDS:g} s") from None


def stage_heads(repo: Path, plan_branch: str, stage_id: str) -> dict[str, str]:
    """The stage's branches (`<plan>-s<N>`, `-redo-<K>`) as `{ref: sha}`, on
    origin when there is one, else local."""
    want = re.compile(rf"refs/heads/{re.escape(plan_branch)}-s{re.escape(stage_arg(stage_id).lower())}(-redo-\d+)?$")
    r = git(repo, "ls-remote", "--heads", "origin")
    if r.returncode:
        r = git(repo, "for-each-ref", "--format=%(objectname)\t%(refname)", "refs/heads")
    heads = (line.split("\t", 1) for line in r.stdout.splitlines() if "\t" in line)
    return {ref.strip(): sha for sha, ref in heads if want.match(ref.strip())}


def current_branch(repo: Path) -> str:
    r = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if r.returncode:
        raise PlanError(f"{repo} is not a git clone")
    return r.stdout.strip()


def default_branch(repo: Path) -> str:
    r = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return r.stdout.strip().split("/", 1)[-1] if r.returncode == 0 else ""


def state_dir(repo: Path, branch: str) -> Path:
    r = git(repo, "rev-parse", "--git-common-dir")
    base = Path(r.stdout.strip())
    if not base.is_absolute():
        base = repo / base
    slug = branch[5:] if branch.startswith("plan-") else branch
    return base / "plan-run-local" / re.sub(r"[^A-Za-z0-9._-]", "-", slug)


class PlanSource:
    """Plan files as pushed: `origin/<branch>` when it exists, else the tree.

    A stage's own push is the completion signal, so the pushed copy is the
    one read; a clone with no remote branch reads its working tree.
    """

    def __init__(self, repo: Path, branch: str):
        self.repo, self.branch = repo, branch

    def refresh(self) -> None:
        git(self.repo, "fetch", "--quiet", "origin", self.branch)

    def remote(self) -> bool:
        ref = f"refs/remotes/origin/{self.branch}"
        return git(self.repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0

    def read(self, name: str) -> str | None:
        if self.remote():
            r = git(self.repo, "show", f"origin/{self.branch}:{PLAN_DIR}/{name}")
            return r.stdout if r.returncode == 0 else None
        path = self.repo / PLAN_DIR / name
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def load(self) -> tuple[list[dict], dict, dict]:
        plan = self.read("PLAN.md")
        if plan is None:
            raise PlanError(f"no {PLAN_DIR}/PLAN.md on {self.branch}")
        ledger = self.read("LEDGER.md") or ""
        blocked = self.read("BLOCKED.md") or ""
        return parse_index(plan), parse_ledger(ledger), parse_blocked(blocked)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def heartbeat_age(state: dict) -> float | None:
    """Seconds since a status file's `updated`, or None when unreadable."""
    try:
        seen = datetime.strptime(state["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - seen).total_seconds()


def pid_alive(pid) -> bool:
    """Whether a process with this id is running. It may be another process
    that reused the id; the caller says so rather than acting on it."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) terminates the process on Windows: ask the kernel instead.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def recorded_sessions(state: dict | None) -> list[dict]:
    """The stage sessions a status file records as in flight: its
    `in_flight` list, and the single `current` one a status file written
    before stages ran side by side carries."""
    state = state or {}
    records = list(state.get("in_flight") or [])
    if isinstance(state.get("current"), dict):
        records.append(state["current"])
    return [r for r in records if isinstance(r, dict) and r.get("id")
            and not r.get("waiting") and not r.get("finished")]


def live_stage_sessions(state: dict | None) -> list[dict]:
    """The stage sessions an earlier driver recorded as in flight whose
    process is still running."""
    return [r for r in recorded_sessions(state) if pid_alive(r.get("pid"))]


# --- running one stage --------------------------------------------------------

def stop(proc: subprocess.Popen) -> None:
    """An interrupt, then terminate; Windows has no SIGINT for a child."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        for sig, wait in ((signal.SIGINT, INTERRUPT_SECONDS), (signal.SIGTERM, 10)):
            try:
                os.killpg(proc.pid, sig)
                proc.wait(wait)
                return
            except ProcessLookupError:
                return
            except subprocess.TimeoutExpired:
                continue
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    proc.wait()


def empty_result() -> dict:
    """What a stage session's watch returns before it has read anything."""
    return {"killed": None, "mismatch": [], "session_id": None, "result": None,
            "is_error": None, "usage": None, "window_first": None, "window_last": None,
            "limit": None, "exit_code": None}


def spawn_stage(cmd: list[str], cwd: Path) -> subprocess.Popen:
    """Start one stage session in its own process group. `cwd` is the clone,
    on the plan branch: the session makes its own stage worktree there."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **kwargs)


def run_stage(cmd: list[str], cwd: Path, log: Path, stage: dict, conf: dict,
              beat, started=None, on_window=None) -> dict:
    """Start one stage session and watch it to its end (`watch_stage`).
    `started(proc)` is called once the session's process exists."""
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = spawn_stage(cmd, cwd)
    if started:
        started(proc)
    return watch_stage(proc, log, stage, conf, beat, on_window)


def watch_stage(proc: subprocess.Popen, log: Path, stage: dict, conf: dict,
                beat, on_window=None) -> dict:
    """Watch one stage session to its end; never reads past what it needs.

    Every stream-json line goes to `log`. The opening `system/init` line is
    checked against what was asked and the session is stopped before any
    work on a mismatch. No line for the idle threshold stops it too.
    `on_window(window)` is called with each 5-hour reading as it arrives.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    lines: queue.Queue = queue.Queue()

    def pump():
        try:
            for line in proc.stdout:
                lines.put(line)
        except (OSError, ValueError):  # closed under it after a stop
            pass
        lines.put(None)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    result = empty_result()
    last = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        while True:
            try:
                line = lines.get(timeout=min(HEARTBEAT_SECONDS, conf["idle_seconds"]))
            except queue.Empty:
                beat()
                if time.monotonic() - last >= conf["idle_seconds"]:
                    result["killed"] = "idle"
                    stop(proc)
                    break
                continue
            if line is None:
                break
            last = time.monotonic()
            out.write(line)
            out.flush()
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            window = five_hour(event)
            if window:
                result["window_first"] = result["window_first"] or window
                result["window_last"] = window
                if on_window:
                    on_window(window)
            hit = limit_hit(event)
            if hit:
                seen = result["limit"] or {}
                result["limit"] = {k: seen.get(k) if seen.get(k) is not None else hit[k] for k in hit}
            if event.get("type") == "system" and event.get("subtype") == "init":
                result["session_id"] = event.get("session_id")
                result["init"] = {k: event.get(k) for k in
                                  ("model", "permissionMode", "effort", "claude_code_version")}
                result["mismatch"] = check_init(event, stage, conf)
                if result["mismatch"]:
                    result["killed"] = "mismatch"
                    stop(proc)
                    break
            elif event.get("type") == "result":
                result["result"] = (event.get("result") or "")[:500]
                result["is_error"] = event.get("is_error")
                result["usage"] = event.get("usage")
    try:
        proc.wait(30)
    except subprocess.TimeoutExpired:
        stop(proc)
    reader.join(5)
    proc.stdout.close()
    result["exit_code"] = proc.returncode
    return result


# --- the driver ---------------------------------------------------------------

class Driver:
    def __init__(self, repo: Path, env: dict, launcher_argv: list[str] | None = None,
                 grace_seconds: float = GRACE_SECONDS, usage: dict | None = None):
        self.repo = repo
        self.env = env
        self.launcher_argv = launcher_argv
        self.grace = grace_seconds
        self.branch = current_branch(repo)
        self.dir = state_dir(repo, self.branch)
        self.status_path = self.dir / "status.json"
        self.events_path = self.dir / EVENTS_FILE
        self.state: dict = {}
        self.reading = usage      # the latest 5-hour reading: {"percent", "resets_at"}
        self.max_jump: float | None = None
        self.clock = time.time    # replaced in tests, with `sleep`
        self.sleep = time.sleep
        self.stagger = START_STAGGER_SECONDS
        self.free_memory = free_memory_mb  # replaced in tests
        # Stages in flight: id -> {"stage", "record", "proc", "heads", "before", "start"}.
        # Their sessions are watched in threads that only read the stream;
        # every git command and every decision stays on the main loop.
        self.running: dict[str, dict] = {}
        self.finished: queue.Queue = queue.Queue()   # (stage id, watch result)
        self.stops: list[dict] = []     # why a person is needed, in the order found
        self.retry: dict[str, float] = {}  # stage id -> when its limit reset is waited out
        self.ended: set[str] = set()    # stages that ended short of `done` this run
        self.last_start: float | None = None
        # The watchdog: the main loop's heartbeat and what it is doing.
        # `emit` and `exit` are replaced in tests.
        self.lock = threading.RLock()
        self.beat_at = time.monotonic()
        self.doing = "starting"
        self.hung: str | None = None    # the driver-hung STATUS line, once reported
        self.done = threading.Event()
        self.stale = STALE_SECONDS
        self.watch_every = WATCH_SECONDS
        self.emit = lambda line: print(line, flush=True)
        self.exit = os._exit

    # status file
    def save(self) -> None:
        """Write the status file; every write is also the main loop's heartbeat."""
        with self.lock:
            if self.hung:
                raise Hung()
            self.beat_at = time.monotonic()
            self.state["updated"] = now()
            write_json(self.status_path, self.state)

    def step(self, doing: str) -> None:
        """Name what the main loop does next, for the watchdog's report."""
        self.doing = doing
        self.save()

    def running_text(self) -> str:
        parts = [f"{sid}'s session (process {e['proc'].pid})" for sid, e in self.running.items()]
        return "running " + " and ".join(parts) if parts else "running no stage session"

    def watch(self) -> None:
        """The watchdog thread: when the main loop has not beaten for
        `stale` seconds, report the driver hung, stop every stage session in
        flight, record it and exit the process, which wakes the orchestrator."""
        while not self.done.wait(self.watch_every):
            with self.lock:
                if self.done.is_set():
                    return
                quiet = time.monotonic() - self.beat_at
                if quiet < self.stale:
                    continue
                message = (f"the driver made no progress for {quiet / 60:.0f} min "
                           f"(the limit is {self.stale / 60:g}) while {self.doing}")
                stopped = []
                for sid, entry in list(self.running.items()):
                    proc = entry["proc"]
                    if proc.poll() is None:
                        stop(proc)
                        stopped.append(f"{sid}'s session (process {proc.pid})")
                if stopped:
                    message += "; stopped " + ", ".join(stopped)
                message += ("; nothing was written to the ledger. `driver status` and each stage's log "
                            "show where it stood")
                line = f"STATUS: driver-hung · {message}"
                self.hung = line
                # `in_flight` stays: a session that would not stop is found by the next run.
                self.state.update({"state": "exited", "status": "driver-hung", "message": message,
                                   "line": line, "updated": now()})
                write_json(self.status_path, self.state)
                self.emit(line)
                self.exit(0)
                return

    def finish(self, status: str, message: str, **extra) -> str:
        usage = self.state.get("usage") or {}
        if self.state.get("stages") and not usage.get("seen"):
            message += " · usage gate skipped: no stage session reported a 5-hour reading"
        line = f"STATUS: {status} · {message}"
        with self.lock:
            left = [e["record"] for e in self.running.values() if e["proc"].poll() is None]
        self.state.update({"state": "exited", "status": status, "message": message,
                           "line": line, "in_flight": left, "waiting": None, **extra})
        self.save()
        return line

    def halt(self, status: str, message: str, stage: str | None = None, **extra) -> None:
        """Record why a person is needed: nothing more starts, and the run
        ends once the stages in flight have ended."""
        self.stops.append({"status": status, "message": message, "stage": stage, **extra})
        self.state["stops"] = self.stops
        self.save()

    def finish_stops(self) -> str:
        """End on the stops found, the first one's status leading the line."""
        for sid, until in list(self.retry.items()):  # a wait the stopping run will not make
            self.halt("stage-limited", f"{sid} hit the usage limit, which resets "
                      f"{clock_text(until - RESET_MARGIN_SECONDS)}; the run stopped for another stage "
                      f"instead of waiting, so after the reset run {resume_hint(sid)}", stage=sid)
        self.retry.clear()
        first, rest = self.stops[0], self.stops[1:]
        message = first["message"] + "".join(f" · also {s['status']}: {s['message']}" for s in rest)
        extra = {k: v for k, v in first.items() if k not in ("status", "message")}
        return self.finish(first["status"], message, **extra)

    def event(self, line: str) -> None:
        """Append one progress line to the events file. Best effort."""
        try:
            with self.events_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
                fh.flush()
        except OSError:
            pass

    # preflight
    def launcher(self, conf: dict) -> list[str] | None:
        if self.launcher_argv:
            return self.launcher_argv
        found = shutil.which(conf["launcher"])
        return [found] if found else None

    def preflight(self, conf: dict) -> tuple[str, str] | None:
        launcher = self.launcher(conf)
        if not launcher:
            return ("launcher-missing",
                    f"{conf['launcher']!r} is not on PATH (CLAUDE_STAGE_LAUNCHER names the command)")
        self.cmd_prefix = launcher
        if self.launcher_argv:
            return None
        ver = subprocess.run([*launcher, "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        found = parse_version(ver.stdout)
        if not found or found < MIN_VERSION:
            want = ".".join(map(str, MIN_VERSION))
            return ("version-too-old",
                    f"Claude Code {ver.stdout.strip() or 'unknown'}; {want} or later is needed")
        auth = subprocess.run([*launcher, "auth", "status"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        try:
            logged_in = json.loads(auth.stdout).get("loggedIn") is True
        except (ValueError, AttributeError):
            logged_in = False
        if auth.returncode or not logged_in:
            return ("not-logged-in",
                    "stage sessions are not logged in: run `claude auth login` in a terminal, "
                    "or point CLAUDE_STAGE_LAUNCHER at a wrapper that supplies the login")
        return None

    def running_elsewhere(self) -> bool:
        old = read_json(self.status_path)
        if not old or old.get("state") != "running":
            return False
        age = heartbeat_age(old)
        return age is not None and age < STALE_SECONDS

    # the usage limit
    def current_reading(self) -> dict | None:
        """The latest reading, or a fresh window once its reset has passed."""
        r = self.reading
        if r and r.get("resets_at") is not None and r["resets_at"] <= self.clock():
            return {"percent": 0.0, "resets_at": None}
        return r

    def saw_window(self, window: dict) -> None:
        """A stage session's stream reported the 5-hour window: the latest
        reading from any session is the account's share now."""
        with self.lock:
            self.reading = window

    def note_usage(self, **fields) -> None:
        usage = self.state.setdefault("usage", {})
        usage.update(fields)
        usage["reading"], usage["max_jump"] = self.reading, self.max_jump

    def pause(self, until: float) -> None:
        """Sleep to `until` on the driver's clock, keeping the heartbeat."""
        while (left := until - self.clock()) > 0:
            self.sleep(min(HEARTBEAT_SECONDS, left))
            self.save()

    def wait_until(self, until: float, stage_ids: list[str], why: str) -> None:
        """Sleep to `until`, keeping the heartbeat so no second driver starts.
        Only ever called with nothing in flight."""
        wait = {"id": stage_ids[0], "ids": stage_ids, "why": why, "from": now(),
                "until": clock_text(until)}
        self.state.setdefault("waits", []).append(wait)
        self.state["waiting"] = {"ids": stage_ids, "why": why, "until": wait["until"]}
        self.step(f"waiting until {wait['until']} for the usage limit to reset before "
                  f"{', '.join(stage_ids)}")
        self.event(f"{', '.join(stage_ids)} waiting for the usage reset at "
                   f"{clock_text(until - RESET_MARGIN_SECONDS)}")
        self.pause(until)
        wait["ended"] = now()
        self.state["waiting"] = None
        # The window just reset: no reading until a stage reports one.
        self.reading = None
        self.note_usage()
        self.save()

    def gate(self, stage: dict, conf: dict) -> tuple[str | None, bool]:
        """With nothing in flight: hold `stage` until the reset when the share
        says so. Returns (a STATUS line when the hold cannot be waited out,
        whether it waited); (None, False) means it may start now."""
        reading = self.current_reading()
        hold = gate_holds(reading and reading["percent"], self.max_jump)
        # A window that has just reset has nothing left to wait for: the stage starts.
        fresh = hold and reading["resets_at"] is None
        line = gate_line(stage["id"], reading, self.max_jump, hold and not fresh)
        if fresh:
            line += " (the window has just reset, so there is no later reset to wait for)"
        self.note_usage(gate=line)
        self.save()
        if not hold or fresh:
            return None, False
        until = reading["resets_at"] + RESET_MARGIN_SECONDS
        if until - self.clock() > conf["max_wait_seconds"]:
            return self.finish("usage-held", f"{line}, more than CLAUDE_STAGE_MAX_WAIT_HOURS away; "
                               "run /plan-run-local again then", stage=stage["id"]), False
        self.wait_until(until, [stage["id"]], "gate")
        return None, True

    def ramp(self, stage: dict) -> bool:
        """Beside stages in flight: may `stage` start now? Records the line."""
        reading = self.current_reading()
        running = list(self.running)
        allowed = ramp_allows(reading and reading["percent"], self.max_jump, len(running))
        self.note_usage(gate=ramp_line(stage["id"], reading, self.max_jump, running, allowed))
        self.save()
        return allowed

    def room(self, stage: dict, conf: dict) -> bool:
        """May `stage` start now, for the machine's memory and the cap?
        Records the line. A running stage is never stopped to make room."""
        running = list(self.running)
        free = self.free_memory()
        cap = conf["max_parallel"]
        allowed = room_allows(free, len(running), cap)
        self.state["resources"] = {
            "free_mb": None if free is None else round(free), "max_parallel": cap,
            "held": not allowed, "line": room_line(stage["id"], free, running, cap,
                                                   conf["max_parallel_from"], allowed)}
        self.save()
        return allowed

    def measure(self, record: dict, start: dict | None, ran: dict) -> None:
        """Fold a finished stage's readings into the gate's state. The
        reading itself is kept current by `saw_window` as lines arrive."""
        first, last = ran.get("window_first"), ran.get("window_last")
        if last:
            self.state.setdefault("usage", {})["seen"] = True
        jump = stage_jump(start, last)
        if jump is None:  # no reading before the stage, or a reset between: its own first line
            jump = stage_jump(first, last)
        record["usage_window"] = {"start": start, "first": first, "last": last, "jump": jump}
        if jump is not None:
            self.max_jump = jump if self.max_jump is None else max(self.max_jump, jump)
        self.note_usage()

    def run(self, resume: str | list[str] | None = None) -> str:
        """Run until a person is needed; the one STATUS line. A hang ends in
        the watchdog's own line and exit instead (`driver-hung`)."""
        try:
            return self.loop(resume)
        except GitTimeout as e:
            message = f"{e} while {self.doing}; check the network and the remote, then run /plan-run-local again"
            if self.state.get("state") != "running":  # before this run owned the status file
                return f"STATUS: git-timeout · {message}"
            first = next(iter(self.running), None)
            try:
                unread = self.drain_unread()
            except Hung:
                return self.hung or "STATUS: driver-hung"
            if unread:
                message += (f"; {', '.join(unread)} ran on to {'their' if len(unread) > 1 else 'its'} end "
                            "unread, so `driver status` and the logs show where each stood")
            return self.finish("git-timeout", message, stage=first)
        except Hung:
            return self.hung or "STATUS: driver-hung"
        finally:
            self.done.set()

    def drain_unread(self) -> list[str]:
        """Git is not answering: let the sessions in flight end, recording
        them unread (classifying them needs git)."""
        unread = []
        while self.running:
            self.step(self.running_text() + " to their end; git is not answering")
            sid, ran = self.wait_any()
            with self.lock:
                entry = self.running.pop(sid)
                record = entry["record"]
                record.update({k: ran.get(k) for k in ("session_id", "exit_code", "killed", "result")})
                record.update({"finished": now(), "outcome": "unread"})
                self.state["in_flight"].remove(record)
                self.state["stages"].append(record)
            self.event(f"{sid} finished: unread")
            unread.append(sid)
        self.save()
        return unread

    def wait_any(self) -> tuple[str, dict]:
        """Block until a stage in flight ends, beating the heartbeat."""
        self.step(self.running_text())
        while True:
            try:
                return self.finished.get(timeout=HEARTBEAT_SECONDS)
            except queue.Empty:
                self.save()

    def loop(self, resume: str | list[str] | None) -> str:
        if self.branch in PROTECTED or self.branch == default_branch(self.repo):
            return f"STATUS: protected-branch · {self.branch} is protected; check out the plan branch"
        if self.running_elsewhere():
            return f"STATUS: already-running · a driver for {self.branch} updated {self.status_path} within {STALE_SECONDS // 60} min"
        alive = live_stage_sessions(read_json(self.status_path))
        if alive:
            # The status file is left as it is, so the next run finds the sessions too.
            named = "; ".join(f"{a['id']}'s session from an earlier driver (process {a['pid']}), log "
                              f"{a.get('log')}," for a in alive)
            many = len(alive) > 1
            return (f"STATUS: stage-session-alive · {named} {'are' if many else 'is'} still running, so "
                    f"no second session was started. Let {'them' if many else 'it'} end or stop "
                    f"{'them' if many else 'it'} yourself, then run /plan-run-local again. If a log has "
                    "stopped growing, its process id may have been reused by another program")
        self.state = {"state": "running", "plan_branch": self.branch, "started": now(),
                      "status_file": str(self.status_path), "stages": [], "in_flight": [],
                      "waiting": None}
        self.save()
        threading.Thread(target=self.watch, name="watchdog", daemon=True).start()
        try:
            conf = settings(self.env)
        except PlanError as e:
            return self.finish("bad-setting", str(e))
        self.state["settings"] = {k: v for k, v in conf.items()
                                  if k not in ("idle_seconds", "max_wait_seconds")}
        self.state["settings"]["idle_minutes"] = conf["idle_seconds"] / 60
        self.state["settings"]["max_wait_hours"] = conf["max_wait_seconds"] / 3600
        self.state["settings"]["start_at_once"] = START_AT_ONCE
        self.state["settings"]["stage_session_mb"] = STAGE_SESSION_MB
        self.state["settings"]["memory_margin"] = MEMORY_MARGIN
        self.state["usage"] = {"seeded": self.reading, "seen": False}
        self.note_usage()
        self.step("checking the launcher's version and login")
        stopped = self.preflight(conf)
        if stopped:
            return self.finish(*stopped)
        source = PlanSource(self.repo, self.branch)
        first = [sid for item in ([resume] if isinstance(resume, str) else resume or [])
                 for sid in item.replace(",", " ").split()]
        limit_runs: dict[str, int] = {}
        while True:
            while True:  # classify every stage that has ended, without blocking
                try:
                    sid, ran = self.finished.get_nowait()
                except queue.Empty:
                    break
                self.conclude(sid, ran, source, conf, limit_runs)
            if self.stops:
                if self.running:
                    self.finished.put(self.wait_any())
                    continue
                return self.finish_stops()
            # A limit hit is waited out once nothing is in flight; nothing new starts meanwhile.
            pending = {sid: t for sid, t in self.retry.items() if t > self.clock()}
            if pending:
                if self.running:
                    self.finished.put(self.wait_any())
                    continue
                self.wait_until(max(pending.values()), sorted(pending), "limit")
                continue
            self.step(f"fetching origin/{self.branch} and reading the plan")
            if current_branch(self.repo) != self.branch:
                self.halt("branch-changed", f"the clone left {self.branch}; nothing more was started")
                continue
            source.refresh()
            try:
                stages, ledger, blocked = source.load()
            except PlanError as e:
                self.halt("no-plan", str(e))
                continue
            by_id = {s["id"]: s for s in stages}
            named: list[dict] = []
            for sid in [*self.retry, *first]:  # limit retries, then `--resume`, before the runnable set
                stage = by_id.get(sid)
                if stage is None:
                    self.halt("bad-index", f"--resume {sid}: no such stage in the index")
                elif stage["gate"] not in FIRED_GATES:
                    self.halt("gated", f"{sid} has gate {stage['gate']!r}; run /stage-run {stage_arg(sid)} yourself",
                              gated=[{"id": sid, "gate": stage["gate"]}])
                elif stage not in named:
                    named.append(stage)
            if self.stops:
                first = []
                continue
            pick = select(stages, ledger, blocked)
            self.state["gated"] = pick["gated"]
            skip = {s["id"] for s in named} | self.ended
            candidates = named + [s for s in pick["runnable"] if s["id"] not in skip]
            stage = next_to_start(candidates, [e["stage"] for e in self.running.values()])
            if stage is None:
                if self.running:
                    self.finished.put(self.wait_any())
                    continue
                return self.settle(pick)
            try:
                cmd = stage_command(self.cmd_prefix, stage, conf)
            except PlanError as e:
                self.halt("bad-index", f"{stage['id']}: {e}", stage=stage["id"])
                continue
            roomy = self.room(stage, conf)
            if self.running:
                usable = self.ramp(stage)  # both are recorded, so `driver status` names either hold
                if not (roomy and usable):
                    self.finished.put(self.wait_any())
                    continue
                if self.last_start is not None and self.clock() < self.last_start + self.stagger:
                    self.step(f"waiting to start {stage['id']} {self.stagger:g} s after the last start")
                    self.pause(self.last_start + self.stagger)
                    continue  # whatever ended meanwhile is read first
            elif stage["id"] not in self.retry:  # a stage that waited out its limit starts unchecked
                held, waited = self.gate(stage, conf)
                if held:
                    return held
                if waited:
                    continue  # read the plan again after the wait
            first = [sid for sid in first if sid != stage["id"]]
            self.retry.pop(stage["id"], None)
            self.start(stage, cmd, conf, ledger)

    def start(self, stage: dict, cmd: list[str], conf: dict, ledger: dict) -> None:
        """Start one stage session and hand its stream to a watching thread."""
        sid = stage["id"]
        start = self.current_reading()
        record = {"id": sid, "model": stage["model"] or "session default",
                  "effort": effort_flag(stage["effort"]) or "session default",
                  "gate": stage["gate"], "started": now(),
                  "log": str(self.dir / f"{sid}.jsonl")}
        self.step(f"listing {sid}'s stage branches before it starts")
        heads = stage_heads(self.repo, self.branch, sid)
        self.doing = f"starting {sid}'s session"
        log = Path(record["log"])
        log.parent.mkdir(parents=True, exist_ok=True)
        proc = spawn_stage(cmd, self.repo)
        record["pid"] = proc.pid
        with self.lock:
            self.running[sid] = {"stage": stage, "record": record, "proc": proc, "heads": heads,
                                 "before": ledger.get(sid, {}).get("status", "todo"), "start": start}
            self.state["in_flight"].append(record)
        self.last_start = self.clock()
        self.event(f"{sid} started ({record['model']}, {record['effort']})")
        self.step(self.running_text())

        def watch_one():
            try:
                ran = watch_stage(proc, log, stage, conf, lambda: None, self.saw_window)
            except Exception as e:  # the stream could not be read or logged
                stop(proc)
                ran = {**empty_result(), "killed": "error", "result": f"watching the session failed: {e}"[:500],
                       "exit_code": proc.returncode}
            self.finished.put((sid, ran))

        threading.Thread(target=watch_one, name=f"stage-{sid}", daemon=True).start()

    def conclude(self, sid: str, ran: dict, source: PlanSource, conf: dict,
                 limit_runs: dict[str, int]) -> None:
        """Classify a stage whose session has ended, from the pushed plan."""
        with self.lock:
            entry = self.running.pop(sid)
        record = entry["record"]
        record.update({k: ran.get(k) for k in
                       ("session_id", "exit_code", "killed", "mismatch", "is_error", "result", "usage",
                        "init", "limit")})
        record.update({"finished": now(), "outcome": "unread"})
        with self.lock:
            self.state["in_flight"].remove(record)
            self.state["stages"].append(record)
        try:
            self.classify(sid, entry, ran, source, conf, limit_runs)
        finally:  # every way a stage ends, a git timeout while reading it included
            self.event(f"{sid} finished: {record['outcome']}")

    def classify(self, sid: str, entry: dict, ran: dict, source: PlanSource, conf: dict,
                 limit_runs: dict[str, int]) -> None:
        """Read how an ended stage stands and record its outcome."""
        stage, record, heads, before = entry["stage"], entry["record"], entry["heads"], entry["before"]
        self.step(f"reading {sid}'s result from the pushed plan")
        self.measure(record, entry["start"], ran)
        if ran["limit"] is None or ran["limit"].get("resets_at") is None:
            logged = transcript_limit(ran.get("session_id"), self.env)
            if logged:
                ran["limit"] = {k: (ran["limit"] or {}).get(k) or logged[k] for k in logged}
                record["limit"] = ran["limit"]
        if ran["killed"] == "mismatch":
            record["outcome"] = "launch-mismatch"
            self.ended.add(sid)
            self.halt("launch-mismatch",
                      f"{sid} started with {'; '.join(ran['mismatch'])}; stopped before any work", stage=sid)
            return
        source.refresh()
        after, now_blocked = self.read_row(source, sid)
        pushed = stage_heads(self.repo, self.branch, sid) not in ({}, heads)
        limited = ran["limit"] is not None
        result = outcome(before, after, now_blocked, bool(ran["killed"]), pushed, limited)
        if result not in ("done", "stage-blocked") and self.grace:
            self.step(f"waiting {self.grace:g} s for {sid}'s push to settle")
            time.sleep(self.grace)
            self.step(f"reading {sid}'s result from the pushed plan again")
            source.refresh()
            after, now_blocked = self.read_row(source, sid)
            pushed = stage_heads(self.repo, self.branch, sid) not in ({}, heads)
            result = outcome(before, after, now_blocked, bool(ran["killed"]), pushed, limited)
        record.update({"outcome": result, "pushed": pushed, "row": after})
        self.save()
        if result == "done":
            limit_runs.pop(sid, None)
            self.ended.discard(sid)
            return
        self.ended.add(sid)
        if result == "stage-limited":
            stopped = self.limited(stage, ran["limit"], conf, limit_runs)
            if stopped:
                self.halt("stage-limited", stopped, stage=sid)
            return
        _, ledger, blocked = source.load()
        reason = blocked.get(sid) or ledger.get(sid, {}).get("result", "")
        msg = {
            "stage-blocked": f"{sid} is blocked: {reason or 'see .plan/BLOCKED.md'}",
            "stage-stopped": f"{sid} stopped short of `done` with no block recorded"
                             + (" after pushing its stage branch" if pushed else "")
                             + ": most often a merge that did not happen (a permission rule, red checks) "
                             "or the breaker; its session's last words are in the status file",
            "stage-dead": f"{sid} ended with its row still `{after}`"
                          + (" after going quiet for the idle threshold" if ran["killed"] == "idle" else "")
                          + "; nothing was written on its behalf",
        }[result]
        self.halt(result, msg, stage=sid)

    def limited(self, stage: dict, limit: dict, conf: dict, runs: dict[str, int]) -> str | None:
        """A stage ended on the usage limit: queue it to run again once its
        reset is waited out (None), or say why a person is needed."""
        sid = stage["id"]
        kind = f"the {limit['type'].replace('_', '-')} limit" if limit.get("type") else "the usage limit"
        if limit.get("resets_at") is None:
            return f"{sid} hit {kind} and no reset time could be read; once it resets, run {resume_hint(sid)}"
        if runs.get(sid, 0) >= LIMIT_RETRIES:
            return (f"{sid} hit {kind} again straight after waiting for its reset; the limit reads "
                    f"{clock_text(limit['resets_at'])} now. Run {resume_hint(sid)} when it has reset")
        until = max(limit["resets_at"], self.clock()) + RESET_MARGIN_SECONDS
        if until - self.clock() > conf["max_wait_seconds"]:
            return (f"{sid} hit {kind}, which resets {clock_text(limit['resets_at'])}, more than "
                    f"CLAUDE_STAGE_MAX_WAIT_HOURS away; then run {resume_hint(sid)}")
        if self.stops:
            return (f"{sid} hit {kind}, which resets {clock_text(limit['resets_at'])}; the run stopped for "
                    f"another stage instead of waiting, so after the reset run {resume_hint(sid)}")
        runs[sid] = runs.get(sid, 0) + 1
        self.retry[sid] = until
        return None

    def read_row(self, source: PlanSource, stage_id: str) -> tuple[str, bool]:
        try:
            _, ledger, blocked = source.load()
        except PlanError:
            return "unreadable", False
        return ledger.get(stage_id, {}).get("status", "todo"), stage_id in blocked

    def settle(self, pick: dict) -> str:
        ran = list(dict.fromkeys(s["id"] for s in self.state["stages"]))
        done = f"ran {', '.join(ran)}; " if ran else ""
        if pick["complete"]:
            return self.finish("plan-complete", f"{done}every stage is done or skipped; close the plan "
                                                "with /plan-staged-rollout:plan-close")
        if pick["gated"]:
            named = ", ".join(f"{g['id']} (gate {g['gate']})" for g in pick["gated"])
            return self.finish("gated", f"{done}left for a person: {named}")
        named = ", ".join(f"{w['id']} ({w['status']})" for w in pick["waiting"]) or "nothing"
        return self.finish("waiting", f"{done}nothing runnable; the rest waits on {named}")


def resume_hint(stage_id: str) -> str:
    return f"`driver run --resume {stage_id}` (from /plan-run-local) to pick the stage up"


# --- commands -----------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    usage = seed_reading(args.usage_percent, args.usage_resets_at)
    driver = Driver(Path(args.repo).resolve(), dict(os.environ), usage=usage)
    print(driver.run(resume=args.resume))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    branch = current_branch(repo)
    stages, ledger, blocked = PlanSource(repo, branch).load()
    pick = select(stages, ledger, blocked)
    conf = settings(dict(os.environ))
    usage = seed_reading(args.usage_percent, args.usage_resets_at)
    if usage and usage["resets_at"] <= time.time():
        usage = {"percent": 0.0, "resets_at": None}
    out = {"plan_branch": branch, "gated": pick["gated"], "waiting": pick["waiting"],
           "complete": pick["complete"], "runnable": pick["runnable"],
           "start_together": [], "stage": None, "command": None, "usage_gate": None,
           "resources": None, "events_file": (state_dir(repo, branch) / EVENTS_FILE).as_posix()}
    if pick["stage"]:
        out["stage"] = pick["stage"]
        out["command"] = stage_command([conf["launcher"]], pick["stage"], conf)
        hold = gate_holds(usage and usage["percent"], None)
        out["usage_gate"] = {"hold": hold, "line": gate_line(pick["stage"]["id"], usage, None, hold)}
        free = free_memory_mb()
        out["resources"] = {"free_mb": None if free is None else round(free),
                            "max_parallel": conf["max_parallel"], "from": conf["max_parallel_from"]}
        together: list[dict] = []
        while not hold:  # nothing is measured before the run, so the ramp-up's opening step
            stage = next_to_start(pick["runnable"], together)
            if (stage is None or not ramp_allows(usage and usage["percent"], None, len(together))
                    or not room_allows(free, len(together), conf["max_parallel"])):
                break
            together.append(stage)
        out["start_together"] = [s["id"] for s in together]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    path = state_dir(repo, current_branch(repo)) / "status.json"
    state = read_json(path)
    if state is None:
        print(f"No run recorded for this plan ({path}).")
        return 0
    age = heartbeat_age(state)
    gone = state.get("state") == "running" and (age is None or age >= STALE_SECONDS)
    if gone:
        since = f"{age / 60:.0f} min ago" if age is not None else "at an unreadable time"
        lines = [f"Driver gone · the status file still reads running, but it was last updated "
                 f"{state.get('updated')} ({since}): the driver crashed or was stopped without a "
                 f"STATUS line, so nothing is running these stages · started {state.get('started')}"]
    else:
        lines = [f"Driver {state.get('state')} · started {state.get('started')} · updated {state.get('updated')}"]
    for s in state.get("stages", []):
        lines.append(f"  {s['id']}: {s.get('outcome')} · model {s['model']}, effort {s['effort']} · "
                     f"{s['started']} → {s.get('finished')}")
    waiting = state.get("waiting")
    legacy = state.get("current")  # a status file from before stages ran side by side
    if not waiting and isinstance(legacy, dict) and legacy.get("waiting"):
        waiting = {"ids": [legacy["id"]], "why": legacy["waiting"], "until": legacy.get("until")}
    if waiting:
        why = "the usage gate held it" if waiting["why"] == "gate" else "it hit the usage limit"
        then = "; it starts then" if state.get("state") == "running" and not gone else ", when the driver stopped"
        lines.append(f"  {', '.join(waiting['ids'])}: waiting until {waiting['until']} ({why}){then}")
    for cur in recorded_sessions(state):
        lines.append(f"  {cur['id']}: {'running' if not gone else 'was running'} since {cur['started']} · "
                     f"model {cur['model']}, effort {cur['effort']}")
        if cur.get("pid"):
            alive = pid_alive(cur["pid"])
            lines.append(f"  {cur['id']}'s session, process {cur['pid']}: "
                         + ("still running" if alive else "no longer running")
                         + f" · log {cur.get('log')}")
    gate = (state.get("usage") or {}).get("gate")
    if gate:
        lines.append(f"  last {gate}")
    room = (state.get("resources") or {}).get("line")
    if room:
        lines.append(f"  last {room}")
    if state.get("line"):
        lines.append(state["line"])
    print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="plan_run_local.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("run", cmd_run, "run stages until a person is needed"),
                            ("next", cmd_next, "say what run would start; runs nothing"),
                            ("status", cmd_status, "print the status file")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--repo", default=".", help="the clone, on the plan branch")
        sp.set_defaults(fn=fn)
        if name in ("run", "next"):
            sp.add_argument("--usage-percent", type=float, metavar="P",
                            help="the 5-hour limit's share used now, 0-100 (the desktop app's usage card)")
            sp.add_argument("--usage-resets-at", metavar="TIME",
                            help="when that window resets: ISO 8601 or epoch seconds")
        if name == "run":
            sp.add_argument("--resume", metavar="S<N>", action="append",
                            help="run this stage first: a `doing` row whose PR was merged outside "
                                 "the run, which the stage's preflight records `done`. Repeat it, "
                                 "or separate ids with commas, for several")
    return p


def main(argv: list[str] | None = None) -> int:
    # The STATUS line carries `·`; a Windows console code page would mangle it.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (PlanError, OSError) as e:
        print(f"plan_run_local.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
