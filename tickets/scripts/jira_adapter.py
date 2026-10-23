#!/usr/bin/env python3
"""Jira tracker adapter for the tickets plugin (relay transport).

Implements references/adapter-contract.md for Jira through the Atlassian
MCP server. Only the model can call an MCP tool, so this script never talks
to Jira itself. It prints call specs; the model makes exactly those calls,
saves each raw result to the named file, and runs the same command again.
Every op is a small state machine over a run directory, so a re-run is
always safe and resumes where the last one stopped.

The relay loop the skill follows, for every op:

    run the command
    while stdout says {"status": "RELAY", "calls": [...]}:
        make each call with its arguments unchanged
        write each raw result (or the error text) to its result_file
        run the same command again
    stdout is now the op's output; the exit code is per the contract

Standard library only. Python 3.11 or later. Shares ticket_core.py (S2).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ticket_core as core  # shared checks and body rendering
import write_guard  # opt-in pipeline gate and relay tokens

EXIT_OK, EXIT_INVALID, EXIT_TRACKER, EXIT_DENIED, EXIT_UNREACHABLE = 0, 1, 2, 3, 4

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")

# Call shapes for the Atlassian MCP v2 tool set, verified against the live
# server (2026-10-08). It is the only tool set supported: Atlassian serves
# v2 tools on the /v1/mcp endpoints too, so a server still exposing the
# retired v1 tools is refused by detect() rather than driven (issue #199).
TOOLS = {
    "create": "createJiraIssue",
    "edit": "editJiraIssue",
    "get": "getJiraIssue",
    "search": "searchJiraIssuesUsingJql",
    "comment": "addOrEditJiraIssueComment",
    "link": ("executeWrite", "createJiraIssueLink"),
    "read_op": ("executeRead", "getJiraIssue"),
    # getJiraIssue reports only a comment count; the comments are a list op.
    "comments": ("executeRead", "listJiraIssueComments"),
    "transitions": ("executeRead", "listJiraIssueTransitions"),
    "transition": "transitionJiraIssue",
}
# Tools only the retired v1 tool set has; their presence without the v2
# meta-tools marks a server detect() refuses.
V1_ONLY = {"addCommentToJiraIssue", "createIssueLink", "getTransitionsForJiraIssue"}
V2_ONLY = {"discover", "executeRead", "executeWrite"}
V2_ENDPOINT = "https://mcp.atlassian.com/v2/mcp"
WRITE_OPS = ("create", "edit", "comment", "link")
SYSTEM_READ_FIELDS = ["summary", "description", "priority", "status", "assignee"]
STATUS_READ_FIELDS = ["status", "resolution"]
COMMENT_PAGE = 100  # the most listJiraIssueComments returns in one page
# Jira's three fixed status categories; a workflow's status names vary, these do not.
CATEGORY_KEYS = {"to do": "new", "in progress": "indeterminate", "done": "done"}
# A blocker closed with one of these resolutions was dropped, not finished:
# the wait asks before it goes on, as GitHub's NOT_PLANNED does.
ABANDONED_RESOLUTION = re.compile(r"won'?t|duplicate|declined|rejected|cannot|can't|invalid|"
                                  r"obsolete|incomplete|not a bug|not needed", re.IGNORECASE)
WAIT_HOURS = 24


class Stop(Exception):
    """Ends the op with an exit code and a JSON body for stdout."""

    def __init__(self, code: int, body: dict):
        super().__init__(body.get("message", ""))
        self.code = code
        self.body = body


class Relay(Exception):
    """Ends the op early: these calls must be made before it can go on."""

    def __init__(self, calls: list[dict]):
        super().__init__("relay")
        self.calls = calls


# --------------------------------------------------------------------------
# detect


def detect(tool_names: list[str]) -> dict:
    """Find the Atlassian MCP tool-name prefix and its v2 tools from the tool list."""
    prefixes: dict[str, set[str]] = {}
    known = {b[0] if isinstance(b, tuple) else b for b in TOOLS.values()} | V1_ONLY | V2_ONLY
    for full in tool_names:
        for bare in known:
            if full.endswith(bare) and full != bare:
                prefix = full[: -len(bare)]
                if prefix.startswith("mcp__") and prefix.endswith("__"):
                    prefixes.setdefault(prefix, set()).add(bare)
    candidates, legacy = [], []
    for prefix, bares in prefixes.items():
        if "getJiraIssue" not in bares:
            continue
        if bares & V1_ONLY and not bares & V2_ONLY:
            legacy.append(prefix)
            continue
        tools, missing = {}, []
        for op, bare in TOOLS.items():
            tool = bare[0] if isinstance(bare, tuple) else bare
            if tool in bares:
                tools[op] = prefix + tool
            else:
                missing.append(op)
        writes = all(op in tools for op in WRITE_OPS)
        candidates.append({"prefix": prefix, "tools": tools, "writes": writes, "missing": missing})
    if not candidates:
        if legacy:
            return {"status": "unsupported", "candidates": legacy,
                    "message": ("The Atlassian MCP server here exposes the retired v1 tool set, "
                                "which is not supported. Reconnect it to "
                                f"{V2_ENDPOINT} and start a new session.")}
        return {"status": "not-configured",
                "message": "No Atlassian MCP server is connected in this session."}
    candidates.sort(key=lambda c: (not c["writes"], c["prefix"]))
    best = dict(candidates[0])
    best["status"] = "ok"
    best["candidates"] = [c["prefix"] for c in candidates]
    if not best["writes"]:
        best["message"] = ("The Atlassian MCP server here is read-only "
                           f"(missing: {', '.join(best['missing'])}).")
    return best


# --------------------------------------------------------------------------
# template and ticket loading


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_template(path: str) -> dict:
    """Load a *resolved* template: `ticket_template.py resolve` output, or a bare one."""
    template = core.load_template(path)
    if template.get("extends"):
        raise Stop(EXIT_INVALID, {"status": "INVALID", "message":
                                  f"{path} still has 'extends'; pass the template the loader resolved."})
    return template


# --------------------------------------------------------------------------
# build


def build(ticket: dict, template: dict, env: dict) -> tuple[dict, list[str], list[str]]:
    """Validate a draft against the template; return (payload, errors, warnings).

    The tracker-independent checks and the body rendering are ticket_core's;
    this adds only what is specific to Jira and to the MCP call shapes.
    """
    errors, warnings = core.check_draft(template, ticket)
    if env.get("status") != "ok":
        errors.append("env: detect found no Atlassian MCP server; run detect first")
    if ticket.get("tracker") != "jira":
        errors.append(f"tracker: {ticket.get('tracker')!r}, this is the Jira adapter")
    target = ticket.get("target") or {}
    site, project = target.get("site"), target.get("project")
    if not site:
        errors.append("target.site: required")
    if not project:
        errors.append("target.project: required")

    title = (ticket.get("title") or "").strip()
    issue_type = ticket.get("type") or template.get("types", {}).get("default")
    if not issue_type:
        errors.append("type: missing, and the template has no default")
    if ticket.get("sections") is not None:
        body = core.render_body(template, ticket).strip()
    else:
        body = (ticket.get("body") or "").strip()

    notes = ticket.get("draft_notes") or {}
    confirmations = notes.get("confirmations") or {}
    source_key = notes.get("source_key")
    if source_key is not None and not KEY_RE.match(str(source_key)):
        errors.append(f"draft_notes.source_key: {source_key!r} is not an issue key")
        source_key = None
    fdefs = template.get("fields", {})
    values = {k: v for k, v in (ticket.get("fields") or {}).items() if v not in (None, "unset")}

    priority = None
    pcfg = template.get("priority", {})
    pvalue = ticket.get("priority") or pcfg.get("default")
    if pvalue is not None:
        pfield = pcfg.get("field", "priority")
        if pfield == "priority":
            priority = pvalue
        else:
            values.setdefault(pfield, pvalue)

    comment = None
    estimate = ticket.get("estimate") or {}
    ecfg = template.get("estimate", {})
    if estimate.get("value") is not None and ecfg.get("kind", "none") != "none":
        evalue = estimate["value"]
        if ecfg.get("set_only_if") == "investigated" and not core.investigated(ticket):
            warnings.append("estimate: not set, the template sets it only after an investigation")
        else:
            efield = ecfg.get("field")
            if not efield or efield not in fdefs:
                errors.append(f"estimate.field: {efield!r} is not declared under [fields]")
            else:
                values[efield] = evalue
                if ecfg.get("comment"):
                    comment = ecfg["comment"].replace("{guide}", ecfg.get("guide", ""))

    for key in list(values):
        if (fdefs.get(key) or {}).get("set_only_if") == "investigated" and not core.investigated(ticket):
            warnings.append(f"fields.{key}: not set, the template sets it only after an investigation")
            del values[key]

    for key, fdef in fdefs.items():
        default = fdef.get("default", "unset")
        if key not in values and default != "unset":
            values[key] = default

    parent = ticket.get("parent")
    links_cfg = template.get("links", {})
    parent_mode = links_cfg.get("parent", "native")
    if parent and not KEY_RE.match(str(parent)):
        errors.append(f"parent: {parent!r} is not an issue key")
    if parent and parent_mode != "native":
        values[parent_mode] = parent
        parent = None

    expected_fields, additional = {}, {}
    for key, value in values.items():
        fdef = fdefs.get(key)
        if fdef is None:
            continue  # check_draft has already reported it
        if value in (fdef.get("confirm_values") or []) and confirmations.get(key) != value:
            continue  # check_draft has already reported it
        if not fdef.get("id"):
            errors.append(f"fields.{key}: the template gives no id")
            continue
        shaped = shape_value(key, fdef, value, errors)
        if shaped is None:
            continue
        additional[fdef["id"]] = shaped
        expected_fields[key] = {"id": fdef["id"], "kind": fdef.get("kind", "text"),
                                "value": value, "jira": shaped}
    unset_guarded = {}
    for key, fdef in fdefs.items():
        if fdef.get("confirm_values") and key not in expected_fields and fdef.get("id"):
            unset_guarded[key] = {"id": fdef["id"], "confirm_values": fdef["confirm_values"],
                                  "option_ids": [str((fdef.get("values") or {}).get(v, v))
                                                 for v in fdef["confirm_values"]]}

    links = []
    for link in ticket.get("links") or []:
        kind = link.get("kind")
        lcfg_kind = links_cfg.get(kind) if kind != "parent" else None
        if not isinstance(lcfg_kind, dict):
            errors.append(f"links: kind {kind!r} is not declared under [links]")
            continue
        if not lcfg_kind.get("name"):
            errors.append(f"links.{kind}: no 'name'; the Jira MCP needs the link type name")
            continue
        direction = link.get("direction", "outward")
        if direction not in ("outward", "inward"):
            errors.append(f"links: direction {direction!r} must be 'outward' or 'inward'")
            continue
        if not KEY_RE.match(str(link.get("target", ""))):
            errors.append(f"links: target {link.get('target')!r} is not an issue key")
            continue
        links.append({"kind": kind, "name": lcfg_kind["name"], "direction": direction,
                      "target": link["target"]})

    repair_wait = max([int((f.get("repair") or {}).get("after_seconds", 0))
                       for f in fdefs.values()] or [0])
    expected = {"title": title, "type": issue_type, "body": body,
                "labels": core.effective_labels(template, ticket), "priority": priority, "parent": parent,
                "fields": expected_fields, "unset_guarded": unset_guarded, "links": links}
    payload = {"tracker": "jira", "env": env, "cloudId": site, "project": project,
               "site_url": site_url(site), "expected": expected, "comment": comment,
               "assignee": ticket.get("assignee"), "additional_fields": additional,
               "repair_wait": repair_wait, "write": "create",
               "source_key": source_key}
    return payload, errors, warnings


def shape_value(key: str, fdef: dict, value, errors: list[str]):
    kind = fdef.get("kind", "text")
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"fields.{key}: needs a number, got {value!r}")
            return None
        return value
    if kind == "select":
        options = fdef.get("values") or {}
        if options:
            return {"id": str(options[value])} if value in options else None
        return {"value": str(value)}
    if kind == "user":
        return {"accountId": str(value)}
    if kind == "date":
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
            errors.append(f"fields.{key}: needs a YYYY-MM-DD date, got {value!r}")
            return None
        return str(value)
    if kind == "text":
        return str(value)
    errors.append(f"fields.{key}: unknown kind {kind!r}")
    return None


def parse_sections(body: str, level: int = 2) -> dict[str, str]:
    marker = re.compile(rf"^#{{{level}}}\s+(.+?)\s*#*\s*$")
    sections: dict[str, list[str]] = {}
    current = None
    for line in (body or "").splitlines():
        m = marker.match(line)
        if m and not line.startswith("#" * (level + 1)):
            current = core.strip_icon(m.group(1))
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def site_url(site: str | None) -> str:
    if not site:
        return ""
    return site if site.startswith("http") else f"https://{site}"


# --------------------------------------------------------------------------
# call specs


def tool(payload: dict, op: str) -> str:
    env = payload["env"]
    if op not in env.get("tools", {}):
        if op in WRITE_OPS:
            raise Stop(EXIT_DENIED, denied_body(payload, "read-only server"))
        raise Stop(EXIT_UNREACHABLE, {"status": "UNREACHABLE", "message":
                                      f"The Atlassian MCP server here has no '{op}' tool."})
    return env["tools"][op]


def spec(run: Path, name: str, tool_name: str, arguments: dict) -> dict:
    return {"tool": tool_name, "arguments": arguments,
            "result_file": str(result_path(run, name))}


def result_path(run: Path, name: str) -> Path:
    return run / "results" / f"{name}.json"


def create_spec(run: Path, payload: dict) -> dict:
    exp = payload["expected"]
    args = {"cloudId": payload["cloudId"], "projectKey": payload["project"],
            "summary": exp["title"], "description": exp["body"], "contentFormat": "markdown",
            "issueType": exp["type"]}
    if exp["labels"]:
        args["labels"] = exp["labels"]
    if exp["priority"]:
        args["priority"] = exp["priority"]
    if exp["parent"]:
        args["parent"] = exp["parent"]
    if payload.get("assignee"):
        args["assignee"] = payload["assignee"]
    extra = dict(payload["additional_fields"])
    if extra:
        args["additional_fields"] = extra
    return spec(run, "create", tool(payload, "create"), args)


def edit_spec(run: Path, payload: dict, key: str, fields: dict, name: str) -> dict:
    args = {"cloudId": payload["cloudId"], "issueIdOrKey": key, "fields": fields}
    if "description" in fields:
        args["contentFormat"] = "markdown"
    return spec(run, name, tool(payload, "edit"), args)


def link_spec(run: Path, payload: dict, key: str, link: dict, name: str) -> dict:
    # The link reads inwardIssue -> outwardIssue with the type's outward
    # wording ("A blocks B"). "outward" means this ticket is the subject.
    inward, outward = (key, link["target"]) if link["direction"] == "outward" else (link["target"], key)
    return spec(run, name, tool(payload, "link"),
                {"name": TOOLS["link"][1], "cloudId": payload["cloudId"],
                 "inputs": {"linkType": link["name"], "inwardIssue": inward,
                            "outwardIssue": outward}})


def comment_spec(run: Path, payload: dict, key: str, text: str) -> dict:
    return spec(run, "comment", tool(payload, "comment"),
                {"cloudId": payload["cloudId"], "issueIdOrKey": key, "commentBody": text})


def readback_specs(run: Path, payload: dict, key: str, suffix: str) -> list[dict]:
    """Read back every field the payload set, custom fields by explicit id."""
    exp = payload["expected"]
    ids = [f["id"] for f in exp["fields"].values()] + [g["id"] for g in exp["unset_guarded"].values()]
    get = tool(payload, "get")
    calls = [spec(run, f"readback-fields{suffix}", get,
                  {"cloudId": payload["cloudId"], "issueIdOrKey": key,
                   "fields": SYSTEM_READ_FIELDS + sorted(set(ids))})]
    # getJiraIssue drops issuetype, labels, parent and issuelinks from an
    # explicit field list; the evidence view carries them.
    if exp["parent"] or exp["links"]:
        calls.append(spec(run, f"readback-evidence{suffix}", get,
                          {"cloudId": payload["cloudId"], "issueIdOrKey": key,
                           "view": "evidence"}))
    else:
        calls.append(spec(run, f"readback-system{suffix}", tool(payload, "read_op"),
                          {"name": TOOLS["read_op"][1], "cloudId": payload["cloudId"],
                           "inputs": {"issueIdOrKey": key, "view": "evidence"},
                           "responseFields": ["key", "fields.issuetype.name", "fields.labels"]}))
    return calls


def search_spec(run: Path, payload: dict, name: str, jql: str) -> dict:
    return spec(run, name, tool(payload, "search"),
                {"cloudId": payload["cloudId"], "jql": jql, "maxResults": 10,
                 "fields": ["summary", "status", "issuetype"]})


def comments_spec(run: Path, payload: dict, key: str, name: str, newest_first: bool = False) -> dict:
    """One page of comments through listJiraIssueComments."""
    return spec(run, name, tool(payload, "comments"),
                {"name": TOOLS["comments"][1], "cloudId": payload["cloudId"],
                 "inputs": {"issueIdOrKey": key, "maxResults": COMMENT_PAGE,
                            "orderBy": "-created" if newest_first else "created"}})


def status_spec(run: Path, payload: dict, key: str, name: str) -> dict:
    """Status, its category and the resolution. The explicit field list drops the
    category, so it reads through executeRead with responseFields (verified live)."""
    return spec(run, name, tool(payload, "read_op"),
                {"name": TOOLS["read_op"][1], "cloudId": payload["cloudId"],
                 "inputs": {"issueIdOrKey": key, "fields": STATUS_READ_FIELDS, "fieldsByKeys": True},
                 "responseFields": ["key", "fields.status.name",
                                    "fields.status.statusCategory.key", "fields.resolution.name"]})


def transitions_spec(run: Path, payload: dict, key: str, name: str) -> dict:
    return spec(run, name, tool(payload, "transitions"),
                {"name": TOOLS["transitions"][1], "cloudId": payload["cloudId"],
                 "inputs": {"issueIdOrKey": key}})


def transition_spec(run: Path, payload: dict, key: str, transition_id: str) -> dict:
    args = {"cloudId": payload["cloudId"], "issueIdOrKey": key, "transitionId": transition_id}
    return spec(run, "transition", tool(payload, "transition"), args)


# --------------------------------------------------------------------------
# reading relay results


def read_result(run: Path, name: str, payload: dict | None = None, key: str | None = None):
    """Return the parsed result, or None if the file is not there yet.

    An error result stops the op: exit 3 when it is a denial, else exit 2.
    """
    path = result_path(run, name)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    data = None
    try:
        data = json.loads(text) if text else None
    except json.JSONDecodeError:
        pass
    error = error_text(data, text)
    if error is not None:
        blocker = classify_denial(error)
        if blocker and payload is not None:
            raise Stop(EXIT_DENIED, denied_body(payload, blocker, key=key, step=name))
        raise Stop(EXIT_TRACKER, {"status": "FAILED", "key": key, "step": name,
                                  "message": f"Jira call '{name}' failed: {error[:300]}"})
    return data


def error_text(data, text: str) -> str | None:
    if data is None:
        return text or "empty result"
    if isinstance(data, dict) and (data.get("isError") or data.get("error") or data.get("errors")):
        parts = [data.get("error"), data.get("errors"), data.get("message"), data.get("repairHint")]
        return " ".join(json.dumps(p) if not isinstance(p, str) else p for p in parts if p)
    return None


DENIAL_PATTERNS = [
    ("hook", re.compile(r"\bhook\b|PreToolUse", re.IGNORECASE)),
    ("read-only server", re.compile(r"read[- ]only", re.IGNORECASE)),
    ("policy", re.compile(r"\bpolicy\b|managed setting|not allowed by", re.IGNORECASE)),
    ("permission", re.compile(r"permission|denied|doesn't want to proceed|rejected|forbidden|"
                              r"\b403\b|\b401\b|scope|unauthori[sz]ed|not permitted", re.IGNORECASE)),
]


def classify_denial(error: str) -> str | None:
    for label, pattern in DENIAL_PATTERNS:
        if pattern.search(error):
            return label
    return None


def denied_body(payload: dict, blocker: str, key: str | None = None, step: str | None = None) -> dict:
    where = payload.get("_path", "the run directory")
    if key:
        message = (f"Writes to Jira are blocked in this session ({blocker}). {key} was created, "
                   f"but step '{step}' was not applied. The validated payload is saved at {where}. "
                   "Finish it from a session where writes are allowed, or by hand.")
    else:
        message = (f"Writes to Jira are blocked in this session ({blocker}). Nothing was posted. "
                   f"The validated payload is saved at {where}. Post it from a session where "
                   "writes are allowed, or paste it in by hand.")
    return {"status": "DENIED", "key": key, "blocker": blocker, "message": message}


def unwrap(data):
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], (dict, list)):
        data = data["data"]
    if isinstance(data, dict) and isinstance(data.get("issues"), list):
        data = data["issues"][0] if data["issues"] else {}
    return data


def find_key(data) -> str | None:
    data = unwrap(data)
    if isinstance(data, dict):
        if isinstance(data.get("key"), str) and KEY_RE.match(data["key"]):
            return data["key"]
        for value in data.values():
            found = find_key(value) if isinstance(value, (dict, list)) else None
            if found:
                return found
    if isinstance(data, list):
        for value in data:
            found = find_key(value)
            if found:
                return found
    return None


_ABSENT = object()


def normalize_issue(raw) -> dict:
    """Map one getJiraIssue result (v2 customFields shape or raw REST) to flat keys.

    Only keys present in the result are set, so partial reads can be merged.
    """
    data = unwrap(raw)
    if not isinstance(data, dict):
        return {}
    f = data.get("fields") or {}
    out: dict = {}
    if data.get("key"):
        out["key"] = data["key"]
    for name in ("summary", "description"):
        if name in f:
            out[name] = f[name]
    for name in ("priority", "issuetype", "status", "resolution"):
        if name in f:
            out[name] = (f[name] or {}).get("name") if isinstance(f[name], dict) else f[name]
    if isinstance(f.get("status"), dict) and isinstance(f["status"].get("statusCategory"), dict):
        cat = f["status"]["statusCategory"]
        # The evidence view carries only the category's name (verified live).
        out["status_category"] = cat.get("key") or CATEGORY_KEYS.get(str(cat.get("name", "")).lower())
    if "labels" in f:
        out["labels"] = list(f["labels"] or [])
    if "parent" in f:
        out["parent"] = (f["parent"] or {}).get("key")
    if "issuelinks" in f:
        out["links"] = [link_view(link) for link in f["issuelinks"] or []]
    custom = {}
    for entry in (f.get("customFields") or {}).values():
        if isinstance(entry, dict) and entry.get("id"):
            custom[entry["id"]] = entry.get("value")
    for name, value in f.items():
        if name.startswith("customfield_"):
            custom[name] = value
    if custom:
        out["custom"] = custom
    return out


def link_view(link: dict) -> dict:
    ltype = (link.get("type") or {}).get("name")
    if link.get("outwardIssue"):
        return {"name": ltype, "direction": "outward", "target": link["outwardIssue"].get("key")}
    return {"name": ltype, "direction": "inward", "target": (link.get("inwardIssue") or {}).get("key")}


def merge_reads(reads: list[dict]) -> dict:
    merged: dict = {"custom": {}}
    for read in reads:
        for name, value in read.items():
            if name == "custom":
                merged["custom"].update(value)
            else:
                merged[name] = value
    return merged


def adf_text(node) -> str:
    """Plain text of an Atlassian Document Format body, when a comment comes back as ADF."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    if node.get("type") == "hardBreak":
        return "\n"
    inner = adf_text(node.get("content") or [])
    return inner + "\n\n" if node.get("type") in ("paragraph", "heading", "listItem") else inner


def parse_comments(raw) -> tuple[list[dict], int]:
    """(comments oldest first as {id, author, created_at, body}, total on the server).

    Takes a listJiraIssueComments page, or tolerates a getJiraIssue result whose
    `comment` field holds the page (raw REST shape).
    """
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    if isinstance(data, dict) and "comments" not in data:
        data = ((data.get("fields") or {}).get("comment")) or {}
    comments = (data.get("comments") or []) if isinstance(data, dict) else []
    out = []
    for c in comments:
        if not isinstance(c, dict):
            continue
        body = c.get("body")
        out.append({"id": str(c["id"]) if c.get("id") is not None else None,
                    "author": (c.get("author") or {}).get("displayName"),
                    "created_at": c.get("created"),
                    "body": (adf_text(body).strip() if not isinstance(body, str) else body)
                    .replace("\r\n", "\n")})
    out.sort(key=lambda c: c["created_at"] or "")
    total = data.get("total") if isinstance(data, dict) else None
    return out, total if isinstance(total, int) else len(out)


def parse_transitions(raw) -> list[dict]:
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    out = []
    for t in (data.get("transitions") or []) if isinstance(data, dict) else []:
        to = t.get("to") or {}
        out.append({"id": str(t.get("id")), "name": t.get("name"), "to": to.get("name"),
                    "category": (to.get("statusCategory") or {}).get("key")})
    return out


# --------------------------------------------------------------------------
# diff


def norm_text(text) -> str:
    text = str(text or "").replace("\r\n", "\n")
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", text)  # markdown escapes
    text = re.sub(r"^(\s*)[*+]\s", r"\1- ", text, flags=re.MULTILINE)      # bullet markers
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)                # trailing spaces / hard breaks
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def custom_matches(fexp: dict, actual) -> bool:
    kind = fexp["kind"]
    if actual is None:
        return False
    if kind == "number":
        try:
            return float(actual) == float(fexp["value"])
        except (TypeError, ValueError):
            return False
    if kind == "select":
        jira = fexp["jira"]
        if isinstance(actual, list):
            actual = actual[0] if actual else None
        if isinstance(actual, dict):
            if "id" in jira:
                return str(actual.get("id")) == jira["id"]
            return actual.get("value") == jira.get("value") or actual.get("name") == jira.get("value")
        return str(actual) in (jira.get("id"), jira.get("value"), str(fexp["value"]))
    if kind == "user":
        aid = actual.get("accountId") if isinstance(actual, dict) else actual
        return aid == fexp["jira"]["accountId"]
    if kind == "date":
        return str(actual)[:10] == fexp["jira"]
    if isinstance(actual, dict):  # an object field set by id, such as Team, reads back as an object
        return norm_text(fexp["value"]) in {norm_text(actual.get(k)) for k in ("id", "value", "name") if actual.get(k)}
    return norm_text(actual) == norm_text(fexp["value"])


def show(value):
    if isinstance(value, dict):
        return value.get("value") or value.get("name") or value.get("id") or value
    return value


def diff(expected: dict, actual: dict) -> list[dict]:
    rows = []

    def row(name, exp, act, ok, repair=None):
        rows.append({"name": name, "expected": exp, "actual": act, "ok": bool(ok),
                     "_repair": repair})

    missing = "(not returned by the read-back)"
    if expected.get("title"):
        act = actual.get("summary", missing)
        row("title", expected["title"], act, act != missing and act.strip() == expected["title"],
            ("summary", expected["title"]))
    if expected.get("body"):
        act = actual.get("description", missing)
        row("description", "(body as built)", "(matches)" if act != missing and
            norm_text(act) == norm_text(expected["body"]) else "(differs)" if act != missing else missing,
            act != missing and norm_text(act) == norm_text(expected["body"]),
            ("description", expected["body"]))
    if expected.get("type"):
        act = actual.get("issuetype", missing)
        row("type", expected["type"], act, act == expected["type"])
    if expected.get("priority"):
        act = actual.get("priority", missing)
        row("priority", expected["priority"], act, act == expected["priority"],
            ("priority", {"name": expected["priority"]}))
    if expected.get("labels"):
        act = actual.get("labels", missing)
        row("labels", sorted(expected["labels"]), sorted(act) if act != missing else act,
            act != missing and set(act) == set(expected["labels"]), ("labels", expected["labels"]))
    if expected.get("parent"):
        act = actual.get("parent", missing)
        row("parent", expected["parent"], act, act == expected["parent"],
            ("parent", {"key": expected["parent"]}))
    custom = actual.get("custom", {})
    for key, fexp in expected.get("fields", {}).items():
        act = custom.get(fexp["id"], missing)
        ok = act is not missing and act != missing and custom_matches(fexp, act)
        row(key, fexp["value"], show(act) if act is not missing else missing, ok,
            (fexp["id"], fexp["jira"]))
    for key, guard in expected.get("unset_guarded", {}).items():
        act = custom.get(guard["id"], None)
        shown = show(act)
        bad = act is not None and (str(shown) in guard["confirm_values"] or
                                   (isinstance(act, dict) and str(act.get("id")) in guard["option_ids"]))
        row(key, f"not {' or '.join(guard['confirm_values'])} (unconfirmed)",
            shown if act is not None else "unset", not bad, (guard["id"], None))
    actual_links = actual.get("links")
    for link in expected.get("links", []):
        name = f"link {link['kind']} {link['direction']} {link['target']}"
        if actual_links is None:
            row(name, "present", missing, False)
            continue
        found = any(a["name"] == link["name"] and a["direction"] == link["direction"]
                    and a["target"] == link["target"] for a in actual_links)
        row(name, "present", "present" if found else "absent", found)
    return rows


def public_rows(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


# --------------------------------------------------------------------------
# the write driver (create, set-fields, link, comment all end here)


def load_run(run: Path) -> tuple[dict, dict]:
    payload_path = run / "payload.json"
    if not payload_path.exists():
        raise Stop(EXIT_INVALID, {"status": "INVALID", "message": f"no payload.json in {run}; run build first"})
    payload = load_json(payload_path)
    payload["_path"] = str(payload_path)
    state_path = run / "state.json"
    state = load_json(state_path) if state_path.exists() else {}
    return payload, state


def save_state(run: Path, state: dict) -> None:
    (run / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def drive(run: Path, confirm: bool) -> dict:
    payload, state = load_run(run)
    exp = payload["expected"]
    key = state.get("key") or payload.get("key")

    def need_confirm(step):
        if not confirm:
            raise Stop(EXIT_INVALID, {"status": "INVALID", "message":
                                      f"refusing to {step} without --confirm; nothing was sent"})

    # 1. the write itself
    if payload.get("write") == "create" and not key:
        if state.get("create_unknown"):
            return unknown_create(run, payload)
        result_file = result_path(run, "create")
        if not result_file.exists():
            need_confirm("create the issue")
            if not payload["env"].get("writes"):
                raise Stop(EXIT_DENIED, denied_body(payload, "read-only server"))
            call = create_spec(run, payload)
            write_guard.issue_token(call)
            raise Relay([call])
        try:
            data = read_result(run, "create", payload)
        except Stop as stop:
            if stop.code == EXIT_TRACKER and re.search(r"time(d)? ?out|lost|unknown|empty result",
                                                       stop.body["message"], re.IGNORECASE):
                state["create_unknown"] = True
                save_state(run, state)
                return unknown_create(run, payload)
            raise
        key = find_key(data)
        if not key:
            state["create_unknown"] = True
            save_state(run, state)
            return unknown_create(run, payload)
        state.update({"key": key, "created_at": result_file.stat().st_mtime})
        save_state(run, state)
    elif payload.get("write") == "edit" and not state.get("edited"):
        if not result_path(run, "edit").exists():
            need_confirm("edit the issue")
            raise Relay([edit_spec(run, payload, key, payload["edit_fields"], "edit")])
        read_result(run, "edit", payload, key)
        state.update({"edited": True, "created_at": result_path(run, "edit").stat().st_mtime})
        save_state(run, state)

    # 2. links: the first one, read back to confirm direction, then the rest
    links = exp.get("links", [])
    for i, link in enumerate(links, start=1):
        name = f"link-{i}"
        if not result_path(run, name).exists():
            need_confirm("create links")
            if i == 1:
                raise Relay([link_spec(run, payload, key, link, name)])
            raise Relay([link_spec(run, payload, key, lk, f"link-{j}")
                         for j, lk in enumerate(links, start=1) if j >= i])
        read_result(run, name, payload, key)
        if i == 1 and not state.get("link_checked"):
            check = "link-1-check"
            if not result_path(run, check).exists():
                raise Relay([spec(run, check, tool(payload, "get"),
                                  {"cloudId": payload["cloudId"], "issueIdOrKey": key,
                                   "view": "evidence"})])
            seen = normalize_issue(read_result(run, check, payload, key)).get("links") or []
            if not any(a["name"] == link["name"] and a["direction"] == link["direction"]
                       and a["target"] == link["target"] for a in seen):
                raise Stop(EXIT_TRACKER, {"status": "FAILED", "key": key, "message":
                                          f"The first link did not land as {link['kind']} "
                                          f"{link['direction']} {link['target']}. Links cannot be "
                                          "deleted from this session: fix it by hand in Jira, then "
                                          "create the remaining links."})
            state["link_checked"] = True
            save_state(run, state)

    # 3. the comment (the estimate attribution, or an explicit one)
    if payload.get("comment") and not state.get("commented"):
        if not result_path(run, "comment").exists():
            need_confirm("add the comment")
            raise Relay([comment_spec(run, payload, key, payload["comment"])])
        read_result(run, "comment", payload, key)
        state["commented"] = True
        save_state(run, state)
    if payload.get("comment_readback"):
        return check_comment(run, payload, state, key)

    # 4. read back (after any automation-overwrite wait), diff, repair once
    if not any(exp.get(k) for k in ("title", "body", "type", "priority", "labels", "parent",
                                    "fields", "unset_guarded", "links")):
        return result_body("VERIFIED", payload, key, [], "Done; no field to read back.")
    rows = read_back_and_diff(run, payload, state, key, "")
    if all(r["ok"] for r in rows):
        return result_body("VERIFIED", payload, key, rows, "Every field landed as built.")
    fix = {r["_repair"][0]: r["_repair"][1] for r in rows if not r["ok"] and r["_repair"]}
    if fix and not result_path(run, "repair").exists():
        need_confirm("repair the issue")
        raise Relay([edit_spec(run, payload, key, fix, "repair")])
    if fix:
        read_result(run, "repair", payload, key)
        rows = read_back_and_diff(run, payload, state, key, "-2", wait=False)
        if all(r["ok"] for r in rows):
            return result_body("REPAIRED", payload, key, rows, "Fixed after one repair.")
    bad = ", ".join(r["name"] for r in rows if not r["ok"])
    raise Stop(EXIT_TRACKER, result_body("FAILED", payload, key, rows,
                                         f"Still wrong after one repair: {bad}." if fix else
                                         f"Wrong and not repairable by an edit: {bad}."))


def check_comment(run: Path, payload: dict, state: dict, key: str) -> dict:
    """Read the posted comment back from the issue and compare its body.

    The add call's own response is not trusted: the comment is found again
    on the issue, by the id the add call returned, else by its text.
    """
    text = payload["comment"]
    added = unwrap(read_result(run, "comment", payload, key))
    cid = None
    if isinstance(added, dict):
        found = added.get("commentId") or added.get("id")
        cid = str(found) if found is not None else None
    name = "comment-check"
    if not result_path(run, name).exists():
        raise Relay([comments_spec(run, payload, key, name, newest_first=True)])
    comments, _ = parse_comments(read_result(run, name, payload, key))
    mine = [c for c in comments if cid and c["id"] == cid] or \
           [c for c in comments if norm_text(c["body"]) == norm_text(text)]
    url = f"{payload['site_url'].rstrip('/')}/browse/{key}" if payload.get("site_url") else None
    if not mine:
        raise Stop(EXIT_TRACKER, {"status": "FAILED", "key": key, "url": url, "comment_id": cid,
                                  "message": "The comment call returned, but the comment was not "
                                             "found on the issue when read back. Check the issue "
                                             "before posting again."})
    if norm_text(mine[0]["body"]) != norm_text(text):
        raise Stop(EXIT_TRACKER, {"status": "FAILED", "key": key, "url": url, "comment_id": mine[0]["id"],
                                  "expected": text, "actual": mine[0]["body"],
                                  "message": "The comment landed, but its text reads back differently."})
    state["comment_checked"] = True
    save_state(run, state)
    return {"status": "VERIFIED", "key": key, "url": url, "comment_id": mine[0]["id"],
            "message": "Comment added and read back from the issue."}


def read_back_and_diff(run: Path, payload: dict, state: dict, key: str, suffix: str,
                       wait: bool = True) -> list[dict]:
    calls = readback_specs(run, payload, key, suffix)
    pending = [c for c in calls if not Path(c["result_file"]).exists()]
    if pending:
        if wait and payload.get("repair_wait") and state.get("created_at"):
            remaining = state["created_at"] + payload["repair_wait"] - time.time()
            if remaining > 0:
                time.sleep(remaining)
        raise Relay(pending)
    reads = [normalize_issue(read_result(run, Path(c["result_file"]).stem, payload, key))
             for c in calls]
    return diff(payload["expected"], merge_reads(reads))


def result_body(status: str, payload: dict, key: str, rows: list[dict], message: str) -> dict:
    url = f"{payload['site_url'].rstrip('/')}/browse/{key}" if payload.get("site_url") else None
    return {"status": status, "key": key, "url": url, "fields": public_rows(rows), "message": message}


def unknown_create(run: Path, payload: dict) -> dict:
    """A create whose outcome is unknown: look for the exact title before anything else."""
    title = payload["expected"]["title"]
    name = "create-unknown-search"
    jql = f'project = "{payload["project"]}" AND summary ~ "\\"{jql_escape(title)}\\"" ORDER BY created DESC'
    if not result_path(run, name).exists():
        raise Relay([search_spec(run, payload, name, jql)])
    hits = search_hits(read_result(run, name, payload))
    exact = [h for h in hits if h["summary"].strip() == title]
    if exact:
        msg = (f"The create's outcome was unknown, and {exact[0]['key']} has this exact title. "
               "Check it before doing anything else; do not post again.")
    else:
        msg = ("The create's outcome was unknown, and no issue with this exact title exists. "
               f"Post again only if the user says yes: delete {result_path(run, 'create')}, "
               f"{result_path(run, name)} and state.json, then re-run with --confirm.")
    raise Stop(EXIT_TRACKER, {"status": "FAILED", "key": exact[0]["key"] if exact else None,
                              "hits": exact, "message": msg})


# --------------------------------------------------------------------------
# duplicates and fetch


def jql_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


STOP_WORDS = frozenset("""
    about above after again also another because been before being between both
    could does doing done each else even every from have having here into just
    like make many more most much must only other over same should since some
    such than that their them then there these they this those through under
    until upon very want were what when where which while will with within
    without would your
""".split())


def search_words(title: str) -> list[str]:
    """Title words longer than three letters that are not common stop words,
    in order and without repeats, at most eight."""
    words, seen = [], set()
    for w in re.findall(r"[A-Za-z0-9]+", title):
        low = w.lower()
        if len(w) > 3 and low not in STOP_WORDS and low not in seen:
            seen.add(low)
            words.append(w)
    return words[:8]


def keyword_jql(words: list[str]) -> str:
    """One summary clause per word, joined with OR, so a reworded title still
    finds its ticket; duplicates() ranks the hits by how many words match."""
    return "(" + " OR ".join(f'summary ~ "{jql_escape(w)}"' for w in words) + ")"


def source_jql(source_key: str) -> str:
    return f'(key = {source_key} OR text ~ "{jql_escape(source_key)}")'


def words_matched(words: list[str], summary: str) -> int:
    have = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", summary)}
    return sum(1 for w in words if w.lower() in have)


def search_hits(data) -> list[dict]:
    data = data.get("data", data) if isinstance(data, dict) else data
    issues = data.get("issues", []) if isinstance(data, dict) else []
    hits = []
    for issue in issues:
        f = issue.get("fields") or {}
        hits.append({"key": issue.get("key"), "summary": f.get("summary", ""),
                     "status": (f.get("status") or {}).get("name")})
    return hits


def duplicates(run: Path) -> dict:
    payload, _ = load_run(run)
    exp = payload["expected"]
    words = search_words(exp["title"])
    source_key = payload.get("source_key")
    plan = []
    if exp.get("parent") and words:
        plan.append(("dup-children", f'parent = {exp["parent"]} AND {keyword_jql(words)}'))
    if source_key:
        plan.append(("dup-source", f'project = "{payload["project"]}" AND {source_jql(source_key)}'))
    if words:
        plan.append(("dup-keyword",
                     f'project = "{payload["project"]}" AND {keyword_jql(words)} ORDER BY created DESC'))
    pending = [search_spec(run, payload, n, q) for n, q in plan if not result_path(run, n).exists()]
    if pending:
        raise Relay(pending)
    seen, hits = set(), []
    for name, _ in plan:
        for hit in search_hits(read_result(run, name, payload)):
            if hit["key"] in seen:
                continue
            seen.add(hit["key"])
            hit["match"] = {"dup-children": "child", "dup-source": "source"}.get(name, "keyword")
            hit["words_matched"] = words_matched(words, hit["summary"])
            hit["exact_title"] = hit["summary"].strip().lower() == exp["title"].lower()
            hits.append(hit)
    # Source-key hits first, then the most matched words; the sort is stable,
    # so ties keep the order the searches returned them in.
    hits.sort(key=lambda h: (h["match"] != "source", -h["words_matched"]))
    return {"status": "OK", "hits": hits}


def fetch(run: Path, env: dict, site: str, key: str, template: dict | None) -> dict:
    payload = {"env": env, "cloudId": site, "_path": str(run)}
    name = "fetch"
    # An env from an older detect has no comments tool; the issue is still fetched.
    reads_comments = "comments" in env.get("tools", {})
    pending = []
    if not result_path(run, name).exists():
        args = {"cloudId": site, "issueIdOrKey": key, "view": "evidence"}
        pending.append(spec(run, name, tool(payload, "get"), args))
    if reads_comments and not result_path(run, "fetch-comments").exists():
        pending.append(comments_spec(run, payload, key, "fetch-comments"))
    if pending:
        raise Relay(pending)
    raw = normalize_issue(read_result(run, name, payload, key))
    thread, thread_note = [], None
    if not reads_comments:
        thread_note = "comments were not read: run detect again, this env has no comments tool"
    else:
        try:
            thread, total = parse_comments(read_result(run, "fetch-comments", payload, key))
            if total > len(thread):
                thread_note = f"only the first {len(thread)} of {total} comments were read"
        except Stop as stop:
            thread_note = f"comments were not read: {stop.body.get('message', 'the call failed')}"
    bcfg = (template or {}).get("body", {})
    sections = parse_sections(core.strip_evidence(raw.get("description"))[0], int(bcfg.get("heading_level", 2)))
    ai_section, ai_prompt = core.ai_prompt_of(template or {}, sections)
    fields = {}
    for fkey, fdef in ((template or {}).get("fields") or {}).items():
        if fdef.get("id") in raw.get("custom", {}):
            fields[fkey] = show(raw["custom"][fdef["id"]])
    return {"tracker": "jira", "target": {"site": site, "project": key.split("-")[0]},
            "key": raw.get("key", key), "url": f"{site_url(site).rstrip('/')}/browse/{key}",
            "type": raw.get("issuetype"), "title": raw.get("summary"), "body": raw.get("description"),
            "sections": sections, "labels": raw.get("labels", []), "priority": raw.get("priority"),
            "fields": fields, "parent": raw.get("parent"), "links": raw.get("links", []),
            "state": raw.get("status"), "status_category": raw.get("status_category"),
            "resolution": raw.get("resolution"),
            "thread": [{k: c[k] for k in ("author", "created_at", "body")} for c in thread],
            "thread_note": thread_note,
            "has_ai_prompt": ai_prompt is not None, "ai_prompt": ai_prompt,
            "ai_prompt_section": ai_section}


# --------------------------------------------------------------------------
# transition


def transition(run: Path, confirm: bool) -> dict:
    """Move an issue to the status named in the payload, then read it back.

    Reads the current status and the transitions this user can take now,
    picks the one whose target status has that name (case-insensitive; a
    transition's own name often differs), makes it after --confirm, and
    reads the status again. An issue already there is not moved.
    """
    payload, state = load_run(run)
    key, target = payload["key"], payload["target_status"]
    url = f"{payload['site_url'].rstrip('/')}/browse/{key}" if payload.get("site_url") else None

    def answer(status, message, **extra):
        return {"status": status, "key": key, "url": url, "target_status": target,
                "message": message, **extra}

    if not result_path(run, "transition").exists():
        reads = [status_spec(run, payload, key, "transition-before"),
                 transitions_spec(run, payload, key, "transition-options")]
        pending = [c for c in reads if not Path(c["result_file"]).exists()]
        if pending:
            raise Relay(pending)
        current = normalize_issue(read_result(run, "transition-before", payload)).get("status")
        if (current or "").lower() == target.lower():
            return answer("VERIFIED", f"{key} is already in '{current}'; nothing was changed.",
                          changed=False, from_status=current)
        options = parse_transitions(read_result(run, "transition-options", payload))
        match = [o for o in options if (o["to"] or "").lower() == target.lower()]
        if not match:
            reachable = sorted({o["to"] for o in options if o["to"]})
            raise Stop(EXIT_TRACKER, answer(
                "FAILED", f"No transition from '{current}' leads to '{target}'. Statuses reachable "
                          f"now: {', '.join(reachable) or 'none'}. Nothing was changed.",
                from_status=current, reachable=reachable))
        if not confirm:
            raise Stop(EXIT_INVALID, {"status": "INVALID", "message":
                                      f"refusing to move {key} to '{target}' without --confirm; "
                                      "nothing was sent"})
        state.update({"from_status": current, "transition": match[0]})
        save_state(run, state)
        raise Relay([transition_spec(run, payload, key, match[0]["id"])])
    read_result(run, "transition", payload)
    check = status_spec(run, payload, key, "transition-check")
    if not Path(check["result_file"]).exists():
        raise Relay([check])
    landed = normalize_issue(read_result(run, "transition-check", payload)).get("status")
    if (landed or "").lower() != target.lower():
        raise Stop(EXIT_TRACKER, answer("FAILED", f"The transition was made, but {key} reads back "
                                                  f"as '{landed}'.", from_status=state.get("from_status"),
                                        actual=landed))
    return answer("VERIFIED", f"{key} moved from '{state.get('from_status')}' to '{landed}'.",
                  changed=True, from_status=state.get("from_status"), via=state.get("transition"))


# --------------------------------------------------------------------------
# wait (work-issue --after on a Jira blocker)


def wait(run: Path) -> dict:
    """One check of a blocker per call; the session calls it again on each tick.

    No background process can call the MCP, so the session paces the wait
    itself. Each call relays one status read, then answers WAITING, CLEARED
    (status category done), ABANDONED (done with a resolution such as Won't
    Do: ask before going on) or TIMEOUT once the hours have passed. The
    blocker's status category is the only input; its status name, assignee
    and comments decide nothing.
    """
    payload, state = load_run(run)
    key = payload["key"]
    if "started_at" not in state:
        state["started_at"] = time.time()
        save_state(run, state)
    checks = state.get("checks", 0)
    name = f"wait-{checks + 1}"
    if not result_path(run, name).exists():
        if checks and time.time() - state["started_at"] > payload["hours"] * 3600:
            return {"status": "TIMEOUT", "key": key, "checks": checks,
                    "message": f"{key} was still not done after {payload['hours']}h."}
        raise Relay([status_spec(run, payload, key, name)])
    state["checks"] = checks + 1
    try:
        read = normalize_issue(read_result(run, name, payload))
    except Stop as stop:
        if stop.code != EXIT_TRACKER or state.get("failures", 0) >= 2:
            raise
        state["failures"] = state.get("failures", 0) + 1
        save_state(run, state)
        return {"status": "WAITING", "key": key, "checks": state["checks"],
                "message": f"This check failed and is retried on the next tick: {stop.body['message']}"}
    state["failures"] = 0
    save_state(run, state)
    current, category, resolution = read.get("status"), read.get("status_category"), read.get("resolution")
    body = {"key": key, "state": current, "status_category": category, "resolution": resolution,
            "checks": state["checks"]}
    if category is None:
        raise Stop(EXIT_TRACKER, {"status": "FAILED", **body, "message":
                                  f"The status category of {key} could not be read, so the wait "
                                  "cannot tell when it is done."})
    if category != "done":
        return {"status": "WAITING", **body, "message": f"{key} is '{current}', not done yet."}
    if resolution and ABANDONED_RESOLUTION.search(resolution):
        return {"status": "ABANDONED", **body,
                "message": f"{key} was closed as '{resolution}', not finished."}
    return {"status": "CLEARED", **body, "message": f"{key} is done ('{current}')."}


# --------------------------------------------------------------------------
# CLI


def write_payload(run: Path, payload: dict) -> None:
    run.mkdir(parents=True, exist_ok=True)
    (run / "results").mkdir(exist_ok=True)
    (run / "payload.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_detect(args) -> tuple[int, dict]:
    names = load_json(args.tools) if args.tools != "-" else json.load(sys.stdin)
    if isinstance(names, dict):
        names = names.get("tools", [])
    result = detect(names)
    return (EXIT_OK if result["status"] == "ok" else EXIT_UNREACHABLE), result


def cmd_build(args) -> tuple[int, dict]:
    ticket = load_json(args.ticket)
    template = load_template(args.template)
    env = load_json(args.env)
    payload, errors, warnings = build(ticket, template, env)
    if write_guard.guard_enabled(Path.cwd()):
        errors += write_guard.pipeline_gate(Path(args.ticket).resolve().parent, template)
    if errors:
        return EXIT_INVALID, {"status": "INVALID", "errors": errors, "warnings": warnings,
                              "message": f"{len(errors)} validation error(s); nothing was sent"}
    run = Path(args.run)
    write_payload(run, payload)
    return EXIT_OK, {"status": "BUILT", "payload": str(run / "payload.json"), "warnings": warnings,
                     "create": create_spec(run, payload)}


def cmd_set_fields(args) -> tuple[int, dict]:
    """Prepare an edit run from {"fields": {...}, "confirmations": {...}} and drive it."""
    run = Path(args.run)
    if not (run / "payload.json").exists():
        template = load_template(args.template)
        env = load_json(args.env)
        req = load_json(args.fields)
        draft = {"tracker": "jira", "target": {"site": args.site, "project": args.key.split("-")[0]},
                 "title": "-", "type": "-", "fields": req.get("fields", {}),
                 "draft_notes": {"confirmations": req.get("confirmations", {})}}
        trimmed = {"fields": template.get("fields", {}), "links": template.get("links", {})}
        payload, errors, _ = build(draft, trimmed, env)
        if errors:
            return EXIT_INVALID, {"status": "INVALID", "errors": errors,
                                  "message": f"{len(errors)} validation error(s); nothing was sent"}
        exp = payload["expected"]
        exp.update({"title": "", "type": None, "body": "", "labels": [], "priority": None,
                    "parent": None, "links": []})
        exp["unset_guarded"] = {}
        payload.update({"write": "edit", "key": args.key, "comment": None,
                        "edit_fields": payload["additional_fields"]})
        write_payload(run, payload)
    return EXIT_OK, drive(run, args.confirm)


def cmd_update(args) -> tuple[int, dict]:
    """Rewrite an existing issue from a full draft, then read it back and diff.

    Title, description, priority, labels, parent and template fields are
    edited; the issue type and existing links are left alone (an edit cannot
    change the type, and links already made are not re-created). The
    estimate comment is added as on create. Added in S7, when the maintainer
    asked for the trial tickets to be re-run in place.
    """
    run = Path(args.run)
    if not (run / "payload.json").exists():
        ticket = load_json(args.ticket)
        payload, errors, warnings = build(ticket, load_template(args.template), load_json(args.env))
        if errors:
            return EXIT_INVALID, {"status": "INVALID", "errors": errors, "warnings": warnings,
                                  "message": f"{len(errors)} validation error(s); nothing was sent"}
        exp = payload["expected"]
        fields = {"summary": exp["title"], "description": exp["body"], **payload["additional_fields"]}
        if exp["priority"]:
            fields["priority"] = {"name": exp["priority"]}
        if exp["labels"]:
            fields["labels"] = exp["labels"]
        if exp["parent"]:
            fields["parent"] = {"key": exp["parent"]}
        exp["links"] = []
        payload.update({"write": "edit", "key": args.key, "edit_fields": fields})
        if args.no_comment:
            payload["comment"] = None
        write_payload(run, payload)
    return EXIT_OK, drive(run, args.confirm)


def cmd_link(args) -> tuple[int, dict]:
    run = Path(args.run)
    if not (run / "payload.json").exists():
        template = load_template(args.template)
        env = load_json(args.env)
        req = load_json(args.links)
        draft = {"target": {"site": args.site, "project": args.key.split("-")[0]},
                 "title": "-", "type": "-", "links": req.get("links", []),
                 "parent": req.get("parent")}
        payload, errors, _ = build(draft, {"links": template.get("links", {})}, env)
        if errors:
            return EXIT_INVALID, {"status": "INVALID", "errors": errors,
                                  "message": f"{len(errors)} validation error(s); nothing was sent"}
        exp = payload["expected"]
        parent = exp["parent"]
        exp.update({"title": "", "type": None, "body": "", "labels": [], "priority": None,
                    "fields": {}, "unset_guarded": {}})
        payload.update({"write": "edit" if parent else None, "key": args.key, "comment": None,
                        "edit_fields": {"parent": {"key": parent}} if parent else {}})
        write_payload(run, payload)
    return EXIT_OK, drive(run, args.confirm)


def cmd_comment(args) -> tuple[int, dict]:
    run = Path(args.run)
    if not (run / "payload.json").exists():
        env = load_json(args.env)
        text = Path(args.body).read_text(encoding="utf-8") if args.body else ""
        if not text.strip():
            return EXIT_INVALID, {"status": "INVALID", "message": "comment body is empty"}
        payload = {"tracker": "jira", "env": env, "cloudId": args.site, "site_url": site_url(args.site),
                   "project": args.key.split("-")[0], "key": args.key, "write": None,
                   "comment": text, "comment_readback": True, "additional_fields": {}, "repair_wait": 0,
                   "expected": {"title": "", "type": None, "body": "", "labels": [], "priority": None,
                                "parent": None, "fields": {}, "unset_guarded": {}, "links": []}}
        write_payload(run, payload)
    return EXIT_OK, drive(run, args.confirm)


def cmd_transition(args) -> tuple[int, dict]:
    run = Path(args.run)
    if not (run / "payload.json").exists():
        if not args.status.strip():
            return EXIT_INVALID, {"status": "INVALID", "message": "--status is empty"}
        write_payload(run, {"tracker": "jira", "env": load_json(args.env), "cloudId": args.site,
                            "site_url": site_url(args.site), "key": args.key,
                            "target_status": args.status.strip()})
    return EXIT_OK, transition(run, args.confirm)


def cmd_wait(args) -> tuple[int, dict]:
    run = Path(args.run)
    if not (run / "payload.json").exists():
        write_payload(run, {"tracker": "jira", "env": load_json(args.env), "cloudId": args.site,
                            "site_url": site_url(args.site), "key": args.key, "hours": args.hours})
    return EXIT_OK, wait(run)


def cmd_readback(args) -> tuple[int, dict]:
    run = Path(args.run)
    payload, state = load_run(run)
    key = state.get("key") or payload.get("key")
    calls = readback_specs(run, payload, key, args.suffix)
    pending = [c for c in calls if not Path(c["result_file"]).exists()]
    if pending:
        raise Relay(pending)
    reads = [normalize_issue(read_result(run, Path(c["result_file"]).stem, payload, key)) for c in calls]
    return EXIT_OK, {"status": "OK", "key": key, "read": merge_reads(reads)}


def cmd_diff(args) -> tuple[int, dict]:
    run = Path(args.run)
    payload, state = load_run(run)
    key = state.get("key") or payload.get("key")
    calls = readback_specs(run, payload, key, args.suffix)
    if any(not Path(c["result_file"]).exists() for c in calls):
        return EXIT_INVALID, {"status": "INVALID", "message": "run readback first"}
    reads = [normalize_issue(read_result(run, Path(c["result_file"]).stem, payload, key)) for c in calls]
    rows = diff(payload["expected"], merge_reads(reads))
    status = "VERIFIED" if all(r["ok"] for r in rows) else "FAILED"
    return (EXIT_OK if status == "VERIFIED" else EXIT_TRACKER), result_body(
        status, payload, key, rows, "Every field matches." if status == "VERIFIED" else
        "Mismatched: " + ", ".join(r["name"] for r in rows if not r["ok"]))


def cmd_create(args) -> tuple[int, dict]:
    return EXIT_OK, drive(Path(args.run), args.confirm)


def cmd_duplicates(args) -> tuple[int, dict]:
    return EXIT_OK, duplicates(Path(args.run))


def cmd_fetch(args) -> tuple[int, dict]:
    template = load_template(args.template) if args.template else None
    run = Path(args.run)
    (run / "results").mkdir(parents=True, exist_ok=True)
    return EXIT_OK, fetch(run, load_json(args.env), args.site, args.key, template)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="op", required=True)

    s = sub.add_parser("detect", help="find the Atlassian MCP tool prefix and its v2 tools")
    s.add_argument("--tools", required=True, help="JSON list of this session's tool names, or - for stdin")
    s.set_defaults(func=cmd_detect)

    s = sub.add_parser("build", help="validate a draft and write the run's payload")
    s.add_argument("--ticket", required=True)
    s.add_argument("--template", required=True, help="ticket_template.py resolve output (or a bare resolved template)")
    s.add_argument("--env", required=True, help="detect's output")
    s.add_argument("--run", required=True, help="run directory")
    s.set_defaults(func=cmd_build)

    for name, func in (("duplicates", cmd_duplicates), ("create", cmd_create),
                       ("readback", cmd_readback), ("diff", cmd_diff), ("repair", cmd_create)):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        if name in ("create", "repair"):
            s.add_argument("--confirm", action="store_true")
        if name in ("readback", "diff"):
            s.add_argument("--suffix", default="")
        s.set_defaults(func=func)

    for name, func, extra in (("set-fields", cmd_set_fields, "--fields"),
                              ("link", cmd_link, "--links"),
                              ("comment", cmd_comment, "--body")):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--key", required=True)
        s.add_argument("--site", required=True)
        s.add_argument("--env", required=True)
        if name != "comment":
            s.add_argument("--template", required=True)
        s.add_argument(extra, required=True)
        s.add_argument("--confirm", action="store_true")
        s.set_defaults(func=func)

    s = sub.add_parser("transition", help="move an issue to a named status, then read it back")
    s.add_argument("--run", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--site", required=True)
    s.add_argument("--env", required=True)
    s.add_argument("--status", required=True, help="the target status name, as the board shows it")
    s.add_argument("--confirm", action="store_true")
    s.set_defaults(func=cmd_transition)

    s = sub.add_parser("wait", help="check once whether a blocker is done; call again on each tick")
    s.add_argument("--run", required=True, help="one run directory for the whole wait")
    s.add_argument("--key", required=True, help="the blocker")
    s.add_argument("--site", required=True)
    s.add_argument("--env", required=True)
    s.add_argument("--hours", type=float, default=WAIT_HOURS, help="give up after this long")
    s.set_defaults(func=cmd_wait)

    s = sub.add_parser("update", help="rewrite an existing issue from a full draft, then verify it")
    s.add_argument("--run", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--ticket", required=True)
    s.add_argument("--template", required=True)
    s.add_argument("--env", required=True)
    s.add_argument("--no-comment", action="store_true",
                   help="skip the estimate comment, when the points are unchanged since it was posted")
    s.add_argument("--confirm", action="store_true")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("fetch")
    s.add_argument("--run", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--site", required=True)
    s.add_argument("--env", required=True)
    s.add_argument("--template")
    s.set_defaults(func=cmd_fetch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        code, body = args.func(args)
    except Relay as relay:
        code, body = EXIT_OK, {"status": "RELAY", "calls": relay.calls,
                               "message": "Make each call unchanged, save each raw result to its "
                                          "result_file, then run the same command again."}
    except Stop as stop:
        code, body = stop.code, stop.body
    except (OSError, json.JSONDecodeError) as exc:
        code, body = EXIT_INVALID, {"status": "INVALID", "message": f"{type(exc).__name__}: {exc}"}
    sys.stdout.write(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
