#!/usr/bin/env python3
"""work-issue's deterministic half.

The model reads the ticket and does the work. This script settles the parts
that must not drift between runs:

  assess         a fetched Ticket (an adapter's `fetch` output) plus the
                 resolved template -> act | guide | ask, with the target
                 repo and base branch and the template's [work] rules
  branch         the branch name, from the template's [work].branch pattern
  merge-ask      the merge ask's AskUserQuestion payload, which always opens
                 on a short plain-language change description
  merge-command  the template's merge command, released only with --confirm
  status         a `github_adapter.py set-fields` payload for a [work].status
                 flip on a GitHub board
  weight-check   the ticket's model/effort tier against this session's model
                 and effort -> match | mismatch | ask, with the one-line stop
  unblocked      after a merge: the tickets it blocked whose blockers are all
                 done now, each with its tier and the command to work it

It never calls a tracker or git itself, and it never runs the merge: the
model runs the printed command as its own visible tool call, so a permission
rule or hook that matches `gh pr merge` still sees it.

Exit codes follow the adapter contract: 0 ok, 1 invalid input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ticket_core as core

EXIT_OK, EXIT_INVALID = 0, 1

WORK_DEFAULTS = {
    "branch": "{type}/{number}-{slug}",
    "commit_style": "conventional",
    "merge_command": "gh pr merge {pr} --squash --delete-branch",
    "merge_ask_header": "Merge?",
    "status": {},
    "attribution": {"commit_trailer": "", "pr_footer": ""},
}
BRANCH_TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "build", "ci")
CLOSED_STATES = {"closed", "done", "resolved", "cancelled", "canceled", "won't do"}
STOPWORDS = {"a", "an", "the", "to", "of", "for", "and", "or", "in", "on", "with", "when",
             "from", "into", "by", "at", "is", "be", "it", "its", "that", "this"}
MAX_DESCRIPTION_WORDS = 60
MAX_HEADER_CHARS = 12  # AskUserQuestion's chip limit

REPO_RE = r"(?<![\w.-])([A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*?)(?:\.git)?(?![\w/-])"
LABELLED_REPO = re.compile(
    r"^\W*(?:target\s+)?(?:repo|repository)\W*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
INLINE_REPO = re.compile(
    r"\b(?:repo|repository)\s+`([^`\s]+/[^`\s]+)`|`([^`\s]+/[^`\s]+)`\s+(?:repo|repository)\b",
    re.IGNORECASE)
GITHUB_URL = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?=[/\s)`'\"]|$)")
LABELLED_BASE = re.compile(
    r"^\W*(?:base(?:\s+branch)?|target\s+branch)\W*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
INLINE_BASE = re.compile(r"\bbase\s+branch\s+(?:is\s+)?`([^`\s]+)`", re.IGNORECASE)
EFFORT_LINE = re.compile(r"proposed\s+model\s*/\s*effort\W*(.*)$", re.IGNORECASE)
TIER_RE = re.compile(
    r"\b(opus|sonnet|haiku|fable)\b(?:[\s/_-]*(low|medium|med|high|extra|xhigh|max|ultracode)\b)?",
    re.IGNORECASE)
EFFORT_ONLY_RE = re.compile(r"^\W*(low|medium|med|high|extra|xhigh|max|ultracode)\b", re.IGNORECASE)
# plan-staged-rollout's "Model weight tiers" rubric: Opus-class (Opus, and a
# frontier family at or above it), Sonnet-class, Haiku-class.
MODEL_RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 3}
MODEL_NAMES = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus", "fable": "Fable"}
# `ultracode` has no CLAUDE_EFFORT level, so it is asked about, never guessed.
EFFORT_LEVELS = {"low": "low", "med": "medium", "medium": "medium", "high": "high",
                 "extra": "xhigh", "xhigh": "xhigh", "max": "max"}
VERIFY_RE = re.compile(r"\b(verif\w*|test\w*|acceptance|check\w*|confirm\w*|reproduc\w*)\b", re.IGNORECASE)


class Invalid(Exception):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def work_rules(template: dict) -> dict:
    rules = {k: (dict(v) if isinstance(v, dict) else v) for k, v in WORK_DEFAULTS.items()}
    for key, value in (template.get("work") or {}).items():
        rules[key] = value
    return rules


def unquote(text: str) -> str:
    """The AI prompt is often a block quote; parse it without the markers."""
    return "\n".join(re.sub(r"^\s*>\s?", "", line) for line in (text or "").split("\n"))


def find_section(sections: dict, titles: list[str]) -> tuple[str | None, str | None]:
    lowered = {k.lower(): k for k in sections}
    for title in titles:
        key = lowered.get(title.lower())
        if key is not None:
            return key, sections[key]
    return None, None


def repo_in(value: str) -> str | None:
    m = GITHUB_URL.search(value)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.search(REPO_RE, value.replace("`", " "))
    return m.group(1) if m else None


def repo_candidates(prompt: str) -> list[str]:
    """Repos the prompt names: a labelled line wins outright; otherwise every
    inline mention ("repo `o/n`", "`o/n` repository") and repo URL."""
    labelled = [r for r in (repo_in(m.group(1)) for m in LABELLED_REPO.finditer(prompt)) if r]
    if labelled:
        return dedupe(labelled)
    found = [a or b for a, b in INLINE_REPO.findall(prompt)]
    found += [f"{o}/{n}" for o, n in GITHUB_URL.findall(prompt)]
    return dedupe(found)


def base_candidates(prompt: str) -> list[str]:
    """Base branches the prompt names, only where it says so: a labelled line
    ("Base branch: develop") or "base branch `develop`". A branch mentioned in
    passing ("work on `feat/x` off `main`") is not read as the base."""
    found = []
    for m in LABELLED_BASE.finditer(prompt):
        token = re.sub(r"[`*]", " ", m.group(1)).split()
        if token:
            found.append(token[0].strip(".,;:"))
    found += INLINE_BASE.findall(prompt)
    return dedupe(found)


def dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item.lower() not in {x.lower() for x in out}:
            out.append(item)
    return out


def prompt_tier(prompt: str | None) -> str | None:
    """The tier on the AI prompt's opening `Proposed model/effort:` line, as
    written ("sonnet-med"). Plain, block-quoted, bold or inside a code fence;
    only the first line of content counts, as create-issue writes it there."""
    for line in unquote(prompt or "").splitlines():
        text = re.sub(r"[`*_]", "", line).strip()
        if not text or text.startswith("~~~"):
            continue
        m = EFFORT_LINE.search(text)
        if not m:
            return None
        value = m.group(1).strip()
        m = TIER_RE.search(value) or EFFORT_ONLY_RE.search(value)
        return m.group(0).strip() if m else (value.split(",")[0].strip() or None)
    return None


def ai_prompt_of(ticket: dict, template: dict) -> tuple[str | None, str | None]:
    """(section title, text) of the ticket's AI prompt, or (None, None)."""
    sections = ticket.get("sections") or {}
    tsections = (template.get("body") or {}).get("sections") or []
    ai_titles = [s["title"] for s in tsections if s.get("kind") == "ai_prompt"] + ["AI prompt"]
    ai_title, ai_text = find_section(sections, ai_titles)
    if not (ai_text or "").strip() and ticket.get("ai_prompt"):
        ai_text = ticket["ai_prompt"]
    ai_text = (ai_text or "").strip() or None
    return (ai_title if ai_text else None), ai_text


def effort_hint(ticket: dict, template: dict, prompt: str | None = None) -> tuple[str | None, str | None]:
    """(tier, where it came from): a board field mapped to `effort` (GitHub,
    fetched with --with-board), a `fields.effort` value, or, failing both, the
    AI prompt's opening `Proposed model/effort:` line."""
    mapping = (template.get("routing") or {}).get("board_fields") or {}
    board = ticket.get("board") or {}
    for name, source in mapping.items():
        if source == "effort" and board.get(name):
            return board[name], "the board's Effort field"
    value = (ticket.get("fields") or {}).get("effort")
    if value:
        return value, "the ticket's effort field"
    tier = prompt_tier(prompt)
    return (tier, "the AI prompt's Proposed model/effort line") if tier else (None, None)


def parse_tier(text: str | None) -> dict:
    """A written tier ("sonnet-med", "Opus / high", "high") -> model family
    and effort level. `ok` is false when something was written that matches
    no known tier: that is asked about, never guessed."""
    raw = (text or "").strip()
    out = {"raw": raw, "model": None, "effort": None, "effort_word": None, "ok": bool(raw)}
    m = TIER_RE.search(raw)
    word = None
    if m:
        out["model"] = m.group(1).lower()
        word = (m.group(2) or "").lower() or None
    else:
        e = EFFORT_ONLY_RE.search(raw)
        word = e.group(1).lower() if e else None
        out["ok"] = out["ok"] and bool(e)
    out["effort_word"] = word
    if word:
        out["effort"] = EFFORT_LEVELS.get(word)
        if out["effort"] is None:
            out["ok"] = False
    return out


def session_model(model_id: str | None) -> str | None:
    """Model family of the running session, from its model ID or name."""
    low = (model_id or "").lower()
    found = [fam for fam in MODEL_RANK if fam in low]
    return found[0] if len(found) == 1 else None


def weight_check(tier_text: str | None, model_id: str | None, effort: str | None) -> dict:
    """Compare a ticket's tier with this session, as plan-staged-rollout's
    `stage-run` does for a stage: a lighter model, or an effort that differs in
    either direction, is a mismatch; a heavier model alone is not; an effort
    that cannot be read is said and never a mismatch; a model that matches no
    tier is asked about, never guessed. `go` re-runs the check, never overrides."""
    tier = parse_tier(tier_text)
    out = {"ticket": {"tier": tier["raw"], "model": tier["model"], "effort": tier["effort"]},
           "session": {"model_id": model_id or None, "model": session_model(model_id),
                       "effort": None}}
    if not tier["raw"]:
        out.update(status="match", line="The ticket names no model/effort tier, so there is nothing to check.")
        return out
    read = (effort or "").strip().lower()
    session_effort = EFFORT_LEVELS.get(read) if read else None
    out["session"]["effort"] = session_effort
    if not tier["ok"] or (tier["model"] is None and tier["effort"] is None):
        out.update(status="ask", line=(
            f"The ticket's tier {tier['raw']!r} matches no known model or effort. "
            f"This session is on {model_id or 'an unknown model'}. Ask which tier applies; do not guess."))
        return out
    if tier["model"] and out["session"]["model"] is None:
        out.update(status="ask", line=(
            f"This session's model {model_id or '(unreadable)'!r} matches no known tier "
            f"(Opus-class, Sonnet-class, Haiku-class). The ticket needs {MODEL_NAMES[tier['model']]}. "
            "Ask which tier the session is; do not guess."))
        return out

    lighter = bool(tier["model"]) and MODEL_RANK[out["session"]["model"]] < MODEL_RANK[tier["model"]]
    differs = bool(tier["effort"]) and session_effort is not None and session_effort != tier["effort"]
    notes = []
    if tier["effort"] and not read:
        notes.append("this session's effort could not be read, so it was not compared")
    elif tier["effort"] and session_effort is None:
        notes.append(f"this session's effort {read!r} is not a known level, so it was not compared")
    if lighter or differs:
        have = " / ".join(x for x in (MODEL_NAMES.get(out["session"]["model"]), session_effort or "effort unread") if x)
        need = " / ".join(x for x in (MODEL_NAMES.get(tier["model"]), tier["effort"]) if x)
        out.update(status="mismatch", line=(
            f"This session is on {have}; this ticket needs {need}. Switch the model and effort in "
            "this session's model menu, then type **go** (or just **.**)."))
    else:
        out.update(status="match", line="The session matches the ticket's tier.")
    if notes:
        out["line"] += " Note: " + "; ".join(notes) + "."
    return out


def is_blocks(link: dict) -> bool:
    """A blocking link: GitHub's `kind`, or the Jira link type named Blocks."""
    return (link.get("kind") or link.get("name") or "").lower() == "blocks"


def unblocked(merged: dict, others: list[dict], template: dict) -> dict:
    """After `merged` landed: the tickets it blocks whose every other blocker
    is done. `others` holds each blocked ticket and each of their other
    blockers, fetched the same way as `merged`. A blocker that was not
    fetched cannot be confirmed done, so its ticket is listed as unchecked,
    never offered."""
    mkey = str(merged.get("key"))
    by_key = {str(t.get("key")): t for t in others}
    blocked = [str(link["target"]) for link in merged.get("links") or []
               if is_blocks(link) and link.get("direction") == "outward"]
    result = {"merged": mkey, "unblocked": [], "still_blocked": [], "unchecked": [], "already_closed": []}
    for key in dict.fromkeys(blocked):
        cand = by_key.get(key)
        if cand is None:
            result["unchecked"].append({"key": key, "reason": "the ticket was not fetched"})
            continue
        if str(cand.get("state") or "").lower() in CLOSED_STATES:
            result["already_closed"].append({"key": key, "title": cand.get("title")})
            continue
        waiting, missing = [], []
        for link in cand.get("links") or []:
            if not (is_blocks(link) and link.get("direction") == "inward"):
                continue
            bkey = str(link["target"])
            if bkey == mkey:
                continue
            blocker = by_key.get(bkey)
            if blocker is None:
                missing.append(bkey)
            elif str(blocker.get("state") or "").lower() not in CLOSED_STATES:
                waiting.append(bkey)
        title = {"key": key, "title": cand.get("title"), "url": cand.get("url")}
        if missing:
            result["unchecked"].append({**title, "reason": f"blocker {', '.join(missing)} was not fetched"})
        elif waiting:
            result["still_blocked"].append({**title, "waiting_on": waiting})
        else:
            _, prompt = ai_prompt_of(cand, template)
            tier, source = effort_hint(cand, template, prompt)
            result["unblocked"].append({
                **title, "mode": "act" if prompt else "guide", "tier": tier, "tier_source": source,
                "command": f"/tickets:work-issue {key}"})
    return result


# --------------------------------------------------------------------------
# ops
# --------------------------------------------------------------------------

def assess(ticket: dict, template: dict, *, base: str | None = None, repo: str | None = None) -> dict:
    tracker = ticket.get("tracker")
    if tracker not in ("github", "jira"):
        raise Invalid("ticket has no tracker; pass an adapter's `fetch` output")
    sections = ticket.get("sections") or {}
    tsections = (template.get("body") or {}).get("sections") or []

    plain_titles = [s["title"] for s in tsections if s.get("no_identifiers")] + ["In plain terms"]
    _, plain = find_section(sections, plain_titles)

    ai_title, ai_text = ai_prompt_of(ticket, template)
    effort, effort_source = effort_hint(ticket, template, ai_text)

    state = str(ticket.get("state") or "")
    out = {
        "tracker": tracker,
        "key": ticket.get("key"),
        "title": ticket.get("title"),
        "url": ticket.get("url"),
        "state": state,
        "closed": state.lower() in CLOSED_STATES,
        "plain_terms": (plain or "").strip() or None,
        "ai_prompt_section": ai_title if ai_text else None,
        "ai_prompt": ai_text,
        "effort": effort,
        "effort_source": effort_source,
        "target": {"repo": None, "repo_source": None, "base_branch": None, "base_source": None},
        "candidates": {"repo": [], "base_branch": []},
        "needs_user": [],
        "warnings": [],
        "work": work_rules(template),
    }
    if not ai_text:
        out["mode"] = "guide"
        out["reason"] = "the ticket has no AI prompt, so the work is guided, not done"
        return out

    prompt = unquote(ai_text)
    repos, bases = repo_candidates(prompt), base_candidates(prompt)
    out["candidates"] = {"repo": repos, "base_branch": bases}
    target = out["target"]

    if tracker == "github":
        own = (ticket.get("target") or {}).get("repo")
        target.update(repo=own, repo_source="the issue's own repo")
        others = [r for r in repos if own and r.lower() != own.lower()]
        if repo:
            target.update(repo=repo, repo_source="given by the user")
        elif others:
            out["needs_user"].append("repo")
            out["warnings"].append(
                f"the AI prompt names {', '.join(others)}, not the issue's own repo {own}")
    else:
        if repo:
            target.update(repo=repo, repo_source="given by the user")
        elif len(repos) == 1:
            target.update(repo=repos[0], repo_source="the AI prompt")
        else:
            out["needs_user"].append("repo")
            if repos:
                out["warnings"].append(f"the AI prompt names more than one repo: {', '.join(repos)}")

    if base:
        target.update(base_branch=base, base_source="given by the user")
    elif len(bases) == 1:
        target.update(base_branch=bases[0], base_source="the AI prompt")
    elif len(bases) > 1:
        out["needs_user"].append("base_branch")
        out["warnings"].append(f"the AI prompt names more than one base branch: {', '.join(bases)}")
    elif tracker == "jira":
        out["needs_user"].append("base_branch")
    else:
        target["base_source"] = "the repo's default branch"

    requires = ((template.get("body") or {}).get("ai_prompt") or {}).get("requires") or []
    if "verification" in requires and not VERIFY_RE.search(prompt):
        out["warnings"].append("the AI prompt names no way to verify the change")

    if out["needs_user"]:
        out["mode"] = "ask"
        missing = " and ".join("repository" if n == "repo" else "base branch" for n in out["needs_user"])
        out["reason"] = f"the AI prompt does not settle the {missing}; ask before branching"
    else:
        out["mode"] = "act"
        out["reason"] = "the ticket has an AI prompt and its target is settled"
    return out


def slugify(title: str, max_words: int = 5) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", title or "")
    words = [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w]
    kept = [w for w in words if w not in STOPWORDS] or words
    return "-".join(kept[:max_words])


def branch_name(template: dict, kind: str, number: str, title: str, slug: str | None = None) -> str:
    if kind not in BRANCH_TYPES:
        raise Invalid(f"branch type {kind!r} is not one of {', '.join(BRANCH_TYPES)}")
    slug = slug or slugify(title)
    if not slug:
        raise Invalid("cannot make a slug from an empty title; pass --slug")
    pattern = work_rules(template)["branch"]
    unknown = set(re.findall(r"{(\w+)}", pattern)) - {"type", "number", "slug"}
    if unknown:
        raise Invalid(f"[work].branch uses unknown placeholder(s): {', '.join(sorted(unknown))}")
    name = pattern.format(type=kind, number=str(number).lstrip("#"), slug=slug)
    if (re.search(r"[\s~^:?*\[\\]|\.\.|@\{|//", name) or name.startswith(("-", "/"))
            or name.endswith((".", "/", ".lock"))):
        raise Invalid(f"{name!r} is not a valid branch name")
    return name


def merge_ask(template: dict, pr_url: str, description: str, warnings: list[str],
              acceptance_open: bool) -> dict:
    description = " ".join((description or "").split())
    words = len(description.split())
    problems = []
    if not description:
        problems.append("the change description is empty")
    if words > MAX_DESCRIPTION_WORDS:
        problems.append(f"the change description is {words} words; the limit is {MAX_DESCRIPTION_WORDS}")
    if "`" in description or re.search(r"https?://", description):
        problems.append("the change description must be plain language: no code spans or links "
                        "(the PR link goes on its own line)")
    if not pr_url:
        problems.append("the PR link is missing")
    header = work_rules(template)["merge_ask_header"]
    if not header or len(header) > MAX_HEADER_CHARS:
        problems.append(f"[work].merge_ask_header {header!r} must be 1-{MAX_HEADER_CHARS} characters")
    if problems:
        raise Invalid("; ".join(problems))
    lines = [f"Change description: {description}", "", f"PR: {pr_url}"]
    if acceptance_open:
        unaccepted = ("the change has a surface a person can verify, and it has not been "
                      "accepted yet")
        warnings = [unaccepted, *warnings]
    lines += [f"⚠️ Warning: {w}" for w in warnings]
    options = [
        {"label": "Merge now", "description": "Run the merge command, then tidy the local branch."},
        {"label": "Not yet", "description": "Leave the PR open; nothing is merged."},
    ]
    if acceptance_open:
        options.insert(0, {"label": "Deploy first (Recommended)",
                           "description": "Deploy this PR head for acceptance before any merge."})
    return {"header": header, "question": "\n".join(lines), "options": options,
            "multiSelect": False}


def merge_command(template: dict, pr: str, confirmed: bool) -> str:
    if not confirmed:
        raise Invalid("no --confirm: the merge ask has not been answered yes, so there is "
                      "no merge command to give")
    command = work_rules(template)["merge_command"]
    if not command.startswith("gh pr merge ") or "{pr}" not in command:
        raise Invalid(f"[work].merge_command {command!r} must start with 'gh pr merge' and contain {{pr}}")
    if not re.fullmatch(r"\d+", str(pr).lstrip("#")):
        raise Invalid(f"PR number {pr!r} is not a number")
    return command.format(pr=str(pr).lstrip("#"))


def status_payload(template: dict, tracker: str, repo: str, when: str,
                   board: int | None = None) -> dict:
    """A set-fields payload for one [work].status flip, or {"skip": reason}."""
    name = (work_rules(template).get("status") or {}).get(when)
    if not name:
        return {"skip": f"the template sets no status for {when}"}
    if tracker != "github":
        return {"skip": "status flips are written to GitHub boards only; the Jira adapter "
                        "has no transition operation"}
    routing = template.get("routing") or {}
    fields = [f for f, src in (routing.get("board_fields") or {}).items() if src == "status"]
    if not fields:
        return {"skip": "the template maps no board field to status"}
    import github_adapter as ga  # the routing rules are the adapter's, not a copy
    try:
        target, reason = ga.routing_board(routing, repo, board)
    except ga.AdapterExit as exc:
        return {"skip": str(exc), "needs_user": exc.body.get("needs_user", "board")}
    if target is None:
        return {"skip": reason}
    values = ((template.get("fields") or {}).get("status") or {}).get("values") or {}
    option = values.get(name, name)
    # tracker and issue make it a payload the adapter's set-fields accepts
    # (S7: without them the claim was refused as "not a payload produced by build").
    return {"tracker": "github", "repo": repo, "issue": None,
            "board": {**target, "values": {fields[0]: option}},
            "proposal_only": [], "status": name, "routed_by": reason}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="op", required=True)

    p = sub.add_parser("assess", help="act, guide or ask, from a fetched ticket")
    p.add_argument("--ticket", required=True, help="an adapter's `fetch` output")
    p.add_argument("--template", required=True, help="`ticket_template.py resolve` output")
    p.add_argument("--base", help="base branch the user named")
    p.add_argument("--repo", help="target repo the user named (owner/name)")

    p = sub.add_parser("branch", help="branch name from [work].branch")
    p.add_argument("--template", required=True)
    p.add_argument("--type", required=True, dest="kind")
    p.add_argument("--number", required=True, help="issue number or Jira key")
    p.add_argument("--title", required=True)
    p.add_argument("--slug")

    p = sub.add_parser("merge-ask", help="the merge ask's AskUserQuestion payload")
    p.add_argument("--template", required=True)
    p.add_argument("--pr-url", required=True)
    p.add_argument("--description", required=True, help="at most 60 plain-language words")
    p.add_argument("--warning", action="append", default=[])
    p.add_argument("--acceptance-open", action="store_true")

    p = sub.add_parser("merge-command", help="the merge command, only after a yes")
    p.add_argument("--template", required=True)
    p.add_argument("--pr", required=True)
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("status", help="set-fields payload for a [work].status flip")
    p.add_argument("--template", required=True)
    p.add_argument("--tracker", required=True, choices=("github", "jira"))
    p.add_argument("--repo", required=True)
    p.add_argument("--when", required=True, choices=("on_start", "on_pr"))
    p.add_argument("--board", type=int)
    p.add_argument("--out", help="write the payload here (default: stdout only)")

    p = sub.add_parser("weight-check", help="the ticket's tier against this session's model and effort")
    p.add_argument("--tier", default="", help="the assess output's `effort` value")
    p.add_argument("--model-id", default="", help="this session's model ID or name, from the system prompt")
    p.add_argument("--effort", default="", help="this session's CLAUDE_EFFORT; empty when unreadable")

    p = sub.add_parser("unblocked", help="after a merge: tickets it blocked that are now free")
    p.add_argument("--merged", required=True, help="the merged ticket's adapter `fetch` output")
    p.add_argument("--others", required=True,
                   help="JSON list of fetched tickets: each one it blocks and each one's other blockers")
    p.add_argument("--template", required=True)

    args = ap.parse_args(argv)
    try:
        if args.op == "weight-check":
            emit(weight_check(args.tier, args.model_id, args.effort))
            return EXIT_OK
        template = core.load_template(args.template)
        if args.op == "unblocked":
            others = load(args.others)
            if not isinstance(others, list):
                raise Invalid("--others must be a JSON list of fetched tickets")
            emit(unblocked(load(args.merged), others, template))
        elif args.op == "assess":
            emit(assess(load(args.ticket), template, base=args.base, repo=args.repo))
        elif args.op == "branch":
            emit({"branch": branch_name(template, args.kind, args.number, args.title, args.slug)})
        elif args.op == "merge-ask":
            emit(merge_ask(template, args.pr_url, args.description, args.warning, args.acceptance_open))
        elif args.op == "merge-command":
            emit({"command": merge_command(template, args.pr, args.confirm)})
        else:
            payload = status_payload(template, args.tracker, args.repo, args.when, args.board)
            if args.out and "skip" not in payload:
                Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
            emit(payload)
    except Invalid as exc:
        emit({"status": "INVALID", "message": str(exc)})
        return EXIT_INVALID
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        emit({"status": "INVALID", "message": f"{type(exc).__name__}: {exc}"})
        return EXIT_INVALID
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
