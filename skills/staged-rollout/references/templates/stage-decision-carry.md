# S<N> — Carry decisions out of `.plan/`

<!-- This stage's flags (depends / mode / exec / model / effort / gate /
estimate) live ONLY in the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts.

Scaffolded ONLY when the plan flags line says `plan-dir: delete`; a plan with
`plan-dir: keep` has no such stage, so delete this file's copy there. It takes
the number just below `SF` and `depends` on every other stage but `SF`. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`, and the `DECISIONS.md` format spec, `decisions-format.md`:
> `.plan/decisions-format.md` when the plan carries a copy, otherwise the
> plugin's `skills/staged-rollout/references/decisions-format.md`. The spec
> defines the keep rule, the entry and ADR shapes and where the record lives —
> this file does not restate them.

## Goal

This plan deletes `.plan/` at closeout, and its frozen decisions live nowhere
else. Move the ones still in force into the docs that own them while every
build stage has landed, so the final review stage (`SF`) finds them already
carried and only has to catch what changed afterwards.

## Steps

- [ ] List every frozen decision in `PLAN.md`, including any a stage amended
  (read the ledger notes for amendments).
- [ ] **Find the target**, per the spec's *Where it lives*: an existing ADR
  folder takes ADRs, an existing current-decisions document takes entries,
  and `DECISIONS.md` at the repository root is created only when neither
  exists. If `PLAN.md` already records the target, use it. When the choice
  is ambiguous, ask — unattended, record it as a block through the plan's
  *Recording a block* path.
- [ ] Write the decision map into this stage's ledger notes, one row per
  decision: `<decision> — drop | entry | ADR — <target path>`. Apply the
  spec's keep rule; "drop" needs a one-line reason.
- [ ] Attended, show the whole map and get one yes for the batch. Unattended,
  apply the map as proposed: merging the plan→main PR is the approval.
- [ ] Write each approved `entry` and `ADR` to its target path, in the target's
  own format; an ADR decision also gets an entry that links to it.

## Acceptance

- Every frozen decision in `PLAN.md` appears once in the map in this stage's
  ledger notes, with exactly one outcome and, for `entry` and `ADR`, a target path.
- Each target path in the map exists and holds its entry or ADR
  (`grep -n "<decision title>" <target path>` shows it).
- This stage did not change `SF`'s triage or any closeout step: a decision
  amended after this stage ran is `SF`'s to catch.

## Artifacts

The decisions document or ADR files the map names, and this stage's own
ledger notes. Nothing under `.plan/` other than the ledger.
