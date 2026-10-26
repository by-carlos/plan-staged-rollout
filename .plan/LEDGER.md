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
| S1 Bootstrap flow | doing | yes | 2026-10-27 | plan-stages reordered; effortlog gains plan-stages + subagent_tokens; checks pass |
| S2 Runner and preflight | todo | — | — | — |
| S3 Close-time triage | done | yes | 2026-10-27 | SF template gains decision triage; plan-close PR body gains Kept decisions |
| S4 Method (SKILL.md) | done | yes | 2026-10-27 | SKILL.md describes the new steps; each reference linked once |
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

**As built** (commits on `plan-brief-decisions-s1`):
- `commands/plan-stages.md` — eleven steps. The old free-form design pass
  (`superpowers:brainstorming`, one question at a time) is gone: step 3's one
  batch ask replaces it, with a second ask only when an answer opens a new
  **Needs you** question. Size check (D-7) opens step 2; ADR / decisions-doc
  detection (D-6) is a step-2 item fed into step 3's triage. Scaffold
  subagent leaves `BRIEF.md` and `PLAN.md` › Plan review alone; the parent
  generates the brief (step 7), re-checks lens triggers against
  `## Artifacts`, runs lenses + a Sonnet digest-merge subagent (step 8), then
  commits (step 9). The review ask and the brief-feedback invitation are one
  ask. End announcement hands off wave 0 via `stage-run.md` step 7
  *Desktop-app chips* (D-11), reading "what the finished stage left behind" as
  "what the bootstrap left behind". Also fixed the weight gate's garbled "as
  a effort actually set" sentence.
- `skills/staged-rollout/scripts/effortlog.py` — `--source` gains
  `plan-stages`; `--outcome` help gains `plan-scaffolded`. **Added beyond the
  step list:** every `log` row now carries `subagent_tokens` — the sum of each
  `<sid>/subagents/*.jsonl` transcript's last-turn context (same unit as
  `context_tokens`), `null` when the session had none. That is how D-5's
  "including review subagents' tokens" is met without the model adding them
  up. Verified against an older session with subagents: 145347.

**For S2 / S4 / S5:** `plan-stages.md` step numbers changed (scaffold is now
6, brief 7, review 8, commit 9, end announcement 11); no other file referenced
the old numbers (grep found none outside `.plan/` and `CHANGELOG.md`).

**Follow-up (not this stage's scope, carried from S0):**
`scripts/validate_plugin.py` `TEMPLATE_FILES` still does not list `BRIEF.md`,
and `plan-stages.md` now copies it with `templates/*.md`. Candidate for SF.

**Acceptance evidence** (re-run in the stage worktree on the merged result after re-syncing with the plan branch at c300660, which landed S4; output unchanged, 2026-10-27):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

$ python skills/staged-rollout/scripts/effortlog.py log --help | grep source
usage: effortlog.py log [-h] --source {work-issue,stage-run,plan-stages}
  --source {work-issue,stage-run,plan-stages}

$ grep -n "top-level sessions" commands/plan-stages.md
grep exit 1   (no matches)

$ grep -n "stage-run.md\` step 7" commands/plan-stages.md
397:    app, one card per stage by following `commands/stage-run.md` step 7,

$ grep -nE "^[0-9]+\. \*\*" commands/plan-stages.md   (step headings)
39:1. **Weight gate (first, before anything else).**
52:2. **Requirements and playback — before any decision.**
87:3. **Decision triage — one batch ask.**
116:4. **Decompose.**
167:5. **Git model (fixed, not a question).**
220:6. **Scaffold — dispatch a subagent, don't commit yet.**
294:7. **Brief.**
317:8. **Plan review — before the commit.**
340:9. **Commit.**
352:10. **Run record.**
371:11. **End announcement.**
```

Requirements (2) and triage (3) precede decomposition (4) and every frozen
decision; the review (8) precedes the commit (9).

### S2 Runner and preflight
_(empty)_

### S3 Close-time triage

**As built** (commits on `plan-brief-decisions-s3`):
- `skills/staged-rollout/references/templates/stage-f-review.md` — the loose-end
  checklist is kept verbatim under `### Loose ends`; two new step groups follow.
  `### Decision triage`: find the target (D-6, the spec's *Where it lives*;
  ambiguous → one more batch question attended, hard stop for this step only
  unattended), propose drop / entry / ADR per frozen decision by the spec's keep
  rule (the fixed git/worktree/final-review protocol entries are left out), one
  batch ask attended vs applied-own-proposals unattended (D-1), write the
  approved ones, record them under a heading that reads exactly
  `#### Kept decisions` in the SF notes block — one line per decision plus an
  approval line. `### README, pointer line and cold reader`: README (or module
  doc) update, the pointer line from the spec, and the cold-reader subagent
  (repo only, never `.plan/`; how to test / where is X / why Y; every miss is
  fixed and re-asked). Goal reworded from "never implements" to "writes
  documentation only; never product code" (D-1). Acceptance and Artifacts
  gained matching items.
- `commands/plan-close.md` step 3 — the PR body shape gains a **Kept
  decisions** section, copied line for line from SF's `#### Kept decisions`;
  an unattended list opens with "merging this PR approves these decisions";
  a plan with no such list says no triage ran.

**Contract for S5/S6/SF:** the heading `#### Kept decisions` in the SF notes
block is the hand-off between SF and `/plan-close` — the example plan (S6)
should show it in that exact form.

**Follow-ups (not this stage's scope — for SF):**
- **The spec does not reach a cloud SF.** The template reads
  `decisions-format.md` from `.plan/decisions-format.md` if the plan carries a
  copy, else from the plugin. Nothing copies it into `.plan/` at bootstrap
  today (S1's territory), so in a cloud session — where the plugin does not
  load — a plan in any repo other than this one cannot read it. Either
  `/plan-stages` copies it alongside `RUNNER.md`, or this is accepted.
- **SKILL.md's *Unattended mode* table** has no row for SF's decision-triage
  approval (apply own proposals; the plan→main PR merge approves). S4 states it
  in prose under the final review stage section, but the table that
  classifies every unattended decision point does not list it.

**Acceptance evidence** (re-run in the stage worktree on the merged result after re-syncing with the plan branch at 6fe9b67, which added S4; output unchanged, 2026-10-27):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

$ grep -n "^## \|^### " skills/staged-rollout/references/templates/stage-f-review.md
19:## Goal
27:## Steps
29:### Loose ends
46:### Decision triage
80:### README, pointer line and cold reader
104:## Acceptance
118:## Artifacts

$ grep -n "Kept decisions" commands/plan-close.md
120:     the ledger notes), a **Kept decisions** section, and any spin-off
123:   - the rule for **Kept decisions**: copy the `#### Kept decisions` list from
```

The three-outcome checklist (new stage / spin-off / accepted, won't fix) sits
unchanged under `### Loose ends`; the decision triage, README, pointer and
cold-reader items are the step groups at lines 46 and 80.

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
