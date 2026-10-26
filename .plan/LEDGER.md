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
| S1 Bootstrap flow | done | yes | 2026-10-27 | plan-stages reordered; effortlog gains plan-stages + subagent_tokens; checks pass |
| S2 Runner and preflight | done | yes | 2026-10-27 | Brief stamp + decisions steps in protocol, runner, README, stage-run |
| S3 Close-time triage | done | yes | 2026-10-27 | SF template gains decision triage; plan-close PR body gains Kept decisions |
| S4 Method (SKILL.md) | done | yes | 2026-10-27 | SKILL.md describes the new steps; each reference linked once |
| S5 User docs and changelog | done | yes | 2026-10-27 | Docs, reference and one CHANGELOG entry written; validate passes |
| S6 Example plan | done | yes | 2026-10-27 | examples/feed-digest/ shows all five artifacts; validator OK |
| SF Plan review | done | yes | 2026-10-27 | 10 loose ends sorted; 7 decisions kept in DECISIONS.md; S7 spawned |
| S7 Close the gaps | todo | — | — | — |

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

**As built** (commits on `plan-brief-decisions-s2`):
- `templates/PLAN.md` — new preflight **step 0.6 "Check the brief is
  current"** (stamp vs first 12 hex of `git hash-object .plan/PLAN.md`;
  mismatch → rebuild each section from the `PLAN.md` section its italic
  source line names, commit `chore(plan): regenerate brief` directly on the
  plan branch with the `done` write's race handling). "Report, don't repair"
  is now 0.7 (nothing referenced it by number). Read scope (step 1) gains a
  **Decisions in force** paragraph (D-1, D-6). **Added beyond the step
  list:** finish step 3 now says a stage that amends Frozen decisions
  regenerates the brief in the same commit — without it, mismatches would be
  the norm, not the backstop.
- `templates/RUNNER.md` §3 and `commands/stage-run.md` step 2 carry the same
  two bullets word for word, framed as "run whether or not `PLAN.md` spells
  them out", so plans scaffolded earlier get them too. RUNNER §9's
  file-creation list now allows a regenerated `BRIEF.md`. No RUNNER section
  was renumbered (examples cite §7).
- `templates/README.md` — the two steps in plain words, plus a `BRIEF.md`
  entry under Files. **D-6 target-path convention** (recorded in README and
  `stage-run.md`): the decisions document is the one a **Decided** frozen
  decision records as adopted, else `DECISIONS.md` at the repo root.

**S1 alignment (checked at re-sync):** `commands/plan-stages.md` records the
existing decision record as a **Decided** triage item (none → a new root
`DECISIONS.md` at close) — the same convention the runner reads.

**Gaps for SF:** the preflight backstop regenerates only the file, not a
published brief artifact (D-2 makes the file canonical, so the artifact can
go stale until next published). An adopted decisions document without
`Paths:` lines is only named, not matched.

**Acceptance evidence** (2026-10-27, re-run in the stage worktree on the merged result after re-syncing with the plan branch at 6fe9b67 (S4) and again at b2de2ab (S1, S3; LEDGER table conflict resolved keeping all rows); output unchanged):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

# RUNNER.md §3 bullets vs stage-run.md step 2 bullets, whitespace-normalized
$ diff runner.txt stagerun.txt
IDENTICAL (whitespace-normalized)   # 242 words, no differences

# A plan with no DECISIONS.md / BRIEF.md behaves as before: both steps are
# gated on the file existing, and each copy states the no-file outcome.
# This plan itself has neither, so this very run exercised that path.
$ test -e DECISIONS.md; test -e .plan/BRIEF.md
DECISIONS.md absent
.plan/BRIEF.md absent
$ grep -n "means this step does nothing|nothing to show and nothing else changes|nothing to do.|runs as it always has"
templates/PLAN.md:340:      existed — means this step does nothing.
templates/PLAN.md:367:   section, means nothing to show and nothing else changes.
templates/RUNNER.md:66:  handling. No `BRIEF.md`, or a matching stamp: nothing to do.
templates/RUNNER.md:79:  show, and the stage runs as it always has.
templates/README.md:35:and the stage runs as it always has.
commands/stage-run.md:92:     handling. No `BRIEF.md`, or a matching stamp: nothing to do.
commands/stage-run.md:105:     show, and the stage runs as it always has.
```

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

**As built** (commits on `plan-brief-decisions-s5`):
- `docs/staged-rollout.md` — section 1 rewritten for the new order (size check, requirements + playback, triage + one batch ask, decompose, brief, plan review, commit, session cards), with new subsections *The brief* and *Plan review*; section 2 gains the brief-stamp and decisions-in-force bullets; section 3 gains *Which decisions outlive the plan* (drop / entry / ADR, attended vs unattended approval, README, pointer line, cold reader); section 4 mentions the Kept decisions section. `.plan/` tree lists `BRIEF.md`.
- `docs/reference.md` — `BRIEF.md` row and updated `PLAN.md` row in *Plan files*; new section *Brief, review and decisions formats* (links the three reference files, runner behaviour, effort-log row).
- `CHANGELOG.md` — one `### Added` entry under a new `## [Unreleased]` heading (none existed), referencing #226. No version heading, no `plugin.json` change.

**Acceptance evidence** (2026-10-27, stage worktree):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0
```

Changelog entry:

> - **Requirements, a brief and a plan review before stage 1, and kept decisions after `.plan/` is gone.** `plan-stages` now captures and plays back your requirements before deciding how, sorts decisions into Decided, Needs you and Default for now and asks the open ones once, generates a one-page `.plan/BRIEF.md` from `PLAN.md` (also published as an artifact where that tool exists), and runs a plan review with up to four lenses before the scaffold is committed. The review stage proposes drop, a `DECISIONS.md` entry or an ADR for every frozen decision, updates the README and runs a cold-reader check; `plan-close` lists the kept decisions in the final PR. Stages check the brief's stamp and show the decisions in force for the paths they touch. Work that fits one issue is unchanged. `DECISIONS.md` follows a new portable format (#226).

**Not done (out of scope, for SF):** the docs do not cover the S3 follow-up that the decisions spec does not reach a cloud SF in other repos.

### S6 Example plan

**As built** (commits on `plan-brief-decisions-s6`): `examples/feed-digest/`,
a toy daily RSS-to-chat job frozen at closeout (every stage `done`,
`/plan-close` next), listed in `examples/README.md`. `.plan/PLAN.md`,
`README.md` and `RUNNER.md` take their protocol text from the current
templates with the slug substituted (assembled by script, not hand-copied);
everything above *Git strategy* and the Plan review / Stage index sections are
written for the toy. S2 is `gate: local` to show that flag in passing.
**Added beyond the step list:** the toy's pointer line sits in `AGENTS.md`,
not `CLAUDE.md` — a nested `CLAUDE.md` would be loaded by Claude Code as
instructions whenever a session in this repo reads files under it. The
plan-review digest is kept outside `.plan/` and labelled as normally-scratch.

**Where each item is** (file › heading):

- Requirements section — `examples/feed-digest/.plan/PLAN.md` › `## Requirements`
- Triage groups — `examples/feed-digest/.plan/PLAN.md` › `## Frozen decisions`
  (D-1/D-3/D-7 Decided, D-2/D-4 Needs you — answered, D-5/D-6 Default for now)
- Filled brief with stamp and Mermaid flow — `examples/feed-digest/.plan/BRIEF.md`
  line 1 stamp, `## Day to day` (Mermaid), `## Stage map` (Mermaid)
- Plan-review digest with outcomes — `examples/feed-digest/plan-review-digest.md`
  (five findings: three change, one follow-up, one accept), recorded in
  `examples/feed-digest/.plan/PLAN.md` › `## Plan review`
- Close-time outcomes — `examples/feed-digest/.plan/LEDGER.md` › `### SF Plan review`
  › `#### Kept decisions` (D-1, D-6, D-7 drop; D-2, D-3, D-5 entry; D-4 ADR);
  `examples/feed-digest/DECISIONS.md` (areas Posting, Feed state, Scheduling);
  `examples/feed-digest/docs/adr/0001-dedupe-by-stable-entry-key.md`;
  pointer line in `examples/feed-digest/AGENTS.md`

**Gotcha for whoever edits the example:** the brief's stamp is the real
`git hash-object` of the example `PLAN.md`. Any edit to that file means
regenerating the stamp, or the README's "the hash matches" claim goes false.

**Acceptance evidence** (2026-10-27, re-run in the stage worktree on the merged result after re-syncing with the plan branch at 04250da, which landed S5; LEDGER table conflict resolved keeping both rows; output unchanged):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0

$ head -1 examples/feed-digest/.plan/BRIEF.md
Generated from PLAN.md @ 93a8b7e4f1b9 — do not edit
$ git hash-object examples/feed-digest/.plan/PLAN.md | cut -c1-12
93a8b7e4f1b9

$ grep -n "^## Requirements\|^## Plan review" examples/feed-digest/.plan/PLAN.md
27:## Requirements
137:## Plan review

$ grep -n "^## \|mermaid" examples/feed-digest/.plan/BRIEF.md
8:## Outcome
16:## Day to day
20:```mermaid
28:## Constraints and out of scope
42:## Decisions
62:## Done when
73:## Stage map
77:```mermaid

$ grep -c "Outcome:" examples/feed-digest/plan-review-digest.md
5

$ grep -n "^#### Kept decisions" examples/feed-digest/.plan/LEDGER.md
115:#### Kept decisions
$ head -1 examples/feed-digest/DECISIONS.md
<!-- decisions-format: 1 -->
$ ls examples/feed-digest/docs/adr
0001-dedupe-by-stable-entry-key.md
```

**For SF:** the example duplicates template protocol text by design (it
ships a whole `.plan/`), so a later template change leaves it stale, as it
already does `uptime-page/`. Nothing checks it; accept or add a check.

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

**Loose ends** (every item from the S0–S6 notes, each mapped to exactly one outcome):

| # | Loose end (source) | Outcome |
|---|---|---|
| L1 | `validate_plugin.py` `TEMPLATE_FILES` lists neither `BRIEF.md` nor `RUNNER.md` (S0, S1) | **New stage S7** |
| L2 | The decisions spec never reaches a cloud SF in another repo: `/plan-stages` copies `templates/*.md` only, not `references/decisions-format.md` — against ranked constraint 3 (S3, S5) | **New stage S7** |
| L3 | SKILL.md *Unattended mode* table has no row for SF's decision-triage approval (S3) | **New stage S7** |
| L4 | SKILL.md does not describe the runner's "decisions in force" step (S4) | **New stage S7** |
| L5 | The preflight backstop regenerates `BRIEF.md` but not a published artifact (S2) | **Accepted, won't fix** — D-2 makes the file the brief; the artifact is only a render |
| L6 | An adopted decisions doc without `Paths:` lines is named, not matched (S2) | **Accepted, won't fix** — D-6 adopts the existing format; imposing `Paths:` is the migration it rejected |
| L7 | Example plans copy template protocol text and go stale unchecked (S6; `uptime-page/` already is) | **Spin-off** — a validator check for example drift |
| L8 | `feed-digest`'s brief stamp must be regenerated on any edit to its `PLAN.md` (S6) | **Spin-off** — fold into L7's check (stamp vs `git hash-object`) |
| L9 | D-5: the bootstrap overhead share is to be read off the effort log after the next real plan | **Spin-off** — measure after the next real plan |
| L10 | Preflight sees an unrelated `feat/205-log-gap-review-tally-each` branch | **Accepted, won't fix** — not a `plan-*` branch, outside this plan |

Count check: 10 captured = 4 new stage + 3 spin-off + 3 accepted. S7 is a
stage index row, the ledger row above and `.plan/stage-7-close-gaps.md`.

**Spin-offs for the plan→main PR body:** L7 + L8 (validator check that example
plans match the templates and their brief stamps), L9 (read the `plan-stages`
overhead share off the effort log after the next real plan).

**Issue #226 "When this closes" walk:**

1. Requirements and triage before any frozen decision, one batch — **met**:
   `commands/plan-stages.md` steps 2 (l.52), 3 (l.87, *Ask once* l.102) precede 4 *Decompose* (l.116).
2. Brief generated from `PLAN.md`, refreshed on change — **met**: `plan-stages.md` step 7
   (*Regenerate the brief after every later `PLAN.md` edit*, l.311); `templates/PLAN.md`
   preflight step 0.6 *Check the brief is current* (l.325) as the backstop.
3. Plans above the threshold get a review before stage 1, findings land in the plan — **met**:
   `plan-stages.md` step 8 *Plan review — before the commit* (l.317) precedes 9 *Commit* (l.340);
   the record goes in `PLAN.md` › Plan review.
4. Every frozen decision dropped / entry / ADR, approved in one batch — **met**: this stage,
   `#### Kept decisions` below, approved in one ask.
5. `CLAUDE.md` has the pointer line; each stage shown its entries — **met**: `CLAUDE.md` › *Decisions*
   (l.23); *Decisions in force* in `templates/PLAN.md` (l.351), `templates/RUNNER.md` (l.67),
   `commands/stage-run.md` (l.93).
6. Final stage updates the README; cold-reader check runs — **met**: `README.md` › *How a plan runs*
   and *Try it* steps 2 and 4; cold-reader record below.
7. A small fix runs none of this — **met**: `plan-stages.md` step 2 *Size first* sends one-issue
   work to `work-issue` with no brief or review; `git diff --stat origin/main...HEAD -- skills/work-issue` is empty.
8. User docs and changelog — **met**: `docs/staged-rollout.md` › *The brief* (l.127), *Plan review*
   (l.147), *Which decisions outlive the plan* (l.352); `CHANGELOG.md` `## [Unreleased]` (l.11).

#### Kept decisions

Target: `DECISIONS.md` at the repo root (no ADR folder or decisions document existed).

- D-1 — entry — `DECISIONS.md` › Planning flow
- D-2 — entry — `DECISIONS.md` › Planning flow
- D-3 — drop — the brief's "do not edit" stamp and `plan-stages.md` step 7 already say feedback edits `PLAN.md` only
- D-4 — entry — `DECISIONS.md` › Planning flow
- D-5 — entry — `DECISIONS.md` › Planning flow
- D-6 — drop — `decisions-format.md` › *Where it lives* is its record
- D-7 — entry — `DECISIONS.md` › Planning flow
- D-8 — entry — `DECISIONS.md` › Decisions format (the portability rule; the file locations are plain from the tree)
- D-9 — drop — only mattered while the plan ran
- D-10 — drop — only mattered for this plan's own SF
- D-11 — entry — `DECISIONS.md` › Planning flow

Approved by Carlos Eng on 2026-10-27, in one batch.

Git strategy, worktree strategy and final review stage are method, not project: left out.
D-10 dogfood: the triage ran from `skills/staged-rollout/references/templates/stage-f-review.md`
(S3's rewrite), not `.plan/stage-f-review.md`; `CLAUDE.md` gained the pointer line.

**Cold-reader check** (fresh Sonnet subagent, repo only, told never to open `.plan/`; one pass, no misses, nothing fixed):

| Question | First answer (sources it cited) |
|---|---|
| How do I test a change? | `python3 scripts/validate_plugin.py`, same as CI (`CONTRIBUTING.md` › Validation, `CLAUDE.md`) |
| Where is the plan review defined? | `references/plan-review.md` › The four lenses; run in `plan-stages.md` step 8 |
| Where is the `DECISIONS.md` format, first line? | `references/decisions-format.md`; `<!-- decisions-format: 1 -->` |
| Why the review runs in `/plan-stages` (D-1)? | no extra session or human gate; review before stage 1 by construction (`DECISIONS.md` › Planning flow, `plan-review.md`) |
| Why only Simplicity always (D-4)? | all four would double the cost (`DECISIONS.md` › Planning flow) |
| Why `decisions-format.md` stays plugin-neutral (D-8)? | Daikenja carries an identical copy (`DECISIONS.md` › Decisions format) |
| Where is the brief template, how is staleness found? | `templates/BRIEF.md`; stamp vs `git hash-object`, preflight regenerates (`stage-run.md`, `docs/staged-rollout.md`) |

**Acceptance evidence** (2026-10-27, stage worktree):

```
$ python3 scripts/validate_plugin.py
validate-plugin: OK
exit 0
$ head -1 DECISIONS.md
<!-- decisions-format: 1 -->
$ grep -n "DECISIONS.md" CLAUDE.md
23:- **Decisions in force live in [`DECISIONS.md`](DECISIONS.md).** ...
```
