#!/usr/bin/env python3
"""Run a staged rollout unattended: launch one `/plan-run` session per runnable
stage, back to back, until nothing is runnable or something needs a person.

The driver is a re-scanning loop, not a pre-built schedule. Each round it reads
`.plan/LEDGER.md` and `.plan/PLAN.md`'s stage index, recomputes the runnable set
exactly as `commands/plan-run.md` step 6 does, launches the next stage as its own
`claude -p` session, waits for it, and re-reads the ledger. The ledger is the only
state; the driver holds none of its own between rounds.

It stops - and calls the notify command - on a `gate: human` stage, on a stage
that comes back anything other than `done` after the retry cap, and when closeout
is finished. Once every stage is `done` or `skipped` it launches one more session,
`/plan-close --unattended`, which applies the plan flags instead of asking and
opens the plan-to-main PR (`--no-close` stops before that instead). It never
targets a protected branch, and it never merges anything itself: merges belong to
the stage sessions under the plan's `merge` flag, and the plan-to-main PR is
manual in every mode - no flag, no argument and no runner may take that gate.

Sequential only. Parallel waves are deliberate future work - see README.

Stdlib only, so it runs wherever the plugin does.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Branch names the driver refuses to run on, whatever the repo's own policy
# says. The plan branch is the only correct place to drive a rollout from: the
# clone stays parked there for the life of the plan, and every stage lands via a
# PR into it. Running on a protected branch would mean stage sessions branching
# off it and, under `merge: auto`, merging back into it.
PROTECTED_BRANCHES = {"main", "master", "release", "trunk", "develop"}

# `S0`..`S99` and `SF`, the stage-id vocabulary the templates and the
# session-start hook already use.
STAGE_ID_RE = re.compile(r"^(S(?:\d{1,2}|F))(?:\s|$)")
LEDGER_STATUSES = {"todo", "doing", "done", "blocked", "skipped"}
EMPTY_CELLS = {"", "-", "—", "–"}
PLAN_FLAGS_RE = re.compile(r"^\**\s*Plan flags:", re.IGNORECASE)
MERGE_FLAG_RE = re.compile(r"merge:\s*`?(auto|manual)`?", re.IGNORECASE)
PLAN_DIR_FLAG_RE = re.compile(r"plan-dir:\s*`?(delete|keep)`?", re.IGNORECASE)

# `model`/`effort` in the stage index are launch hints written for humans;
# `--effort` on the CLI takes a fixed vocabulary. Map what the templates use and
# refuse to guess at anything else.
EFFORT_ALIASES = {
    "low": "low",
    "med": "medium",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
}

# The profile a stage session needs under `-p`. Documented in README §Unattended
# runs: with nobody to answer a prompt, any rule that would ask resolves as a
# denial, so the tools a stage actually uses have to be allowed up front.
DEFAULT_PERMISSION_MODE = "acceptEdits"
# `AskUserQuestion` is in the list even though an unattended session never asks:
# the profile is also what an operator copies to launch a session by hand, and a
# session that cannot offer buttons falls back to asking in prose.
DEFAULT_ALLOWED_TOOLS = [
    "Bash",
    "Edit",
    "Write",
    "Read",
    "Glob",
    "Grep",
    "Task",
    "Skill",
    "TodoWrite",
    "AskUserQuestion",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
]

NOTIFY_ENV = "PLAN_DRIVER_NOTIFY"


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def log(message: str = "") -> None:
    """Print a driver line. Stage sessions inherit stdio, so their output lands
    between these unprefixed."""
    print(f"[plan-driver] {message}" if message else "", flush=True)


def fail(message: str) -> None:
    print(f"[plan-driver] error: {message}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Parsing - mirrors hooks/session-start, which reads the same two tables
# --------------------------------------------------------------------------


@dataclass
class LedgerRow:
    stage_id: str
    name: str
    status: str
    cells: list[str]
    line_no: int


@dataclass
class IndexRow:
    stage_id: str
    name: str
    file: str
    depends: list[str]
    model: str
    effort: str
    gate: str


@dataclass
class Plan:
    ledger: list[LedgerRow] = field(default_factory=list)
    index: list[IndexRow] = field(default_factory=list)
    merge_flag: str = "manual"
    plan_dir_flag: str = "delete"


def split_row(line: str) -> list[str] | None:
    """Split a markdown table row into trimmed cells; None for non-table lines."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    body = stripped[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells = [c.strip() for c in body.split("|")]
    return cells if len(cells) >= 2 else None


def stage_id_of(cell: str) -> str | None:
    match = STAGE_ID_RE.match(cell.strip())
    return match.group(1) if match else None


def section_lines(text: str, heading_prefix: str) -> list[tuple[int, str]]:
    """Numbered lines of the first `## <heading_prefix>...` section. `###`
    subsections stay inside it, matching the session-start hook."""
    out: list[tuple[int, str]] = []
    inside = False
    for line_no, line in enumerate(text.splitlines()):
        if line.startswith("## "):
            if inside:
                break
            inside = line.startswith(f"## {heading_prefix}")
            continue
        if inside:
            out.append((line_no, line))
    return out


def parse_ledger(path: Path) -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    for line_no, line in section_lines(path.read_text(encoding="utf-8"), "Status"):
        cells = split_row(line)
        if not cells:
            continue
        stage_id = stage_id_of(cells[0])
        if not stage_id:
            continue
        status = cells[1].lower()
        if status not in LEDGER_STATUSES:
            continue
        rows.append(
            LedgerRow(
                stage_id=stage_id,
                name=cells[0][len(stage_id):].strip(),
                status=status,
                cells=cells,
                line_no=line_no,
            )
        )
    return rows


def parse_plan(path: Path) -> tuple[list[IndexRow], str, str]:
    rows: list[IndexRow] = []
    merge_flag = "manual"
    plan_dir_flag = "delete"
    for _, line in section_lines(path.read_text(encoding="utf-8"), "Stage index"):
        if PLAN_FLAGS_RE.match(line.strip()):
            match = MERGE_FLAG_RE.search(line)
            if match:
                merge_flag = match.group(1).lower()
            match = PLAN_DIR_FLAG_RE.search(line)
            if match:
                plan_dir_flag = match.group(1).lower()
            continue
        cells = split_row(line)
        if not cells or len(cells) < 3:
            continue
        stage_id = stage_id_of(cells[0])
        if not stage_id:
            continue

        def cell(i: int) -> str:
            value = cells[i].strip().strip("`") if i < len(cells) else ""
            return "" if value in EMPTY_CELLS else value

        # Anything left in this list that is not a known stage id makes the
        # stage un-runnable in deps_satisfied() - never launch on a guess.
        depends = [
            token
            for token in cells[2].replace(",", " ").split()
            if token not in EMPTY_CELLS
        ]
        rows.append(
            IndexRow(
                stage_id=stage_id,
                name=cells[0][len(stage_id):].strip(),
                file=cell(1),
                depends=depends,
                model=cell(5),
                effort=cell(6),
                gate=(cell(7) or "auto").lower(),
            )
        )
    return rows, merge_flag, plan_dir_flag


def load_plan(plan_dir: Path) -> Plan:
    index, merge_flag, plan_dir_flag = parse_plan(plan_dir / "PLAN.md")
    return Plan(
        ledger=parse_ledger(plan_dir / "LEDGER.md"),
        index=index,
        merge_flag=merge_flag,
        plan_dir_flag=plan_dir_flag,
    )


# --------------------------------------------------------------------------
# Runnable set - the same rule as commands/plan-run.md step 6
# --------------------------------------------------------------------------


def deps_satisfied(depends: list[str], statuses: dict[str, str]) -> bool:
    """Every listed dependency is `done` or `skipped` - a skip is a settled
    outcome (decided against), not an unmet one, so it must not deadlock a
    dependent. Anything unrecognized counts as NOT satisfied - the driver must
    never launch a stage on a guess."""
    for dep in depends:
        if not STAGE_ID_RE.match(dep):
            return False
        if statuses.get(dep) not in ("done", "skipped"):
            return False
    return True


def runnable_set(plan: Plan, statuses: dict[str, str]) -> list[IndexRow]:
    """Every `doing` stage (resumable) then every `todo` stage whose depends are
    all `done`, each in stage-index order. A stage missing from the index is
    invisible to this logic, exactly as PLAN.md says."""
    doing: list[IndexRow] = []
    todo: list[IndexRow] = []
    for row in plan.index:
        status = statuses.get(row.stage_id)
        if status == "doing":
            doing.append(row)
        elif status == "todo" and deps_satisfied(row.depends, statuses):
            todo.append(row)
    return doing + todo


def stage_argument(stage_id: str) -> str:
    """`S3` -> `3`, `SF` -> `f` - the token /plan-run takes."""
    return stage_id[1:].lower()


# --------------------------------------------------------------------------
# Notify
# --------------------------------------------------------------------------


def shell_quote(value: str) -> str:
    if os.name == "nt":
        return '"' + value.replace('"', '""') + '"'
    return shlex.quote(value)


def notify(command: str, event: str, message: str, stage_id: str, plan_dir: Path) -> None:
    """Shell out to the operator's notify command.

    The message is passed as one appended argument (with newlines flattened, so
    it stays a single argument) and every field is also exported, so a one-liner
    like `notify-send "plan driver"` and a script reading `$PLAN_DRIVER_EVENT`
    both work without a wrapper.
    """
    if not command:
        log(f"notify: {event} - {message}  (set ${NOTIFY_ENV} to be told out of band)")
        return
    env = os.environ.copy()
    env["PLAN_DRIVER_EVENT"] = event
    env["PLAN_DRIVER_MESSAGE"] = message
    env["PLAN_DRIVER_STAGE"] = stage_id
    env["PLAN_DRIVER_PLAN"] = str(plan_dir)
    one_line = " ".join(message.split())
    try:
        subprocess.run(
            f"{command} {shell_quote(one_line)}", shell=True, env=env, check=False
        )
    except OSError as exc:  # a broken notify command must never end the run
        fail(f"notify command failed to start: {exc}")


# --------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def repo_root(start: Path) -> Path | None:
    result = git(start, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def current_branch(root: Path) -> str:
    return git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def default_branch(root: Path) -> str:
    """The remote's default branch, or "" when it cannot be resolved offline."""
    result = git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if result.returncode != 0:
        return ""
    return result.stdout.strip().rsplit("/", 1)[-1]


def commit_driver_block(root: Path, plan_dir: Path, stage_id: str) -> None:
    """Commit (and push, when the branch has an upstream) the driver's own
    block note in `.plan/BLOCKED.md`, so the state survives the operator's
    absence. Never touches `.plan/LEDGER.md` - see record_driver_block."""
    rel = (plan_dir / "BLOCKED.md").relative_to(root).as_posix()
    if git(root, "add", "--", rel).returncode != 0:
        fail("could not stage BLOCKED.md; the block note is written but uncommitted")
        return
    message = f"chore(plan): record {stage_id} blocked - driver retry cap reached"
    result = git(root, "commit", "-m", message, "--", rel)
    if result.returncode != 0:
        fail(f"could not commit BLOCKED.md: {result.stderr.strip() or result.stdout.strip()}")
        return
    log(f"committed the block note for {stage_id}")
    if git(root, "rev-parse", "--abbrev-ref", "@{upstream}").returncode != 0:
        log("plan branch has no upstream - the block note is committed locally only")
        return
    push = git(root, "push")
    if push.returncode != 0:
        fail(f"could not push the block note: {push.stderr.strip()}")
    else:
        log("pushed the block note to the plan branch")


# --------------------------------------------------------------------------
# Driver block file - deliberately NOT `.plan/LEDGER.md`
# --------------------------------------------------------------------------
#
# By the time the driver hits the retry cap, the stage has usually already
# committed its own edits to LEDGER.md's row and notes on its own branch -
# real acceptance evidence, or a PR that opened but couldn't merge. Writing
# the driver's block into those same lines on the plan branch would diverge
# from that unmerged commit and leave the stage's own pull request
# unmergeable, which is exactly the failure this file exists to avoid (#89).
# `.plan/BLOCKED.md` is a sibling the stage branch never edits, so the two
# writers never contend for the same lines.

BLOCKED_HEADER = [
    "# Driver blocks",
    "",
    "Stages the unattended driver could not land in `LEDGER.md`, because the "
    "stage's own branch might already hold unmerged edits to it. A driver "
    "round treats every stage id listed below as `blocked` - never retried - "
    "even though its `LEDGER.md` row may still read `todo` or `doing`. "
    "Resolving a stage does not clear its section automatically: delete it "
    "once the stage reaches `done`.",
]


def read_driver_blocked_ids(plan_dir: Path) -> set[str]:
    """Stage ids with a section in `.plan/BLOCKED.md` - see record_driver_block."""
    path = plan_dir / "BLOCKED.md"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("### "):
            continue
        stage_id = stage_id_of(line[len("### ") :])
        if stage_id:
            ids.add(stage_id)
    return ids


def record_driver_block(
    plan_dir: Path,
    row: LedgerRow,
    attempts: int,
    last_status: str,
    plan_branch: str,
) -> None:
    """Append (or refresh) this stage's section in `.plan/BLOCKED.md`, instead of
    editing `.plan/LEDGER.md`'s row and notes - see the module note above."""
    path = plan_dir / "BLOCKED.md"
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    lines = (
        path.read_text(encoding="utf-8").splitlines() if path.exists() else list(BLOCKED_HEADER)
    )

    stage_branch = f"{plan_branch}-s{stage_argument(row.stage_id)}"
    # Wrapped to match the hand-written prose elsewhere in `.plan/`; an
    # unwrapped paragraph reads as machine spill.
    runbook = [
        f"Driver runbook ({today}): the unattended driver launched "
        f"{row.stage_id} {attempts} time(s) and it did not reach `done` — the "
        f"last status read back from `LEDGER.md` was `{last_status}`. Recorded "
        f"here rather than in `LEDGER.md`, because {row.stage_id}'s own branch "
        "may already hold unmerged ledger edits.",
        "",
        f"To unblock: check for an open pull request from `{stage_branch}` "
        f"(`gh pr list --head {stage_branch}`). If one exists, resolve whatever "
        "stopped it merging — a permission gate, a failing check — and merge it "
        "yourself. If none exists, run "
        f"`/plan-staged-rollout:plan-run {stage_argument(row.stage_id)}` in a "
        "fresh session with someone at the keyboard, to pick the stage back up "
        "from its unticked Steps. Either way, once the stage reads `done` in "
        f"`LEDGER.md`, delete this file's `### {row.stage_id}` section — the "
        "driver will not retry a stage listed here while its section remains, "
        "no matter what `LEDGER.md` says.",
    ]
    runbook = [
        "\n".join(textwrap.wrap(part, width=79)) if part else part for part in runbook
    ]

    heading = f"### {row.stage_id}"
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith(heading) and (len(line) == len(heading) or line[len(heading)] == " ")
        ),
        None,
    )
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"### {row.stage_id} {row.name}".rstrip(), "", *runbook])
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("### ")),
            len(lines),
        )
        lines[start + 1 : end] = ["", *runbook, ""]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Launching
# --------------------------------------------------------------------------


def session_profile(args: argparse.Namespace) -> list[str]:
    """The permission/plugin/budget flags every session the driver launches gets -
    stage sessions and the closeout session alike, so one `--plugin-dir` or
    `--setting-sources` covers the whole run rather than the stages only."""
    argv = ["--permission-mode", args.permission_mode]
    if args.allowed_tools:
        argv += ["--allowedTools", *args.allowed_tools]
    for plugin_dir in args.plugin_dir or []:
        argv += ["--plugin-dir", str(plugin_dir)]
    if args.setting_sources:
        argv += ["--setting-sources", args.setting_sources]
    if args.max_budget_usd is not None:
        argv += ["--max-budget-usd", str(args.max_budget_usd)]
    return argv


def weight_argv(model: str, effort: str, source: str) -> tuple[list[str], list[str]]:
    """`--model`/`--effort` for one session, plus warnings for what was missing.
    `source` names where the values came from, so the warning says what to fix."""
    argv: list[str] = []
    warnings: list[str] = []

    if model:
        argv += ["--model", model]
    else:
        warnings.append(f"no `model` {source} - launching on the CLI default")

    if effort:
        resolved = EFFORT_ALIASES.get(effort.lower())
        if resolved:
            argv += ["--effort", resolved]
        else:
            warnings.append(
                f"effort `{effort}` is not one of "
                f"{'/'.join(sorted(set(EFFORT_ALIASES.values())))} - omitting --effort"
            )
    else:
        warnings.append(f"no `effort` {source} - launching on the CLI default")
    return argv, warnings


def build_command(args: argparse.Namespace, row: IndexRow) -> tuple[list[str], list[str]]:
    """The `claude -p` argv for one stage, plus any warnings worth printing."""
    prompt = f"/plan-staged-rollout:plan-run {stage_argument(row.stage_id)} --unattended"
    weight, warnings = weight_argv(row.model, row.effort, "in the stage index")
    return [args.claude_bin, "-p", prompt, *weight, *session_profile(args)], warnings


def build_close_command(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """The `claude -p` argv for the closeout session. Closeout has no stage-index
    row to read a weight from, so it takes `--close-model`/`--close-effort` and
    falls back to the CLI default."""
    prompt = "/plan-staged-rollout:plan-close --unattended"
    weight, warnings = weight_argv(
        args.close_model or "", args.close_effort or "", "for closeout (--close-model/--close-effort)"
    )
    return [args.claude_bin, "-p", prompt, *weight, *session_profile(args)], warnings


def describe(row: IndexRow) -> str:
    weight = ", ".join(
        part
        for part in (
            f"model {row.model}" if row.model else "",
            f"effort {row.effort}" if row.effort else "",
        )
        if part
    )
    name = f" - {row.name}" if row.name else ""
    return f"{row.stage_id}{name} ({weight or 'no launch hints'}, gate {row.gate})"


# --------------------------------------------------------------------------
# Closeout - the one session the driver launches that is not a stage
# --------------------------------------------------------------------------


def open_plan_pr(root: Path, branch: str, base: str) -> str | None:
    """The URL of the open PR from the plan branch, "" when there is none, and
    None when `gh` cannot answer (missing, unauthenticated, offline). The three
    cases are deliberately distinct: "no PR" is a failed closeout, "cannot tell"
    is not."""
    if shutil.which("gh") is None:
        return None
    argv = ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "url"]
    if base:
        argv += ["--base", base]
    result = subprocess.run(argv, cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    urls = re.findall(r'"url"\s*:\s*"([^"]+)"', result.stdout)
    return urls[0] if urls else ""


def close_out(
    args: argparse.Namespace,
    root: Path,
    plan_dir: Path,
    notify_cmd: str,
    branch: str,
    stages_run: int,
) -> int:
    """Launch `/plan-close --unattended` and report where it got to.

    This is the last thing the driver does: under `plan-dir: delete` the plan
    directory this driver has been reading is gone once the session ends, so
    there is nothing left to re-scan and no round after this one.
    """
    argv, warnings = build_close_command(args)
    log("")
    log("every stage is done or skipped - launching closeout")
    for warning in warnings:
        log(f"  warning: {warning}")
    log(f"  $ {' '.join(shell_quote(part) for part in argv)}")

    if args.dry_run:
        log("dry run - closeout is not launched")
        return 0

    result = subprocess.run(argv, cwd=str(root))
    log(f"closeout session exited {result.returncode}")

    base = default_branch(root)
    url = open_plan_pr(root, branch, base)
    if url:
        message = (
            f"plan complete - {stages_run} stage(s) run this pass, closeout done, and "
            f"the plan->main PR is open at {url}. Review and merge it yourself: "
            "merging into the default branch is the one gate no mode takes."
        )
        log(message)
        notify(notify_cmd, "complete", message, "", plan_dir)
        return 0

    if url is None:
        message = (
            f"plan complete - {stages_run} stage(s) run this pass and the closeout "
            "session finished, but `gh` could not be asked whether the plan->main PR "
            "is open. Check the branch yourself before assuming the plan is closed."
        )
        log(message)
        notify(notify_cmd, "complete", message, "", plan_dir)
        return 0

    message = (
        "closeout ran but no open PR from the plan branch was found, so it stopped "
        "at one of its own gates - a stage worktree holding unpushed work is the "
        "usual one. Read the closeout session's output above; under "
        "`plan-dir: delete` the ledger may already be gone from the working tree, "
        "and the plan branch's history is where to look for it."
    )
    log(message)
    notify(notify_cmd, "stop", message, "", plan_dir)
    return 1


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def drive(
    args: argparse.Namespace, root: Path, plan_dir: Path, notify_cmd: str, branch: str
) -> int:
    attempts: dict[str, int] = {}
    simulated: dict[str, str] = {}
    launched: list[str] = []

    plan = load_plan(plan_dir)
    if not plan.ledger:
        fail(f"{plan_dir / 'LEDGER.md'} has no recognizable status table")
        return 2
    if not plan.index:
        fail(f"{plan_dir / 'PLAN.md'} has no recognizable stage index")
        return 2

    log(f"plan flags: merge {plan.merge_flag}, plan-dir {plan.plan_dir_flag}")
    if args.close:
        log(
            "closeout will run unattended when every stage is settled; `.plan/` is "
            + (
                "deleted as its last commit"
                if plan.plan_dir_flag == "delete"
                else "kept"
            )
            + " and the plan->main PR is opened, never merged"
        )
    if plan.merge_flag == "manual":
        log(
            "merge is `manual`, so a stage session stops at its own PR instead of "
            "merging it - no stage reaches `done` unattended, and the driver will "
            "stop at the first one. Set `merge: auto` on the plan flags line to let "
            "sessions merge their own stage PRs."
        )

    # Each round either advances a stage or burns an attempt, so this cap only
    # ever catches a ledger that contradicts itself (a row flipping back to todo).
    max_rounds = len(plan.index) * max(1, args.max_attempts) + len(plan.index) + 2

    for _ in range(max_rounds):
        plan = load_plan(plan_dir)
        statuses = {row.stage_id: row.status for row in plan.ledger}
        statuses.update(simulated)
        # A stage recorded in BLOCKED.md is never retried, even across a driver
        # restart, regardless of what its LEDGER.md row still reads - the whole
        # point of keeping the block out of the ledger is that the row may be
        # stale until a human resolves the stage branch's own unmerged edit.
        for stage_id in read_driver_blocked_ids(plan_dir):
            statuses[stage_id] = "blocked"
        runnable = runnable_set(plan, statuses)

        if not runnable:
            open_stages = [
                stage_id
                for stage_id, status in statuses.items()
                if status not in ("done", "skipped")
            ]
            if not open_stages:
                if args.close:
                    return close_out(
                        args, root, plan_dir, notify_cmd, branch, len(launched)
                    )
                message = (
                    f"plan complete - {len(launched)} stage(s) run this pass; every "
                    "stage is done or skipped. --no-close was passed, so close it "
                    "out yourself with /plan-close."
                )
                log(message)
                notify(notify_cmd, "complete", message, "", plan_dir)
                return 0
            open_list = ", ".join(sorted(open_stages))
            verb = "is" if len(open_stages) == 1 else "are"
            message = (
                f"nothing runnable - {open_list} {verb} blocked or waiting on unmet "
                "dependencies. See .plan/LEDGER.md and .plan/BLOCKED.md."
            )
            log(message)
            notify(notify_cmd, "stop", message, open_list, plan_dir)
            return 1

        if len(runnable) > 1:
            log(
                f"{len(runnable)} stages are runnable "
                f"({', '.join(r.stage_id for r in runnable)}); this driver is "
                "sequential, so it takes them one at a time in stage-index order."
            )

        row = runnable[0]

        if row.gate == "human":
            message = (
                f"stopped in front of {describe(row)} - it is `gate: human`, so it is "
                "never launched with nobody watching. Run it yourself with "
                f"`/plan-staged-rollout:plan-run {stage_argument(row.stage_id)}`, then "
                "start the driver again."
            )
            log(message)
            notify(notify_cmd, "stop", message, row.stage_id, plan_dir)
            return 1

        attempt = attempts.get(row.stage_id, 0) + 1
        attempts[row.stage_id] = attempt
        argv, warnings = build_command(args, row)

        log("")
        log(
            f"launching {describe(row)} - attempt {attempt} of {args.max_attempts}"
            + (f", file {row.file}" if row.file else "")
        )
        for warning in warnings:
            log(f"  warning: {warning}")
        log(f"  $ {' '.join(shell_quote(part) for part in argv)}")

        if args.dry_run:
            launched.append(row.stage_id)
            simulated[row.stage_id] = "done"
            continue

        result = subprocess.run(argv, cwd=str(root))
        launched.append(row.stage_id)

        plan = load_plan(plan_dir)
        after = next((r for r in plan.ledger if r.stage_id == row.stage_id), None)
        status = after.status if after else "missing"
        log(f"{row.stage_id} session exited {result.returncode}; ledger now reads `{status}`")

        if status == "done":
            continue
        if status == "skipped":
            log(f"{row.stage_id} was skipped by its session; carrying on")
            continue

        if status == "blocked":
            message = (
                f"{row.stage_id} came back `blocked` - its session hit something only a "
                "person or an external system can clear. The runbook is in "
                ".plan/LEDGER.md. Not retried."
            )
            log(message)
            notify(notify_cmd, "blocked", message, row.stage_id, plan_dir)
            return 1

        if attempt < args.max_attempts:
            log(f"{row.stage_id} is `{status}` - retrying (resume) once more")
            continue

        message = (
            f"{row.stage_id} did not reach `done` in {attempt} attempt(s) (last status "
            f"`{status}`). Recorded as blocked in .plan/BLOCKED.md with a runbook so "
            "the driver never retries it."
        )
        log(message)
        if after is not None:
            record_driver_block(plan_dir, after, attempt, status, branch)
            if args.commit:
                commit_driver_block(root, plan_dir, row.stage_id)
            else:
                log("--no-commit: the block note is written but left uncommitted")
        notify(notify_cmd, "blocked", message, row.stage_id, plan_dir)
        return 1

    message = (
        "round cap reached without the plan settling - the ledger is contradicting "
        "itself (a row moving backwards?). Stopping rather than looping."
    )
    fail(message)
    notify(notify_cmd, "stop", message, "", plan_dir)
    return 1


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="plan_driver.py",
        description=(
            "Run a staged rollout unattended: one `claude -p` session per runnable "
            "stage, sequentially, until nothing is runnable or a person is needed."
        ),
    )
    parser.add_argument(
        "--plan-dir",
        type=Path,
        help=(
            "path to the .plan/ directory (default: <repo root>/.plan). Intended "
            "for inspecting a plan with --dry-run; a real run drives the repo it "
            "is standing in, so pointing this elsewhere runs stage sessions "
            "against the wrong tree"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "compute and print the stages, their order and their model/effort without "
            "launching claude at all; assumes each stage would reach `done`"
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="attempts per stage before it is marked `blocked` (default: 2)",
    )
    parser.add_argument(
        "--claude-bin",
        default="claude",
        help="the Claude Code binary to launch (default: claude)",
    )
    parser.add_argument(
        "--permission-mode",
        default=DEFAULT_PERMISSION_MODE,
        help=(
            "--permission-mode passed to every session the driver launches "
            f"(default: {DEFAULT_PERMISSION_MODE})"
        ),
    )
    parser.add_argument(
        "--allowed-tools",
        nargs="*",
        default=DEFAULT_ALLOWED_TOOLS,
        help=(
            "--allowedTools passed to every session the driver launches; pass with "
            "no values to "
            "omit the flag entirely (default: " + " ".join(DEFAULT_ALLOWED_TOOLS) + ")"
        ),
    )
    parser.add_argument(
        "--plugin-dir",
        action="append",
        metavar="PATH",
        help=(
            "load a plugin from a directory or .zip in every session the driver "
            "launches "
            "(repeatable), passed straight through to `claude --plugin-dir`. The "
            "reason it exists: a stage session resolves "
            "`/plan-staged-rollout:plan-run` against the *installed* plugin, so "
            "testing an unreleased change to this plugin - or to this driver - "
            "means pointing the stage sessions at the working tree instead"
        ),
    )
    parser.add_argument(
        "--setting-sources",
        metavar="SOURCES",
        help=(
            "comma-separated setting sources for every session the driver launches "
            "(`user`, "
            "`project`, `local`), passed through to `claude --setting-sources`. "
            "Dropping `user` is the only measured way past a `permissions.ask` "
            "entry in your own settings - but it drops your user hooks and user "
            "CLAUDE.md with it, so read the README before reaching for it"
        ),
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help=(
            "optional --max-budget-usd ceiling per session; unattended spend "
            "with nobody watching is the real risk here"
        ),
    )
    parser.add_argument(
        "--no-close",
        dest="close",
        action="store_false",
        help=(
            "stop when every stage is done or skipped instead of launching "
            "`/plan-close --unattended`. Closeout opens the plan->main PR and never "
            "merges it, so the default is to run it"
        ),
    )
    parser.add_argument(
        "--close-model",
        metavar="MODEL",
        help=(
            "--model for the closeout session (default: the CLI default). Closeout "
            "has no stage-index row to read a weight from, so this is the only place "
            "to set one"
        ),
    )
    parser.add_argument(
        "--close-effort",
        metavar="EFFORT",
        help=(
            "--effort for the closeout session, one of "
            + "/".join(sorted(set(EFFORT_ALIASES.values())))
            + " (default: the CLI default)"
        ),
    )
    parser.add_argument(
        "--notify",
        default=None,
        help=f"notify command, overriding ${NOTIFY_ENV}",
    )
    parser.add_argument(
        "--no-commit",
        dest="commit",
        action="store_false",
        help="write the block note in `.plan/BLOCKED.md` but do not commit or push it",
    )
    parser.set_defaults(commit=True, close=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_attempts < 1:
        fail("--max-attempts must be at least 1")
        return 2

    root = repo_root(Path.cwd())
    if root is None:
        fail("not inside a git repository - run the driver from the plan branch clone")
        return 2

    branch = current_branch(root)
    protected = set(PROTECTED_BRANCHES)
    resolved_default = default_branch(root)
    if resolved_default:
        protected.add(resolved_default)
    if branch in protected or branch == "HEAD":
        fail(
            f"refusing to run on `{branch}`. The driver only ever drives a plan branch: "
            "stage branches are cut from the checked-out branch and, under "
            "`merge: auto`, merged back into it. Check out the plan branch "
            "(`plan-<slug>`) first."
        )
        return 2
    if not branch.startswith("plan-"):
        log(
            f"warning: `{branch}` does not look like a plan branch (`plan-<slug>`). "
            "Continuing, but check you are where you meant to be."
        )

    plan_dir = (args.plan_dir if args.plan_dir else root / ".plan").resolve()
    if plan_dir != (root / ".plan").resolve() and not args.dry_run:
        fail(
            f"--plan-dir points at {plan_dir}, which is not this repo's own .plan/. "
            "Stage sessions run in the checked-out repo, so a real run against "
            "another plan would work the wrong tree. Use --dry-run to inspect a "
            "plan from outside it."
        )
        return 2
    for required in ("PLAN.md", "LEDGER.md"):
        if not (plan_dir / required).is_file():
            fail(f"{plan_dir / required} not found - is this the plan branch?")
            return 2

    if not args.dry_run and shutil.which(args.claude_bin) is None:
        fail(f"`{args.claude_bin}` is not on PATH; use --claude-bin or --dry-run")
        return 2

    # A mistyped --plugin-dir is the one failure the driver must not pass on: the
    # stage sessions would silently fall back to the *installed* plugin and the
    # run would look fine while testing the wrong code.
    resolved_plugin_dirs = []
    for raw in args.plugin_dir or []:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            if not (path / ".claude-plugin" / "plugin.json").is_file():
                fail(
                    f"--plugin-dir {path} has no .claude-plugin/plugin.json - "
                    "stage sessions would silently use the installed plugin instead"
                )
                return 2
        elif not (path.is_file() and path.suffix == ".zip"):
            fail(f"--plugin-dir {path} is neither a plugin directory nor a .zip")
            return 2
        resolved_plugin_dirs.append(path)
    args.plugin_dir = resolved_plugin_dirs

    if args.setting_sources is not None:
        valid = {"user", "project", "local"}
        given = [s.strip() for s in args.setting_sources.split(",") if s.strip()]
        unknown = [s for s in given if s not in valid]
        if not given or unknown:
            fail(
                "--setting-sources takes a comma-separated subset of "
                f"user/project/local; got `{args.setting_sources}`"
            )
            return 2
        args.setting_sources = ",".join(given)

    notify_cmd = args.notify if args.notify is not None else os.environ.get(NOTIFY_ENV, "")

    log(f"repo {root}")
    log(f"branch {branch}")
    log(f"plan {plan_dir}")
    for plugin_dir in args.plugin_dir or []:
        log(f"plugin {plugin_dir} (side-loaded into every session launched)")
    if args.setting_sources:
        log(f"setting-sources {args.setting_sources} (for every session launched)")
        if "user" not in args.setting_sources.split(","):
            log(
                "  note: `user` is omitted, so launched sessions run without your "
                "user settings - no user hooks, no user CLAUDE.md, no user "
                "permission rules"
            )
    if args.dry_run:
        log("dry run - nothing is launched and the ledger is not written")
    if not notify_cmd:
        log(f"no ${NOTIFY_ENV} set - stops will only be reported on this stream")

    return drive(args, root, plan_dir, notify_cmd, branch)


if __name__ == "__main__":
    sys.exit(main())
