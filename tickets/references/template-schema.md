# Ticket template schema

A **template** tells `create-issue` how a team writes tickets: which body
sections, which title rules, which types, labels, priority and estimate
scales, and which tracker fields to set. It also tells `work-issue` how that
team merges. With no template at all, both skills run on the built-in
default (`templates/default.toml`), and that default must produce a good
ticket on its own. Where GitHub and Jira need different values (priority
scale, estimate, AI-prompt requirements), the built-in default carries them
in `[per_tracker.<tracker>]` overlays (see *Layering*).

Templates are TOML (`tomllib`, Python 3.11 or later, standard library only).
`scripts/` loads and validates them; nothing else parses a template.

## Selecting a template

One config key, `ticket_template`, in the plan-staged-rollout config file:

| Level | Path | Notes |
|---|---|---|
| User | `$CLAUDE_CONFIG_DIR/plan-staged-rollout.toml`, else `~/.claude/plan-staged-rollout.toml` | One per Claude profile. |
| Project | `<repo root>/.claude/plan-staged-rollout.toml` | Overrides the user file, key by key. |

```toml
ticket_template = "~/.claude/templates/my-team.toml"

# or one template per tracker, since a template names its tracker:
ticket_template = { github = "~/.claude/templates/mine.toml", jira = "~/.claude/templates/team.toml" }
```

- The value is a file path, or a table mapping `github` and `jira` to a file
  path each. `~` expands, and a relative path resolves against the directory
  of the config file that set it.
- In a table each tracker is its own key: the project file can override one
  tracker's template and inherit the other's.
- **Key missing** (or a table without an entry for the active tracker): use
  the built-in default and say nothing.
- **A table, but no tracker was given:** one notice, then the built-in default.
- **Key set, but the file is missing, unreadable or fails validation:** give
  one ℹ️ **Notice** that names the path and the first validation error, then
  continue on the built-in default. Never stop the pipeline over a template.
- The config file and the key are named after the plugin the skills ship in
  (plan-staged-rollout).

### `guard_tracker_creates` — the opt-in write guard

```toml
guard_tracker_creates = true
```

Not a template setting, but read from the same files. When either file sets
it to `true`, a tracker create can only happen at the end of create-issue
(`tickets/scripts/write_guard.py` holds the rules):

- the adapters' `build` refuses a create unless the draft's folder holds
  `template.json` (from `resolve`, and the same template `build` was given),
  `review-filtered.json` or `review-skipped.json`, and `estimate.json`;
- the `tracker-write-guard` hook denies a `createJiraIssue` call whose
  arguments the Jira adapter did not issue after `--confirm` (each issued
  call passes once, within two hours; a retry after a failed call needs
  `create --confirm` again), any `executeWrite` create, and `gh issue create`
  or a `gh api` POST to an issues endpoint from the Bash tool, judged on the
  commands the shell will run (`tickets/scripts/shell_cmd.py`), not on words
  inside quotes or heredocs.
- the hook never answers "allow": a call it lets through gets no decision
  from it, so the user's own permission rules still apply.

Edits, comments and links are not guarded. A project file cannot turn off
what the user file turned on; the adapters read the project file from their
working directory, so run them from the repo for a project-only setting to
count. The pipeline gate checks that the evidence files exist, not that they
belong to the current draft. A config file that cannot be read leaves the
guard off, and the hook passes everything through when no Python 3.11 is on
`PATH`.

## Layering

```toml
extends = "default"          # or a path to another template file
```

- `extends` takes `"default"` (the built-in template) or a path, resolved
  the same way as `ticket_template`. A chain may be at most three files deep.
  A cycle is a validation error.
- Merge rule: **tables merge key by key, arrays and scalars replace.** An
  overlay that sets `body.sections` replaces the whole section list. It does
  not append to it.
- **Exception: tables keyed by a list's values replace as a whole:**
  `priority.rubric`, `estimate.matrix` and `fields.<key>.values`. An overlay
  that changes a scale must not inherit rubric entries for the old one.
- **Per-tracker overlays.** Any template may carry `[per_tracker.github]`
  and `[per_tracker.jira]` tables, holding the same tables as the top level
  (`body`, `priority`, `estimate` and so on). Each file's overlay for the
  active tracker is applied to **that file** before the next file in the
  chain is layered on top, so a child's own values always win over its
  base's overlay. The resolved template carries no `per_tracker` table.
- The **active tracker** is the one the user asked for, else the `tracker`
  named in the chain (the child's wins). A template that names a different
  tracker from the one asked for is treated as unreachable.
- A team usually writes one shared template (`extends = "default"`), and a
  sub-team writes a short overlay (`extends = "<shared template path>"`) that
  carries only its own differences.

## Public patterns, private values

Every *mechanism* below is generic and ships in the public plugin. What
identifies one organisation's tracker is a *value*, and values stay in
private template files:

- custom field ids and option ids
- custom field names
- project, board and link-type ids
- site URLs, internal page links, private repo names
- team names

The public plugin carries example templates that use every mechanism with
placeholder values (for example `customfield_00000`, or a field named
"Sensitive data review").

## Top level

| Key | Type | Meaning |
|---|---|---|
| `schema` | int | Schema version. `1` for this document. Required. |
| `name` | string | Short name, shown in notices. Required. |
| `tracker` | `"github"` \| `"jira"` | The tracker this template posts to. Required, except in a template that only other templates extend. |
| `extends` | string | See *Layering*. |
| `description` | string | One line on who uses it. |

## `[body]` — the description

```toml
[body]
sections = [
  { title = "In plain terms", required = true, guidance = "3-5 sentences, no identifiers", no_identifiers = true },
  { title = "Context", required = true, guidance = "why, why now, evidence" },
  { title = "Out of scope", required = false },
  { title = "Acceptance Criteria", required = true, guidance = "bullets, each one observable" },
  { title = "AI prompt", required = false, kind = "ai_prompt" },
]
heading_level = 2
list_style = "bullets"         # "bullets" | "free"
```

- Sections are emitted in list order, as headings at `heading_level`.
- `required = false` sections are left out when empty, never emitted blank.
- `no_identifiers = true` marks the section the gap reviewer holds to plain
  words: no ticket keys, ids, paths or codenames.
- `kind = "ai_prompt"` marks the section that makes a ticket **actionable**.
  `work-issue` acts (branch, implement, PR, merge after confirmation) only
  when this section exists. Without it, `work-issue` only guides. At most
  one section may carry this kind.
- `kind = "acceptance"` (default for a section titled "Acceptance Criteria")
  marks the section the rubric checks for measurable criteria.
- `wrap = "code"` puts the section in a fenced code block when the body is
  rendered; the draft holds it plain, and `check` refuses a draft that
  fences it itself.
- `icon` is an emoji put before the section's heading when the body is
  rendered, as a visual anchor for skimming. Use the emoji character, not a
  `:shortcode:`, which Jira leaves as text. Drafts and every section lookup
  use the plain `title`: both adapters' parsers drop a leading emoji word.
- `list_style` on a section overrides the body's: `"bullets"`,
  `"numbered"` or `"free"`. An acceptance section is `"numbered"` unless it
  says otherwise, and `check` refuses bullets in a numbered section.
- Built-in default: In plain terms / Context / Out of scope / Acceptance
  Criteria / AI prompt (optional), all at H2, bullets.

```toml
[body.ai_prompt]
requires = ["repo", "base_branch", "verification"]   # what the prompt must name; also "effort"
```

`effort` makes the prompt open with a `Proposed model/effort: <tier>` line,
which `check` enforces. For trackers whose tickets do not map to a repo (Jira), the AI prompt must
name the repository and base branch the work lands in. The built-in Jira
default requires both. The GitHub default requires only `verification`,
because the issue's own repo is the target.

```toml
[body.footer]
text = "Drafted with AI"           # appended as the last line, optional
provenance = "_Surfaced in {tool} session {session}, {date} {tz}._"
timezone = "UTC"                    # IANA name or abbreviation used in {tz}
```

## `[title]`

| Key | Type | Meaning |
|---|---|---|
| `verb_first` | bool | Title starts with a verb. Default `true`. |
| `prefix_one_of` | array | Title must start with one of these tags, e.g. an area tag. |
| `keep_existing_tags` | bool | Never strip bracketed tags from a title being edited. Default `true`. |
| `max_length` | int | Default 80. |
| `no_dates` | bool | Dates and urgency words belong in priority or a due date, not the title. Default `true`. |

## `[types]` and `[labels]`

```toml
[types]
allowed = ["Story", "Task", "Bug", "Spike"]
default = "Story"
spike_when = "cannot be estimated"   # rubric hint

[labels]
allowed = ["backend", "frontend"]   # closed list; omit for an open list
create = false                       # never create a label that does not exist
groups = { area = ["backend", "frontend"] }   # at most one label per group
always = ["ai-written"]              # added to every ticket; outside the closed list
```

## `[priority]`

```toml
[priority]
field = "priority"                   # "priority" (native) or a [fields] key
scale = ["Highest", "High", "Medium", "Low", "Lowest"]
default = "Medium"
rubric = { Highest = "outage or data-loss risk", Medium = "normal" }
```

The built-in GitHub default is a board field named `Priority` with `P0`..`P4`.
The Jira default is the native priority with the stock Jira names.

## `[estimate]` — size or story points

```toml
[estimate]
kind = "points"                      # "points" | "size" | "none"
field = "story_points"               # a [fields] key, or "size"; optional
scale = [1, 2, 3, 5, 8]
ceiling = 8                          # largest value allowed
split_above = 8                      # above this, propose a split instead of a number
proposal_only = true                 # the team confirms; the skill says so
set_only_if = "investigated"         # "always" | "investigated"
comment = "Estimate proposed by AI using {guide}"   # posted with the value, optional
guide = "<link to the team's estimation guide>"

[estimate.matrix]                    # optional; without it the estimate is judgement
rows = ["known process", "some unknowns", "many unknowns"]
columns = ["<= 1 day", "2-3 days", "about a week", "more than a week", "whole iteration"]
cells = [
  [1, 2, 3, 5, 8],
  [2, 3, 5, "timebox:8", "split"],
  ["-", 3, 5, "timebox:8", "split"],
]
bump = { when = "depends on another team", cells = [
  [2, 3, 5, 8, "split"],
  [3, 5, 8, "split", "split"],
  ["-", 5, 8, "split", "split"],
] }
questions = ["Is there an existing process?", "Roughly how many days?", "How many unknowns?", "Does it depend on another team?"]
```

- A cell is a number, `"split"` (do not estimate, propose a split),
  `"timebox:<n>"` (the value is a time limit on an investigation, not a
  delivery estimate), or `"-"` (no such combination).
- `bump` is a second matrix, used when its condition holds. The condition
  text is a template value, so team names stay private.
- `questions` are what the skill asks the author when the draft does not
  answer them. They are asked once, together, never one at a time.
- `kind = "size"` uses `scale` as labels (for example `XS`..`XL`) and no
  matrix.
- With no `field` the estimate is **proposed only**: shown in the preview,
  never set on the tracker. `field = ""` clears a field inherited from a
  base template. The built-in Jira default has no field, because a
  story-points field id differs per site.

## `[fields.<key>]` — tracker fields

Every field beyond title, body, type, labels and priority is declared here
under a local key that the rest of the template refers to.

```toml
[fields.story_points]
id = "customfield_00000"             # tracker id (Jira) or Projects field name (GitHub)
kind = "number"                      # number | text | select | user | date

[fields.sensitive_review]
id = "customfield_00001"
kind = "select"
values = { Yes = "10001", No = "10002" }    # display name -> option id
default = "unset"                    # "unset" or a value name
confirm_values = ["Yes"]             # never set without the user's explicit yes
ask_when = "the work touches regulated or personal data"

[fields.team]
id = "customfield_00002"
kind = "select"
repair = { after_seconds = 10 }      # automation overwrites it after create: wait, read, repair
```

- **`default = "unset"` is the default.** A field with no default is left
  out of the payload.
- **`confirm_values`** makes a field *guarded*: the skill never sets one of
  these values by inference. It asks, with the field's `ask_when` text as the
  reason, and records the answer. Absence of an answer means unset.
- **`repair`** marks a field that tracker automation is known to change after
  create. The adapter waits `after_seconds`, reads back, and repairs once
  (see the adapter contract).
- `id` values and field names are private. A public example uses
  placeholders.

## `[links]`

```toml
[links]
blocks = { id = "00000", name = "Blocks", inward = "blocker", outward = "blocked" }
split_from = { id = "00001", name = "Split" }
relates = { id = "relates", name = "Relates" }
parent = "native"                    # "native" parent field, or a [fields] key
```

Link direction is declared, never guessed. The adapter creates one link,
reads it back, and only then creates the rest.

`name` is the link type's name as the tracker shows it. The Jira MCP's link
operation takes the name, not the id, so the Jira adapter rejects a link kind
without one (added in S3).

## `[intake]` — tickets that arrive from a form

```toml
[intake]
footer_keys = { "Stream" = "component", "Environment" = "context", "Relevant links" = "context" }
operational_checklist = ["target system", "environment", "expected effect", "rollback or confirmation"]
```

For requests a form creates (a one-line ask plus `Key: value` lines),
`footer_keys` maps each footer key to a field, a label, or a line in Context.
`operational_checklist` is what the gap reviewer asks for on a "run this
change" request.

## `[routing]` — GitHub only

```toml
[routing]
owner = "<account>"
fallback = "same-name-board"         # "same-name-board" | "stop" | "none"
repos = { "my-repo" = { board = 3 }, "other-repo" = { board = "none" } }
board_fields = { Priority = "priority", Size = "size", Effort = "effort", Env = "env" }
```

- A repo not in `repos` follows `fallback`. `"stop"` asks the user, and
  never picks a board by resemblance.
- `board_fields` maps Projects field names to `[fields]` keys or to the
  built-in `priority` and `size`.

## `[review]` — extra gap-review rules

```toml
[review]
extra_checks = ["Every UI change links its design"]
skip_when = ["title starts with 'Automated review:'"]   # machine-created tickets
max_questions = 5

[[review.references]]                # pages a ticket on these topics should be checked against
name = "Team security and reliability work"
url = "https://example.com/wiki/security-and-reliability"
covers = "access, backups, restore testing, alerting, auditing, encryption, retention"
points = ["A ticket that both sets a standard and implements it is split"]   # optional
```

These add to the rubric in `gap-rubric.md`, never remove from it.

- **`references`** feed the `unsourced-decision` check. The reviewer gets the
  name, link, `covers` and `points` as text, never the page itself. When a
  draft touches what an entry covers, it asks whether the draft was checked
  against it, by name. `covers` is written by the template author: the skill
  holds no list of sensitive topics. `points` is optional and is a hand-kept
  excerpt, so it goes stale when the page changes; keep it to the few rules a
  reviewer can check against a draft.

## `[work]` — how `work-issue` lands the change

```toml
[work]
branch = "{type}/{number}-{slug}"
commit_style = "conventional"
merge_command = "gh pr merge {pr} --squash --delete-branch"
merge_ask_header = "Merge?"
status = { on_start = "In progress", on_pr = "In review" }   # tracker status names
attribution = { commit_trailer = "", pr_footer = "" }
```

**A template may tighten these rules, never loosen them.** The plugin always
does these things, and no key can switch any of them off:

- ask for explicit confirmation before every merge, opening on a short
  plain-language description of the change
- run the pre-merge gap check, and the acceptance check when the change has
  something a user can verify
- never force-push, rewrite history, or alter remotes
- never commit to the default branch
- one branch per issue

The validator rejects unknown `[work]` keys. A key that would loosen a rule
has no name to be written under.

`scripts/work_core.py` applies this section for `work-issue` and refuses two
more shapes at run time: a `merge_command` that does not start with
`gh pr merge` or lacks `{pr}`, and a `merge_ask_header` longer than 12
characters (the dialog's chip limit). `branch` may use only `{type}`,
`{number}` (a Jira key for Jira) and `{slug}`. `status` names are written
to a GitHub board field mapped to `status` in `[routing].board_fields`;
Jira statuses are not written (the adapter has no transition operation).

## Validation

`scripts/` validates a resolved template and reports every error at once:

- unknown keys, at every level
- wrong types
- a `[fields]` reference that does not exist
- more than one `ai_prompt` section
- `ceiling` not in `scale`
- matrix rows or columns of the wrong length
- a field whose `default` is one of its own `confirm_values` (a guarded
  value can never be a default)

- a `[fields]` entry with `confirm_values` but no `ask_when` (the skill
  needs the reason to ask)
- `estimate.scale` of the wrong kind (integers for points, labels for size)

An invalid template is treated as unreachable (one notice, then the
built-in default). `scripts/ticket_template.py validate <path>` runs these
checks by hand; `resolve` is what the skills call.

## Not designed out: stage-to-issue linking

A later change lets `plan-stages` create one issue per stage. That needs a
link from the ticket back to its stage file. It uses the existing `[links]`
and body machinery: a `stage` link kind or a body line. No new top-level key
is reserved, and nothing in this schema prevents adding one.
