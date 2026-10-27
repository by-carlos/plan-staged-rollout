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
| S1 Measure stage size | todo | — | — | — |
| S2 Runners respect `live` | todo | — | — | — |
| S3 Renumbering script | todo | — | — | — |
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
_(empty)_

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
