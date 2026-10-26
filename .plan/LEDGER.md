# plan-staged-rollout: brief and decisions — build ledger

Statuses: `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook) and `skipped` (decided against,
one-line reason). Partial completion is a normal, resumable state.

Keep table rows to **ONE line** — detail goes in the notes block below, never
in a table cell. Sessions read the status table plus only the notes blocks of
the stages they `depend` on (the final review stage reads all of it). Update
your stage's row and notes block at the end of every session (Operating
protocol, finish protocol).

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Formats (keystone) | done | yes | 2026-10-26 | Four formats written; all acceptance checks pass |
| S1 Bootstrap flow | todo | — | — | — |
| S2 Runner and preflight | todo | — | — | — |
| S3 Close-time triage | todo | — | — | — |
| S4 Method (SKILL.md) | doing | yes | 2026-10-27 | SKILL.md describes the new steps; each reference linked once |
| S5 User docs and changelog | todo | — | — | — |
| S6 Example plan | todo | — | — | — |
| SF Plan review | todo | — | — | — |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Formats (keystone)

**As built** (commits on `plan-brief-decisions-s0`):
- `skills/staged-rollout/references/decisions-format.md` — portable spec. Line 1
  is `<!-- decisions-format: 1 -->`; every `DECISIONS.md` written to it starts
  with the same line. Entry shape: `**<rule>** — <why>. Revisit: <cond>.
  Source: <ref>.` Areas are `##` headings whose first line is `Paths:`
  (repo-relative; trailing `/` = subtree, `*`/`**` globs, `.` = whole repo) —
  this is what S2's path-overlap matching reads. Split: `Moved: <folder>/DECISIONS.md`
  under the area heading. Pointer-line wording is in its *The pointer line*.
- `skills/staged-rollout/references/templates/BRIEF.md` — stamp line 1;
  `<hash>` = first 12 hex chars of `git hash-object .plan/PLAN.md` (S2's
  preflight compares exactly this). Six sections, each with an italic
  `*From `PLAN.md` › …*` source line. Plan-review lenses appear as a line
  inside the Decisions section (D-4: the brief lists each lens + trigger).
- `skills/staged-rollout/references/plan-review.md` — four lenses (table:
  trigger, what it reads for, model), finding shape (Where / Problem /
  Change), ~40-line digest, three outcomes, record in `PLAN.md` › Plan review.
- `templates/PLAN.md` — new `## Requirements` (five bullets) before Frozen
  decisions; triage-group preamble + `.plan/BRIEF.md` pointer; example
  decisions `D-1…D-4` show each group, incl. `(Needs you — pending; blocks S2)`.
  **Added beyond the step list:** a `## Plan review` section (before the stage
  index) — the review record needed a home and the brief's Decisions section
  sources from it.

**For S1 (bootstrap flow):** D-1 orders the one batch ask *before*
decomposition, but D-4 evaluates lens triggers against every stage's
`## Artifacts`. `plan-review.md` resolves it: the batch judges triggers
against requirements only; after decomposition a lens that newly turns on is
added and shown in the brief, not asked. Findings that need the user go in one
ask before the scaffold commit.

**Follow-up (not this stage's scope):** `scripts/validate_plugin.py`
`TEMPLATE_FILES` does not list `BRIEF.md`, so a missing brief template would
not fail validation. Candidate for S1 or SF.

**Acceptance evidence** (re-run in the stage worktree on the merged result after re-syncing with the plan branch at d811c9d, which added D-11; output unchanged, 2026-10-26):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

$ grep -niE "plan-staged-rollout|\.plan/|stage|SF" skills/staged-rollout/references/decisions-format.md
exit 1 (1 = no matches)

$ head -1 skills/staged-rollout/references/decisions-format.md
<!-- decisions-format: 1 -->

$ head -1 skills/staged-rollout/references/templates/BRIEF.md; grep "^## " BRIEF.md
Generated from PLAN.md @ <hash> — do not edit
23:## Outcome
29:## Day to day
41:## Constraints and out of scope
52:## Decisions
68:## Done when
75:## Stage map
6

$ grep lens rows in plan-review.md
20:| **Simplicity** | Always, for every plan. | Stages, steps or decisions that could be c
21:| **Architect** | The plan touches **two or more components**, or **changes an interfac
22:| **Security / red team** | The plan touches **authentication, input handling, secrets,
23:| **Operator** | The **product** runs unattended or pages someone — a scheduled job,
```

### S1 Bootstrap flow
_(empty)_

### S2 Runner and preflight
_(empty)_

### S3 Close-time triage
_(empty)_

### S4 Method (SKILL.md)

**As built** (`skills/staged-rollout/SKILL.md`):
- New section *Requirements and decisions, before decomposing* (before
  *Decomposing the work*): requirements step + playback + existing-ADR
  detection (D-6), decision triage into the three groups with one batch ask,
  the brief, the plan review, and a **Depth by size** paragraph (D-7).
- *The final review stage* gains "It also owns what outlives `.plan/`": close
  triage drop / entry / ADR, attended vs unattended approval, README +
  `CLAUDE.md` pointer, cold-reader check, still `gate: auto` (D-1).
- Intro's template list now names `BRIEF.md` (plain name, not a link).

**For S5:** user docs can point at the new SKILL.md section by name. Not done
here (out of scope): D-1's runner showing overlapping `DECISIONS.md` entries
is not described in SKILL.md — S2 owns the runner; SF may judge whether the
method needs a line on it.

**Acceptance evidence** (2026-10-27, stage worktree):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

$ grep -cF 'references/decisions-format.md)' skills/staged-rollout/SKILL.md
1
$ grep -cF 'references/plan-review.md)' skills/staged-rollout/SKILL.md
1
$ grep -cF 'references/templates/BRIEF.md)' skills/staged-rollout/SKILL.md
1
```

### S5 User docs and changelog
_(empty)_

### S6 Example plan
_(empty)_

<!-- One ### S<N> block per stage. Templates for the states you'll hit:

  done      — paste the real acceptance output, then the as-built summary and
              any gotchas the next stage needs to know.
  doing     — tick the completed Steps checkboxes in the stage file; write a
              handoff note here (what's left, where to resume).
  blocked   — record exactly what human/external action unblocks it, as a
              runbook the human can follow; no faked progress. Where that row
              and runbook get committed depends on whether the stage branch
              exists yet — see PLAN.md, Operating protocol, "Recording a
              block". A mid-stage block lands on the stage branch, so this
              file's copy on the plan branch keeps reading `doing` and the
              block is recorded in BLOCKED.md instead. Discovered mid-run that
              the stage needs a resource only the local machine has? Use the
              literal reason `needs-local` in the Result cell (or the
              BLOCKED.md section) instead of a generic note — see PLAN.md,
              "Recording a block", "The discovered case".
  skipped   — one-line reason; if this stage owned acceptance/verification
              work nothing else covers, say so here too, so SF sees it.
  follow-up — a shortcut or scope-creep item spotted here that became (or
              should become) its own stage; name it so the review stage sees it.
-->

### SF Plan review
_(empty)_
