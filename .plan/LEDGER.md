# Milestones, live stages, plain numbers and a final review that stays last — build ledger

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
| S0 Format contract: `gate: live` and plain stage IDs | done | yes | 2026-10-27 | `live` gate and plain-ID rule written into PLAN/BRIEF templates and SKILL.md; validator passes |
| S1 Measure stage size | done | yes | 2026-10-27 | D-15 amended from 46 stage sessions (interventions + active hours); PR #242 merged |
| S2 Runners respect `live` | done | yes | 2026-10-27 | every runner fires only `auto`/absent and refuses `live`/unknown; hook run on fixture; validator passes; PR #244 merged |
| S3 Renumbering script | done | yes | 2026-10-27 | renumber_stages.py renumbers only unstarted stages; 37-test suite passes; PR #245 merged |
| S4 Bootstrap: programmes, waits, ordering | done | yes | 2026-10-27 | programme, wait refusal, running-order IDs and `live` grouping written into plan-stages/plan-close/SKILL.md; validator passes; PR #243 merged |
| S5 Final review that stays last | doing | yes | 2026-10-27 | SF template, SKILL.md section, PLAN template line and both drivers now give D-4/D-7 outcomes, capped fix, docs on clean pass only, unattended stop; validator passes |
| S6 Docs, lens checks and changelog | todo | — | — | — |
| SF Plan review | todo | — | — | — |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Format contract: `gate: live` and plain stage IDs

Acceptance output (2026-10-27, worktree `../plan-staged-rollout-s0`, branch `plan-stage-shape-s0`):

- `python3 scripts/validate_plugin.py` → `validate-plugin: OK`
- `grep -n "live"` shows the new rule at:
  - `templates/PLAN.md` 131–145 (`live` value, never driver-fired, fire only on `auto`/absent, unknown values refused and named, build-stage definition, two-`live` start-time refusal), 156 (escalation list), 193 (operator-action bullet), and a new **Stage IDs** paragraph after the flag values.
  - `templates/BRIEF.md` 87–89 (stage-map gate label).
  - `SKILL.md` 124–130 (*Group by gate*), 187–207 (*Flag heuristics* `gate` bullet), 266 and the *Derive, never store* bullet (*Parallel stages*: no two `live` at once, ID rule), 357 (*Statuses and human-gated stages*), 417–418 and 440 (*Unattended mode* table rows and "never launched" sentence).
- "An **absent** `gate` column reads as `auto`" is untouched (`SKILL.md` 220); the template's "a missing `gate` column … means those defaults" also stands.

As built: the ID rule says plain numbers plus `SF`, suffixed IDs read but never created (scaffold or insert), numbering in running order with side-by-side stages consecutive, and no stage numbered below anything it depends on. The *Group by gate* bullet was extended to `live` (D-11) and now says "front or end … as far as the dependencies allow".

Left for later stages (not touched here, per scope):
- S2: the template `PLAN.md` operating protocol still says "a `gate: human` or `gate: local` stage is never started unattended" (weight-check step, finish step 6 announcement, *The discovered case*), and `templates/RUNNER.md` §4 refuses only `human`/`local`; both need `live` and the unknown-value refusal. The `/stage-run` preflight check for two `live` stages is S2's too.
- S3/S4: the stage-ID grammar in `RUNNER.md` §1 and the hook/command text still describe suffixed IDs as ordinary; the "rejected at scaffold time and on insert" behaviour belongs to S3/S4.

### S1 Measure stage size
Scratchpad script (not committed) read structured transcript fields only. Stage session = first user message names
`stage-run` or `RUNNER.md`, or the session ran on a `plan-*-s<N>` branch. Interventions = user messages after the first,
not tool results, task notices or compaction summaries. Active hours = elapsed time with gaps over 10 minutes dropped. The
running sessions (this one included) were skipped. Pooling other projects was approved by the maintainer; output carries
ordinal labels only.

This repository alone (10 stage sessions, 179 files scanned):

```
session            wall_h  active_h interv compac   out_tok   calls   peak_ctx
stage session 1      0.09      0.09      6      0     11257      20      67253
stage session 2      0.10      0.10      2      0      7792      15      90353
stage session 3      0.12      0.12      1      0     19464      14      52953
stage session 4      0.12      0.12      3      0     10320      21      78673
stage session 5      0.16      0.16      0      0     28892      36     152984
stage session 6      0.18      0.18      0      0     16312      24     149264
stage session 7      0.23      0.23      0      0     36187      52     176068
stage session 8      0.31      0.31      8      0     14642      23     103433
stage session 9      0.31      0.20      0      0      5096      14     119933
stage session 10     0.40      0.40      7      0     19866      31     122303
median               0.17      0.17    1.5    0.0     15477      22     111683
max                  0.40      0.40    8.0    0.0     36187      52     176068
sessions with >=1 compaction: 0 of 10
sessions with >=1 intervention: 6 of 10
```

Pooled (46 stage sessions, 1573 files scanned), summary lines and quantiles. The pooled maximum wall time (898.39 h) is a
session resumed after long gaps, which is why active hours are used:

```
median               0.39      0.39    2.0    0.0     27527      49     147871
max                898.39      2.42   13.0    0.0    190100     227     375509
sessions with >=1 compaction: 0 of 46
sessions with >=1 intervention: 32 of 46

quantiles min/p25/median/p75/p90/max
active   [0.01, 0.17, 0.39, 0.88, 1.67, 2.42]
interv   [0.0, 0.0, 2.0, 4.0, 6.0, 13.0]
calls    [3.0, 23.25, 49.5, 97.25, 135.5, 227.0]
out_tok  [918.0, 10554.25, 27527.5, 66343.75, 109693.5, 190100.0]
peak_ctx [52953.0, 99815.0, 147871.0, 231178.75, 299456.5, 375509.0]
Spearman rank correlation of interventions with: active hours 0.58, output tokens 0.35, model calls 0.39, peak context 0.16
Mean interventions above / below the median: active hours 3.48 / 1.70; peak context 2.61 / 2.57
```

Sample size: 10 here, 46 pooled; enough to say compactions never happen in a stage and that time, not context,
tracks interventions. Not enough to separate stage types. Story points were never recorded in a session, so none are
reported. Throwaway script lives in the session scratchpad only.

Leak grep over the stage diff (personal paths, project folder names, hostnames, emails, token-like strings); output empty:

```
git diff plan-stage-shape...HEAD | grep -nE '[C]:[\/]Users|[/]Users[/]|[/]home[/]|[C]--|[[:alnum:]-]+[.](local|lan|internal|home|corp)\b|[[:alnum:]._-]+[@][[:alnum:].-]+[.][a-z]{2,}|gh[pousr]_[[:alnum:]]{20}|sk-[[:alnum:]]{20}|AKIA[[:alnum:]]{16}|[[:alnum:]+/]{40,}'
```

Decision change: D-15 amended in `.plan/PLAN.md`; `.plan/BRIEF.md` regenerated in the same commit. Follow-up for S6: write the
threshold (more than 4 interventions or 1 hour of active time) into SKILL.md › *Decomposing the work*.

### S2 Runners respect `live`

Acceptance output (2026-10-27, worktree `../plan-staged-rollout-s2`, branch `plan-stage-shape-s2`).

Hook run from a scratch copy of `skills/staged-rollout/tests/fixtures/live-plan/.plan/` (`git init` there; S1 build,
S2 and S3 `live`, S4 gate `canary`; S0 done, S5 waits on S1) — the context it printed:

```
**Active staged rollout in this repo** (`.plan/` present). **4 stages are runnable right now** — their `depends` are all satisfied and none of them depends on another, so they can be run **concurrently, one per fresh session**:

- **S1 — Build the API** — `/plan-staged-rollout:plan-run 1` (model `sonnet`, effort `high`)
- **S2 — Deploy to staging** — `/plan-staged-rollout:stage-run 2` (model `sonnet`, effort `high`) — `gate: live`: it changes a running system, so no driver fires it
- **S3 — Migrate the production data** — `/plan-staged-rollout:stage-run 3` (model `sonnet`, effort `high`) — `gate: live`: it changes a running system, so no driver fires it
- **S4 — Warm the cache** — `/plan-staged-rollout:stage-run 4` (model `sonnet`, effort `medium`) — REFUSED: `gate: canary` is not a gate value (auto, human, local or live), so no driver or unattended run starts it; the stage index needs fixing first

Surface all of them to the user and wait for their go-ahead — do NOT auto-run any. [...]

**Only one `live` stage may run at a time.** S2, S3 are all `gate: live` and runnable: start one, and finish it (its PR merged) before the next — `/stage-run` refuses to start a second `live` stage while another one's branch or worktree is open. This note is all the hook does; the refusal is `/stage-run`'s.
```

Grep over `commands/`, `hooks/`, `skills/staged-rollout/` (tests excluded) for a line naming `human`/`local` together,
then dropping every line that also names `live`:

```
grep -rniE "(human|local)[`* ]*(or|and|/|,)[`* ]*(gate: ?)?`?(human|local)" commands hooks skills/staged-rollout -I | grep -v "/tests/" | grep -viE "live"
skills/staged-rollout/references/templates/RUNNER.md:96:reads as `auto`). Unattended, if it is anything but `auto` — `human`, `local`,
```

The one line is a wrapped sentence: line 97 carries `live` and the unknown-value refusal.

`python3 scripts/validate_plugin.py` → `validate-plugin: OK`. Existing suffixed IDs still parse (an `S12b` row in the
scratch copy kept the same runnable set).

As built:
- `commands/stage-run.md`: lead note and the unattended gate check refuse anything but `auto`; a new **Live check** (step 3) refuses a second `live` stage when preflight 0.5's live-sibling signature finds another `live` stage's `todo` branch or worktree; attended runs refuse an unknown value too; the end announcement names `live`.
- `hooks/session-start`: parses `gate` (`normalize_gate`); a non-`auto` stage is offered `/stage-run`, not `/plan-run`, with its gate noted; an unknown value shows as REFUSED and named; two or more runnable `live` stages add the one-at-a-time note.
- `commands/plan-run.md`: lead note, step 3 (refreshes a stale `.plan/RUNNER.md` by comparing it with the template, not only back-filling), step 5 (fire only `auto`/absent), steps 7 and 8. `remote-driver.md` refusal bullet rewritten to the same rule; the separate "never two `live`" item was not added.
- `templates/RUNNER.md` §4 refuses `live` and unknown values. `templates/PLAN.md` weight-check step and finish step 6 announcement — left to S2 by S0's notes though not in this stage's Artifacts list — now name `live` and the unknown value.
- Fixture: `skills/staged-rollout/tests/fixtures/live-plan/.plan/` (index, ledger, seven stage files).

Re-synced after S3 (#245) and S4 (#243) merged: plan branch merged into the stage branch (only `LEDGER.md` conflicted; both sibling rows kept), then re-run on the merged result — `validate-plugin: OK`, the same fixture hook output (two `live` stages, `canary` REFUSED, one-at-a-time note), and the same single wrapped-line grep hit; 37 tests in `skills/staged-rollout/tests` pass.

Left alone (outside this stage): this plan's own `.plan/PLAN.md` operating protocol still reads "human or local" (a copy of the template made before S2; a plan in flight keeps its copy), and `commands/plan-stages.md` line ~153 ("neither `human` nor `local` changes anything") belongs to S4. S5 reads `plan-run.md` step 5 and `remote-driver.md` as written here.

### S3 Renumbering script

Acceptance output (2026-10-27, worktree `../plan-staged-rollout-s3`, branch `plan-stage-shape-s3`):

- `python -m unittest discover -s skills/staged-rollout/tests` → `Ran 37 tests` / `OK (skipped=2)` (the two skips are the
  real-symlink tests on Windows without symlink rights; a mocked-`is_symlink` test covers the same refusal everywhere).
- `python scripts/validate_plugin.py` → `validate-plugin: OK`
- Both re-run after merging `plan-stage-shape` (S4, PR #243) into the stage branch: 37 tests OK (skipped=2); validator OK.
- Fixture run (scratch copy, `git init`ed; a new `S6 Fix: login` row inserted before S2; S0 done, S1 doing with a
  `BLOCKED.md` section): `renumber_stages.py --slug demo` printed `S6 -> S2`, `S2 -> S3`, `S3 -> S4`, `S4 -> S5`, exit 0.
  Index afterwards: S0, S1, S2 Fix: login, S3 Parser, S4 Writer, S5 Docs (`depends` S3, S4), SF (`depends` S5, S2) — SF last;
  stage files renamed to match; `BLOCKED.md` prose `S3` became `S4`; S0 and S1 kept their numbers and files.

As built: `skills/staged-rollout/scripts/renumber_stages.py --slug <slug> [--plan-dir .plan]`, standard library only. The
caller edits the index (row order is running order; a new stage has a row, a ledger row and a stage file under any unused
plain ID); the script walks the index and gives each unstarted stage the next free plain number above the previous row, then
rewrites file names and every `S<N>` token in `PLAN.md`, `LEDGER.md`, `BLOCKED.md` and the stage files from one mapping, so
swaps cannot collide. Started = non-`todo` status, a `plan-<slug>-s<N>[-redo-K]` ref (local or remote), or a `BLOCKED.md`
section. Everything is validated before the first write (grammar, `depends` order, SF last, paths inside `.plan/`, no
symlinks, UTF-8); a refusal exits 2.

Gotchas for S5 (the fix-insertion path):
- Pass `--slug`; the script reads `git for-each-ref` from the repo above `.plan/`, so it must run where that repo is.
- It does not touch `BRIEF.md` (regenerate in the same commit) and does not reorder ledger rows or notes blocks.
- An **unstarted** stage with a suffixed ID is refused (it cannot tell a new one from an old one); a started one is kept.
- A bare `S<N>` in prose that means something else is rewritten too; read the diff.
- The new fix row needs an ID not already in the index (next free number) — a duplicate is refused.

Template: `references/templates/PLAN.md` "adding a new stage" sentence now names the script. No frozen decision changed.

### S4 Bootstrap: programmes, waits, ordering

Acceptance (2026-10-27, worktree `../plan-staged-rollout-s4`, branch `plan-stage-shape-s4`):
`python3 scripts/validate_plugin.py` → `validate-plugin: OK`.

Edited text, as written:

- `/plan-stages` step 3, **Programme check** (D-1): "Count the outcomes in the confirmed requirements that could each merge
  into `main` on their own — a count of outcomes, never of stages, which are not known until step 4. Two or more: put a
  **Needs you** decision in the batch proposing a **programme** — one plan per outcome, in running order, each closing into
  `main` through its own final PR … Accepted: this bootstrap scaffolds the **first** plan only, its `## Requirements`
  narrowed to that outcome, and step 6 writes the programme index. Declined, or fewer than two outcomes: one plan, nothing
  else changes. When `PROGRAMME.md` already exists on `main` and its first line names this plan, the programme is already
  accepted: scaffold that plan, propose nothing, and ask nothing."
- `/plan-stages` step 4, wait refusal (D-7): "**A wait measured in days is not a stage.** … is refused as a stage … Leave it
  out of the stage index and record it as a **dated follow-up** under `PLAN.md` › Requirements › Out of scope: the date, the
  exact check, the pass condition (with why that threshold …) and what to do if it fails. SF lists it and files it after the
  user's yes. A wait of hours stays inside the stage that needs it."
- `/plan-stages` step 4, numbering (D-9, D-10): "**Number stages in running order.** Stage IDs are plain numbers plus `SF`.
  Number the stages in the order they will run: stages that can run side by side get consecutive numbers, and no stage has a
  lower number than anything it `depends` on. **Reject a suffixed ID** (`S12b`) — renumber instead of suffixing. Existing
  suffixed IDs in a plan already in flight are still read, but never created here."
- `/plan-stages` step 4, group by gate (D-11): `live` added to the gate list ("a driver never fires it, and two `live`
  stages never run at once — where two would land in the same wave, add the edge") and to the grouping rule ("`human` stages
  go at the **front** …, `live` stages at the front or the **end**, and the review stage last … never a `human` or `live`
  stage wedged between two `auto` ones unless a dependency edge genuinely forces it").
- `/plan-stages` step 6, `PROGRAMME.md` creation (D-6): "**Programme index — only when a programme was accepted in step 3.**
  After the subagent returns, write `PROGRAMME.md` at the **repository root** yourself, not into `.plan/` and not through the
  subagent: follow `references/programme-format.md`, one numbered line per plan in running order, each with the outcome in
  plain words and the plan branch `plan-<slug>` as its pointer, the first line being this plan. Leave it uncommitted with the
  rest of the scaffold." Step 9 puts it in the scaffold commit; step 11 names the remaining plans.
- `/plan-close` step 4, **Programme index** (D-6): removes this plan's line (the one pointing at `plan-<slug>`) in its own
  commit on the plan branch, the file itself when it was the last line; no file → nothing; no matching line → reported and
  left. Step 6 offers to plan the next plan: names the first remaining line and gives
  `/plan-staged-rollout:plan-stages <that outcome>`, to run from `main` after the merge; unattended it only prints the line.
- `SKILL.md` › *Decomposing the work*: three bullets (running-order numbering with plain IDs; a wait in days is not a stage;
  several independent outcomes make a programme) before *Standing final review stage*. *Group by gate* already covered `live`
  from S0. › *Closeout*: one paragraph on the programme line removal and the offer to plan the next plan.
- New `skills/staged-rollout/references/programme-format.md`: when a programme exists, where it lives (root, created by the
  first plan's scaffold commit, reaches `main` with that plan's final PR), the line shape (outcome + `plan-<slug>` pointer,
  no state column), and the lifecycle table.

Validator check: `scripts/validate_plugin.py` `TEMPLATE_FILES` only checks `references/templates/`; the new file is outside it
and nothing else in the validator lists reference files, so **no validator change was needed**.

Decisions made inside the stage (none amend `PLAN.md`):
- The wait-follow-up lands in `PLAN.md` › Requirements › Out of scope, because the stage index must not hold it (D-7) and
  Out of scope is where the requirements already name what the plan leaves aside. S5 should have SF read that bullet for
  dated follow-ups.
- `PROGRAMME.md` rides the first plan's scaffold commit and reaches `main` with its final PR; the first plan's closeout
  then removes its own line, so `main` carries the remaining lines. Later plans branch from `main` after that merge.
- The programme proposal is a **Needs you** item in the one bootstrap batch (D-1 answered the trigger, not each programme).

Left for later stages: S5 (SF outcomes, "later plan" and the dated-follow-up handling that consumes `PROGRAMME.md` and the
wait refusal; SF-last rule), S6 (docs, README/`docs/` mention of `PROGRAMME.md`, changelog entry). `templates/PLAN.md` and
the `/plan-stages` step 2 playback were not touched.

### S5 Final review that stays last

Acceptance (2026-10-27, worktree `../plan-staged-rollout-s5`, branch `plan-stage-shape-s5`):

- `python3 scripts/validate_plugin.py` → `validate-plugin: OK`
- `grep -rn "New stage in this plan" skills commands hooks docs README.md scripts` → no output, exit 1 (no remaining outcome).

Edited text, as written:

- `references/templates/stage-f-review.md` — outcomes (replacing "New stage in this plan" and "Spin-off candidate"): "**Issue** — work
  that belongs in its own ticket, including a **dated follow-up** for a wait measured in days. A dated follow-up's body states the
  **date**, the **exact check** to make, the **pass condition** (with the basis for its threshold) and the **action on failure**;
  nothing is scheduled. Attended: file it through `create-issue` after the user's yes. Unattended: file nothing; record it under a
  `closeout will list` heading in this stage's ledger notes, and `/plan-close` copies it into the final PR body." · "**Later plan** —
  work for a later plan of the programme (the programme index, `PROGRAMME.md` at the repository root, names it). Unattended: record
  it under the same `closeout will list` heading." · "**Accepted, won't fix**" (unchanged). A new step reads `PLAN.md` ›
  Requirements › Out of scope for the dated follow-ups `/plan-stages` recorded there (S4's note).
- Same file, the fix exception: "**Exception — a fix.** Never a feature. A fix names the requirement, failing Done check or regression
  it repairs, and is made only with the user present and saying yes, each with its own verification. Fix stages are titled `Fix: …`;
  keep a `#### Fixes` list in this stage's ledger notes — one line per fix — because it is the durable count. **At most 3 per plan: a
  fourth fix is a hard stop in every mode.**" *How a fix runs*: "This stage's own PR lands what it found … the `Fix:` stage's index
  row placed **before SF** (… run the plugin's `skills/staged-rollout/scripts/renumber_stages.py --slug <slug>` …), SF's `depends`
  extended to it, and SF's row set back to `todo`. The fix runs as an ordinary stage; this stage then re-runs **from the top** as a
  redo." *Documentation waits*: "A pass that adds a fix writes none of the Decision triage and README steps below — they run only on
  a clean pass." *Unattended*: "this stage stops and asks: it records a block through the plan's *Recording a block* path instead of
  adding the fix." The Decision triage and README sections each open with a clean-pass-only line; Goal, Acceptance and Artifacts
  rewritten to match.
- `SKILL.md` › *The final review stage* (that section only): the same four outcomes and the fix paragraph; "All three are written
  **only on a clean pass**: a run that adds a fix writes none of them, and the redo does." and "`SF` stays `gate: auto` by default,
  though an unattended run stops and asks when it finds a fix."
- `references/templates/PLAN.md`, Final review stage frozen-decision line: "…each becomes an issue, a later plan (the programme), or an
  explicit "accepted, won't fix" — and NEVER implements and never adds a stage, except a **fix** … at most 3 per plan (a fourth is a
  hard stop in every mode). Unattended, `SF` stops and asks instead of adding a fix."
- `skills/staged-rollout/references/remote-driver.md`, *What the orchestrator refuses*: "**An unattended `SF` that finds a fix stops
  and asks.** … a fired `SF` records a block instead of adding one. The orchestrator reports that block as a fix awaiting the user,
  quotes its `.plan/BLOCKED.md` section, and does not re-fire `SF`, add the `Fix:` stage or choose the fix itself; the user runs
  `/stage-run SF` attended to approve it."
- `commands/plan-run.md` step 6: "A blocked `SF` whose section describes a fix is the unattended final review stopping to ask … say
  so, and leave the fix to the user — run `/stage-run SF` attended, never add a `Fix:` stage or re-fire `SF` from here."

As built: this plan's own `.plan/stage-f-review.md` was not touched (fixed at bootstrap, per the stage file). No frozen decision
changed; D-4 and D-7 are implemented as written. S2's driver text was read first and only appended to.

Left for S6 (outside this stage's Artifacts, found by grep):
- `SKILL.md` line ~120 (*Decomposing the work*: "its three outcomes are…") and line ~442 (*Unattended mode* table row for SF's
  kept-decisions list: still true on a clean pass, may want "and a fix stops and asks").
- `commands/plan-close.md` ~120 still says "any spin-off" in the final PR body; it should list the `closeout will list` items
  (issues, later plans, dated follow-ups) that an unattended SF records.
- `docs/staged-rollout.md` ~334–342 still draws "A spin-off" as an SF outcome and the stage-spawning outcome.
- `commands/plan-stages.md` / `plan-review.md` "three outcomes" are the plan-review outcomes, a different thing; leave.

### S6 Docs, lens checks and changelog
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
