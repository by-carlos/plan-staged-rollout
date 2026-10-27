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
| S2 Runners respect `live` | todo | — | — | — |
| S3 Renumbering script | doing | no | 2026-10-27 | in progress on plan-stage-shape-s3 |
| S4 Bootstrap: programmes, waits, ordering | todo | — | — | — |
| S5 Final review that stays last | todo | — | — | — |
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
_(empty)_

### S3 Renumbering script
_(empty)_

### S4 Bootstrap: programmes, waits, ordering
_(empty)_

### S5 Final review that stays last
_(empty)_

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
