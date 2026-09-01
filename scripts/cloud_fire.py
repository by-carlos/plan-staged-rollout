#!/usr/bin/env python3
"""Fire one stage of a staged rollout as a Claude Code **cloud** session.

The counterpart to `plan_driver.py`, which launches stages as local `claude -p`
processes. This script launches the same stage on Anthropic's hosted
infrastructure instead, by creating a session against the session-creation API.
It fires exactly one stage and returns: sequencing, retries and closeout stay in
`plan_driver.py`, and choosing which stage to fire stays with the caller.

Why the API rather than `claude --cloud`: the CLI command requires a real TTY -
it errors under `--print`, under a pipe, and under pty emulation - so nothing
scripted can drive it. It also silently drops `--effort` behind a server-side
feature gate, booking the model and nothing else, which is the exact
wrong-weight failure the stage index's `effort` column exists to prevent. The
API accepts both and echoes them back, and this script refuses a fire whose echo
disagrees with what it asked for.

One limit stated plainly, because a booking you cannot check is a booking you
should not trust silently: the **model** is confirmed to take effect - a fired
session reports it from inside the container - while the **effort level** is
not. `CLAUDE_EFFORT`, the variable a container used to report it with, came back
empty from sessions booked at low, medium and high alike (1 Sep 2026). Treat a
booked effort level as requested, not proven; the measurements are in the
reference below.

**Plugins do not load in cloud containers**, so a fired session cannot invoke
`/plan-staged-rollout:plan-run`. It does not need to. `.plan/PLAN.md` carries
the whole operating protocol - including what an unattended session does at
every gate - so the prompt is built on the standalone pointer `PLAN.md` was
designed for: name the stage file, say the session is unattended, and describe
the two things about a cloud container `PLAN.md` cannot know (no plugin, and a
start branch that is not the plan branch). Nothing of the protocol itself is
restated - a copy is what drifts.

The beta request shape lives in exactly one function, `build_payload`, and is
recorded in `../skills/staged-rollout/references/cloud-session-api.md`. When the
endpoint changes, fix it there and **re-measure against the live API** - never
guess at a replacement shape.

Stdlib only, so it runs wherever the plugin does.

Usage:

    python scripts/cloud_fire.py 3                 # fire stage S3
    python scripts/cloud_fire.py f --dry-run       # print the request, send nothing
    python scripts/cloud_fire.py --probe-credentials
    python scripts/cloud_fire.py --seed-token
    python scripts/cloud_fire.py --tail session_...

Exit codes: 0 fired (or dry run / read-back printed), 1 the API refused or the
response did not echo the booking, 2 a usage, guardrail or credential failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plan_driver  # noqa: E402  - sibling module, imported for its PLAN.md parser

API_BASE = "https://api.anthropic.com/v1/sessions"

# The self-renewing OAuth grant this script maintains, seeded once per machine
# with --seed-token. Deliberately the same path other batch tooling on this
# machine uses: every refresh invalidates the previous refresh token, so two
# grant files forked from one login would kill each other's chain at the first
# renewal. One file, shared, is the only arrangement that survives.
# Shape: {"accessToken": ..., "refreshToken": ..., "expiresAt": <epoch ms>,
# "updatedAt": <ISO>}.
TOKEN_PATH_ENV = "PLAN_CLOUD_TOKEN_FILE"
DEFAULT_TOKEN_PATH = Path.home() / ".claude" / ".batch-oauth-token.json"

# OAuth refresh endpoint and public client id, both read out of the installed
# Claude Code binary rather than guessed. The user-agent matters: Cloudflare in
# front of the token endpoint refuses Python's default signature (403, 1010).
#
# The client id is a *public* OAuth client identifier - it ships inside the
# Claude Code binary, travels in every refresh request, and has no paired client
# secret, so it authenticates nothing on its own. Secret scanning cannot tell
# that from its shape, hence the inline allow.
OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"  # gitleaks:allow
OAUTH_USER_AGENT = "claude-cli/2.1.240 (external, cli)"

# Renew when less than this much lifetime remains, so a token that would die
# mid-request is refreshed up front. Measured lifetime is 8h.
REFRESH_MARGIN_MS = 5 * 60 * 1000

# The stage index's `model` cell is a launch hint written for a human and for
# `claude --model`, which takes family aliases. The API takes a full model id,
# so the aliases are resolved here. Anything already shaped like an id is passed
# through untouched - this table is config that ages, not a contract.
MODEL_BY_ALIAS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "fable": "claude-fable-5",
}

# API effort vocabulary. `plan_driver.EFFORT_ALIASES` normalises the stage
# index's cell to the CLI vocabulary first (low/medium/high/xhigh/max); the CLI
# tiers above `high` have no measured API equivalent, so they book `high` and
# the caller is told, rather than being dropped silently.
EFFORT_BY_CLI_VALUE = {"low": "low", "medium": "medium", "high": "high"}
UNVERIFIED_EFFORT = {"xhigh": "high", "max": "high"}

# Gates that mean a stage is never started by a runner. Same rule the local
# driver applies before launching - a cloud container has strictly less access
# than the local machine, so `local` is if anything more disqualifying here.
UNFIREABLE_GATES = {"human", "local"}


def log(message: str) -> None:
    print(f"[cloud-fire] {message}", flush=True)


def die(message: str, code: int = 2) -> None:
    print(f"[cloud-fire] error: {message}", file=sys.stderr, flush=True)
    sys.exit(code)


# --------------------------------------------------------------------------
# Weight - the stage index's launch hints, resolved to what the API takes
# --------------------------------------------------------------------------


def resolve_model(cell: str) -> str | None:
    """The API `model` id for a stage index `model` cell, or None to let the
    platform default stand."""
    value = cell.strip().strip("`").lower()
    if not value:
        return None
    if value in MODEL_BY_ALIAS:
        return MODEL_BY_ALIAS[value]
    # Already an id (`claude-sonnet-5`, a dated snapshot, a future family).
    # Passing it through is right: refusing would make this table a gate on
    # every model released after it was written.
    return value


def resolve_effort(cell: str) -> tuple[str | None, str | None]:
    """(API effort_level, warning) for a stage index `effort` cell."""
    value = cell.strip().strip("`").lower()
    if not value:
        return None, None
    cli_value = plan_driver.EFFORT_ALIASES.get(value)
    if cli_value is None:
        return None, (
            f"effort `{cell}` is not one of "
            f"{'/'.join(sorted(set(plan_driver.EFFORT_ALIASES.values())))} - "
            f"omitting effort_level, the session runs at the platform default"
        )
    if cli_value in EFFORT_BY_CLI_VALUE:
        return EFFORT_BY_CLI_VALUE[cli_value], None
    booked = UNVERIFIED_EFFORT[cli_value]
    return booked, (
        f"effort `{cli_value}` has no measured API equivalent - booking "
        f"`{booked}`; the fired session will report that, not `{cli_value}`"
    )


# --------------------------------------------------------------------------
# Repo & plan context
# --------------------------------------------------------------------------


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def repo_slug(root: Path) -> str | None:
    """`owner/repo` from the origin remote, for both URL forms git uses."""
    url = git(root, "remote", "get-url", "origin")
    if not url:
        return None
    url = url.removesuffix(".git")
    if url.startswith("git@") and ":" in url:
        url = url.split(":", 1)[1]
    elif "://" in url:
        url = url.split("://", 1)[1].split("/", 1)[-1]
    parts = [p for p in url.split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def stage_branch_for(plan_branch: str, stage_id: str) -> str:
    """`plan-<slug>` + `S3` -> `plan-<slug>-s3`; `SF` -> `plan-<slug>-sf`.

    Flat names, because a git ref cannot nest a branch under an existing one -
    the naming `PLAN.md`'s git strategy fixes.
    """
    return f"{plan_branch}-s{plan_driver.stage_argument(stage_id)}"


def find_stage(plan_dir: Path, token: str) -> plan_driver.IndexRow:
    """The stage index row for `3`, `f`, `S3` or `SF`."""
    index, _, _ = plan_driver.parse_plan(plan_dir / "PLAN.md")
    if not index:
        die(f"{plan_dir / 'PLAN.md'} has no readable stage index")
    wanted = token.strip().upper().lstrip("S")
    for row in index:
        if plan_driver.stage_argument(row.stage_id).upper() == wanted:
            return row
    known = ", ".join(row.stage_id for row in index)
    die(f"no stage `{token}` in the stage index - it lists {known}")
    raise AssertionError  # unreachable


def check_dependencies(plan_dir: Path, row: plan_driver.IndexRow) -> None:
    """Refuse a stage whose `depends` are not settled, using the ledger the
    protocol treats as the only state. `--ignore-deps` is the escape, because a
    deliberate out-of-order fire is a legitimate operator choice - an accidental
    one is not."""
    statuses = {
        ledger_row.stage_id: ledger_row.status
        for ledger_row in plan_driver.parse_ledger(plan_dir / "LEDGER.md")
    }
    if plan_driver.deps_satisfied(row.depends, statuses):
        return
    unmet = [
        f"{dep} ({statuses.get(dep, 'not in the ledger')})"
        for dep in row.depends
        if statuses.get(dep) not in ("done", "skipped")
    ]
    die(
        f"{row.stage_id} depends on {', '.join(unmet or row.depends)} - not "
        f"settled. Fire the dependency first, or pass --ignore-deps."
    )


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------


def build_prompt(row: plan_driver.IndexRow, plan_dir_name: str) -> str:
    """The instruction the fired session starts with.

    Deliberately thin. `.plan/PLAN.md` is the single source of truth for the
    operating protocol, including everything an unattended session does at a
    gate, so this prompt points at it rather than restating it - the same
    discipline `commands/plan-run.md` keeps. Restating the protocol here would
    create a second copy to drift.
    """
    stage_file = f"{plan_dir_name}/{row.file}" if row.file else "the stage file"
    return (
        f"Follow the instructions in `{stage_file}`, and the operating protocol "
        f"in `{plan_dir_name}/PLAN.md` that it defers to. Read `PLAN.md` first, "
        f"starting with its Preflight & sync block, before reading any status "
        f"or touching any branch.\n\n"
        f"This session is **unattended**: there is nobody to answer a question. "
        f"Honour `PLAN.md`'s unattended rules exactly - take the declared "
        f"default where the plan flags line gives one, and where it does not, "
        f"record the block with its runbook and stop. Never proceed past a gate "
        f"on a guess.\n\n"
        f"This is a cloud container, so the plan-staged-rollout plugin is not "
        f"loaded and its slash commands do not exist here. Nothing depends on "
        f"them: `PLAN.md` is self-contained. Use the git and GitHub access you "
        f"have, and push only to the branches this session is permitted.\n\n"
        f"One thing about this container will look wrong and is not: **you do "
        f"not start on the plan branch.** The platform checks out a branch of "
        f"its own making, named after the branch you are allowed to push with a "
        f"random suffix. Its *content* is the plan branch, which is why `.plan/` "
        f"is there. Treat it as the ordinary drift `PLAN.md`'s preflight already "
        f"knows how to correct - check the plan branch out in the clone and "
        f"follow the protocol's worktree rules from there - not as evidence "
        f"that something is broken."
    )


# --------------------------------------------------------------------------
# The beta payload - the ONE place the request shape lives
# --------------------------------------------------------------------------


def build_payload(
    *,
    repo: str,
    source_branch: str,
    push_branches: list[str],
    model: str | None,
    effort: str | None,
    title: str,
    prompt: str,
    environment_id: str,
) -> dict:
    """The `POST /v1/sessions` body.

    BETA ENDPOINT - this shape is measured, not documented, and can change
    without notice. The record it was measured against is
    `skills/staged-rollout/references/cloud-session-api.md`. If a request starts
    failing, re-measure against the live API and fix this function; do not guess
    at a replacement shape, and update that record with what you measured.

    Two parts are easy to get wrong and are called out there too: the initial
    prompt is a top-level user-message **event**, not a `session_context` field;
    and `environment_id` is required, though its absence returns a bare
    `invalid_request_error` naming no field.
    """
    context: dict = {
        "sources": [
            {
                "type": "git_repository",
                "url": f"https://github.com/{repo}",
                # Where the container starts. For a staged rollout this is the
                # plan branch - `.plan/` exists nowhere else.
                "revision": source_branch,
            }
        ],
        "outcomes": [
            {
                "type": "git_repository",
                "git_info": {
                    "type": "github",
                    "repo": repo,
                    # The only branches the session may push.
                    "branches": push_branches,
                },
            }
        ],
    }
    if model is not None:
        context["model"] = model
    if effort is not None:
        context["effort_level"] = effort
    return {
        "title": title,
        "events": [
            {
                "type": "event",
                "data": {
                    "uuid": str(uuid.uuid4()),
                    "session_id": str(uuid.uuid4()),
                    "type": "user",
                    "parent_tool_use_id": None,
                    "message": {"role": "user", "content": prompt},
                },
            }
        ],
        "session_context": context,
        "environment_id": environment_id,
    }


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


def token_path() -> Path:
    override = os.environ.get(TOKEN_PATH_ENV)
    return Path(override) if override else DEFAULT_TOKEN_PATH


def stamp(epoch_ms: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(epoch_ms / 1000))


def load_credentials() -> tuple[str, str]:
    """Bearer token and organization UUID. First hit wins:

    1. `CLAUDE_CODE_OAUTH_TOKEN` - the CLI's own override, honoured so CI or a
       one-off shell can inject a credential.
    2. The grant file (see TOKEN_PATH_ENV), **renewed by this script** when the
       stored access token is lapsed or nearly so. This is the source an
       unattended run is meant to use. A file that exists but cannot be parsed
       or renewed is an error, not a fall-through: skipping past a broken grant
       to a probably-stale CLI file would defeat the reason it exists.
    3. `~/.claude/.credentials.json` - the CLI's own short-lived token. Last
       resort: on a machine where sessions are desktop-hosted the host refreshes
       OAuth in memory and nothing maintains this file, so finding it lapsed is
       routine rather than a fault.

    A `claude setup-token` credential (`sk-ant-oat01-...`) does **not** work
    here: it is accepted by inference endpoints but lacks the
    `user:sessions:claude_code` scope and is refused with `401`.
    """
    env_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if env_token:
        log("token source: CLAUDE_CODE_OAUTH_TOKEN")
        token = env_token
    elif token_path().is_file():
        log(f"token source: {token_path()}")
        token = _grant_token()
    else:
        log("token source: ~/.claude/.credentials.json (cannot renew itself)")
        token = _cli_file_token()
    try:
        config = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        org = config["oauthAccount"]["organizationUuid"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        die(f"cannot read the organization UUID from ~/.claude.json ({exc})")
    return token, org


def _grant_token() -> str:
    """The grant file's access token, refreshed and persisted when stale.

    Rotation caveat: every refresh invalidates the previous refresh token, so
    the pair in the file is the only live copy of the chain. The rotated pair is
    written back before the new access token is used, and concurrent
    invocations must not race a refresh - the margin makes that a once-per-8h
    event. The refresh window itself renews on use (~26 days), so a chain used
    at least that often stays alive; one left idle past it dies and needs
    re-seeding.
    """
    path = token_path()
    try:
        stored = json.loads(path.read_text(encoding="utf-8-sig"))
        access = stored["accessToken"]
        refresh = stored["refreshToken"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        die(
            f"the grant file {path} exists but is unreadable ({exc}) - re-seed "
            f"it with `python scripts/cloud_fire.py --seed-token`"
        )

    expires_at = stored.get("expiresAt")
    if (
        isinstance(expires_at, (int, float))
        and time.time() * 1000 < expires_at - REFRESH_MARGIN_MS
    ):
        return access

    request = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=json.dumps(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": OAUTH_CLIENT_ID,
            }
        ).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": OAUTH_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            grant = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        die(
            f"refreshing the grant was refused ({exc.code}): "
            f"{exc.read().decode('utf-8', errors='replace')[:300]} - if the "
            f"chain has died (idle past its refresh window, or revoked), log in "
            f"interactively and re-seed with --seed-token"
        )
    except urllib.error.URLError as exc:
        die(f"transport failure refreshing the grant: {exc}")

    renewed = {
        "accessToken": grant["access_token"],
        "refreshToken": grant.get("refresh_token", refresh),
        "expiresAt": int(time.time() * 1000) + grant.get("expires_in", 0) * 1000,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _write_grant(renewed)
    log(f"grant refreshed, good until {stamp(renewed['expiresAt'])}")
    return renewed["accessToken"]


def _write_grant(payload: dict) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)


def _cli_file_token() -> str:
    try:
        creds = json.loads(
            (Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8")
        )
        oauth = creds["claudeAiOauth"]
        token = oauth["accessToken"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        die(f"cannot read a bearer token from ~/.claude/.credentials.json ({exc})")

    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)):
        lapsed_ms = time.time() * 1000 - expires_at
        if lapsed_ms > 0:
            die(
                f"the Claude Code access token lapsed {lapsed_ms / 3600000:.1f}h "
                f"ago (~/.claude/.credentials.json, expiresAt "
                f"{stamp(expires_at)}), and no grant is seeded on this machine. "
                f"Nothing is wrong with the request - set up the self-renewing "
                f"credential instead of re-authenticating: log in "
                f"interactively once, then run "
                f"`python scripts/cloud_fire.py --seed-token`."
            )
    return token


def seed_token() -> None:
    """Fork the CLI file's current token pair into the grant file (one-time).

    Copies, never edits: `~/.claude/.credentials.json` is left untouched. The
    first refresh rotates the copied pair, and from then on the grant is
    independent of anything the CLI or desktop app does. Needs the CLI file's
    refresh token to still be live, so run it soon after an interactive login.
    """
    try:
        oauth = json.loads(
            (Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8")
        )["claudeAiOauth"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        die(
            f"cannot seed from ~/.claude/.credentials.json ({exc}) - log in "
            f"interactively first, then re-run --seed-token"
        )
    _write_grant(
        {
            "accessToken": oauth["accessToken"],
            "refreshToken": oauth["refreshToken"],
            "expiresAt": oauth.get("expiresAt", 0),
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )
    log(f"grant seeded at {token_path()} - verify with --probe-credentials")


def api_headers(token: str, org: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "ccr-byoc-2025-07-29",
        "anthropic-client-platform": "claude_code_cli",
        "x-organization-uuid": org,
        "content-type": "application/json",
    }


def api_get(url: str) -> dict:
    token, org = load_credentials()
    request = urllib.request.Request(url, headers=api_headers(token, org))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        die(
            f"the API refused {url} ({exc.code}): "
            f"{exc.read().decode('utf-8', errors='replace')[:300]}",
            code=1,
        )
    except urllib.error.URLError as exc:
        die(f"transport failure reading {url}: {exc}", code=1)
    raise AssertionError  # unreachable


def probe_credentials() -> None:
    """Verify the resolved credential with one cheap authenticated read. Exit 0
    means the credential the next fire would use is accepted right now."""
    api_get(f"{API_BASE}?limit=1")
    log("credential accepted by GET /v1/sessions")


def discover_environment() -> str:
    """The environment the account's most recent session ran in.

    Environments are account-level, not per-repo, so the discovered value is
    reusable for a repo that has never had a session.
    """
    for session in api_get(f"{API_BASE}?limit=1").get("data") or []:
        if session.get("environment_id"):
            return session["environment_id"]
    die(
        "no environment found on any existing session - pass --environment-id. "
        "One can be captured from a `claude --cloud` launch run with "
        "--debug-file, which logs the payload it sends.",
        code=1,
    )
    raise AssertionError  # unreachable


# --------------------------------------------------------------------------
# Read-back - the only honest way to confirm what was booked took effect
# --------------------------------------------------------------------------


def tail_session(session_id: str, limit: int) -> None:
    """Print a fired session's stored context and the tail of its transcript.

    The create response echoes what the server *stored*; this reads what the
    session is actually doing. Confirming a booked effort level means finding
    `CLAUDE_EFFORT` reported from inside the container here - inferring it from
    the request that was sent proves nothing.
    """
    record = api_get(f"{API_BASE}/{session_id}")
    context = record.get("session_context") or {}
    log(
        f"{record.get('id')} status={record.get('session_status')} "
        f"model={context.get('model')} effort_level={context.get('effort_level')}"
    )
    events = api_get(f"{API_BASE}/{session_id}/events").get("data") or []
    log(f"{len(events)} event(s); showing the last {min(limit, len(events))}")
    for event in events[-limit:]:
        print(json.dumps(event, indent=2)[:4000])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fire one stage of a staged rollout as a Claude Code cloud session."
        )
    )
    parser.add_argument(
        "stage",
        nargs="?",
        help="stage to fire: a number, `f` for the review stage, or `S3`/`SF`",
    )
    parser.add_argument(
        "--plan-dir",
        type=Path,
        default=Path(".plan"),
        help="the plan folder (default: .plan)",
    )
    parser.add_argument(
        "--repo", help="owner/repo (default: read from the origin remote)"
    )
    parser.add_argument(
        "--plan-branch",
        help=(
            "the branch the container checks out, and where `.plan/` lives "
            "(default: the current branch)"
        ),
    )
    parser.add_argument(
        "--push-branch",
        action="append",
        help=(
            "a branch the fired session may push (repeatable). Default: the "
            "stage branch and the plan branch - the plan branch because a "
            "session that blocks before its stage branch exists commits the "
            "block record there"
        ),
    )
    parser.add_argument("--title", help="session title; defaults to the stage")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="use this file's contents as the prompt instead of the built one",
    )
    parser.add_argument(
        "--environment-id",
        help=(
            "cloud environment id (env_...), required by the endpoint. Omit to "
            "reuse the one the account's most recent session ran in"
        ),
    )
    parser.add_argument(
        "--ignore-deps",
        action="store_true",
        help="fire even though the stage's `depends` are not settled",
    )
    parser.add_argument(
        "--ignore-gate",
        action="store_true",
        help=(
            "fire a `gate: human` or `gate: local` stage anyway. Almost always "
            "wrong: a cloud container has less access than the local machine"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the request (token redacted) and send nothing",
    )
    parser.add_argument(
        "--probe-credentials",
        action="store_true",
        help="resolve and verify the credential a fire would use, then exit",
    )
    parser.add_argument(
        "--seed-token",
        action="store_true",
        help="fork the CLI's token pair into the self-renewing grant file",
    )
    parser.add_argument(
        "--tail", metavar="SESSION_ID", help="read a fired session back and exit"
    )
    parser.add_argument(
        "--tail-limit",
        type=int,
        default=5,
        help="how many trailing events --tail prints (default: 5)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.seed_token:
        seed_token()
        return 0
    if args.probe_credentials:
        probe_credentials()
        return 0
    if args.tail:
        tail_session(args.tail, args.tail_limit)
        return 0
    if not args.stage:
        die("no stage given - `cloud_fire.py <stage>`, or see --help")

    plan_dir = args.plan_dir.resolve()
    if not (plan_dir / "PLAN.md").is_file():
        die(
            f"{plan_dir / 'PLAN.md'} not found - run this from the plan branch "
            f"clone, where `.plan/` lives, or pass --plan-dir"
        )
    root = plan_driver.repo_root(plan_dir) or plan_dir.parent

    repo = args.repo or repo_slug(root)
    if not repo:
        die("cannot read owner/repo from the origin remote - pass --repo")

    plan_branch = args.plan_branch or plan_driver.current_branch(root)
    if not plan_branch:
        die("cannot read the current branch - pass --plan-branch")
    if plan_branch.lower() in plan_driver.PROTECTED_BRANCHES:
        die(
            f"`{plan_branch}` is a protected branch, not a plan branch. A stage "
            f"fired from it would branch off it and, under `merge: auto`, merge "
            f"back into it. Check out the plan branch first."
        )

    row = find_stage(plan_dir, args.stage)
    if row.gate in UNFIREABLE_GATES and not args.ignore_gate:
        reason = (
            "needs a person present"
            if row.gate == "human"
            else "needs a resource only the local machine has"
        )
        die(
            f"{row.stage_id} is `gate: {row.gate}` - it {reason}, so a cloud "
            f"session is the wrong place for it. Run it locally, or pass "
            f"--ignore-gate if you are certain."
        )
    if not args.ignore_deps:
        check_dependencies(plan_dir, row)

    model = resolve_model(row.model)
    effort, effort_warning = resolve_effort(row.effort)
    if model is None:
        log(f"warning: {row.stage_id} has no `model` in the stage index - "
            f"the session runs at the platform default")
    if effort_warning:
        log(f"warning: {effort_warning}")

    stage_branch = stage_branch_for(plan_branch, row.stage_id)
    push_branches = args.push_branch or [stage_branch, plan_branch]
    prompt = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file
        else build_prompt(row, plan_dir.name)
    )
    title = args.title or f"{plan_branch}: {row.stage_id} {row.name}".strip()

    environment_id = args.environment_id or (
        "<discovered from GET /v1/sessions at fire time>"
        if args.dry_run
        else discover_environment()
    )

    payload = build_payload(
        repo=repo,
        source_branch=plan_branch,
        push_branches=push_branches,
        model=model,
        effort=effort,
        title=title,
        prompt=prompt,
        environment_id=environment_id,
    )

    log(
        f"firing {row.stage_id}"
        f"{' - ' + row.name if row.name else ''} on {repo} "
        f"(model {model or 'default'}, effort {effort or 'default'}, "
        f"gate {row.gate})"
    )
    log(f"  start branch: {plan_branch}")
    log(f"  may push:     {', '.join(push_branches)}")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "url": API_BASE,
                    "authorization": "Bearer <redacted>",
                    "body": payload,
                },
                indent=2,
            )
        )
        return 0

    token, org = load_credentials()
    request = urllib.request.Request(
        API_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers=api_headers(token, org),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            record = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        hint = (
            " - the credential was refused; check it with --probe-credentials"
            if exc.code == 401
            else ""
        )
        die(f"the API refused the fire ({exc.code}): {detail}{hint}", code=1)
    except urllib.error.URLError as exc:
        die(f"transport failure firing the session: {exc}", code=1)

    # The server echoes what it stored. A booking that came back different is a
    # silent wrong-weight run - exactly what this mechanism exists to prevent -
    # so it fails the fire loudly rather than reporting success.
    stored = record.get("session_context") or {}
    if (model is not None and stored.get("model") != model) or (
        effort is not None and stored.get("effort_level") != effort
    ):
        print(json.dumps(record, indent=2))
        die(
            f"the response did not echo the booking (asked "
            f"{model}/{effort}, stored {stored.get('model')}/"
            f"{stored.get('effort_level')})",
            code=1,
        )

    log(
        f"created {record.get('id')} status={record.get('session_status')} "
        f"model={stored.get('model')} effort_level={stored.get('effort_level')}"
    )
    log(f"read it back with: --tail {record.get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
