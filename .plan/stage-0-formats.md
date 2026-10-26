# S0 — Formats (keystone)

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read issue #226 (change 5 defines the `DECISIONS.md` spec).

## Goal

Define every format the other stages consume: the portable `DECISIONS.md` spec,
the brief template, the plan-review lens reference, and the new `PLAN.md`
template sections. S1–S4 and S6 are all written against these.

## Steps

- [ ] Write the portable spec `skills/staged-rollout/references/decisions-format.md` per D-8 and issue #226 change 5.
- [ ] Write the brief template `skills/staged-rollout/references/templates/BRIEF.md` per D-2 and D-3: stamp line first, all six D-2 sections, each naming its source `PLAN.md` section.
- [ ] Write `skills/staged-rollout/references/plan-review.md` per D-4 and D-7: the four lenses with their triggers, the digest cap, the finding rule, the three outcomes.
- [ ] Edit `skills/staged-rollout/references/templates/PLAN.md`: add a Requirements section before Frozen decisions; give the Frozen decisions format a triage group per decision (Decided / Needs you / Default for now) and a pointer to `BRIEF.md`.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `decisions-format.md` contains no occurrence of `plan-staged-rollout`, `.plan/`, `stage` or `SF` (a grep shows none) and its first line is the format-version line.
- `BRIEF.md` has the stamp line and all six D-2 sections.
- `plan-review.md` names four lenses with their triggers.

## Artifacts

- New `skills/staged-rollout/references/decisions-format.md`.
- New `skills/staged-rollout/references/templates/BRIEF.md`.
- New `skills/staged-rollout/references/plan-review.md`.
- `skills/staged-rollout/references/templates/PLAN.md` (Requirements section, triage group per decision, pointer to `BRIEF.md`).
