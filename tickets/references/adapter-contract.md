# Tracker adapter contract

One adapter per tracker (`github`, `jira`). Each is a Python script in
`tickets/scripts/`, standard library only, shared by `create-issue` and
`work-issue`. Both skills talk to a tracker **only** through its adapter.
This file is the contract the adapters implement and the skills rely on.

## Why a script sits between the model and the tracker

Posting is deterministic. The pipeline is fixed:

1. A script builds the payload and validates it.
2. The model passes the payload to the tracker unchanged.
3. A script reads the ticket back and diffs every field.
4. The script repairs once if needed.

The model never composes a tracker call by hand. It also never retypes a
field value that a script produced.

## Two transports

| Transport | Used by | Who performs the call |
|---|---|---|
| `direct` | GitHub | The adapter calls `gh api` itself, with the body sent as UTF-8 on stdin. |
| `relay` | Jira | The adapter prints a **call spec**. The model makes exactly that tool call and saves the raw result to a file. The adapter reads the file. |

A Jira call has to go through MCP because only the model can call an MCP
tool. The relay keeps it deterministic. A call spec is:

```json
{"tool": "<full tool name>", "arguments": { ... }, "result_file": "<path>"}
```

The model passes `arguments` verbatim. When a relayed call fails, the model
writes the error text to `result_file` the same way, so the adapter can
classify it.

## Shared data shapes (JSON, UTF-8)

**Ticket** is the normalized form that both directions use:

```json
{
  "tracker": "github | jira",
  "target": {"repo": "owner/name"} ,
  "key": "existing key or number, absent before create",
  "url": "...",
  "type": "Story",
  "title": "...",
  "body": "markdown",
  "sections": {"Context": "...", "Acceptance Criteria": "..."},
  "labels": ["..."],
  "priority": "Medium",
  "estimate": {"kind": "points", "value": 3},
  "fields": {"<template field key>": "<value name>"},
  "parent": "key",
  "links": [{"kind": "blocks", "direction": "outward", "target": "key"}],
  "state": "open",
  "assignee": null
}
```

For Jira, `target` is `{"site": "...", "project": "KEY"}`.

A **draft** is a Ticket plus an optional `draft_notes` object, which is never
rendered or posted:

```json
"draft_notes": {
  "confirmations": {"<field key>": "<value name the user explicitly chose>"},
  "waivers": ["<check>: <why the user waived it>"],
  "investigated": true,
  "provenance": {"tool": "...", "session": "..."}
}
```

`confirmations` is where `build` looks for the record that a guarded value
was confirmed. The tracker-independent checks and the body rendering live in
`scripts/ticket_core.py` (`check`, `render`); an adapter's `build` calls them
rather than re-implementing them.

A link's `direction` is from this ticket's side: `outward` means "this
ticket blocks the target", `inward` means "the target blocks this ticket".

**Result** comes from every write operation:

```json
{"status": "VERIFIED | REPAIRED | FAILED", "key": "...", "url": "...",
 "fields": [{"name": "...", "expected": "...", "actual": "...", "ok": true}],
 "message": "one line for the user"}
```

## Operations

Each one is a subcommand: `python scripts/<tracker>_adapter.py <op> ...`.
Input comes as a JSON file path or on stdin; output goes to stdout as JSON.

| Op | Writes? | What it does |
|---|---|---|
| `detect` | no | Checks what this session can reach. GitHub: `gh auth status`, plus the repo's visibility (a public repo raises the publication warning). Jira: takes the list of tool names the session has, and returns the MCP generation (v1 or v2), the tool-name prefix and the call shapes to use. With no Atlassian tools present, it returns `not-configured`. |
| `build` | no | Takes a draft Ticket and the resolved template, and returns the create payload: a call spec for relay, or the exact `gh api` input for direct. Returns every validation error at once: a missing required section, a value outside a scale, an unknown field, or a guarded value with no recorded confirmation. |
| `duplicates` | no | Returns a search for likely duplicates (same title, same source thread, same external reference). Jira searches children first, then keywords. The skill shows the hits and asks before creating. |
| `create` | **yes** | Posts the built payload. It needs `--confirm`, which the skill passes only after the user's yes. |
| `set-fields` | **yes** | Sets fields that the create call cannot carry: GitHub Projects board fields, or Jira fields that are not on the create screen. |
| `link` | **yes** | Creates links and the parent. It creates the first link, reads it back to confirm the direction, and only then creates the rest. |
| `comment` | **yes** | Adds a comment, such as the estimate attribution comment, then finds it on the ticket again and compares its text. |
| `fetch` | no | Reads one ticket into a Ticket, sections parsed, with its comments as `thread`, for `work-issue`. It also reports whether an `ai_prompt` section exists. |
| `transition` | **yes** | Jira only. Moves a ticket to a named status through a workflow transition that leads there, then reads the status back. GitHub's status lives on the board and goes through `set-fields`. |
| `wait` | no | Jira only. One check of whether a blocking ticket is done, for `work-issue --after`; the session calls it again on each tick. GitHub's wait is a background `gh` loop in the skill. |
| `readback` | no | Like `fetch`, but asks for every field the payload set, **by explicit field id**. Create and edit responses do not echo custom fields, so a write is never confirmed from its own response. |
| `diff` | no | Compares the expected Ticket with the read-back one and returns the per-field list in the Result shape. Whitespace and markdown are normalized; any other difference is reported, not silently accepted. |
| `repair` | **yes** | Makes one corrective write for the mismatched fields, then runs `readback` and `diff` again. Fields with `repair.after_seconds` (automation overwrite) are read only after that wait. There is **one** repair, never a loop. A mismatch that is still there afterwards is `FAILED`, and the message names each field. |

Every write op ends with a read-back, `readback` + `diff` (Jira's
`comment` and `transition` read back the comment or status they wrote), and returns `VERIFIED`
(matched first time), `REPAIRED` (matched after the one repair) or `FAILED`.

## Safety rules every adapter follows

- **No write without `--confirm`.** The skill holds the gate. The flag is
  the record that the gate was passed.
- **Never retry a create blindly.** If a create's outcome is unknown (a
  timeout, or a lost result), run `duplicates` for the exact title before
  anything else. Post again only if it finds nothing and the user says yes.
- **Guarded fields:** `build` rejects a guarded value (`confirm_values`)
  unless the draft records the user's explicit answer for that field. A
  missing answer means unset, never the guarded value.
- **Encoding:** bodies are UTF-8. GitHub bodies go on stdin
  (`gh api --input -`), never through `--body-file`, `-F` or `@path`, which
  double-encode on Windows.
- **No secrets on disk or in output.** Adapters never read or print tokens.
  GitHub uses `gh`'s own login and Jira uses the MCP session's OAuth.

## When writes are denied

A write can be denied by a permission rule, a hook, a managed policy, a
read-only MCP server, or a missing scope. When that happens, the adapter
exits with code `3` and this message, filled in:

> Writes to <tracker> are blocked in this session (<what blocked it: hook,
> policy, permission, read-only server>). Nothing was posted. The validated
> payload is saved at <path>. Post it from a session where writes are
> allowed, or paste it in by hand.

Then the skill stops. **It never falls back** to curl, to the REST API, or
to a different tool or server. A denial is an answer, not an obstacle.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (for writes: `VERIFIED` or `REPAIRED`) |
| 1 | Validation error in the input or the template; nothing was sent |
| 2 | Tracker error (a call failed or returned something unexpected), or `FAILED` after the repair |
| 3 | Write denied (message above) |
| 4 | Tracker not reachable or not configured (`detect`) |

## Jira specifics (S3)

- **Generations:**
  - v1 (`/v1/mcp`): `createJiraIssue` takes `issueTypeName`,
    `assignee_account_id` and `additional_fields` (snake_case).
  - v2 (`/v2/mcp`): it takes `issueType` and `assignee`, and adds
    `discover` and `executeRead` / `executeWrite` / `executeDestructive`.
  - `detect` decides which from the tool list, never from a guess.
- **Prefix:** at least three tool-name prefixes exist in the wild. `detect`
  finds the one present at runtime and never hard-codes one.
- **Body:** markdown with `contentFormat: "markdown"`, which applies only
  to `description`. Other rich-text fields need ADF and are out of scope
  unless a template declares one.
- **No REST path in this plan.** The contract leaves room for a REST
  backend: a third transport would reuse every op above, but none is built.
- **Not supported:** attachment upload (the OAuth token cannot do it).

### As built (S3): `scripts/jira_adapter.py`

- **The relay loop.** Every op works over a run directory (`--run`), which
  holds `payload.json`, `state.json` and `results/`. While an op needs
  calls made, it prints `{"status": "RELAY", "calls": [<call spec>...]}`
  with exit 0. The skill makes each call unchanged, writes each raw result
  (or the error text) to its `result_file`, and runs **the same command
  again**. Any other `status` is the op's answer. Re-running is always safe:
  an op resumes from the result files already present, and never re-emits
  a create whose result file exists.
- **`create` runs the whole write:** create, then the first link, a
  read-back of that link's direction, the remaining links, the estimate
  comment, the read-back (after the template's `repair.after_seconds`
  wait), the diff, and at most one repair edit. `repair` is the same driver.
  `set-fields`, `link` and `comment` prepare their own run and use it too.
- **`update`** (added in S7) rewrites an existing issue from a full draft:
  title, description, priority, labels, parent and template fields in one
  edit, then the estimate comment (`--no-comment` skips it when the points
  have not changed since it was posted) and the same read-back and diff. It never
  changes the issue type and never re-creates links. Jira only; GitHub has
  no equivalent yet.
- **`fetch`** (comments added for issue 196) also reads the comments into
  `thread`, oldest first: `listJiraIssueComments` on v2, the `comment`
  field on v1. When they were cut off or could not be read, `thread_note`
  says so and the ticket is still returned. It also returns
  `status_category` (`new`, `indeterminate` or `done`) and `resolution`.
- **`comment`** finds the posted comment on the ticket again and compares
  its text before it reports `VERIFIED`.
- **`transition`** reads the current status and the transitions open to
  this user, and picks the one whose **target status** has the requested
  name, case-insensitive (a transition's own name often differs). It makes
  that transition only with `--confirm`, then reads the status back. A
  ticket already in that status is not moved (`changed: false`). When no
  transition leads there it exits 2, naming the statuses reachable now.
- **`wait`** makes one status read per call and answers `WAITING`,
  `CLEARED` (status category `done`), `ABANDONED` (done, with a resolution
  such as Won't Do or Duplicate) or `TIMEOUT` (after `--hours`, 24 by
  default, and at least one check). The status category is the only input.
  A failed read is retried on the next two calls before it stops the wait.
  No background process can call the MCP, so the session paces the calls.
- **The template it takes is the resolved one** (`ticket_template.py resolve`
  output, or a bare resolved template). The adapter does not resolve
  layering. Its tracker-independent checks and body rendering are
  `ticket_core.py`'s.
- **Verified live, v2, 2026-10-08:**
  - `getJiraIssue` with explicit `fields` honours custom field ids. They
    come back under `fields.customFields`, keyed by field **name**, each as
    `{"id": ..., "value": ...}`. An empty field has no `value`. A select is
    `{"value": ..., "id": <option id>}`.
  - The same explicit list silently drops `issuetype`, `labels`, `parent`
    and `issuelinks`, with or without `fieldsByKeys`. `executeRead` with
    `responseFields` returns scalars and string arrays (`issuetype.name`,
    `labels`) but not objects (`parent`, `issuelinks`). Only the `evidence`
    view returns parent and links, at roughly 5 KB per issue. So the
    read-back is one call by explicit ids plus one small `responseFields`
    call, and the large evidence call only when a parent or link was set.
  - Issue links go through `executeWrite` with `createJiraIssueLink`,
    which takes the link type **name** (`linkType`), `inwardIssue` and
    `outwardIssue`. "`inwardIssue` Blocks `outwardIssue`".
- **v1 call shapes are not verified live.** They come from skills that pin
  `/v1/mcp`: `issueTypeName`, `additional_fields` for priority, labels and
  parent, `addCommentToJiraIssue`, `createIssueLink`. The S7 trial confirms
  them, or a v1 session reports the first mismatch.
- **Denial classification** is by the error text the model saved: a hook,
  a read-only server, a policy, or a permission/scope refusal gives exit 3
  and the message above. Any other error gives exit 2. A create with an
  unknown outcome (timeout, empty or keyless result) searches for the exact
  title instead of posting again.

## GitHub specifics (S4)

Implemented in `scripts/github_adapter.py`; tests in `tests/`.

- **Read-back.** `create` and `comment` compare the body in the POST
  response, so a write costs no extra call, and PATCH once if it differs.
  The comparison normalizes only line endings (GitHub stores CRLF) and
  whitespace at the very end of the text. `readback` re-reads the title,
  body, labels and type, and the board fields by field name through one
  GraphQL query on this issue. `gh issue view --json projectItems` omits
  custom fields and would report a correctly set field as empty.
- **Body guard.** `hooks/gh-body-guard` denies `gh issue|pr create|comment|edit`
  with `--body-file`, `-F` or `--body "@path"`. It fails open: anything it
  cannot parse is allowed. `gh api` is never touched.
- **Board fields** come from the template: `[routing]` picks the board per
  repo and `board_fields` maps each board field name to `priority`, `size` or
  a `[fields]` key. The adapter sets single-select fields only. Where a value
  cannot be set (no board for the repo, an estimate that was not
  investigated, a number field), `build` lists it under `proposal_only` with
  the reason, and nothing is written. With `fallback = "stop"`, a repo with
  no routing entry makes `build` exit 1 with `needs_user: "board"`; the skill
  asks and passes `--board N`.
- **Schema cache.** Field and option ids are cached on disk under
  `~/.claude/cache/tickets/` (or `TICKETS_CACHE_DIR`). A miss re-reads the
  schema once before it is believed. `item-list` is never called.
- **Labels are never created.** GitHub creates an unknown label silently
  when an issue is posted with it, so `create` lists the repo's labels
  first and exits 1 if one is missing.
- **Type** is sent only when the owner has an issue type of that name
  (`orgs/{owner}/issue-types`); otherwise `build` lists it as a proposal.
- **Links.** `blocks` links use `gh issue edit --add-blocked-by` (`inward`)
  and `--add-blocking` (`outward`); the first is read back before the rest.
  A parent uses the sub-issues endpoint. Other kinds exit 1.
- **`fetch`** returns the Ticket plus `thread` (the comments), `has_ai_prompt`
  and `ai_prompt`. Pass `--with-board` to include board fields.
- **`detect`** warns on a public repo and exits 4 when issues are disabled.

## Not designed out: stage-to-issue linking

`fetch` returns every link, and `link` accepts any kind a template declares.
A future `stage` link kind (ticket ↔ stage file) needs no new op.
