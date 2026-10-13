#!/usr/bin/env python3
"""GitHub adapter for create-issue and work-issue (references/adapter-contract.md).

Standard library only; Python 3.11 or later. Every call to GitHub goes through
`gh api`, and every body goes out as ASCII-escaped JSON on stdin
(`--input -`). Two `gh` shapes corrupt a body silently on native Windows and
neither is used here:

  * `gh issue|pr create|comment|edit --body-file <utf8 file>` decodes the file
    as cp1252, double-encoding every non-ASCII character.
  * `gh issue|pr ... --body "@path"` posts the literal string `@path`. Only
    `gh api` expands `@<path>`.

    github_adapter.py detect     --repo OWNER/NAME
    github_adapter.py build      --template T.json --draft D.json [--repo OWNER/NAME] [--board N]
    github_adapter.py duplicates --repo OWNER/NAME --title TEXT [--source-ref TEXT]
    github_adapter.py create     --payload P.json --confirm
    github_adapter.py set-fields --payload P.json --number N --confirm
    github_adapter.py link       --payload P.json --number N --confirm
    github_adapter.py comment    --repo OWNER/NAME --number N --body-file F --confirm
    github_adapter.py fetch      --repo OWNER/NAME --number N [--template T.json] [--with-board]
    github_adapter.py readback   --payload P.json --number N
    github_adapter.py diff       --payload P.json --actual A.json
    github_adapter.py repair     --payload P.json --number N --confirm

`--template` takes the output of `ticket_template.py resolve`. `--payload` is
the output of `build`. Output is JSON on stdout.

Exit codes: 0 success (VERIFIED or REPAIRED), 1 validation error (nothing was
sent), 2 tracker error or FAILED after the one repair, 3 write denied,
4 GitHub not reachable or not configured.

Labels are never created: GitHub creates an unknown label silently when an
issue is posted with it, so `create` checks every label against the repo
first and stops if one is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ticket_core as core

EXIT_OK, EXIT_INVALID, EXIT_TRACKER, EXIT_DENIED, EXIT_UNREACHABLE = 0, 1, 2, 3, 4

PUBLIC_WARNING = ("This repository is public: everything posted is visible to anyone. "
                  "Remove names, ids and customer data before posting.")
UNKNOWN_OUTCOME = ("The outcome is unknown: run `duplicates` for the exact title "
                   "before anything else, and post again only if it finds nothing.")


class AdapterExit(Exception):
    def __init__(self, code: int, body: dict):
        super().__init__(body.get("message") or body.get("error") or "")
        self.code, self.body = code, body


class GhError(Exception):
    def __init__(self, returncode: int, stderr: str):
        super().__init__(stderr.strip() or f"gh exited {returncode}")
        self.returncode, self.stderr = returncode, stderr


def fail(code: int, message: str, **extra) -> AdapterExit:
    return AdapterExit(code, {"ok": False, "error": message, **extra})


# --------------------------------------------------------------------------
# process plumbing
# --------------------------------------------------------------------------

def run_gh(args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run `gh`, decoding as UTF-8. `text=True` alone decodes as cp1252 on
    native Windows and raises the moment gh prints a non-ASCII character."""
    return subprocess.run(["gh", *args], input=input_text, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False)


def gh(args: list[str], input_text: str | None = None) -> str:
    try:
        proc = run_gh(args, input_text)
    except FileNotFoundError:
        raise fail(EXIT_UNREACHABLE, "The GitHub CLI (`gh`) is not installed or not on PATH.")
    if proc.returncode != 0:
        raise GhError(proc.returncode, proc.stderr or proc.stdout)
    return proc.stdout


def gh_json(args: list[str], input_text: str | None = None):
    out = gh(args, input_text)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise GhError(0, f"could not parse gh output: {out[:300]}")


def gh_api(endpoint: str, *, method: str | None = None, payload: dict | None = None,
           fields: dict | None = None):
    args = ["api", endpoint]
    if method:
        args += ["--method", method]
    for key, value in (fields or {}).items():
        args += ["-f", f"{key}={value}"]
    body = None
    if payload is not None:
        args += ["--input", "-"]
        body = json.dumps(payload, ensure_ascii=True)
    return gh_json(args, body)


DENIED_RE = re.compile(r"HTTP 40[13]|Resource not accessible|must have (push|write|admin)|"
                       r"not permitted|blocked by", re.IGNORECASE)


def is_denied(err: GhError) -> bool:
    text = err.stderr
    return bool(DENIED_RE.search(text)) and "rate limit" not in text.lower()


def denied(err: GhError, payload_path: str | None) -> AdapterExit:
    reason = (err.stderr.strip().splitlines() or ["permission"])[0][:200]
    where = payload_path or "the payload file you passed"
    return AdapterExit(EXIT_DENIED, {
        "ok": False,
        "message": (f"Writes to GitHub are blocked in this session ({reason}). Nothing was posted. "
                    f"The validated payload is saved at {where}. Post it from a session where "
                    f"writes are allowed, or paste it in by hand."),
    })


def write_guard(args) -> None:
    if not getattr(args, "confirm", False):
        raise fail(EXIT_INVALID, "This operation writes to GitHub and needs --confirm, "
                                  "which is passed only after the user's explicit yes.")


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

def norm_text(text) -> str:
    """Normalise ONLY line endings and whitespace at the very end. GitHub
    stores bodies with CRLF, so a raw comparison fails on every post. Nothing
    else is normalised: truncation, substitution and inner whitespace changes
    all still show up as a difference, which is the point."""
    return (text or "").replace("\r\n", "\n").rstrip()


def diff_report(expected: str, actual: str) -> str:
    exp, act = norm_text(expected), norm_text(actual)
    lines = [f"expected {len(exp)} chars, got {len(act)} chars"]
    for index, (left, right) in enumerate(zip(exp, act)):
        if left != right:
            start = max(0, index - 40)
            lines.append(f"first difference at char {index}")
            lines.append(f"expected: ...{exp[start:index + 40]!r}")
            lines.append(f"actual:   ...{act[start:index + 40]!r}")
            break
    else:
        if len(exp) != len(act):
            lines.append(f"bodies agree for {min(len(exp), len(act))} chars, then one ends")
    return "\n".join(lines)


def field_result(name: str, expected, actual) -> dict:
    if name == "body":
        ok = norm_text(expected) == norm_text(actual)
        out = {"name": name, "expected": f"{len(norm_text(expected))} chars",
               "actual": f"{len(norm_text(actual))} chars", "ok": ok}
        if not ok:
            out["detail"] = diff_report(expected, actual)
        return out
    if name == "labels":
        exp = sorted(str(x).lower() for x in expected or [])
        act = sorted(str(x).lower() for x in actual or [])
        return {"name": name, "expected": sorted(expected or []), "actual": sorted(actual or []),
                "ok": exp == act}
    return {"name": name, "expected": expected, "actual": actual, "ok": expected == actual}


def compare_issue(issue: dict, actual: dict) -> list[dict]:
    out = [field_result("title", issue["title"], actual.get("title")),
           field_result("body", issue["body"], actual.get("body")),
           field_result("labels", issue.get("labels") or [], actual.get("labels") or [])]
    if issue.get("type"):
        out.append(field_result("type", issue["type"], actual.get("type")))
    return out


def compare_board(values: dict, actual_board: dict | None) -> list[dict]:
    actual_board = actual_board or {}
    return [field_result(f"board.{name}", value, actual_board.get(name))
            for name, value in values.items()]


def verdict(fields: list[dict], repaired: bool) -> str:
    if all(f["ok"] for f in fields):
        return "REPAIRED" if repaired else "VERIFIED"
    return "FAILED"


def result(status: str, key=None, url=None, fields=None, message="", **extra) -> dict:
    return {"status": status, "key": key, "url": url, "fields": fields or [],
            "message": message, **extra}


def finish(res: dict) -> int:
    emit(res)
    return EXIT_OK if res["status"] in ("VERIFIED", "REPAIRED") else EXIT_TRACKER


def failed_message(fields: list[dict]) -> str:
    bad = [f["name"] for f in fields if not f["ok"]]
    return "Still different after the one repair: " + ", ".join(bad) + "."


# --------------------------------------------------------------------------
# reading an issue
# --------------------------------------------------------------------------

def actual_from_issue(resp: dict) -> dict:
    t = resp.get("type")
    return {"number": resp.get("number"), "url": resp.get("html_url"),
            "title": resp.get("title"), "body": resp.get("body"),
            "labels": [(x["name"] if isinstance(x, dict) else x) for x in resp.get("labels") or []],
            "type": t.get("name") if isinstance(t, dict) else t,
            "state": resp.get("state")}


FIELD_READBACK = """
query($owner:String!,$repo:String!,$num:Int!){
  repository(owner:$owner,name:$repo){
    issue(number:$num){
      projectItems(first:5){nodes{
        project{title number}
        fieldValues(first:20){nodes{
          ... on ProjectV2ItemFieldSingleSelectValue{
            name field{... on ProjectV2SingleSelectField{name}}
          }
        }}
      }}
    }
  }
}
"""


def read_board_fields(repo: str, number: int | str, board_number: int | None = None):
    """The issue's board fields, by field name. `gh issue view --json
    projectItems` omits custom fields entirely and would report a correctly
    set field as null, so this targeted query is the check. It never walks
    the board."""
    owner, name = repo.split("/", 1)
    data = gh_json(["api", "graphql", "-f", f"query={FIELD_READBACK}",
                    "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"num={number}"])
    try:
        nodes = data["data"]["repository"]["issue"]["projectItems"]["nodes"]
    except (KeyError, TypeError):
        raise GhError(0, "unexpected GraphQL response while reading board fields")
    out: dict = {}
    for item in nodes:
        if board_number is not None and (item.get("project") or {}).get("number") != board_number:
            continue
        for value in (item.get("fieldValues") or {}).get("nodes") or []:
            field = (value or {}).get("field") or {}
            if field.get("name"):
                out[field["name"]] = value.get("name")
    return out


def readback(repo: str, number, payload: dict) -> dict:
    actual = actual_from_issue(gh_api(f"repos/{repo}/issues/{number}"))
    board = payload.get("board")
    if board and board.get("values"):
        actual["board"] = read_board_fields(repo, number, board.get("number"))
    return actual


# --------------------------------------------------------------------------
# board fields
# --------------------------------------------------------------------------

def cache_path() -> Path:
    base = os.environ.get("TICKETS_CACHE_DIR")
    root = Path(base) if base else Path.home() / ".claude" / "cache" / "tickets"
    return root / "board-fields.json"


def load_cache() -> dict:
    try:
        return json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def project_fields(owner: str, number: int, *, refresh: bool = False) -> dict:
    """Field and option ids of one board, cached on disk. `field-list` reads
    the board's schema (a handful of nodes); it is not `item-list`, which
    walks every item and is the most expensive command in the toolbox. This
    adapter never calls item-list. The cache never expires, so `refresh`
    exists to tell a field the board lacks from a stale cache."""
    cache = load_cache()
    key = f"{owner}/{number}"
    if not refresh and key in cache:
        return cache[key]
    listing = gh_json(["project", "field-list", str(number), "--owner", owner,
                       "--format", "json", "--limit", "50"])
    view = gh_json(["project", "view", str(number), "--owner", owner, "--format", "json"])
    entry = {"projectId": view["id"], "fields": {
        f["name"]: {"id": f["id"], "options": {o["name"]: o["id"] for o in f.get("options", [])}}
        for f in listing.get("fields", [])}}
    cache[key] = entry
    save_cache(cache)
    return entry


def board_number(board: dict) -> int:
    if board.get("number") is not None:
        return int(board["number"])
    title = board.get("lookup_title")
    listing = gh_json(["project", "list", "--owner", board["owner"], "--format", "json",
                       "--limit", "100"])
    for project in listing.get("projects", []):
        if project.get("title") == title:
            return int(project["number"])
    raise fail(EXIT_INVALID, f"No board titled {title!r} under {board['owner']!r}. "
                             "Pass --board N to `build`, or add the repo to the template's routing.")


def set_board_fields(board: dict, issue_url: str, values: dict) -> list[str]:
    """Add the issue to the board and set the named single-select fields.
    Returns the problems (a field or option the board lacks, after the schema
    was re-read once); an empty list means every value was applied."""
    owner, number = board["owner"], board_number(board)
    schema = project_fields(owner, number)
    item = gh_json(["project", "item-add", str(number), "--owner", owner,
                    "--url", issue_url, "--format", "json"])
    problems: list[str] = []
    refreshed = False
    for name, option in values.items():
        if not option:
            continue
        field = schema["fields"].get(name)
        option_id = field["options"].get(option) if field else None
        if option_id is None and not refreshed:
            # A miss is not evidence the board lacks the field: the cache
            # never expires. Re-read the schema once, then believe the answer.
            schema = project_fields(owner, number, refresh=True)
            refreshed = True
            field = schema["fields"].get(name)
            option_id = field["options"].get(option) if field else None
        if not field:
            problems.append(f"board has no field {name!r}")
            continue
        if not option_id:
            problems.append(f"field {name!r} has no option {option!r}")
            continue
        gh(["project", "item-edit", "--id", item["id"], "--project-id", schema["projectId"],
            "--field-id", field["id"], "--single-select-option-id", option_id])
    return problems


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------

def load_json(path: str):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def load_payload(path: str) -> dict:
    payload = load_json(path)
    if not isinstance(payload, dict) or payload.get("tracker") != "github" or "issue" not in payload:
        raise fail(EXIT_INVALID, f"{path}: not a payload produced by `build` for GitHub")
    return payload


def emit(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------
# detect
# --------------------------------------------------------------------------

def op_detect(args) -> int:
    try:
        gh(["auth", "status"])
    except GhError as exc:
        raise fail(EXIT_UNREACHABLE, "GitHub is not configured: run `gh auth login` first.",
                   status="not-configured", detail=exc.stderr.strip()[:200])
    try:
        repo = gh_api(f"repos/{args.repo}")
    except GhError as exc:
        raise fail(EXIT_UNREACHABLE, f"Cannot read {args.repo}: {exc.stderr.strip()[:200]}",
                   status="not-configured")
    visibility = repo.get("visibility") or ("private" if repo.get("private") else "public")
    out = {"status": "ok", "tracker": "github", "repo": args.repo, "visibility": visibility,
           "has_issues": repo.get("has_issues", True),
           "can_push": bool((repo.get("permissions") or {}).get("push", False)), "warnings": []}
    if not out["has_issues"]:
        raise fail(EXIT_UNREACHABLE, f"Issues are disabled on {args.repo}. Track the work "
                                     "in the team's other tracker.", status="not-configured")
    if visibility == "public":
        out["warnings"].append(PUBLIC_WARNING)
    emit(out)
    return EXIT_OK


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def routing_board(routing: dict, repo: str, override: int | None) -> tuple[dict | None, str]:
    """Pick the board for a repo. Returns (board or None, reason)."""
    owner = routing.get("owner")
    if override is not None:
        return {"owner": owner or repo.split("/", 1)[0], "number": override}, "given on the command line"
    if not owner:
        return None, "the template has no routing owner"
    name = repo.split("/", 1)[1]
    entry = (routing.get("repos") or {}).get(repo, (routing.get("repos") or {}).get(name))
    if entry is not None:
        number = entry.get("board") if isinstance(entry, dict) else entry
        if number in (None, "none"):
            return None, "the template routes this repo to no board"
        return {"owner": owner, "number": int(number)}, "template routing"
    fallback = routing.get("fallback", "none")
    if fallback == "same-name-board":
        return {"owner": owner, "number": None, "lookup_title": name}, "board named like the repo"
    if fallback == "stop":
        raise fail(EXIT_INVALID, f"{repo} has no routing entry and the template says to stop and ask. "
                                 "Ask the user which board number to use, then pass --board N.",
                   needs_user="board")
    return None, "the repo has no routing entry"


def board_value(source: str, t: dict, d: dict) -> tuple[object, str]:
    """The value a board field takes from the draft, and why it is withheld
    (empty reason means settable)."""
    notes = d.get("draft_notes") or {}
    if source == "priority":
        return d.get("priority"), ""
    if source in ("size", "estimate"):
        est_t, est = t.get("estimate") or {}, d.get("estimate") or {}
        if est.get("value") is None:
            return None, ""
        if est_t.get("kind") != "size":
            return est["value"], "this adapter sets single-select board fields only, not numbers"
        if est_t.get("set_only_if", "investigated") == "investigated" and not notes.get("investigated"):
            return est["value"], "the work was not investigated, so the estimate is proposed only"
        return est["value"], ""
    value = (d.get("fields") or {}).get(source)
    return (None if value == "unset" else value), ""


def owner_has_type(owner: str, name: str) -> bool:
    """Issue types exist only for organizations that enabled them."""
    try:
        types = gh_api(f"orgs/{owner}/issue-types")
    except GhError:
        return False
    return any(str(x.get("name", "")).lower() == name.lower()
               for x in types if isinstance(x, dict))


def op_build(args) -> int:
    t = core.load_template(args.template)
    d = core.load_json(args.draft)
    repo = args.repo or (d.get("target") or {}).get("repo")
    errors: list[str] = []
    if not repo or "/" not in repo:
        errors.append("repo: give --repo OWNER/NAME or set target.repo in the draft")
    if t.get("tracker") not in (None, "github"):
        errors.append(f"template: is for {t['tracker']!r}, not github")
    check_errors, warnings = core.check_draft(t, d)
    errors += check_errors
    if errors:
        emit({"ok": False, "errors": errors, "warnings": warnings})
        return EXIT_INVALID

    body = core.render_body(t, d)
    labels = core.effective_labels(t, d)
    issue = {"title": d["title"].strip(), "body": body, "labels": labels}
    proposal: list[dict] = []

    if d.get("type"):
        owner = repo.split("/", 1)[0]
        if owner_has_type(owner, d["type"]):
            issue["type"] = d["type"]
        else:
            proposal.append({"what": "type", "value": d["type"],
                             "reason": f"{owner} has no issue type of that name; not applied"})

    routing = t.get("routing") or {}
    board, why_board = routing_board(routing, repo, args.board)
    board_fields = routing.get("board_fields") or {}
    values: dict = {}
    for field_name, source in board_fields.items():
        value, withheld = board_value(source, t, d)
        if value is None:
            continue
        if board is None:
            proposal.append({"what": field_name, "value": value, "reason": f"no board: {why_board}"})
        elif withheld:
            proposal.append({"what": field_name, "value": value, "reason": withheld})
        else:
            values[field_name] = value
    if board is None:
        for what, value in (("priority", d.get("priority")),
                            ("estimate", (d.get("estimate") or {}).get("value"))):
            if value is not None and not any(p["what"] == what for p in proposal) and not board_fields:
                proposal.append({"what": what, "value": value, "reason": f"no board: {why_board}"})

    settle = max([(t.get("fields", {}).get(src, {}).get("repair") or {}).get("after_seconds", 0)
                  for src in board_fields.values()] or [0])
    payload = {
        "tracker": "github", "repo": repo, "issue": issue,
        "board": ({**board, "values": values} if board else None),
        "links": d.get("links") or [], "parent": d.get("parent"),
        "settle_seconds": settle, "proposal_only": proposal,
    }
    emit({"ok": True, **payload, "warnings": warnings})
    return EXIT_OK


# --------------------------------------------------------------------------
# duplicates
# --------------------------------------------------------------------------

def op_duplicates(args) -> int:
    clean = args.title.replace('"', " ").strip()
    queries = [f'repo:{args.repo} is:issue in:title "{clean}"']
    if args.source_ref:
        queries.append(f'repo:{args.repo} is:issue in:body "{args.source_ref.replace(chr(34), " ")}"')
    hits: dict = {}
    try:
        for q in queries:
            data = gh_api("search/issues", method="GET", fields={"q": q})
            for item in data.get("items", []):
                hits.setdefault(item["number"], {
                    "number": item["number"], "title": item["title"], "state": item["state"],
                    "url": item["html_url"],
                    "exact": norm_text(item["title"]).lower() == norm_text(args.title).lower()})
    except GhError as exc:
        raise fail(EXIT_TRACKER, f"Duplicate search failed: {exc.stderr.strip()[:200]}")
    emit({"hits": sorted(hits.values(), key=lambda h: (not h["exact"], h["number"])),
          "message": f"{len(hits)} possible duplicate(s)."})
    return EXIT_OK


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def existing_labels(repo: str) -> set[str]:
    out = gh(["api", "--paginate", f"repos/{repo}/labels?per_page=100", "-q", ".[].name"])
    return {line.strip().lower() for line in out.splitlines() if line.strip()}


def patch_for(issue: dict, bad: list[dict]) -> dict:
    names = {f["name"] for f in bad}
    return {k: issue[k] for k in ("title", "body", "labels", "type") if k in names and k in issue}


def op_create(args) -> int:
    write_guard(args)
    payload = load_payload(args.payload)
    repo, issue = payload["repo"], payload["issue"]
    try:
        missing = [x for x in issue.get("labels") or [] if x.lower() not in existing_labels(repo)]
        if missing:
            raise fail(EXIT_INVALID, f"{', '.join(missing)}: not a label of {repo}. This adapter never "
                                     "creates labels; drop them or create them by hand first.")
        resp = gh_api(f"repos/{repo}/issues", method="POST", payload=issue)
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.payload)
        raise fail(EXIT_TRACKER, f"Creating the issue failed: {exc.stderr.strip()[:300]} {UNKNOWN_OUTCOME}")
    number, url = resp["number"], resp["html_url"]
    fields = compare_issue(issue, actual_from_issue(resp))
    if all(f["ok"] for f in fields):
        return finish(result("VERIFIED", number, url, fields, f"Created #{number} and the read-back matches."))
    bad = [f for f in fields if not f["ok"]]
    try:
        patched = gh_api(f"repos/{repo}/issues/{number}", method="PATCH", payload=patch_for(issue, bad))
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.payload)
        raise fail(EXIT_TRACKER, f"Created #{number} ({url}) but the repair failed: {exc.stderr.strip()[:300]}")
    fields = compare_issue(issue, actual_from_issue(patched))
    status = verdict(fields, True)
    message = (f"Created #{number}; the first read-back differed and one repair fixed it."
               if status == "REPAIRED" else f"Created #{number} ({url}). {failed_message(fields)}")
    return finish(result(status, number, url, fields, message))


def op_set_fields(args) -> int:
    write_guard(args)
    payload = load_payload(args.payload)
    board = payload.get("board")
    repo = payload["repo"]
    if not board or not board.get("values"):
        emit(result("VERIFIED", args.number, None, [], "Nothing to set on a board; "
                    "priority and estimate stay proposals: " + json.dumps(payload.get("proposal_only", []))))
        return EXIT_OK
    url = f"https://github.com/{repo}/issues/{args.number}"
    try:
        problems = set_board_fields(board, url, board["values"])
        actual = read_board_fields(repo, args.number, board_number(board))
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.payload)
        raise fail(EXIT_TRACKER, f"Setting board fields failed: {exc.stderr.strip()[:300]}")
    fields = compare_board(board["values"], actual)
    status = verdict(fields, False)
    message = "Board fields set and read back." if status == "VERIFIED" else (
        "; ".join(problems) or failed_message(fields))
    return finish(result(status, args.number, url, fields, message))


def issue_ref(target: str) -> str:
    return str(target)


def op_link(args) -> int:
    write_guard(args)
    payload = load_payload(args.payload)
    repo, links = payload["repo"], list(payload.get("links") or [])
    if not links and not payload.get("parent"):
        emit(result("VERIFIED", args.number, None, [], "No links to create."))
        return EXIT_OK
    unsupported = [lk for lk in links if lk.get("kind") != "blocks"]
    if unsupported:
        raise fail(EXIT_INVALID, "GitHub supports only `blocks` links and a parent; "
                                 f"got {[lk.get('kind') for lk in unsupported]}.")
    fields: list[dict] = []
    flags = {"inward": "--add-blocked-by", "outward": "--add-blocking"}
    try:
        for index, link in enumerate(links):
            if link.get("direction") not in flags:
                raise fail(EXIT_INVALID, f"links[{index}]: direction must be inward or outward")
            gh(["issue", "edit", str(args.number), "--repo", repo, flags[link["direction"]],
                issue_ref(link["target"])])
            if index == 0:
                # One link first, read back, then the rest: direction is verified, not assumed.
                seen = gh_json(["issue", "view", str(args.number), "--repo", repo,
                                "--json", "blockedBy,blocking"])
                key = "blockedBy" if link["direction"] == "inward" else "blocking"
                numbers = {str(x.get("number")) for x in nodes(seen.get(key))}
                tail = str(link["target"]).rstrip("/").split("/")[-1]
                ok = tail in numbers
                fields.append(field_result(f"link.{link['direction']}", tail, tail if ok else None))
                if not ok:
                    return finish(result("FAILED", args.number, None, fields,
                                         "The first link did not read back in the expected direction; "
                                         "no further links were created."))
            else:
                fields.append(field_result(f"link.{link['direction']}", str(link["target"]),
                                           str(link["target"])))
        if payload.get("parent"):
            parent = str(payload["parent"])
            child = gh_api(f"repos/{repo}/issues/{args.number}")
            gh_api(f"repos/{repo}/issues/{parent}/sub_issues", method="POST",
                   payload={"sub_issue_id": child["id"]})
            fields.append(field_result("parent", parent, parent))
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.payload)
        raise fail(EXIT_TRACKER, f"Creating a link failed: {exc.stderr.strip()[:300]}")
    return finish(result(verdict(fields, False), args.number, None, fields, "Links created."))


def op_comment(args) -> int:
    write_guard(args)
    try:
        body = Path(args.body_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise fail(EXIT_INVALID, f"{args.body_file}: cannot read as UTF-8 ({exc})")
    base = f"repos/{args.repo}/issues"
    try:
        resp = gh_api(f"{base}/{args.number}/comments", method="POST", payload={"body": body})
        fields = [field_result("body", body, resp.get("body"))]
        if fields[0]["ok"]:
            return finish(result("VERIFIED", resp["id"], resp.get("html_url"), fields, "Comment posted."))
        patched = gh_api(f"{base}/comments/{resp['id']}", method="PATCH", payload={"body": body})
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.body_file)
        raise fail(EXIT_TRACKER, f"Commenting failed: {exc.stderr.strip()[:300]} {UNKNOWN_OUTCOME}")
    fields = [field_result("body", body, patched.get("body"))]
    status = verdict(fields, True)
    return finish(result(status, resp["id"], resp.get("html_url"), fields,
                         "Comment posted; one repair fixed the body." if status == "REPAIRED"
                         else failed_message(fields)))


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------

def parse_sections(body: str, level: int) -> dict[str, str]:
    heading = re.compile(rf"^{'#' * level}\s+(.+?)\s*$")
    sections: dict[str, str] = {}
    current, buf = None, []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = heading.match(line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = core.strip_icon(m.group(1)), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


BASE_FIELDS = "number,title,body,state,labels,assignees,comments,url"
EXTRA_FIELDS = ",issueType,blockedBy,blocking,parent"


def nodes(value) -> list:
    """`gh issue view --json` wraps relation fields as {"nodes": [...],
    "totalCount": n}; accept a bare list too, in case another gh version
    returns one."""
    if isinstance(value, dict):
        value = value.get("nodes")
    return [x for x in value or [] if isinstance(x, dict)]


def op_fetch(args) -> int:
    try:
        try:
            data = gh_json(["issue", "view", str(args.number), "--repo", args.repo,
                            "--json", BASE_FIELDS + EXTRA_FIELDS])
        except GhError as exc:
            if "Unknown JSON field" not in exc.stderr:
                raise
            data = gh_json(["issue", "view", str(args.number), "--repo", args.repo,
                            "--json", BASE_FIELDS])
    except GhError as exc:
        raise fail(EXIT_TRACKER, f"Cannot read {args.repo}#{args.number}: {exc.stderr.strip()[:300]}")
    t = core.load_template(args.template) if args.template else {}
    level = (t.get("body") or {}).get("heading_level", 2)
    sections = parse_sections(data.get("body"), level)
    prompt_titles = [s["title"] for s in (t.get("body") or {}).get("sections", [])
                     if s.get("kind") == "ai_prompt"] or [k for k in sections if k.lower() == "ai prompt"]
    ai_prompt = next((sections[k] for k in prompt_titles if sections.get(k)), None)
    links = [{"kind": "blocks", "direction": "inward", "target": str(x.get("number"))}
             for x in nodes(data.get("blockedBy"))]
    links += [{"kind": "blocks", "direction": "outward", "target": str(x.get("number"))}
              for x in nodes(data.get("blocking"))]
    issue_type = data.get("issueType")
    parent = data.get("parent")
    assignees = data.get("assignees") or []
    ticket = {
        "tracker": "github", "target": {"repo": args.repo}, "key": str(data["number"]),
        "url": data.get("url"),
        "type": issue_type.get("name") if isinstance(issue_type, dict) else issue_type,
        "title": data.get("title"), "body": (data.get("body") or "").replace("\r\n", "\n"),
        "sections": sections, "labels": [x["name"] for x in data.get("labels") or []],
        "priority": None, "estimate": None, "fields": {},
        "parent": str(parent.get("number")) if isinstance(parent, dict) else None,
        "links": links, "state": str(data.get("state", "")).lower(),
        "assignee": assignees[0].get("login") if assignees else None,
        "thread": [{"author": (c.get("author") or {}).get("login"), "created_at": c.get("createdAt"),
                    "body": (c.get("body") or "").replace("\r\n", "\n")}
                   for c in data.get("comments") or []],
        "has_ai_prompt": ai_prompt is not None, "ai_prompt": ai_prompt,
    }
    if args.with_board:
        try:
            ticket["board"] = read_board_fields(args.repo, args.number)
        except GhError as exc:
            ticket["board"] = None
            ticket["board_error"] = exc.stderr.strip()[:200]
    emit(ticket)
    return EXIT_OK


def op_readback(args) -> int:
    payload = load_payload(args.payload)
    try:
        emit(readback(payload["repo"], args.number, payload))
    except GhError as exc:
        raise fail(EXIT_TRACKER, f"Read-back failed: {exc.stderr.strip()[:300]}")
    return EXIT_OK


def diff_all(payload: dict, actual: dict) -> list[dict]:
    fields = compare_issue(payload["issue"], actual)
    board = payload.get("board")
    if board and board.get("values"):
        fields += compare_board(board["values"], actual.get("board"))
    return fields


def op_diff(args) -> int:
    payload = load_payload(args.payload)
    fields = diff_all(payload, core.load_json(args.actual))
    status = verdict(fields, False)
    return finish(result(status, None, None, fields,
                         "Every field matches." if status == "VERIFIED" else failed_message(fields)))


def op_repair(args) -> int:
    write_guard(args)
    payload = load_payload(args.payload)
    repo, number, issue = payload["repo"], args.number, payload["issue"]
    try:
        if payload.get("settle_seconds") and not args.no_wait:
            time.sleep(payload["settle_seconds"])
        fields = diff_all(payload, readback(repo, number, payload))
        bad = [f for f in fields if not f["ok"]]
        if not bad:
            return finish(result("VERIFIED", number, None, fields, "Nothing to repair."))
        issue_patch = patch_for(issue, bad)
        if issue_patch:
            gh_api(f"repos/{repo}/issues/{number}", method="PATCH", payload=issue_patch)
        board = payload.get("board")
        stale = {f["name"][len("board."):]: board["values"][f["name"][len("board."):]]
                 for f in bad if f["name"].startswith("board.")}
        if stale:
            set_board_fields(board, f"https://github.com/{repo}/issues/{number}", stale)
        fields = diff_all(payload, readback(repo, number, payload))
    except GhError as exc:
        if is_denied(exc):
            raise denied(exc, args.payload)
        raise fail(EXIT_TRACKER, f"Repair failed: {exc.stderr.strip()[:300]}")
    status = verdict(fields, True)
    return finish(result(status, number, None, fields,
                         "One repair made every field match." if status == "REPAIRED"
                         else failed_message(fields)))


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True)

    def add(name, func, *, repo=False, number=False, payload=False, confirm=False):
        p = sub.add_parser(name)
        if repo:
            p.add_argument("--repo", required=True, metavar="OWNER/NAME")
        if payload:
            p.add_argument("--payload", required=True)
        if number:
            p.add_argument("--number", required=True, type=int)
        if confirm:
            p.add_argument("--confirm", action="store_true")
        p.set_defaults(func=func)
        return p

    add("detect", op_detect, repo=True)
    p = add("build", op_build)
    p.add_argument("--template", required=True)
    p.add_argument("--draft", required=True)
    p.add_argument("--repo")
    p.add_argument("--board", type=int, help="board number, when the template cannot decide")
    p = add("duplicates", op_duplicates, repo=True)
    p.add_argument("--title", required=True)
    p.add_argument("--source-ref")
    add("create", op_create, payload=True, confirm=True)
    add("set-fields", op_set_fields, payload=True, number=True, confirm=True)
    add("link", op_link, payload=True, number=True, confirm=True)
    p = add("comment", op_comment, repo=True, number=True, confirm=True)
    p.add_argument("--body-file", required=True, help="UTF-8 text file; the adapter reads it, not gh")
    p = add("fetch", op_fetch, repo=True, number=True)
    p.add_argument("--template")
    p.add_argument("--with-board", action="store_true")
    add("readback", op_readback, payload=True, number=True)
    p = add("diff", op_diff, payload=True)
    p.add_argument("--actual", required=True, help="output of `readback`, or - for stdin")
    p = add("repair", op_repair, payload=True, number=True, confirm=True)
    p.add_argument("--no-wait", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AdapterExit as exc:
        emit(exc.body)
        return exc.code
    except GhError as exc:
        emit({"ok": False, "error": exc.stderr.strip()[:300]})
        return EXIT_TRACKER


if __name__ == "__main__":
    sys.exit(main())
