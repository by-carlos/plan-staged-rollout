#!/usr/bin/env python3
"""Read a Bash tool command the way the shell will run it, for the two
PreToolUse guards (gh-body-guard and tracker-write-guard).

Standard library only; Python 3.11 or later. A guard must judge the commands
that will run, not words that merely appear in the string: a commit message
that mentions `gh issue create -F x` is not a gh call, while
`GH_REPO=o/r gh issue create \\<newline> --body-file b.md` is one. So:

- line continuations (backslash-newline) are folded;
- the string is split into simple commands on ; & && || | newlines and
  ( ) $( ` -- but only outside quotes, so a `|` in a quoted title stays put;
- heredoc bodies are dropped (they are data fed to a command);
- leading `NAME=value` assignments and the wrappers command, exec, env, time,
  nohup and builtin are stripped from each command.

    shell_cmd.py gh-body-guard     # reads the PreToolUse event on stdin
"""

from __future__ import annotations

import json
import re
import shlex
import sys

HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
ASSIGN_RE = re.compile(r"""^[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|"(?:[^"\\]|\\.)*"|\S*)\s+""")
WRAPPER_RE = re.compile(r"^(?:command|exec|env|time|nohup|builtin)\s+")
ISSUES_PATH_RE = re.compile(r"^/?repos/[^/]+/[^/]+/issues/?$")


def _clean(seg: str) -> str:
    seg = seg.strip().lstrip("{!").strip()
    while True:
        m = ASSIGN_RE.match(seg) or WRAPPER_RE.match(seg)
        if not m:
            return seg
        seg = seg[m.end():].lstrip()


def segments(cmd: str) -> list[str]:
    """The simple commands in `cmd`, cleaned, heredoc bodies left out."""
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    out: list[str] = []
    buf: list[str] = []
    pending: list[str] = []  # heredoc terminators whose bodies start at the next newline
    quote = None
    i, n = 0, len(cmd)

    def cut():
        out.append("".join(buf))
        buf.clear()

    while i < n:
        c = cmd[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(cmd[i + 1])
                i += 1
            elif c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(cmd[i:i + 2])
            i += 2
            continue
        if cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            m = HEREDOC_RE.match(cmd, i)
            if m:
                pending.append(m.group(2))
                buf.append(m.group(0))
                i = m.end()
                continue
        if c == "\n":
            cut()
            i += 1
            for term in pending:  # skip each body, up to its terminator line
                while i < n:
                    j = cmd.find("\n", i)
                    line = cmd[i:j if j != -1 else n]
                    i = j + 1 if j != -1 else n
                    if line.strip() == term:
                        break
            pending.clear()
            continue
        if cmd.startswith(("&&", "||", "$("), i):
            cut()
            i += 2
            continue
        if c in ";&|()`":
            cut()
            i += 1
            continue
        buf.append(c)
        i += 1
    cut()
    return [s for s in (_clean(x) for x in out) if s]


def words(seg: str) -> list[str]:
    try:
        return shlex.split(seg)
    except ValueError:  # an unbalanced quote: fall back to plain whitespace
        return seg.split()


# ------------------------------------------------------------ gh judgements

def gh_body_problem(seg: str) -> str | None:
    """Why this command would corrupt a gh issue/pr body, or None.

    --body-file / -F: on native Windows gh reads the file as cp1252, so every
    non-ASCII character is double-encoded. --body/-b "@path": only gh api
    expands @<path>; here it posts the path as the body and exits 0."""
    w = words(seg)
    if len(w) < 3 or w[0] != "gh" or w[1] not in ("issue", "pr") or w[2] not in ("create", "comment", "edit"):
        return None
    for k, tok in enumerate(w[3:], start=3):
        if tok == "--body-file" or tok.startswith(("--body-file=", "-F")):
            return ("gh issue/pr --body-file (and its -F alias) reads the file as cp1252 on native "
                    "Windows, double-encoding every non-ASCII character.")
        nxt = w[k + 1] if k + 1 < len(w) else ""
        if (tok in ("--body", "-b") and nxt.startswith("@")) or tok.startswith(("--body=@", "-b@")):
            return ("gh issue/pr --body never expands @<path> -- only gh api does -- so this would "
                    "post the literal file path as the body text, and gh would exit 0.")
    return None


def is_issue_create(seg: str) -> bool:
    """`gh issue create`, or `gh api` writing to an issues collection."""
    w = words(seg)
    if len(w) >= 3 and w[0] == "gh" and w[1] == "issue" and w[2] == "create":
        return True
    if len(w) < 3 or w[0] != "gh" or w[1] != "api":
        return False
    if not any(ISSUES_PATH_RE.match(tok) for tok in w[2:]):
        return False
    method, fields = None, False
    for k, tok in enumerate(w[2:], start=2):
        if tok in ("-X", "--method") and k + 1 < len(w):
            method = w[k + 1]
        elif tok.startswith("--method="):
            method = tok.split("=", 1)[1]
        elif tok.startswith("-X") and len(tok) > 2:
            method = tok[2:]
        elif tok in ("-f", "-F", "--field", "--raw-field", "--input") or tok.startswith(
                ("-f", "-F", "--field=", "--raw-field=", "--input=")):
            fields = True
    if method:
        return method.upper() == "POST"
    return fields  # gh api switches to POST when it is given fields or input


# -------------------------------------------------------------------- hook

REPLACEMENT = ('Use the plan-staged-rollout GitHub adapter instead: python '
               '"${CLAUDE_PLUGIN_ROOT}/tickets/scripts/github_adapter.py" create|comment|repair ... -- it posts '
               "ASCII-escaped JSON through gh api --input and verifies the body that actually landed.")


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def gh_body_guard() -> int:
    """Deny a corrupting gh body flag; otherwise emit nothing, so the
    harness's own permission rules decide as if no hook ran."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    cmd = str((event.get("tool_input") or {}).get("command") or "")
    for seg in segments(cmd):
        problem = gh_body_problem(seg)
        if problem:
            deny(f"{problem} {REPLACEMENT}")
            break
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["gh-body-guard"]:
        return gh_body_guard()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
