#!/usr/bin/env python3
"""Opt-in guard: a tracker create happens only at the end of create-issue.

Standard library only; Python 3.11 or later. Off unless a
`plan-staged-rollout.toml` (user or project, see template-schema.md) sets

    guard_tracker_creates = true

When it is on, two things hold:

1. **The adapters refuse to build a create** unless the run's work folder
   (the folder holding the draft) shows the pipeline ran: `template.json`
   from `ticket_template.py resolve`, the gap review's `review-filtered.json`
   (or a recorded `review-skipped.json`) and `estimate.json`. The template
   passed to `build` must be the one in `template.json`.
2. **The PreToolUse hook denies a hand-made create.** A Jira create is a
   relayed MCP call, so the hook allows `createJiraIssue` only when its
   arguments match a call spec the Jira adapter issued after `--confirm`
   (one use each, two hours at most). `executeWrite` naming a create, and
   `gh issue create` or a `gh api` POST to an issues endpoint from the Bash
   tool, are denied outright: the GitHub adapter runs `gh` itself, never
   through the Bash tool.

Edits, comments and links are not guarded.

    write_guard.py hook      # reads the PreToolUse event on stdin
    write_guard.py status [--project-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import ticket_template as tmpl

GUARD_KEY = "guard_tracker_creates"
TOKEN_TTL = 2 * 60 * 60
CREATE_TOOLS = ("createJiraIssue",)

MCP_CREATE_RE = re.compile(r"^mcp__.+__(createJiraIssue)$")
MCP_EXECUTE_RE = re.compile(r"^mcp__.+__executeWrite$")
GH_ISSUE_CREATE_RE = re.compile(r"(^|[;&|(\s])gh\s+issue\s+create(\s|$)")
GH_API_RE = re.compile(r"(^|[;&|(\s])gh\s+api\s")
GH_ISSUES_PATH_RE = re.compile(r"repos/[^/\s]+/[^/\s]+/issues/?([\s\"'?]|$)")
GH_WRITE_FLAG_RE = re.compile(r"\s(-X\s*POST|--method[=\s]+POST|--input|-f|-F|--field|--raw-field)([=\s]|$)",
                              re.IGNORECASE)

SKILL_HINT = ("Tracker creates go through the plan-staged-rollout create-issue skill and its adapter "
              f"({GUARD_KEY} is on in plan-staged-rollout.toml). Run the skill's pipeline; if a step "
              "looks unnecessary, ask the user rather than skipping it. Only the user turns the guard off.")


# ------------------------------------------------------------------ config

def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def guard_enabled(project_dir: Path | None = None) -> bool:
    """True when the user or the project config sets the guard. Either file
    can turn it on; neither can turn off what the other turned on. A config
    that cannot be read leaves the guard off (the template loader already
    reports that file as a notice)."""
    candidates = [config_dir() / tmpl.CONFIG_NAME]
    root = tmpl._repo_root(project_dir) if project_dir else None
    if root:
        candidates.append(root / ".claude" / tmpl.CONFIG_NAME)
    for cfg in candidates:
        if not cfg.is_file():
            continue
        try:
            if tmpl._read_toml(cfg).get(GUARD_KEY) is True:
                return True
        except tmpl.TemplateError:
            continue
    return False


# ------------------------------------------------------------ pipeline gate

def pipeline_gate(work: Path, template: dict) -> list[str]:
    """What create-issue must have left in the work folder before a create
    is built. Returns one error per missing step; empty means go."""
    errors: list[str] = []
    resolved = None
    try:
        data = json.loads((work / "template.json").read_text(encoding="utf-8"))
        if isinstance(data, dict) and "template" in data and "source" in data:
            resolved = data["template"]
        else:
            errors.append("template.json: not the output of `ticket_template.py resolve` (step 1)")
    except (OSError, json.JSONDecodeError):
        errors.append(f"template.json: missing from {work}; run `ticket_template.py resolve` (step 1)")
    if resolved is not None and resolved != template:
        errors.append("template: differs from the one in template.json; build with the resolved template")
    if not (work / "review-filtered.json").is_file() and not (work / "review-skipped.json").is_file():
        errors.append("review: no review-filtered.json or review-skipped.json; run the gap review (step 4)")
    if not (work / "estimate.json").is_file():
        errors.append("estimate.json: missing; run `ticket_core.py estimate` (step 5)")
    return [f"pipeline gate ({GUARD_KEY}): {e}" for e in errors]


# ----------------------------------------------------------- relay tokens

def _token_dir() -> Path:
    return config_dir() / "plan-staged-rollout" / "allowed-writes"


def _token_key(tool: str, arguments: dict) -> str:
    bare = tool.rsplit("__", 1)[-1]
    blob = json.dumps({"tool": bare, "arguments": arguments}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def issue_token(spec: dict) -> None:
    """Record that the adapter issued this create call spec, so the hook
    lets exactly that call through once. Written whether or not the guard
    is on, so turning it on mid-run cannot strand a confirmed create."""
    d = _token_dir()
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in d.glob("*.json"):
        try:
            if now - old.stat().st_mtime > TOKEN_TTL:
                old.unlink()
        except OSError:
            pass
    key = _token_key(spec["tool"], spec["arguments"])
    (d / f"{key}.json").write_text(json.dumps({"tool": spec["tool"], "issued": now}), encoding="utf-8")


def consume_token(tool: str, arguments: dict) -> bool:
    path = _token_dir() / f"{_token_key(tool, arguments)}.json"
    try:
        fresh = time.time() - path.stat().st_mtime <= TOKEN_TTL
        path.unlink()
    except OSError:
        return False
    return fresh


# -------------------------------------------------------------------- hook

def decide(event: dict) -> tuple[str, str] | None:
    """Return (allow|deny, reason), or None to stay out of the decision."""
    name = event.get("tool_name") or ""
    tin = event.get("tool_input") or {}
    project = Path(event["cwd"]) if event.get("cwd") else None

    if MCP_CREATE_RE.match(name):
        if not guard_enabled(project):
            return None
        if consume_token(name, tin):
            return "allow", "create matches a call spec the create-issue adapter issued"
        return "deny", ("This createJiraIssue call was not issued by the create-issue Jira adapter "
                        "(or its arguments were changed). " + SKILL_HINT)

    if MCP_EXECUTE_RE.match(name):
        op = str(tin.get("name") or "")
        if op.rsplit("__", 1)[-1] not in CREATE_TOOLS or not guard_enabled(project):
            return None
        return "deny", f"executeWrite {op} is a hand-made create. " + SKILL_HINT

    if name == "Bash":
        cmd = str(tin.get("command") or "")
        hit = GH_ISSUE_CREATE_RE.search(cmd) or (
            GH_API_RE.search(cmd) and GH_ISSUES_PATH_RE.search(cmd) and GH_WRITE_FLAG_RE.search(cmd))
        if not hit or not guard_enabled(project):
            return None
        return "deny", "Creating a GitHub issue from the Bash tool bypasses create-issue. " + SKILL_HINT

    return None


def run_hook() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    try:
        result = decide(event)
    except Exception as exc:  # noqa: BLE001 -- a guarded call that cannot be checked fails closed
        result = "deny", f"write_guard could not check this call ({type(exc).__name__}: {exc}). " + SKILL_HINT
    if result:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": result[0],
                                                 "permissionDecisionReason": result[1]}}))
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True)
    sub.add_parser("hook", help="decide one PreToolUse event read from stdin")
    s = sub.add_parser("status", help="say whether the guard is on here")
    s.add_argument("--project-dir", default=".")
    args = ap.parse_args(argv)
    if args.op == "hook":
        return run_hook()
    print(json.dumps({GUARD_KEY: guard_enabled(Path(args.project_dir).resolve())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
