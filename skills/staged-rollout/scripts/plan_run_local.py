#!/usr/bin/env python3
"""Drive a plan's remaining stages as fresh local `claude -p` sessions.

`/plan-run-local` starts `run` in the background from an interactive session
-- the orchestrator -- and is woken when it exits. The driver holds the loop:
it picks the next runnable stage, runs `/plan-staged-rollout:stage-run <N>
--unattended --runner local` as its own headless session at the model and
effort the stage index books, re-reads the ledger, and carries on while
stages land `done`. It exits only when a person is needed, printing one
`STATUS:` line that the orchestrator reads instead of any stage output.

Subcommands:

  run     Run runnable stages, one at a time, until a person is needed.
  next    Say which stage `run` would start, and the exact command. Runs nothing.
  status  Print the status file: the stages run so far and the one in flight.

What it never does: write `.plan/LEDGER.md` or `.plan/BLOCKED.md` (a stage's
own push is the only completion signal), fire a stage whose `gate` is
`human`, `live` or unknown, run two stages at once, open or merge a pull
request, or read a secret. Logging in is the launcher's job.

Settings, from the environment:

  CLAUDE_STAGE_LAUNCHER         One executable, no arguments, run in place of
                                `claude` with the same arguments (a wrapper
                                that supplies a login). Default `claude`.
  CLAUDE_STAGE_PERMISSION_MODE  `auto` (default), `manual`, `acceptEdits` or
                                `dontAsk`.
  CLAUDE_STAGE_IDLE_MINUTES     Minutes without a stream-json line before a
                                stage session is stopped. Default 15.
  CLAUDE_STAGE_MAX_BUDGET_USD   Passed as `--max-budget-usd`. Unset: no cap.

The status file and the logs live outside `.plan/`, in the clone's git
directory: `<git common dir>/plan-run-local/<plan slug>/`.

Invoke as `python <path>/plan_run_local.py <subcommand> [--repo <dir>]`.

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
PLAN_DIR = ".plan"


class PlanError(Exception):
    pass


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
    """The next stage to run, and why nothing else is.

    Returns {"stage": <row or None>, "gated": [...], "waiting": [...],
    "complete": bool}. A stage is runnable when its row reads `todo` (or is
    missing) and every `depends` entry reads `done` or `skipped`; it is fired
    only when its gate is `auto`, absent or `local`. Index order breaks ties.
    A stage with a BLOCKED.md section reads `blocked` until a person deletes
    the section, whatever its row says, as it does for the cloud runner.
    """
    status = {s["id"]: ledger.get(s["id"], {}).get("status", "todo") for s in stages}
    for sid in blocked or {}:
        if sid in status and status[sid] not in CLOSED:
            status[sid] = "blocked"
    gated, waiting, chosen = [], [], None
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
        if chosen is None:
            chosen = s
    complete = all(v in CLOSED for v in status.values())
    return {"stage": chosen, "gated": gated, "waiting": waiting, "complete": complete}


def outcome(before: str, after: str, blocked: bool, killed: bool, pushed: bool = False) -> str:
    """Classify a finished stage session by its ledger row and stage branch.

    `done`/`skipped` carry on; `blocked`, or `doing` with a BLOCKED.md
    section, is a block; `doing` with none is a stop (a refused merge, the
    breaker). A row that never moved is a stop too when the session pushed its
    stage branch, since the `doing` flip rides that branch until it merges;
    with no push it is a dead run, as in remote-driver.md.
    """
    if after in CLOSED:
        return "done"
    if after == "blocked" or (after == "doing" and blocked):
        return "stage-blocked"
    if killed:
        return "stage-dead"
    if after == before:
        return "stage-stopped" if pushed else "stage-dead"
    if after == "doing":
        return "stage-stopped"
    return "stage-dead"


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
    try:
        idle_min = float(idle)
        if idle_min <= 0:
            raise ValueError
        if budget:
            float(budget)
    except ValueError:
        raise PlanError("CLAUDE_STAGE_IDLE_MINUTES must be a positive number and "
                        "CLAUDE_STAGE_MAX_BUDGET_USD a number") from None
    return {
        "launcher": env.get("CLAUDE_STAGE_LAUNCHER", "").strip() or "claude",
        "mode": mode,
        "idle_seconds": idle_min * 60,
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
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


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


def run_stage(cmd: list[str], cwd: Path, log: Path, stage: dict, conf: dict,
              beat) -> dict:
    """Run one stage session to its end; never reads past what it needs.

    Every stream-json line goes to `log`. The opening `system/init` line is
    checked against what was asked and the session is stopped before any
    work on a mismatch. No line for the idle threshold stops it too.
    """
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **kwargs)
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
    result = {"killed": None, "mismatch": [], "session_id": None, "result": None,
              "is_error": None, "usage": None}
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
                 grace_seconds: float = GRACE_SECONDS):
        self.repo = repo
        self.env = env
        self.launcher_argv = launcher_argv
        self.grace = grace_seconds
        self.branch = current_branch(repo)
        self.dir = state_dir(repo, self.branch)
        self.status_path = self.dir / "status.json"
        self.state: dict = {}

    # status file
    def save(self) -> None:
        self.state["updated"] = now()
        write_json(self.status_path, self.state)

    def finish(self, status: str, message: str, **extra) -> str:
        line = f"STATUS: {status} · {message}"
        self.state.update({"state": "exited", "status": status, "message": message,
                           "line": line, "current": None, **extra})
        self.save()
        return line

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
        try:
            seen = datetime.strptime(old["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            return False
        return (datetime.now(timezone.utc) - seen).total_seconds() < STALE_SECONDS

    def run(self, resume: str | None = None) -> str:
        if self.branch in PROTECTED or self.branch == default_branch(self.repo):
            return f"STATUS: protected-branch · {self.branch} is protected; check out the plan branch"
        if self.running_elsewhere():
            return f"STATUS: already-running · a driver for {self.branch} updated {self.status_path} within {STALE_SECONDS // 60} min"
        self.state = {"state": "running", "plan_branch": self.branch, "started": now(),
                      "status_file": str(self.status_path), "stages": [], "current": None}
        try:
            conf = settings(self.env)
        except PlanError as e:
            return self.finish("bad-setting", str(e))
        self.state["settings"] = {k: v for k, v in conf.items() if k != "idle_seconds"}
        self.state["settings"]["idle_minutes"] = conf["idle_seconds"] / 60
        self.save()
        stopped = self.preflight(conf)
        if stopped:
            return self.finish(*stopped)
        source = PlanSource(self.repo, self.branch)
        first = resume
        while True:
            if current_branch(self.repo) != self.branch:
                return self.finish("branch-changed",
                                   f"the clone left {self.branch}; nothing more was run")
            source.refresh()
            try:
                stages, ledger, blocked = source.load()
            except PlanError as e:
                return self.finish("no-plan", str(e))
            if first:
                stage = next((s for s in stages if s["id"] == first), None)
                if stage is None:
                    return self.finish("bad-index", f"--resume {first}: no such stage in the index")
                if stage["gate"] not in FIRED_GATES:
                    return self.finish("gated", f"{first} has gate {stage['gate']!r}; run /stage-run {stage_arg(first)} yourself",
                                       gated=[{"id": first, "gate": stage["gate"]}])
                first = None
                pick = {"stage": stage, "gated": [], "waiting": [], "complete": False}
            else:
                pick = select(stages, ledger, blocked)
            self.state["gated"] = pick["gated"]
            stage = pick["stage"]
            if stage is None:
                return self.settle(pick)
            try:
                cmd = stage_command(self.cmd_prefix, stage, conf)
            except PlanError as e:
                return self.finish("bad-index", f"{stage['id']}: {e}")
            before = ledger.get(stage["id"], {}).get("status", "todo")
            record = {"id": stage["id"], "model": stage["model"] or "session default",
                      "effort": effort_flag(stage["effort"]) or "session default",
                      "gate": stage["gate"], "started": now(),
                      "log": str(self.dir / f"{stage['id']}.jsonl")}
            self.state["current"] = record
            self.save()
            heads = stage_heads(self.repo, self.branch, stage["id"])
            ran = run_stage(cmd, self.repo, Path(record["log"]), stage, conf, self.save)
            record.update({k: ran.get(k) for k in
                           ("session_id", "exit_code", "killed", "mismatch", "is_error", "result", "usage", "init")})
            record["finished"] = now()
            if ran["killed"] == "mismatch":
                record["outcome"] = "launch-mismatch"
                self.state["stages"].append(record)
                return self.finish("launch-mismatch",
                                   f"{stage['id']} started with {'; '.join(ran['mismatch'])}; stopped before any work")
            source.refresh()
            after, now_blocked = self.read_row(source, stage["id"])
            pushed = stage_heads(self.repo, self.branch, stage["id"]) not in ({}, heads)
            result = outcome(before, after, now_blocked, bool(ran["killed"]), pushed)
            if result not in ("done", "stage-blocked") and self.grace:
                time.sleep(self.grace)
                source.refresh()
                after, now_blocked = self.read_row(source, stage["id"])
                pushed = stage_heads(self.repo, self.branch, stage["id"]) not in ({}, heads)
                result = outcome(before, after, now_blocked, bool(ran["killed"]), pushed)
            record["outcome"] = result
            record["pushed"] = pushed
            record["row"] = after
            self.state["stages"].append(record)
            self.state["current"] = None
            self.save()
            if result == "done":
                continue
            _, ledger, blocked = source.load()
            reason = blocked.get(stage["id"]) or ledger.get(stage["id"], {}).get("result", "")
            msg = {
                "stage-blocked": f"{stage['id']} is blocked: {reason or 'see .plan/BLOCKED.md'}",
                "stage-stopped": f"{stage['id']} stopped short of `done` with no block recorded"
                                 + (" after pushing its stage branch" if pushed else "")
                                 + ": most often a merge that did not happen (a permission rule, red checks) "
                                 "or the breaker; its session's last words are in the status file",
                "stage-dead": f"{stage['id']} ended with its row still `{after}`"
                              + (" after going quiet for the idle threshold" if ran["killed"] == "idle" else "")
                              + "; nothing was written on its behalf",
            }[result]
            return self.finish(result, msg, stage=stage["id"])

    def read_row(self, source: PlanSource, stage_id: str) -> tuple[str, bool]:
        try:
            _, ledger, blocked = source.load()
        except PlanError:
            return "unreadable", False
        return ledger.get(stage_id, {}).get("status", "todo"), stage_id in blocked

    def settle(self, pick: dict) -> str:
        ran = [s["id"] for s in self.state["stages"]]
        done = f"ran {', '.join(ran)}; " if ran else ""
        if pick["complete"]:
            return self.finish("plan-complete", f"{done}every stage is done or skipped; close the plan "
                                                "with /plan-staged-rollout:plan-close")
        if pick["gated"]:
            named = ", ".join(f"{g['id']} (gate {g['gate']})" for g in pick["gated"])
            return self.finish("gated", f"{done}left for a person: {named}")
        named = ", ".join(f"{w['id']} ({w['status']})" for w in pick["waiting"]) or "nothing"
        return self.finish("waiting", f"{done}nothing runnable; the rest waits on {named}")


# --- commands -----------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    driver = Driver(Path(args.repo).resolve(), dict(os.environ))
    print(driver.run(resume=args.resume))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    branch = current_branch(repo)
    stages, ledger, blocked = PlanSource(repo, branch).load()
    pick = select(stages, ledger, blocked)
    conf = settings(dict(os.environ))
    out = {"plan_branch": branch, "gated": pick["gated"], "waiting": pick["waiting"],
           "complete": pick["complete"], "stage": None, "command": None}
    if pick["stage"]:
        out["stage"] = pick["stage"]
        out["command"] = stage_command([conf["launcher"]], pick["stage"], conf)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    path = state_dir(repo, current_branch(repo)) / "status.json"
    state = read_json(path)
    if state is None:
        print(f"No run recorded for this plan ({path}).")
        return 0
    lines = [f"Driver {state.get('state')} · started {state.get('started')} · updated {state.get('updated')}"]
    for s in state.get("stages", []):
        lines.append(f"  {s['id']}: {s.get('outcome')} · model {s['model']}, effort {s['effort']} · "
                     f"{s['started']} → {s.get('finished')}")
    cur = state.get("current")
    if cur:
        lines.append(f"  {cur['id']}: running since {cur['started']} · model {cur['model']}, effort {cur['effort']}")
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
        if name == "run":
            sp.add_argument("--resume", metavar="S<N>",
                            help="run this stage first: a `doing` row whose PR was merged outside "
                                 "the run, which the stage's preflight records `done`")
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
